#!/usr/bin/env python3
"""SessionStart hook: add rules/workflow.md to the session's context.

Plugins can't ship a CLAUDE.md, so this is how the rules load in every session.
Turn it off with WORKFLOW_RULES=off.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import disabled, read_payload  # noqa: E402

RULES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules", "workflow.md")


def main():
    read_payload()  # drain stdin; the payload isn't needed
    if disabled("WORKFLOW_RULES"):
        return
    try:
        with open(RULES, encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError:
        return
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never break the session
        pass
    sys.exit(0)
