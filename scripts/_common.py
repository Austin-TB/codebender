"""Small helpers shared by the workflow plugin's hook scripts (stdlib only)."""
import json
import os
import sys

OFF_VALUES = {"0", "off", "false", "no", "disabled"}


def disabled(var):
    """True when an environment switch such as WORKFLOW_TDD=off turns a check off."""
    return os.environ.get(var, "").strip().lower() in OFF_VALUES


def read_payload():
    """The hook's JSON input from stdin, or {} when it is missing or malformed."""
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def deny(event, reason):
    """Block the tool call; Claude sees the reason and can correct course."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event,
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
