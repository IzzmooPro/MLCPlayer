# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""NATIVE-001 asama 2: URUN KAPANIS yolunun tek yalitilmis kabulu.

Bu modul `tests/native_player_shutdown_child.py` cocugunu **bir kez**
calistirir ve sonucu SAF bir sozlesmeyle degerlendirir. Modul `mpv`,
`PyQt6` veya `app.player` IMPORT ETMEZ; boylece degerlendirici, aralikli
native olguyu tekrar kosturmadan deterministik olarak sinanabilir.

Olculen urun yolu:

    player.close() -> closeEvent() -> stop() -> terminate()

Child bu yolu KENDI baslatmaz; yalnizca `player.close()` cagirir.

FAIL-CLOSED: child `exit 0` verse ve butun marker'lari tasisa bile genel
stderr/fatal izleri kabul DUSURUR. Tek dar istisna, CPython'in Windows VEH
faulthandler'inin yakalanmis LuaJIT `LUA_ERRRUN` SEH olayi icin yazdigi TAM
biçimli rapordur; nonzero exit, eksik marker veya ek stderr bunu aklayamaz.

OLCULEN BES FAIL-OPEN (18 Agustos 2026, bagimsiz denetim) ve kapatilmasi:

1. `FREE` dilbilgisi EKSIK KANITI kabul ediyordu: `MARK_PLAYER_CREATED
   t=0.51` (medya adi yok), `MARK_MEDIA_OPEN_REQUESTED t=0.52`,
   `MARK_MEDIA_READY t=1.24` (duration/position yok) ve
   `MARK_CLOSE_ACCEPTED ... visible=True` YESIL geciyordu. `FREE`
   KALDIRILDI; her marker kesin sozlesmeye baglandi.
2. Zaman damgasi yalnizca `float()` donusumuyle olculuyordu; `t=nan`,
   `t=inf` ve negatif degerler geciyordu. Artik `math.isfinite` ve
   `>= 0` zorunlu.
3. Medya turu dogrulanmiyordu: `MLC_NATIVE_TEST_VIDEO` bir `.py` dosyasi
   gosterse bile gecerli sayiliyordu. Artik yalniz gercek `.mkv`/`.mp4`
   dosyalari kabul edilir ve gecersiz medyada child HIC baslatilmaz.
4. Canli kabul yalnizca medya degiskeninin varligiyla tetikleniyordu.
   Artik ayrica ACIK opt-in gerekir:
   `MLC_NATIVE_SHUTDOWN_ACCEPTANCE=1`.
5. `os.stat()` cagrilari korumasizdi; medya kosumdan sonra silinir veya
   okunamazsa traceback uretilirdi. Artik kontrollu FAIL doner.
