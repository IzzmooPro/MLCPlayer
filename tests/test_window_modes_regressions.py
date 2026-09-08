# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Şeffaflık ve PiP ana HWND'yi koruyan oturumluk pencere modlarıdır."""
import os
from ctypes import wintypes
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QRect, QSize
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

import app.window_modes as window_modes
from app.player import MPVPlayer
from app.window_modes import (PIP_MIN_SIZE, keep_rect_inside,
                              set_native_window_geometry)


@pytest.fixture
def mode_window():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.setMinimumSize(400, 300)
    window.setGeometry(80, 90, 900, 600)
    window.window_opacity_percent = 100
    window.window_transparency_enabled = False
    window.picture_in_picture_enabled = False
    window.current_file = "fixture.mp4"
    window._pip_media_available = True
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


def test_repeated_fullscreen_toggles_return_to_windowed_state(mode_window):
    app, window = mode_window

    def enter():
        window.video_frame.is_video_fullscreen = True

    def exit_():
        window.video_frame.is_video_fullscreen = False

    window.video_frame.enter_fullscreen = enter
    window.video_frame.exit_fullscreen = exit_

    for _index in range(3):
        assert MPVPlayer.toggle_fullscreen(window) is True
        assert window.video_frame.is_video_fullscreen is True
        assert MPVPlayer.toggle_fullscreen(window) is True
        assert window.video_frame.is_video_fullscreen is False


def test_resized_pip_stays_inside_available_screen():
    available = QRect(0, 0, 2560, 1392)

    bounded = keep_rect_inside(QRect(2024, 1098, 560, 315), available)

    assert bounded == QRect(2000, 1077, 560, 315)


def test_native_window_geometry_maps_qt_work_area_to_monitor_pixels(
        mode_window, monkeypatch):
    app, window = mode_window
    calls = []

    class User32:
        def MonitorFromWindow(self, hwnd, fallback):
            calls.append(("monitor", hwnd.value, fallback))
            return 7

        def GetMonitorInfoW(self, monitor, pointer):
            info = pointer._obj
            info.rcWork.left = 200
            info.rcWork.top = 100
            info.rcWork.right = 2200
            info.rcWork.bottom = 1500
            return 1

        def ShowWindow(self, hwnd, command):
            calls.append(("show", hwnd.value, command))
            return 1

        def SetWindowPos(self, hwnd, insert_after, x, y, width, height,
                         flags):
            calls.append(("position", hwnd.value, insert_after.value,
                          x, y, width, height, flags))
            return 1

    window.screen = lambda: SimpleNamespace(
        availableGeometry=lambda: QRect(100, 50, 1000, 700))
    monkeypatch.setattr(window_modes, "_user32", User32())
    monkeypatch.setattr(window_modes, "_native_window_geometry_supported",
                        lambda: True)

    assert set_native_window_geometry(
        window, QRect(300, 250, 400, 300)) is True
    hwnd = int(window.winId())
    assert calls == [
        ("monitor", hwnd, 2),
        ("show", hwnd, 4),
        ("position", hwnd, None, 600, 500, 800, 600, 0x0214),
    ]


def test_native_topmost_keeps_existing_hwnd_and_never_activates(
        mode_window, monkeypatch):
    app, window = mode_window
    calls = []

    class User32:
        def SetWindowPos(self, hwnd, insert_after, x, y, width, height,
                         flags):
            calls.append((hwnd.value, insert_after.value, x, y,
                          width, height, flags))
            return 1

    monkeypatch.setattr(window_modes, "_user32", User32())

    assert window_modes.set_native_topmost(window, True) is True
    assert window_modes.set_native_topmost(window, False) is True
    hwnd = int(window.winId())
    assert calls == [
        (hwnd, wintypes.HWND(-1).value, 0, 0, 0, 0, 0x0013),
        (hwnd, wintypes.HWND(-2).value, 0, 0, 0, 0, 0x0013),
    ]


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


def test_pip_does_not_open_without_loaded_media(mode_window, monkeypatch):
    app, window = mode_window
    window.current_file = ""
    monkeypatch.setattr("app.player.set_native_topmost",
                        lambda *_args: pytest.fail("PiP must not enter"))

    assert MPVPlayer.toggle_picture_in_picture(window, True) is False
    assert window.picture_in_picture_enabled is False


@pytest.mark.parametrize("path", ("audio-only.mp3", "pending-video.mkv"))
def test_pip_requires_an_observed_video_track_not_only_a_path(
        mode_window, monkeypatch, path):
    app, window = mode_window
    window.current_file = path
    window._pip_media_available = False
    monkeypatch.setattr("app.player.set_native_topmost",
                        lambda *_args: pytest.fail("PiP must not enter"))

    assert MPVPlayer.toggle_picture_in_picture(window, True) is False
    assert window.picture_in_picture_enabled is False


