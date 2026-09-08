# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fiziksel playlist yeniden-sıralama kabul sözleşmesinin statik sınırları."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHILD = (ROOT / "tests" / "native_physical_acceptance_child.py").read_text(
    encoding="utf-8")
RUNNER = (ROOT / "tests" / "run_physical_acceptance.py").read_text(
    encoding="utf-8")


def _body():
    start = CHILD.index("def group_playlist_reorder():")
    end = CHILD.index("# ================= GRUP 4", start)
    return CHILD[start:end]


def test_reorder_group_is_opt_in_runner_group_with_a_bounded_timeout():
    assert '("14", "playlist_reorder", 180)' in RUNNER
    assert 'elif GROUP == "playlist_reorder":' in CHILD


def test_reorder_uses_physical_input_and_checks_after_last_before_release():
    body = _body()
    assert "mouse_button(True)" in body
    assert "user32.SetCursorPos" in body
    assert "view._drag_after_last" in body
    assert body.index("target_seen =") < body.index("mouse_button(False)")


def test_reorder_requires_three_videos_and_keeps_playing_selection_in_sync():
    body = _body()
    assert "view.count() < 3" in body
    assert "BLOCKED: NEED_THREE_VIDEOS" in body
    assert "expected = before[1:] + before[:1]" in body
    assert "playlist_reorder_playing_and_selection" in body
