"""Shared Bedrock Flow invoke helpers for eval runners."""

from __future__ import annotations

import boto3
import os
import uuid
from typing import Any

SID_MARKER = "__SID__"

OUTPUT_NODE_TO_CATEGORY = {
    "BugOutput": "bug_report",
    "FAQOutput": "faq",
    "OtherOutput": "other",
}

# ARNs for the deployed us-east-1 infrastructure
# HARNESS_ARN must be set via environment variable for security.
# Get this from your AWS Console → Bedrock → AgentCore → Harnesses
BUG_HARNESS_ARN = os.environ.get(
    "BUG_HARNESS_ARN",
    "<HARNESS_ARN_FROM_AWS_CONSOLE>"
)
FLOW_ID = os.environ.get("BEDROCK_FLOW_ID", "<YOUR_FLOW_ID>")
FLOW_ALIAS_ID = os.environ.get("BEDROCK_FLOW_ALIAS_ID", "<YOUR_FLOW_ALIAS_ID>")


def _pad_session(session_id: str) -> str:
    """Pad session ID to minimum 33 chars, matching the proxy Lambda."""
    while len(session_id) < 33:
        session_id += "0"
    return session_id


def wrap_session(session_id: str, message: str) -> str:
    return f"{SID_MARKER}{session_id}{SID_MARKER}{message}"


def is_terminal_bug_response(text: str) -> bool:
    if not text:
        return False
    upper = text.upper()
    return "TKT-" in upper or ("TICKET" in upper and "CREATED" in upper)


def _get_flow_client(region: str):
    """Create the correct bedrock-agent-runtime client with SSL fixed."""
    import sys
    sys.path.insert(0, ".")
    import aws_setup
    aws_setup.ensure_aws_ssl()
    del sys.path[0]
    return boto3.client("bedrock-agent-runtime", region_name=region)


def _get_harness_client(region: str):
    """Create the bedrock-agentcore client for direct harness invocation."""
    import sys
    sys.path.insert(0, ".")
    import aws_setup
    aws_setup.ensure_aws_ssl()
    del sys.path[0]
    return boto3.client("bedrock-agentcore", region_name=region)


def _extract_category_from_trace(resp) -> str | None:
    """Parse flow trace events to determine which Output node fired."""
    trace = resp.get("responseStream", [])
    for event in trace:
        if "flowTraceEvent" not in event:
            continue
        node_trace = event["flowTraceEvent"].get("trace", {}).get("nodeInputTrace", {})
        node_name = node_trace.get("nodeName", "") if isinstance(node_trace, dict) else ""
        if node_name in OUTPUT_NODE_TO_CATEGORY:
            return OUTPUT_NODE_TO_CATEGORY[node_name]
    return None


def _extract_text_from_stream(resp) -> str:
    """Extract the assistant's final text response from a flow stream."""
    parts = []
    for event in resp.get("responseStream", []):
        if "flowOutputEvent" in event:
            doc = event["flowOutputEvent"].get("content", {}).get("document")
            if doc:
                parts.append(doc)
        elif "flowMultiTurnInputRequestEvent" in event:
            doc = event["flowMultiTurnInputRequestEvent"].get("content", {}).get("document")
            if doc:
                parts.append(doc)
    return "".join(parts)


def _extract_text_from_harness_stream(resp) -> str:
    """Extract streamed text deltas from a harness invoke response."""
    parts = []
    for event in resp.get("stream", []):
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if isinstance(delta, dict) and "text" in delta:
                parts.append(delta["text"])
    return "".join(parts)


def invoke_flow_once(
    client,
    prompt: str = "",
    *,
    enable_trace: bool = False,
) -> dict[str, Any]:
    """Single-shot invoke through the deployed Bedrock Flow."""
    region = client.meta.region_name
    try:
        resp = client.invoke_flow(
            flowIdentifier=FLOW_ID,
            flowAliasIdentifier=FLOW_ALIAS_ID,
            enableTrace=enable_trace or True,
            inputs=[
                {
                    "nodeName": "FlowInput",
                    "nodeOutputName": "document",
                    "content": {"document": prompt},
                }
            ],
        )
    except client.exceptions.ResourceNotFoundException:
        # Flow alias may have changed — try looking it up by name
        agent_client = boto3.client("bedrock-agent", region_name=region)
        flows = agent_client.list_flows(maxResults=50)
        for f in flows.get("flowSummaries", []):
            if "customer-support-chatbot" in f.get("name", ""):
                fid = f.get("flowIdentifier") or FLOW_ID
                break
        else:
            fid = FLOW_ID
        resp = client.invoke_flow(
            flowIdentifier=fid,
            flowAliasIdentifier=FLOW_ALIAS_ID,
            enableTrace=enable_trace or True,
            inputs=[
                {
                    "nodeName": "FlowInput",
                    "nodeOutputName": "document",
                    "content": {"document": prompt},
                }
            ],
        )
    category = _extract_category_from_trace(resp)
    response = _extract_text_from_stream(resp)
    return {
        "category": category or "other",
        "response": response,
        "turns": 1,
        "session_id": None,
        "multi_turn": False,
    }


def invoke_harness_direct(
    client,
    prompt: str,
    follow_ups: list[str] | None = None,
    *,
    session_id: str | None = None,
    max_turns: int = 4,
) -> dict[str, Any]:
    """Invoke the AgentCore harness directly for multi-turn bug tests.

    Bypasses the Bedrock Flow + proxy Lambda entirely, calling the AgentCore
    harness directly via bedrock-agentcore client. This saves ~15-30s on
    3-turn bug tests compared to the flow path.
    """
    region = client.meta.region_name
    harness_client = _get_harness_client(region)
    sid = _pad_session(session_id or uuid.uuid4().hex)
    messages = [prompt] + list(follow_ups or [])
    response_parts = []
    turns = 0

    for message in messages[:max_turns]:
        wrapped = wrap_session(sid, message)
        resp = harness_client.invoke_harness(
            harnessArn=BUG_HARNESS_ARN,
            runtimeSessionId=sid,
            messages=[{"role": "user", "content": [{"text": wrapped}]}],
        )
        text = _extract_text_from_harness_stream(resp)
        response_parts.append(text)
        turns += 1
        if is_terminal_bug_response(text):
            break

    return {
        "category": "bug_report",
        "response": "\n".join(response_parts),
        "turns": turns,
        "session_id": sid,
        "multi_turn": True,
    }
