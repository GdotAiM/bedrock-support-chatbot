"""``create_bug_report`` tool - the local twin of the Lambda-backed tool that the
Bedrock Agent uses in production.

In Bedrock: this code runs as a Lambda function (``lambda_handler`` below) that
writes a ticket to DynamoDB.
Locally: the same logic runs in-process against an in-memory store, or against
DynamoDB when the ``BUG_TICKET_TABLE`` environment variable is set.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    def __init__(self):
        self.items = []

    def save(self, ticket):
        self.items.append(ticket)
        return ticket

    def __len__(self):
        return len(self.items)


class DynamoDBStore:
    def __init__(self, table_name):
        import boto3

        self._table = boto3.resource("dynamodb").Table(table_name)

    def save(self, ticket):
        self._table.put_item(Item=ticket)
        return ticket


_MEMORY = MemoryStore()


def get_store():
    table = os.environ.get("BUG_TICKET_TABLE")
    if table:
        return DynamoDBStore(table)
    return _MEMORY


def create_bug_report(user_message, **details):
    """Create a support ticket and persist it. Returns the ticket dict."""
    ticket = {
        "ticket_id": f"TKT-{uuid.uuid4().hex[:8].upper()}",
        "user_message": user_message,
        "details": {k: v for k, v in details.items() if v not in (None, "")},
        "status": "open",
        "created_at": _now(),
    }
    get_store().save(ticket)
    return ticket


def _extract_payload(event):
    # Agents Classic: {"parameters": [{"name": ..., "value": ...}, ...]}
    if isinstance(event, dict) and isinstance(event.get("parameters"), list):
        return {
            p.get("name"): p.get("value", "")
            for p in event["parameters"]
            if isinstance(p, dict) and p.get("name")
        }
    if isinstance(event, dict) and "toolUse" in event:
        return event["toolUse"].get("input", {})
    if isinstance(event, dict) and "input" in event:
        return event["input"]
    return event or {}


def lambda_handler(event, context):
    """Lambda entry point. Accepts an Agents Classic ``parameters`` list, a
    Bedrock Agent ``toolUse`` event, a plain ``{"input": {...}}`` payload, or a
    raw ticket dict. Returns the Agents Classic ``functionResponse`` shape."""
    payload = _extract_payload(event)
    ticket = create_bug_report(
        user_message=payload.get("description") or payload.get("user_message", ""),
        **{k: v for k, v in payload.items() if k not in ("user_message",)},
    )
    body = json.dumps({"ticketId": ticket["ticket_id"], "status": "OPEN"})
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", "bug-report-actions")
            if isinstance(event, dict)
            else "bug-report-actions",
            "function": event.get("function", "create_bug_report")
            if isinstance(event, dict)
            else "create_bug_report",
            "functionResponse": {"responseBody": {"TEXT": {"body": body}}},
        },
    }