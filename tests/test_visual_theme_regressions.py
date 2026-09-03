# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Gorunur yuzeylerin tek urun kimligini kullandigini kilitler."""
from pathlib import Path

from app import config


ROOT = Path(__file__).resolve().parents[1]
VISIBLE_THEME_FILES = (
    "app/config.py",
    "app/empty_state.py",
    "app/media_info_dialog.py",
    "app/modern_info_dialog.py",
    "app/playlist_panel.py",
    "app/title_bar.py",
    "app/video_frame.py",
)


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_visual_identity_has_one_central_accent_and_font_family():
    assert config.UI_ACCENT == "#F26A3D"
    assert config.UI_ACCENT_HOVER == "#FF7A48"
    assert config.UI_FONT_FAMILY == '"Segoe UI Variable Text", "Segoe UI"'


def test_visible_surfaces_do_not_reintroduce_old_blue_or_second_orange():
    combined = "\n".join(path.read_text(encoding="utf-8")
                           for path in (ROOT / "app").glob("*.py"))
    for stale in ("#2E7DB8", "#2E9BD8", "#FF5A1F", "#FF6A32"):
        assert stale not in combined, f"eski vurgu rengi kaldi: {stale}"


def test_shared_style_applies_the_product_font_and_accent_tokens():
    style = config.APP_STYLE
    assert f"font-family: {config.UI_FONT_FAMILY}" in style
    assert config.UI_ACCENT in style
    assert "#2E7DB8" not in style and "#2E9BD8" not in style


def test_keyboard_focus_is_explicit_on_title_playlist_and_media_info():
    title = source("app/title_bar.py")
    playlist = source("app/playlist_panel.py")
    media = source("app/media_info_dialog.py")

    assert "QPushButton:focus" in title
    assert "QPushButton:focus" in playlist
    assert "QPushButton:focus" in media
    assert "QTabBar::tab:focus" in media


def test_media_info_actions_have_distinct_primary_and_secondary_surfaces():
    media = source("app/media_info_dialog.py")
    assert "QPushButton#mediaInfoCopyButton" in media
    assert "QPushButton#mediaInfoCloseButton" in media
    assert "border: 1px solid" in media


def test_shortcuts_dialog_is_compact_and_accepts_with_done_button():
    menu_actions = source("app/menu_actions.py")
    assert "shortcut_dialog.setFixedSize(450, 520)" in menu_actions
    assert 'cellspacing="4" cellpadding="0"' in menu_actions
    assert "ok_button.clicked.connect(shortcut_dialog.accept)" in menu_actions
    assert "ok_button.setDefault(True)" in menu_actions


def test_empty_state_is_raised_only_when_it_becomes_visible():
    video_frame = source("app/video_frame.py")
    block = video_frame[video_frame.index("def sync_empty_state"):]
    block = block[:block.index("def _create_control_overlay")]
    assert "if not surface.isVisible():" in block
    assert block.count("surface.raise_()") == 1
    assert block.index("surface.show()") < block.index("surface.raise_()")


def test_media_open_returns_focus_to_video_surface():
    media_controls = source("app/media_controls.py")
    assert "def _focus_video_surface_after_open" in media_controls
    assert media_controls.count("_focus_video_surface_after_open(player)") >= 2
    assert "refresh_modes()" in media_controls


def test_empty_state_startup_returns_focus_to_video_surface():
    source = (ROOT / "app" / "video_frame.py").read_text(encoding="utf-8")
    assert "self.setFocus(Qt.FocusReason.OtherFocusReason)" in source


def test_transparency_popup_cannot_take_global_resize_override():
    source = (ROOT / "app" / "title_bar.py").read_text(encoding="utf-8")
    assert "control_overlay = self.player.video_frame.control_overlay" in source
    assert "watched is control_overlay" in source
