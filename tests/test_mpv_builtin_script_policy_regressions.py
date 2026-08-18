# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Urunun kullanmadigi mpv select istemcisinin geri acilma korumasi."""

from types import SimpleNamespace

from app.config import MPV_CONFIG
from app.player import MPVPlayer


def test_the_unused_mpv_select_client_is_disabled():
    """Qt arayuzu mpv menu-data/context-menu/select binding kullanmaz."""
    assert MPV_CONFIG.get("load_select") is False


def test_the_select_fix_does_not_disable_other_builtin_clients():
    """Dar duzeltme stats/ytdl gibi ayri istemcileri topluca kapatmaz."""
    assert "load_stats_overlay" not in MPV_CONFIG
    assert "ytdl" not in MPV_CONFIG


def test_the_runtime_constructor_receives_the_disabled_select_flag(
        monkeypatch):
    captured = {}

    class FakeMPV:
        def __init__(self, **config):
            captured.update(config)

        def observe_property(self, *_args):
            pass

    monkeypatch.setattr("app.player.mpv.MPV", FakeMPV)
    monkeypatch.setattr(MPVPlayer, "restore_subtitle_settings",
                        lambda self: None)
    monkeypatch.setattr(MPVPlayer, "refresh_audio_devices",
                        lambda self: None)

    player = MPVPlayer.__new__(MPVPlayer)
    player.video_frame = SimpleNamespace(
        winId=lambda: 1, sync_subtitle_safe_band=lambda: None)
    MPVPlayer.init_mpv_player(player)

    assert captured["load_select"] is False
