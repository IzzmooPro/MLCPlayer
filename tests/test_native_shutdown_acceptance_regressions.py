# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""NATIVE-001 asama 2 sozlesmesi: URUN kapanis yolunun kabul olcutu.

Bu dosya GERCEK MPV veya urun kodu YUKLEMEZ. Yalnizca saf
`evaluate_shutdown_result()` sozlesmesini olcer; canli kabul ayri ve TEK
bir kosumdur (`test_the_product_shutdown_path_survives_a_real_run`).

CPython 3.14 Windows faulthandler, daha sonra LuaJIT tarafindan yakalanan
first-chance `0xe24c4a02` olayini da "fatal" diye yazar. Yalniz TAM CPython
raporu + exit 0 + eksiksiz marker/RESULTS sozlesmesi kabul edilir. Truncated
rapor, baska kod, ek stderr, nonzero exit ve eksik marker fail-closed kalir.
Aralikli native olguyu kirmizi uretmek icin canli test TEKRARLANMAZ.
"""

import ast
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from native_media_contract import (MEDIA_FIELD_PREFIX,  # noqa: E402
                                   decode_media_basename,
                                   encode_media_basename,
                                   is_supported_media)
from native_windows_exception_contract import (  # noqa: E402
    LUAJIT_RUNTIME_ERROR_TRACE, complete_luajit_faulthandler_reports)
import native_shutdown_acceptance as acceptance  # noqa: E402
from native_shutdown_acceptance import (CHILD, EXPECTED_RESULTS,  # noqa: E402
                                        FAILURE_PATTERNS, MARKER_GRAMMAR,
                                        MEDIA_MARKERS, OPT_IN_VARIABLE,
                                        REQUIRED_MARKERS,
                                        evaluate_shutdown_result,
                                        live_run_blockers,
                                        media_stat, media_stat_problems,
                                        native_acceptance_requested,
                                        resolve_media, run_native_shutdown,
                                        timeout_problems)

MEDIA_NAME = "ornek.mkv"
MEDIA_FIELD = MEDIA_FIELD_PREFIX + encode_media_basename(MEDIA_NAME)

#: Child'in SAGLIKLI ciktisi (bicim `mark()` ile birebir ayni).
GOOD_STDOUT = "\n".join([
    "MARK_FAULTHANDLER_ENABLED t=0.00",
    "MARK_PLAYER_CREATED t=0.51 " + MEDIA_FIELD,
    "MARK_MEDIA_OPEN_REQUESTED t=0.52 " + MEDIA_FIELD,
    "MARK_MEDIA_READY t=1.24 duration=132.00 position=0.10",
    "MARK_CLOSE_REQUESTED t=1.65",
    "MARK_STOP_CALLED t=1.66 count=1",
    "MARK_TERMINATE_CALLED t=1.71 count=1",
    "MARK_CLOSE_ACCEPTED t=1.72 visible=False",
    "MARK_APP_EXEC_RETURNED t=1.73 code=0",
    "MARK_THREADS_AFTER t=1.74 count=0",
    EXPECTED_RESULTS,
    "MARK_MAIN_RETURNED t=1.75 0",
]) + "\n"

FATAL_STDERR = ("Windows fatal exception: code 0xe24c4a02\n"
                "Thread 0x000021f4 [MPVEventHandlerThread] (most recent "
                "call first):\n")

HANDLED_LUAJIT_STDERR = (
    "Windows fatal exception: code 0xe24c4a02\n\n"
    "Thread 0x000021f4 [MPVEventHandlerThread] (most recent call first):\n"
    "  File \"C:\\\\Python\\\\Lib\\\\site-packages\\\\mpv.py\", "
    "line 689 in _event_generator\n"
    "\n"
    "Thread 0x00001234 (most recent call first):\n"
    "  File \"C:\\\\project\\\\app\\\\player.py\", line 460 in update_ui\n"
    "\n"
    "Current thread's C stack trace (most recent call first):\n"
    "  <cannot get C stack on this system>\n")

GENERIC_FATAL_STDERR = "Windows fatal exception: code 0xc0000005\n"

MEDIA_BEFORE = {"path": "C:\\media\\ornek.mkv", "size": 12345,
                "mtime_ns": 1755400000000000000}


def drop_marker(marker, stdout=None):
    text = GOOD_STDOUT if stdout is None else stdout
    kept = [line for line in text.splitlines()
            if line.split()[:1] != [marker]]
    return "\n".join(kept) + "\n"


def replace_marker(marker, new_line, stdout=None):
    return drop_marker(marker, stdout) + new_line + "\n"


# =====================================================================
# 1. Asil kirmizi ve fatal desenler
# =====================================================================

def test_a_completely_healthy_shutdown_is_accepted():
    assert evaluate_shutdown_result(0, GOOD_STDOUT, "") == []


def test_exit_zero_with_a_fatal_stderr_is_rejected():
    """Eksik/truncated `fatal` metni yakalanmis SEH kaniti sayilamaz."""
    problems = evaluate_shutdown_result(0, GOOD_STDOUT, FATAL_STDERR)

    assert problems, "exit 0 + fatal stderr KABUL EDILDI"
    assert any("Windows fatal exception" in p for p in problems), problems


def test_luajit_runtime_error_is_classified_without_becoming_a_pass():
    problems = evaluate_shutdown_result(0, GOOD_STDOUT, FATAL_STDERR)

    assert any("LuaJIT" in problem and "LUA_ERRRUN" in problem
               for problem in problems), problems
    assert not any("fatal iz" in problem and "Windows fatal exception" in problem
                   for problem in problems), problems


def test_a_complete_handled_luajit_faulthandler_report_is_not_a_crash():
    """CPython VEH first-chance'i `fatal` yazar; exit 0 yakalandigini kanitlar."""
    assert evaluate_shutdown_result(
        0, GOOD_STDOUT, HANDLED_LUAJIT_STDERR) == []


