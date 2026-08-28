# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Surukle-birak SRT ETKINLESTIRME sozlesmesi (2A).

Mevcut davranis yalnizca `mpv.sub_add(path)` cagiriyordu: track eklense bile
DOGRULANMIS secim ve gorunurluk garantisi yoktu, ayni dosya iki kez
eklenebiliyordu ve gecersiz dosya sessizce mevcut durumu bozabiliyordu.

Bu tur IKINCI bir altyazi yasam dongusu YAZMAZ: Altyazi Merkezi'nin
`SubtitleSession.apply()` sozlesmesi yeniden kullanilir (ayni yola ait eski
track kaldirilir, yeni track `external-filename` ile DOGRULANIR, `sid`
verilir, `sub_visibility=True` yapilir, dogrulanamazsa hicbir sey secilmez).

Olculen sozlesme:
- Oynayan videoya birakilan gecerli SRT: yuklenir, O track secilir, gorunur.
- Video yuklenirken birakilan SRT pending akistan sonra ayni sekilde secilir.
- Video + SRT birlikte birakilirsa video hazir olunca SRT acilir.
- Gomulu/baska altyazi YANLISLIKLA secilmez (tam yol dogrulanir).
- Gecersiz SRT mevcut `sid`, gorunurluk ve oynatmayi BOZMAZ.
- Ayni SRT iki kez EKLENMEZ.
- Basarida mevcut "Altyazi eklendi" OSD'si korunur.
"""
import os

import pytest

import app.player as player_module
from app.player import MPVPlayer
from app.subtitle_service import SubtitleSession


class FakeMpv:
    """MPV'nin yalniz altyazi track yuzeyini taklit eder."""

    def __init__(self, tracks=None):
        self.track_list = list(tracks or [])
        self.sid = None
        self.sub_visibility = False
        self.added = []
        self.removed = []
        self._next_id = max([t.get("id", 0) for t in self.track_list] or [0]) + 1
        self.fail_on_add = False

    def sub_add(self, path, *args):
        if self.fail_on_add:
            raise RuntimeError("mpv sub-add rejected")
        self.added.append(path)
        self.track_list.append({"id": self._next_id, "type": "sub",
                                "external-filename": path})
        self._next_id += 1

    def load_media(self):
        """Medya yuklendi: gercek mpv `track_list`'inde en az video track'i olur.

        Pending kuyrugu BILEREK yalniz gercek `track_list` hazir oldugunda
        bosaltilir (mpv yukleme sirasinda dis altyazilari siler).
        """
        self.track_list.append({"id": self._next_id, "type": "video"})
        self._next_id += 1

    def sub_remove(self, sid):
        self.removed.append(sid)
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


class FakeFrame:
    def __init__(self):
        self.osd = []
        self.playlist_panel = None

    def show_osd(self, text, *args, **kwargs):
        self.osd.append(text)

    def _update_overlay_subtitle_state(self):
        pass


class FakePlayer:
    """`MPVPlayer` metodlarinin GERCEK govdesiyle calisan ince tasiyici.

    Urun metodlari OLDUGU GIBI baglanir; govde kopyalanmaz.
    """

    dropEvent = MPVPlayer.dropEvent
    _activate_dropped_subtitle = MPVPlayer._activate_dropped_subtitle
    _apply_pending_subtitles = MPVPlayer._apply_pending_subtitles
    _subtitle_track_wait = MPVPlayer._subtitle_track_wait

    def __init__(self, mpv, current_file="D:/film.mkv", duration=120.0):
        self.mpv_player = mpv
        self.video_frame = FakeFrame()
        self.current_file = current_file
        self.duration = duration
        self._core_idle = False
        self._pending_subs = []
        self._drop_subtitle_session = None
        self.playlist = []
        self.current_playlist_index = 0


class FakeUrl:
    def __init__(self, path):
        self._path = path

    def isLocalFile(self):
        return True

    def toLocalFile(self):
        return self._path


class FakeMime:
    def __init__(self, paths):
        self._paths = paths

    def urls(self):
        return [FakeUrl(p) for p in self._paths]


class FakeDropEvent:
    def __init__(self, paths):
        self._mime = FakeMime(paths)
        self.accepted = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True


