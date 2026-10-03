# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ses değişiminde gösterilen OSD metni çevrilmeli.

`set_volume()` metni önce bir değişkene atayıp sonra `show_osd()`'ye
veriyordu; `"Sessiz"` ve `"Ses: %N"` `tr()` dışında kaldığı için başka
dildeki kullanıcı ses değiştirince Türkçe görüyordu. Arayüz çağrısının
sabit argümanını arayan AST taraması bu dolaylı yolu yakalamıyordu.
"""

from types import SimpleNamespace

from app import media_controls


def _player(osd):
    class Style:
        def standardIcon(self, _pixmap):
            return None

    mpv = SimpleNamespace(volume=50.0, volume_max=130)
    return SimpleNamespace(
        mpv_player=mpv, last_volume=50.0, is_muted=False, _ui_ready=True,
        volume_label=SimpleNamespace(setText=lambda _t: None),
        volume_icon=SimpleNamespace(setIcon=lambda _i: None),
        style=lambda: Style(),
        video_frame=SimpleNamespace(show_osd=osd.append))


def test_volume_osd_text_is_translated(monkeypatch):
    monkeypatch.setattr(media_controls, "tr", lambda text: f"«{text}»")
    osd = []

    assert media_controls.set_volume(_player(osd), 70)
    assert media_controls.set_volume(_player(osd), 0)

    assert osd == ["«Ses: %{volume}»".format(volume=70), "«Sessiz»"]
