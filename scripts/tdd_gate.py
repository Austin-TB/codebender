#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|MultiEdit): no source edits until a test has changed.

- Test files, non-source files, files outside the project and vendored or generated
  folders are always allowed.
- In a git repo, a source edit is allowed once the working tree has an added, modified
  or deleted test file. Committing resets it, so each commit needs its own test change.
- Outside git, a source edit is allowed once a test file was edited in this session.
- Any internal error allows the edit.
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import deny, read_payload  # noqa: E402

SOURCE_EXT = {
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".go", ".rs",
    ".java", ".kt", ".scala", ".rb", ".php", ".cs", ".swift", ".c", ".h", ".cc", ".cpp",
    ".hpp", ".ex", ".exs", ".dart", ".vue", ".svelte",
}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "e2e"}
TEST_NAME = re.compile(
    r"^test_.+"                                   # test_models.py
    r"|.+_test\.[^.]+$"                           # models_test.py, handler_test.go
    r"|.+\.(test|spec)\.[^.]+$"                   # button.test.tsx, api.spec.ts
    r"|.+(Test|Tests|Spec)\.(java|kt|scala|cs|swift|php)$"  # UserServiceTest.java
    r"|.+_spec\.rb$"                              # user_spec.rb
    r"|^conftest\.py$"
)
SKIP_DIRS = {
    "node_modules", ".venv", "venv", ".tox", "dist", "build", "vendor", "third_party",
    ".git", "__pycache__", ".next", "target", "migrations",
}
MARKER_DIR = os.path.join(tempfile.gettempdir(), "codebender-tdd")


def is_test(path):
    parts = path.replace("\\", "/").split("/")
    return any(part in TEST_DIRS for part in parts[:-1]) or bool(TEST_NAME.match(parts[-1]))


def inside(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def git_changed_paths(start):
    """Paths with changes in the working tree, [] if clean, None if not a git repo.

    Raises on timeouts or other failures so the caller can allow the edit.
    """
    folder = start
    while folder and not os.path.isdir(folder):
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    inside_repo = subprocess.run(["git", "-C", folder, "rev-parse", "--is-inside-work-tree"],
                                 capture_output=True, text=True, timeout=5)
    if inside_repo.returncode != 0 or inside_repo.stdout.strip() != "true":
        return None
    status = subprocess.run(["git", "-C", folder, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                            capture_output=True, text=True, timeout=10, check=True)
    entries = status.stdout.split("\0")
    paths, index = [], 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        paths.append(path)
        if "R" in code or "C" in code:  # renames and copies are followed by the original path
            if index < len(entries):
                paths.append(entries[index])
            index += 1
    return paths


def marker_path(payload):
    session = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("session_id") or ""))
    return os.path.join(MARKER_DIR, session) if session else None


def mark_session(payload):
    marker = marker_path(payload)
    if marker:
        os.makedirs(MARKER_DIR, exist_ok=True)
        with open(marker, "a", encoding="utf-8"):
            pass


def main():
    payload = read_payload()
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path:
        return

    cwd = payload.get("cwd") or os.getcwd()
    project = os.path.realpath(cwd)
    target = os.path.realpath(file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path))
    if not inside(target, project):
        return
    rel = os.path.relpath(target, project).replace(os.sep, "/")
    if any(part in SKIP_DIRS for part in rel.split("/")[:-1]):
        return
    if is_test(rel):
        mark_session(payload)
        return
    if os.path.splitext(rel)[1].lower() not in SOURCE_EXT:
        return

    try:
        changed = git_changed_paths(os.path.dirname(target))
    except Exception:
        return  # git is slow or broken: don't block on our own failure
    if changed is None:
        marker = marker_path(payload)
        if marker is None or os.path.exists(marker):
            return
        where = "in this session"
    else:
        if any(is_test(path) for path in changed):
            return
        where = "in the working tree (git status shows no added or modified test files)"

    deny("PreToolUse",
         "TDD rule (codebender plugin): {rel} is source code, and no test has changed yet {where}. "
         "Write or update a failing test for this change first (for example tests/test_<module>.py, "
         "<name>.test.ts or <name>_test.go), run it and watch it fail, then edit {rel}. If this change "
         "really needs no test, stop and ask the user; don't work around this check through the shell."
         .format(rel=rel, where=where))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
