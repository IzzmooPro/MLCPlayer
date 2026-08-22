# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Liste tekrarı açıkken önceki/sonraki SARMA regresyonları.

`play_next()` son parçadan ilk parçaya sarıyordu ama `play_previous()` ilk
parçadan son parçaya SARMIYOR, yalnız "Listenin başındasınız" mesajı
gösteriyordu. Sağ-tık menüsü ise liste tekrarı açıkken iki satırı da
koşulsuz enabled yapıyordu: menü durumu ürün davranışıyla ÇELİŞİYORDU.

Bu dosya yalnız bu davranışı ölçer; menü görseli ve sırası değişmez.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QSlider, QVBoxLayout, QWidget)

from app import media_controls

PLAYLIST = ["A.mkv", "B.mkv", "C.mkv"]


@pytest.fixture
def player_stub(monkeypatch):
    """`play_from_playlist` ve bilgi kutusu izlenen sahte oynatıcı."""
    played = []
    boxes = []

    monkeypatch.setattr(media_controls, "play_from_playlist",
                        lambda player, index: played.append(index))
    monkeypatch.setattr(
        media_controls, "show_information",
        lambda *args, **kwargs: boxes.append(args[1:3]))

    def factory(index=0, loop_playlist=False, playlist=None):
        player = SimpleNamespace(
            playlist=list(PLAYLIST if playlist is None else playlist),
            current_playlist_index=index,
            loop_playlist=loop_playlist)
        return SimpleNamespace(player=player, played=played, boxes=boxes)

    return factory


# =====================================================================
# 1. Ürün davranışı
# =====================================================================

def test_previous_wraps_to_the_last_track_when_looping(player_stub):
    env = player_stub(index=0, loop_playlist=True)

    media_controls.play_previous(env.player)

    assert env.player.current_playlist_index == 2
    assert env.played == [2]
    assert env.boxes == [], "sarma yerine bilgi kutusu gosterildi"


def test_next_wraps_to_the_first_track_when_looping(player_stub):
    env = player_stub(index=2, loop_playlist=True)

    media_controls.play_next(env.player)

    assert env.player.current_playlist_index == 0
    assert env.played == [0]
    assert env.boxes == []


def test_previous_still_steps_back_normally(player_stub):
    env = player_stub(index=2, loop_playlist=True)

    media_controls.play_previous(env.player)

    assert env.player.current_playlist_index == 1
    assert env.played == [1]


def test_previous_without_looping_keeps_the_boundary_message(player_stub):
    env = player_stub(index=0, loop_playlist=False)

    media_controls.play_previous(env.player)

    assert env.player.current_playlist_index == 0
    assert env.played == []
    assert len(env.boxes) == 1


def test_next_without_looping_keeps_the_boundary_message(player_stub):
    env = player_stub(index=2, loop_playlist=False)

    media_controls.play_next(env.player)

    assert env.played == []
    assert len(env.boxes) == 1


def test_empty_playlist_is_safe(player_stub):
    env = player_stub(index=0, loop_playlist=True, playlist=[])

    media_controls.play_previous(env.player)
    media_controls.play_next(env.player)

    assert env.played == []


# --- BAŞLATILMAMIŞ liste: index = -1 ---
#
# Hiçbir parça başlamamışken "Önceki" son parçaya SARMAMALI; liste tekrarı
# açık olsa bile. "Sonraki" ilk parçayı başlatır.

@pytest.mark.parametrize("loop", [False, True])
def test_previous_does_nothing_before_playback_started(player_stub, loop):
    env = player_stub(index=-1, loop_playlist=loop)

    media_controls.play_previous(env.player)

    assert env.player.current_playlist_index == -1
    assert env.played == [], "baslamamis listede son parcaya sarildi"
    assert len(env.boxes) == 1


