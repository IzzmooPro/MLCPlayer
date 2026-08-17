# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Cover-art native senaryolari — AYRI SURECTE kosar.

NEDEN AYRI SUREC (olculdu, 17 Agustos 2026): bu senaryolar ana pytest
surecinde gercek `mpv.MPV` kuruyordu. Bagimsiz kosum **3 passed /
exit 0** verdigi halde stderr'e su dustu:

    Windows fatal exception: code 0xe24c4a02
      MPVEventHandlerThread -> mpv.py:689 _event_generator

Olay hem fixture gecisinde hem AKTIF testin `wait_until_playing()`
satirinda gorulmustur. Exit kodu yesil oldugu icin pytest bunu SESSIZCE
geciyordu.

BU MODUL `mpv`yi MODUL DUZEYINDE IMPORT ETMEZ. Ust test buradan yalnizca
saf yardimcilari alir; import etmek libmpv'yi ana surece SOKMAZ.

Cikti sozlesmesi (stdout, satir basina bir marker; TEKIL marker'lar tam
BIR KEZ yazilir):

    MARK_COVER_TRACKS <n>            kapakli senaryoda albumart parcasi
    MARK_COVER_SELECTED <0|1>        o parca SECILDI mi
    MARK_COVER_STOP                  1. senaryoda stop() dondu
    MARK_COVER_TERMINATE             1. senaryoda terminate() dondu
    MARK_NOCOVER_ALBUMART <n>        kapaksiz senaryoda albumart parcasi
    MARK_NOCOVER_AUDIO_SELECTED <0|1>
    MARK_NOCOVER_STOP                2. senaryoda stop() dondu
    MARK_NOCOVER_TERMINATE           2. senaryoda terminate() dondu
    MARK_THREADS_AFTER <n>           kapanistan sonra yasayan MPV thread'i
    MARK_DONE                        butun senaryolar bitti

HER SENARYONUN KENDI kapanis marker'lari vardir. Onceki surumde tek bir
`MARK_STOP`/`MARK_TERMINATE` cifti vardi; ikinci kapanis tamamen
kaldirilsa bile degerlendirici YESIL kalabiliyordu.

`MARK_*_ERROR` yazilirsa kosum BASARISIZDIR. Urundeki gibi `terminate()`
yine denenir, ama basarisiz cagri normal marker'la AKLANMAZ.
"""
import os
import struct
import sys
import threading
import time
import wave

#: stderr'de bunlardan biri varsa kosum BASARISIZDIR -- exit 0 olsa bile.
NATIVE_FAILURE_PATTERNS = (
    "Windows fatal exception",
    "Traceback (most recent call last)",
    "Fatal Python error",
)

def _at_least_one(value):
    return value >= 1


def _exactly(expected):
    return lambda value: value == expected


#: Her zorunlu marker'in KESIN sozdizimi.
#:
#: OLCULEN FAIL-OPEN (18 Agustos 2026, bagimsiz denetim): degerler yalnizca
#: "beklenenden farkli mi" diye bakiliyordu, BICIM hic denetlenmiyordu.
#: Bu yuzden `MARK_COVER_TRACKS abc`, `MARK_THREADS_AFTER` (degersiz) ve
#: `MARK_DONE junk` iceren bir cikti `[]` — yani TAMAM — donuyordu.
#: Artik her marker'in token sayisi ve deger dilbilgisi zorunludur.
#:
#: Bicim: marker -> None (degersiz, TAM 1 token)
#:                  veya (beklenti metni, tam sayi yuklemi) (TAM 2 token)
MARKER_GRAMMAR = (
    ("MARK_COVER_TRACKS",
     ("tam sayi >= 1 (kapak parcasi yuklenmis olmali)", _at_least_one)),
    ("MARK_COVER_SELECTED",
     ("yalniz 1 (kapak bulundu ama secilmezse video alani siyah kalir)",
      _exactly(1))),
    ("MARK_COVER_STOP", None),
    ("MARK_COVER_TERMINATE", None),
    ("MARK_NOCOVER_ALBUMART",
     ("yalniz 0 (kapaksiz dosyada albumart bildirilemez)", _exactly(0))),
    ("MARK_NOCOVER_AUDIO_SELECTED",
     ("yalniz 1 (ses parcasi secilmis olmali)", _exactly(1))),
    ("MARK_NOCOVER_STOP", None),
    ("MARK_NOCOVER_TERMINATE", None),
    ("MARK_THREADS_AFTER",
     ("yalniz 0 (kapanistan sonra MPV thread'i yasamamali)", _exactly(0))),
    ("MARK_DONE", None),
)

#: Tam BIR KEZ yazilmasi gereken marker'lar (dilbilgisiyle TEK kaynaktan).
REQUIRED_MARKERS = tuple(name for name, _ in MARKER_GRAMMAR)

#: (stop, terminate) ciftleri — her senaryo AYRI dogrulanir.
CLOSE_ORDER_PAIRS = (
    ("MARK_COVER_STOP", "MARK_COVER_TERMINATE"),
    ("MARK_NOCOVER_STOP", "MARK_NOCOVER_TERMINATE"),
)

#: Bu son ekle biten her marker kosumu DUSURUR.
ERROR_MARKER_SUFFIX = "_ERROR"

# 2x2 tek renk PNG — kapak olarak taninmasi icin yeterli.
COVER_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000020000000208020000"
    "00fdd49a730000000f49444154789c6360f8cf80000000ffff03000600"
    "0300b4b4b4b40000000049454e44ae426082")


def decode_stream(raw):
    """Child akisini ACIKCA cozer; yerel kodlamaya BIRAKILMAZ.

    `subprocess(text=True)` yerel kodlamayi kullanir (bu makinede
    `cp1254`) ve cozulemeyen bayt okuma THREAD'inde patlayip `stdout`u
    sessizce `None` yapabilir. Bayt yakalanip burada `errors="replace"`
    ile cozulur: ASCII failure desenleri bozuk kodlamada bile ARANABILIR
    kalir.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    return raw.decode("utf-8", errors="replace")


