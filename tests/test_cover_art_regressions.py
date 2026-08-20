# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ses dosyalarında albüm kapağı GÖSTERİLİR — native senaryolar AYRI SÜREÇTE.

ÖLÇÜLEN EKSİK (16 Ağustos 2026): ses dosyası açıldığında video alanı siyah
kalıyordu. Ölçüm, bu libmpv sürümünde `audio-display` VARSAYILANININ kapalı
olduğunu gösterdi (ürün yapılandırması suçlu değildi). Kapak TANINIYOR
(`cover-art-auto = 'exact'`) ama parça SEÇİLMİYORDU.

ÖLÇÜLEN İKİNCİ SORUN (17 Ağustos 2026): bu dosya ANA pytest sürecinde
gerçek `mpv.MPV` kuruyordu. Bağımsız koşumda **3 passed / exit 0**
verildiği hâlde stderr'e `Windows fatal exception: code 0xe24c4a02`
düşüyordu (`MPVEventHandlerThread -> mpv.py:689`). Olay hem fixture
geçişinde hem AKTİF testin `wait_until_playing()` satırında görüldü.
Sonraki exact kaynak + CDB denetimi bunun CPython faulthandler'in yakalanmis
LuaJIT first-chance olayina koydugu yaniltici baslik olabilecegini kanitladi;
baslik tek basina crash kaniti sayilmaz.

ÖLÇÜLEN ÜÇÜNCÜ SORUN (aynı gün, bağımsız denetim): bu dosyanın ilk
düzeltmesi `assert "mpv" not in sys.modules` yazıyordu. `app.player`
zaten `mpv` import ettiği için o iddia SIRAYA BAĞLIYDI ve başka bir test
önce koştuğunda düşüyordu:

    pytest test_app_icon_regressions.py::test_the_real_main_window_uses_the_shared_icon \
           test_cover_art_regressions.py::test_the_parent_process_never_imports_mpv
    -> 1 passed, 1 failed

Doğru ölçüm süreç geneli değil, BU MODÜLÜN İMPORT ETKİSİDİR.

NOT: module-scoped fixture'a GEÇİLMEDİ. O yalnız instance sayısını
azaltır; olguyu gizler, çözmez.
"""

import importlib.util
import os
import subprocess
import sys
import threading

import pytest


HOSTED_CI = os.environ.get("MLC_CI") == "1"

from app.config import MPV_CONFIG

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cover_art_native_child import (CLOSE_ORDER_PAIRS, MARKER_GRAMMAR,
                                    NATIVE_FAILURE_PATTERNS, REQUIRED_MARKERS,
                                    decode_stream, evaluate_child,
                                    marker_values)

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "cover_art_native_child.py")
CHILD_TIMEOUT = 120

#: Child'in TAM ve saglikli ciktisi — deterministik testlerin temeli.
GOOD_STDOUT = "\n".join([
    "MARK_COVER_TRACKS 1",
    "MARK_COVER_SELECTED 1",
    "MARK_COVER_STOP",
    "MARK_COVER_TERMINATE",
    "MARK_NOCOVER_ALBUMART 0",
    "MARK_NOCOVER_AUDIO_SELECTED 1",
    "MARK_NOCOVER_STOP",
    "MARK_NOCOVER_TERMINATE",
    "MARK_THREADS_AFTER 0",
    "MARK_DONE",
]) + "\n"

HANDLED_LUAJIT_STDERR = (
    "Windows fatal exception: code 0xe24c4a02\n\n"
    "Thread 0x1234 [MPVEventHandlerThread] (most recent call first):\n"
    "  File \"C:\\\\Python\\\\Lib\\\\site-packages\\\\mpv.py\", "
    "line 689 in _event_generator\n"
    "\n"
    "Current thread's C stack trace (most recent call first):\n"
    "  <cannot get C stack on this system>\n")


def drop_marker(marker, stdout=None):
    """Verilen marker satirini cikarir (TAM ilk-token eslesmesiyle)."""
    text = GOOD_STDOUT if stdout is None else stdout
    kept = [line for line in text.splitlines()
            if line.split()[:1] != [marker]]
    return "\n".join(kept) + "\n"


# =====================================================================
# 1. Deterministik degerlendirme sozlesmesi (native kosum YOK)
# =====================================================================

def test_a_completely_healthy_child_is_accepted():
    assert evaluate_child(0, GOOD_STDOUT, "") == []


def test_a_fatal_native_exception_fails_even_with_exit_zero():
    """ASIL KIRMIZI: exit 0 + butun marker'lar + fatal stderr -> FAIL."""
    stderr = ("Windows fatal exception: code 0xe24c4a02\n"
              "Thread 0x1234 [MPVEventHandlerThread] (most recent call "
              "first):\n  File \"mpv.py\", line 689 in _event_generator\n")

    problems = evaluate_child(0, GOOD_STDOUT, stderr)

    assert problems, "exit 0 + fatal stderr KABUL EDILDI"
    assert any("Windows fatal exception" in p for p in problems), problems


