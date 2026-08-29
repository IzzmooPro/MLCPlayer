# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Gercek Windows + gercek MPV ile NORMAL kullanici kapanisi olcumu.

Child MPV'yi kendi DURDURMAZ ve SONLANDIRMAZ: kapanis yalnizca urunun
`player.close()` yolundan baslar. `stop`/`terminate` metotlari sadece
cagri SIRASINI ve SAYISINI kaydetmek icin saydam bir vekil (proxy) ile
sarilir.

Marker'lar:
    MARK_FAULTHANDLER_ENABLED
    MARK_PLAYER_CREATED
    MARK_MEDIA_OPEN_REQUESTED
    MARK_MEDIA_READY
    MARK_SUBTITLE_APPLIED (yalniz dis altyazi senaryosunda)
    MARK_CLOSE_REQUESTED
    MARK_STOP_CALLED
    MARK_TERMINATE_CALLED
    MARK_CLOSE_ACCEPTED
    MARK_APP_EXEC_RETURNED
    MARK_THREADS_AFTER
    RESULTS: failures=...
    MARK_MAIN_RETURNED

Kabul: stop=1, terminate=1, stop marker'i terminate'ten ONCE, eksik marker
yok, exit code 0. Child, uygulamanin `main.py` giris noktasi gibi Qt event
loop'u dondukten ve urun kapanis sozlesmesini dogruladiktan sonra
`os._exit(ret)` kullanir. Python yorumlayici finalizasyonu bu kabulun parcasi
degildir; Qt + libmpv + `audio-device-list` icin ayri bir tani riskidir.

Guvenlik:
- Yalniz KENDI surecini yonetir; baska uygulama acilmaz/kapatilmaz.
- Video dosyasi READ-ONLY acilir; degistirilmez, tasinmaz, silinmez.
- QSettings gecici dizine yonlendirilir.
"""
import faulthandler
import os
import shutil
import sys
import tempfile
import threading
import time

# GORUNURLUK ONCE: PyQt, mpv ve `app.player` IMPORT EDILMEDEN ONCE acilir.
# Bir native istisna (ornegin `0xe24c4a02`) importun kendisinde veya
# libmpv'nin baslattigi bir thread'de olusabilir; faulthandler sonradan
# acilirsa o iz KAYBOLUR. Hedef acikca `sys.stderr`dir ve ebeveyn stderr'i
# BAYT olarak yakalar.
faulthandler.enable(file=sys.stderr, all_threads=True)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
# MPV native `wid` yuzeyi GERCEK pencere ister.
os.environ.pop("QT_QPA_PLATFORM", None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ORTAK sozlesme: uzanti listesi ve ad kodlamasi TEK kaynaktan gelir.
# Bu modul `mpv`/`PyQt6` yuklemez, bu yuzden burada guvenle import edilir.
from native_media_contract import (MEDIA_FIELD_PREFIX,  # noqa: E402
                                   encode_media_basename,
                                   is_supported_media)
from native_mpv_trace_contract import (configure_script_ablation,  # noqa: E402
                                       configure_trace_mode,
                                       script_bisection_profile)

VIDEO_PATH = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
READY_TIMEOUT_S = float(os.environ.get("MLC_READY_TIMEOUT", "25"))
WORKSPACE = tempfile.mkdtemp(prefix="mlc-shutdown-")

START = time.time()
failures = []
calls = []
markers = []


def mark(name, extra=""):
    markers.append(name)
    print(f"{name} t={time.time() - START:.2f} {extra}".rstrip(), flush=True)


def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    print("PYTHON_EXCEPTION " + "".join(
        traceback.format_exception(exc_type, exc_value, exc_tb)).strip(),
        flush=True)
    sys.exit(90)


sys.excepthook = _excepthook

# Gorunurlugun ACIK oldugu ebeveyne de bildirilir; kabul bu marker'i arar.
mark("MARK_FAULTHANDLER_ENABLED")

from PyQt6.QtCore import QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import app.player as player_module  # noqa: E402
from app import subtitle_service  # noqa: E402

MPVPlayer = player_module.MPVPlayer

EXTERNAL_SUBTITLE_REQUESTED = (
    os.environ.get("MLC_NATIVE_SHUTDOWN_EXTERNAL_SUBTITLE") == "1")
SUBTITLE_PATH = os.path.join(WORKSPACE, "shutdown-external-subtitle.srt")
SUBTITLE_BYTES = (
    b"1\n00:00:01,000 --> 00:00:05,000\nMLC shutdown timing\n")


def install_call_recorder():
    """`mpv.MPV.stop/terminate` cagrilarini SINIF duzeyinde kaydeder.

    Vekil nesne kullanilmaz: olcum, urunun tuttugu MPV nesnesine fazladan
    referans EKLEMEZ; boylece kapanis sirasi olcumun kendisinden
    etkilenmez. Metotlar birebir gercek metoda yonlendirir.
    """
    import mpv as mpv_module

    real_stop = mpv_module.MPV.stop
    real_terminate = mpv_module.MPV.terminate

    def recording_stop(self, *args, **kwargs):
        calls.append("stop")
        mark("MARK_STOP_CALLED", f"count={calls.count('stop')}")
        return real_stop(self, *args, **kwargs)

    def recording_terminate(self, *args, **kwargs):
        calls.append("terminate")
        mark("MARK_TERMINATE_CALLED", f"count={calls.count('terminate')}")
        return real_terminate(self, *args, **kwargs)

    mpv_module.MPV.stop = recording_stop
    mpv_module.MPV.terminate = recording_terminate


def external_subtitle_tracks(mpv_player):
    """Return tracks backed by this child's private temporary SRT."""
    wanted = os.path.normcase(os.path.abspath(SUBTITLE_PATH))
    matches = []
    for track in (mpv_player.track_list or []):
        if not isinstance(track, dict) or track.get("type") != "sub":
            continue
        filename = track.get("external-filename")
        if (filename and
                os.path.normcase(os.path.abspath(str(filename))) == wanted):
            matches.append(track)
    return matches


