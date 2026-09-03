# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Görünür tekrar/karışık kontrollerinin ürün davranışı sözleşmesi."""
import os
import inspect
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from app import media_controls
from app import player as player_module
from app.player import MPVPlayer
from app.video_frame import VideoFrame


class LoopMpv:
    def __init__(self):
        self.loop_file = "no"


def _mode_player(loop_file=False, loop_playlist=False):
    return SimpleNamespace(
        loop_file=loop_file,
        loop_playlist=loop_playlist,
        shuffle=False,
        playlist=["a.mkv", "b.mkv", "c.mkv"],
        current_playlist_index=0,
        mpv_player=LoopMpv(),
    )


def test_repeat_modes_are_mutually_exclusive_and_cycle_off_list_file_off():
    player = _mode_player()

    assert MPVPlayer.cycle_repeat_mode(player) == "playlist"
    assert (player.loop_file, player.loop_playlist) == (False, True)

    assert MPVPlayer.cycle_repeat_mode(player) == "file"
    assert (player.loop_file, player.loop_playlist) == (True, False)
    assert player.mpv_player.loop_file == "inf"

    assert MPVPlayer.cycle_repeat_mode(player) == "off"
    assert (player.loop_file, player.loop_playlist) == (False, False)
    assert player.mpv_player.loop_file == "no"


def test_failed_native_switch_keeps_existing_playlist_repeat_mode():
    class RefusingLoop:
        loop_file = "no"

        def __setattr__(self, name, value):
            if name == "loop_file":
                return
            super().__setattr__(name, value)

    player = _mode_player(loop_playlist=True)
    player.mpv_player = RefusingLoop()

    assert MPVPlayer.set_loop_file(player, True) is False
    assert (player.loop_file, player.loop_playlist) == (False, True)


def test_native_false_node_readback_is_canonical_no_not_a_failed_write():
    class NativeLikeLoop:
        def __init__(self):
            self._value = "inf"

        @property
        def loop_file(self):
            return False if self._value == "no" else self._value

        @loop_file.setter
        def loop_file(self, value):
            self._value = value

        def _get_property(self, name, fmt=None):
            assert name == "loop-file"
            return self._value

    player = _mode_player(loop_file=True)
    player.mpv_player = NativeLikeLoop()

    assert MPVPlayer.set_loop_file(player, False) is True
    assert player.loop_file is False
    assert player.mpv_player._value == "no"


def test_native_loop_readback_does_not_require_mpv_format_enum(monkeypatch):
    """GitHub CI'deki python-mpv yüzeyinde ``MpvFormat`` yoktur."""
    class NativeLikeLoop:
        def __init__(self):
            self._value = "inf"

        @property
        def loop_file(self):
            return False if self._value == "no" else self._value

        @loop_file.setter
        def loop_file(self, value):
            self._value = value

        def _get_property(self, name, fmt=None):
            assert name == "loop-file"
            assert fmt is None
            return self._value

    monkeypatch.delattr(player_module.mpv, "MpvFormat", raising=False)
    player = _mode_player(loop_file=True)
    player.mpv_player = NativeLikeLoop()

    assert MPVPlayer.set_loop_file(player, False) is True
    assert player.loop_file is False
    assert player.mpv_player._value == "no"


def test_shuffle_keeps_visible_playlist_order_and_builds_internal_order(
        monkeypatch):
    player = _mode_player()
    original = list(player.playlist)
    monkeypatch.setattr("random.shuffle", lambda values: values.reverse())

    assert MPVPlayer.toggle_shuffle(player, True) is True

    assert player.playlist == original
    assert player._shuffle_order == [0, 2, 1]
    assert player._shuffle_cursor == 0

    assert MPVPlayer.toggle_shuffle(player, False) is False
    assert player.playlist == original
    assert player._shuffle_order == []


def test_shuffle_next_previous_follow_internal_order_without_reordering_list(
        monkeypatch):
    player = _mode_player()
    monkeypatch.setattr("random.shuffle", lambda values: values.reverse())
    MPVPlayer.toggle_shuffle(player, True)

    assert media_controls._playlist_step_target(player, 1) == 2
    player.current_playlist_index = 2
    assert media_controls._playlist_step_target(player, 1) == 1
    assert media_controls._playlist_step_target(player, -1) == 0
    assert player.playlist == ["a.mkv", "b.mkv", "c.mkv"]


