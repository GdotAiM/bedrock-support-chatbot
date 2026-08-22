#!/usr/bin/env python3
"""Local helper around the course's evaluation flow.

Consumes the authoritative test-suite format (``flowInputNode`` + ``tests`` with
``id`` / ``prompt`` / ``expected``) and produces:
  eval/run_result.jsonl            detailed: prompt, ground truth, prediction, response
  eval/bedrock_eval_dataset.jsonl  BYOI JSONL: prompt, referenceResponse, modelResponses

Two run modes:
  local    (default)  runs the local prototype flow (mock or Bedrock model) so you can
                      sanity-check routing without the deployed flow.
  deployed            runs the DEPLOYED Bedrock Flow via invoke_flow (streaming API,
                      node-based input), same as the course's generate-eval-dataset.py.
                      Use --flow-id + --alias-id. The routed path is read from trace.

Bug tests with a ``followUps`` array use the ``__SID__`` session protocol so the
AgentCore harness can complete multi-turn intake before the proxy Lambda times out.

For the real submission use the course's `generate-eval-dataset.py` at the repo root:
  python generate-eval-dataset.py --tests-json eval/flow-tests.json \\
      --flow-id <id> --flow-alias-id <id> --out-jsonl eval/bedrock_eval_dataset.jsonl

Usage:
    python -m eval.generate_eval_dataset
    python -m eval.generate_eval_dataset --backend bedrock
    python -m eval.generate_eval_dataset --flow-id <id> --alias-id <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Windows Python 3.14 ships an empty default CA bundle; inject system certs
# before any boto3 import so HTTPS calls to Bedrock work without manual
# SSL_CERT_FILE configuration.
_here = str(Path(__file__).resolve().parent.parent.resolve())
sys.path.insert(0, _here)
import aws_setup  # noqa: E402
aws_setup.ensure_aws_ssl()
del sys.path[0]

# Load AWS credentials from logins.txt (same source as deployed-eval.ps1).
# Without this, boto3 has no credentials and all AWS calls fail.
_LOGINS_PATH = Path(__file__).resolve().parent.parent / "logins.txt"
if _LOGINS_PATH.exists():
    _creds = {}
    _current_key = None
    for _line in _LOGINS_PATH.read_text(encoding="utf-8").strip().splitlines():
        _s = _line.strip()
        if not _s:
            continue
        if _s == "AWS Access Key ID:":
            _current_key = "AWS_ACCESS_KEY_ID"
        elif _s == "AWS Secret Access Key:":
            _current_key = "AWS_SECRET_ACCESS_KEY"
        elif _s == "AWS Session Token":
            _current_key = "AWS_SESSION_TOKEN"
        elif _current_key and _s and not _s.startswith("AWS"):
            _creds[_current_key] = _s
            _current_key = None
    for _k, _v in _creds.items():
        os.environ[_k] = _v
    if "AWS_DEFAULT_REGION" not in os.environ:
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

from chatbot.flow import SupportChatbotFlow
from chatbot.llm import get_llm
from eval.flow_client import invoke_flow_once, invoke_harness_direct, is_terminal_bug_response

HERE = Path(__file__).resolve().parent


def run_local_case(flow: SupportChatbotFlow, case: dict) -> dict:
    session_id = f"eval-{case['id']}"
    flow.reset_session(session_id)
    follow_ups = case.get("followUps") or []
    messages = [case["prompt"]] + follow_ups

    predicted = "other"
    response = ""
    turns = 0
    for message in messages:
        result = flow.handle(message, session_id=session_id)
        predicted = result.classification.category
        response = result.response
        turns += 1
        if is_terminal_bug_response(response):
            break

    return {
        "category": predicted,
        "response": response,
        "turns": turns,
        "session_id": session_id if follow_ups else None,
        "multi_turn": bool(follow_ups),
    }


def run_deployed_case(client, case: dict) -> dict:
    """Run a single test case against the deployed infrastructure.

    Multi-turn bug tests use direct harness invocation (bypassing the flow +
    proxy Lambda) to avoid cumulative timeout overhead.  Single-shot tests
    go through the full flow as before.
    """
    follow_ups = case.get("followUps") or []
    if follow_ups:
        return invoke_harness_direct(
            client,
            case["prompt"],
            follow_ups=follow_ups,
        )
    return invoke_flow_once(client, prompt=case["prompt"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default=str(HERE / "flow-tests.json"))
    parser.add_argument("--out", default=str(HERE))
    parser.add_argument("--backend", default=None, help="bedrock | mock | auto (local mode only)")
    parser.add_argument(
        "--flow-id", default=None,
        help="deployed Bedrock Flow id or ARN (switches to deployed mode)",
    )
    parser.add_argument("--alias-id", default=None, help="deployed flow alias id or ARN")
    parser.add_argument("--region", default=None, help="AWS region for deployed mode (default: us-east-1)")
    args = parser.parse_args(argv)

    suite = json.loads(Path(args.template).read_text(encoding="utf-8"))
    cases = suite["tests"]

    if args.flow_id:
        import boto3

        region = args.region or "us-east-1"
        client = boto3.client("bedrock-agent-runtime", region_name=region)

        def run(case):
            return run_deployed_case(client, case)

        mode = "deployed"
    else:
        llm = None if args.backend is None else get_llm(args.backend)
        flow = SupportChatbotFlow(llm=llm)

        def run(case):
            return run_local_case(flow, case)

        mode = "local"

    detail_path = Path(args.out) / "run_result.jsonl"
    eval_path = Path(args.out) / "bedrock_eval_dataset.jsonl"

    total = correct = failed = 0
    mismatches = []
    with open(detail_path, "w", encoding="utf-8") as detail, open(eval_path, "w", encoding="utf-8") as evalu:
        for case in cases:
            prompt = case["prompt"]
            ground = case["category"]
            reference = case.get("expected", "")
            meta = {"turns": 1, "session_id": None, "multi_turn": False}
            try:
                result = run(case)
                predicted = result["category"]
                response = result["response"]
                meta = {
                    "turns": result.get("turns", 1),
                    "session_id": result.get("session_id"),
                    "multi_turn": result.get("multi_turn", False),
                }
            except Exception as exc:  # noqa: BLE001 - record failures, keep going
                predicted, response = "error", f"[FLOW_ERROR] {type(exc).__name__}: {exc}"
                failed += 1
            is_correct = predicted == ground
            total += 1
            correct += int(is_correct)
            if not is_correct:
                mismatches.append((case["id"], prompt, ground, predicted))

            detail.write(
                json.dumps(
                    {
                        "id": case["id"],
                        "mode": mode,
                        "prompt": prompt,
                        "expected_category": ground,
                        "predicted_category": predicted,
                        "response": response,
                        "correct": is_correct,
                        "notes": case.get("notes", ""),
                        **meta,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            evalu.write(
                json.dumps(
                    {
                        "prompt": prompt,
                        "referenceResponse": reference,
                        "modelResponses": [
                            {"response": response, "modelIdentifier": "customer-support-chatbot"}
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    accuracy = correct / total if total else 0.0
    print(f"wrote {detail_path}")
    print(f"wrote {eval_path} (upload to Bedrock Evaluations - BYOI)")
    print(f"mode: {mode} | routing accuracy: {correct}/{total} = {accuracy:.0%} | failures: {failed}")
    for test_id, prompt, ground, predicted in mismatches:
        print(f"  MISROUTE [{test_id}]: {prompt!r} expected={ground} predicted={predicted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
