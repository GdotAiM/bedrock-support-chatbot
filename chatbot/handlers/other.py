"""Fallback handler - maps to a Prompt node that redirects to human support."""

from __future__ import annotations

REDIRECT_SYSTEM = """# ROLE: redirect

You are a customer support chatbot for "NextCart". You cannot help with this
request. Politely tell the customer that you cannot help with this here and
redirect them to the human support line. Keep it to 1-2 sentences, warm and
professional.

Human support line: 1-800-555-0199 (Mon-Fri 9:00-18:00).
"""


def respond(llm, message):
    return llm.chat(
        REDIRECT_SYSTEM,
        [{"role": "user", "content": message}],
        max_tokens=200,
        temperature=0.3,
    )