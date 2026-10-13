# Codebender rules for Claude Code

These are the user's standing rules for every session, installed through the `codebender` plugin. Rules marked (enforced) are also checked by the plugin's hooks, so a blocked edit or a rejected plan points back to this list.

## Thinking and talking
- Reasoning is caveman-terse: short fragments, no filler, every fact kept.
- Everything the user reads (questions, progress notes, the summary after the work) is in normal, complete sentences.

## Plans
- Big tasks (several files or several steps) start with a plan in plan mode. Small tasks are done directly.
- Every plan is split into phases, and every phase into numbered steps, with no exceptions. (enforced: a plan without phases and numbered steps is rejected when it is submitted for approval)
- Each step names the files it touches and the test that proves it.

## Doing the steps
- Steps run in subagents, so the main conversation stays a clean orchestrator that holds the plan and reads short reports.
- Each brief covers the goal, the files, the constraints, the test command, the TDD rule below, and the shape of the report. Subagents see none of this conversation.
- Each subagent gets a model strong enough for its step: opus for design and tricky logic, sonnet for routine edits.
- Steps and phases that touch different files run in parallel; ones that touch the same files run in sequence.

## TDD (enforced)
- Test-driven development is the rule for every code change, not a judgment call: write a failing test, run it and see it fail for the right reason, write the least code that makes it pass, then refactor with the tests green.
- A project without a test suite gets one in the first phase.
- The plugin blocks edits to source files until a test file has changed: in a git repo, a test change must be in the working tree; elsewhere, a test file must have been edited earlier in the session. A blocked edit means writing the test first. Exceptions (generated code, config written in code) need the user's explicit OK; the check is not worked around through the shell.

## After every phase
1. `codebender:test-runner` runs the full suite. The next phase starts only when it passes.
2. `codebender:reviewer`, a fresh agent that has not seen the work, reviews that phase's changes for bugs and edge cases.
3. Confirmed issues are fixed, test first, before the next phase starts. Fixes target real inputs: no speculative abstractions, options or features.

## Tools
- At the start of each big task, the installed skills and `claude plugin list --available --json` are checked for a plugin or skill that would make the work easier or better. A good fit is suggested in one line and installed only with the user's OK.
