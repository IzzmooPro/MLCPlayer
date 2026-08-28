# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Durdurma, yükleme ve doğal medya sonu için dar yaşam döngüsü sözleşmeleri."""
from types import SimpleNamespace

import pytest

from app.media_controls import (_load_media_without_blocking_ui,
                                finish_media_at_start,
                                natural_end_should_rewind, play_pause, stop,
                                seek_position, set_playback_speed, set_volume,
                                toggle_mute, toggle_subtitles)
from app.video_frame import VideoFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QSlider


class AsyncMpv:
    def __init__(self):
        self.calls = []
        self.pause = False

    def command_async(self, name, *args):
        self.calls.append((name, args))

    def stop(self):
        raise AssertionError("GUI thread'ini bekleten senkron stop çağrılmamalı")


def _player(mpv):
    overlay = SimpleNamespace(update_overlay_play_state=lambda: None)
    frame = SimpleNamespace(control_overlay=overlay,
                            update_overlay_play_state=lambda: None,
                            placeholder_label=SimpleNamespace(show=lambda: None))
    label = SimpleNamespace(setText=lambda _text: None)
    slider = SimpleNamespace(setValue=lambda _value: None)
    return SimpleNamespace(
        mpv_player=mpv, play_button=SimpleNamespace(setIcon=lambda _icon: None),
        play_icon=object(), pause_icon=object(), is_paused=False,
        duration=12.0, position=11.9,
        _load_started_at=1.0, _core_idle=True, _audio_menu_file="x",
        _chapter_menu_file="x", _pending_subs=["x"], current_file="x.mkv",
        video_frame=frame, set_title=lambda: None, position_slider=slider,
        current_time_label=label, total_time_label=label,
        _updating_position_slider=False)


def test_stop_submits_non_blocking_mpv_command_before_resetting_ui():
    mpv = AsyncMpv()
    player = _player(mpv)

    assert stop(player) is True

    assert mpv.calls == [("stop", ())]
    assert player.current_file == ""
    assert player.duration == 0
    assert player.position == 0


def test_failed_stop_submission_keeps_current_playback_state():
    mpv = AsyncMpv()
    mpv.command_async = lambda *_args: (_ for _ in ()).throw(RuntimeError())
    player = _player(mpv)
    before = (player.current_file, player.duration, player.position,
              player.is_paused, player._core_idle)

    assert stop(player) is False

    assert (player.current_file, player.duration, player.position,
            player.is_paused, player._core_idle) == before


def test_media_load_is_queued_without_waiting_on_sync_play():
    mpv = AsyncMpv()

    _load_media_without_blocking_ui(mpv, "movie.mkv")

    assert mpv.calls == [("loadfile", ("movie.mkv", "replace"))]


def test_hidden_playlist_is_rebuilt_only_when_user_opens_it():
    calls = []
    panel = SimpleNamespace(is_open=False,
                            refresh=lambda: calls.append("refresh"))
    frame = SimpleNamespace(playlist_panel=panel)

    VideoFrame.refresh_playlist_panel(frame)
    assert calls == []

    panel.is_open = True
    VideoFrame.refresh_playlist_panel(frame)
    assert calls == ["refresh"]


def test_natural_end_rewinds_to_zero_and_pauses_without_advancing_playlist():
    mpv = AsyncMpv()
    player = _player(mpv)
    player.playlist = ["first.mkv", "second.mkv"]
    player.current_playlist_index = 0
    player._eof_rewound = False

    assert finish_media_at_start(player) is True

    assert mpv.pause is True
    assert mpv.calls == [("seek", (0, "absolute+exact"))]
    assert player.position == 0
    assert player.is_paused is True
    assert player.current_playlist_index == 0
    assert player._eof_rewound is True


def test_natural_end_is_one_shot_until_a_new_media_load_resets_it():
    mpv = AsyncMpv()
    player = _player(mpv)
    player._eof_rewound = True

    assert finish_media_at_start(player) is False
    assert mpv.calls == []


def test_play_after_natural_end_restarts_from_zero_before_unpausing():
    mpv = AsyncMpv()
    mpv.pause = True
    player = _player(mpv)
    player._eof_rewound = True
    player._core_idle = True
    player.is_paused = True

    play_pause(player)

    assert mpv.calls == [("seek", (0, "absolute+exact"))]
    assert mpv.pause is False
    assert player.is_paused is False