def test_multiple_complete_handled_luajit_reports_are_accepted():
    stderr = HANDLED_LUAJIT_STDERR + HANDLED_LUAJIT_STDERR

    assert evaluate_shutdown_result(0, GOOD_STDOUT, stderr) == []


def test_a_luajit_report_with_nonzero_exit_is_still_rejected():
    problems = evaluate_shutdown_result(
        0xE24C4A02, GOOD_STDOUT, HANDLED_LUAJIT_STDERR)

    assert any("exit code" in problem for problem in problems), problems


def test_a_luajit_report_cannot_acquit_an_incomplete_shutdown():
    problems = evaluate_shutdown_result(
        0, drop_marker("MARK_MAIN_RETURNED"), HANDLED_LUAJIT_STDERR)

    assert any("MARK_MAIN_RETURNED" in problem for problem in problems)


def test_extra_stderr_next_to_a_luajit_report_is_rejected():
    problems = evaluate_shutdown_result(
        0, GOOD_STDOUT, HANDLED_LUAJIT_STDERR + "libpng warning: iCCP\n")

    assert any("stderr bos DEGIL" in problem for problem in problems), problems


def test_a_complete_luajit_report_on_stdout_is_never_exempt():
    problems = evaluate_shutdown_result(
        0, GOOD_STDOUT + HANDLED_LUAJIT_STDERR, "")

    assert problems
    assert any("Windows fatal exception" in problem for problem in problems)


@pytest.mark.parametrize("mutate", [
    lambda text: text.replace(
        LUAJIT_RUNTIME_ERROR_TRACE + "\n\n",
        LUAJIT_RUNTIME_ERROR_TRACE + "\n", 1),
    lambda text: text.replace(
        "Thread 0x000021f4 [MPVEventHandlerThread] "
        "(most recent call first):\n", "", 1),
    lambda text: text.replace(
        "  File \"C:\\\\Python\\\\Lib\\\\site-packages\\\\mpv.py\", "
        "line 689 in _event_generator\n", "", 1),
    lambda text: text.replace(
        "Current thread's C stack trace (most recent call first):\n", "", 1),
    lambda text: text.replace(
        "  <cannot get C stack on this system>\n", "", 1),
    lambda text: "\ufffd" + text,
    lambda text: "on ek\n" + text,
    lambda text: text + "son ek\n",
])
def test_incomplete_or_contaminated_luajit_reports_are_rejected(mutate):
    broken = mutate(HANDLED_LUAJIT_STDERR)

    assert broken != HANDLED_LUAJIT_STDERR
    assert not complete_luajit_faulthandler_reports(broken)
    assert evaluate_shutdown_result(0, GOOD_STDOUT, broken)


def test_the_windows_exception_contract_is_native_import_free():
    path = os.path.join(os.path.dirname(__file__),
                        "native_windows_exception_contract.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "mpv" not in imported
    assert "PyQt6" not in imported


def test_both_native_gates_use_the_single_windows_exception_classifier():
    root = os.path.dirname(__file__)
    for name in ("native_shutdown_acceptance.py",
                 "cover_art_native_child.py"):
        with open(os.path.join(root, name), encoding="utf-8") as handle:
            source = handle.read()
        assert "complete_luajit_faulthandler_reports" in source, name
        assert "def complete_luajit_faulthandler_reports" not in source, name


def test_an_unrelated_windows_fatal_exception_keeps_the_generic_guard():
    problems = evaluate_shutdown_result(0, GOOD_STDOUT, GENERIC_FATAL_STDERR)

    assert any("fatal iz" in problem and "Windows fatal exception" in problem
               for problem in problems), problems


@pytest.mark.parametrize("pattern", FAILURE_PATTERNS)
def test_every_failure_pattern_is_enforced_on_stderr(pattern):
    assert evaluate_shutdown_result(0, GOOD_STDOUT, f"{pattern} ek\n")


@pytest.mark.parametrize("pattern", FAILURE_PATTERNS)
def test_every_failure_pattern_is_enforced_on_stdout(pattern):
    """Fatal iz stdout'a dusse de kabul edilemez."""
    noisy = GOOD_STDOUT + f"{pattern} ek\n"

    assert any(pattern in p for p in evaluate_shutdown_result(0, noisy, ""))


def test_any_nonempty_stderr_is_rejected_without_a_whitelist():
    """Ilk turda 'zararsiz uyari' muafiyeti YOK."""
    problems = evaluate_shutdown_result(0, GOOD_STDOUT, "libpng warning: iCCP\n")

    assert any("stderr bos DEGIL" in p for p in problems), problems


def test_a_nonzero_exit_code_is_rejected():
    assert any("exit code" in p
               for p in evaluate_shutdown_result(1, GOOD_STDOUT, ""))


# =====================================================================
# 2. Marker varligi, tekilligi ve sozdizimi
# =====================================================================

@pytest.mark.parametrize("marker", REQUIRED_MARKERS)
def test_every_required_marker_is_mandatory(marker):
    problems = evaluate_shutdown_result(0, drop_marker(marker), "")

    assert any(marker in p for p in problems), (marker, problems)


@pytest.mark.parametrize("marker", REQUIRED_MARKERS)
def test_a_repeated_marker_is_rejected(marker):
    line = [ln for ln in GOOD_STDOUT.splitlines()
            if ln.split()[:1] == [marker]][0]
    doubled = GOOD_STDOUT + line + "\n"

    problems = evaluate_shutdown_result(0, doubled, "")

    assert any("tekil marker" in p for p in problems), (marker, problems)


def test_the_stop_marker_must_come_before_terminate():
    swapped = GOOD_STDOUT.replace(
        "MARK_STOP_CALLED t=1.66 count=1\n"
        "MARK_TERMINATE_CALLED t=1.71 count=1",
        "MARK_TERMINATE_CALLED t=1.71 count=1\n"
        "MARK_STOP_CALLED t=1.66 count=1")
    assert swapped != GOOD_STDOUT

    assert any("kapanis sirasi yanlis" in p
               for p in evaluate_shutdown_result(0, swapped, ""))


@pytest.mark.parametrize("line", [
    "MARK_STOP_CALLED t=1.66 count=0",
    "MARK_STOP_CALLED t=1.66 count=2",
    "MARK_STOP_CALLED t=1.66",
    "MARK_STOP_CALLED t=1.66 count=1 extra",
    "MARK_STOP_CALLED count=1",
])
def test_a_malformed_stop_marker_is_rejected(line):
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_STOP_CALLED", line), "")

    assert any(p.startswith("MARK_STOP_CALLED") for p in problems), problems


@pytest.mark.parametrize("line", [
    "MARK_TERMINATE_CALLED t=1.71 count=0",
    "MARK_TERMINATE_CALLED t=1.71 count=2",
    "MARK_TERMINATE_CALLED t=1.71",
    "MARK_TERMINATE_CALLED t=abc count=1",
])
def test_a_malformed_terminate_marker_is_rejected(line):
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_TERMINATE_CALLED", line), "")

    assert any(p.startswith("MARK_TERMINATE_CALLED") for p in problems), problems


@pytest.mark.parametrize("value", ["1", "-1", "9"])
def test_a_surviving_mpv_thread_is_rejected(value):
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_THREADS_AFTER",
                          f"MARK_THREADS_AFTER t=1.74 count={value}"), "")

    assert any(p.startswith("MARK_THREADS_AFTER") for p in problems), problems


