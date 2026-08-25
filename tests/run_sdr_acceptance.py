# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Exact fingerprintli BT.709 fixture icin tek child native SDR runner'i."""
import csv
import hashlib
import json
import os
import subprocess
import sys
import time


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)
CHILD = os.path.join(TESTS_DIR, "native_sdr_probe_child.py")
VERIFIER = os.path.join(ROOT, "scripts", "verify_video_format_media.py")
MANIFEST = os.path.join(ROOT, "docs", "VIDEO_FORMAT_MEDIA_MANIFEST.json")
sys.path.insert(0, TESTS_DIR)

from hdr_probe_contract import parse_dxdiag_bytes  # noqa: E402
from native_media_contract import is_supported_media  # noqa: E402
from sdr_probe_contract import (SDR_CHILD_TIMEOUT_SECONDS,  # noqa: E402
                                CURRENT_PROFILE, DISPLAY_MODES,
                                HDR_DISPLAY_MODE, PROFILES,
                                SDR_DISPLAY_MODE,
                                display_problems, report_problems)


def file_identity(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    stat = os.stat(path)
    return {"size": stat.st_size, "sha256": digest.hexdigest()}


def process_ids():
    completed = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=20,
        check=False)
    found = set()
    for row in csv.reader(completed.stdout.splitlines()):
        if len(row) < 2 or row[0].lower() not in (
                "mlc player.exe", "python.exe", "pythonw.exe"):
            continue
        try:
            found.add(int(row[1].replace(",", "")))
        except ValueError:
            pass
    return found


def windows_display_colorspace(workspace, suffix):
    target = os.path.join(workspace, f"dxdiag-{suffix}.txt")
    completed = subprocess.run(
        [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                      "System32", "dxdiag.exe"),
         "/dontskip", "/whql:off", "/t", target],
        capture_output=True, timeout=45, check=False)
    deadline = time.monotonic() + 20
    while not os.path.isfile(target) and time.monotonic() < deadline:
        time.sleep(0.1)
    if completed.returncode != 0 or not os.path.isfile(target):
        return ""
    with open(target, "rb") as handle:
        raw = handle.read()
    return parse_dxdiag_bytes(raw)


def parse_child_report(text):
    found = [line.split("=", 1)[1] for line in text.splitlines()
             if line.startswith("SDR_REPORT_JSON=")]
    if len(found) != 1:
        return {}, [f"SDR_REPORT_JSON sayisi {len(found)}; beklenen 1"]
    try:
        return json.loads(found[0]), []
    except json.JSONDecodeError as exc:
        return {}, [f"SDR_REPORT_JSON gecersiz: {exc}"]


def required_path(name):
    value = os.environ.get(name, "")
    return os.path.abspath(value) if value else ""


