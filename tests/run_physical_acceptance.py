# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fiziksel kabul runner'i: 13 grubu AYRI taze child process'lerde kosar.

- Her grup icin sinirli timeout ve takip edilen PID.
- Bir grubun kilitlenmesi digerlerini engellemez.
- Runner yalnizca KENDI baslattigi PID'leri sonlandirir.
- Baslangic mouse konumu ve foreground HWND runner tarafinda da kaydedilir;
  child cokse bile runner geri yukler.
- Timeout, eksik MARK_DONE veya zorla sonlandirma PASS sayilmaz.

Repoya ait normal pytest paketine dahil degildir (dosya adi test_ ile
baslamaz) ve MLC_NATIVE_SMOKE=1 gerektirir.
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)
CHILD = os.path.join(TESTS_DIR, "native_physical_acceptance_child.py")
LOG_DIR = os.path.join(os.environ.get("TEMP", "."), "mlc_physical_logs")
os.makedirs(LOG_DIR, exist_ok=True)

sys.path.insert(0, TESTS_DIR)
from physical_buttons_contract import (  # noqa: E402
    BUTTONS_GROUP_TIMEOUT_SECONDS,
    FULLSCREEN_GROUP_TIMEOUT_SECONDS,
    PLAYBACK_SEEK_GROUP_TIMEOUT_SECONDS,
    TIMELINE_GROUP_TIMEOUT_SECONDS,
    WINDOW_RESIZE_GROUP_TIMEOUT_SECONDS,
)
from native_feature_acceptance import create_job_guard  # noqa: E402

user32 = ctypes.windll.user32
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]