def test_rapid_play_pause_play_after_natural_end_rewinds_only_once():
    mpv = AsyncMpv()
    mpv.pause = True
    player = _player(mpv)
    player._eof_rewound = True
    player._core_idle = True
    player.is_paused = True

    play_pause(player)
    play_pause(player)
    play_pause(player)

    assert mpv.calls == [("seek", (0, "absolute+exact"))]
    assert mpv.pause is False
    assert player.is_paused is False
    assert player._eof_rewound is False
    assert player._core_idle is False


def test_failed_restart_after_natural_end_keeps_paused_ui_state():
    mpv = AsyncMpv()
    mpv.pause = True
    mpv.command_async = lambda *_args: (_ for _ in ()).throw(RuntimeError())
    player = _player(mpv)
    player._eof_rewound = True
    player._core_idle = True
    player.is_paused = True

    play_pause(player)

    assert mpv.pause is True
    assert player.is_paused is True


@pytest.mark.parametrize("initial_paused", [False, True])
def test_failed_regular_pause_toggle_keeps_ui_state(initial_paused):
    class RejectPause:
        @property
        def pause(self):
            return initial_paused

        @pause.setter
        def pause(self, _value):
            raise RuntimeError("pause write rejected")

    player = _player(RejectPause())
    player.is_paused = initial_paused
    player._eof_rewound = False
    player._core_idle = False

    assert play_pause(player) is False
    assert player.is_paused is initial_paused


def _volume_player(mpv):
    return SimpleNamespace(
        mpv_player=mpv, last_volume=70, is_muted=False, _ui_ready=False,
        volume_slider=SimpleNamespace(setValue=lambda _value: None),
        volume_label=SimpleNamespace(setText=lambda _text: None),
        volume_icon=SimpleNamespace(setIcon=lambda _icon: None),
        style=lambda: SimpleNamespace(standardIcon=lambda _kind: object()))


def test_repeated_mute_round_trips_restore_the_original_volume():
    mpv = SimpleNamespace(volume=70)
    player = _volume_player(mpv)

    for _index in range(3):
        toggle_mute(player)
        toggle_mute(player)

    assert mpv.volume == 70
    assert player.last_volume == 70
    assert player.is_muted is False


def test_mute_read_failure_does_not_guess_and_change_the_volume():
    class UnreadableVolume:
        @property
        def volume(self):
            raise RuntimeError("volume unreadable")

        @volume.setter
        def volume(self, _value):
            raise AssertionError("unreadable state must not be overwritten")

    player = _volume_player(UnreadableVolume())

    assert toggle_mute(player) is False
    assert player.is_muted is False


def test_failed_volume_write_restores_both_visible_sliders():
    class RejectVolume:
        volume = 70

        def __setattr__(self, name, value):
            if name == "volume":
                raise RuntimeError("volume write rejected")
            super().__setattr__(name, value)

    app = QApplication.instance() or QApplication([])
    main_slider = QSlider(Qt.Orientation.Horizontal)
    overlay_slider = QSlider(Qt.Orientation.Horizontal)
    for slider in (main_slider, overlay_slider):
        slider.setRange(0, 175)
        slider.setValue(95)
    player = _volume_player(RejectVolume())
    player.volume_slider = main_slider
    player.video_frame = SimpleNamespace(overlay_volume_slider=overlay_slider)
    player.volume_label = QLabel()
    player.volume_icon = QPushButton()
    player.style = app.style

    assert set_volume(player, 95) is False
    assert main_slider.value() == 70
    assert overlay_slider.value() == 70


def test_failed_seek_restores_main_and_overlay_timelines():
    class RejectSeek:
        time_pos = 10.0

        def __setattr__(self, name, value):
            if name == "time_pos":
                raise RuntimeError("seek rejected")
            super().__setattr__(name, value)

    app = QApplication.instance() or QApplication([])
    main_slider = QSlider(Qt.Orientation.Horizontal)
    overlay_slider = QSlider(Qt.Orientation.Horizontal)
    for slider in (main_slider, overlay_slider):
        slider.setRange(0, 1000)
        slider.setValue(900)
    player = SimpleNamespace(
        mpv_player=RejectSeek(), duration=100.0,
        _updating_position_slider=False, position_slider=main_slider,
        video_frame=SimpleNamespace(overlay_timeline=overlay_slider))

    assert seek_position(player, 900) is False
    assert main_slider.value() == 100
    assert overlay_slider.value() == 100