def resolve_video():
    """Once `MLC_NATIVE_TEST_VIDEO`; yoksa `MLC_NATIVE_VIDEO_DIR` KOKUNDEKI
    ilk mkv/mp4. Hicbiri verilmemisse "" doner (calistiran kisinin kendi
    medya klasoru betige GOMULMEZ).

    FAIL-CLOSED: child DOGRUDAN calistirilsa bile yalniz gercek
    `.mkv`/`.mp4` kabul edilir. Uzanti listesi burada TEKRARLANMAZ;
    ebeveyn kapisiyla ayni `is_supported_media()` kullanilir.
    """
    if VIDEO_PATH:
        # Yanlis dosya verildiginde SESSIZCE klasore dusulmez.
        return VIDEO_PATH if is_supported_media(VIDEO_PATH) else ""
    folder = os.environ.get("MLC_NATIVE_VIDEO_DIR", "")
    if not folder:
        return ""
    try:
        names = os.listdir(folder)
    except OSError:
        return ""
    for name in sorted(names):
        path = os.path.join(folder, name)
        if is_supported_media(path):
            return path
    return ""


def main():
    video = resolve_video()
    if not video:
        print("RESULTS: failures=no_real_video (ORTAM EKSIGI)", flush=True)
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_MAIN_RETURNED", 2)
        os._exit(2)

    # PDB'siz tani YALNIZ iki acik opt-in + gecerli yeni `.log` hedefiyle
    # kurulur. Normal child kosumunda `MPV_CONFIG` aynen kalir. Trace
    # secenekleri ortak saf sozlesmeden gelir; burada kopyalanmaz.
    trace_field, trace_problems = configure_trace_mode(
        player_module, video, env=os.environ)
    if trace_problems:
        for problem in trace_problems:
            print("TRACE_CONFIG_ERROR " + problem, flush=True)
        print("RESULTS: failures=trace_config_invalid stop=0 terminate=0",
              flush=True)
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_MAIN_RETURNED", 2)
        os._exit(2)
    if trace_field:
        mark("MARK_TRACE_CONFIGURED", trace_field)

    ablation_applied, ablation_problems = configure_script_ablation(
        player_module, env=os.environ)
    if ablation_problems:
        for problem in ablation_problems:
            print("SCRIPT_ABLATION_CONFIG_ERROR " + problem, flush=True)
        print("RESULTS: failures=script_ablation_invalid stop=0 terminate=0",
              flush=True)
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_MAIN_RETURNED", 2)
        os._exit(2)
    if ablation_applied:
        mark("MARK_SCRIPT_ABLATION_CONFIGURED")
        bisection_profile, _ = script_bisection_profile(os.environ)
        if bisection_profile is not None:
            mark("MARK_SCRIPT_BISECTION_CONFIGURED",
                 "profile=" + bisection_profile)

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      WORKSPACE)

    install_call_recorder()
    app = QApplication([sys.argv[0]])
    player = MPVPlayer()
    player.resize(1280, 720)
    player.show()
    app.processEvents()
    # Ad BOSLUKLA ayrisan bir alanda TASINMAZ: `kayıt 01.mkv` gibi
    # gecerli adlar protokolu bozardi. Kayipsiz, bosluksuz alan.
    media_field = MEDIA_FIELD_PREFIX + encode_media_basename(
        os.path.basename(video))
    mark("MARK_PLAYER_CREATED", media_field)

    state = {"ready": False, "closed": False, "deadline": 0.0}

    def request_media():
        player.open_path(video)
        mark("MARK_MEDIA_OPEN_REQUESTED", media_field)
        state["deadline"] = time.time() + READY_TIMEOUT_S
        poll.start(100)

    def poll_ready():
        try:
            duration = float(getattr(player.mpv_player, "duration", 0) or 0)
            position = float(getattr(player.mpv_player, "time_pos", 0) or 0)
        except Exception:
            duration = position = 0.0
        if duration > 0 or position > 0:
            poll.stop()
            state["ready"] = True
            mark("MARK_MEDIA_READY",
                 f"duration={duration:.2f} position={position:.2f}")
            QTimer.singleShot(0, prepare_close_scenario)
            return
        if time.time() > state["deadline"]:
            poll.stop()
            failures.append("media_not_ready")
            mark("MARK_MEDIA_READY", "TIMEOUT")
            QTimer.singleShot(0, close_player)

    def prepare_close_scenario():
        """Optionally reproduce the user's external-subtitle close path."""
        if not EXTERNAL_SUBTITLE_REQUESTED:
            QTimer.singleShot(400, close_player)
            return

        applied = False
        tracks = []
        chosen = []
        visible = False
        try:
            store = subtitle_service.SubtitleStore()
            store.save(SUBTITLE_PATH, SUBTITLE_BYTES)
            session = subtitle_service.SubtitleSession(store=store)
            applied = session.apply(
                player, SUBTITLE_PATH,
                wait=lambda: (app.processEvents(), time.sleep(0.02)))
            app.processEvents()
            tracks = external_subtitle_tracks(player.mpv_player)
            selected = player.mpv_player.sid
            chosen = [track for track in tracks
                      if track.get("id") == selected]
            visible = bool(player.mpv_player.sub_visibility)
        except Exception as exc:
            failures.append(
                f"subtitle_apply_exception={type(exc).__name__}")

        mark("MARK_SUBTITLE_APPLIED",
             f"applied={bool(applied)} external_tracks={len(tracks)} "
             f"sid_is_ours={bool(chosen)} visibility={visible}")
        if not applied:
            failures.append("subtitle_not_applied")
        if len(tracks) != 1:
            failures.append(f"subtitle_track_count={len(tracks)}")
        if not chosen:
            failures.append("subtitle_wrong_track_selected")
        if not visible:
            failures.append("subtitle_not_visible")
        QTimer.singleShot(400, close_player)

    def close_player():
        # KAPANIS URUN YOLUNDAN baslar: stop/terminate burada CAGRILMAZ.
        mark("MARK_CLOSE_REQUESTED")
        accepted = player.close()
        state["closed"] = bool(accepted)
        if accepted:
            mark("MARK_CLOSE_ACCEPTED", f"visible={player.isVisible()}")
        else:
            failures.append("close_not_accepted")
        QTimer.singleShot(0, app.quit)

    poll = QTimer()
    poll.timeout.connect(poll_ready)
    QTimer.singleShot(0, request_media)

    exec_code = app.exec()
    mark("MARK_APP_EXEC_RETURNED", f"code={exec_code}")

    # Kapanistan ve `app.exec()` donusunden SONRA yasayan MPV thread'leri.
    # Kabul icin sayi KESINLIKLE 0 olmalidir: sonlandirilmis bir MPV'nin
    # olay thread'i hayatta kalirsa, surec `os._exit()` ile kapanana kadar
    # libmpv geri cagirmalari devam edebilir.
    alive = [t.name for t in threading.enumerate()
             if "MPV" in t.name.upper()]
    mark("MARK_THREADS_AFTER", f"count={len(alive)}")
    if alive:
        failures.append(f"mpv_threads_alive={len(alive)}")

    stops = calls.count("stop")
    terminates = calls.count("terminate")
    if stops != 1:
        failures.append(f"stop_count={stops}")
    if terminates != 1:
        failures.append(f"terminate_count={terminates}")
    if calls[:2] != ["stop", "terminate"]:
        failures.append(f"order={calls}")
    if player.mpv_player is not None:
        failures.append("mpv_reference_not_released")
    for required in ("MARK_FAULTHANDLER_ENABLED", "MARK_THREADS_AFTER",
                     "MARK_PLAYER_CREATED", "MARK_MEDIA_OPEN_REQUESTED",
                     "MARK_MEDIA_READY", "MARK_CLOSE_REQUESTED",
                     "MARK_STOP_CALLED", "MARK_TERMINATE_CALLED",
                     "MARK_CLOSE_ACCEPTED", "MARK_APP_EXEC_RETURNED"):
        if required not in markers:
            failures.append(f"missing_marker={required}")

    print(f"RESULTS: failures={','.join(failures) or 'none'} "
          f"stop={stops} terminate={terminates}", flush=True)

    # Uretim giris noktasi `app.exec()` dondukten sonra Python/Qt/libmpv
    # nesnelerini yorumlayici finalizasyonuna sokmaz; dogrudan `os._exit(ret)`
    # uygular. Child da ayni noktada, ayni politikayla cikar. Marker ve sonuc
    # satiri flush edildigi icin ebeveyn butun kapanis kanitini okuyabilir.
    exit_code = 1 if failures else 0
    shutil.rmtree(WORKSPACE, ignore_errors=True)
    mark("MARK_MAIN_RETURNED", exit_code)
    os._exit(exit_code)


main()
