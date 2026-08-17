# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Süreç içi child import'u Qt platformunu SIZDIRMAMALI.

ÖLÇÜLEN KIRMIZI KANIT (tam paket, 2026-08-15)
---------------------------------------------
`pytest -q tests` üç bağımsız koşumda 78 / 54 / 78 FAIL verdi; başarısız
testlerin tamamı overlay görünürlük, opaklık ve geometri ölçümleriydi
(`overlay_button_hit`, `overlay_autohide`, `overlay_fade`, `overlay_visual`,
`playlist_panel`, `title_bar_hardening` ...). Her dosya TEK BAŞINA yeşildi.

Teşhis eklentisi başarısızlık anındaki gerçek durumu yazdı:

    overlay_visible: True      overlay_opacity: 0.0
    fade_state: State.Running  suppressed: False
    window_geom: QRect(640, 336, 1280, 720)
    platform: windows

Yani QApplication `offscreen` değil GERÇEK `windows` platformunda kurulmuştu:
pencereler ekranda konumlanıyor, fade animasyonu gerçek zamanla ilerliyor ve
`_foreground_measurement_supported()` açılıyor. Test dosyalarının başındaki
`os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` çağrıları anahtar
zaten silinmiş olduğu için işe yarıyor sanılıyordu; oysa QApplication ondan
sonra kuruluyordu.

KÖK NEDEN
---------
`tests/native_resize_diag_child.py` AYRI SÜREÇTE gerçek pencereyle koşmak
üzere yazılmıştır ve modül düzeyinde bilerek

    os.environ.pop("QT_QPA_PLATFORM", None)

yapar. Bu child DOĞRU davranıştır ve DEĞİŞTİRİLMEZ. Ancak
`test_native_resize_input_safety_regressions.py::child_module` fixture'ı aynı
modülü `exec_module()` ile SÜREÇ İÇİNDE çalıştırıyor; pop bu durumda pytest
sürecinin kendi ortamını kalıcı olarak bozuyor. Fixture `MLC_NATIVE_SMOKE`
anahtarını zaten kaydedip geri yüklüyordu, `QT_QPA_PLATFORM` unutulmuştu.

Alfabetik sırada `test_native_resize_input_safety` bütün `test_overlay_*`
dosyalarından ÖNCE geldiği için sızıntı tam pakette overlay testlerine
vuruyordu; FAIL sayısının koşumdan koşuma değişmesi gerçek pencere/zamanlama
davranışının belirsizliğindendi.

Bu dosya sözleşmeyi iki ayrı seviyede kilitler: gerçek pytest koşumu ve
fixture'ın kendi ortam sözleşmesi.
"""
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")

# Sızıntıyı üreten dosya ve ondan SONRA gelen ilk kurban dosya.
LEAKING_MODULE = "tests/test_native_resize_input_safety_regressions.py"
VICTIM_MODULE = "tests/test_overlay_fade_regressions.py"

pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="sizinti yalniz Windows child modulunde uretiliyor")


def test_the_overlay_suite_survives_the_in_process_child_import():
    """Kırmızı kanıtın birebir kendisi: iki dosya birlikte YEŞİL olmalı.

    Düzeltmeden önce bu koşum `5 failed, 25 passed` veriyordu.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no",
         LEAKING_MODULE, VICTIM_MODULE],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, (
        "Sizinti geri geldi:\n" + completed.stdout[-2000:])


def test_the_in_process_child_import_keeps_the_offscreen_platform():
    """Fixture'ın kendi sözleşmesi: import ortam anahtarını GERİ YÜKLER.

    Fixture doğrudan çağrılamaz (module kapsamlı generator değil, düz
    fonksiyondur); ürün olmayan harness kodu olduğu için gerçek çağrı
    `pytest` üzerinden yapılır ve anahtar koşumdan SONRA denetlenir.
    """
    probe = (
        "import os, sys\n"
        "sys.path.insert(0, %r)\n"
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location(\n"
        "    'leak_probe_module',\n"
        "    os.path.join(%r, 'test_native_resize_input_safety_regressions.py'))\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "before = os.environ.get('QT_QPA_PLATFORM')\n"
        "module.child_module.__wrapped__()\n"
        "print('BEFORE=%%s AFTER=%%s' %% (before, os.environ.get('QT_QPA_PLATFORM')))\n"
    ) % (ROOT, TESTS)
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr[-2000:]
    line = [row for row in completed.stdout.splitlines()
            if row.startswith("BEFORE=")]
    assert line, completed.stdout
    before, after = line[-1].split(" AFTER=")
    before = before[len("BEFORE="):]
    assert after == before, (
        f"child import QT_QPA_PLATFORM'u degistirdi: {before!r} -> {after!r}")


def test_the_child_itself_still_drops_the_platform_for_real_windows():
    """Child'ın kendi davranışı DEĞİŞMEZ: ayrı süreçte gerçek pencere ister."""
    source_path = os.path.join(TESTS, "native_resize_diag_child.py")
    with open(source_path, encoding="utf-8", errors="replace") as handle:
        source = handle.read()
    assert 'os.environ.pop("QT_QPA_PLATFORM", None)' in source
