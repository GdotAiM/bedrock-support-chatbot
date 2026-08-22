"""Bug report handler - maps to the Bedrock Agents node with tool use.

Collects the required ticket fields through a multi-turn conversation, then
calls the ``create_bug_report`` tool (a Lambda + DynamoDB function in Bedrock, a
local function here) to persist the ticket.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..tools.create_bug_report import create_bug_report

REQUIRED_FIELDS = [
    "description",
    "stepsToReproduce",
    "environment",
]

QUESTIONS = {
    "description": "Thanks - can you tell me in a few words what went wrong?",
    "stepsToReproduce": "What steps did you take right before the problem happened?",
    "environment": "What browser, operating system, or device are you using?",
}

COLLECTOR_SYSTEM = """# ROLE: bug_collector

You are the bug-intake step of a customer support chatbot. The customer was
asked about: {target}

Extract the value for that field from the customer's latest message and respond
with a single JSON object and nothing else:
{{"{target}": "<extracted value>"}}

If the message does not contain the information, respond with an empty string
value for that field.
"""


@dataclass
class BugSession:
    fields: dict = field(default_factory=dict)
    target: str = "description"

    @property
    def complete(self):
        return all(self.fields.get(f) for f in REQUIRED_FIELDS)

    def next_target(self):
        for field in REQUIRED_FIELDS:
            if not self.fields.get(field):
                return field
        return None


def _extract(llm, session, message):
    raw = llm.chat(
        COLLECTOR_SYSTEM.format(target=session.target),
        [{"role": "user", "content": message}],
        max_tokens=256,
        temperature=0.0,
    )
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1]) if start != -1 and end != -1 else {}
    except Exception:
        data = {}
    value = str(data.get(session.target, "") or "").strip()
    if value:
        session.fields[session.target] = value


@dataclass
class BugResult:
    reply: str
    ticket: dict | None = None
    session: BugSession | None = None


def handle(llm, message, session=None, original_message=None):
    """One turn of the bug-intake conversation. Returns a ``BugResult``.

    ``original_message`` is the first message that opened the ticket; it is
    stored on the ticket so support sees the whole context.
    """
    session = session or BugSession()
    _extract(llm, session, message)

    target = session.next_target()
    if target is None:
        ticket = create_bug_report(
            user_message=original_message or message,
            **session.fields,
        )
        summary = (
            f"Your ticket {ticket['ticket_id']} has been created. Our team will "
            f"investigate and follow up at {ticket['details'].get('email', 'your email')}."
        )
        return BugResult(reply=summary, ticket=ticket, session=session)

    session.target = target
    return BugResult(reply=QUESTIONS[target], session=session)