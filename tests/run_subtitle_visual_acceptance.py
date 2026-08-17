# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı görünüm kabul runner'i: her senaryoyu AYRI child'da koşar.

- Her senaryo için sınırlı timeout ve takip edilen PID.
- Runner yalnız KENDİ başlattığı PID'leri sonlandırır.
- Timeout, eksik `MARK_DONE`, BLOCKED satırı veya sıfır olmayan exit
  ASLA PASS değildir (`classify_group` ile aynı sözleşme).
- Başlangıç fare konumu ve foreground penceresi runner tarafında da
  kaydedilir; child çökse bile geri yüklenir.

Normal `pytest` paketine dahil değildir (dosya adı `test_` ile başlamaz)
ve `MLC_NATIVE_SMOKE=1` gerektirir.
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_physical_acceptance import (classify_group,  # noqa: E402
                                     overall_exit_code)

CHILD = os.path.join(ROOT, "tests", "subtitle_visual_acceptance_child.py")
LOG_DIR = os.path.join(os.environ.get("TEMP", "."), "mlc_subtitle_visual_logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ASS tam ekran yolu zamanlama duyarlıdır; tek başarılı child kabul kanıtı
# değildir. Her iki DPI koşumu ayrı süreçlerde en az beş kez tekrarlanır.
ASS_REPEAT_COUNT = 5

user32 = ctypes.windll.user32
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]

