# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Şeffaflık ve PiP ana HWND'yi koruyan oturumluk pencere modlarıdır."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QRect, QSize
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from app.player import MPVPlayer
from app.window_modes import PIP_MIN_SIZE, keep_rect_inside


@pytest.fixture
def mode_window():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.setMinimumSize(400, 300)
    window.setGeometry(80, 90, 900, 600)
    window.window_opacity_percent = 100
    window.window_transparency_enabled = False
    window.picture_in_picture_enabled = False
    window._pip_restore_geometry = None
    window._pip_restore_maximized = False
    title_bar = QWidget(window)
    title_bar.update_window_mode_state = lambda: None
    title_bar.hide_transparency_control = lambda: None
    title_bar.show()
    window.title_bar = title_bar
    window.ensure_title_bar_on_top = lambda: None
    mode_calls = []
    window.video_frame = SimpleNamespace(
        is_video_fullscreen=False, exit_fullscreen=lambda: None,
        update_overlay_geometry=lambda: None,
        set_picture_in_picture_mode=lambda enabled: mode_calls.append(enabled))
    window.mode_calls = mode_calls
    window.show()
    app.processEvents()
    yield app, window
    window.close()
    window.deleteLater()
    app.processEvents()


def test_transparency_is_adjustable_and_clamped(mode_window):
    app, window = mode_window

    assert MPVPlayer.set_window_opacity_percent(window, 58) == 58
    assert window.windowOpacity() == pytest.approx(0.58, abs=0.01)
    assert MPVPlayer.set_window_opacity_percent(window, 5) == 35
    assert window.windowOpacity() == pytest.approx(0.35, abs=0.01)
    assert MPVPlayer.set_window_opacity_percent(window, 150) == 100
    assert window.windowOpacity() == pytest.approx(1.0, abs=0.01)


def test_delayed_media_raise_cannot_restore_title_inside_pip(mode_window):
    app, window = mode_window
    window.cinematic_ui_enabled = True
    window.picture_in_picture_enabled = True
    window.title_bar.hide()

    MPVPlayer.ensure_title_bar_on_top(window)

    assert window.title_bar.isVisible() is False


def test_fullscreen_command_is_ignored_while_pip_is_active(mode_window):
    app, window = mode_window
    window.picture_in_picture_enabled = True
    window.video_frame.enter_fullscreen = lambda: pytest.fail(
        "PiP must not enter fullscreen")

    assert MPVPlayer.toggle_fullscreen(window) is False


def test_resized_pip_stays_inside_available_screen():
    available = QRect(0, 0, 2560, 1392)

    bounded = keep_rect_inside(QRect(2024, 1098, 560, 315), available)

    assert bounded == QRect(2000, 1077, 560, 315)


def test_pip_is_small_resizable_topmost_and_restores_geometry(
        mode_window, monkeypatch):
    app, window = mode_window
    calls = []
    monkeypatch.setattr("app.player.set_native_topmost",
                        lambda _window, enabled: calls.append(enabled) or True)
    original = QRect(window.geometry())
    real_show_normal = window.showNormal
    # Gercek Windows'ta gozlenen Qt davranisi: parent durum degisimi child
    # basligi yeniden gosterebilir. Urun gizlemeyi bundan sonra yapmalidir.
    window.showNormal = lambda: (real_show_normal(), window.title_bar.show())

    assert MPVPlayer.toggle_picture_in_picture(window, True) is True
    assert window.size() == QSize(480, 270)
    assert window.minimumSize() == PIP_MIN_SIZE
    assert window.title_bar.isVisible() is False
    assert window.mode_calls == [True]
    assert calls == [True]

    assert MPVPlayer.toggle_picture_in_picture(window, False) is False
    assert calls == [True, False]
    assert window.geometry() == original
    assert window.minimumSize() == QSize(400, 300)
    assert window.title_bar.isVisible() is True
    assert window.mode_calls == [True, False]


def test_pip_stays_enabled_if_windows_cannot_release_topmost(
        mode_window, monkeypatch):
    app, window = mode_window
    answers = iter((True, False))
    monkeypatch.setattr("app.player.set_native_topmost",
                        lambda _window, _enabled: next(answers))

    assert MPVPlayer.toggle_picture_in_picture(window, True) is True
    assert MPVPlayer.toggle_picture_in_picture(window, False) is True
    assert window.picture_in_picture_enabled is True
