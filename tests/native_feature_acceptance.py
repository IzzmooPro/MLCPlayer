# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fail-closed parent gate for the opt-in Windows native feature smoke.

This module deliberately imports neither Qt nor libmpv. Its evaluator and
media/process safety contracts can therefore be tested without opening a
window. The real child is launched only with a feature-specific opt-in and an
explicit supported video path.
"""
import ctypes
from ctypes import wintypes
import hashlib
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cover_art_native_child import (NATIVE_FAILURE_PATTERNS,  # noqa: E402
                                    decode_stream)
from native_feature_contract import (MEDIA_VARIABLE, OPTIONAL_CHECKS,  # noqa: E402
                                     OPT_IN_VALUE, OPT_IN_VARIABLE,
                                     REQUIRED_CHECKS)
from native_media_contract import (MEDIA_EXTENSIONS,  # noqa: E402
                                   is_supported_media)

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "native_feature_batch_smoke_child.py")
ROOT = os.path.dirname(os.path.dirname(CHILD))
DEFAULT_TIMEOUT_S = 180
FULL_HASH_LIMIT = 64 * 1024 * 1024
HASH_CHUNK_SIZE = 1024 * 1024
EXPECTED_RESULT = "RESULT failures=0"
EXTRA_FAILURE_PATTERNS = ("Traceback", "PYTHON_EXCEPTION", "BLOCKED ",
                          "SKIPPED:", "CONTRACT_ERROR")
FAILURE_PATTERNS = tuple(dict.fromkeys(
    tuple(NATIVE_FAILURE_PATTERNS) + EXTRA_FAILURE_PATTERNS))
CHECK_PATTERN = re.compile(
    r"^CHECK (PASS|FAIL) ([a-z0-9_]+) :: (.+)$")


def native_feature_requested(env=None):
    environment = os.environ if env is None else env
    return environment.get(OPT_IN_VARIABLE, "") == OPT_IN_VALUE


def evaluate_feature_result(returncode, stdout, stderr,
                            expect_screenshot=False):
    """Return a problem list; an empty list is the only accepted result."""
    problems = []
    stdout = decode_stream(stdout)
    stderr = decode_stream(stderr)

    for stream_name, text in (("stdout", stdout), ("stderr", stderr)):
        for pattern in FAILURE_PATTERNS:
            if pattern in text:
                problems.append(
                    f"{stream_name} icinde hata izi var: {pattern!r}")
    if stderr.strip():
        problems.append(
            f"stderr bos DEGIL ({len(stderr)} karakter): "
            f"{stderr.strip()[:400]!r}")
    if returncode != 0:
        problems.append(f"child exit code {returncode} (beklenen 0)")

    parsed = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("CHECK"):
            continue
        match = CHECK_PATTERN.fullmatch(stripped)
        if match is None:
            problems.append(f"bozuk CHECK satiri: {stripped!r}")
            continue
        parsed.append(match.groups())

    expected = set(REQUIRED_CHECKS)
    if expect_screenshot:
        expected.update(OPTIONAL_CHECKS)
    seen = {}
    for status, name, evidence in parsed:
        seen.setdefault(name, []).append((status, evidence))
        if name not in expected:
            problems.append(f"beklenmeyen CHECK: {name}")
        if status != "PASS":
            problems.append(f"FAIL CHECK: {name} :: {evidence}")
    for name in expected:
        entries = seen.get(name, [])
        if not entries:
            problems.append(f"eksik CHECK: {name}")
        elif len(entries) != 1:
            problems.append(f"tekil CHECK {len(entries)} kez yazilmis: {name}")

    results = [line.strip() for line in stdout.splitlines()
               if line.strip().startswith("RESULT")]
    if len(results) != 1:
        problems.append(f"RESULT satiri sayisi {len(results)} (beklenen 1)")
    if results and results[0] != EXPECTED_RESULT:
        problems.append(
            f"RESULT beklenenden farkli: {results[0]!r} "
            f"(beklenen {EXPECTED_RESULT!r})")

    done = [line.strip() for line in stdout.splitlines()
            if line.strip().startswith("MARK_DONE")]
    if done != ["MARK_DONE"]:
        problems.append(f"MARK_DONE tam ve tekil degil: {done!r}")
    nonempty = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not nonempty or nonempty[-1] != "MARK_DONE":
        problems.append("MARK_DONE son dolu satir degil")
    return problems


def media_fingerprint(path):
    """Read-only identity plus full/sampled SHA-256 for potentially huge media."""
    try:
        absolute = os.path.abspath(path)
        with open(absolute, "rb") as handle:
            before = os.fstat(handle.fileno())
            digest = hashlib.sha256()
            if before.st_size <= FULL_HASH_LIMIT:
                mode = "full"
                while True:
                    chunk = handle.read(HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    digest.update(chunk)
            else:
                mode = "sampled-v1"
                digest.update(b"MLC-SAMPLED-SHA256-v1\0")
                digest.update(before.st_size.to_bytes(8, "little"))
                last = max(0, before.st_size - HASH_CHUNK_SIZE)
                middle = max(0, (before.st_size - HASH_CHUNK_SIZE) // 2)
                for offset in sorted(set((0, middle, last))):
                    handle.seek(offset)
                    chunk = handle.read(HASH_CHUNK_SIZE)
                    digest.update(offset.to_bytes(8, "little"))
                    digest.update(len(chunk).to_bytes(8, "little"))
                    digest.update(chunk)
            after = os.fstat(handle.fileno())
    except (OSError, ValueError, OverflowError):
        return None
    return {
        "path": absolute,
        "size": before.st_size,
        "mtime_ns": before.st_mtime_ns,
        "hash_mode": mode,
        "sha256": digest.hexdigest(),
        "stable_during_read": (
            before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns),
    }


def media_fingerprint_problems(before, after):
    problems = []
    if before is None:
        problems.append("medya kosum ONCESI okunamadi; butunluk olculemedi")
    if after is None:
        problems.append("medya kosum SONRASI okunamadi; butunluk olculemedi")
    if before is None or after is None:
        return problems
    if not before.get("stable_during_read"):
        problems.append("medya ilk fingerprint okunurken degisti")
    if not after.get("stable_during_read"):
        problems.append("medya son fingerprint okunurken degisti")
    for field in ("path", "size", "mtime_ns", "hash_mode", "sha256"):
        if before.get(field) != after.get(field):
            problems.append(
                f"medya dosyasi kosumdan ETKILENDI: {field} "
                f"{before.get(field)!r} -> {after.get(field)!r}")
    return problems


class _IOCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    )


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IOCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


class _BasicAccountingInformation(ctypes.Structure):
    _fields_ = (
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    )


class WindowsJobGuard:
    """Own only the launched child tree; closing never targets foreign PIDs."""
    KILL_ON_JOB_CLOSE = 0x00002000

    def __init__(self, process):
        if os.name != "nt":
            raise RuntimeError("Windows Job Object yalniz Windows'ta vardir")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p,
                                               wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE,
                                                       wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32
        self._handle = kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits = _ExtendedLimitInformation()
            limits.BasicLimitInformation.LimitFlags = self.KILL_ON_JOB_CLOSE
            if not kernel32.SetInformationJobObject(
                    self._handle, 9, ctypes.byref(limits),
                    ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel32.AssignProcessToJobObject(
                    self._handle, wintypes.HANDLE(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise

    def active_processes(self):
        accounting = _BasicAccountingInformation()
        if not self._kernel32.QueryInformationJobObject(
                self._handle, 1, ctypes.byref(accounting),
                ctypes.sizeof(accounting), None):
            return None
        return int(accounting.ActiveProcesses)

    def close(self):
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def create_job_guard(process):
    return WindowsJobGuard(process)


def _detail(**values):
    base = {"returncode": None, "stdout": "", "stderr": "",
            "raw_stdout": b"", "raw_stderr": b"", "child_pid": None,
            "active_processes_after": None, "media_before": None,
            "media_after": None}
    base.update(values)
    return base


def run_native_feature(video, timeout=DEFAULT_TIMEOUT_S, env=None):
    """Launch the child once, only behind the feature-specific safety gate."""
    environment = dict(os.environ if env is None else env)
    blockers = []
    if not native_feature_requested(environment):
        blockers.append(
            f"canli kosum ISTENMEDI: {OPT_IN_VARIABLE}="
            f"{environment.get(OPT_IN_VARIABLE, '')!r}; child BASLATILMADI")
    if not is_supported_media(video):
        blockers.append(
            f"gecerli gercek medya degil (yalniz {MEDIA_EXTENSIONS}): "
            f"{video!r}")
    if blockers:
        return blockers, _detail()

    before = media_fingerprint(video)
    if before is None or not before.get("stable_during_read"):
        return (["medya kosum ONCESI guvenle fingerprint edilemedi; "
                 "child BASLATILMADI"], _detail(media_before=before))

    environment[OPT_IN_VARIABLE] = OPT_IN_VALUE
    environment[MEDIA_VARIABLE] = os.path.abspath(video)
    environment.pop("MLC_NATIVE_SMOKE", None)
    environment.pop("QT_QPA_PLATFORM", None)
    process = None
    guard = None
    try:
        process = subprocess.Popen(
            [sys.executable, CHILD], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, env=environment)
        guard = create_job_guard(process)
    except (OSError, RuntimeError) as exc:
        if process is not None:
            process.kill()
            process.communicate()
        after = media_fingerprint(video)
        problems = [f"child guvenli Job Object icinde baslatilamadi: "
                    f"{type(exc).__name__}"]
        problems.extend(media_fingerprint_problems(before, after))
        return problems, _detail(
            returncode=None if process is None else process.returncode,
            child_pid=None if process is None else process.pid,
            media_before=before, media_after=after)

    timed_out = False
    raw_stdout = b""
    raw_stderr = b""
    active_after = None
    try:
        try:
            raw_stdout, raw_stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as expired:
            timed_out = True
            raw_stdout = bytes(expired.output or b"")
            raw_stderr = bytes(expired.stderr or b"")
            process.kill()
            tail_stdout, tail_stderr = process.communicate()
            raw_stdout += bytes(tail_stdout or b"")
            raw_stderr += bytes(tail_stderr or b"")
        active_after = guard.active_processes()
    finally:
        guard.close()

    after = media_fingerprint(video)
    expect_screenshot = bool(environment.get("MLC_NATIVE_SCREENSHOT"))
    if timed_out:
        problems = [f"child {timeout} sn icinde bitmedi (timeout); "
                    "yalniz kendi Job Object surecleri kapatildi"]
    else:
        problems = evaluate_feature_result(
            process.returncode, raw_stdout, raw_stderr,
            expect_screenshot=expect_screenshot)
    if active_after is None:
        problems.append("Job Object surec sayisi okunamadi; sizinti olculemedi")
    elif active_after:
        problems.append(
            f"surec sizintisi: child bittikten sonra Job Object icinde "
            f"{active_after} aktif surec kaldi; kapatildi")
    problems.extend(media_fingerprint_problems(before, after))
    return problems, _detail(
        returncode=process.returncode,
        stdout=decode_stream(raw_stdout), stderr=decode_stream(raw_stderr),
        raw_stdout=raw_stdout, raw_stderr=raw_stderr,
        child_pid=process.pid, active_processes_after=active_after,
        media_before=before, media_after=after)