@pytest.fixture
def errors(monkeypatch):
    shown = []
    monkeypatch.setattr(player_module, "show_user_error",
                        lambda *a, **k: shown.append(a[1] if len(a) > 1 else ""))
    return shown


@pytest.fixture
def srt(tmp_path):
    path = tmp_path / "film.srt"
    path.write_text("1\n00:00:01,000 --> 00:00:02,000\nmerhaba\n",
                    encoding="utf-8")
    return str(path)


def external_tracks(mpv, path):
    return [t for t in mpv.track_list
            if os.path.normcase(str(t.get("external-filename") or ""))
            == os.path.normcase(path)]


# =====================================================================
# 1. Oynayan videoya birakilan SRT
# =====================================================================

def test_a_dropped_subtitle_is_loaded_selected_and_visible(errors, srt):
    mpv = FakeMpv()
    player = FakePlayer(mpv)

    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert mpv.added == [srt]
    assert len(external_tracks(mpv, srt)) == 1
    assert mpv.sid == external_tracks(mpv, srt)[0]["id"]
    assert mpv.sub_visibility is True
    assert errors == []


def test_the_dropped_file_keeps_the_existing_osd(errors, srt):
    mpv = FakeMpv()
    player = FakePlayer(mpv)

    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert "Altyazı eklendi" in player.video_frame.osd


def test_an_embedded_track_is_never_selected_by_accident(errors, srt):
    """Gomulu altyazi varken secim BIRAKILAN tam yola ait olmali."""
    mpv = FakeMpv(tracks=[{"id": 1, "type": "sub", "lang": "eng"}])
    player = FakePlayer(mpv)

    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert mpv.sid != 1
    assert external_tracks(mpv, srt)[0]["id"] == mpv.sid


def test_the_same_subtitle_is_not_added_twice(errors, srt):
    mpv = FakeMpv()
    player = FakePlayer(mpv)

    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))
    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert len(external_tracks(mpv, srt)) == 1
    assert mpv.sub_visibility is True


# =====================================================================
# 2. Gecersiz dosya mevcut durumu bozmaz
# =====================================================================

def test_a_missing_subtitle_does_not_disturb_the_current_state(errors, tmp_path):
    mpv = FakeMpv(tracks=[{"id": 1, "type": "sub", "lang": "tur"}])
    mpv.sid = 1
    mpv.sub_visibility = True
    player = FakePlayer(mpv)

    MPVPlayer.dropEvent(player, FakeDropEvent([str(tmp_path / "yok.srt")]))

    assert mpv.sid == 1
    assert mpv.sub_visibility is True
    assert mpv.added == []
    assert errors  # kullaniciya guvenli mesaj gitti


def test_a_rejected_subtitle_does_not_disturb_the_current_state(errors, srt):
    """mpv `sub-add`'i reddederse mevcut secim ve gorunurluk korunur."""
    mpv = FakeMpv(tracks=[{"id": 1, "type": "sub", "lang": "tur"}])
    mpv.sid = 1
    mpv.sub_visibility = True
    mpv.fail_on_add = True
    player = FakePlayer(mpv)

    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert mpv.sid == 1
    assert mpv.sub_visibility is True
    assert errors


# =====================================================================
# 3. Pending akis (video yuklenirken)
# =====================================================================

def test_a_subtitle_dropped_while_loading_is_queued(errors, srt):
    mpv = FakeMpv()
    player = FakePlayer(mpv, duration=0.0)

    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert player._pending_subs == [srt]
    assert mpv.added == []


def test_the_pending_subtitle_is_selected_and_visible_after_load(errors, srt):
    mpv = FakeMpv()
    player = FakePlayer(mpv, duration=0.0)
    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))
    player.duration = 120.0
    mpv.load_media()

    MPVPlayer._apply_pending_subtitles(player)

    assert player._pending_subs == []
    assert mpv.sid == external_tracks(mpv, srt)[0]["id"]
    assert mpv.sub_visibility is True


