"""Condition node - maps to a Bedrock Flows Condition node.

Routes on the classifier output to exactly one downstream handler:

    bug_report        -> bug   (Bedrock Agent node with tool use)
    bug_followup      -> bug   (same handler — already in bug-intake mode)
    faq               -> faq   (Prompt node with embedded reference document)
    other             -> redirect (Prompt node -> human support line)
"""

HANDLERS = {
    "bug_report": "bug",
    "bug_followup": "bug",
    "faq": "faq",
    "other": "redirect",
}

DEFAULT_HANDLER = "redirect"


def route(classification):
    """Return the handler name for a Classification (mirrors the Condition node)."""
    if not classification.is_valid:
        return DEFAULT_HANDLER
    return HANDLERS.get(classification.category, DEFAULT_HANDLER)