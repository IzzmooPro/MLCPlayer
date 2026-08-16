"""Gercek Windows + gercek MPV ile NORMAL kullanici kapanisi olcumu.

Child MPV'yi kendi DURDURMAZ ve SONLANDIRMAZ: kapanis yalnizca urunun
`player.close()` yolundan baslar. `stop`/`terminate` metotlari sadece
cagri SIRASINI ve SAYISINI kaydetmek icin saydam bir vekil (proxy) ile
sarilir.

Marker'lar:
    MARK_PLAYER_CREATED
    MARK_MEDIA_OPEN_REQUESTED
    MARK_MEDIA_READY
    MARK_CLOSE_REQUESTED
    MARK_STOP_CALLED
    MARK_TERMINATE_CALLED
    MARK_CLOSE_ACCEPTED
    MARK_APP_EXEC_RETURNED
    RESULTS: failures=...

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
import os
import shutil
import sys
import tempfile
import time

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
# MPV native `wid` yuzeyi GERCEK pencere ister.
os.environ.pop("QT_QPA_PLATFORM", None)

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

from PyQt6.QtCore import QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.player import MPVPlayer  # noqa: E402


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


def resolve_video():
    """Once `MLC_NATIVE_TEST_VIDEO`; yoksa `MLC_NATIVE_VIDEO_DIR` KOKUNDEKI
    ilk mkv/mp4. Hicbiri verilmemisse "" doner (calistiran kisinin kendi
    medya klasoru betige GOMULMEZ)."""
    if VIDEO_PATH and os.path.isfile(VIDEO_PATH):
        return VIDEO_PATH
    folder = os.environ.get("MLC_NATIVE_VIDEO_DIR", "")
    if not folder:
        return ""
    try:
        names = os.listdir(folder)
    except OSError:
        return ""
    for name in sorted(names):
        if os.path.splitext(name)[1].lower() not in (".mkv", ".mp4"):
            continue
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path):
                return path
        except OSError:
            continue
    return ""


def main():
    video = resolve_video()
    if not video:
        print("RESULTS: failures=no_real_video (ORTAM EKSIGI)", flush=True)
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_MAIN_RETURNED", 2)
        os._exit(2)

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      WORKSPACE)

    install_call_recorder()
    app = QApplication([sys.argv[0]])
    player = MPVPlayer()
    player.resize(1280, 720)
    player.show()
    app.processEvents()
    mark("MARK_PLAYER_CREATED", os.path.basename(video))

    state = {"ready": False, "closed": False, "deadline": 0.0}

    def request_media():
        player.open_path(video)
        mark("MARK_MEDIA_OPEN_REQUESTED", os.path.basename(video))
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
            QTimer.singleShot(400, close_player)
            return
        if time.time() > state["deadline"]:
            poll.stop()
            failures.append("media_not_ready")
            mark("MARK_MEDIA_READY", "TIMEOUT")
            QTimer.singleShot(0, close_player)

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
    for required in ("MARK_PLAYER_CREATED", "MARK_MEDIA_OPEN_REQUESTED",
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