"""

import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ORTAK YARDIMCILAR: cozumleme ve fatal desen listesi cover-art kapisiyla
# TEK kaynaktan gelir; ikinci bir kopya tutulmaz (bkz. NATIVE-001).
from cover_art_native_child import (NATIVE_FAILURE_PATTERNS,  # noqa: E402
                                    decode_stream, marker_tokens)
# Medya sozlesmesi (uzanti listesi + ad kodlamasi) child ile ORTAK; iki
# yerde kopyalanmaz. Modul `mpv`/`PyQt6` yuklemez.
from native_media_contract import (MEDIA_EXTENSIONS,  # noqa: E402
                                   MEDIA_FIELD_PREFIX,
                                   decode_media_basename,
                                   encode_media_basename, is_supported_media)
from native_windows_exception_contract import (  # noqa: E402
    LUAJIT_RUNTIME_ERROR_TRACE, complete_luajit_faulthandler_reports)

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "native_player_shutdown_child.py")

#: Kapanis kabulunde ayrica aranan desenler.
#:
#: Ortak liste `Traceback (most recent call last)` tam ifadesini arar;
#: burada DAHA GENIS `Traceback` yeterlidir. `PYTHON_EXCEPTION` ise bu
#: child'in kendi `sys.excepthook` isaretidir ve yalnizca burada anlamli
#: oldugu icin ortak listeye TASINMADI.
EXTRA_FAILURE_PATTERNS = ("Traceback", "PYTHON_EXCEPTION")

#: stdout VE stderr icinde aranan tum desenler.
FAILURE_PATTERNS = tuple(dict.fromkeys(
    tuple(NATIVE_FAILURE_PATTERNS) + EXTRA_FAILURE_PATTERNS))

#: Kabul edilen TEK RESULTS satiri.
EXPECTED_RESULTS = "RESULTS: failures=none stop=1 terminate=1"

#: Canli kabulu ACIK olarak isteyen degisken. `MLC_NATIVE_SMOKE` BILEREK
#: kullanilmaz: o degisken baska native testleri de acar ve bu kabulun
#: yanlislikla calismasina yol acardi.
OPT_IN_VARIABLE = "MLC_NATIVE_SHUTDOWN_ACCEPTANCE"
OPT_IN_VALUE = "1"
EXTERNAL_SUBTITLE_VARIABLE = "MLC_NATIVE_SHUTDOWN_EXTERNAL_SUBTITLE"

DEFAULT_TIMEOUT_S = 180


# =====================================================================
# Ortam kapisi ve medya dogrulamasi
# =====================================================================

def native_acceptance_requested(env=None):
    """Canli kabul ACIK olarak istendi mi?

    Yalnizca tam `"1"` degeri sayilir; `0`, bos, `true`, `yes` gibi
    degerler istek DEGILDIR.
    """
    environment = os.environ if env is None else env
    return environment.get(OPT_IN_VARIABLE, "") == OPT_IN_VALUE


def resolve_media(env=None):
    """Medya YALNIZ ilan edilen iki ortam degiskeninden gelir.

    Genis disk taramasi YAPILMAZ; uretilmis bir WAV veya baska bir dosya
    turu gercek video yerine KULLANILMAZ.
    """
    environment = os.environ if env is None else env

    direct = environment.get("MLC_NATIVE_TEST_VIDEO", "")
    if direct:
        # Yol verilmis ama gecerli video degilse SESSIZCE klasore
        # dusulmez; kullanici yanlis dosyayi verdigini gormelidir.
        return direct if is_supported_media(direct) else ""

    folder = environment.get("MLC_NATIVE_VIDEO_DIR", "")
    if not folder or not os.path.isdir(folder):
        return ""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return ""
    for name in names:
        path = os.path.join(folder, name)
        if is_supported_media(path):
            return path
    return ""


def live_run_blockers(env=None):
    """Canli kosumun neden calismadigini aciklayan sebep listesi.

    Bos liste = kosum istendi ve ortam hazir.
    """
    environment = os.environ if env is None else env
    reasons = []
    if not native_acceptance_requested(environment):
        reasons.append(
            f"canli kosum ISTENMEDI: {OPT_IN_VARIABLE}="
            f"{environment.get(OPT_IN_VARIABLE, '')!r} (beklenen "
            f"{OPT_IN_VALUE!r})")
    if not resolve_media(environment):
        reasons.append(
            "gecerli gercek medya yok: MLC_NATIVE_TEST_VIDEO / "
            "MLC_NATIVE_VIDEO_DIR bir .mkv/.mp4 dosyasi gostermiyor")
    return reasons


# =====================================================================
# Medya degismezligi (kontrollu hata)
# =====================================================================

def media_stat(path):
    """Medyanin SALT-OKUNUR kimligi: boyut ve mtime_ns.

    Buyuk dosyanin hash'i BILEREK hesaplanmaz. Dosya yoksa veya
    okunamazsa `None` doner; cagiran traceback ALMAZ.
    """
    try:
        info = os.stat(path)
    except OSError:
        return None
    return {"path": os.path.abspath(path),
            "size": info.st_size,
            "mtime_ns": info.st_mtime_ns}


def media_stat_problems(before, after):
    """Medya koşumdan ETKILENMEMIS olmali; eksik stat de FAIL'dir."""
    problems = []
    if before is None:
        problems.append(
            "medya kosum ONCESI okunamadi (silinmis, tasinmis veya erisim "
            "yok); degismezlik olculemedi")
    if after is None:
        problems.append(
            "medya kosum SONRASI okunamadi (silinmis, tasinmis veya erisim "
            "yok); degismezlik olculemedi")
    if before is None or after is None:
        return problems
    for field in ("path", "size", "mtime_ns"):
        if before.get(field) != after.get(field):
            problems.append(
                f"medya dosyasi kosumdan ETKILENDI: {field} "
                f"{before.get(field)!r} -> {after.get(field)!r}")
    return problems


