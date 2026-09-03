# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tek komutluk, tekrarlanabilir ana pencere Windows kabul runner'ı.

Bu script pytest paketi değildir. ``run_physical_acceptance.py`` içindeki
13 fiziksel grubu kanonik sırada çalıştırır; bütün bir döngü PASS olmadan
sonraki döngüye geçmez. Herhangi bir FAIL/BLOCKED/TIMEOUT/INCOMPLETE sonucu
otomatik kör retry yapılmadan fail-closed durur.

    set MLC_NATIVE_SMOKE=1
    set MLC_NATIVE_TEST_VIDEO=C:\\path\\fixture.mkv
    python tests/run_main_window_acceptance.py --repeat 3
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHYSICAL_RUNNER = ROOT / "tests" / "run_physical_acceptance.py"
LOG_DIR = Path(os.environ.get("TEMP", ".")) / "mlc_physical_logs"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repeat", type=int, default=3,
        help="Başarılı tam döngü sayısı (1-5; ilk başarısızlıkta durur).")
    return parser.parse_args(argv)


def _run_cycle(cycle):
    print(f"MAIN_WINDOW_CYCLE_START cycle={cycle}", flush=True)
    completed = subprocess.run(
        [sys.executable, str(PHYSICAL_RUNNER)], cwd=ROOT,
        env=dict(os.environ), text=True, check=False)
    source_report = LOG_DIR / "summary.json"
    cycle_report = LOG_DIR / f"main-window-cycle-{cycle}.json"
    if source_report.is_file():
        shutil.copy2(source_report, cycle_report)
    else:
        cycle_report = None
    return completed.returncode, cycle_report


def _report_is_all_pass(report_path):
    if report_path is None or not report_path.is_file():
        return False, "summary.json missing"
    try:
        rows = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"summary unreadable: {type(exc).__name__}"
    statuses = [row.get("group_status") for row in rows]
    if not rows or any(status != "PASS" for status in statuses):
        return False, f"group_statuses={statuses!r}"
    return True, f"groups={len(rows)}"


def main(argv=None):
    args = parse_args(argv)
    if os.environ.get("MLC_NATIVE_SMOKE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    if not 1 <= args.repeat <= 5:
        print("HARNESS_FAILURE repeat must be between 1 and 5", flush=True)
        return 2
    if not PHYSICAL_RUNNER.is_file():
        print(f"HARNESS_FAILURE missing_runner={PHYSICAL_RUNNER}", flush=True)
        return 2

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    print(f"MAIN_WINDOW_ACCEPTANCE_START repeat={args.repeat} utc={started}",
          flush=True)
    cycles = []
    for cycle in range(1, args.repeat + 1):
        exit_code, report_path = _run_cycle(cycle)
        passed, detail = _report_is_all_pass(report_path)
        result = {
            "cycle": cycle,
            "runner_exit": exit_code,
            "report": str(report_path) if report_path else None,
            "passed": passed and exit_code == 0,
            "detail": detail,
        }
        cycles.append(result)
        print(f"MAIN_WINDOW_CYCLE_RESULT cycle={cycle} "
              f"passed={result['passed']} exit={exit_code} {detail}",
              flush=True)
        if not result["passed"]:
            print("MAIN_WINDOW_ACCEPTANCE_STOP reason=first_failed_cycle",
                  flush=True)
            break

    report = {
        "repeat_requested": args.repeat,
        "cycles_completed": len(cycles),
        "all_passed": len(cycles) == args.repeat and all(
            cycle["passed"] for cycle in cycles),
        "cycles": cycles,
    }
    final_path = LOG_DIR / "main-window-acceptance-summary.json"
    final_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    print(f"MAIN_WINDOW_ACCEPTANCE_REPORT {final_path}", flush=True)
    print(f"MARK_DONE main_window_acceptance all_passed={report['all_passed']}",
          flush=True)
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