@pytest.mark.parametrize("loop", [False, True])
def test_next_starts_the_first_track_before_playback_started(player_stub,
                                                             loop):
    env = player_stub(index=-1, loop_playlist=loop)

    media_controls.play_next(env.player)

    assert env.player.current_playlist_index == 0
    assert env.played == [0]
    assert env.boxes == []


def test_single_track_loop_replays_the_same_index(player_stub):
    env = player_stub(index=0, loop_playlist=True, playlist=["A.mkv"])

    media_controls.play_previous(env.player)

    assert env.player.current_playlist_index == 0
    assert env.played == [0]


# =====================================================================
# 2. Menü durumu ürün davranışıyla EŞLEŞİR
# =====================================================================

@pytest.fixture
def frame_factory(tmp_path):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    created = []

    def factory(playlist=None, index=0, loop_playlist=False):
        from app.video_frame import VideoFrame

        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.duration = 600.0
        window.position = 0.0
        window.current_file = "C:/video.mkv"
        window.is_paused = False
        window.is_muted = False
        window.playlist = list(PLAYLIST if playlist is None else playlist)
        window.current_playlist_index = index
        window.loop_file = False
        window.loop_playlist = loop_playlist
        window.shuffle = False
        window._updating_position_slider = False
        window._pending_subs = []
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(
            time_pos=0.0, pause=False, sub_visibility=False, sid=1, aid=1,
            speed=1.0, track_list=[], audio_device="auto",
            audio_device_list=[], stop=lambda: None,
            command=lambda *a, **k: None)
        window.recent_files = []
        for name in ("open_file", "open_folder", "open_url", "open_path",
                     "play_pause", "stop",
                     "play_previous", "play_next", "show_playlist",
                     "toggle_mute", "select_audio_track",
                     "select_audio_device", "toggle_subtitles",
                     "select_subtitle_language", "open_subtitle",
                     "open_subtitle_center", "show_subtitle_settings",
                     "toggle_fullscreen", "take_screenshot",
                     "toggle_picture_in_picture",
                     "setup_video_adjustments", "seek_relative", "goto_time",
                     "set_playback_speed", "set_loop_file",
                     "set_loop_playlist", "toggle_shuffle", "close",
                     "seek_position", "show_media_info"):
            setattr(window, name, lambda *a, **k: None)
        frame = VideoFrame(window)
        window.video_frame = frame
        created.append(window)
        app.processEvents()
        return frame

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def find_action(menu, title):
    for action in menu.actions():
        if action.text() == title:
            return action
    return None


@pytest.mark.parametrize("index,loop,previous,following", [
    (0, True, True, True),
    (2, True, True, True),
    (1, True, True, True),
    (0, False, False, True),
    (2, False, True, False),
])
def test_menu_state_matches_the_product(frame_factory, index, loop, previous,
                                        following):
    frame = frame_factory(index=index, loop_playlist=loop)

    menu = frame.build_context_menu()

    assert find_action(menu, "Önceki").isEnabled() is previous
    assert find_action(menu, "Sonraki").isEnabled() is following


def test_empty_playlist_disables_both(frame_factory):
    frame = frame_factory(playlist=[], loop_playlist=True)

    menu = frame.build_context_menu()

    assert find_action(menu, "Önceki").isEnabled() is False
    assert find_action(menu, "Sonraki").isEnabled() is False


@pytest.mark.parametrize("loop", [False, True])
def test_unstarted_playlist_index(frame_factory, loop):
    """`current_playlist_index=-1`: Önceki yok, Sonraki ilk parçayı açar.

    Liste tekrarı AÇIK olsa bile Önceki etkin OLMAZ; henüz oynatılan bir
    parça yokken "önceki"nin anlamı yoktur.
    """
    frame = frame_factory(index=-1, loop_playlist=loop)

    menu = frame.build_context_menu()

    assert find_action(menu, "Önceki").isEnabled() is False
    assert find_action(menu, "Sonraki").isEnabled() is True
