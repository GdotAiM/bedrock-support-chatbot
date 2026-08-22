# Condition Node Rules (RouteByCategory Node)

This file corresponds to the **RouteByCategory** Condition node in the deployed
Bedrock Flow. It mirrors the routing logic in `chatbot/route.py`.

---

## Routing Table

| Category          | Handler      | Description                           |
|-------------------|--------------|---------------------------------------|
| `bug_report`      | BugAgent     | Multi-turn bug-intake via AgentCore   |
| `bug_followup`    | BugAgent     | Resumes existing bug-intake session   |
| `faq`             | AnswerFAQ    | Answers using embedded FAQ document   |
| `other`           | HumanSupport | Redirects to phone support            |
| *(invalid / default)* | HumanSupport | Fallback for unclassifiable input   |

---

## Condition Expressions (exact string match)

```
IF category == "bug_report"        → route to BugAgent
IF category == "bug_followup"      → route to BugAgent
IF category == "faq"               → route to AnswerFAQ
ELSE                               → route to HumanSupport
```

## Invalid Output Handling

If the classifier returns a JSON object whose `category` field is not one of
the four expected values, `NormalizeCategory` (InlineCode node) falls back to
bare-word matching before the Condition node sees it. If bare-word matching
also fails, the Condition's default branch sends the message to **HumanSupport**.

---

## Evidence

- Flow definition: `bedrock/flow_definition_e1.json` (search for `RouteByCategory`)
- Local mirror: `chatbot/route.py` (HANDLERS dict + `route()` function)
