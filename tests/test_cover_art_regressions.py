# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ses dosyalarında albüm kapağı GÖSTERİLİR.

ÖLÇÜLEN EKSİK (16 Ağustos 2026): ses dosyası açıldığında video alanı siyah
kalıyordu. Ölçüm, bu libmpv sürümünde `audio-display` VARSAYILANININ kapalı
olduğunu gösterdi (ürün yapılandırması suçlu değildi):

    mpv varsayılanı  audio-display = False
    bizim config ile audio-display = False

Kapak zaten TANINIYOR (`cover-art-auto = 'exact'`, dosyanın yanındaki
`cover.png` `albumart: True` olarak listeleniyor) ama parça SEÇİLMİYORDU.

Bu testler GERÇEK libmpv kullanır; sahte nesne kapak seçimini ölçemez.
Pencere açılmaz (`vo=null`), ses çıkmaz (`ao=null`).
"""

import os
import struct
import time
import wave

import pytest

from app.config import MPV_CONFIG

# 2x2 tek renk PNG — kapak olarak tanınması için yeterli.
COVER_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000020000000208020000"
    "00fdd49a730000000f49444154789c6360f8cf80000000ffff03000600"
    "0300b4b4b4b40000000049454e44ae426082")


def _audio_file(folder, name="parca.wav", seconds=1):
    path = os.path.join(folder, name)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"".join(struct.pack("<h", 0)
                                    for _ in range(8000 * seconds)))
    return path


@pytest.fixture
def player():
    import mpv
    instance = mpv.MPV(**dict(MPV_CONFIG, vo="null", ao="null", hwdec="no"))
    try:
        yield instance
    finally:
        instance.terminate()


def _album_art_tracks(player):
    return [track for track in player.track_list
            if track.get("type") == "video" and track.get("albumart")]


def test_cover_next_to_the_audio_file_is_displayed(player, tmp_path):
    """Dosyanın yanındaki kapak resmi video alanında GÖSTERİLİR."""
    folder = tmp_path / "album"
    folder.mkdir()
    (folder / "cover.png").write_bytes(COVER_PNG)
    path = _audio_file(str(folder))

    player.play(path)
    player.wait_until_playing()
    time.sleep(1.0)

    tracks = _album_art_tracks(player)
    assert tracks, "kapak parçası hiç yüklenmedi"
    assert any(track.get("selected") for track in tracks), (
        "kapak bulundu ama seçilmedi; video alanı siyah kalır")


def test_audio_without_a_cover_still_plays(player, tmp_path):
    """Kapağı olmayan ses dosyası kapak açıkken de sorunsuz çalar."""
    path = _audio_file(str(tmp_path))

    player.play(path)
    player.wait_until_playing()
    time.sleep(0.5)

    assert not _album_art_tracks(player)
    assert any(track.get("type") == "audio" and track.get("selected")
               for track in player.track_list)


def test_cover_display_is_configured_in_the_single_mpv_config():
    """Ayar ürünün TEK mpv yapılandırmasından gelir, dağınık yama değil."""
    assert MPV_CONFIG.get("audio_display") in ("embedded-first",
                                               "external-first"), MPV_CONFIG