def test_a_video_and_its_subtitle_dropped_together(errors, srt, monkeypatch, tmp_path):
    """Video + SRT: SRT video hazir olunca acilir."""
    video = tmp_path / "film.mkv"
    video.write_bytes(b"0")
    opened = []
    monkeypatch.setattr(player_module, "open_path",
                        lambda player, path: opened.append(path) or True)
    mpv = FakeMpv()
    player = FakePlayer(mpv, current_file=None, duration=0.0)

    MPVPlayer.dropEvent(player, FakeDropEvent([str(video), srt]))

    assert opened == [str(video)]
    assert player._pending_subs == [srt]

    player.current_file = str(video)
    player.duration = 120.0
    mpv.load_media()
    MPVPlayer._apply_pending_subtitles(player)

    assert mpv.sid == external_tracks(mpv, srt)[0]["id"]
    assert mpv.sub_visibility is True


def test_failed_video_drop_does_not_replace_existing_pending_subtitles(
        errors, srt, monkeypatch, tmp_path):
    video = tmp_path / "rejected.mkv"
    video.write_bytes(b"0")
    monkeypatch.setattr(player_module, "open_path",
                        lambda _player, _path: False)
    player = FakePlayer(FakeMpv(), current_file=None, duration=0.0)
    player._pending_subs = ["already-pending.srt"]

    MPVPlayer.dropEvent(player, FakeDropEvent([str(video), srt]))

    assert player._pending_subs == ["already-pending.srt"]


def test_the_pending_drain_waits_for_a_real_track_list(errors, srt):
    """`track_list` bos oldugu surece kuyruk BOSALTILMAZ."""
    mpv = FakeMpv()
    mpv.track_list = []
    player = FakePlayer(mpv, duration=0.0)
    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    MPVPlayer._apply_pending_subtitles(player)   # duration hala 0

    assert player._pending_subs == [srt]
    assert mpv.added == []


# =====================================================================
# 4. Basarisiz IKINCI birakma mevcut altyaziyi YOK ETMEMELI
# =====================================================================

def test_a_failed_second_subtitle_keeps_the_working_one(errors, srt, tmp_path):
    """A calisiyorken B reddedilirse A track'i, sid'i ve gorunurlugu kalir."""
    other = tmp_path / "digeri.srt"
    other.write_text("1\n00:00:01,000 --> 00:00:02,000\nb\n", encoding="utf-8")
    mpv = FakeMpv()
    player = FakePlayer(mpv)
    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))
    sid_a = mpv.sid
    assert sid_a == external_tracks(mpv, srt)[0]["id"]

    mpv.fail_on_add = True
    MPVPlayer.dropEvent(player, FakeDropEvent([str(other)]))

    assert len(external_tracks(mpv, srt)) == 1
    assert mpv.sid == sid_a
    assert mpv.sub_visibility is True
    assert errors


def test_a_failed_reload_of_the_same_subtitle_keeps_the_track(errors, srt):
    """Ayni A.srt yeniden yuklenirken reddedilirse A track'i SILINMEMELI."""
    mpv = FakeMpv()
    player = FakePlayer(mpv)
    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))
    sid_a = mpv.sid

    mpv.fail_on_add = True
    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert len(external_tracks(mpv, srt)) == 1
    assert mpv.sid == sid_a
    assert mpv.sub_visibility is True
    assert errors


def test_a_successful_second_subtitle_replaces_the_first(errors, srt, tmp_path):
    """A -> B basariliysa B TEK secili birakma track'i olur; A kaldirilir."""
    other = tmp_path / "digeri.srt"
    other.write_text("1\n00:00:01,000 --> 00:00:02,000\nb\n", encoding="utf-8")
    mpv = FakeMpv()
    player = FakePlayer(mpv)
    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    MPVPlayer.dropEvent(player, FakeDropEvent([str(other)]))

    assert external_tracks(mpv, srt) == []
    assert len(external_tracks(mpv, str(other))) == 1
    assert mpv.sid == external_tracks(mpv, str(other))[0]["id"]
    assert mpv.sub_visibility is True
    assert errors == []


# =====================================================================
# 5. Tek yasam dongusu
# =====================================================================

def test_the_existing_subtitle_session_is_reused(errors, srt):
    """Ikinci bir altyazi yasam dongusu yazilmaz."""
    mpv = FakeMpv()
    player = FakePlayer(mpv)

    MPVPlayer.dropEvent(player, FakeDropEvent([srt]))

    assert isinstance(player._drop_subtitle_session, SubtitleSession)