def verify_fingerprint(video):
    command = [
        sys.executable, VERIFIER,
        "--manifest", MANIFEST,
        "--record", required_path("MLC_SDR_FINGERPRINT_RECORD"),
        "--media", video,
        "--ffprobe", required_path("MLC_SDR_FFPROBE"),
        "--generator", required_path("MLC_SDR_GENERATOR"),
        "--probe-artifact", required_path("MLC_SDR_PROBE_ARTIFACT"),
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def main():
    if os.environ.get("MLC_NATIVE_SDR_ACCEPTANCE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    video = required_path("MLC_SDR_TEST_VIDEO")
    profile = os.environ.get("MLC_SDR_PROBE_PROFILE", CURRENT_PROFILE)
    display_mode = os.environ.get(
        "MLC_SDR_DISPLAY_MODE", SDR_DISPLAY_MODE)
    evidence_dir = required_path("MLC_SDR_EVIDENCE_DIR")
    if not is_supported_media(video):
        print("BLOCKED: MLC_SDR_TEST_VIDEO gecerli .mkv/.mp4 olmali", flush=True)
        return 2
    if profile not in PROFILES:
        print("BLOCKED: MLC_SDR_PROBE_PROFILE gecersiz", flush=True)
        return 2
    if display_mode not in DISPLAY_MODES:
        print("BLOCKED: MLC_SDR_DISPLAY_MODE gecersiz", flush=True)
        return 2
    if not evidence_dir or os.path.exists(evidence_dir):
        print("BLOCKED: yeni ve exact MLC_SDR_EVIDENCE_DIR gerekli", flush=True)
        return 2
    os.makedirs(evidence_dir)
    log_path = os.path.join(evidence_dir, "native-sdr-child.log")
    report_path = os.path.join(evidence_dir, "native-sdr-report.json")
    print(f"LIVE_LOG={log_path}", flush=True)
    print(f"REPORT={report_path}", flush=True)

    fingerprint_exit, fingerprint_stdout, fingerprint_stderr = (
        verify_fingerprint(video))
    if fingerprint_exit != 0 or "MEDIA_FINGERPRINT_OK " not in fingerprint_stdout:
        payload = {"fingerprint_exit": fingerprint_exit,
                   "fingerprint_stdout": fingerprint_stdout,
                   "fingerprint_stderr": fingerprint_stderr,
                   "problems": ["exact medya fingerprint kapisi gecmedi"]}
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        print("SDR_NATIVE FAIL fingerprint", flush=True)
        return 1
    fingerprint = json.loads(
        fingerprint_stdout.split("MEDIA_FINGERPRINT_OK ", 1)[1].splitlines()[0])

    runtime_dll = os.path.join(ROOT, "bin", "mpv-2.dll")
    if not os.path.isfile(runtime_dll):
        print("BLOCKED: bin/mpv-2.dll bulunamadi", flush=True)
        return 2
    media_before = file_identity(video)
    runtime_before = file_identity(runtime_dll)

    colorspace_before = windows_display_colorspace(evidence_dir, "before")
    print(f"WINDOWS_COLORSPACE_BEFORE={colorspace_before or 'UNKNOWN'}", flush=True)
    baseline_pids = process_ids()
    env = dict(os.environ)
    env.update({
        "MLC_NATIVE_PROJECT_ROOT": ROOT,
        "MLC_NATIVE_SETTINGS": os.path.join(evidence_dir, "settings"),
        "MLC_SDR_PROBE_PROFILE": profile,
    })
    started = time.monotonic()
    timed_out = False
    with open(log_path, "w", encoding="utf-8", buffering=1) as log_handle:
        proc = subprocess.Popen(
            [sys.executable, CHILD], cwd=ROOT, env=env, stdout=log_handle,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace")
        try:
            _, stderr = proc.communicate(timeout=SDR_CHILD_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            _, stderr = proc.communicate(timeout=10)
    elapsed = round(time.monotonic() - started, 3)
    with open(log_path, encoding="utf-8", errors="replace") as handle:
        stdout = handle.read()
    report, parse_problems = parse_child_report(stdout)
    report.update({
        "exit_code": proc.returncode,
        "mark_done": "MARK_DONE" in stdout,
        "leaked_processes": sorted(process_ids() - baseline_pids),
        "stderr": stderr,
        "timed_out": timed_out,
        "elapsed_s": elapsed,
    })
    colorspace_after = windows_display_colorspace(evidence_dir, "after")
    media_after = file_identity(video)
    runtime_after = file_identity(runtime_dll)
    problems = (parse_problems + report_problems(report, display_mode)
                + display_problems(
                    colorspace_before, colorspace_after, display_mode))
    if media_after != media_before:
        problems.append("exact SDR medya kimligi kosumda degisti")
    if runtime_after != runtime_before:
        problems.append("exact libmpv runtime kimligi kosumda degisti")
    payload = {
        "scenario": ("VF-CORE-02-partial-native-smoke"
                     if display_mode == HDR_DISPLAY_MODE
                     else "VF-CORE-01-partial-native-smoke"),
        "profile": profile,
        "display_mode": display_mode,
        "fingerprint": fingerprint,
        "windows_colorspace_before": colorspace_before,
        "windows_colorspace_after": colorspace_after,
        "media_before": media_before,
        "media_after": media_after,
        "runtime_before": runtime_before,
        "runtime_after": runtime_after,
        "report": report,
        "problems": problems,
    }
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
    status = "PASS" if not problems else "FAIL"
    print(f"SDR_NATIVE {status} elapsed={elapsed} problems={problems}", flush=True)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
