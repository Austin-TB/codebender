#!/usr/bin/env python3
"""PreToolUse hook (ExitPlanMode): a plan must be phases, each with numbered steps.

Claude Code puts the plan text in tool_input.plan (and its file in planFilePath) before
hooks run. A plan without a "Phase N" heading, or with a phase that has no numbered
steps, is rejected with a reason, and Claude stays in plan mode to fix it.
WORKFLOW_PLANS=off turns the check off. No plan text, or any internal error, allows it.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import deny, disabled, read_payload  # noqa: E402

# "## Phase 1: Setup", "**Phase 2 - API**", "Phase III", "### Phase A"
PHASE = re.compile(r"^\s{0,3}(?:#{1,6}\s*)?(?:[*_]{1,2}\s*)?phase\s+(\d+|[ivx]+|[a-z])\b(.*)$", re.I)
# "1. ...", "2) ...", "1.2 ...", "- 3. ...", "- [ ] 4. ...", "**Step 5:** ...", "### Step 6 - ..."
STEP = re.compile(
    r"^\s*(?:#{1,6}\s+)?(?:[-*+]\s+)?(?:\[[ xX]\]\s+)?(?:\*\*|__)?(?:step\s+)?\d+(?:\.\d+)*[.):]?(?:\*\*|__)?[.):]?\s+\S",
    re.I,
)

SHAPE = (
    "## Phase 1: <goal>\n"
    "1. <step> (files: ...; test: ...)\n"
    "2. <step>\n"
    "## Phase 2: <goal>\n"
    "1. <step>"
)


def phases(plan):
    """[(phase label, number of steps)] in the order they appear."""
    found = []
    in_code = False
    for line in plan.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = PHASE.match(line)
        if match:
            title = re.sub(r"[*_#:\-–—\s]+", " ", match.group(2)).strip()
            label = "Phase " + match.group(1) + (": " + title if title else "")
            found.append([label, 0])
        elif found and STEP.match(line):
            found[-1][1] += 1
    return [(label, steps) for label, steps in found]


def plan_text(tool_input):
    plan = tool_input.get("plan")
    if isinstance(plan, str) and plan.strip():
        return plan
    path = tool_input.get("planFilePath")
    if isinstance(path, str) and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return None


def main():
    payload = read_payload()
    if disabled("WORKFLOW_PLANS"):
        return
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return
    plan = plan_text(tool_input)
    if not plan:
        return
    found = phases(plan)
    if not found:
        problem = "This plan has no phases"
    else:
        empty = [label for label, steps in found if steps == 0]
        if not empty:
            return
        problem = "These phases have no numbered steps: " + "; ".join(empty)
    deny("PreToolUse",
         "Plan rule (workflow plugin): every plan is split into phases, and every phase into numbered "
         "steps. {problem}. Rewrite the plan in this shape, then submit it again:\n{shape}"
         .format(problem=problem, shape=SHAPE))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
