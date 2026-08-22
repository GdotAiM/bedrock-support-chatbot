#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

# Windows Python 3.14 ships an empty default CA bundle; inject system certs
# before any boto3 import so HTTPS calls to Bedrock work without manual
# SSL_CERT_FILE configuration.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aws_setup  # noqa: E402
aws_setup.ensure_aws_ssl()
del sys.path[0]

import boto3

from eval.flow_client import invoke_flow_multi_turn, invoke_flow_once


def main():
    p = argparse.ArgumentParser(description="Run Bedrock Flow tests and emit Bedrock Evaluations JSONL (LLM-as-judge BYOI).")
    p.add_argument("--tests-json", required=True, help="Path to the test suite JSON (the file from section 1).")
    p.add_argument("--flow-id", required=True, help="Bedrock Flow identifier.")
    p.add_argument("--flow-alias-id", required=True, help="Bedrock Flow alias identifier.")
    p.add_argument("--model-identifier", default="my-flow-app", help="Value to put in modelResponses[0].modelIdentifier.")
    p.add_argument("--out-jsonl", default="output_eval_dataset.jsonl", help="Where to write the eval dataset JSONL.")
    p.add_argument("--region", default=None, help="AWS region (optional; otherwise uses default boto config).")
    p.add_argument("--enable-trace", action="store_true", help="Include trace collection (not written to eval JSONL).")
    args = p.parse_args()

    suite = json.loads(Path(args.tests_json).read_text(encoding="utf-8"))
    input_node_name = suite["flowInputNode"]["nodeName"]

    print("Input node name: " + input_node_name)

    tests = suite["tests"]

    session = boto3.Session(region_name=args.region) if args.region else boto3.Session()
    client = session.client("bedrock-agent-runtime")

    out_path = Path(args.out_jsonl)
    n_ok = 0

    with out_path.open("w", encoding="utf-8") as f:
        for t in tests:
            test_id = t["id"]
            reference = t.get("expected", "")
            prompt = t.get("prompt", "")

            try:
                follow_ups = t.get("followUps") or []
                if follow_ups:
                    result = invoke_flow_multi_turn(
                        client,
                        args.flow_id,
                        args.flow_alias_id,
                        input_node_name,
                        prompt,
                        follow_ups=follow_ups,
                        enable_trace=args.enable_trace,
                    )
                else:
                    result = invoke_flow_once(
                        client,
                        args.flow_id,
                        args.flow_alias_id,
                        input_node_name,
                        prompt,
                        enable_trace=args.enable_trace,
                    )
                response_text = result["response"]
                n_ok += 1
            except Exception as e:
                print(e)
                response_text = f"[FLOW_ERROR] {type(e).__name__}: {e}"

            record = {
                "prompt": prompt,
                "referenceResponse": reference,
                "modelResponses": [
                    {
                        "response": response_text,
                        "modelIdentifier": args.model_identifier,
                    }
                ],
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"{test_id}: wrote eval line", file=sys.stderr)

    print(f"\nWrote {len(tests)} JSONL lines to {out_path} ({n_ok} flow calls succeeded).", file=sys.stderr)


if __name__ == "__main__":
    main()
