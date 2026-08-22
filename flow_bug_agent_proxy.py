import json
import os
import uuid

import boto3

HARNESS_ARN = os.environ["HARNESS_ARN"]
client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))

SID_MARKER = "__SID__"


def lambda_handler(event, context):
    raw = _find_input(event, "message")
    if not raw:
        return _resp("I didn't receive your message. Could you repeat it?")

    message, session_id = _split_session(raw)
    if session_id is None:
        session_id = _pad_session("flow-" + uuid.uuid4().hex)

    text = ""
    try:
        resp = client.invoke_harness(
            harnessArn=HARNESS_ARN,
            runtimeSessionId=session_id,
            messages=[{"role": "user", "content": [{"text": message}]}],
        )
        for ev in resp.get("stream", []):
            if "contentBlockDelta" in ev:
                delta = ev["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    text += delta["text"]
    except Exception as e:
        print("HARNESS_ERROR:", type(e).__name__, str(e))
        return _resp(
            "I'm sorry, I couldn't process the bug report right now. "
            "Please try again in a moment, or contact support at 1-800-555-0199."
        )

    return _resp(text.strip() or "I'm sorry, I couldn't process the bug report right now.")


def _split_session(raw):
    if isinstance(raw, str) and raw.startswith(SID_MARKER):
        rest = raw[len(SID_MARKER):]
        idx = rest.find(SID_MARKER)
        if idx != -1 and rest[:idx]:
            return rest[idx + len(SID_MARKER):], rest[:idx]
    return raw, None


def _pad_session(session_id):
    while len(session_id) < 33:
        session_id += "0"
    return session_id


def _resp(text):
    return text


def _find_input(event, name):
    try:
        inputs = event.get("node", {}).get("inputs", [])
        for item in inputs:
            if isinstance(item, dict) and item.get("name") == name:
                value = item.get("value")
                if isinstance(value, str):
                    return value
                return json.dumps(value, ensure_ascii=False)
    except Exception:
        pass
    return None
