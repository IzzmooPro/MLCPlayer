# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""NATIVE-001 icin PDB gerektirmeyen mpv trace tani sozlesmesi.

Bu modul `mpv`, PyQt veya `app.player` import etmez. Gercek kosumdan once
tamamen sentetik verilerle sinanabilir. Trace tanisi URUN KABULUNDEN
ayridir: Lua hata metninin yakalanmasi tani basarisidir, fakat child stderr'i
veya kapanis kabulundeki bir hata bu nedenle aklanmaz.
"""

import base64
import binascii
from collections import namedtuple
import math
import os
import re
import stat

from native_media_contract import is_supported_media


TRACE_OPT_IN_VARIABLE = "MLC_NATIVE_MPV_TRACE"
TRACE_LOG_VARIABLE = "MLC_NATIVE_MPV_TRACE_LOG"
TRACE_OPT_IN_VALUE = "1"
TRACE_FIELD_PREFIX = "trace_b64="
TRACE_CLIENT_LOG_LEVEL = "warn"
CHILD_STDOUT_SUFFIX = ".child_stdout.bin"
CHILD_STDERR_SUFFIX = ".child_stderr.bin"
SHUTDOWN_OPT_IN_VARIABLE = "MLC_NATIVE_SHUTDOWN_ACCEPTANCE"
MAX_TRACE_BYTES = 16 * 1024 * 1024

TraceRecord = namedtuple("TraceRecord", "level module message")

_LEVEL_NAMES = {"f": "fatal", "e": "error", "w": "warning"}
_KNOWN_LUA_MODULES = {"stats", "select", "ytdl_hook"}
_GENERIC_MPV_MODULES = {"cplayer", "global", "libmpv", "terminal"}
_TRACE_LINE = re.compile(
    r"^\[\s*(?P<time>\d+(?:\.\d+)?)\]"
    r"\[(?P<level>[a-z])\]"
    r"\[(?P<module>[^\]\r\n]+)\]\s*(?P<message>.*)$")


def trace_requested(env=None):
    """PDB'siz trace kosumu acikca istendi mi? Yalniz tam `1`."""
    environment = os.environ if env is None else env
    return environment.get(TRACE_OPT_IN_VARIABLE, "") == TRACE_OPT_IN_VALUE


def child_artifact_paths(trace_path):
    """Trace hedefinden kayipsiz raw child kanit yollarini turet."""
    absolute = os.path.abspath(os.fspath(trace_path))
    return {
        "stdout": absolute + CHILD_STDOUT_SUFFIX,
        "stderr": absolute + CHILD_STDERR_SUFFIX,
    }


def _child_artifact_blockers(paths):
    problems = []
    for stream, path in paths.items():
        if os.path.lexists(path):
            problems.append(
                f"{stream} child artifact zaten var; onceki kanit ezilmez: "
                f"{path!r}")
    return problems


def _persist_child_artifacts(detail, paths):
    """Raw stream'leri yeni dosyalara yazar; metinden geri uretmez."""
    raw = {}
    problems = []
    for stream in ("stdout", "stderr"):
        key = f"raw_{stream}"
        value = detail.get(key)
        if not isinstance(value, bytes):
            problems.append(
                f"{key} bayt olarak raporlanmadi; child kaniti yazilmadi")
        else:
            raw[stream] = value
    if problems:
        return problems

    for stream in ("stdout", "stderr"):
        try:
            with open(paths[stream], "xb") as handle:
                handle.write(raw[stream])
        except OSError as exc:
            problems.append(
                f"{stream} child artifact yazilamadi: "
                f"{type(exc).__name__}: {exc}")
    return problems


def encode_trace_path(path):
    """Unicode ve bosluklu yolu tek, bosluksuz marker alanina kodla."""
    return base64.urlsafe_b64encode(
        os.fspath(path).encode("utf-8")).decode("ascii")


def decode_trace_path(token):
    """Strict Base64 + strict UTF-8. Bozuk veya bos deger -> `None`."""
    if not isinstance(token, str) or not token:
        return None
    try:
        raw = base64.b64decode(token.encode("ascii"), altchars=b"-_",
                               validate=True)
        path = raw.decode("utf-8", errors="strict")
    except (binascii.Error, UnicodeDecodeError, UnicodeEncodeError,
            ValueError):
        return None
    return path or None


def diagnostic_mpv_config(base_config, trace_path):
    """Urun sozlugunu MUTATE ETMEDEN child'a ozel trace kopyasi."""
    absolute = os.path.abspath(os.fspath(trace_path))
    configured = dict(base_config)
    configured.update({
        "log_file": absolute,
        "msg_level": "all=trace",
        "msg_time": "yes",
        "msg_module": "yes",
        # python-mpv bunu mpv secenegi olarak gondermez; ayri `loglevel`
        # parametresiyle `mpv_request_log_messages()` esigini ayarlar.
        # Trace DOSYASI all=trace kalirken Python event kuyrugu sinirlanir.
        "loglevel": TRACE_CLIENT_LOG_LEVEL,
    })
    return configured


