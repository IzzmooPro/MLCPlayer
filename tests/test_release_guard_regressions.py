# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kurulu istemcilerin göremeyeceği bir sürüm yayımlanamaz.

ÖLÇÜLEN TUZAK: sürüm karşılaştırması sayısaldır, bu yüzden `v0.31` varken
`v0.4` yayımlanırsa (`31 > 4`) kurulu kopyalar güncellemeyi hiç görmez ve
sessizce "güncelsiniz" der. Kural yayım zincirinde zorlanır.

Testler AĞA ÇIKMAZ: etiket listesi doğrudan verilir.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _guard():
    path = ROOT / "packaging" / "check_publishable.py"
    spec = importlib.util.spec_from_file_location("mlc_release_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _guard()


def test_first_release_is_publishable():
    ok, message = guard.evaluate("v0.1", [])
    assert ok and "Ilk yayin" in message


def test_newer_version_is_publishable():
    ok, message = guard.evaluate("v0.32", ["v0.31", "v0.3"])
    assert ok, message


def test_the_numeric_trap_is_blocked():
    """ASIL KORUMA: v0.31 varken v0.4 istemcilere görünmez."""
    ok, message = guard.evaluate("v0.4", ["v0.31", "v0.3"])
    assert not ok
    assert "GOREMEZ" in message
    assert "v0.40" in message, "kullanıcıya doğru biçim önerilmeli"


def test_the_safe_form_of_a_bigger_step_passes():
    ok, _ = guard.evaluate("v0.40", ["v0.31", "v0.3"])
    assert ok


def test_republishing_the_same_tag_is_blocked(monkeypatch):
    monkeypatch.delenv("MLC_ALLOW_REPUBLISH", raising=False)
    ok, message = guard.evaluate("v0.31", ["v0.31", "v0.3"])
    assert not ok and "ZATEN" in message
    assert "MLC_ALLOW_REPUBLISH" in message, "çıkış yolu söylenmeli"


def test_deliberate_rebuild_is_allowed_with_an_explicit_flag(monkeypatch):
    """Yalnız kurulum sarmalayıcısı değiştiğinde yeniden derleme meşrudur."""
    monkeypatch.setenv("MLC_ALLOW_REPUBLISH", "1")
    ok, message = guard.evaluate("v0.31", ["v0.31", "v0.3"])
    assert ok and "UYARI" in message


def test_equal_or_older_version_is_blocked():
    ok, message = guard.evaluate("v0.2", ["v0.31"])
    assert not ok and "YENI DEGIL" in message


def test_missing_network_warns_but_does_not_stop_the_chain():
    """Ağsız makinede build durmamalı; ama sessiz de geçmemeli."""
    ok, message = guard.evaluate("v0.9", None)
    assert ok
    assert "UYARI" in message and "elle dogrulayin" in message


def test_build_chain_runs_the_guard():
    """Kontrol betiği zincire bağlı değilse hiçbir şeyi korumaz."""
    chain = (ROOT / "packaging" / "build_release.bat").read_text(
        encoding="utf-8", errors="ignore")
    assert "check_publishable.py" in chain
