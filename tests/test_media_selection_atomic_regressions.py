# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yeni medya seçimi senkron reddedilirse eski oturum atomik kalmalıdır."""
from types import SimpleNamespace

from app import media_controls
from app.playlist_panel import PlaylistPanel


class RejectingMpv:
    def __init__(self):
        self.calls = []
        self.sub_delay = 1.25
        self.sub_visibility = True
        self.pause = False

    def command_async(self, name, *args):
        self.calls.append((name, args))
        raise RuntimeError("native command rejected")


class Placeholder:
    def __init__(self):
        self._text = media_controls.PLACEHOLDER_DEFAULT_TEXT
        self.visible = False

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text

    def setVisible(self, visible):
        self.visible = bool(visible)


def player_state():
    mpv = RejectingMpv()
    placeholder = Placeholder()
    panel = SimpleNamespace(is_open=True, refresh=lambda: None)
    overlay = SimpleNamespace(update_overlay_play_state=lambda: None)
    frame = SimpleNamespace(
        placeholder_label=placeholder, playlist_panel=panel,
        control_overlay=overlay, update_overlay_play_state=lambda: None,
        sync_empty_state=lambda: None)
    return SimpleNamespace(
        mpv_player=mpv,
        playlist=["old-a.mkv", "old-b.mkv"],
        current_playlist_index=0,
        current_file="old-a.mkv",
        last_dir="C:/old",
        duration=90.0,
        position=27.0,
        is_paused=False,
        _core_idle=False,
        _audio_menu_file="old-a.mkv",
        _chapter_menu_file="old-a.mkv",
        _pending_subs=["old.srt"],
        _load_started_at=10.0,
        _title_bar_raise_pending=False,
        _eof_rewound=False,
        _url_loading_active=False,
        _url_loading_started_at=0.0,
        settings=None,
        video_frame=frame,
        play_button=SimpleNamespace(setIcon=lambda _icon: None),
        play_icon=object(), pause_icon=object(),
        set_title=lambda: None,
        add_recent_file=lambda _path: None,
        clear_title_bar_raise_pending=lambda: None,
        mark_title_bar_raise_pending=lambda: None,
        position_slider=SimpleNamespace(setValue=lambda _value: None),
        current_time_label=SimpleNamespace(setText=lambda _text: None),
        total_time_label=SimpleNamespace(setText=lambda _text: None),
        _updating_position_slider=False)


def snapshot(player):
    return (list(player.playlist), player.current_playlist_index,
            player.current_file, player.last_dir, player.duration,
            player.position, player.is_paused, player._core_idle,
            list(player._pending_subs), player.mpv_player.sub_delay,
            player.mpv_player.sub_visibility,
            player._url_loading_active)


def silence_errors(monkeypatch):
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda *_args, **_kwargs: None)


def test_failed_direct_file_open_restores_the_previous_session(
        tmp_path, monkeypatch):
    player = player_state()
    new_media = tmp_path / "new.mkv"
    new_media.write_bytes(b"x")
    before = snapshot(player)
    silence_errors(monkeypatch)

    result = media_controls.open_path(player, str(new_media))

    assert result is False
    assert snapshot(player) == before


def test_failed_url_open_restores_playlist_and_previous_media(monkeypatch):
    player = player_state()
    before = snapshot(player)
    silence_errors(monkeypatch)

    result = media_controls.open_media_url(
        player, "https://example.test/new-video")

    assert result is False
    assert snapshot(player) == before
    assert player.video_frame.placeholder_label.visible is False


def test_external_local_target_propagates_the_open_failure(monkeypatch):
    player = player_state()
    monkeypatch.setattr(media_controls, "open_path", lambda *_args: False)

    assert media_controls.open_external_target(player, r"C:\new.mkv") is False


def test_failed_playlist_file_load_restores_the_previous_session(
        tmp_path, monkeypatch):
    player = player_state()
    new_media = tmp_path / "new.mkv"
    new_media.write_bytes(b"x")
    playlist_file = tmp_path / "new.m3u"
    playlist_file.write_text(str(new_media), encoding="utf-8")
    monkeypatch.setattr(
        media_controls.QFileDialog, "getOpenFileName",
        lambda *_args, **_kwargs: (str(playlist_file), ""))
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = media_controls.load_playlist(player)

    assert result is False
    assert snapshot(player) == before
    assert [name for name, _args in player.mpv_player.calls] == ["loadfile"]


def test_failed_replacement_after_removing_active_item_restores_the_list(
        monkeypatch):
    player = player_state()
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = media_controls.remove_from_playlist(player, 0)

    assert result is False
    assert snapshot(player) == before


def test_failed_stop_does_not_clear_the_playlist(monkeypatch):
    player = player_state()
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = media_controls.clear_playlist(player)

    assert result is False
    assert snapshot(player) == before


def test_failed_first_drop_does_not_leave_unplayable_queue(monkeypatch):
    player = player_state()
    player.playlist = []
    player.current_playlist_index = -1
    player.current_file = ""
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = media_controls.append_media_paths(player, ["new-a.mkv", "new-b.mkv"])

    assert result is False
    assert snapshot(player) == before


def test_failed_add_dialog_does_not_leave_unplayable_queue(monkeypatch):
    player = player_state()
    player.playlist = []
    player.current_playlist_index = -1
    player.current_file = ""
    monkeypatch.setattr(
        media_controls.QFileDialog, "getOpenFileNames",
        lambda *_args, **_kwargs: (["new-a.mkv", "new-b.mkv"], ""))
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = media_controls.add_to_playlist(player)

    assert result is False
    assert snapshot(player) == before


def test_failed_panel_external_add_does_not_leave_unplayable_queue(
        tmp_path, monkeypatch):
    player = player_state()
    player.playlist = []
    player.current_playlist_index = -1
    player.current_file = ""
    media = tmp_path / "new.mkv"
    media.write_bytes(b"x")
    panel = SimpleNamespace(player=player, refresh=lambda: None)
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = PlaylistPanel.add_external_files(panel, [str(media)])

    assert result is False
    assert snapshot(player) == before