def trace_capture_problems(stdout):
    """Child log-event akisi mesaj kaybettiyse tani fail-closed kalir."""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    text = str(stdout)
    if re.search(r"log message buffer overflow:\s*\d+\s+messages?\s+skipped",
                 text, flags=re.IGNORECASE):
        return ["mpv log event buffer overflow; mesajlar atlandi ve tani eksik"]
    return []


def trace_target_problems(video, trace_path):
    """Trace hedefi yeni, mutlak ve medyadan ayri bir `.log` olmali."""
    problems = []
    if not trace_path:
        return [f"trace yolu yok: {TRACE_LOG_VARIABLE} bos"]

    path = os.fspath(trace_path)
    if not os.path.isabs(path):
        problems.append(f"trace yolu mutlak degil: {path!r}")
    if os.path.splitext(path)[1].lower() != ".log":
        problems.append(f"trace hedefi .log degil: {path!r}")

    absolute = os.path.abspath(path)
    if video and os.path.normcase(absolute) == os.path.normcase(
            os.path.abspath(os.fspath(video))):
        problems.append("trace hedefi medya dosyasiyla AYNI")

    parent = os.path.dirname(absolute)
    if not parent or not os.path.isdir(parent):
        problems.append(f"trace ust dizini yok veya dizin degil: {parent!r}")
    if os.path.lexists(absolute):
        problems.append(
            f"trace hedefi zaten var; onceki kanit ezilmez: {absolute!r}")
    return problems


def trace_run_blockers(video, trace_path, env=None):
    """Runner'a ulasmadan onceki iki opt-in + medya + hedef kapisi."""
    environment = os.environ if env is None else env
    problems = []
    if environment.get(SHUTDOWN_OPT_IN_VARIABLE, "") != "1":
        problems.append(
            f"native kapanis kosumu ISTENMEDI: {SHUTDOWN_OPT_IN_VARIABLE} "
            "tam '1' degil")
    if not trace_requested(environment):
        problems.append(
            f"mpv trace kosumu ISTENMEDI: {TRACE_OPT_IN_VARIABLE} tam '1' "
            "degil")
    if not is_supported_media(video):
        problems.append(f"gecerli .mkv/.mp4 medya degil: {video!r}")
    problems.extend(trace_target_problems(video, trace_path))
    return problems


def configure_trace_mode(player_module, video, env=None):
    """Child icinde kosullu trace kopyasini kur.

    Doner: `(marker_field_or_none, problems)`. Trace istenmediyse urun
    sozlugu AYNEN kalir. Istendiyse iki opt-in ve hedef kurallari gecmeden
    sozluk DEGISTIRILMEZ.
    """
    environment = os.environ if env is None else env
    if not trace_requested(environment):
        return None, []

    trace_path = environment.get(TRACE_LOG_VARIABLE, "")
    problems = trace_run_blockers(video, trace_path, environment)
    if problems:
        return None, problems

    absolute = os.path.abspath(trace_path)
    player_module.MPV_CONFIG = diagnostic_mpv_config(
        player_module.MPV_CONFIG, absolute)
    return TRACE_FIELD_PREFIX + encode_trace_path(absolute), []