def test_a_complete_handled_luajit_report_is_not_a_cover_art_crash():
    assert evaluate_child(0, GOOD_STDOUT, HANDLED_LUAJIT_STDERR) == []


def test_a_handled_luajit_report_does_not_acquit_nonzero_exit():
    problems = evaluate_child(
        0xE24C4A02, GOOD_STDOUT, HANDLED_LUAJIT_STDERR)

    assert any("exit" in problem.lower() for problem in problems), problems


def test_extra_stderr_after_a_luajit_report_still_fails_cover_art():
    problems = evaluate_child(
        0, GOOD_STDOUT, HANDLED_LUAJIT_STDERR + "ek uyari\n")

    assert problems
    assert any("Windows fatal exception" in problem for problem in problems)


@pytest.mark.parametrize("pattern", NATIVE_FAILURE_PATTERNS)
def test_every_declared_failure_pattern_is_enforced(pattern):
    assert evaluate_child(0, GOOD_STDOUT, f"onceki\n{pattern} ek\n"), (
        f"bildirilen desen zorlanmiyor: {pattern!r}")


def test_a_nonzero_exit_code_fails():
    problems = evaluate_child(1, GOOD_STDOUT, "")

    assert any("exit" in p.lower() for p in problems), problems


@pytest.mark.parametrize("marker", REQUIRED_MARKERS)
def test_every_required_marker_is_mandatory(marker):
    """Marker'lardan biri bile eksikse kabul EDILMEZ."""
    problems = evaluate_child(0, drop_marker(marker), "")

    assert any(marker in p for p in problems), (
        f"{marker} eksikken gecti: {problems}")


# --- Ikinci senaryonun kapanisi AYRI olculur --------------------------

def test_the_second_scenario_stop_marker_is_mandatory():
    """ONCEKI KUSUR: tek `MARK_STOP` cifti vardi; ikinci kapanis
    tamamen kaldirilsa bile degerlendirici YESIL kalabiliyordu."""
    problems = evaluate_child(0, drop_marker("MARK_NOCOVER_STOP"), "")

    assert any("MARK_NOCOVER_STOP" in p for p in problems), problems


def test_the_second_scenario_terminate_marker_is_mandatory():
    problems = evaluate_child(0, drop_marker("MARK_NOCOVER_TERMINATE"), "")

    assert any("MARK_NOCOVER_TERMINATE" in p for p in problems), problems


@pytest.mark.parametrize("stop_marker, term_marker", CLOSE_ORDER_PAIRS)
def test_each_scenario_requires_stop_before_terminate(stop_marker,
                                                      term_marker):
    """Her senaryonun sirasi AYRI dogrulanir."""
    swapped = GOOD_STDOUT.replace(f"{stop_marker}\n{term_marker}",
                                  f"{term_marker}\n{stop_marker}")
    assert swapped != GOOD_STDOUT, "test verisi degismedi"

    problems = evaluate_child(0, swapped, "")

    assert any(stop_marker in p and term_marker in p for p in problems), (
        f"{stop_marker} sira ihlali yakalanmadi: {problems}")


# --- Kapanis HATALARI aklanamaz --------------------------------------

@pytest.mark.parametrize("error_marker", [
    "MARK_COVER_STOP_ERROR",
    "MARK_COVER_TERMINATE_ERROR",
    "MARK_NOCOVER_STOP_ERROR",
    "MARK_NOCOVER_TERMINATE_ERROR",
])
def test_a_shutdown_error_marker_fails(error_marker):
    """`MARK_*_ERROR` varsa, basarili marker'lar onu AKLAMAZ."""
    noisy = GOOD_STDOUT + f"{error_marker} RuntimeError\n"

    problems = evaluate_child(0, noisy, "")

    assert any(error_marker in p for p in problems), problems


# --- Ayristirma: TAM ilk-token, tekrar YASAK -------------------------

def test_a_lookalike_marker_does_not_satisfy_the_real_one():
    """`MARK_DONE_FAKE`, `MARK_DONE` yerine GECMEZ.

    `startswith()` ile ayristiran surum bunu kabul ederdi.
    """
    faked = drop_marker("MARK_DONE") + "MARK_DONE_FAKE\n"

    problems = evaluate_child(0, faked, "")

    assert any("MARK_DONE" in p and "eksik" in p for p in problems), problems


