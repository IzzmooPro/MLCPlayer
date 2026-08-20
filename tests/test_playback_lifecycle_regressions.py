# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Durdurma, yükleme ve doğal medya sonu için dar yaşam döngüsü sözleşmeleri."""
from types import SimpleNamespace

from app.media_controls import (_load_media_without_blocking_ui,
                                finish_media_at_start,
                                natural_end_should_rewind, stop)
from app.video_frame import VideoFrame


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
        play_icon=object(), is_paused=False, duration=12.0, position=11.9,
        _load_started_at=1.0, _core_idle=True, _audio_menu_file="x",
        _chapter_menu_file="x", _pending_subs=["x"], current_file="x.mkv",
        video_frame=frame, set_title=lambda: None, position_slider=slider,
        current_time_label=label, total_time_label=label,
        _updating_position_slider=False)


def test_stop_submits_non_blocking_mpv_command_before_resetting_ui():
    mpv = AsyncMpv()
    player = _player(mpv)

    stop(player)

    assert mpv.calls == [("stop", ())]
    assert player.current_file == ""
    assert player.duration == 0
    assert player.position == 0


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
