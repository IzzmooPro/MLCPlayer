# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os
from collections import Counter
import subprocess
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QDialog, QListWidget, QMainWindow, QPushButton

from app.media_controls import show_playlist
from app.player import MPVPlayer


def test_timeline_drag_uses_real_slider_and_timer_does_not_take_control(tmp_path):
    project_root = os.path.dirname(os.path.dirname(__file__))
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PATH"] = os.path.join(project_root, "bin") + os.pathsep + env["PATH"]
    env["MLCPLAYER_TEST_SETTINGS"] = str(tmp_path / "timeline-settings")
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "timeline_child.py")],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, output
    assert "Windows fatal exception" not in output, output


def test_playlist_window_tracks_model_after_remove(monkeypatch):
    app = QApplication.instance() or QApplication([])
    player = QMainWindow()
    player.playlist = ["first.mkv", "second.mkv"]
    player.current_playlist_index = -1
    captured = {}

    def fake_exec(dialog):
        playlist_view = dialog.findChild(QListWidget)
        playlist_view.setCurrentRow(1)
        remove_button = next(
            button for button in dialog.findChildren(QPushButton)
            if button.text() == "Kaldır"
        )
        remove_button.click()
        captured["count"] = playlist_view.count()
        return 0

    monkeypatch.setattr(QDialog, "exec", fake_exec)
    show_playlist(player)

    assert captured["count"] == len(player.playlist)
    player.deleteLater()
    app.processEvents()


def test_shuffle_preserves_duplicate_playlist_entries():
    player = SimpleNamespace(
        playlist=["same.mkv", "other.mkv", "same.mkv"],
        current_playlist_index=0,
        shuffle=False,
    )

    MPVPlayer.toggle_shuffle(player, True)

    assert Counter(player.playlist) == Counter(
        ["same.mkv", "other.mkv", "same.mkv"]
    )