@pytest.mark.parametrize("value", ["1", "-1"])
def test_a_nonzero_qt_exec_code_is_rejected(value):
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_APP_EXEC_RETURNED",
                          f"MARK_APP_EXEC_RETURNED t=1.73 code={value}"), "")

    assert any(p.startswith("MARK_APP_EXEC_RETURNED") for p in problems), problems


@pytest.mark.parametrize("line", [
    "MARK_MAIN_RETURNED t=1.75 1",
    "MARK_MAIN_RETURNED t=1.75 2",
    "MARK_MAIN_RETURNED t=1.75",
    "MARK_MAIN_RETURNED t=1.75 0 extra",
])
def test_a_bad_main_return_value_is_rejected(line):
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_MAIN_RETURNED", line), "")

    assert any(p.startswith("MARK_MAIN_RETURNED") for p in problems), problems


def test_a_valueless_marker_may_not_carry_a_value():
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_CLOSE_REQUESTED",
                          "MARK_CLOSE_REQUESTED t=1.65 junk"), "")

    assert any(p.startswith("MARK_CLOSE_REQUESTED") for p in problems), problems


def test_a_media_timeout_is_not_a_success():
    """`MARK_MEDIA_READY TIMEOUT` bilgilendirici degil, BASARISIZLIKTIR."""
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_MEDIA_READY",
                          "MARK_MEDIA_READY t=26.0 TIMEOUT"), "")

    assert any("TIMEOUT" in p for p in problems), problems


@pytest.mark.parametrize("fake", [
    "MARK_STOP_CALLED_FAKE t=1.66 count=1",
    "MARK_MAIN_RETURNED_EXTRA t=1.75 0",
    "MARK_THREADS_AFTER_TOTAL t=1.74 count=0",
])
def test_a_lookalike_marker_does_not_satisfy_the_real_one(fake):
    """Prefix benzeri satir gercek marker YERINE GECMEZ."""
    real = fake.split()[0].rsplit("_", 1)[0]
    real = next(m for m in REQUIRED_MARKERS if fake.split()[0].startswith(m))
    faked = drop_marker(real) + fake + "\n"

    problems = evaluate_shutdown_result(0, faked, "")

    assert any(f"eksik marker: {real}" in p for p in problems), problems


# =====================================================================
# 2b. BAGIMSIZ DENETIMIN BES KANITI (18 Agustos 2026)
# =====================================================================

@pytest.mark.parametrize("line", [
    "MARK_PLAYER_CREATED t=0.51",           # medya adi YOK
    "MARK_MEDIA_OPEN_REQUESTED t=0.52",     # medya adi YOK
    "MARK_MEDIA_READY t=1.24",              # duration/position YOK
    "MARK_CLOSE_ACCEPTED t=1.72 visible=True",   # pencere KAPANMAMIS
    "MARK_CLOSE_REQUESTED t=nan",           # gecersiz zaman damgasi
])
def test_the_audited_fail_open_lines_are_now_rejected(line):
    """ASIL KIRMIZI: bu bes satirin her biri `[]` ile KABUL EDILIYORDU."""
    marker = line.split()[0]

    problems = evaluate_shutdown_result(0, replace_marker(marker, line), "")

    assert any(p.startswith(marker) for p in problems), (line, problems)


# --- Medya marker'lari -------------------------------------------------

@pytest.mark.parametrize("marker", MEDIA_MARKERS)
def test_a_media_marker_without_a_name_is_rejected(marker):
    problems = evaluate_shutdown_result(
        0, replace_marker(marker, f"{marker} t=0.51"), "")

    assert any("medya alani ister" in p for p in problems), problems


@pytest.mark.parametrize("marker", MEDIA_MARKERS)
def test_a_media_marker_must_report_the_expected_file(marker):
    """Beklenen basename verilmisse marker BASKA dosya bildiremez."""
    stdout = replace_marker(
        marker, f"{marker} t=0.51 {MEDIA_FIELD_PREFIX}"
        + encode_media_basename("baska.mkv"))

    problems = evaluate_shutdown_result(0, stdout, "",
                                        expected_basename=MEDIA_NAME)

    assert any("beklenen medyayi bildirmiyor" in p for p in problems), problems


def test_the_two_media_markers_must_agree_with_each_other():
    """Beklenen ad verilmese bile iki marker AYNI dosyayi bildirmeli."""
    stdout = replace_marker(
        "MARK_MEDIA_OPEN_REQUESTED",
        "MARK_MEDIA_OPEN_REQUESTED t=0.52 " + MEDIA_FIELD_PREFIX
        + encode_media_basename("baska.mp4"))

    problems = evaluate_shutdown_result(0, stdout, "")

    assert any("ayrisiyor" in p for p in problems), problems


