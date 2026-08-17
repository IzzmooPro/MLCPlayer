# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı gecikmesinin başka medya ve oturumlara sızma regresyonları."""
from types import SimpleNamespace

import pytest

from app import media_controls
from app.config import MPV_CONFIG
from app.player import MPVPlayer


class FakeSettings:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.writes = []

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value
        self.writes.append((key, value))


class FakeMPV:
    def __init__(self, delay=1.5):
        self.sub_delay = delay
        self.sub_visibility = True
        self.played = []

    def play(self, path):
        self.played.append((path, self.sub_delay))


class FakePlaceholder:
    """`QLabel`'in ürün tarafından GERÇEKTEN kullanılan yüzeyi.

    Eski taklit yalnız `hide`/`show` taşıyordu. URL yükleme turunda ürün
    `media_controls._set_placeholder_text()` üzerinden `text()`/`setText()`/
    `setVisible()` çağırmaya başladı; taklit geride kaldığı için testler
    `AttributeError: 'types.SimpleNamespace' object has no attribute 'text'`
    ile düşüyordu. Ürün kusuru değildir: gerçek `QLabel` bu API'yi taşır.
    """

    def __init__(self):
        self._text = ""
        self.visible = True

    def text(self):
        return self._text

    def setText(self, value):
        self._text = value

    def setVisible(self, visible):
        self.visible = bool(visible)

    def hide(self):
        self.visible = False

    def show(self):
        self.visible = True


def fake_player(delay=1.5):
    frame = SimpleNamespace(
        control_overlay=None,
        placeholder_label=FakePlaceholder(),
    )
    return SimpleNamespace(
        duration=0, position=0, _core_idle=False, _audio_menu_file="",
        _chapter_menu_file="", _pending_subs=[], playlist=[],
        current_playlist_index=-1, current_file="", _load_started_at=0,
        last_dir="", is_paused=True, mpv_player=FakeMPV(delay),
        settings=FakeSettings({"subtitle/sub_delay": delay}),
        play_button=SimpleNamespace(setIcon=lambda icon: None),
        pause_icon=object(), video_frame=frame,
        clear_title_bar_raise_pending=lambda: None,
        mark_title_bar_raise_pending=lambda: None,
        set_title=lambda: None, add_recent_file=lambda path: None,
    )


def test_saved_delay_is_not_restored_into_a_new_player_session():
    player = SimpleNamespace(
        settings=FakeSettings({"subtitle/sub_delay": "1.5"}),
        mpv_player=SimpleNamespace(),
    )

    MPVPlayer.restore_subtitle_settings(player)

    assert player.mpv_player.sub_delay == 0.0


def test_reset_helper_clears_runtime_and_stored_delay():
    player = fake_player()

    media_controls._reset_subtitle_timing_for_new_media(player)

    assert player.mpv_player.sub_delay == 0.0
    assert player.settings.values["subtitle/sub_delay"] == 0.0


def test_direct_open_resets_delay_before_play():
    player = fake_player()

    media_controls.open_path(player, "C:/media/video.mkv")

    assert player.mpv_player.played == [("C:/media/video.mkv", 0.0)]


def test_url_open_resets_delay_before_play(monkeypatch):
    player = fake_player()
    monkeypatch.setattr(
        media_controls.QInputDialog, "getText",
        lambda *args, **kwargs: ("https://example.test/video", True))

    media_controls.open_url(player)

    assert player.mpv_player.played == [("https://example.test/video", 0.0)]


def test_playlist_open_resets_delay_before_play():
    player = fake_player()
    player.playlist = ["C:/media/episode.mkv"]

    media_controls.play_from_playlist(player, 0)

    assert player.mpv_player.played == [("C:/media/episode.mkv", 0.0)]


def test_mpv_auto_discovers_matching_subtitles_but_starts_them_hidden():
    """Bu testin konusu GİZLİ BAŞLAMA sözleşmesidir; keşif GENİŞLİĞİ değil.

    Eskiyen beklenti gevşetilmeden dönüştürüldü: yerel-SRT turunda
    `sub_auto` bilerek `fuzzy` -> `exact` yapıldı (yalnız tam video gövdesi
    ve dil/etiket sonekleri yüklenir, bkz. `app/local_subtitle.py`). Yeni
    sözleşmenin sahibi `test_local_subtitle_autoload_regressions.py`'dir;
    buradaki eski `fuzzy` beklentisi onunla ÇELİŞİYORDU.
    """
    assert MPV_CONFIG["sub_auto"] == "exact"
    assert MPV_CONFIG["sub_visibility"] == "no"


@pytest.mark.parametrize("flow", ("path", "url", "playlist"))
def test_every_new_media_flow_resets_auto_found_subtitles_to_hidden(
        flow, monkeypatch):
    player = fake_player()
    player.mpv_player.sub_visibility = True
    if flow == "path":
        media_controls.open_path(player, "C:/media/video.mkv")
    elif flow == "url":
        monkeypatch.setattr(
            media_controls.QInputDialog, "getText",
            lambda *args, **kwargs: ("https://example.test/video", True))
        media_controls.open_url(player)
    else:
        player.playlist = ["C:/media/video.mkv"]
        media_controls.play_from_playlist(player, 0)

    assert player.mpv_player.sub_visibility is False


@pytest.mark.parametrize("delay", (1.5, -2.0, 0.1))
def test_any_previous_media_delay_is_cleared(delay):
    player = fake_player(delay)

    media_controls._reset_subtitle_timing_for_new_media(player)

    assert player.mpv_player.sub_delay == 0.0