# (sıra, senaryo, timeout_s, video_ortam_degiskeni)
SCENARIOS = [
    ("A", "a_text_color", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("B", "b_background_off", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("C", "c_background_on", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("D", "d_box_padding", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("E", "e_border_color", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("F", "f_border_size", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("G", "g_text_size", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("H", "h_position", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("I", "i_delay", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("J", "j_ass_override", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("K", "k_lifecycle", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("L", "l_bitmap", 720, "MLC_SUB_BITMAP_VIDEO"),
    ("M", "m_enter_key", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("N", "n_background_pick", 720, "MLC_NATIVE_TEST_VIDEO"),
    ("O", "o_band", 900, "MLC_NATIVE_TEST_VIDEO"),
    # %150 DPI GERÇEK kabulü AYRI child sürecinde çalışır
    # (`QT_SCALE_FACTOR` süreç başlamadan okunur). Ölçümler DPR'a göre
    # mantıksal piksele normalize edilir.
    ("O150", "o_band", 900, "MLC_NATIVE_TEST_VIDEO", {"QT_SCALE_FACTOR": "1.5"}),
    ("P", "p_ass_band", 900, "MLC_NATIVE_TEST_VIDEO"),
    ("P150", "p_ass_band", 900, "MLC_NATIVE_TEST_VIDEO",
     {"QT_SCALE_FACTOR": "1.5"}),
]


def cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def restore(cursor, hwnd):
    for attempt in range(1, 6):
        user32.SetCursorPos(int(cursor[0]), int(cursor[1]))
        if hwnd:
            user32.SetForegroundWindow(hwnd)
        time.sleep(0.25)
        now = cursor_pos()
        if abs(now[0] - cursor[0]) <= 2 and abs(now[1] - cursor[1]) <= 2:
            return True, now, attempt
    return False, cursor_pos(), 5


def parse_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.startswith("RESULT|"):
            continue
        parts = line.split("|")
        if len(parts) >= 7:
            rows.append({"test": parts[2], "method": parts[3],
                         "expected": parts[4], "measured": parts[5],
                         "status": parts[6],
                         "evidence": parts[7] if len(parts) > 7 else ""})
    return rows


def parse_shots(text):
    """`SHOT <ad> <yol>` satırlarından ad → tam yol eşlemesi."""
    shots = {}
    for line in text.splitlines():
        if line.startswith("SHOT "):
            parts = line.split(" ", 2)
            if len(parts) == 3:
                shots[parts[1]] = parts[2].strip()
    return shots


def repeat_count_for(number, name):
    if name == "p_ass_band" and number in ("P", "P150"):
        return ASS_REPEAT_COUNT
    return 1


def log_path_for_attempt(run_dir, number, name, attempt, total_attempts):
    suffix = f"-r{attempt:02d}" if total_attempts > 1 else ""
    return os.path.join(run_dir, f"{number}{suffix}-{name}.log")


def run_scenario(number, name, timeout, video, env, extra_env=None,
                 run_dir=LOG_DIR, attempt=1, total_attempts=1):
    log_path = log_path_for_attempt(run_dir, number, name, attempt,
                                    total_attempts)
    run_label = (f"{number}-r{attempt:02d}"
                 if total_attempts > 1 else number)
    started = time.time()
    print(f"\n=== {run_label} ({name}) start timeout={timeout}s ===",
          flush=True)
    if not video or not os.path.isfile(video):
        print(f"=== {number} ({name}) -> BLOCKED (video yok) ===", flush=True)
        return {"order": number, "run_label": run_label,
                "attempt": attempt, "name": name, "pid": None, "exit": None,
                "elapsed_s": 0.0, "timed_out": False, "mark_done": False,
                "log": log_path, "rows": [], "shots": {},
                "status": "BLOCKED",
                "counts": {"pass": 0, "fail": 0, "blocked": 1}}
    child_env = dict(env)
    child_env["MLC_NATIVE_TEST_VIDEO"] = video
    if extra_env:
        child_env.update(extra_env)
        child_env["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    with open(log_path, "w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.Popen(
            [sys.executable, CHILD, "--scenario", name, "--video", video],
            cwd=ROOT, env=child_env, stdout=handle,
            stderr=subprocess.STDOUT, text=True)
        pid = proc.pid
        killed = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            killed = True
            try:
                proc.kill()
                proc.wait(timeout=10)
            except Exception:
                pass
        finally:
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
    elapsed = round(time.time() - started, 1)
    text = open(log_path, encoding="utf-8", errors="replace").read()
    rows = parse_rows(text)
    done = f"MARK_DONE scenario={name}" in text
    status = classify_group(rows, timed_out=killed, mark_done=done,
                            exit_code=proc.returncode)
    counts = {
        "pass": len([r for r in rows if r["status"] == "PASS"]),
        "fail": len([r for r in rows if r["status"] == "FAIL"]),
        "blocked": len([r for r in rows if r["status"] == "BLOCKED"]),
    }
    print(f"=== {run_label} ({name}) -> {status} exit={proc.returncode} "
          f"elapsed={elapsed}s pass={counts['pass']} fail={counts['fail']} "
          f"blocked={counts['blocked']} done={done} log={log_path}",
          flush=True)
    for row in rows:
        if row["status"] in ("FAIL", "BLOCKED"):
            print(f"    {row['status']} {row['test']} :: {row['measured']} "
                  f"{row['evidence']}", flush=True)
    return {"order": number, "run_label": run_label,
            "attempt": attempt, "name": name, "pid": pid,
            "exit": proc.returncode, "elapsed_s": elapsed,
            "timed_out": killed, "mark_done": done, "log": log_path,
            "rows": rows, "shots": parse_shots(text), "status": status,
            "counts": counts}


def main():
    if os.environ.get("MLC_NATIVE_SMOKE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    only = {name for name in (sys.argv[1].split(",") if len(sys.argv) > 1
                              else []) if name}
    env = dict(os.environ)
    env["MLC_NATIVE_SMOKE"] = "1"
    main_video = env.get("MLC_NATIVE_TEST_VIDEO", "")
    if not os.path.isfile(main_video):
        print("HARNESS_FAILURE MLC_NATIVE_TEST_VIDEO gerçek bir dosya olmalı",
              flush=True)
        return 2

    original_cursor = cursor_pos()
    original_hwnd = int(user32.GetForegroundWindow())
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    run_dir = os.path.join(LOG_DIR, run_id)
    os.makedirs(run_dir, exist_ok=False)
    print(f"RUNNER_SESSION {run_id} dir={run_dir}", flush=True)
    print(f"RUNNER_SAVED cursor={original_cursor} fg={original_hwnd}",
          flush=True)

    summaries = []
    try:
        for entry in SCENARIOS:
            number, name, timeout, video_key = entry[:4]
            extra_env = entry[4] if len(entry) > 4 else None
            # Filtre hem senaryo adını hem koşum etiketini kabul eder
            # (`o_band` her iki DPI koşumunu, `O150` yalnız birini seçer).
            if only and name not in only and number not in only:
                continue
            total_attempts = repeat_count_for(number, name)
            for attempt in range(1, total_attempts + 1):
                summaries.append(run_scenario(
                    number, name, timeout, env.get(video_key, ""), env,
                    extra_env=extra_env, run_dir=run_dir, attempt=attempt,
                    total_attempts=total_attempts))
    finally:
        ok, now, attempts = restore(original_cursor, original_hwnd)
        print(f"RUNNER_RESTORED cursor={now} target={original_cursor} "
              f"ok={ok} attempts={attempts}", flush=True)

    report = os.path.join(run_dir, "summary.json")
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(summaries, handle, indent=2, ensure_ascii=False)
    print(f"\nREPORT {report}", flush=True)
    totals = {}
    for entry in summaries:
        totals[entry["status"]] = totals.get(entry["status"], 0) + 1
        label = entry.get("run_label", entry["order"])
        print(f"{label:>7} {entry['name']:<18} {entry['status']:<10} "
              f"pass={entry['counts']['pass']} fail={entry['counts']['fail']} "
              f"blocked={entry['counts']['blocked']} "
              f"timeout={entry['timed_out']} done={entry['mark_done']}",
              flush=True)
    print(f"TOTALS {totals}", flush=True)
    _print_ass_band_table(summaries)
    leaked = [entry for entry in summaries
              if entry["pid"] and _still_running(entry["pid"])]
    print(f"PROCESS_LEAK {[e['pid'] for e in leaked] or 'none'}", flush=True)
    if leaked:
        return 2
    return overall_exit_code(entry["status"] for entry in summaries)


def _still_running(pid):
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(handle)
    return code.value == 259  # STILL_ACTIVE


def _metric(rows, test, key):
    row = next((item for item in rows if item.get("test") == test), None)
    if row is None:
        return "?"
    match = re.search(rf"(?:^|\s){re.escape(key)}=(-?[0-9]+(?:\.[0-9]+)?)",
                      row.get("measured", ""))
    return match.group(1) if match else "?"


def _print_ass_band_table(summaries):
    ass_runs = [entry for entry in summaries
                if entry.get("name") == "p_ass_band"]
    if not ass_runs:
        return
    print("ASS_BAND_TABLE run status normal(gap,pos) playlist(gap,pos) "
          "fullscreen(gap,pos) return(gap,pos)", flush=True)
    cases = (("p_ass_gap_at_100", "normal"),
             ("p_ass_gap_with_playlist", "playlist"),
             ("p_ass_gap_fullscreen", "fullscreen"),
             ("p_ass_gap_after_fullscreen_return", "return"))
    for entry in ass_runs:
        cells = []
        for test, _label in cases:
            cells.append(f"{_metric(entry['rows'], test, 'gap')},"
                         f"{_metric(entry['rows'], test, 'mpv_sub_pos')}")
        print(f"ASS_BAND_ROW {entry.get('run_label', entry['order'])} "
              f"{entry['status']} " + " ".join(cells), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