def test_the_expected_basename_is_accepted_when_it_matches():
    assert evaluate_shutdown_result(0, GOOD_STDOUT, "",
                                    expected_basename=MEDIA_NAME) == []


# --- MARK_MEDIA_READY ---------------------------------------------------

@pytest.mark.parametrize("line", [
    "MARK_MEDIA_READY t=1.24 duration=132.00",            # position YOK
    "MARK_MEDIA_READY t=1.24 position=0.10",              # duration YOK
    "MARK_MEDIA_READY t=1.24 duration=abc position=0.10",
    "MARK_MEDIA_READY t=1.24 duration=nan position=0.10",
    "MARK_MEDIA_READY t=1.24 duration=inf position=0.10",
    "MARK_MEDIA_READY t=1.24 duration=-1 position=0.10",
    "MARK_MEDIA_READY t=1.24 duration=132.00 position=nan",
    "MARK_MEDIA_READY t=1.24 duration=132.00 position=-0.5",
    "MARK_MEDIA_READY t=1.24 duration=0 position=0",      # medya ACILMAMIS
    "MARK_MEDIA_READY t=26.0 TIMEOUT",
    "MARK_MEDIA_READY t=1.24 sure=132.00 position=0.10",  # yanlis alan adi
])
def test_a_malformed_media_ready_marker_is_rejected(line):
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_MEDIA_READY", line), "")

    assert any(p.startswith("MARK_MEDIA_READY") for p in problems), problems


def test_a_media_ready_with_only_a_position_is_accepted():
    """Canli akista `duration` 0 olabilir; position > 0 yeterlidir."""
    stdout = replace_marker(
        "MARK_MEDIA_READY",
        "MARK_MEDIA_READY t=1.24 duration=0.00 position=0.10")

    assert evaluate_shutdown_result(0, stdout, "") == []


# --- MARK_CLOSE_ACCEPTED ------------------------------------------------

@pytest.mark.parametrize("line", [
    "MARK_CLOSE_ACCEPTED t=1.72 visible=True",
    "MARK_CLOSE_ACCEPTED t=1.72",
    "MARK_CLOSE_ACCEPTED t=1.72 visible=False extra",
    "MARK_CLOSE_ACCEPTED t=1.72 False",
])
def test_a_malformed_close_accepted_marker_is_rejected(line):
    problems = evaluate_shutdown_result(
        0, replace_marker("MARK_CLOSE_ACCEPTED", line), "")

    assert any(p.startswith("MARK_CLOSE_ACCEPTED") for p in problems), problems


# --- Zaman damgalari ----------------------------------------------------

@pytest.mark.parametrize("marker", REQUIRED_MARKERS)
@pytest.mark.parametrize("stamp", ["nan", "inf", "-inf", "-1.0", "abc"])
def test_an_invalid_timestamp_is_rejected_for_every_marker(marker, stamp):
    """`float()` donusumu YETMEZ; sonlu ve negatif olmayan olmali."""
    line = [ln for ln in GOOD_STDOUT.splitlines()
            if ln.split()[:1] == [marker]][0]
    broken = line.replace(line.split()[1], f"t={stamp}", 1)

    problems = evaluate_shutdown_result(0, replace_marker(marker, broken), "")

    assert any(p.startswith(marker) and "zaman damgasi" in p
               for p in problems), (broken, problems)


@pytest.mark.parametrize("marker", REQUIRED_MARKERS)
def test_a_missing_timestamp_is_rejected_for_every_marker(marker):
    line = [ln for ln in GOOD_STDOUT.splitlines()
            if ln.split()[:1] == [marker]][0]
    without = " ".join([line.split()[0]] + line.split()[2:])

    problems = evaluate_shutdown_result(0, replace_marker(marker, without), "")

    assert any("zaman damgasi" in p for p in problems), (without, problems)


# =====================================================================
# 2b-2. Bosluklu ve Unicode medya adlari (kayipsiz protokol)
# =====================================================================

REALISTIC_NAMES = [
    "kayıt 01.mkv",                    # BAGIMSIZ KANIT: eski protokol DUSURUYORDU
    "4K HEVC Film 01.mkv",
    "Şğüöçİ Türkçe Kayıt.mkv",
    "film (2026) [1080p].mp4",
    "🎬 movie night.mkv",
    "  bosluklu  kenar  .mkv",
    "ornek.mkv",
]


@pytest.mark.parametrize("name", REALISTIC_NAMES)
def test_the_codec_round_trips_every_realistic_name(name):
    """Kodlama KAYIPSIZ ve cikti BOSLUKSUZ olmali."""
    token = encode_media_basename(name)

    assert " " not in token, f"token bosluk iceriyor: {token!r}"
    assert token.isascii(), f"token ASCII disi: {token!r}"
    assert decode_media_basename(token) == name


@pytest.mark.parametrize("name", REALISTIC_NAMES)
def test_a_name_with_spaces_or_unicode_is_accepted_end_to_end(name):
    """ASIL KIRMIZI (eski protokol): `kayıt 01.mkv` iki alan sayilip FAIL'di."""
    field = MEDIA_FIELD_PREFIX + encode_media_basename(name)
    stdout = replace_marker(
        "MARK_PLAYER_CREATED", f"MARK_PLAYER_CREATED t=0.51 {field}")
    stdout = replace_marker(
        "MARK_MEDIA_OPEN_REQUESTED",
        f"MARK_MEDIA_OPEN_REQUESTED t=0.52 {field}", stdout)

    assert evaluate_shutdown_result(0, stdout, "",
                                    expected_basename=name) == []


