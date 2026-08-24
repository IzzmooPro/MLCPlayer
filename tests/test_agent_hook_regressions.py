# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Agent safety hooks enforce destructive-command and startup contracts."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))
import guard_git  # noqa: E402


@pytest.mark.parametrize("command", (
    "git reset --hard",
    "git.exe reset --hard",
    "GIT RESET --hard",
    "git -C repo reset --hard",
    'git -C "path with spaces" restore .',
    "git --no-pager reset --hard",
    "git --git-dir=.git clean -fd",
    "git clean -fd",
    "git switch --discard-changes master",
    "git switch -f master",
))
def test_git_guard_blocks_destructive_variants(command):
    assert guard_git.blocked_action(command)


@pytest.mark.parametrize("command", (
    "git status --short",
    "git switch -c codex/safe-branch",
    'git commit -m "document reset behavior"',
    "python -m pytest -q tests",
))
def test_git_guard_keeps_safe_commands_available(command):
    assert guard_git.blocked_action(command) is None


def test_compile_hook_blocks_an_invalid_edited_python_file(tmp_path):
    broken = tmp_path / "broken.py"
    broken.write_text("def broken(:\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(HOOKS / "compile_check.py")],
        input=json.dumps({"tool_input": {"file_path": str(broken)}}),
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "block"
    assert "compileall" in payload["reason"]
