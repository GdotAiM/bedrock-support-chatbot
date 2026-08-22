import json
import os
import uuid
from datetime import datetime, timezone
import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

REQUIRED_FIELDS = ("description", "stepsToReproduce", "environment")

def lambda_handler(event, context):
    print("EVENT:", json.dumps(event, indent=2, default=str))

    if event.get("messageVersion") == "1.0" and event.get("function") == "create_bug_report":
        params = event.get("parameters") or []
        body = {
            p.get("name"): p.get("value")
            for p in params
            if isinstance(p, dict) and p.get("name") is not None
        }
        ticket = _create_ticket(body)
        if "error" in ticket:
            return _agent_response(event, ticket)
        return _agent_response(event, {"ticketId": ticket["ticketId"], "status": ticket["status"]})

    body = _extract_args(event)
    return _create_ticket(body)


def _extract_args(event):
    if isinstance(event, dict):
        for key in ("input", "arguments", "args", "body"):
            if isinstance(event.get(key), dict):
                return event[key]
        return event
    return {}


def _create_ticket(body):
    description = (body.get("description") or "").strip()
    steps = (body.get("stepsToReproduce") or "").strip()
    environment = (body.get("environment") or "").strip()

    if not description:
        return {"error": "missing", "field": "description"}

    ticket_id = str(uuid.uuid4())
    item = {
        "ticketId": ticket_id,
        "description": description,
        "stepsToReproduce": steps,
        "environment": environment,
        "status": "OPEN",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    table.put_item(Item=item)

    return {"ticketId": ticket_id, "status": "OPEN"}


def _agent_response(event, obj):
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "function": event.get("function"),
            "functionResponse": {
                "responseBody": {
                    "TEXT": {
                        "body": json.dumps(obj)
                    }
                }
            },
        },
    }