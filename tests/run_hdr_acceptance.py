# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in HDR A/B runner: mevcut gpu ve gpu-next/D3D11 profilleri."""
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)
CHILD = os.path.join(TESTS_DIR, "native_hdr_probe_child.py")
sys.path.insert(0, TESTS_DIR)

from hdr_probe_contract import (CANDIDATE_PROFILE, CURRENT_PROFILE,  # noqa: E402
                                HDR_CHILD_TIMEOUT_SECONDS,
                                parse_dxdiag_bytes,
                                report_problems)
from native_media_contract import is_supported_media  # noqa: E402


HDR_COLORSPACE = "DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020"


def file_identity(path, include_sha256=False):
    stat = os.stat(path)
    identity = {"path": os.path.abspath(path), "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns}
    if include_sha256:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        identity["sha256"] = digest.hexdigest()
    return identity


def process_ids():
    completed = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=20,
        check=False)
    found = set()
    for row in csv.reader(completed.stdout.splitlines()):
        if len(row) < 2:
            continue
        if row[0].lower() not in ("mlc player.exe", "python.exe", "pythonw.exe"):
            continue
        try:
            found.add(int(row[1].replace(",", "")))
        except ValueError:
            pass
    return found


def windows_display_colorspace(workspace):
    """DxDiag'dan etkin DXGI renk uzayini okur; tahmin veya override yok."""
    target = os.path.join(workspace, "dxdiag.txt")
    if os.path.isfile(target):
        os.remove(target)
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


def parse_child_report(stdout):
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    found = []
    for line in stdout.splitlines():
        if line.startswith("HDR_REPORT_JSON="):
            found.append(line.split("=", 1)[1])
    if len(found) != 1:
        return {}, [f"HDR_REPORT_JSON sayisi {len(found)}; beklenen 1"]
    try:
        return json.loads(found[0]), []
    except json.JSONDecodeError as exc:
        return {}, [f"HDR_REPORT_JSON gecersiz: {exc}"]


def run_profile(profile, video, workspace, baseline_pids):
    env = dict(os.environ)
    env.update({
        "MLC_NATIVE_HDR_ACCEPTANCE": "1",
        "MLC_HDR_TEST_VIDEO": video,
        "MLC_HDR_PROBE_PROFILE": profile,
        "MLC_NATIVE_PROJECT_ROOT": ROOT,
        "MLC_NATIVE_SETTINGS": os.path.join(workspace, "settings", profile),
    })
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            [sys.executable, CHILD], cwd=ROOT, env=env,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=HDR_CHILD_TIMEOUT_SECONDS,
            check=False)
        exit_code = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    report, parse_problems = parse_child_report(stdout)
    leaked = sorted(process_ids() - baseline_pids)
    report.update({
        "exit_code": exit_code,
        "mark_done": "MARK_DONE" in stdout,
        "leaked_processes": leaked,
        "stderr": stderr,
        "timed_out": timed_out,
        "elapsed_s": round(time.monotonic() - started, 1),
    })
    problems = parse_problems + report_problems(
        report, expected_hdr=(profile == CANDIDATE_PROFILE))
    return {"profile": profile, "report": report, "problems": problems,
            "stdout": stdout}


def main():
    if os.environ.get("MLC_NATIVE_HDR_ACCEPTANCE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    video = os.environ.get("MLC_HDR_TEST_VIDEO", "")
    if not is_supported_media(video):
        print("BLOCKED: MLC_HDR_TEST_VIDEO gecerli .mkv/.mp4 olmali",
              flush=True)
        return 2

    media_before = file_identity(video)
    runtime_dll = os.path.join(ROOT, "bin", "mpv-2.dll")
    if not os.path.isfile(runtime_dll):
        print("BLOCKED: bin/mpv-2.dll bulunamadi", flush=True)
        return 2
    runtime_identity = file_identity(runtime_dll, include_sha256=True)

    workspace = tempfile.mkdtemp(prefix="mlc-hdr-probe-")
    colorspace = windows_display_colorspace(workspace)
    print(f"WINDOWS_COLORSPACE={colorspace or 'UNKNOWN'}", flush=True)
    if colorspace != HDR_COLORSPACE:
        print(f"BLOCKED: Windows HDR renk uzayi {HDR_COLORSPACE} degil",
              flush=True)
        return 2

    baseline_pids = process_ids()
    results = [run_profile(profile, video, workspace, baseline_pids)
               for profile in (CURRENT_PROFILE, CANDIDATE_PROFILE)]
    colorspace_after = windows_display_colorspace(workspace)
    media_after = file_identity(video)
    global_problems = []
    if colorspace_after != colorspace:
        global_problems.append(
            f"Windows renk uzayi kosumda degisti: {colorspace!r} -> "
            f"{colorspace_after!r}")
    if media_after != media_before:
        global_problems.append("HDR medya boyut/zaman kimligi degisti")
    report_path = os.path.join(workspace, "hdr-report.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump({"windows_colorspace_before": colorspace,
                   "windows_colorspace_after": colorspace_after,
                   "media_before": media_before, "media_after": media_after,
                   "runtime_dll": runtime_identity,
                   "global_problems": global_problems, "results": results},
                  handle, indent=2, ensure_ascii=False)
    for result in results:
        status = "PASS" if not result["problems"] else "FAIL"
        report = result["report"]
        print(f"PROFILE {result['profile']} {status} "
              f"elapsed={report.get('elapsed_s')} "
              f"input={report.get('input_class')} "
              f"target={report.get('target')} "
              f"problems={result['problems']}", flush=True)
    if global_problems:
        print(f"GLOBAL FAIL problems={global_problems}", flush=True)
    print(f"REPORT={report_path}", flush=True)
    return 0 if (not global_problems and
                 all(not item["problems"] for item in results)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
