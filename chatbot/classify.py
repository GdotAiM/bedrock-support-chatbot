"""Classification node - maps to the first Prompt node in the Bedrock Flow.

The LLM labels an inbound message as ``bug_report``, ``bug_followup``,
``faq`` or ``other`` and returns JSON. In Bedrock Flows the same prompt runs
as a Prompt node whose JSON output feeds the downstream Condition node.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

CATEGORIES = ("bug_report", "bug_followup", "faq", "other")

CLASSIFIER_SYSTEM = """# ROLE: classifier

You are the message classifier of a customer support chatbot for an online shop
called "NextCart". You label every inbound customer message with exactly one of
four categories:

- bug_report: the customer reports something broken, erroring or unexpected
  (crashes, error messages, pages not loading, wrong or missing items,
  checkout failing, account problems). First mention of a bug.
- bug_followup: the user provides missing details for a previously reported
  bug (e.g., "the steps are...", "environment is Chrome", "I clicked pay and
  got an error", "this happens on my iPhone"). Look for imperative detail
  delivery without a new problem statement.
- faq: the customer asks a question about how the platform works
  (orders, shipping, returns, refunds, payments, account settings, policies).
- other: anything that is neither a bug report nor a platform question
  (greetings, off-topic, requests to speak to a human).

Rules:
- If in doubt between bug_report and platform_question, choose bug_report when
  the customer describes something that failed or misbehaved; choose faq when
  they are clearly asking "how to", "where" or "when".
- A message that states a problem AND provides follow-up details is still
  bug_report (the first mention takes priority).
- Never invent categories. Always pick exactly one of the four.
- Respond with a single JSON object and nothing else:
  {"category": "<bug_report|bug_followup|faq|other>", "confidence": <0-1>, "reason": "<short rationale>"}
"""


def build_messages(message):
    return [{"role": "user", "content": message}]


def _extract_json(text):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in classifier output: {text!r}")
    return json.loads(text[start : end + 1])


@dataclass
class Classification:
    category: str
    confidence: float
    reason: str

    @property
    def is_valid(self):
        return self.category in CATEGORIES


def classify(llm, message):
    """Run the classifier node and return a ``Classification``."""
    raw = llm.chat(CLASSIFIER_SYSTEM, build_messages(message), max_tokens=128, temperature=0.0)
    try:
        data = _extract_json(raw)
        category = str(data.get("category", "other")).strip().lower()
        if category not in CATEGORIES:
            category = "other"
        return Classification(
            category=category,
            confidence=float(data.get("confidence", 0.0)),
            reason=str(data.get("reason", "")),
        )
    except Exception:
        return Classification(category="other", confidence=0.0, reason="failed to parse classifier output")