def timeout_problems(seconds):
    """Timeout KONTROLLU bir FAIL'dir; sessizce yesile donmez."""
    return [f"child {seconds} sn icinde bitmedi (timeout); kapanis yolu "
            "tamamlanmadi"]


# =====================================================================
# Marker dilbilgisi
# =====================================================================

def _finite_non_negative(text):
    """Sonlu ve negatif olmayan sayi mi? `nan`/`inf`/negatif HAYIR."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _no_fields(marker, fields, context):
    if fields:
        return [f"{marker} deger ALMAZ; fazla alan: {' '.join(fields)!r}"]
    return []


def _exact_field(expected):
    """TAM bir alan ve TAM beklenen deger."""
    def check(marker, fields, context):
        if len(fields) != 1:
            return [f"{marker} TAM bir deger ister ({expected}); "
                    f"{len(fields)} alan bulundu: {' '.join(fields)!r}"]
        if fields[0] != expected:
            return [f"{marker} degeri beklentiyi karsilamiyor "
                    f"(beklenen {expected}): {fields[0]!r}"]
        return []
    return check


def _media_basename(marker, fields, context):
    """TAM bir `media_b64=` alani; kayipsiz cozulmeli ve beklenenle ayni olmali.

    Ad BOSLUKLA ayrisan bir alanda TASINMAZ: `kayıt 01.mkv` gecerli bir
    dosya adidir ve eski protokolde iki alan sayilip kabulu DUSURUYORDU.
    """
    if len(fields) != 1:
        return [f"{marker} TAM bir medya alani ister "
                f"({MEDIA_FIELD_PREFIX}<base64>); {len(fields)} alan "
                f"bulundu: {' '.join(fields)!r}"]
    field = fields[0]
    if not field.startswith(MEDIA_FIELD_PREFIX):
        return [f"{marker} medya alani {MEDIA_FIELD_PREFIX!r} ile "
                f"baslamiyor: {field!r}"]

    name = decode_media_basename(field[len(MEDIA_FIELD_PREFIX):])
    if name is None:
        return [f"{marker} medya adi cozulemedi (gecersiz Base64 veya "
                f"gecersiz UTF-8): {field!r}"]
    if not name:
        return [f"{marker} medya adi BOS"]

    expected = context.get("expected_basename")
    if expected is not None and name != expected:
        return [f"{marker} beklenen medyayi bildirmiyor "
                f"(beklenen {expected!r}): {name!r}"]
    return []


def _media_ready(marker, fields, context):
    """TAM olarak `duration=<sayi> position=<sayi>`; en az biri > 0."""
    if len(fields) != 2:
        return [f"{marker} TAM iki alan ister (duration=, position=); "
                f"{len(fields)} alan bulundu: {' '.join(fields)!r}"]

    problems = []
    values = {}
    for prefix, field in zip(("duration=", "position="), fields):
        if not field.startswith(prefix):
            problems.append(f"{marker} alani {prefix!r} ile baslamiyor: "
                            f"{field!r}")
            continue
        value = _finite_non_negative(field[len(prefix):])
        if value is None:
            problems.append(
                f"{marker} {prefix}degeri sonlu ve negatif olmayan bir sayi "
                f"degil: {field!r}")
            continue
        values[prefix] = value

    if problems:
        return problems
    if not any(value > 0 for value in values.values()):
        return [f"{marker} medyanin ACILDIGINI kanitlamiyor: "
                f"{' '.join(fields)} (duration ve position ikisi de 0)"]
    return []


#: Zorunlu marker'lar ve kesin dogrulayicilari. `FREE` KALDIRILDI.
MARKER_GRAMMAR = (
    ("MARK_FAULTHANDLER_ENABLED", _no_fields),
    ("MARK_PLAYER_CREATED", _media_basename),
    ("MARK_MEDIA_OPEN_REQUESTED", _media_basename),
    ("MARK_MEDIA_READY", _media_ready),
    ("MARK_CLOSE_REQUESTED", _no_fields),
    ("MARK_STOP_CALLED", _exact_field("count=1")),
    ("MARK_TERMINATE_CALLED", _exact_field("count=1")),
    ("MARK_CLOSE_ACCEPTED", _exact_field("visible=False")),
    ("MARK_APP_EXEC_RETURNED", _exact_field("code=0")),
    ("MARK_THREADS_AFTER", _exact_field("count=0")),
    ("MARK_MAIN_RETURNED", _exact_field("0")),
)

REQUIRED_MARKERS = tuple(name for name, _ in MARKER_GRAMMAR)

#: Ayni medyayi bildirmesi gereken marker cifti.
MEDIA_MARKERS = ("MARK_PLAYER_CREATED", "MARK_MEDIA_OPEN_REQUESTED")


def evaluate_shutdown_result(returncode, stdout, stderr,
                             expected_basename=None,
                             require_external_subtitle=False):
    """Child sonucunu degerlendirir. Doner: sorun listesi (bos = TAMAM).

    SAF fonksiyondur: dosya okumaz, surec calistirmaz, urun kodu veya
    gercek MPV yuklemez. `expected_basename` verilirse iki medya
    marker'inin GERCEKTEN o dosyayi bildirdigi dogrulanir.
    """
    problems = []
    stdout = decode_stream(stdout)
    stderr = decode_stream(stderr)
    context = {"expected_basename": expected_basename}

    # 1. Hata izleri ONCE: genel fatal desenleri exit 0 AKLAMAZ. Yalniz
    # CPython VEH'nin tam LuaJIT raporu, exit 0 ile birlikte stderr taramasindan
    # cikarilir; marker/RESULTS bozuksa asagidaki kontroller yine FAIL verir.
    handled_luajit_stderr = (
        returncode == 0 and complete_luajit_faulthandler_reports(stderr))
    stderr_to_scan = "" if handled_luajit_stderr else stderr
    for stream_name, text in (("stdout", stdout),
                              ("stderr", stderr_to_scan)):
        scan_text = text
        if LUAJIT_RUNTIME_ERROR_TRACE in scan_text:
            problems.append(
                f"{stream_name} icinde LuaJIT LUA_ERRRUN SEH izi var "
                f"({LUAJIT_RUNTIME_ERROR_TRACE!r}); bu akistan handled/"
                "second-chance ayrimi yapilamaz ve kabul edilmez")
            scan_text = scan_text.replace(LUAJIT_RUNTIME_ERROR_TRACE, "")
        for pattern in FAILURE_PATTERNS:
            if pattern in scan_text:
                problems.append(
                    f"{stream_name} icinde fatal iz var ({pattern!r}); "
                    "exit 0 olsa bile kabul edilmez")

    # 2. Genel stderr TAMAMEN bos olmali. Tam CPython/LuaJIT VEH raporu disinda
    # "zararsiz uyari" muafiyeti YOK.
    if stderr_to_scan.strip():
        problems.append(
            f"stderr bos DEGIL ({len(stderr)} karakter); ilk turda hicbir "
            f"uyari muaf tutulmaz: {stderr.strip()[:400]!r}")

    if returncode != 0:
        problems.append(f"child exit code {returncode} (beklenen 0)")

    # 3. Marker'lar: tam bir kez, gecerli zaman damgasi ve KESIN sozdizimi.
    for marker, validator in MARKER_GRAMMAR:
        found = [parts for parts in marker_tokens(stdout)
                 if parts[0] == marker]
        if not found:
            problems.append(f"eksik marker: {marker}")
            continue
        if len(found) > 1:
            problems.append(
                f"tekil marker {len(found)} kez yazilmis: {marker}")

        tail = found[0][1:]
        timestamp_problems = _timestamp_problems(marker, tail)
        if timestamp_problems:
            problems.extend(timestamp_problems)
            continue
        problems.extend(validator(marker, tail[1:], context))

    if require_external_subtitle:
        subtitle_lines = [line.strip() for line in stdout.splitlines()
                          if line.strip().startswith(
                              "MARK_SUBTITLE_APPLIED ")]
        required_fields = ("applied=True", "external_tracks=1",
                           "sid_is_ours=True", "visibility=True")
        if len(subtitle_lines) != 1:
            problems.append(
                "MARK_SUBTITLE_APPLIED tam bir kez bulunmali; "
                f"bulunan={len(subtitle_lines)}")
        else:
            parts = subtitle_lines[0].split()
            if (len(parts) != 6 or
                    _finite_non_negative(parts[1][2:]
                                         if parts[1].startswith("t=")
                                         else None) is None or
                    tuple(parts[2:]) != required_fields):
                problems.append(
                    "MARK_SUBTITLE_APPLIED dis altyazinin secili ve "
                    f"gorunur oldugunu kanitlamiyor: {subtitle_lines[0]!r}")

    # 4. Iki medya marker'i AYNI dosyayi bildirmeli.
    reported = {}
    for marker in MEDIA_MARKERS:
        fields = _fields(stdout, marker)
        if len(fields) != 1 or not fields[0].startswith(MEDIA_FIELD_PREFIX):
            continue
        name = decode_media_basename(fields[0][len(MEDIA_FIELD_PREFIX):])
        if name is not None:
            reported[marker] = name
    if len(reported) == len(MEDIA_MARKERS) and len(set(reported.values())) > 1:
        problems.append(
            f"medya marker'lari birbiriyle ayrisiyor: {reported}")

    # 5. Kapanis SIRASI: stop, terminate'ten ONCE.
    stop_at = _first_index(stdout, "MARK_STOP_CALLED")
    term_at = _first_index(stdout, "MARK_TERMINATE_CALLED")
    if stop_at is not None and term_at is not None and stop_at > term_at:
        problems.append(
            "kapanis sirasi yanlis: MARK_STOP_CALLED, MARK_TERMINATE_CALLED "
            "marker'indan SONRA")

    # 6. RESULTS satiri TAM olarak beklenen olmali.
    results = [line.strip() for line in stdout.splitlines()
               if line.strip().startswith("RESULTS")]
    if not results:
        problems.append("RESULTS satiri yok")
    elif len(results) > 1:
        problems.append(f"RESULTS {len(results)} kez yazilmis")
    if results and results[0] != EXPECTED_RESULTS:
        problems.append(
            f"RESULTS beklenenden farkli: {results[0]!r} "
            f"(beklenen {EXPECTED_RESULTS!r})")

    return problems


def _timestamp_problems(marker, tail):
    """Her marker `t=<sonlu, negatif olmayan sayi>` tasir.

    `float()` donusumu YETMEZ: `nan`, `inf`, `-inf` ve negatif degerler
    donusur ama gecerli bir zaman damgasi DEGILDIR.
    """
    if not tail or not tail[0].startswith("t="):
        return [f"{marker} zaman damgasi (`t=`) tasimiyor: "
                f"{' '.join(tail)!r}"]
    if _finite_non_negative(tail[0][2:]) is None:
        return [f"{marker} zaman damgasi sonlu ve negatif olmayan bir sayi "
                f"degil: {tail[0]!r}"]
    return []


def _fields(stdout, marker):
    """Marker'in `t=` sonrasi alanlari (ilk esleşen satir)."""
    for parts in marker_tokens(stdout):
        if parts[0] == marker:
            tail = parts[1:]
            return tail[1:] if tail and tail[0].startswith("t=") else tail
    return []