def test_observed_video_track_enables_pip_but_audio_track_does_not(mode_window):
    app, window = mode_window
    calls = []
    window.title_bar.update_window_mode_state = lambda: calls.append(True)
    window._pip_media_available = False

    assert MPVPlayer._set_picture_in_picture_media_available(
        window, [{"type": "audio"}], "fixture.mp4") is False
    assert window._pip_media_available is False
    assert MPVPlayer._set_picture_in_picture_media_available(
        window, [{"type": "video"}, {"type": "audio"}], "fixture.mp4") is True
    assert window._pip_media_available is True
    assert calls == [True]


@pytest.mark.parametrize("selected,observed,expected", [
    ("I:/Film/video.mkv", r"I:\Film\video.mkv", True),
    ("I:/Film/VIDEO.mkv", r"i:\film\video.mkv", True),
    ("//server/share/video.mkv", r"\\server\share\video.mkv", True),
    ("I:/Film/video.mkv", r"I:\Film\other.mkv", False),
    ("https://example.test/Video.mkv", "https://example.test/video.mkv", False),
    ("https://example.test/v?token=A", "https://example.test/v?token=a", False),
    ("https://example.test/v", "https://example.test/v", True),
    ("", "", False),
    (None, None, False),
])
def test_pip_observed_path_identity(mode_window, selected, observed, expected):
    app, window = mode_window
    window.current_file = selected
    window._pip_media_available = False

    assert MPVPlayer._set_picture_in_picture_media_available(
        window, [{"type": "video"}], observed) is expected
    assert window._pip_media_available is expected


def test_previous_media_track_snapshot_cannot_enable_pip_for_new_path(
        mode_window):
    app, window = mode_window
    window.current_file = "new-audio.mp3"
    window._pip_media_available = False

    assert MPVPlayer._set_picture_in_picture_media_available(
        window, [{"type": "video"}], "previous-video.mkv") is False
    assert window._pip_media_available is False


def test_repeated_pip_cycles_restore_the_same_geometry(mode_window,
                                                       monkeypatch):
    app, window = mode_window
    monkeypatch.setattr("app.player.set_native_topmost",
                        lambda _window, _enabled: True)
    original = QRect(window.geometry())

    for _index in range(3):
        assert MPVPlayer.toggle_picture_in_picture(window, True) is True
        assert MPVPlayer.toggle_picture_in_picture(window, False) is False
        assert window.geometry() == original
        assert window.minimumSize() == QSize(400, 300)


def test_failed_native_loop_toggle_keeps_the_previous_local_state():
    class RejectLoop:
        @property
        def loop_file(self):
            return "no"

        @loop_file.setter
        def loop_file(self, _value):
            raise RuntimeError("loop write rejected")

    player = SimpleNamespace(loop_file=False, mpv_player=RejectLoop())

    assert MPVPlayer.set_loop_file(player, True) is False
    assert player.loop_file is False


def test_repeated_native_loop_toggles_return_to_disabled_state():
    player = SimpleNamespace(
        loop_file=False, mpv_player=SimpleNamespace(loop_file="no"))

    for _index in range(3):
        assert MPVPlayer.set_loop_file(player, True) is True
        assert player.loop_file is True
        assert player.mpv_player.loop_file == "inf"
        assert MPVPlayer.set_loop_file(player, False) is True

    assert player.loop_file is False
    assert player.mpv_player.loop_file == "no"


def test_silently_ignored_native_loop_write_keeps_local_state():
    class SilentLoop:
        def __init__(self):
            self._value = "no"

        @property
        def loop_file(self):
            return self._value

        @loop_file.setter
        def loop_file(self, _value):
            pass

    player = SimpleNamespace(loop_file=False, mpv_player=SilentLoop())

    assert MPVPlayer.set_loop_file(player, True) is False
    assert player.loop_file is False
    assert player.mpv_player.loop_file == "no"


def test_pip_stays_enabled_if_windows_cannot_release_topmost(
        mode_window, monkeypatch):
    app, window = mode_window
    answers = iter((True, False))
    monkeypatch.setattr("app.player.set_native_topmost",
                        lambda _window, _enabled: next(answers))

    assert MPVPlayer.toggle_picture_in_picture(window, True) is True
    assert MPVPlayer.toggle_picture_in_picture(window, False) is True
    assert window.picture_in_picture_enabled is True


def test_failed_pip_entry_restores_the_previous_fullscreen_mode(
        mode_window, monkeypatch):
    app, window = mode_window
    transitions = []
    window.video_frame.is_video_fullscreen = True

    def exit_fullscreen():
        transitions.append("exit")
        window.video_frame.is_video_fullscreen = False

    def enter_fullscreen():
        transitions.append("enter")
        window.video_frame.is_video_fullscreen = True

    window.video_frame.exit_fullscreen = exit_fullscreen
    window.video_frame.enter_fullscreen = enter_fullscreen
    monkeypatch.setattr("app.player.set_native_topmost",
                        lambda _window, _enabled: False)

    assert MPVPlayer.toggle_picture_in_picture(window, True) is False
    assert transitions == ["exit", "enter"]
    assert window.video_frame.is_video_fullscreen is True
    assert window.picture_in_picture_enabled is False
