# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Bırakılan/menüden eklenen altyazı oturumu medya değişince sıfırlanmalı.

`SubtitleSession` önceki MLC track'inin `sid`'ini hatırlar ve yeni ekleme
sonrası onu kaldırır. Oturum videolar arasında yaşadığı için A videosundan
kalan `sid` B videosunda BAŞKA bir track'i gösterir (ör. B'nin otomatik
yüklenen kendi SRT'si) ve o track yanlışlıkla kaldırılıyordu.
"""

from types import SimpleNamespace

from app.player import MPVPlayer


class FakeMpv:
    def __init__(self):
        self.track_list = []
        self.sid = False
        self.sub_visibility = False
        self.removed = []

    def sub_add(self, path, *args):
        next_id = max([t["id"] for t in self.track_list] + [0]) + 1
        self.track_list.append({"id": next_id, "type": "sub",
                                "external": True,
                                "external-filename": path})

    def sub_remove(self, sid):
        self.removed.append(sid)
        self.track_list = [t for t in self.track_list if t["id"] != sid]


def _player(mpv, current_file):
    player = SimpleNamespace(
        mpv_player=mpv, current_file=current_file,
        _drop_subtitle_session=None,
        video_frame=SimpleNamespace(show_osd=lambda *a, **k: None,
                                    _update_overlay_subtitle_state=None),
        _subtitle_track_wait=lambda: None)
    player.activate = lambda path: MPVPlayer._activate_dropped_subtitle(
        player, path)
    return player


def test_new_media_does_not_remove_a_track_by_a_stale_sid(tmp_path):
    first = tmp_path / "A.en.srt"
    second = tmp_path / "B.tr.srt"
    auto = tmp_path / "B.srt"
    for path in (first, second, auto):
        path.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n",
                        encoding="utf-8")
    mpv = FakeMpv()
    player = _player(mpv, str(tmp_path / "A.mkv"))
    assert player.activate(str(first)) is True
    assert mpv.sid == 1

    # B videosu yüklendi: MPV track listesini sıfırlar ve B'nin kendi
    # SRT'sini otomatik yükler; o da id 1 alır.
    player.current_file = str(tmp_path / "B.mkv")
    mpv.track_list = [{"id": 1, "type": "sub", "external": True,
                       "external-filename": str(auto)}]
    mpv.sid = 1

    assert player.activate(str(second)) is True

    assert mpv.removed == []
    assert [t["id"] for t in mpv.track_list] == [1, 2]
    assert mpv.sid == 2
