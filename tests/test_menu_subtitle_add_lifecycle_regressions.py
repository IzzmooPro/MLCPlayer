# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Menüden "Altyazı Ekle" sürükle-bırakla AYNI yaşam döngüsünü kullanmalı.

Gerçek libmpv ölçümü (24 Eylül 2026, vo/ao=null, lavfi testsrc):
`sub_visibility=False` iken `sub_add()` izi seçer (`sid 1`) ama
görünürlük `False` KALIR. Yeni medya açılışında görünürlük kapatıldığı
için menü yolu "Altyazı eklendi" deyip altyazıyı göstermiyordu. Sürükle-
bırak yolu (`SubtitleSession.apply`) izi doğrular, seçer ve görünür yapar.
"""

from types import SimpleNamespace

from app import media_controls


def _player(duration, activated):
    return SimpleNamespace(
        current_file="film.mkv", duration=duration, _pending_subs=[],
        video_frame=SimpleNamespace(show_osd=lambda *a, **k: None),
        mpv_player=SimpleNamespace(
            sub_add=lambda path: activated.append(("raw_sub_add", path))),
        _activate_dropped_subtitle=lambda path: activated.append(
            ("session", path)) or True)


def test_menu_add_uses_the_single_subtitle_lifecycle(monkeypatch, tmp_path):
    subtitle = tmp_path / "film.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nmerhaba\n",
                        encoding="utf-8")
    monkeypatch.setattr(
        media_controls.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(subtitle), "")))
    calls = []

    media_controls.open_subtitle(_player(120.0, calls))

    assert calls == [("session", str(subtitle))]


def test_menu_add_before_load_still_queues(monkeypatch, tmp_path):
    subtitle = tmp_path / "film.srt"
    subtitle.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        media_controls.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(subtitle), "")))
    calls = []
    player = _player(0, calls)

    media_controls.open_subtitle(player)

    assert calls == []
    assert player._pending_subs == [str(subtitle)]