@pytest.mark.parametrize("marker", MEDIA_MARKERS)
@pytest.mark.parametrize("field", [
    "media_b64=!!!bozuk!!!",                 # gecersiz Base64
    "media_b64=/w==",                        # Base64 dogru, UTF-8 GECERSIZ
    "media_b64=",                            # bos token
    "media_b64=" + "",                       # bos token (acik)
    "ornek.mkv",                             # onek YOK (eski protokol)
    "medya=" + encode_media_basename("ornek.mkv"),   # yanlis onek
])
def test_a_malformed_media_field_is_rejected(marker, field):
    problems = evaluate_shutdown_result(
        0, replace_marker(marker, f"{marker} t=0.51 {field}"), "")

    assert any(p.startswith(marker) for p in problems), (field, problems)


@pytest.mark.parametrize("marker", MEDIA_MARKERS)
def test_an_empty_decoded_name_is_rejected(marker):
    field = MEDIA_FIELD_PREFIX + encode_media_basename("")

    problems = evaluate_shutdown_result(
        0, replace_marker(marker, f"{marker} t=0.51 {field}"), "")

    assert any("BOS" in p or "cozulemedi" in p for p in problems), problems


@pytest.mark.parametrize("marker", MEDIA_MARKERS)
def test_an_extra_media_field_is_rejected(marker):
    line = f"{marker} t=0.51 {MEDIA_FIELD} {MEDIA_FIELD}"

    problems = evaluate_shutdown_result(0, replace_marker(marker, line), "")

    assert any("TAM bir medya alani" in p for p in problems), problems


def test_invalid_base64_is_not_silently_repaired():
    """`errors='replace'` ile kurtarma YOK: yanlis dosya dogru gorunemez."""
    assert decode_media_basename("/w==") is None       # gecersiz UTF-8
    assert decode_media_basename("!!!") is None        # gecersiz Base64
    assert decode_media_basename("") is None
    assert decode_media_basename(None) is None


def test_the_child_and_the_gate_share_one_codec():
    """Kod iki yerde KOPYALANMAZ; ikisi de ortak modulden import eder."""
    with open(CHILD, encoding="utf-8") as handle:
        child_source = handle.read()
    gate = os.path.join(os.path.dirname(CHILD), "native_shutdown_acceptance.py")
    with open(gate, encoding="utf-8") as handle:
        gate_source = handle.read()

    for source, label in ((child_source, "child"), (gate_source, "kapi")):
        assert "from native_media_contract import" in source, label
        for copied in ("import base64", "b64encode(", "b64decode("):
            assert copied not in source, (
                f"{label} kendi kodlama kodunu tasiyor ({copied!r}); "
                "codec TEK kaynak olmali")


# =====================================================================
# 2b-3. Child'in KENDI medya dogrulamasi (kaynak sozlesmesi)
# =====================================================================

def test_the_child_uses_the_shared_media_validator():
    """Uzanti listesi child'da TEKRARLANMAZ."""
    with open(CHILD, encoding="utf-8") as handle:
        source = handle.read()

    assert "is_supported_media(" in source
    assert '".mkv"' not in source and '".mp4"' not in source, (
        "child uzanti listesini ikinci kez tasiyor")


@pytest.mark.parametrize("name", ["ornek.py", "ornek.wav", "ornek.txt",
                                  "ornek"])
def test_the_shared_validator_rejects_non_video_for_the_child(tmp_path, name):
    """Child DOGRUDAN calistirilsa bile bu dosyalari kabul edemez."""
    path = tmp_path / name
    path.write_bytes(b"x")

    assert not is_supported_media(str(path))


def test_the_shared_validator_rejects_directories_and_missing_paths(tmp_path):
    assert not is_supported_media(str(tmp_path))
    assert not is_supported_media(str(tmp_path / "yok.mkv"))


@pytest.mark.parametrize("name", ["ornek.MKV", "ornek.MP4",
                                  "kayıt 01.mkv", "4K HEVC Film 01.MKV"])
def test_the_shared_validator_accepts_valid_names(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"x")

    assert is_supported_media(str(path))


# =====================================================================
# 2c. ACIK native opt-in kapisi
# =====================================================================

def test_media_alone_does_not_request_the_live_run(tmp_path):
    """OLCULEN FAIL-OPEN: medya degiskeni tek basina kosumu baslatiyordu."""
    video = tmp_path / "ornek.mkv"
    video.write_bytes(b"x")
    env = {"MLC_NATIVE_TEST_VIDEO": str(video)}

    assert resolve_media(env) == str(video)
    assert not native_acceptance_requested(env)
    assert live_run_blockers(env), "medya varken opt-in'siz kosum istendi"


@pytest.mark.parametrize("value", ["0", "", "true", "yes", "2", "1 "])
def test_an_invalid_opt_in_value_does_not_request_the_live_run(value):
    assert not native_acceptance_requested({OPT_IN_VARIABLE: value})


def test_the_live_run_is_requested_only_with_opt_in_and_media(tmp_path):
    video = tmp_path / "ornek.mp4"
    video.write_bytes(b"x")
    env = {OPT_IN_VARIABLE: "1", "MLC_NATIVE_TEST_VIDEO": str(video)}

    assert native_acceptance_requested(env)
    assert live_run_blockers(env) == []


def test_opt_in_without_media_still_blocks():
    blockers = live_run_blockers({OPT_IN_VARIABLE: "1"})

    assert any("medya" in b for b in blockers), blockers


def test_the_default_environment_skips_the_native_test():
    """Varsayilan tam pytest kosumunda canli test CALISMAZ."""
    assert live_run_blockers({}), "bos ortamda canli kosum istenmis sayildi"


def test_the_opt_in_variable_is_specific_to_this_acceptance():
    """`MLC_NATIVE_SMOKE` baska native testleri de acar; kullanilmaz."""
    assert OPT_IN_VARIABLE == "MLC_NATIVE_SHUTDOWN_ACCEPTANCE"
    assert not native_acceptance_requested({"MLC_NATIVE_SMOKE": "1"})


# =====================================================================
# 2d. Medya turu fail-closed
# =====================================================================

@pytest.mark.parametrize("name", ["ornek.py", "ornek.txt", "ornek.wav",
                                  "ornek", "ornek.mkv.txt"])
