"""Native overlay crash tetikleyici matrisi çalıştırıcısı.

``native_overlay_smoke_child.py`` scriptini farklı modlarda ayrı süreçlerde
çalıştırır; her koşum için signed exit code, hex Windows hata kodu, son
başarılı marker, RESULTS/MARK_DONE görülüp görülmediği, toplam süre ve artık
child süreç kalıp kalmadığını raporlar.

Bu dosya pytest tarafından toplanmaz ve ``MLC_NATIVE_SMOKE=1`` olmadan hiçbir
native süreç başlatmaz.

Kullanım:
    python tests/run_native_overlay_matrix.py --label current
    python tests/run_native_overlay_matrix.py --project-root <baseline-worktree> --label baseline
    python tests/run_native_overlay_matrix.py --variants
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

MARKER_RE = re.compile(r"^(MARK_[A-Z_]+|RESULTS|VARIANT_APPLIED|SKIP_[A-Z_]+)")
FOCUS_PID_RE = re.compile(r"^MARK_FOCUS_CHILD_STARTED\b.*\bpid=(\d+)\b", re.MULTILINE)


def parse_focus_child_pid(stdout):
    """Yalnızca bu koşumun başlattığı focus child PID'ini döndürür.

    Sentetik modda ``pid=self`` yazılır ve takip edilecek ayrı süreç yoktur.
    """
    match = FOCUS_PID_RE.search(stdout or "")
    return int(match.group(1)) if match else None


def is_process_running(pid):
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:
        return False
    return str(pid) in out


def kill_pid(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                   capture_output=True, text=True)


def cleanup_tracked_child(pid):
    """Güvenli fallback temizlik.

    Birincil mekanizma smoke child'ın kendi try/finally temizliğidir. Burada
    yalnızca bu koşumun raporladığı PID hedeflenir; sistemde geniş süreç
    taraması yapılmaz, böylece paralel testlerin veya kullanıcının Python/Qt
    süreçleri asla kapatılmaz.
    """
    if pid is None:
        return {"leaked": [], "cleanup_error": None}
    try:
        if not is_process_running(pid):
            return {"leaked": [], "cleanup_error": None}
        kill_pid(pid)
        return {"leaked": [pid], "cleanup_error": None}
    except Exception as exc:
        return {"leaked": [], "cleanup_error": f"{type(exc).__name__}: {exc}"}


FAILURE_CHECKS = (
    ("timeout", lambda row: row["timed_out"]),
    ("exit_code", lambda row: row["exit_code"] not in (0, None) or
     (row["exit_code"] is None and not row["timed_out"])),
    ("python_exception", lambda row: row["python_exception"]),
    ("no_results", lambda row: not row["results_seen"]),
    ("no_mark_done", lambda row: not row["done_seen"]),
    ("leaked_child", lambda row: bool(row["leaked_children"])),
    ("cleanup_error", lambda row: bool(row.get("cleanup_error"))),
)


def failure_reasons(row):
    return [name for name, check in FAILURE_CHECKS if check(row)]


def matrix_exit_code(rows):
    return 1 if any(failure_reasons(row) for row in rows) else 0


def run_case(case, project_root, timeout):
    env = dict(os.environ)
    env["MLC_NATIVE_SMOKE"] = "1"
    env["MLC_NATIVE_PROJECT_ROOT"] = project_root
    env["MLCPLAYER_OVERLAY_PREVIEW"] = case["preview"]
    env["MLC_NATIVE_FOCUS_HANDOFF"] = "1" if case["focus"] else "0"
    env["MLC_NATIVE_VARIANT"] = case.get("variant", "none")
    env["MLC_NATIVE_SYNTHETIC"] = "1" if case.get("synthetic") else "0"
    # Kontrollü PYEXC gösterimi normal matrix koşumuna sızmamalı; yalnızca
    # --force-pyexc-demo modunda açıkça etkinleştirilir.
    if case.get("force_pyexc"):
        env["MLC_NATIVE_FORCE_PYEXC"] = "1"
        env["MLC_NATIVE_NO_EXCEPTHOOK"] = case.get("no_excepthook", "1")
    else:
        env.pop("MLC_NATIVE_FORCE_PYEXC", None)
        env.pop("MLC_NATIVE_NO_EXCEPTHOOK", None)
    env["MLC_NATIVE_IDLE_MS"] = str(case.get("idle_ms", 5000))
    env["MLC_NATIVE_PLAY_MS"] = str(case.get("play_ms", 4000))
    env["MLC_NATIVE_SETTINGS"] = os.path.join(
        env.get("TEMP", project_root), "MLCPlayer-native-smoke", case["name"])
    env.pop("QT_QPA_PLATFORM", None)
    if case["video"]:
        env["MLC_NATIVE_TEST_VIDEO"] = case["video"]
    else:
        env.pop("MLC_NATIVE_TEST_VIDEO", None)

    script = os.path.join(project_root, "tests", "native_overlay_smoke_child.py")
    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run([sys.executable, script], env=env, cwd=project_root,
                              capture_output=True, text=True, timeout=timeout)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        code = None
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    elapsed = time.time() - start

    cleanup = cleanup_tracked_child(parse_focus_child_pid(out))

    markers = [line.split()[0].rstrip(":") for line in out.splitlines()
               if MARKER_RE.match(line)]
    real_marks = [m for m in markers if m.startswith("MARK_") or m == "RESULTS"]
    return {
        "name": case["name"],
        "preview": case["preview"],
        "video": bool(case["video"]),
        "focus": case["focus"],
        "variant": case.get("variant", "none"),
        "exit_code": code,
        "hex": "TIMEOUT" if code is None else f"0x{code & 0xFFFFFFFF:08X}",
        "last_marker": real_marks[-1] if real_marks else "NONE",
        "results_seen": any(m == "RESULTS" for m in markers),
        "done_seen": any(m == "MARK_DONE" for m in markers),
        "elapsed_s": round(elapsed, 2),
        "leaked_children": cleanup["leaked"],
        "cleanup_error": cleanup["cleanup_error"],
        "timed_out": timed_out,
        "python_exception": "PYTHON_EXCEPTION" in out or "Traceback (most recent" in err,
        "stdout": out,
        "stderr": err,
    }


def base_matrix(video):
    return [
        {"name": "preview_on_novideo_nofocus", "preview": "1", "video": "", "focus": False},
        {"name": "preview_on_video_nofocus", "preview": "1", "video": video, "focus": False},
        {"name": "preview_on_novideo_focus", "preview": "1", "video": "", "focus": True},
        {"name": "preview_on_video_focus", "preview": "1", "video": video, "focus": True},
        {"name": "preview_off_video_focus", "preview": "0", "video": video, "focus": True},
        # Madde 4: sentetik aktivasyonun gerçek foreground devrinden farkını ölçer.
        {"name": "synthetic_preview_on_novideo", "preview": "1", "video": "",
         "focus": True, "synthetic": True},
        {"name": "synthetic_preview_on_video", "preview": "1", "video": video,
         "focus": True, "synthetic": True},
    ]


def variant_matrix(video, variants):
    """İzolasyon varyantları: her koşum üründen tek bir özelliği çıkarır."""
    return [
        {"name": f"variant_{v}", "preview": "1", "video": video, "focus": True, "variant": v}
        for v in variants
    ]


ALL_VARIANTS = (
    "none", "no_stay_on_top", "no_tool", "no_owner", "no_translucent",
    "no_show_without_activating", "accepts_focus", "no_event_filter", "empty_content",
)


def run_pyexc_demo(args):
    """Ayrı, açıkça istenen gösterim; normal matrix başarısı sayılmaz.

    Beklenen: excepthook kapalıyken 0xC0000409, açıkken exit 90.
    Beklenti karşılanırsa 0, karşılanmazsa 1 döner.
    """
    expectations = (
        ("no_excepthook (PyQt6 varsayilan abort)", "1", 0xC0000409),
        ("excepthook acik (harness)", "0", 90),
    )
    ok = True
    print("=== KONTROLLU PYEXC GOSTERIMI (normal matrix degildir) ===", flush=True)
    for label, no_excepthook, expected in expectations:
        case = {"name": f"pyexc_{no_excepthook}", "preview": "1", "video": "",
                "focus": False, "force_pyexc": True, "no_excepthook": no_excepthook,
                "idle_ms": 500}
        row = run_case(case, args.project_root, args.timeout)
        actual = None if row["exit_code"] is None else row["exit_code"] & 0xFFFFFFFF
        matched = actual == expected
        ok = ok and matched
        print(f"{label:42} beklenen=0x{expected:08X} "
              f"gercek={row['hex']} eslesti={matched}", flush=True)
    print(f"PYEXC_DEMO_OK={ok}", flush=True)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=DEFAULT_ROOT)
    parser.add_argument("--label", default="current")
    parser.add_argument("--video", default=os.environ.get("MLC_NATIVE_TEST_VIDEO", ""))
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--variants", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--json-out", default="")
    parser.add_argument(
        "--force-pyexc-demo", action="store_true",
        help="Kontrollü gösterim: slot içindeki Python istisnasının 0xC0000409 "
             "ürettiğini kanıtlar. Normal matrix koşumu DEĞİLDİR.")
    args = parser.parse_args()

    if os.environ.get("MLC_NATIVE_SMOKE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED (MLC_NATIVE_SMOKE=1 gerekli)", flush=True)
        return 0

    if args.force_pyexc_demo:
        return run_pyexc_demo(args)

    if args.variants:
        names = (list(ALL_VARIANTS) if args.variants == "all"
                 else [v.strip() for v in args.variants.split(",")])
        cases = variant_matrix(args.video, names)
    else:
        cases = base_matrix(args.video)
    if args.only:
        wanted = {n.strip() for n in args.only.split(",")}
        cases = [c for c in cases if c["name"] in wanted]

    rows = []
    for case in cases:
        print(f"\n=== [{args.label}] {case['name']} ===", flush=True)
        row = run_case(case, args.project_root, args.timeout)
        row["label"] = args.label
        rows.append(row)
        print(row["stdout"].strip(), flush=True)
        if row["stderr"].strip():
            print("--- stderr ---\n" + row["stderr"].strip()[-2000:], flush=True)
        print(
            f"--> exit={row['exit_code']} hex={row['hex']} last={row['last_marker']} "
            f"RESULTS={row['results_seen']} DONE={row['done_seen']} "
            f"t={row['elapsed_s']}s leaked={row['leaked_children']} "
            f"fail={failure_reasons(row)}",
            flush=True,
        )

    print("\n\n=== TABLO (%s) ===" % args.label, flush=True)
    header = (f"{'case':34} {'exit':>12} {'hex':>10} {'last_marker':24} "
              f"{'RES':>5} {'DONE':>5} {'t(s)':>7} {'pyexc':>6} {'leak':>8} fail")
    print(header, flush=True)
    for row in rows:
        print(
            f"{row['name']:34} {str(row['exit_code']):>12} {row['hex']:>10} "
            f"{row['last_marker']:24} {str(row['results_seen']):>5} "
            f"{str(row['done_seen']):>5} {row['elapsed_s']:>7} "
            f"{str(row['python_exception']):>6} {str(row['leaked_children']):>8} "
            f"{','.join(failure_reasons(row)) or '-'}",
            flush=True,
        )

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump([{k: v for k, v in r.items() if k not in ("stdout", "stderr")}
                       for r in rows], handle, indent=2)

    exit_code = matrix_exit_code(rows)
    failed = [row["name"] for row in rows if failure_reasons(row)]
    print(f"\nMATRIX_EXIT={exit_code} failed_cases={failed or '-'}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
