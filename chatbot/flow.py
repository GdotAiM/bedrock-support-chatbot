"""SupportChatbotFlow - orchestrates the pipeline exactly like the Bedrock Flow:

    Prompt(ClassifyMessage) -> Condition(RouteByCategory) -> one of
        Agent(BugReport) | Prompt(FAQ) | Prompt(HumanSupport)

Every ``handle()`` records a node trace so you can see what each Bedrock node
would produce, which is useful when comparing against the deployed flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .classify import Classification, classify
from .handlers import bug_report, faq, other
from .llm import get_llm
from .route import route


@dataclass
class FlowResult:
    message: str
    classification: Classification
    handler: str
    response: str
    ticket: dict | None = None
    trace: list = field(default_factory=list)


class SupportChatbotFlow:
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        self.sessions = {}
        self.session_meta = {}

    def handle(self, message, session_id="default"):
        """Classify, route and respond to one customer message."""
        active = self.sessions.get(session_id)
        if active is not None and not active.complete:
            classification = self.session_meta.get(session_id, {}).get("classification") or Classification(
                "bug_report", 0.0, "resumed bug intake"
            )
            result = bug_report.handle(
                self.llm,
                message,
                session=active,
                original_message=active.fields.get("description") or message,
            )
            trace = [
                ("resume_bug_intake", {"session": session_id}),
                ("bug_report", {"ticket": result.ticket, "fields": active.fields}),
            ]
            return FlowResult(message, classification, "bug", result.reply, ticket=result.ticket, trace=trace)

        trace = [("classify", {"message": message})]
        classification = classify(self.llm, message)
        trace.append(
            ("route", {"category": classification.category, "confidence": classification.confidence})
        )

        handler = route(classification)
        trace.append(("route->handler", handler))

        if handler == "bug":
            session = self.sessions.setdefault(session_id, bug_report.BugSession())
            self.session_meta[session_id] = {"classification": classification}
            result = bug_report.handle(
                self.llm,
                message,
                session=session,
                original_message=session.fields.get("description") or message,
            )
            trace.append(("bug_report", {"ticket": result.ticket, "fields": session.fields}))
            return FlowResult(message, classification, handler, result.reply, ticket=result.ticket, trace=trace)

        if handler == "faq":
            response = faq.answer(self.llm, message)
            trace.append(("faq", {"answer": response}))
            return FlowResult(message, classification, handler, response, trace=trace)

        response = other.respond(self.llm, message)
        trace.append(("redirect", {"reply": response}))
        return FlowResult(message, classification, handler, response, trace=trace)

    def reset_session(self, session_id="default"):
        self.sessions.pop(session_id, None)
        self.session_meta.pop(session_id, None)