def _finite_non_negative(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and value >= 0


def extract_trace_marker_problems(stdout, expected_path):
    """Child'in trace hedefini tam bir kez ve kayipsiz bildirdigini olc."""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    found = []
    for line in str(stdout).splitlines():
        parts = line.strip().split()
        if parts[:1] == ["MARK_TRACE_CONFIGURED"]:
            found.append(parts)

    if not found:
        return ["eksik marker: MARK_TRACE_CONFIGURED"]
    if len(found) != 1:
        return [f"MARK_TRACE_CONFIGURED {len(found)} kez yazilmis"]

    parts = found[0]
    if len(parts) != 3:
        return ["MARK_TRACE_CONFIGURED tam `t=` ve `trace_b64=` alanlarini "
                f"ister: {' '.join(parts)!r}"]
    if not parts[1].startswith("t=") or not _finite_non_negative(parts[1][2:]):
        return [f"MARK_TRACE_CONFIGURED gecersiz zaman: {parts[1]!r}"]
    if not parts[2].startswith(TRACE_FIELD_PREFIX):
        return [f"MARK_TRACE_CONFIGURED alani {TRACE_FIELD_PREFIX!r} ile "
                f"baslamiyor: {parts[2]!r}"]

    decoded = decode_trace_path(parts[2][len(TRACE_FIELD_PREFIX):])
    if decoded is None:
        return ["MARK_TRACE_CONFIGURED yolu strict Base64/UTF-8 ile "
                "cozulemedi"]
    if os.path.normcase(os.path.abspath(decoded)) != os.path.normcase(
            os.path.abspath(expected_path)):
        return [f"MARK_TRACE_CONFIGURED beklenen yolu bildirmiyor: "
                f"{decoded!r} != {expected_path!r}"]
    return []


def evaluate_trace_log(raw):
    """mpv trace baytlarindan Lua hata/traceback kayitlarini ayikla.

    Doner: `(problems, TraceRecord listesi)`. Bos liste ancak en az bir
    Lua adayi, kesin zaman/seviye/modul dilbilgisiyle yakalandiysa tani
    basarisidir. Bu URUN PASS'i anlamina gelmez.
    """
    if isinstance(raw, str):
        text = raw
    else:
        try:
            text = bytes(raw).decode("utf-8", errors="strict")
        except (TypeError, UnicodeDecodeError):
            return ["mpv trace gecerli UTF-8 degil"], []

    if not text.strip():
        return ["mpv trace bos; Lua hata mesaji olculemedi"], []

    records = []
    for line in text.splitlines():
        match = _TRACE_LINE.match(line.strip())
        if not match:
            continue
        if not _finite_non_negative(match.group("time")):
            continue
        level_code = match.group("level")
        if level_code not in _LEVEL_NAMES:
            continue
        module = match.group("module").strip()
        message = match.group("message").strip()
        if not module or not message:
            continue

        module_lower = module.lower()
        message_lower = message.lower()
        module_is_lua = (module_lower.startswith("lua/") or
                         module_lower in _KNOWN_LUA_MODULES)
        message_is_lua = ("lua error" in message_lower or
                          "stack traceback" in message_lower)
        if module_is_lua and (level_code in ("e", "f") or message_is_lua):
            records.append(TraceRecord(
                _LEVEL_NAMES[level_code], module, message))
        elif message_is_lua:
            records.append(TraceRecord(
                _LEVEL_NAMES[level_code], module, message))

    if not records:
        return ["mpv trace icinde Lua hata/traceback kaniti bulunamadi; "
                "tani SONUCSUZ"], []

    problems = []
    has_error_message = any(
        record.level in ("error", "fatal") and
        "stack traceback" not in record.message.lower()
        for record in records)
    if not has_error_message:
        problems.append(
            "Lua traceback bulundu fakat asil Lua hata mesaji bulunamadi; "
            "tani KISMI")

    has_script_source = any(
        record.module.lower() not in _GENERIC_MPV_MODULES
        for record in records)
    if not has_script_source:
        problems.append(
            "Lua hata mesaji bulundu fakat script kaynagi belirlenemedi; "
            "genel mpv modulu tani icin yeterli degil")
    return problems, records


def _read_new_trace(path):
    """Yeni trace'i link/ozel dosya/asin boyut icin fail-closed oku."""
    try:
        info = os.lstat(path)
    except OSError as exc:
        return [f"mpv trace okunamadi: {type(exc).__name__}: {exc}"], b""
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return ["mpv trace normal dosya degil (link/ozel giris reddedildi)"], b""
    if info.st_size <= 0:
        return ["mpv trace bos dosya"], b""
    if info.st_size > MAX_TRACE_BYTES:
        return [f"mpv trace boyut sinirini asti: {info.st_size} > "
                f"{MAX_TRACE_BYTES}"], b""
    try:
        with open(path, "rb") as handle:
            return [], handle.read(MAX_TRACE_BYTES + 1)
    except OSError as exc:
        return [f"mpv trace okunamadi: {type(exc).__name__}: {exc}"], b""


def run_native_trace(video, trace_path, timeout=180, env=None,
                     shutdown_runner=None):
    """PDB'siz taniyi TEK child kosumuyla yurutmeye hazir runner.

    Bu fonksiyonun gercek kullanimi AYRI ONAY B ister. Deterministik testler
    `shutdown_runner` enjekte eder; subprocess baslatmaz. Tani sorunlari ile
    urun kapanis sorunlari AYRI raporlanir.
    """
    environment = dict(os.environ if env is None else env)
    blockers = trace_run_blockers(video, trace_path, environment)
    artifacts = child_artifact_paths(trace_path)
    blockers.extend(_child_artifact_blockers(artifacts))
    empty_detail = {"shutdown_problems": [], "shutdown_detail": {},
                    "trace_records": [], "child_artifacts": artifacts}
    if blockers:
        return blockers, empty_detail

    if shutdown_runner is None:
        from native_shutdown_acceptance import run_native_shutdown
        shutdown_runner = run_native_shutdown

    absolute_trace = os.path.abspath(trace_path)
    child_env = dict(environment)
    child_env[TRACE_LOG_VARIABLE] = absolute_trace
    shutdown_problems, shutdown_detail = shutdown_runner(
        video, timeout=timeout, env=child_env)

    diagnostic_problems = _persist_child_artifacts(
        shutdown_detail, artifacts)
    diagnostic_problems.extend(trace_capture_problems(
        shutdown_detail.get("stdout", "")))
    diagnostic_problems.extend(extract_trace_marker_problems(
        shutdown_detail.get("stdout", ""), absolute_trace))
    read_problems, raw = _read_new_trace(absolute_trace)
    diagnostic_problems.extend(read_problems)
    records = []
    if not read_problems:
        log_problems, records = evaluate_trace_log(raw)
        diagnostic_problems.extend(log_problems)

    return diagnostic_problems, {
        "shutdown_problems": list(shutdown_problems),
        "shutdown_detail": shutdown_detail,
        "trace_records": records,
        "trace_path": absolute_trace,
        "child_artifacts": artifacts,
    }