GROUPS = [
    ("1", "buttons", BUTTONS_GROUP_TIMEOUT_SECONDS),
    ("2", "timeline", TIMELINE_GROUP_TIMEOUT_SECONDS),
    ("3", "separator", 420),
    ("4", "window_resize", WINDOW_RESIZE_GROUP_TIMEOUT_SECONDS),
    ("5", "alttab", 480),
    ("6", "toggle", 600),
    ("7", "dragdrop", 180),
    ("8", "thumbnails", 300),
    ("9", "fullscreen", FULLSCREEN_GROUP_TIMEOUT_SECONDS),
    ("10", "subtitles", 480),
    ("11", "zorder", 480),
    ("12", "playback_seek", PLAYBACK_SEEK_GROUP_TIMEOUT_SECONDS),
    ("13", "tracks", 180),
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


def classify_group(rows, timed_out, mark_done, exit_code, protocol_ok=True,
                   leak_free=True):
    """Bir grubun KESIN sonucu. "Test edilemedi" ASLA "basarili" degildir.

    Sira: TIMEOUT > INCOMPLETE (eksik MARK_DONE veya hic RESULT satiri yok)
    > FAIL > BLOCKED > CRASH (satirlar gecmis gorunurken surec yine de
    sifir olmayan/bilinmeyen exit vermis) > PASS.

    BLOCKED satiri, grupta PASS satirlari da olsa grubu bloklar. Child
    sozlesmesi geregi FAIL varken exit 1 dondurur; bu ayri bir "crash"
    olarak degil FAIL olarak raporlanir.
    """
    if timed_out:
        return "TIMEOUT"
    if not protocol_ok or not leak_free or not mark_done or not rows:
        return "INCOMPLETE"
    statuses = {row.get("status") for row in rows}
    if "FAIL" in statuses:
        return "FAIL"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if statuses != {"PASS"}:
        # Taninmayan durum kodu da "basarili" sayilmaz.
        return "INCOMPLETE"
    if exit_code != 0:
        return "CRASH"
    return "PASS"


def parse_result_line(line, group):
    parts = line.split("|")
    if (len(parts) != 8 or parts[0] != "RESULT" or parts[1] != group
            or parts[6] not in {"PASS", "FAIL", "BLOCKED"}):
        return None
    return {
        "test": parts[2], "method": parts[3], "expected": parts[4],
        "measured": parts[5], "status": parts[6], "evidence": parts[7],
    }


def protocol_problems(text, group, rows, malformed_results=0):
    """Child marker/summary zincirini exact ve fail-closed dogrular."""
    lines = text.splitlines()
    problems = []
    done = [i for i, line in enumerate(lines)
            if line == f"MARK_DONE group={group}"]
    exec_returned = [i for i, line in enumerate(lines)
                     if line == f"MARK_APP_EXEC_RETURNED group={group} code=0"]
    restored = [i for i, line in enumerate(lines)
                if line.startswith("CHILD_RESTORED ") and "ok=True" in line]
    summaries = []
    pattern = re.compile(
        rf"^GROUP_SUMMARY group={re.escape(group)} total=(\d+) "
        r"pass=(\d+) fail=(\d+) blocked=(\d+)$")
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            summaries.append((index, tuple(map(int, match.groups()))))
    if len(done) != 1:
        problems.append(f"mark_done_count={len(done)}")
    if len(exec_returned) != 1:
        problems.append(f"exec_returned_count={len(exec_returned)}")
    if len(restored) != 1:
        problems.append(f"restored_count={len(restored)}")
    if len(summaries) != 1:
        problems.append(f"summary_count={len(summaries)}")
    if malformed_results:
        problems.append(f"malformed_results={malformed_results}")
    if len(summaries) == 1:
        total, passed, failed, blocked = summaries[0][1]
        actual = (
            len(rows),
            len([row for row in rows if row["status"] == "PASS"]),
            len([row for row in rows if row["status"] == "FAIL"]),
            len([row for row in rows if row["status"] == "BLOCKED"]),
        )
        if (total, passed, failed, blocked) != actual:
            problems.append(
                f"summary_mismatch={(total, passed, failed, blocked)}!={actual}")
    if (len(restored) == len(exec_returned) == len(summaries) == len(done) == 1
            and not (restored[0] < exec_returned[0] < summaries[0][0] < done[0])):
        problems.append("marker_order_invalid")
    return problems


def overall_exit_code(group_statuses):
    """Yalniz BUTUN secili gruplar gercek PASS ise 0."""
    statuses = list(group_statuses)
    if not statuses:
        return 1
    return 0 if all(status == "PASS" for status in statuses) else 1


def run_group(number, name, timeout, env):
    log_path = os.path.join(LOG_DIR, f"group{number}-{name}.log")
    started = time.time()
    print(f"\n=== GROUP {number} ({name}) start timeout={timeout}s ===", flush=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.Popen(
            [sys.executable, CHILD, "--group", name],
            cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, text=True)
        pid = proc.pid
        killed = False
        guard = None
        active_after = None
        try:
            guard = create_job_guard(proc)
            proc.wait(timeout=timeout)
        except (OSError, RuntimeError) as exc:
            handle.write(
                f"HARNESS_FAILURE job_guard={type(exc).__name__}\n")
            handle.flush()
            try:
                proc.kill()
                proc.wait(timeout=10)
            except Exception:
                pass
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
            if guard is not None:
                try:
                    active_after = guard.active_processes()
                finally:
                    guard.close()
    elapsed = round(time.time() - started, 1)
    text = open(log_path, encoding="utf-8", errors="replace").read()
    result_lines = [line for line in text.splitlines()
                    if line.startswith("RESULT|")]
    parsed_rows = [parse_result_line(line, name) for line in result_lines]
    malformed = len([row for row in parsed_rows if row is None])
    rows = [row for row in parsed_rows if row is not None]
    done = text.splitlines().count(f"MARK_DONE group={name}") == 1
    protocol_errors = protocol_problems(
        text, name, rows, malformed_results=malformed)
    if active_after is None:
        protocol_errors.append("job_process_count_unavailable")
    elif active_after != 0:
        protocol_errors.append(f"leaked_job_processes={active_after}")
    restored = not any(problem.startswith("restored_count=")
                       for problem in protocol_errors)
    summary = {
        "group": number, "name": name, "pid": pid, "exit": proc.returncode,
        "elapsed_s": elapsed, "timed_out": killed, "mark_done": done,
        "child_restored_cursor": restored, "log": log_path,
        "active_job_processes_after": active_after,
        "rows": [],
    }
    summary["rows"].extend(rows)
    summary["protocol_problems"] = protocol_errors
    passes = [r for r in summary["rows"] if r["status"] == "PASS"]
    fails = [r for r in summary["rows"] if r["status"] == "FAIL"]
    blocked = [r for r in summary["rows"] if r["status"] == "BLOCKED"]
    summary["group_status"] = classify_group(
        summary["rows"], timed_out=killed, mark_done=done,
        exit_code=proc.returncode, protocol_ok=not protocol_errors,
        leak_free=active_after == 0)
    summary["counts"] = {"pass": len(passes), "fail": len(fails),
                         "blocked": len(blocked)}
    print(f"=== GROUP {number} ({name}) -> {summary['group_status']} "
          f"exit={proc.returncode} elapsed={elapsed}s pass={len(passes)} "
          f"fail={len(fails)} blocked={len(blocked)} done={done} "
         f"log={log_path}", flush=True)
    for problem in protocol_errors:
        print(f"    PROTOCOL {problem}", flush=True)
    for row in fails:
        print(f"    FAIL {row['test']} :: {row['measured']}", flush=True)
    for row in blocked:
        print(f"    BLOCKED {row['test']} :: {row['evidence']}", flush=True)
    return summary


def main():
    if os.environ.get("MLC_NATIVE_SMOKE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0

    only = {name for name in (sys.argv[1].split(",") if len(sys.argv) > 1 else [])
            if name}
    original_cursor = cursor_pos()
    original_hwnd = int(user32.GetForegroundWindow())
    print(f"RUNNER_SAVED cursor={original_cursor} foreground_hwnd={original_hwnd}",
          flush=True)

    env = dict(os.environ)
    env["MLC_NATIVE_SMOKE"] = "1"
    env.setdefault("MLC_NATIVE_SETTINGS",
                   os.path.join(os.environ.get("TEMP", "."), "mlc_phys_settings"))
    # Medya olmadan play/pause urunde modal dosya secici acar ve event loop'u
    # bloklar; bu yuzden gercek video yolu ZORUNLUDUR.
    if not os.path.isfile(env.get("MLC_NATIVE_TEST_VIDEO", "")):
        print("HARNESS_FAILURE MLC_NATIVE_TEST_VIDEO gecerli bir dosya olmali",
              flush=True)
        return 2

    summaries = []
    try:
        for number, name, timeout in GROUPS:
            if only and name not in only:
                continue
            summaries.append(run_group(number, name, timeout, env))
    finally:
        ok, now, attempts = restore(original_cursor, original_hwnd)
        print(f"RUNNER_RESTORED cursor={now} target={original_cursor} "
              f"ok={ok} attempts={attempts}", flush=True)
        if not ok:
            print("HARNESS_FAILURE mouse_restore_failed", flush=True)

    report = os.path.join(LOG_DIR, "summary.json")
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(summaries, handle, indent=2, ensure_ascii=False)
    print(f"\nREPORT {report}", flush=True)
    totals = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "TIMEOUT": 0,
              "INCOMPLETE": 0, "CRASH": 0}
    for entry in summaries:
        totals[entry["group_status"]] = totals.get(entry["group_status"], 0) + 1
        print(f"GROUP {entry['group']:>2} {entry['name']:<14} "
              f"{entry['group_status']:<10} pass={entry['counts']['pass']} "
              f"fail={entry['counts']['fail']} "
              f"blocked={entry['counts']['blocked']} "
              f"timeout={entry['timed_out']} done={entry['mark_done']}", flush=True)
    print(f"TOTALS {totals}", flush=True)
    return overall_exit_code(entry["group_status"] for entry in summaries)


if __name__ == "__main__":
    raise SystemExit(main())