def test_failed_speed_write_restores_the_single_previous_check(monkeypatch):
    class RejectSpeed:
        speed = 1.0

        def __setattr__(self, name, value):
            if name == "speed":
                raise RuntimeError("speed rejected")
            super().__setattr__(name, value)

    old_action = QAction("1.0x")
    old_action.setCheckable(True)
    old_action.setChecked(False)
    new_action = QAction("1.5x")
    new_action.setCheckable(True)
    new_action.setChecked(True)
    player = SimpleNamespace(
        mpv_player=RejectSpeed(),
        speed_actions={1.0: old_action, 1.5: new_action})
    monkeypatch.setattr("app.media_controls.show_user_error",
                        lambda *_args, **_kwargs: None)

    assert set_playback_speed(player, 1.5) is False
    assert old_action.isChecked() is True
    assert new_action.isChecked() is False


def test_silently_ignored_volume_write_is_not_reported_as_success():
    class SilentVolume:
        def __init__(self):
            self._volume = 70

        @property
        def volume(self):
            return self._volume

        @volume.setter
        def volume(self, _value):
            pass

    app = QApplication.instance() or QApplication([])
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 175)
    slider.setValue(95)
    player = _volume_player(SilentVolume())
    player.volume_slider = slider
    player.volume_label = QLabel()
    player.volume_icon = QPushButton()
    player.style = app.style

    assert set_volume(player, 95) is False
    assert slider.value() == 70


def test_silently_ignored_speed_write_restores_the_previous_check(
        monkeypatch):
    class SilentSpeed:
        def __init__(self):
            self._speed = 1.0

        @property
        def speed(self):
            return self._speed

        @speed.setter
        def speed(self, _value):
            pass

    old_action = QAction("1.0x")
    old_action.setCheckable(True)
    new_action = QAction("1.5x")
    new_action.setCheckable(True)
    new_action.setChecked(True)
    player = SimpleNamespace(
        mpv_player=SilentSpeed(),
        speed_actions={1.0: old_action, 1.5: new_action})
    monkeypatch.setattr("app.media_controls.show_user_error",
                        lambda *_args, **_kwargs: None)

    assert set_playback_speed(player, 1.5) is False
    assert old_action.isChecked() is True
    assert new_action.isChecked() is False


def test_failed_subtitle_visibility_toggle_restores_the_previous_sid(
        monkeypatch):
    class RejectVisibility:
        track_list = [{"id": 4, "type": "sub"}]
        sid = None

        @property
        def sub_visibility(self):
            return False

        @sub_visibility.setter
        def sub_visibility(self, _value):
            raise RuntimeError("visibility write rejected")

    refreshed = []
    player = SimpleNamespace(
        mpv_player=RejectVisibility(),
        video_frame=SimpleNamespace(
            show_osd=lambda *_a, **_k: None,
            _update_overlay_subtitle_state=lambda: refreshed.append(True)))
    monkeypatch.setattr("app.media_controls.show_user_error",
                        lambda *_a, **_k: None)

    assert toggle_subtitles(player) is False
    assert player.mpv_player.sid is None


def test_finite_url_rewinds_even_though_url_playback_has_no_playlist():
    player = SimpleNamespace(
        _core_idle=True, loop_file=False, duration=120.0, position=119.9,
        current_file="https://example.invalid/video", playlist=[])

    assert natural_end_should_rewind(player) is True


def test_idle_state_without_an_open_media_never_triggers_end_rewind():
    player = SimpleNamespace(
        _core_idle=True, loop_file=False, duration=120.0, position=119.9,
        current_file="", playlist=[])

    assert natural_end_should_rewind(player) is False


def test_live_or_invalid_timing_never_triggers_end_rewind():
    base = dict(
        _core_idle=True, loop_file=False,
        current_file="https://example.invalid/live", playlist=[])

    assert natural_end_should_rewind(SimpleNamespace(
        **base, duration=float("inf"), position=300.0)) is False
    assert natural_end_should_rewind(SimpleNamespace(
        **base, duration=300.0, position=float("nan"))) is False