@pytest.mark.parametrize("marker", ["MARK_COVER_STOP", "MARK_DONE",
                                    "MARK_THREADS_AFTER 0"])
def test_a_repeated_singular_marker_fails(marker):
    doubled = GOOD_STDOUT + marker + "\n"

    problems = evaluate_child(0, doubled, "")

    assert any("tekil marker" in p for p in problems), problems


def test_a_malformed_marker_set_is_not_accepted():
    """ASIL KIRMIZI (18 Ağustos 2026, bağımsız denetim).

    Aşağıdaki çıktı `[]` — yani TAMAM — dönüyordu: değerler yalnız
    "beklenenden farklı mı" diye bakılıyor, BİÇİM hiç denetlenmiyordu.
    `abc` bir sayı değil, `MARK_THREADS_AFTER` değersiz kalmış ve
    `MARK_DONE junk` fazladan token taşıyor.
    """
    malformed = "\n".join([
        "MARK_COVER_TRACKS abc",
        "MARK_COVER_SELECTED 1",
        "MARK_COVER_STOP",
        "MARK_COVER_TERMINATE",
        "MARK_NOCOVER_ALBUMART 0",
        "MARK_NOCOVER_AUDIO_SELECTED 1",
        "MARK_NOCOVER_STOP",
        "MARK_NOCOVER_TERMINATE",
        "MARK_THREADS_AFTER",
        "MARK_DONE junk",
    ]) + "\n"

    problems = evaluate_child(0, malformed, "")

    assert problems, "biçimsiz marker seti KABUL EDILDI (fail-open)"
    for marker in ("MARK_COVER_TRACKS", "MARK_THREADS_AFTER", "MARK_DONE"):
        assert any(p.startswith(marker) for p in problems), (
            f"{marker} biçim hatası raporlanmadı: {problems}")


@pytest.mark.parametrize("line", [
    "MARK_COVER_TRACKS abc",       # sayi yerine metin
    "MARK_COVER_TRACKS -1",        # negatif
    "MARK_COVER_TRACKS 0",         # kapak parcasi hic yuklenmemis
    "MARK_COVER_TRACKS 1 extra",   # fazla token
    "MARK_COVER_TRACKS",           # bos deger
    "MARK_THREADS_AFTER",          # bos deger
    "MARK_THREADS_AFTER abc",      # sayi yerine metin
    "MARK_THREADS_AFTER 0 extra",  # fazla token
    "MARK_DONE junk",              # degersiz marker'a deger
    "MARK_COVER_STOP extra",       # degersiz marker'a deger
    "MARK_COVER_SELECTED 2",       # yalniz 1 olmali
    "MARK_NOCOVER_ALBUMART 1",     # yalniz 0 olmali
])
def test_a_malformed_marker_line_fails(line):
    """Fazla/eksik token, metin, negatif veya boş değer KABUL EDILMEZ."""
    marker = line.split()[0]
    broken = drop_marker(marker) + line + "\n"

    problems = evaluate_child(0, broken, "")

    assert any(p.startswith(marker) for p in problems), (
        f"{line!r} kabul edildi: {problems}")


@pytest.mark.parametrize("marker, spec", MARKER_GRAMMAR)
def test_the_grammar_covers_every_required_marker(marker, spec):
    """Dilbilgisi ile zorunlu marker listesi TEK kaynaktan gelir."""
    assert marker in REQUIRED_MARKERS
    assert spec is None or (len(spec) == 2 and callable(spec[1])), spec


def test_marker_values_match_the_exact_first_token():
    assert marker_values("MARK_DONE_FAKE\nMARK_DONE\n", "MARK_DONE") == [""]
    assert marker_values("MARK_COVER_STOP_ERROR X\n",
                         "MARK_COVER_STOP") == []


# --- Semantik sonuclar -----------------------------------------------

def test_the_cover_must_actually_be_selected():
    unselected = GOOD_STDOUT.replace("MARK_COVER_SELECTED 1",
                                     "MARK_COVER_SELECTED 0")

    assert any("MARK_COVER_SELECTED" in p
               for p in evaluate_child(0, unselected, ""))


def test_an_audio_file_without_a_cover_must_not_report_album_art():
    wrong = GOOD_STDOUT.replace("MARK_NOCOVER_ALBUMART 0",
                                "MARK_NOCOVER_ALBUMART 1")

    assert any("MARK_NOCOVER_ALBUMART" in p
               for p in evaluate_child(0, wrong, ""))