def marker_tokens(stdout):
    """Her satirin ILK token'i. `startswith` KULLANILMAZ.

    `startswith` ile `MARK_DONE_FAKE` satiri `MARK_DONE` sanilirdi ve
    `MARK_COVER_STOP` da `MARK_COVER_STOP_ERROR` ile karisirdi.
    """
    tokens = []
    for line in stdout.splitlines():
        parts = line.strip().split()
        if parts:
            tokens.append(parts)
    return tokens


def marker_values(stdout, marker):
    """`marker` ile TAM eslesen satirlarin degerleri (sirasiyla)."""
    values = []
    for parts in marker_tokens(stdout):
        if parts[0] == marker:
            values.append(parts[1] if len(parts) > 1 else "")
    return values


def evaluate_child(returncode, stdout, stderr):
    """Child sonucunu degerlendirir. Doner: sorun listesi (bos = TAMAM).

    SAF fonksiyondur: dosya okumaz, surec calistirmaz, `mpv` import
    etmez. Aralikli native olguyu tekrar kosturmadan DETERMINISTIK
    sinanabilir.
    """
    problems = []
    stdout = decode_stream(stdout)
    stderr = decode_stream(stderr)

    # 1. stderr ONCE: exit 0 ve tam marker seti native istisnayi AKLAMAZ.
    for pattern in NATIVE_FAILURE_PATTERNS:
        if pattern in stderr:
            problems.append(
                f"stderr'de native/olumcul iz var ({pattern!r}); "
                "exit 0 olsa bile kabul edilmez")

    if returncode != 0:
        problems.append(f"child exit code {returncode} (beklenen 0)")

    # 2. Hata marker'i varsa basarili cagri marker'i onu AKLAMAZ.
    for parts in marker_tokens(stdout):
        name = parts[0]
        if name.startswith("MARK_") and name.endswith(ERROR_MARKER_SUFFIX):
            problems.append(
                f"kapanis hatasi bildirildi: {' '.join(parts)}")

    # 3. Tekil marker'lar TAM BIR KEZ ve KESIN sozdiziminde.
    for marker, spec in MARKER_GRAMMAR:
        found = [parts for parts in marker_tokens(stdout)
                 if parts[0] == marker]
        if not found:
            problems.append(f"eksik marker: {marker}")
            continue
        if len(found) > 1:
            problems.append(
                f"tekil marker {len(found)} kez yazilmis: {marker}")
        problems.extend(_grammar_problems(marker, spec, found[0]))

    # 4. Kapanis SIRASI her senaryo icin AYRI (urunle uyumlu stop->terminate).
    for stop_marker, term_marker in CLOSE_ORDER_PAIRS:
        stop_at = _first_index(stdout, stop_marker)
        term_at = _first_index(stdout, term_marker)
        if stop_at is None or term_at is None:
            continue
        if stop_at > term_at:
            problems.append(
                f"kapanis sirasi yanlis: {stop_marker}, {term_marker} "
                "marker'indan SONRA")

    # Semantik sonuclar (kapak secimi, albumart, ses parcasi, thread
    # sizintisi) 3. adimdaki dilbilgisi yuklemleriyle olculur; ayri ve
    # gevsek bir ikinci denetim BILEREK BIRAKILMADI.
    return problems


