# Codebender

Codebender is a Claude Code workflow plugin. It loads its rules into every session and enforces the two rules that shouldn't depend on judgment: test-driven development, and plans that are split into phases and steps.

## The workflow

1. Caveman for thinking, normal language for everything I read.
2. Big tasks get a plan, and every plan is phases made of numbered steps. **(enforced)**
3. Subagents do the steps, each on a model strong enough for it.
4. Steps and phases that don't touch the same files run in parallel.
5. TDD on every code change: failing test first, then the code. A project without a suite gets one in the first phase. **(enforced)**
6. The full test suite runs after every phase.
7. A fresh agent reviews every phase for bugs and edge cases, without overengineering.
8. Installed skills and the plugin catalog get checked for something that would do the job better.

## Install

```bash
claude plugin marketplace add <owner>/codebender   # or a local path to this folder
claude plugin install codebender@codebender
```

Start a new session. `/context` should show the rules, and the agents appear as `codebender:test-runner` and `codebender:reviewer`.

## What's inside

| File | What it does |
|---|---|
| `rules/codebender.md` | The rules. Plugins can't ship a CLAUDE.md, so a `SessionStart` hook adds this file to every session (about 700 tokens). |
| `scripts/tdd_gate.py` | `PreToolUse` hook on `Edit`/`Write`. Blocks edits to source files until a test has changed. |
| `scripts/plan_gate.py` | `PreToolUse` hook on `ExitPlanMode`. Rejects a plan without phases and numbered steps, and Claude stays in plan mode to fix it. |
| `agents/test-runner.md` | Runs the suite on Haiku and reports only the failures. |
| `agents/reviewer.md` | Reviews one finished phase cold, on Opus. Reports confirmed bugs with the input that breaks them, and doesn't suggest refactors. |

### How the TDD check decides

- Test files, non-code files (Markdown, JSON, YAML, CSS...), files outside the project, and folders like `node_modules`, `.venv`, `dist` and `migrations` are never blocked.
- In a git repo, a source edit is allowed once the working tree has an added, modified or deleted test file. Committing resets it, so each commit needs its own test change.
- Outside git, a source edit is allowed once a test file has been edited in the same session.
- Test files are recognised by folder (`tests/`, `test/`, `__tests__/`, `spec/`, `e2e/`) or name (`test_*.py`, `*_test.go`, `*.test.ts`, `*.spec.js`, `*Test.java`, `*_spec.rb`, `conftest.py`).

It's a guard on the normal path, not a sandbox: it checks that a test changed, not that it failed first, and source files written through the shell (`sed -i`, `cat >`) skip it. The rules cover the rest (red, green, refactor), and they tell Claude to ask instead of working around a block.

## Tests

```bash
python3 -m unittest discover -s tests     # 29 tests: git and non-git TDD cases, plan formats, switches
claude plugin validate . --strict
```

Requires Python 3.8+ as `python3` and git. Built and checked against Claude Code 2.1.296.