@pytest.mark.parametrize(
    "index,loop_playlist,expected",
    [(0, False, 1), (2, False, None), (2, True, 0)],
)
def test_natural_end_uses_real_playlist_progression(
        monkeypatch, index, loop_playlist, expected):
    calls = []
    player = SimpleNamespace(
        current_file="video.mkv",
        _core_idle=True,
        loop_file=False,
        loop_playlist=loop_playlist,
        shuffle=False,
        duration=10.0,
        position=10.0,
        playlist=["a.mkv", "b.mkv", "c.mkv"],
        current_playlist_index=index,
    )
    monkeypatch.setattr(
        media_controls, "play_from_playlist",
        lambda _player, target: calls.append(("play", target)) or True)
    monkeypatch.setattr(
        media_controls, "finish_media_at_start",
        lambda _player: calls.append(("finish", None)) or True)

    assert media_controls.handle_natural_end(player) is True

    if expected is None:
        assert calls == [("finish", None)]
    else:
        assert calls == [("play", expected)]


def test_update_ui_routes_eof_through_the_single_natural_end_handler():
    source = inspect.getsource(MPVPlayer.update_ui)

    assert "handle_natural_end(self)" in source
    assert "finish_media_at_start(self)" not in source


@pytest.fixture
def overlay_window():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.central_widget = QWidget(window)
    window.setCentralWidget(window.central_widget)
    window.main_layout = QVBoxLayout(window.central_widget)
    window.is_paused = True
    window.current_file = "video.mkv"
    window.duration = 30
    window.position = 5
    window.loop_file = False
    window.loop_playlist = False
    window.shuffle = False
    frame = VideoFrame(window)
    window.video_frame = frame
    window.main_layout.addWidget(frame)
    window.resize(1280, 720)
    window.show()
    app.processEvents()
    yield app, window, frame
    frame.close_control_overlay()
    window.close()
    window.deleteLater()
    app.processEvents()


def test_option_b_places_repeat_and_shuffle_before_subtitles(overlay_window):
    _app, _window, frame = overlay_window
    row = frame._overlay_right_row

    assert row.indexOf(frame.overlay_repeat_button) >= 0
    assert row.indexOf(frame.overlay_shuffle_button) >= 0
    assert row.indexOf(frame.overlay_repeat_button) < row.indexOf(
        frame.overlay_shuffle_button)
    assert row.indexOf(frame.overlay_shuffle_button) < row.indexOf(
        frame.overlay_subtitles_button)


def test_option_b_compacts_icons_while_preserving_click_targets(
        overlay_window):
    _app, _window, frame = overlay_window

    assert frame._overlay_right_row.spacing() == 0
    buttons = (frame.overlay_repeat_button, frame.overlay_shuffle_button,
               frame.overlay_subtitles_button,
               frame.overlay_settings_button,
               frame.overlay_volume_button,
               frame.overlay_fullscreen_button)
    for button in buttons:
        assert button.width() == 40
        assert button.height() == 40
        assert button.iconSize().width() == 28
    centres = [button.geometry().center().x() for button in buttons[:5]]
    assert [right - left for left, right in zip(centres, centres[1:])] == [40] * 4


def test_overlay_repeat_and_shuffle_state_is_visible_and_accessible(
        overlay_window):
    _app, window, frame = overlay_window

    window.loop_playlist = True
    window.loop_file = False
    window.shuffle = True
    frame.update_overlay_playback_modes()

    assert frame.overlay_repeat_button.accessibleName() == "Listeyi Tekrarla"
    assert frame.overlay_repeat_button.property("modeActive") is True
    assert frame.overlay_shuffle_button.accessibleName() == "Karışık Oynat: Açık"
    assert frame.overlay_shuffle_button.property("modeActive") is True

    window.loop_playlist = False
    window.loop_file = True
    frame.update_overlay_playback_modes()

    assert frame.overlay_repeat_button.accessibleName() == "Tek Dosyayı Tekrarla"
    assert frame.overlay_repeat_button.property("repeatOne") is True


def test_visible_overlay_buttons_dispatch_one_repeat_cycle_and_shuffle_toggle(
        overlay_window):
    app, window, frame = overlay_window
    calls = []
    window.cycle_repeat_mode = lambda: calls.append("repeat")
    window.toggle_shuffle = lambda enabled: calls.append(("shuffle", enabled))
    frame.control_overlay.show()
    app.processEvents()

    frame.overlay_repeat_button.click()
    frame.overlay_shuffle_button.click()

    assert calls == ["repeat", ("shuffle", True)]