def _grammar_problems(marker, spec, parts):
    """Tek bir marker satirinin token sayisi ve degerini dogrular."""
    problems = []
    value_tokens = parts[1:]

    if spec is None:
        if value_tokens:
            problems.append(
                f"{marker} deger ALMAZ; fazla token: "
                f"{' '.join(value_tokens)!r}")
        return problems

    expectation, predicate = spec
    if len(value_tokens) != 1:
        problems.append(
            f"{marker} TAM bir deger ister ({expectation}); "
            f"{len(value_tokens)} token bulundu: {' '.join(parts)!r}")
        return problems

    raw = value_tokens[0]
    try:
        value = int(raw)
    except ValueError:
        problems.append(
            f"{marker} degeri tam sayi degil ({expectation}): {raw!r}")
        return problems

    if not predicate(value):
        problems.append(f"{marker} degeri beklentiyi karsilamiyor "
                        f"({expectation}): {value}")
    return problems


def _first_index(stdout, marker):
    for index, parts in enumerate(marker_tokens(stdout)):
        if parts[0] == marker:
            return index
    return None


# --- Buradan asagisi YALNIZ child sureci calistirildiginda kullanilir ---

def mark(text):
    print(text, flush=True)


def _audio_file(folder, name="parca.wav", seconds=1):
    path = os.path.join(folder, name)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"".join(struct.pack("<h", 0)
                                    for _ in range(8000 * seconds)))
    return path


def _album_art_tracks(player):
    return [track for track in player.track_list
            if track.get("type") == "video" and track.get("albumart")]


def _shutdown(player, prefix):
    """URUNLE UYUMLU sira: once stop(), sonra terminate().

    `app/player.py::closeEvent` de bu sirayi kullanir. Hata olursa
    `MARK_<prefix>_STOP_ERROR` / `..._TERMINATE_ERROR` yazilir ve
    basarili marker YAZILMAZ; urundeki gibi `terminate()` yine denenir.
    Doner: hata olmadiysa `True`.
    """
    ok = True
    try:
        player.stop()
        mark(f"MARK_{prefix}_STOP")
    except Exception as exc:
        mark(f"MARK_{prefix}_STOP_ERROR {type(exc).__name__}")
        ok = False
    try:
        player.terminate()
        mark(f"MARK_{prefix}_TERMINATE")
    except Exception as exc:
        mark(f"MARK_{prefix}_TERMINATE_ERROR {type(exc).__name__}")
        ok = False
    return ok


def main():
    import tempfile

    # `mpv` importundan ONCE depo `bin/` dizini PATH'in BASINA gelmeli;
    # aksi halde sistemdeki baska bir libmpv yuklenebilir.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ["PATH"] = (os.path.join(root, "bin") + os.pathsep
                          + os.environ.get("PATH", ""))
    sys.path.insert(0, root)

    from app.config import MPV_CONFIG
    import mpv

    config = dict(MPV_CONFIG, vo="null", ao="null", hwdec="no")
    clean = True

    # Gecici dosyalar TEMIZLENIR (`mkdtemp` artik biraktigi icin degil).
    with tempfile.TemporaryDirectory(prefix="mlc_cover_") as workspace:
        # --- Senaryo 1: dosyanin yaninda kapak VAR ---
        album = os.path.join(workspace, "album")
        os.makedirs(album, exist_ok=True)
        with open(os.path.join(album, "cover.png"), "wb") as handle:
            handle.write(COVER_PNG)
        player = mpv.MPV(**config)
        try:
            player.play(_audio_file(album))
            player.wait_until_playing()
            time.sleep(1.0)
            tracks = _album_art_tracks(player)
            mark(f"MARK_COVER_TRACKS {len(tracks)}")
            selected = any(track.get("selected") for track in tracks)
            mark(f"MARK_COVER_SELECTED {1 if selected else 0}")
        finally:
            clean = _shutdown(player, "COVER") and clean

        # --- Senaryo 2: kapak YOK ---
        plain = os.path.join(workspace, "duz")
        os.makedirs(plain, exist_ok=True)
        player = mpv.MPV(**config)
        try:
            player.play(_audio_file(plain))
            player.wait_until_playing()
            time.sleep(0.5)
            mark(f"MARK_NOCOVER_ALBUMART {len(_album_art_tracks(player))}")
            audio_ok = any(
                track.get("type") == "audio" and track.get("selected")
                for track in player.track_list)
            mark(f"MARK_NOCOVER_AUDIO_SELECTED {1 if audio_ok else 0}")
        finally:
            clean = _shutdown(player, "NOCOVER") and clean

    # Kapanistan sonra event thread'i KALMAMALI.
    time.sleep(0.2)
    alive = [t.name for t in threading.enumerate() if "MPV" in t.name.upper()]
    mark(f"MARK_THREADS_AFTER {len(alive)}")

    mark("MARK_DONE")
    return 0 if clean else 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        # libmpv yukleyen child'lar normal finalizasyona GIRMEZ
        # (bkz. main.py ve test_child_shutdown_contract_regressions).
        os._exit(code)
