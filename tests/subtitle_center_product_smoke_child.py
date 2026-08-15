"""Opt-in GERCEK urun kabugu Altyazi Merkezi smoke'u.

Gercek `MPVPlayer` penceresi (main.py ile ayni kabuk), gercek menu eylemi,
gercek libmpv. Yalnizca OpenSubtitles ISTEMCISI sahtedir.

GUVENLIK KURALI
---------------
- GERCEK OpenSubtitles agina CIKILMAZ (sahte istemci).
- Kullanicinin medya dizinine YAZILMAZ: oynatilan medya ve hedef SRT
  benzersiz bir %TEMP% dizinindedir.
- Gercek HKCU kirletilmez: QSettings INI olarak %TEMP%'e yonlendirilir.
- Gercek Credential Manager kirletilmez: sahte kimlik deposu enjekte edilir.

MLC_NATIVE_SMOKE=1 verilmeden hicbir Qt/MPV nesnesi olusturmaz.
"""
import os
import shutil
import sys
import tempfile
import threading
import time

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
# MPV native `wid` yuzeyi GERCEK pencere ister.
os.environ.pop("QT_QPA_PLATFORM", None)

WORKSPACE = tempfile.mkdtemp(prefix="mlc-center-smoke-")
os.environ["MLC_NATIVE_SETTINGS"] = WORKSPACE

from PyQt6.QtCore import QEvent, QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import subtitle_service as service  # noqa: E402
from app.player import MPVPlayer  # noqa: E402
from app.subtitle_center import SubtitleCenterDialog  # noqa: E402
from app.subtitle_center_composition import (  # noqa: E402
    SubtitleCenterCoordinator)
from app.subtitle_settings import SubtitleSettingsStore  # noqa: E402

VIDEO = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
MEDIA_NAME = "MLC.Center.Smoke.S01E01.1080p-TEST"
SRT = ("1\n00:00:01,000 --> 00:00:05,000\nMLC urun smoke altyazisi\n\n"
       "2\n00:00:06,000 --> 00:00:09,000\nIkinci satir\n").encode("utf-8")
# NOT: `language` GERCEK API gibi DIL KODU olmali; cekirdek
# `filter_results` kodla eler, gorunen etiketle degil.
RESULT = {"file_id": 7135238, "name": "Uzak.Ad.turkish", "language": "tr",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}
failures = []


class FakeClient:
    """Ag YOK; gecerli gorunumlu OpenSubtitles yanitlarini taklit eder."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.search_calls = 0
        self.download_calls = 0

    def search(self, **kwargs):
        # Plan hash adimiyla baslayabilir; `query` ZORUNLU DEGIL.
        self.search_calls += 1
        return [RESULT]

    def download_link(self, file_id):
        self.download_calls += 1
        return "https://dl.opensubtitles.com/download/mlc-center-smoke.srt"

    def fetch(self, url):
        return SRT


class FakeCredentialStore:
    """Gercek Credential Manager'a DOKUNMAZ."""

    def __init__(self):
        self.secrets = {"api": "SMOKE-API-KEY"}

    def set_api_key(self, value):
        self.secrets["api"] = value
        return "credential_manager"

    def get_api_key(self):
        return self.secrets.get("api")

    def delete_api_key(self):
        self.secrets.pop("api", None)
        return True

    def set_password(self, username, value):
        self.secrets["pw"] = value
        return "credential_manager"

    def get_password(self, username):
        return self.secrets.get("pw")

    def delete_password(self, username):
        self.secrets.pop("pw", None)
        return True


def mark(name, extra=""):
    print(f"{name} {extra}".rstrip(), flush=True)


def generate_wav(path, seconds=5, rate=8000):
    import wave

    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * (rate * seconds))
    return path


def pump(app, milliseconds):
    end = time.time() + milliseconds / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)


