"""FAQ handler - maps to a Prompt node whose system prompt embeds the FAQ
reference document (in the console: model context / reference documents)."""

from __future__ import annotations

from pathlib import Path

FAQ_PATH = Path(__file__).resolve().parent.parent / "faq" / "online_shop_faq.md"
FAQ_TEXT = FAQ_PATH.read_text(encoding="utf-8")

FAQ_SYSTEM = """# ROLE: faq

You are a friendly support agent for "NextCart", an online shop. Answer the
customer's question using ONLY the FAQ below. Do not invent shipping times,
prices or policies.

<faq>
{faq}
</faq>

If the FAQ does not cover the question, say you are not sure and offer to
connect the customer to human support.
"""


def answer(llm, message, history=None):
    """Answer a platform question using the embedded FAQ document."""
    history = history or []
    system = FAQ_SYSTEM.format(faq=FAQ_TEXT)
    messages = history + [{"role": "user", "content": message}]
    return llm.chat(system, messages, max_tokens=512, temperature=0.3)