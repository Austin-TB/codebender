"""Tests for the Codebender plugin's hook scripts. Run: python3 -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")


def run_hook(script, payload, cwd=None):
    """Run a hook script like Claude Code does; return (exit code, parsed JSON output or None)."""
    result = subprocess.run([sys.executable, "-B", os.path.join(SCRIPTS, script)],
                            input=payload if isinstance(payload, str) else json.dumps(payload),
                            capture_output=True, text=True, cwd=cwd, timeout=30)
    output = result.stdout.strip()
    return result.returncode, (json.loads(output) if output else None)


def decision(output):
    return None if output is None else output["hookSpecificOutput"]["permissionDecision"]


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


class TddGateGitTests(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp(prefix="wf-git-"))
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        os.makedirs(os.path.join(self.repo, "src"))
        os.makedirs(os.path.join(self.repo, "tests"))
        self.write("src/app.py", "def add(a, b):\n    return a + b\n")
        self.write("tests/test_app.py", "from src.app import add\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")
        self.session = "s-" + uuid.uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)

    def edit(self, rel, tool="Edit"):
        payload = {"session_id": self.session, "cwd": self.repo, "hook_event_name": "PreToolUse",
                   "tool_name": tool, "tool_input": {"file_path": os.path.join(self.repo, rel)}}
        return run_hook("tdd_gate.py", payload)

    def test_source_edit_blocked_on_clean_tree(self):
        code, out = self.edit("src/app.py")
        self.assertEqual(code, 0)
        self.assertEqual(decision(out), "deny")
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("src/app.py", reason)
        self.assertIn("working tree", reason)

    def test_new_source_file_blocked_too(self):
        self.assertEqual(decision(self.edit("src/new_module.py", tool="Write")[1]), "deny")

    def test_source_change_alone_does_not_count(self):
        self.write("src/app.py", "def add(a, b):\n    return b + a\n")
        self.assertEqual(decision(self.edit("src/app.py")[1]), "deny")

    def test_modified_test_file_unlocks_source(self):
        self.write("tests/test_app.py", "from src.app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
        self.assertIsNone(self.edit("src/app.py")[1])

    def test_untracked_test_file_unlocks_source(self):
        self.write("tests/unit/test_new.py", "def test_x():\n    assert False\n")
        self.assertIsNone(self.edit("src/app.py")[1])

    def test_commit_resets_the_gate(self):
        self.write("tests/test_app.py", "# changed\n")
        self.assertIsNone(self.edit("src/app.py")[1])
        git(self.repo, "commit", "-qam", "tests")
        self.assertEqual(decision(self.edit("src/app.py")[1]), "deny")

    def test_deleted_test_file_counts_as_a_test_change(self):
        git(self.repo, "rm", "-q", "tests/test_app.py")
        self.assertIsNone(self.edit("src/app.py")[1])

    def test_test_files_are_always_allowed(self):
        for rel in ["tests/test_app.py", "src/app_test.py", "web/button.test.tsx", "web/api.spec.ts",
                    "web/__tests__/x.js", "pkg/handler_test.go", "src/test/java/UserServiceTest.java",
                    "spec/user_spec.rb", "conftest.py"]:
            with self.subTest(rel=rel):
                self.assertIsNone(self.edit(rel, tool="Write")[1])

    def test_non_source_files_are_allowed(self):
        for rel in ["README.md", "pyproject.toml", "config/settings.yaml", "web/styles.css", "data.json"]:
            with self.subTest(rel=rel):
                self.assertIsNone(self.edit(rel)[1])

    def test_vendored_and_generated_folders_are_allowed(self):
        for rel in ["node_modules/lib/index.js", ".venv/lib/x.py", "dist/bundle.js", "db/migrations/0001.py"]:
            with self.subTest(rel=rel):
                self.assertIsNone(self.edit(rel)[1])

    def test_files_outside_the_project_are_allowed(self):
        outside = tempfile.mkdtemp(prefix="wf-outside-")
        try:
            payload = {"session_id": self.session, "cwd": self.repo, "tool_name": "Write",
                       "tool_input": {"file_path": os.path.join(outside, "script.py")}}
            self.assertIsNone(run_hook("tdd_gate.py", payload)[1])
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_relative_paths_resolve_against_cwd(self):
        payload = {"session_id": self.session, "cwd": self.repo, "tool_name": "Edit",
                   "tool_input": {"file_path": "src/app.py"}}
        self.assertEqual(decision(run_hook("tdd_gate.py", payload)[1]), "deny")

class TddGateNoGitTests(unittest.TestCase):
    def setUp(self):
        self.project = os.path.realpath(tempfile.mkdtemp(prefix="wf-plain-"))
        self.session = "s-" + uuid.uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def edit(self, rel, session=None):
        payload = {"session_id": session or self.session, "cwd": self.project, "tool_name": "Write",
                   "tool_input": {"file_path": os.path.join(self.project, rel)}}
        return run_hook("tdd_gate.py", payload)[1]

    def test_test_first_then_source(self):
        out = self.edit("app.py")
        self.assertEqual(decision(out), "deny")
        self.assertIn("in this session", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(self.edit("test_app.py"))
        self.assertIsNone(self.edit("app.py"))

    def test_sessions_are_separate(self):
        self.assertIsNone(self.edit("tests/test_app.py"))
        self.assertEqual(decision(self.edit("app.py", session="other-" + uuid.uuid4().hex)), "deny")


class TddGateRobustnessTests(unittest.TestCase):
    def test_bad_input_never_blocks(self):
        for payload in ["", "not json", "[]", json.dumps({"tool_input": "x"}), json.dumps({"tool_input": {}})]:
            with self.subTest(payload=payload):
                self.assertEqual(run_hook("tdd_gate.py", payload), (0, None))


GOOD_PLAN = """# Add CSV export