def pump_until(app, predicate, timeout_ms=8000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def dialogs(app):
    return [w for w in app.topLevelWidgets()
            if isinstance(w, SubtitleCenterDialog)]


def snapshot_media_dir(video):
    directory = os.path.dirname(os.path.abspath(video))
    state = {}
    for entry in os.scandir(directory):
        if entry.is_file():
            info = entry.stat()
            state[entry.name] = (info.st_size, int(info.st_mtime))
    return directory, state


def main():
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      WORKSPACE)

    real_video = bool(VIDEO and os.path.isfile(VIDEO))
    before_state = None
    if real_video:
        # Gercek video KOPYALANMAZ; hedef SRT'nin kullanici dizinine
        # dusmemesi icin oynatilan yol da %TEMP% icinde olmalidir. Bu yuzden
        # gercek video yalnizca "medya dizini degismedi" kanitinda kullanilir.
        _dir, before_state = snapshot_media_dir(VIDEO)
        mark("MARK_MEDIA_SNAPSHOT", f"files={len(before_state)}")
    media = generate_wav(os.path.join(WORKSPACE, MEDIA_NAME + ".wav"))
    target = service.subtitle_target_path(media)
    mark("MARK_WORKSPACE", WORKSPACE)
    mark("MARK_TARGET", target)
    if os.path.dirname(os.path.abspath(target)) != os.path.abspath(WORKSPACE):
        print("RESULTS: failures=target_outside_workspace", flush=True)
        return 1

    threads_before = threading.active_count()
    app = QApplication(sys.argv)
    player = MPVPlayer()
    player.show()
    app.processEvents()

    # Sahte istemci + izole ayar deposu ENJEKTE edilir; menu eylemi bundan
    # sonra ayni koordinatoru kullanir.
    client = FakeClient()
    store = SubtitleSettingsStore(
        settings=QSettings(os.path.join(WORKSPACE, "center.ini"),
                           QSettings.Format.IniFormat),
        credentials=FakeCredentialStore())
    player._subtitle_center = SubtitleCenterCoordinator(
        player, client_factory=lambda **kwargs: client, settings_store=store)

    player.open_path(media)
    deadline = time.time() + 20
    while time.time() < deadline and not (player.mpv_player.duration or 0):
        app.processEvents()
        time.sleep(0.05)
    mark("MARK_PLAY", f"duration={player.mpv_player.duration}")

    try:
        # 1) Menu eyleminden ac
        action = getattr(player, "subtitle_find_action", None)
        mark("MARK_MENU_ACTION", f"exists={action is not None}")
        if action is None:
            failures.append("menu_action_missing")
            raise RuntimeError("menu action yok")
        action.trigger()
        pump(app, 400)
        dialog = player._subtitle_center.dialog
        mark("MARK_OPENED",
             f"visible={bool(dialog and dialog.isVisible())} "
             f"count={len(dialogs(app))}")
        if dialog is None or not dialog.isVisible():
            failures.append("dialog_not_visible")
        if len(dialogs(app)) != 1:
            failures.append(f"dialog_count={len(dialogs(app))}")

        # 2) Tek pencere sahipligi: tekrar tetikleme yeni pencere uretmemeli
        action.trigger()
        pump(app, 300)
        mark("MARK_SINGLE_WINDOW", f"count={len(dialogs(app))}")
        if len(dialogs(app)) != 1:
            failures.append("second_window_created")
        if dialog.parent() is not player:
            failures.append("dialog_not_owned_by_player")

        # 3) Aktivasyon: player one alinabilmeli, dialog onde ASILI kalmamali
        from PyQt6.QtCore import Qt

        topmost = bool(dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        player.activateWindow()
        player.raise_()
        pump(app, 400)
        player_active = player.isActiveWindow()
        dialog.activateWindow()
        dialog.raise_()
        pump(app, 400)
        dialog_active = dialog.isActiveWindow()
        mark("MARK_ACTIVATION",
             f"topmost={topmost} player_activated={player_active} "
             f"dialog_activated={dialog_active}")
        if topmost:
            failures.append("dialog_is_topmost")

        # 4) Arama
        dialog.search_button.click()
        pump_until(app, lambda: bool(dialog.result_cards()), 8000)
        cards = dialog.result_cards()
        mark("MARK_SEARCH",
             f"client_calls={client.search_calls} cards={len(cards)}")
        if not cards:
            failures.append("no_results")
        else:
            dialog.select_result(cards[0])

        # 5) Indir + uygula (gecici dizine)
        if cards:
            dialog.apply_button.click()
            coordinator = player._subtitle_center
            pump_until(app, lambda: coordinator.is_idle(), 12000)
            pump(app, 300)
            mpv = player.mpv_player
            external = [t for t in (mpv.track_list or [])
                        if isinstance(t, dict)
                        and t.get("external-filename")]
            mark("MARK_APPLY",
                 f"downloads={client.download_calls} "
                 f"saved={os.path.isfile(target)} "
                 f"external_tracks={len(external)} sid={mpv.sid} "
                 f"visibility={mpv.sub_visibility} "
                 f"status={dialog.status_text()!r}")
            if not os.path.isfile(target):
                failures.append("srt_not_saved")
            if len(external) != 1:
                failures.append(f"external_tracks={len(external)}")
            elif mpv.sid != external[0].get("id"):
                failures.append("wrong_track_selected")
            if not mpv.sub_visibility:
                failures.append("subtitles_not_visible")

        # 6) Kapat / yeniden ac
        dialog.close()
        pump_until(app, lambda: player._subtitle_center.dialog is None, 4000)
        mark("MARK_CLOSED", f"count={len(dialogs(app))}")
        action.trigger()
        pump(app, 400)
        reopened = player._subtitle_center.dialog
        visible = [d for d in dialogs(app) if d.isVisible()]
        mark("MARK_REOPENED",
             f"visible={bool(reopened and reopened.isVisible())} "
             f"visible_count={len(visible)}")
        if reopened is None or not reopened.isVisible():
            failures.append("reopen_failed")
        if len(visible) != 1:
            failures.append(f"reopen_visible_count={len(visible)}")

        # Ikinci arama cift baglanti uretmemeli
        calls_before = client.search_calls
        reopened.search_button.click()
        pump_until(app, lambda: player._subtitle_center.is_idle(), 8000)
        delta = client.search_calls - calls_before
        mark("MARK_REOPEN_SEARCH", f"delta={delta}")
        if delta > 1:
            failures.append(f"double_signal delta={delta}")
    finally:
        # 7) Player kapanisi: TEK sahipli kanonik sira (stop -> close).
        #    Ham `player.close()` cagrilirsa mpv once durdurulmadan terminate
        #    ediliyor ve surec teardown'da 0xC0000005 uretiyor; bu davranis
        #    Altyazi Merkezi'nden bagimsizdir.
        try:
            service.shutdown_player(player)
        except Exception as exc:
            print(f"CLOSE_WARNING {exc}", flush=True)
        pump(app, 600)
        mark("MARK_PLAYER_CLOSED", f"dialogs={len(dialogs(app))}")

    leftover_dialogs = len(dialogs(app))
    if leftover_dialogs:
        failures.append(f"dialog_leak={leftover_dialogs}")
    threads_after = threading.active_count()
    mark("MARK_THREADS", f"before={threads_before} after={threads_after}")
    if threads_after > threads_before:
        failures.append(f"thread_leak={threads_after - threads_before}")

    if before_state is not None:
        _dir, after_state = snapshot_media_dir(VIDEO)
        if after_state != before_state:
            failures.append("media_dir_modified")
        mark("MARK_MEDIA_UNCHANGED", str(after_state == before_state))
    else:
        mark("MARK_MEDIA_UNCHANGED", "n/a (medya %TEMP% icinde uretildi)")

    try:
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_WORKSPACE_CLEANED", str(not os.path.exists(WORKSPACE)))
    except Exception as exc:
        print(f"CLEANUP_WARNING {exc}", flush=True)

    print(f"RESULTS: failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