def test_a_surviving_event_thread_fails():
    leaked = GOOD_STDOUT.replace("MARK_THREADS_AFTER 0",
                                 "MARK_THREADS_AFTER 1")

    assert any("thread" in p.lower() for p in evaluate_child(0, leaked, ""))


# --- Kodlama: bayt yakalanir, ACIKCA cozulur -------------------------

def test_undecodable_bytes_do_not_hide_an_ascii_failure_pattern():
    """Bozuk kodlamada bile ASCII desen ARANABILIR olmali.

    `text=True` yerel kodlamayi kullanir; cozulemeyen bayt okuma
    THREAD'inde patlayip `stdout`u sessizce `None` yapabilir. Akislar
    BAYT yakalanip `errors="replace"` ile cozulur.
    """
    raw = (b"\xff\xfe bozuk \x9e\n"
           b"Windows fatal exception: code 0xe24c4a02\n")

    text = decode_stream(raw)
    assert "Windows fatal exception" in text

    problems = evaluate_child(0, GOOD_STDOUT.encode("utf-8"), raw)
    assert any("Windows fatal exception" in p for p in problems), problems


def test_the_evaluator_accepts_bytes_for_both_streams():
    assert evaluate_child(0, GOOD_STDOUT.encode("utf-8"), b"") == []


# =====================================================================
# 2. BU MODULUN import etkisi (surec geneli DEGIL)
# =====================================================================

def _load_child_copy():
    """Child yardimci modulunun TAZE bir kopyasini yukler.

    Benzersiz ad kullanilir; `sys.modules` onbellegi olcumu bozmasin.
    """
    spec = importlib.util.spec_from_file_location(
        "cover_art_native_child__probe", CHILD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_importing_the_child_helper_does_not_touch_mpv():
    """Bu modulun IMPORTU `mpv` durumunu DEGISTIRMEZ.

    Baska testlerin daha once `mpv` import etmis olmasi (ornegin
    `app.player` uzerinden) BURADA failure DEGILDIR; olculen sey yalnizca
    bu import'un ETKISIDIR.
    """
    before = sys.modules.get("mpv")

    _load_child_copy()

    assert sys.modules.get("mpv") is before, (
        "child yardimci modulunun importu `mpv` durumunu degistirdi")


def test_importing_the_child_helper_starts_no_mpv_thread():
    """Import YENI bir MPV thread'i olusturmaz (once/sonra farki)."""
    def mpv_threads():
        return {t.ident for t in threading.enumerate()
                if "MPV" in t.name.upper()}

    before = mpv_threads()

    _load_child_copy()

    assert mpv_threads() - before == set(), (
        "child yardimci modulunun importu MPV thread'i baslatti")


def test_the_child_module_has_no_module_level_mpv_import():
    """Statik sozlesme: `import mpv` YALNIZ fonksiyon icinde olabilir."""
    with open(CHILD, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            stripped = line.rstrip("\n")
            if stripped.startswith(("import mpv", "from mpv")):
                pytest.fail(
                    f"{os.path.basename(CHILD)}:{number} modul duzeyinde "
                    f"mpv import ediyor: {stripped!r}")


# =====================================================================
# 3. Kaynak duzeyi sozlesme (native DEGIL, ana surecte kalabilir)
# =====================================================================

def test_cover_display_is_configured_in_the_single_mpv_config():
    """Ayar ürünün TEK mpv yapılandırmasından gelir, dağınık yama değil."""
    assert MPV_CONFIG.get("audio_display") in ("embedded-first",
                                               "external-first"), MPV_CONFIG


# =====================================================================
# 4. GERCEK native kabul — TEK kosum
# =====================================================================

@pytest.mark.skipif(HOSTED_CI, reason="hosted CI has no native libmpv runtime")
def test_the_native_cover_art_scenarios_pass_in_a_child_process():
    """Gercek libmpv kabulu: ayri surec, TEK kosum.

    Akislar BAYT yakalanir (`text=True` YOK). Yalniz tam CPython/LuaJIT VEH
    raporu + exit 0 + eksiksiz marker sozlesmesi tanisal gurultu sayilir;
    diger fatal/stderr ve kapanis kusurlari FAIL verir.
    """
    result = subprocess.run(
        [sys.executable, CHILD],
        capture_output=True, timeout=CHILD_TIMEOUT,
        cwd=os.path.dirname(os.path.dirname(CHILD)))

    problems = evaluate_child(result.returncode, result.stdout, result.stderr)

    assert not problems, (
        "native cover-art kabulu BASARISIZ:\n  - "
        + "\n  - ".join(problems)
        + f"\n--- STDOUT ---\n{decode_stream(result.stdout)}"
        + f"\n--- STDERR ---\n{decode_stream(result.stderr)}")
