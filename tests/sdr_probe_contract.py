# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Test-only SDR native smoke icin saf, fail-closed degerlendirme."""

from native_windows_exception_contract import (
    complete_luajit_faulthandler_reports,
)


SDR_CHILD_TIMEOUT_SECONDS = 60
SDR_COLORSPACE = "DXGI_COLOR_SPACE_RGB_FULL_G22_NONE_P709"
CURRENT_PROFILE = "current_product"
NO_LATENCY_HACKS_PROFILE = "no_latency_hacks"
PROFILES = (CURRENT_PROFILE, NO_LATENCY_HACKS_PROFILE)
MAX_VISUAL_HOLD_SECONDS = 15.0
_ALLOWED_STDERR_PREFIXES = ("QThreadStorage:",)


def sdr_probe_config(base_config, profile):
    """Urun sozlugunu mutate etmeden test-only profil kopyasi kur."""
    if profile not in PROFILES:
        raise ValueError(f"bilinmeyen SDR probe profili: {profile!r}")
    configured = dict(base_config)
    if profile == NO_LATENCY_HACKS_PROFILE:
        configured["video_latency_hacks"] = "no"
    return configured


def visual_hold_seconds(value):
    """Insan ramp bakisi icin bos/0 veya en fazla 15 saniye kabul et."""
    if value in (None, ""):
        return 0.0
    try:
        seconds = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("gecersiz visual hold") from error
    if not 0 <= seconds <= MAX_VISUAL_HOLD_SECONDS:
        raise ValueError("visual hold 0..15 saniye olmali")
    return seconds


def _text(mapping, key):
    return str((mapping or {}).get(key, "") or "").strip().lower()


def classify_sdr_input(params):
    """Native decoder parametrelerini yalniz BT.709 SDR ise kabul et."""
    params = params or {}
    primaries = _text(params, "primaries")
    gamma = _text(params, "gamma")
    if primaries == "bt.709" and gamma in ("bt.1886", "bt.709"):
        return "sdr_bt709"
    return "other"


def display_problems(before, after):
    problems = []
    if before != SDR_COLORSPACE:
        problems.append(f"Windows SDR/P709 renk uzayi yok: {before!r}")
    if after != before:
        problems.append(
            f"Windows renk uzayi kosumda degisti: {before!r} -> {after!r}")
    return problems


def _stderr_problems(stderr):
    text = (stderr.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes) else str(stderr or ""))
    if complete_luajit_faulthandler_reports(text):
        return []
    problems = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(_ALLOWED_STDERR_PREFIXES):
            problems.append(f"beklenmeyen stderr: {stripped}")
    return problems


def report_problems(report):
    """Child raporunu oynatma, drop, kapanis ve sizintiyle degerlendir."""
    report = report or {}
    problems = []
    if report.get("profile") not in PROFILES:
        problems.append(f"probe profili gecersiz: {report.get('profile')!r}")
    if report.get("timed_out") is True:
        problems.append("child timeout")
    if report.get("exit_code") != 0:
        problems.append(f"child exit 0 degil: {report.get('exit_code')!r}")
    if report.get("mark_done") is not True:
        problems.append("MARK_DONE eksik")
    if report.get("captured") is not True:
        problems.append("SDR ozellikleri yakalanmadi")
    if report.get("input_class") != "sdr_bt709":
        problems.append(
            f"girdi BT.709 SDR degil: {report.get('input_class')!r}")
    target = report.get("target") or {}
    if _text(target, "primaries") != "bt.709":
        problems.append(
            f"target primaries bt.709 degil: {target.get('primaries')!r}")
    if _text(target, "gamma") not in ("bt.1886", "bt.709"):
        problems.append(f"target gamma SDR degil: {target.get('gamma')!r}")
    duration = report.get("duration")
    if not isinstance(duration, (int, float)) or not 2.8 <= duration <= 3.2:
        problems.append(f"duration exact fixture ile uyumsuz: {duration!r}")
    progress = report.get("max_time_pos")
    if not isinstance(progress, (int, float)) or progress <= 0.25:
        problems.append(f"time_pos ilerlemedi: {progress!r}")
    drops = report.get("frame_drops") or {}
    for name in ("decoder-frame-drop-count", "frame-drop-count"):
        value = drops.get(name)
        if not isinstance(value, (int, float)):
            problems.append(f"frame drop sayaci okunamadi: {name}={value!r}")
        elif value != 0:
            problems.append(f"frame drop sifir degil: {name}={value!r}")
    if report.get("stop_calls") != 1 or report.get("terminate_calls") != 1:
        problems.append("stop/terminate sayisi 1/1 degil")
    if report.get("call_order") != ["stop", "terminate"]:
        problems.append(f"kapanis sirasi yanlis: {report.get('call_order')!r}")
    if report.get("close_accepted") is not True:
        problems.append("kanonik player.close() kabul edilmedi")
    if report.get("cursor_restored") is not True:
        problems.append("imlec geri yuklenmedi")
    if report.get("leaked_processes"):
        problems.append(f"surec sizintisi: {report.get('leaked_processes')!r}")
    problems.extend(_stderr_problems(report.get("stderr")))
    return problems
