# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kullanıcıya görünür sonucu olan hataların günlüğe yazılması.

Ölçülen kusur: aşağıdaki üç yol hatayı `except Exception: pass` ile
yutuyordu. Önceki dosyanın altyazı gecikmesi yeni dosyaya taşınabiliyor,
otomatik altyazı gizlenemiyor veya eski MLC altyazı izi kalabiliyordu;
günlükte hiçbir iz olmadığı için kullanıcı raporu teşhis edilemiyordu.
Günlüğe yalnız istisna TÜRÜ yazılır, ham mesaj yazılmaz.
"""
from types import SimpleNamespace

from app import media_controls, subtitle_service


class _RaisingMPV:
    def __setattr__(self, name, value):
        raise RuntimeError(r"C:\Users\secret\video.mkv")


def _capture(monkeypatch, module):
    records = []
    monkeypatch.setattr(module, "log",
                        lambda message, level="INFO": records.append(
                            (level, message)), raising=False)
    return records


def test_subtitle_delay_reset_failure_is_logged(monkeypatch):
    records = _capture(monkeypatch, media_controls)
    player = SimpleNamespace(mpv_player=_RaisingMPV(), settings=None)
    media_controls._reset_subtitle_timing_for_new_media(player)
    assert records == [("WARNING",
                        "Subtitle delay reset failed: RuntimeError")]


def test_subtitle_hide_failure_is_logged(monkeypatch):
    records = _capture(monkeypatch, media_controls)
    player = SimpleNamespace(mpv_player=_RaisingMPV())
    media_controls._hide_subtitles_for_new_media(player)
    assert records == [("WARNING",
                        "Subtitle hide for new media failed: RuntimeError")]


def test_previous_subtitle_track_removal_failure_is_logged(monkeypatch):
    records = _capture(monkeypatch, subtitle_service)

    def remover(_sid):
        raise RuntimeError("raw mpv detail")

    mpv = SimpleNamespace(sub_remove=remover, track_list=[])
    session = subtitle_service.SubtitleSession.__new__(
        subtitle_service.SubtitleSession)
    session._sid = 7
    session._remove_previous(mpv, "target.srt")
    assert session._sid is None
    assert records == [("WARNING",
                        "Previous subtitle track removal failed: "
                        "RuntimeError")]
