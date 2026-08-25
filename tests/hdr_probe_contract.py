# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Test-only HDR probe profilleri ve saf fail-closed degerlendirme."""
import re


CURRENT_PROFILE = "current_gpu"
CANDIDATE_PROFILE = "gpu_next_d3d11"
PROFILES = (CURRENT_PROFILE, CANDIDATE_PROFILE)
HDR_CHILD_TIMEOUT_SECONDS = 60

_TEN_BIT = re.compile(
    r"(?:^|[^0-9])(?:p010|p012|p016|rgb10|x2rgb10|rgba10|"
    r"yuv\d+p10(?:le|be)?)(?:$|[^0-9])",
    re.IGNORECASE,
)
_PQ = {"pq", "smpte2084", "st2084"}
_HLG = {"hlg", "arib-std-b67"}
_ALLOWED_STDERR_PREFIXES = ("QThreadStorage:",)


def hdr_probe_config(base_config, profile):
    """Urun sozlugunu mutate etmeden child'a ozel tani kopyasi kur."""
    if profile not in PROFILES:
        raise ValueError(f"bilinmeyen HDR probe profili: {profile!r}")
    configured = dict(base_config)
    configured.update({"ao": "null", "mute": "yes"})
    if profile == CANDIDATE_PROFILE:
        configured.update({
            "vo": "gpu-next",
            "gpu_api": "d3d11",
            "gpu_context": "d3d11",
            "target_colorspace_hint": "auto",
            "target_colorspace_hint_mode": "target",
        })
    return configured


def _text(mapping, key):
    return str((mapping or {}).get(key, "") or "").strip().lower()


def is_ten_bit_pixel_format(value):
    return bool(_TEN_BIT.search(str(value or "")))


def params_are_ten_bit(params):
    params = params or {}
    return (is_ten_bit_pixel_format(params.get("pixelformat")) or
            is_ten_bit_pixel_format(params.get("hw-pixelformat")))


def parse_dxdiag_colorspace(text):
    """DxDiag metninden etkin ilk ekranin DXGI renk uzayini ayikla."""
    match = re.search(r"^\s*Display Color Space:\s*(\S+)\s*$",
                      str(text or ""), flags=re.MULTILINE)
    return match.group(1) if match else ""


def parse_dxdiag_bytes(raw):
    """DxDiag'in BOM'suz Windows ANSI veya Unicode ciktisini ayikla."""
    for encoding in ("utf-16", "utf-8-sig", "mbcs", "cp1254", "cp1252"):
        try:
            text = raw.decode(encoding)
        except (LookupError, UnicodeError):
            continue
        colorspace = parse_dxdiag_colorspace(text)
        if colorspace:
            return colorspace
    return ""


def classify_input(params):
    """Decoder parametrelerini HDR10/HLG/SDR veya gecersiz HDR diye ayir."""
    primaries = _text(params, "primaries")
    gamma = _text(params, "gamma")
    ten_bit = params_are_ten_bit(params)
    hdr_transfer = gamma in _PQ or gamma in _HLG
    if primaries == "bt.2020" and gamma in _PQ and ten_bit:
        return "hdr10"
    if primaries == "bt.2020" and gamma in _HLG and ten_bit:
        return "hlg"
    if hdr_transfer or primaries == "bt.2020":
        return "invalid_hdr"
    return "sdr"


def output_problems(target, expected_hdr):
    """VO hedef parametreleri beklenen HDR10 swapchain sinyaline uyuyor mu?"""
    target = target or {}
    problems = []
    if expected_hdr:
        if _text(target, "primaries") != "bt.2020":
            problems.append(
                f"target primaries bt.2020 degil: {target.get('primaries')!r}")
        if _text(target, "gamma") not in _PQ:
            problems.append(f"target gamma PQ degil: {target.get('gamma')!r}")
        if not params_are_ten_bit(target):
            problems.append(
                "target pixelformat/hw-pixelformat 10-bit degil: "
                f"{target.get('pixelformat')!r}/"
                f"{target.get('hw-pixelformat')!r}")
    return problems


def _stderr_problems(stderr):
    text = (stderr.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes) else str(stderr or ""))
    problems = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(_ALLOWED_STDERR_PREFIXES):
            problems.append(f"beklenmeyen stderr: {stripped}")
    return problems


def report_problems(report, expected_hdr):
    """Tek child raporunu exit/marker/renk/kapanis/sizinti ile degerlendir."""
    report = report or {}
    problems = []
    if report.get("exit_code") != 0:
        problems.append(f"child exit 0 degil: {report.get('exit_code')!r}")
    if report.get("mark_done") is not True:
        problems.append("MARK_DONE eksik")
    if report.get("captured") is not True:
        problems.append("HDR ozellikleri yakalanmadi")
    if report.get("input_class") not in ("hdr10", "hlg"):
        problems.append(
            f"girdi dogrulanmis HDR degil: {report.get('input_class')!r}")
    problems.extend(output_problems(report.get("target"), expected_hdr))
    if not str(report.get("hwdec_current") or "").strip():
        problems.append("hwdec-current yok")
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