def _first_index(stdout, marker):
    for index, parts in enumerate(marker_tokens(stdout)):
        if parts[0] == marker:
            return index
    return None


def run_native_shutdown(video, timeout=DEFAULT_TIMEOUT_S, env=None,
                        require_external_subtitle=False):
    """Child'i **BIR KEZ** calistirir. Doner: (problems, ayrinti sozlugu).

    OPT-IN KAPISI BURADADIR, pytest dugumunde DEGIL. Onceki surumde izin
    denetimi yalnizca test fonksiyonundaydi; bu fonksiyonu dogrudan cagiran
    baska bir kod (ya da bir mutasyon) gecerli bir `.mkv` vererek ACIK IZIN
    OLMADAN surec baslatabiliyordu. Ayni kaza sinifi 18 Agustos 2026'da bir
    kez gerceklesti; kapi artik gercek `subprocess` sinirindadir.

    Cikti BAYT olarak yakalanir (`text=True` YOK); cozumleme acik ve hata
    toleranslidir. Izin yoksa veya medya gecersizse child HIC baslatilmaz.
    Medya yalnizca SALT-OKUNUR acilir; kosum oncesi/sonrasi stat
    karsilastirilir ve stat okunamazsa kontrollu FAIL doner — child IKINCI
    kez CALISTIRILMAZ.

    `env` verilirse child ortami DA ondan turer; boylece testler global
    ortami kirletmez ve global ortam test davranisini degistirmez.
    """
    environment = dict(os.environ if env is None else env)

    # Kosumu ENGELLEYEN sartlar: hepsi subprocess'ten ONCE olculur.
    blockers = []
    if not native_acceptance_requested(environment):
        blockers.append(
            f"canli kosum ISTENMEDI: {OPT_IN_VARIABLE}="
            f"{environment.get(OPT_IN_VARIABLE, '')!r} (beklenen "
            f"{OPT_IN_VALUE!r}); child BASLATILMADI")
    if not is_supported_media(video):
        blockers.append(
            f"gecerli gercek medya degil (yalniz {MEDIA_EXTENSIONS} "
            f"dosyalari): {video!r}")

    if blockers:
        stat_now = media_stat(video) if video else None
        return blockers, {"returncode": None, "stdout": "", "stderr": "",
                          "raw_stdout": b"", "raw_stderr": b"",
                          "media_before": stat_now, "media_after": stat_now}

    before = media_stat(video)
    if before is None:
        return (["medya kosum ONCESI okunamadi; child BASLATILMADI"],
                {"returncode": None, "stdout": "", "stderr": "",
                 "raw_stdout": b"", "raw_stderr": b"",
                 "media_before": None, "media_after": None})

    environment["MLC_NATIVE_TEST_VIDEO"] = os.path.abspath(video)
    if require_external_subtitle:
        environment[EXTERNAL_SUBTITLE_VARIABLE] = "1"
    else:
        environment.pop(EXTERNAL_SUBTITLE_VARIABLE, None)
    environment.pop("QT_QPA_PLATFORM", None)

    try:
        result = subprocess.run(
            [sys.executable, CHILD],
            capture_output=True, timeout=timeout, env=environment,
            cwd=os.path.dirname(os.path.dirname(CHILD)))
    except subprocess.TimeoutExpired as expired:
        after = media_stat(video)
        problems = timeout_problems(timeout)
        problems.extend(media_stat_problems(before, after))
        raw_stdout = bytes(expired.stdout or b"")
        raw_stderr = bytes(expired.stderr or b"")
        return problems, {"returncode": None,
                          "stdout": decode_stream(raw_stdout),
                          "stderr": decode_stream(raw_stderr),
                          "raw_stdout": raw_stdout,
                          "raw_stderr": raw_stderr,
                          "media_before": before, "media_after": after}

    after = media_stat(video)
    raw_stdout = bytes(result.stdout or b"")
    raw_stderr = bytes(result.stderr or b"")
    problems = evaluate_shutdown_result(
        result.returncode, raw_stdout, raw_stderr,
        expected_basename=os.path.basename(video),
        require_external_subtitle=require_external_subtitle)
    problems.extend(media_stat_problems(before, after))
    return problems, {"returncode": result.returncode,
                      "stdout": decode_stream(raw_stdout),
                      "stderr": decode_stream(raw_stderr),
                      "raw_stdout": raw_stdout,
                      "raw_stderr": raw_stderr,
                      "media_before": before, "media_after": after}
