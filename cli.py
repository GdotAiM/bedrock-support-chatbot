#!/usr/bin/env python3
"""Interactive CLI for the customer support chatbot prototype.

Examples:
    python cli.py                          interactive chat
    python cli.py "my checkout is broken"  one-shot classification + reply
    python cli.py --session bob "..."      multi-turn with a named session
    LLM_BACKEND=mock python cli.py         force the offline mock backend
"""

import argparse
import sys
import uuid

from chatbot.flow import SupportChatbotFlow
from chatbot.llm import get_llm


def _make_session_id(args):
    """Choose a session id for this invocation.

    Interactive mode (no message given) keeps the user-supplied name so
    repeated turns stay in the same conversation. One-shot mode always gets
    a fresh session so each invocation is independent unless the user
    explicitly supplies ``--session``.
    """
    if args.message is not None:
        return args.session or str(uuid.uuid4())
    return args.session or "default"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Customer support chatbot prototype")
    parser.add_argument("message", nargs="*", help="one-shot message to process")
    parser.add_argument("--session", default=None, help="multi-turn session id (auto-generated for one-shot)")
    parser.add_argument(
        "--backend", default=None,
        help="LLM backend: bedrock | mock | auto (default: auto)",
    )
    args = parser.parse_args(argv)

    session_id = _make_session_id(args)
    llm = None if args.backend is None else get_llm(args.backend)
    flow = SupportChatbotFlow(llm=llm)

    if args.message:
        text = " ".join(args.message)
        result = flow.handle(text, session_id=session_id)
        print(f"[{result.handler} | {result.classification.category} | conf {result.classification.confidence:.2f}]")
        print(f"session: {session_id}")
        print(result.response)
        return 0

    print(f"Support chatbot ready (llm={flow.llm.name}). Type 'exit' to quit, 'reset' to clear session.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() == "exit":
            break
        if text.lower() == "reset":
            flow.reset_session(session_id)
            print(f"session {session_id!r} reset")
            continue
        result = flow.handle(text, session_id=session_id)
        print(f"[{result.handler} | {result.classification.category} | conf {result.classification.confidence:.2f}]")
        print(f"bot> {result.response}")

    return 0


if __name__ == "__main__":
    sys.exit(main())