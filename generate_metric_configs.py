#!/usr/bin/env python3
"""Generate eval metric configurations for Bedrock console."""
import json

metrics = [
    {
        "name": "fluency",
        "instructions": """You are evaluating the FLUENCY of a customer support response. Score based on how natural, readable, and well-structured the response is.

Rules:
- Look for natural sentence flow and proper grammar
- Penalize choppy, disjointed, or template-like phrasing
- Check that the response reads like a real human wrote it
- Ignore factual accuracy (that's measured separately)
- Focus on writing quality and readability

Focus: Does the response read naturally and fluently?""",
        "variable": "prediction",
        "schema": [
            {"value": 0, "label": "Unintelligible", "description": "Response is garbled, incomplete, or unreadable"},
            {"value": 1, "label": "Poor", "description": "Response is difficult to follow with awkward phrasing"},
            {"value": 2, "label": "Acceptable", "description": "Response is understandable but has noticeable flaws"},
            {"value": 3, "label": "Excellent", "description": "Response is natural, smooth, and professionally written"}
        ]
    },
    {
        "name": "coherence",
        "instructions": """You are evaluating the COHERENCE of a multi-turn conversation. Score based on whether the response makes logical sense given the conversation context.

Rules:
- Check that the response logically follows from the previous message
- Verify the assistant maintains consistent persona throughout
- Penalize responses that contradict earlier statements
- For single-turn tests, check internal logical consistency
- Focus on whether the conversation flows naturally

Focus: Does the response make logical sense in context?""",
        "variable": "prediction",
        "schema": [
            {"value": 0, "label": "Incoherent", "description": "Response contradicts itself or makes no logical sense"},
            {"value": 1, "label": "Partially coherent", "description": "Response has some logical gaps or inconsistencies"},
            {"value": 2, "label": "Mostly coherent", "description": "Response is mostly logical with minor gaps"},
            {"value": 3, "label": "Logically consistent", "description": "Response flows naturally and maintains logical consistency"}
        ]
    },
    {
        "name": "helpfulness",
        "instructions": """You are evaluating how HELPFUL a customer support response is. Score based on whether it actually helps the customer resolve their issue.

Rules:
- A helpful response addresses the customer's stated problem
- For bug reports, confirm ticket creation was offered or done
- For FAQs, provide the requested information or acknowledge gap
- For other requests, offer escalation path
- Don't penalize for tone — focus on whether the response solves the problem

Focus: Does the response meaningfully address the customer's need?""",
        "variable": "prediction",
        "schema": [
            {"value": 0, "label": "No help", "description": "Response doesn't address the customer's issue at all"},
            {"value": 1, "label": "Minimal help", "description": "Response acknowledges but provides little value"},
            {"value": 2, "label": "Somewhat helpful", "description": "Response partially addresses the issue"},
            {"value": 3, "label": "Fully helpful", "description": "Response completely addresses the customer's need"}
        ]
    },
    {
        "name": "groundedness",
        "instructions": """You are evaluating whether a customer support response is GROUNDED in the FAQ document embedded in the system prompt. Score based ONLY on factual claims about policies, shipping, returns, payments, etc.

Rules:
- If the FAQ doesn't cover a topic, saying so and escalating is CORRECT (not hallucination)
- Minor rephrasing of FAQ content is acceptable
- Strictly penalize invented numbers, timelines, or specific policy details
- Only evaluate factual claims; ignore tone and style

Focus: Does the prediction make any factual claims about shop policies that are NOT in the FAQ?""",
        "variable": "prediction",
        "schema": [
            {"value": 0, "label": "Contradicts", "description": "Response directly contradicts the FAQ"},
            {"value": 1, "label": "Hallucinates", "description": "Makes up information not found in the FAQ"},
            {"value": 2, "label": "Partially grounded", "description": "Mostly correct but includes some unsupported claims"},
            {"value": 3, "label": "Fully grounded", "description": "All factual claims supported by FAQ, no inventions"}
        ]
    },
    {
        "name": "routing_accuracy",
        "instructions": """You are evaluating whether the model correctly ROUTED the customer message to the right category. Score based on whether the response type matches what the customer needed.

Categories:
- bug_report: Customer reports a technical issue, error, crash, or failure
- faq: Customer asks a common question about products, shipping, returns, payments
- other: Everything else (greetings, jokes, weather, etc.)

Rules:
- If FAQ doesn't cover a topic and model escalates, that's CORRECT routing (other)
- Multi-turn bug collection is correct even if only 1 turn completed
- Focus on whether the RESPONSE TYPE matches the request type

Focus: Did the model respond in the right category for this customer message?""",
        "variable": "prediction",
        "schema": [
            {"value": 0, "label": "Wrong category", "description": "Model responded in completely wrong category"},
            {"value": 1, "label": "Partial", "description": "Close but not quite right category"},
            {"value": 2, "label": "Close", "description": "Nearly correct but missed nuance"},
            {"value": 3, "label": "Correct category", "description": "Model correctly identified and handled the request type"}
        ]
    },
    {
        "name": "multi_turn_completeness",
        "instructions": """You are evaluating how COMPLETELY the model collected required information during multi-turn bug report conversations.

Required fields for bug reports:
1. description — What went wrong
2. stepsToReproduce — How to reproduce the issue
3. environment — Browser/OS/device info

Rules:
- Award points for each field successfully collected
- If customer provided info upfront, count it as collected
- Don't penalize for asking questions — reward successful collection
- For single-turn tests with complete info already provided, award full marks
- Focus on whether the FINAL response has all needed info to create a ticket

Focus: Were all required bug report fields collected before creating the ticket?""",
        "variable": "prediction",
        "schema": [
            {"value": 0, "label": "Not started", "description": "No attempt to collect information"},
            {"value": 1, "label": "Started but incomplete", "description": "Began collection but missed key fields"},
            {"value": 2, "label": "Mostly complete", "description": "Collected most fields but missing one"},
            {"value": 3, "label": "All fields collected", "description": "Successfully collected description, steps, and environment"}
        ]
    }
]

if __name__ == "__main__":
    print("=" * 70)
    print("BEDROCK EVALUATION METRIC CONFIGURATIONS")
    print("=" * 70)

    for m in metrics:
        print(f"\n{'='*70}")
        print(f"METRIC: {m['name'].upper()}")
        print("=" * 70)
        print(f"\nINSTRUCTIONS:")
        print(m['instructions'])
        print(f"\nVARIABLE TO ADD:")
        print(f"  Name: {m['variable']}")
        print(f"  Source: Leave blank (auto-pulls from modelResponses[0].response)")
        print(f"\nOUTPUT SCHEMA:")
        for row in m['schema']:
            print(f"  {row['value']}: {row['label']} - {row['description']}")

        # Save to file
        with open(f'metric_{m["name"]}.txt', 'w', encoding='utf-8') as f:
            f.write(f"Metric: {m['name']}\n\n")
            f.write(f"Instructions:\n{m['instructions']}\n\n")
            f.write(f"Variable: {m['variable']}\n\n")
            f.write("Schema:\n")
            for row in m['schema']:
                f.write(f"  {row['value']}: {row['label']} - {row['description']}\n")

    print("\n" + "=" * 70)
    print("Files saved: metric_fluency.txt, metric_coherence.txt, etc.")
    print("=" * 70)
