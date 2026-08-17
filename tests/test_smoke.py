# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os
import subprocess
import sys


def test_player_opens_and_closes_cleanly(tmp_path):
    project_root = os.path.dirname(os.path.dirname(__file__))
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PATH"] = os.path.join(project_root, "bin") + os.pathsep + env["PATH"]
    env["MLCPLAYER_TEST_SETTINGS"] = str(tmp_path / "smoke-settings")
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "smoke_child.py")],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "Windows fatal exception" not in output, output