def test_a_non_video_file_is_not_valid_media(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"x")

    assert not is_supported_media(str(path))
    assert resolve_media({"MLC_NATIVE_TEST_VIDEO": str(path)}) == ""


def test_the_audited_python_file_is_no_longer_accepted_as_media():
    """OLCULEN FAIL-OPEN: `MLC_NATIVE_TEST_VIDEO=<...>.py` gecerli sayildi."""
    assert not is_supported_media(__file__)
    assert resolve_media({"MLC_NATIVE_TEST_VIDEO": __file__}) == ""


def test_a_directory_is_not_valid_media(tmp_path):
    assert not is_supported_media(str(tmp_path))


def test_a_missing_path_is_not_valid_media(tmp_path):
    assert not is_supported_media(str(tmp_path / "yok.mkv"))
    assert not is_supported_media("")


@pytest.mark.parametrize("name", ["ornek.MKV", "ornek.Mp4"])
def test_the_extension_check_is_case_insensitive(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"x")

    assert is_supported_media(str(path))


def test_a_folder_scan_skips_non_video_files(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x")
    (tmp_path / "b.txt").write_bytes(b"x")
    (tmp_path / "c.mp4").write_bytes(b"x")

    assert resolve_media({"MLC_NATIVE_VIDEO_DIR": str(tmp_path)}) == \
        str(tmp_path / "c.mp4")


def test_an_invalid_direct_path_does_not_silently_fall_back(tmp_path):
    """Yanlis dosya verildiginde SESSIZCE klasore dusulmez."""
    (tmp_path / "gercek.mkv").write_bytes(b"x")
    bad = tmp_path / "ornek.wav"
    bad.write_bytes(b"x")

    assert resolve_media({"MLC_NATIVE_TEST_VIDEO": str(bad),
                          "MLC_NATIVE_VIDEO_DIR": str(tmp_path)}) == ""


class SubprocessSentinel:
    """Cagrilirsa testi ANINDA kirmizi yapan nobetci.

    OLCULEN IHLAL (18 Agustos 2026): medya turu denetimini notrlestiren
    bir mutasyon kosumu gercek child'i yaklasik 26,8 sn boyunca
    BASLATTI. Native sinirini olcen testler bir daha gercek surec
    baslatmaz; `subprocess.run` bu nobetciyle degistirilir.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError(
            f"BEKLENMEYEN subprocess cagrisi: {args!r}")


@pytest.fixture
def no_subprocess(monkeypatch):
    """Bu testler HICBIR surec baslatmaz."""
    sentinel = SubprocessSentinel()
    monkeypatch.setattr(acceptance.subprocess, "run", sentinel)
    return sentinel


@pytest.mark.parametrize("video", ["", "yok.mkv", __file__, "ornek.wav"])
def test_the_runner_never_launches_the_child_for_invalid_media(video,
                                                               no_subprocess):
    problems, detail = run_native_shutdown(video)

    assert any("gecerli gercek medya degil" in p for p in problems), problems
    assert detail["returncode"] is None, "gecersiz medyada child BASLATILDI"
    assert detail["stdout"] == "" and detail["stderr"] == ""
    assert no_subprocess.calls == [], "surec baslatildi"


def valid_video(tmp_path, name="ornek.mkv"):
    path = tmp_path / name
    path.write_bytes(b"x")
    return str(path)


def test_valid_media_without_opt_in_never_reaches_subprocess(tmp_path,
                                                             no_subprocess):
    """ASIL KIRMIZI: opt-in YALNIZ pytest dugumunde denetleniyordu.

    `run_native_shutdown()` dogrudan cagrildiginda gecerli bir `.mkv` ile
    ACIK IZIN OLMADAN surec baslatabiliyordu.
    """
    problems, detail = run_native_shutdown(valid_video(tmp_path), env={})

    assert no_subprocess.calls == [], "izin yokken surec baslatildi"
    assert any("ISTENMEDI" in p for p in problems), problems
    assert detail["returncode"] is None
    assert detail["stdout"] == "" and detail["stderr"] == ""
    assert detail["media_before"] is not None, "medya stat raporlanmadi"
    assert detail["media_before"] == detail["media_after"]


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "2", "1 ", "TRUE"])
def test_an_invalid_opt_in_value_never_reaches_subprocess(tmp_path, value,
                                                          no_subprocess):
    problems, detail = run_native_shutdown(
        valid_video(tmp_path), env={OPT_IN_VARIABLE: value})

    assert no_subprocess.calls == [], (value, "surec baslatildi")
    assert any("ISTENMEDI" in p for p in problems), problems
    assert detail["returncode"] is None


def test_opt_in_with_invalid_media_never_reaches_subprocess(tmp_path,
                                                            no_subprocess):
    bad = tmp_path / "ornek.wav"
    bad.write_bytes(b"x")

    problems, detail = run_native_shutdown(
        str(bad), env={OPT_IN_VARIABLE: "1"})

    assert no_subprocess.calls == []
    assert any("gecerli gercek medya degil" in p for p in problems), problems


def test_opt_in_with_valid_media_does_reach_subprocess(tmp_path, monkeypatch):
    """Kapi ACIK oldugunda cagri subprocess sinirina ULASIR.

    Gercek child BASLATILMAZ: sahte bir `CompletedProcess` dondurulur.
    """
    video = valid_video(tmp_path)
    calls = []

    class FakeCompleted:
        returncode = 0
        stdout = GOOD_STDOUT.encode("utf-8")
        stderr = b""

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeCompleted()

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    problems, detail = run_native_shutdown(
        video, env={OPT_IN_VARIABLE: "1"})

    assert len(calls) == 1, "subprocess sinirina ULASILMADI"
    assert problems == [], problems
    assert detail["returncode"] == 0
    assert detail["raw_stdout"] == GOOD_STDOUT.encode("utf-8")
    assert detail["raw_stderr"] == b""
    assert detail["media_before"] == detail["media_after"]

    # Child ortami ENJEKTE EDILEN ortamdan turer; global ortam kullanilmaz.
    child_env = calls[0][1]["env"]
    assert child_env[OPT_IN_VARIABLE] == "1"
    assert child_env["MLC_NATIVE_TEST_VIDEO"] == os.path.abspath(video)
    assert "QT_QPA_PLATFORM" not in child_env


def test_the_injected_environment_does_not_leak_into_the_process(tmp_path,
                                                                 monkeypatch):
    """Enjekte edilen ortam `os.environ`i DEGISTIRMEZ."""
    monkeypatch.delenv(OPT_IN_VARIABLE, raising=False)
    monkeypatch.setattr(acceptance.subprocess, "run",
                        lambda *a, **k: SubprocessSentinel()(*a, **k))

    with pytest.raises(AssertionError):
        run_native_shutdown(valid_video(tmp_path),
                            env={OPT_IN_VARIABLE: "1"})

    assert OPT_IN_VARIABLE not in os.environ
    assert "MLC_NATIVE_TEST_VIDEO" not in os.environ


def test_a_direct_call_is_as_safe_as_the_pytest_node(tmp_path, no_subprocess):
    """Kapi pytest dugumunde DEGIL, gercek subprocess sinirindadir."""
    assert live_run_blockers({}), "pytest dugumu kapisi calismiyor"

    problems, _ = run_native_shutdown(valid_video(tmp_path), env={})

    assert problems and no_subprocess.calls == []


def test_the_gate_is_checked_before_the_subprocess_call_in_source():
    """Kaynak sirasi: izin denetimi `subprocess.run`dan ONCE."""
    gate = os.path.join(os.path.dirname(CHILD), "native_shutdown_acceptance.py")
    with open(gate, encoding="utf-8") as handle:
        source = handle.read()

    body = source[source.index("def run_native_shutdown("):]
    check_at = body.index("native_acceptance_requested(")
    run_at = body.index("subprocess.run(")

    assert check_at < run_at, "izin denetimi subprocess cagrisindan SONRA"


def test_the_sentinel_itself_catches_a_launch(no_subprocess):
    """Nobetci gercekten kirmizi uretiyor mu? (bos olmadiginin kaniti)"""
    with pytest.raises(AssertionError, match="BEKLENMEYEN subprocess"):
        acceptance.subprocess.run(["python", "-c", "pass"])

    assert len(no_subprocess.calls) == 1


def test_the_runner_reports_an_unreadable_media_without_a_traceback(
        tmp_path, no_subprocess):
    """Silinmis/okunamayan medya traceback DEGIL, kontrollu FAIL uretir."""
    video = tmp_path / "ornek.mkv"
    video.write_bytes(b"x")
    path = str(video)
    video.unlink()

    # Uzanti dogru ama dosya YOK: child baslatilmadan kontrollu FAIL.
    problems, detail = run_native_shutdown(path)

    assert problems and detail["returncode"] is None
    assert all(isinstance(p, str) for p in problems)
    assert no_subprocess.calls == [], "surec baslatildi"


def test_media_stat_returns_none_instead_of_raising(tmp_path):
    assert media_stat(str(tmp_path / "yok.mkv")) is None


# =====================================================================
# 3. RESULTS satiri
# =====================================================================

@pytest.mark.parametrize("results", [
    "RESULTS: failures=media_not_ready stop=1 terminate=1",
    "RESULTS: failures=close_not_accepted stop=1 terminate=1",
    "RESULTS: failures=none stop=0 terminate=1",
    "RESULTS: failures=none stop=2 terminate=1",
    "RESULTS: failures=none stop=1 terminate=0",
    "RESULTS: failures=none stop=1 terminate=2",
    "RESULTS: failures=none",
])
def test_a_results_line_other_than_the_expected_one_is_rejected(results):
    broken = GOOD_STDOUT.replace(EXPECTED_RESULTS, results)
    assert broken != GOOD_STDOUT

    problems = evaluate_shutdown_result(0, broken, "")

    assert any("RESULTS" in p for p in problems), problems


def test_a_missing_results_line_is_rejected():
    without = GOOD_STDOUT.replace(EXPECTED_RESULTS + "\n", "")

    assert any("RESULTS satiri yok" in p
               for p in evaluate_shutdown_result(0, without, ""))


def test_a_duplicated_results_line_is_rejected():
    doubled = GOOD_STDOUT + EXPECTED_RESULTS + "\n"

    assert any("RESULTS 2 kez" in p
               for p in evaluate_shutdown_result(0, doubled, ""))


# =====================================================================
# 4. Kodlama, timeout ve medya degismezligi
# =====================================================================

def test_undecodable_bytes_cannot_hide_a_fatal_ascii_pattern():
    raw = b"\xff\xfe bozuk \x9e\nWindows fatal exception: code 0xe24c4a02\n"

    problems = evaluate_shutdown_result(0, GOOD_STDOUT.encode("utf-8"), raw)

    assert any("Windows fatal exception" in p for p in problems), problems


def test_the_evaluator_accepts_bytes_for_both_streams():
    assert evaluate_shutdown_result(0, GOOD_STDOUT.encode("utf-8"), b"") == []


def test_a_timeout_is_a_controlled_failure():
    problems = timeout_problems(180)

    assert problems and "timeout" in problems[0].lower(), problems


@pytest.mark.parametrize("field, value", [
    ("size", 999), ("mtime_ns", 1), ("path", "C:\\media\\baska.mkv")])
def test_a_changed_media_file_fails(field, value):
    after = dict(MEDIA_BEFORE, **{field: value})

    problems = media_stat_problems(MEDIA_BEFORE, after)

    assert any(field in p for p in problems), problems


def test_an_untouched_media_file_passes():
    assert media_stat_problems(MEDIA_BEFORE, dict(MEDIA_BEFORE)) == []


def test_a_missing_media_stat_is_not_silently_accepted():
    assert media_stat_problems(MEDIA_BEFORE, None)
    assert media_stat_problems(None, MEDIA_BEFORE)


def test_media_stat_is_read_only_and_carries_no_hash():
    """Buyuk dosyanin hash'i hesaplanmaz; dosya yalnizca `stat` edilir."""
    info = media_stat(__file__)

    assert set(info) == {"path", "size", "mtime_ns"}
    assert info["size"] > 0


# =====================================================================
# 5. Bu dosya urun kodu veya gercek MPV YUKLEMEZ
# =====================================================================

@pytest.mark.parametrize("module", ["mpv", "PyQt6.QtWidgets", "app.player"])
def test_the_deterministic_contract_loads_neither_qt_nor_libmpv(module):
    """Degerlendirici saftir: import etkisi olculur, surec geneli DEGIL."""
    before = sys.modules.get(module)

    import importlib
    importlib.reload(importlib.import_module("native_shutdown_acceptance"))

    assert sys.modules.get(module) is before, (
        f"degerlendirici modulunun importu {module} durumunu degistirdi")


def test_the_child_is_the_existing_product_path_child():
    """Yeni child YAZILMADI; mevcut urun-yolu child'i kullanilir."""
    assert os.path.basename(CHILD) == "native_player_shutdown_child.py"
    assert os.path.isfile(CHILD)


def test_the_grammar_and_required_list_come_from_one_source():
    assert REQUIRED_MARKERS == tuple(name for name, _ in MARKER_GRAMMAR)


# =====================================================================
# 6. Child kaynak sozlesmesi (native kosum YOK)
# =====================================================================

def read_child():
    with open(CHILD, encoding="utf-8") as handle:
        return handle.read()


def test_the_child_enables_faulthandler_before_qt_and_mpv():
    """Gorunurluk, PyQt/mpv/app.player IMPORTUNDAN ONCE acilmali."""
    source = read_child()

    enabled_at = source.find("faulthandler.enable(")
    assert enabled_at != -1, "child faulthandler'i etkinlestirmiyor"
    call = source[enabled_at:source.index(")", enabled_at) + 1]
    assert "all_threads=True" in call, (
        f"yalniz ana thread izleniyor: {call!r}; native istisna MPV olay "
        "thread'inde olusuyor")

    player_imports = ("from app.player import", "import app.player as")
    player_import = next((item for item in player_imports if item in source),
                         None)
    assert player_import is not None, "app.player importu yok"

    for later in ("from PyQt6", player_import):
        at = source.find(later)
        assert at != -1, later
        assert enabled_at < at, (
            f"faulthandler {later!r} importundan SONRA aciliyor")


def test_the_child_marks_that_faulthandler_is_enabled():
    assert "MARK_FAULTHANDLER_ENABLED" in read_child()


def test_the_child_keeps_stderr_as_the_faulthandler_target():
    """Hedef acikca stderr olmali; baska dosyaya yonlendirilmemeli."""
    source = read_child()

    call_at = source.index("faulthandler.enable(")
    call = source[call_at:source.index(")", call_at) + 1]

    assert "file=sys.stderr" in call, (
        f"faulthandler hedefi acikca stderr degil: {call!r}")


def test_the_child_never_starts_the_shutdown_itself():
    """Kapanis YALNIZ urun yolundan: child stop()/terminate() CAGIRMAZ."""
    source = read_child()

    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for forbidden in ("player.mpv_player.stop(",
                          "player.mpv_player.terminate("):
            assert forbidden not in stripped, (
                f"child kapanisi kendisi baslatiyor: {stripped!r}")

    assert "player.close()" in source, "kapanis urun yolundan baslamiyor"


def test_the_child_counts_surviving_mpv_threads_after_the_event_loop():
    source = read_child()

    # Docstring'de de gecdigi icin ARANAN sey gercek `mark()` cagrisidir.
    exec_at = source.find("exec_code = app.exec()")
    threads_at = source.find('mark("MARK_THREADS_AFTER"')

    assert exec_at != -1 and threads_at != -1, (exec_at, threads_at)
    assert exec_at < threads_at, (
        "thread sayimi `app.exec()` donusunden ONCE yapiliyor")


def test_the_child_still_exits_like_the_product():
    """Urun politikasi: `os._exit(ret)` — normal finalizasyona girilmez."""
    source = read_child()

    assert "os._exit(exit_code)" in source
    assert "flush=True" in source


def test_the_call_recorder_adds_no_extra_reference_to_the_product_object():
    """Vekil nesne YOK: olcum urunun MPV nesnesine referans eklemez."""
    source = read_child()

    assert "mpv_module.MPV.stop = recording_stop" in source
    assert "mpv_module.MPV.terminate = recording_terminate" in source
    assert "return real_stop(self" in source
    assert "return real_terminate(self" in source


# =====================================================================
# 7. GERCEK canli kabul — TEK kosum, medya ortami gerektirir
# =====================================================================

def test_the_product_shutdown_path_survives_a_real_run():
    """TEK gercek kabul: gercek pencere, gercek medya, urun kapanis yolu.

    ACIK opt-in ZORUNLUDUR: yalnizca medya degiskeninin tanimli olmasi bu
    testi baslatmaz (`MLC_NATIVE_SHUTDOWN_ACCEPTANCE=1`). Basarisiz olursa
    TEKRAR CALISTIRILMAZ; kanit oldugu gibi raporlanir.
    """
    blockers = live_run_blockers()
    if blockers:
        pytest.skip("canli kabul kosulmadi: " + "; ".join(blockers))

    video = resolve_media()
    problems, detail = run_native_shutdown(video)

    assert not problems, (
        "URUN KAPANIS YOLU KABULU BASARISIZ:\n  - "
        + "\n  - ".join(problems)
        + f"\n--- exit: {detail['returncode']}"
        + f"\n--- STDOUT ---\n{detail['stdout']}"
        + f"\n--- STDERR ---\n{detail['stderr']}"
        + f"\n--- MEDYA: {detail['media_before']} -> {detail['media_after']}")
