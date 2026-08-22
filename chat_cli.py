#!/usr/bin/env python3
"""Chat CLI for the deployed Bedrock Flow (multi-turn bug report collection).

Each message is sent through invoke_flow with a client-owned session token
prepended (__SID__<sid>__SID__). The flow strips it before classification and
the proxy reuses it as the AgentCore harness runtimeSessionId, so the harness
remembers prior turns and keeps asking until it has enough detail to create a
ticket. Exit with Ctrl+C, 'exit', or 'quit'.

Usage:
    python chat_cli.py [--flow-id 4ILATZYV8W] [--alias-id REUBFKO09A]
"""

import argparse
import os
import sys
import uuid

import boto3

# Windows Python 3.14 ships an empty default CA bundle; inject system certs
# before boto3 is imported so HTTPS calls to Bedrock work without manual
# SSL_CERT_FILE configuration.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aws_setup  # noqa: E402
aws_setup.ensure_aws_ssl()
del sys.path[0]

SID_MARKER = "__SID__"


def invoke_flow(client, flow_id, alias_id, message, sid):
    payload = SID_MARKER + sid + SID_MARKER + message
    resp = client.invoke_flow(
        flowIdentifier=flow_id,
        flowAliasIdentifier=alias_id,
        inputs=[
            {
                "nodeName": "FlowInput",
                "nodeOutputName": "document",
                "content": {"document": payload},
            }
        ],
    )
    text = ""
    for event in resp.get("responseStream", []):
        if "flowOutputEvent" in event:
            text = event["flowOutputEvent"].get("content", {}).get("document") or text
        if "flowMultiTurnInputRequestEvent" in event:
            text = event["flowMultiTurnInputRequestEvent"].get("content", {}).get("document") or text
    return text


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--flow-id", default="R3E15XRIYH")
    p.add_argument("--alias-id", default="VVEANF35OL")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--session", default=None, help="Reuse a session token (optional)")
    args = p.parse_args()

    client = boto3.client("bedrock-agent-runtime", region_name=args.region)
    sid = args.session or uuid.uuid4().hex
    print(f"session: {sid}")
    print("Type your messages (bug reports are collected over multiple turns). exit/quit to stop.\n")

    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message or message.lower() in ("exit", "quit"):
            break
        try:
            reply = invoke_flow(client, args.flow_id, args.alias_id, message, sid)
        except Exception as exc:  # noqa: BLE001 - surface flow errors
            print(f"[FLOW_ERROR] {type(exc).__name__}: {exc}")
            continue
        print("bot> " + (reply.strip() or "(no response)") + "\n")


if __name__ == "__main__":
    sys.exit(main())
