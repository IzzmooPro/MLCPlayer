"""Fiziksel kabul child'inin SESSIZ ses cikisi sozlesmesi.

Buttons grubu sesi 44'ten 140'a cikariyor. Bu, gercek hoparlorden yuksek
ses uretmemeli. Cozum yalnizca TEST child'inda `ao=null` kullanmaktir:
ses parcasi ve `volume` ozellikleri yasamaya devam eder (mute ac/kapat
olculebilir) ama fiziksel cikis olmaz.

`audio=no` KULLANILMAZ: bazi dosyalarda mpv hicbir akis secmiyor ve
`volume`/`mute` yolu olculemez hale geliyor (bkz. thumbnail worker turu).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

from physical_audio import audio_safety_problems, native_mpv_config


def test_native_config_uses_null_audio_output():
    base = {"hwdec": "auto-safe", "vo": "gpu"}

    config = native_mpv_config(base, silent_audio=True)

    assert config["ao"] == "null"


def test_native_config_does_not_mutate_the_original():
    base = {"hwdec": "auto-safe", "vo": "gpu"}
    snapshot = dict(base)

    native_mpv_config(base, silent_audio=True)

    assert base == snapshot
    assert "ao" not in base


def test_native_config_never_disables_audio_tracks():
    """`audio=no` mpv'ye hicbir akis sectirmeyebilir; kullanilmamali."""
    config = native_mpv_config({"vo": "gpu"}, silent_audio=True)

    assert config.get("audio") != "no"
    assert "audio" not in config or config["audio"] != "no"


def test_native_config_does_not_force_mute():
    """Buttons grubu fiziksel mute ac/kapat olcuyor; `mute=yes` sabitlenmez."""
    config = native_mpv_config({"vo": "gpu"}, silent_audio=True)

    assert config.get("mute") in (None, "no")


def test_product_config_is_untouched_when_silence_is_off():
    base = {"hwdec": "auto-safe", "vo": "gpu"}

    config = native_mpv_config(base, silent_audio=False)

    assert config == base
    assert config is not base


def test_real_product_config_is_not_modified():
    from app.config import MPV_CONFIG

    before = dict(MPV_CONFIG)
    native_mpv_config(MPV_CONFIG, silent_audio=True)

    assert dict(MPV_CONFIG) == before
    assert "ao" not in MPV_CONFIG


# =====================================================================
# Guvenlik kapisi
# =====================================================================

def test_safety_gate_blocks_when_output_is_not_null():
    problems = audio_safety_problems("wasapi")

    assert problems, "gercek ses cikisi varken yuksek ses testine izin verildi"


@pytest.mark.parametrize("actual", [None, "", "auto"])
def test_safety_gate_blocks_on_unverifiable_output(actual):
    assert audio_safety_problems(actual)


def test_safety_gate_allows_null_output():
    assert audio_safety_problems("null") == []
    assert audio_safety_problems("null/null") == []
