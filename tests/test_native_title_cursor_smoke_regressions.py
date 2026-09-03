# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Static contract for the opt-in native title-cursor child."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_native_title_cursor_smoke_is_explicit_and_reports_both_states():
    source = (ROOT / "tests" / "native_title_cursor_smoke_child.py").read_text(
        encoding="utf-8")

    assert 'OPT_IN_VARIABLE = "MLC_NATIVE_TITLE_CURSOR_SMOKE"' in source
    assert 'MEDIA_VARIABLE = "MLC_NATIVE_TITLE_CURSOR_MEDIA"' in source
    assert "CURSOR_OPEN=" in source
    assert "CURSOR_FIRST_AFTER_CLOSE=" in source
    assert "CURSOR_AFTER_OUTSIDE_CLOSE=" in source
    assert "CURSOR_HAND=" in source
    assert "target = title.open_button" in source
    assert "OPACITY_APPLIED=" in source
    assert "OPACITY_RESTORED=" in source
    assert "VIDEO_SUBMITTED=" in source
    assert "MARK_DONE" in source and "MARK_FAILED" in source
    assert "SetCursorPos(original_cursor.x(), original_cursor.y())" in source
