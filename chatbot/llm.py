"""LLM adapters for the prototype.

``BedrockLLM`` calls Amazon Bedrock (Claude) through the boto3 Converse API -
the same model invocation the Bedrock Flow will make in production.

``MockLLM`` is a deterministic, offline fallback used when no AWS credentials
are available so the flow is always runnable and testable. It dispatches on the
``# ROLE:`` marker embedded in each system prompt, mirroring how a Bedrock Flow
selects which node to execute.

Backend selection via ``LLM_BACKEND``: ``bedrock`` | ``mock`` | ``auto`` (default).
"""

from __future__ import annotations

import json
import os
import re
import sys

# Must run before any boto3 import so Windows gets a working CA bundle.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aws_setup  # noqa: E402
aws_setup.ensure_aws_ssl()
del sys.path[0]

DEFAULT_BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0"
)


class LLMClient:
    """Minimal chat interface shared by every adapter."""

    name = "base"

    def chat(self, system, messages, max_tokens=1024, temperature=0.0):
        raise NotImplementedError


class BedrockLLM(LLMClient):
    name = "bedrock"

    def __init__(self, model_id=None, region=None):
        import boto3

        self.model_id = model_id or DEFAULT_BEDROCK_MODEL_ID
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=(
                region
                or os.environ.get("AWS_REGION")
                or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            ),
        )

    def chat(self, system, messages, max_tokens=1024, temperature=0.0):
        formatted = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages]
        response = self._client.converse(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=formatted,
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        return response["output"]["message"]["content"][0]["text"]


_MOCK_MISSING = "I'm not sure I understood that - let me connect you with a human support agent."


def _role_from(system):
    match = re.search(r"#\s*ROLE:\s*(\w+)", system)
    return match.group(1).lower() if match else ""


def _mock_classify(message):
    msg = message.lower()
    escalation_keywords = [
        "speak to a human", "talk to a human", "speak to a person", "talk to a person",
        "human agent", "human representative", "customer service", "call me",
    ]
    if any(k in msg for k in escalation_keywords):
        return '{"category": "other", "confidence": 0.9, "reason": "customer explicitly wants human support"}'
    # Follow-up indicators without session context: treat as new bug_report
    # (deployed classifier is stateless — no prior turn awareness)
    followup_indicators = [
        "the steps are", "steps are:", "environment is", "i'm on", "i am on",
        "the environment is", "the browser is", "using chrome", "using firefox",
        "on my", "happens when i", "it occurs when",
    ]
    if any(k in msg for k in followup_indicators) and not any(
        k in msg for k in ["bug", "broken", "error", "crash", "doesn't work", "does not work", "glitch", "freeze", "not loading", "wrong item", "missing order"]
    ):
        return '{"category": "bug_report", "confidence": 0.85, "reason": "detail-providing message without session context"}'
    bug_keywords = [
        "bug", "broken", "error", "crash", "doesn't work", "does not work",
        "glitch", "freeze", "not loading", "wrong item", "missing order",
        "missing", "won't let me", "cannot", "can't",
    ]
    if any(k in msg for k in bug_keywords):
        return '{"category": "bug_report", "confidence": 0.97, "reason": "bug language detected"}'
    faq_keywords = [
        "order", "shipping", "ship", "delivery", "return", "refund", "payment",
        "cancel", "track", "discount", "coupon", "account", "password", "how do",
        "where is", "when will", "do you", "charged", "charge", "card",
        "when is", "can i", "where can",
    ]
    if any(k in msg for k in faq_keywords):
        # Guardrail + no FAQ coverage -> other (matches deployed behavior)
        if "gift wrapping" in msg or "wrap" in msg:
            return '{"category": "other", "confidence": 0.7, "reason": "not covered by FAQ, redirected to human support"}'
        return '{"category": "faq", "confidence": 0.95, "reason": "platform topic detected"}'
    return '{"category": "other", "confidence": 0.8, "reason": "no known topic detected"}'


def _mock_bug_collector(system, messages):
    match = re.search(r"asked about:\s*(.+)", system)
    target = match.group(1).strip() if match else "description"
    last_user = [m for m in messages if m["role"] == "user"][-1]["content"]
    return json.dumps({target: last_user})


def _mock_faq(system, message):
    faq_match = re.search(r"<faq>(.*?)</faq>", system, re.S)
    text = faq_match.group(1) if faq_match else ""
    msg = message.lower()
    msg_words = [w for w in re.split(r"\W+", msg) if len(w) > 3]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "⸻":
            continue
        if stripped.startswith(("-", "Q:", "A:")) or stripped[0].isdigit():
            continue
        if len(stripped) < 40:
            section = stripped.lower()
            words = [w for w in re.split(r"\W+", section) if len(w) > 3]
            if any(w in msg for w in words) or any(w in section for w in msg_words):
                return (
                    f"Good question - that's covered under our FAQ section \"{stripped}\". "
                    "Let me pull up the details for you."
                )
    return (
        "Our FAQ covers orders, shipping, returns and payments. I'd suggest checking those "
        "sections, or I can pass you to a human agent for the specifics."
    )


def _mock_redirect(message):
    return (
        "I'm sorry, I'm not able to help with that request here. Please call our human "
        "support line at 1-800-555-0199 (Mon-Fri 9am-6pm) and a representative will assist you."
    )


class MockLLM(LLMClient):
    name = "mock"

    def chat(self, system, messages, max_tokens=1024, temperature=0.0):
        role = _role_from(system)
        message = messages[-1]["content"] if messages else ""
        if role == "classifier":
            return _mock_classify(message)
        if role == "bug_collector":
            return _mock_bug_collector(system, messages)
        if role == "faq":
            return _mock_faq(system, message)
        if role == "redirect":
            return _mock_redirect(message)
        return _MOCK_MISSING


def _bedrock_available():
    """Return True only when Bedrock can actually be reached, not just when
    credentials happen to exist.  On Windows Python 3.14 the default cert
    bundle is empty so we catch SSLError here and fall back to mock."""
    try:
        import boto3  # noqa: PLC0415 (local import keeps mock fast)

        region = (
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )
        session = boto3.Session()
        if session.get_credentials() is None:
            return False
        client = session.client("bedrock-runtime", region_name=region)
        # Do a lightweight shape-check so a network-level failure is caught
        # before any application code sees the exception.
        client.list_foundation_models(
            byOutputModality="TEXT",
            byInferenceType="ON_DEMAND",
        )
        return True
    except Exception:
        return False


def get_llm(backend=None):
    """Return an LLMClient. ``backend`` in {"bedrock", "mock", "auto"}; auto
    prefers Bedrock when credentials exist and falls back to the mock.
    When ``backend="bedrock"`` but the service is unreachable (e.g. missing
    SSL certs on Windows), prints a diagnostic and returns MockLLM instead."""
    backend = (backend or os.environ.get("LLM_BACKEND", "auto")).strip().lower()
    if backend == "mock":
        return MockLLM()
    if backend == "bedrock":
        if not _bedrock_available():
            print(
                "[WARN] Bedrock unavailable (no credentials or network error);\n"
                "       falling back to mock backend.\n"
                "       Set SSL_CERT_FILE to your CA bundle, or use --backend mock.",
                file=sys.stderr,
            )
            return MockLLM()
        return BedrockLLM()
    if backend == "auto":
        return BedrockLLM() if _bedrock_available() else MockLLM()
    raise ValueError(f"unknown LLM backend: {backend!r} (expected bedrock, mock or auto)")