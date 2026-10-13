"""Small helpers shared by the Codebender plugin's hook scripts (stdlib only)."""
import json
import sys


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