## Phase 1: Data layer
1. Add `to_rows()` to `models/report.py` (test: tests/test_report.py)
2. Handle empty reports

## Phase 2: Endpoint
1. Add `GET /reports/{id}.csv`
2. Stream large files
"""


class PlanGateTests(unittest.TestCase):
    def submit(self, plan=None, plan_file=None):
        tool_input = {}
        if plan is not None:
            tool_input["plan"] = plan
        if plan_file is not None:
            tool_input["planFilePath"] = plan_file
        payload = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode",
                   "tool_input": tool_input}
        return run_hook("plan_gate.py", payload)

    def test_phased_plan_passes(self):
        self.assertEqual(self.submit(GOOD_PLAN), (0, None))

    def test_plan_without_phases_is_rejected(self):
        code, out = self.submit("# Plan\n1. Add the model\n2. Add the endpoint\n")
        self.assertEqual(code, 0)
        self.assertEqual(decision(out), "deny")
        self.assertIn("no phases", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_phase_without_steps_is_rejected_by_name(self):
        plan = "## Phase 1: Setup\n1. Create the venv\n\n## Phase 2: API\nBuild the endpoints.\n"
        out = self.submit(plan)[1]
        self.assertEqual(decision(out), "deny")
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("Phase 2: API", reason)
        self.assertNotIn("Phase 1", reason.split("steps:")[1].split(".")[0])

    def test_common_formats_are_recognised(self):
        plans = [
            "**Phase 1 - Setup**\n- [ ] 1. Create venv\n**Phase 2 - API**\n**Step 1:** Add route\n",
            "### Phase I\n1) one\n### Phase II\n1.1 two\n",
            "Phase A: prep\n- 1. one\nPhase B: build\n### Step 1 - two\n",
            "## Phase 1 — Setup\n  1. indented step\n",
        ]
        for plan in plans:
            with self.subTest(plan=plan):
                self.assertIsNone(self.submit(plan)[1])

    def test_numbered_lines_inside_code_blocks_do_not_count(self):
        plan = "## Phase 1: Script\n```\n1. not a step\n```\n"
        self.assertEqual(decision(self.submit(plan)[1]), "deny")

    def test_words_starting_with_phase_are_not_phases(self):
        self.assertEqual(decision(self.submit("Phase out the old API\n1. remove it\n")[1]), "deny")

    def test_plan_read_from_file(self):
        handle, path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(handle, "w") as plan_file:
            plan_file.write("1. no phases here\n")
        try:
            self.assertEqual(decision(self.submit(plan_file=path)[1]), "deny")
        finally:
            os.unlink(path)

    def test_missing_plan_or_bad_input_never_blocks(self):
        self.assertEqual(self.submit(), (0, None))
        self.assertEqual(run_hook("plan_gate.py", "garbage"), (0, None))

class InjectRulesTests(unittest.TestCase):
    def test_rules_are_added_as_context(self):
        code, out = run_hook("inject_rules.py", {"hook_event_name": "SessionStart", "source": "startup"})
        self.assertEqual(code, 0)
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "SessionStart")
        with open(os.path.join(ROOT, "rules", "codebender.md"), encoding="utf-8") as handle:
            self.assertEqual(spec["additionalContext"], handle.read().strip())

    def test_rules_stay_under_the_context_cap(self):
        with open(os.path.join(ROOT, "rules", "codebender.md"), encoding="utf-8") as handle:
            self.assertLess(len(handle.read()), 9000)  # hook context over 10,000 chars is cut to a preview

    def test_rules_name_the_agents_that_exist(self):
        with open(os.path.join(ROOT, "rules", "codebender.md"), encoding="utf-8") as handle:
            rules = handle.read()
        for agent in os.listdir(os.path.join(ROOT, "agents")):
            self.assertIn("codebender:" + agent[:-3], rules)


if __name__ == "__main__":
    unittest.main()
