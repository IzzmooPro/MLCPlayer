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
    player = SimpleNamespace(
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
        _pip_media_available=True,
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
    title_bar = SimpleNamespace(pip_enabled=True, refreshes=0)

    def refresh_window_modes():
        title_bar.refreshes += 1
        title_bar.pip_enabled = bool(
            player.current_file and player._pip_media_available)

    title_bar.update_window_mode_state = refresh_window_modes
    player.title_bar = title_bar
    return player


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


def test_failed_file_open_restores_the_pip_button_state(tmp_path, monkeypatch):
    player = player_state()
    new_media = tmp_path / "new.mkv"
    new_media.write_bytes(b"x")
    silence_errors(monkeypatch)

    assert media_controls.open_path(player, str(new_media)) is False

    assert player._pip_media_available is True
    assert player.title_bar.pip_enabled is True


def test_failed_playlist_step_restores_the_pip_button(monkeypatch):
    player = player_state()
    player.playlist = ["new.mkv", "old-b.mkv"]
    silence_errors(monkeypatch)

    assert media_controls.play_from_playlist(player, 0) is False

    assert player._pip_media_available is True
    assert player.title_bar.pip_enabled is True


def test_failed_folder_first_item_restores_the_pip_button(monkeypatch):
    player = player_state()
    monkeypatch.setattr(media_controls.QFileDialog, "getExistingDirectory",
                        lambda *_args, **_kwargs: "C:/new")
    monkeypatch.setattr(media_controls, "folder_media_files",
                        lambda _folder: ["C:/new/new.mkv"])
    silence_errors(monkeypatch)

    media_controls.open_folder(player)

    assert player._pip_media_available is True
    assert player.title_bar.pip_enabled is True


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


def test_m3u_round_trip_preserves_http_urls_and_local_entries(
        tmp_path, monkeypatch):
    class AcceptingMpv:
        sub_delay = 0.0
        sub_visibility = False

        def __init__(self):
            self.calls = []

        def command_async(self, name, *args):
            self.calls.append((name, args))

    local = tmp_path / "Türkçe video.mkv"
    local.write_bytes(b"x")
    url = "https://example.test/stream.m3u8?token=a%2Fb#part"
    saved = tmp_path / "liste.m3u"
    writer = player_state()
    writer.playlist = [str(local), url]
    monkeypatch.setattr(media_controls.QFileDialog, "getSaveFileName",
                        lambda *_args, **_kwargs: (str(saved), ""))

    media_controls.save_playlist(writer)

    reader = player_state()
    reader.mpv_player = AcceptingMpv()
    monkeypatch.setattr(media_controls.QFileDialog, "getOpenFileName",
                        lambda *_args, **_kwargs: (str(saved), ""))

    assert media_controls.load_playlist(reader) is True
    assert reader.playlist == [str(local), url]
    assert reader.current_file == str(local)


def test_m3u_url_first_uses_url_loading_lifecycle_and_rejects_other_schemes(
        tmp_path, monkeypatch):
    class AcceptingMpv:
        sub_delay = 0.0
        sub_visibility = False

        def command_async(self, *_args):
            return None

    playlist_file = tmp_path / "remote.m3u"
    url = "https://example.test/live.m3u8?x=1#fragment"
    playlist_file.write_text("\ufeff#EXTM3U\nftp://ignored.test/a\n" + url + "\n",
                             encoding="utf-8")
    player = player_state()
    player.mpv_player = AcceptingMpv()
    monkeypatch.setattr(media_controls.QFileDialog, "getOpenFileName",
                        lambda *_args, **_kwargs: (str(playlist_file), ""))

    assert media_controls.load_playlist(player) is True
    assert player.playlist == [url]
    assert player.current_file == url
    assert player._url_loading_active is True


def test_failed_replacement_after_removing_active_item_restores_the_list(
        monkeypatch):
    player = player_state()
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = media_controls.remove_from_playlist(player, 0)

    assert result is False
    assert snapshot(player) == before


def test_failed_bulk_remove_of_active_items_restores_the_whole_list(monkeypatch):
    player = player_state()
    player.playlist.append("old-c.mkv")
    silence_errors(monkeypatch)
    before = snapshot(player)

    result = media_controls.remove_many_from_playlist(player, [0, 1])

    assert result is False
    assert snapshot(player) == before


def test_bulk_remove_before_active_item_updates_index_without_reloading():
    player = player_state()
    player.playlist = ["zero.mkv", "one.mkv", "active.mkv", "last.mkv"]
    player.current_playlist_index = 2
    player.current_file = "active.mkv"

    result = media_controls.remove_many_from_playlist(player, [0, 1])

    assert result is True
    assert player.playlist == ["active.mkv", "last.mkv"]
    assert player.current_playlist_index == 0
    assert player.current_file == "active.mkv"
    assert player.mpv_player.calls == []


def test_bulk_remove_containing_active_item_loads_one_survivor(monkeypatch):
    player = player_state()
    player.playlist = ["zero.mkv", "active.mkv", "two.mkv", "last.mkv"]
    player.current_playlist_index = 1
    player.current_file = "active.mkv"
    loaded = []

    def accept(owner, index):
        loaded.append((list(owner.playlist), index))
        owner.current_playlist_index = index
        owner.current_file = owner.playlist[index]
        return True

    monkeypatch.setattr(media_controls, "play_from_playlist", accept)

    result = media_controls.remove_many_from_playlist(player, [1, 2])

    assert result is True
    assert player.playlist == ["zero.mkv", "last.mkv"]
    assert player.current_playlist_index == 1
    assert player.current_file == "last.mkv"
    assert loaded == [(["zero.mkv", "last.mkv"], 1)]


def test_bulk_remove_all_items_stops_only_once(monkeypatch):
    player = player_state()
    stops = []

    def accept_stop(owner):
        stops.append(1)
        owner.current_file = ""
        return True

    monkeypatch.setattr(media_controls, "stop", accept_stop)

    result = media_controls.remove_many_from_playlist(player, [0, 1])

    assert result is True
    assert player.playlist == []
    assert player.current_playlist_index == -1
    assert stops == [1]


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
