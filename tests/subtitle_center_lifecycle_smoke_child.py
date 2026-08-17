# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in GERCEK urun kabugu Altyazi Merkezi YASAM DONGUSU smoke'u.

Gercek `MPVPlayer`, gercek libmpv, gercek menu eylemi; yalnizca OpenSubtitles
ISTEMCISI sahtedir ve arama testin serbest biraktigi ana kadar bekler.

Olculen senaryolar:
  1. Gecikmis arama SIRASINDA dialogu kapat -> controller draining'e gecer
  2. Medyayi degistir ve hemen yeniden ac -> yeni generation, yeni hash
  3. Eski arama serbest birakilir -> yeni dialoga YAZMAZ, draining bosalir
  4. Aktif worker varken player.close() -> kapanis ERTELENIR, UI donmaz
  5. Sonda: sifir dialog, sifir draining, thread sizintisi yok

GUVENLIK: gercek aga cikilmaz, kullanici medya dizinine yazilmaz, gercek
HKCU ve Credential Manager kirletilmez.
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import wave

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.pop("QT_QPA_PLATFORM", None)

WORKSPACE = tempfile.mkdtemp(prefix="mlc-center-life-")

from PyQt6.QtCore import QEvent, QSettings, Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import subtitle_center_composition as composition  # noqa: E402
from app.player import MPVPlayer  # noqa: E402
from app.subtitle_center import SubtitleCenterDialog  # noqa: E402
from app.subtitle_center_composition import (  # noqa: E402
    SubtitleCenterCoordinator)
from app.subtitle_settings import SubtitleSettingsStore  # noqa: E402

# `--mode timeout`: kapanis deadline'i dolsa bile pencere kapanmamali.
TIMEOUT_MODE = "--mode" in sys.argv and "timeout" in sys.argv
# `--mode connection`: ayar penceresi kapanisi ve baglanti testi drenaji.
CONNECTION_MODE = "--mode" in sys.argv and "connection" in sys.argv

RESULT = {"file_id": 7135238, "name": "Uzak.Ad", "language": "tr",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba\n"
failures = []


class SlowClient:
    def __init__(self, gate):
        self.release = gate["release"]
        self.entered = gate["entered"]
        self.search_calls = 0

    def search(self, **kwargs):
        # NOT: plan hash adimiyla baslayabilir
        # ({"moviehash", "moviebytesize", "languages"}); `query` ZORUNLU DEGIL.
        self.search_calls += 1
        self.entered.set()
        self.release.wait(25)
        return [RESULT]

    def download_link(self, file_id):
        return "https://dl.opensubtitles.com/download/a.srt"

    def fetch(self, url):
        return SRT


class FakeCredentialStore:
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


def make_media(name, seconds=30, rate=8000):
    """NOT: `opensubtitles_hash` en az 128 KiB ister (bas+son 64'er KiB).
    Daha kucuk dosyada hash HIC hesaplanmaz; bu bir urun kusuru degildir."""
    path = os.path.join(WORKSPACE, name)
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


def pump_until(app, predicate, timeout_ms=15000):
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


def main():
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      WORKSPACE)
    media_a = make_media("MLC.Life.A.S01E01.1080p-TEST.wav")
    media_b = make_media("MLC.Life.B.2026.2160p-TEST.wav")
    mark("MARK_WORKSPACE", WORKSPACE)

    threads_before = threading.active_count()
    mark("MARK_MODE", "connection" if CONNECTION_MODE
         else ("timeout" if TIMEOUT_MODE else "release"))
    app = QApplication([sys.argv[0]])
    player = MPVPlayer()
    player.show()
    app.processEvents()

    gate = {"release": threading.Event(), "entered": threading.Event()}
    store = SubtitleSettingsStore(
        settings=QSettings(os.path.join(WORKSPACE, "center.ini"),
                           QSettings.Format.IniFormat),
        credentials=FakeCredentialStore())
    coordinator = SubtitleCenterCoordinator(
        player, client_factory=lambda **kwargs: SlowClient(gate),
        settings_store=store)
    player._subtitle_center = coordinator

    player.open_path(media_a)
    deadline = time.time() + 20
    while time.time() < deadline and not (player.mpv_player.duration or 0):
        app.processEvents()
        time.sleep(0.05)
    mark("MARK_PLAY", f"duration={player.mpv_player.duration}")

    action = getattr(player, "subtitle_find_action", None)
    if action is None:
        failures.append("menu_action_missing")
        print("RESULTS: failures=menu_action_missing", flush=True)
        return 1

    if CONNECTION_MODE:
        return run_connection_branch(app, player, coordinator, gate)

    # --- 1) Gecikmis arama sirasinda kapat ---
    action.trigger()
    pump(app, 300)
    first_dialog = coordinator.dialog
    first_generation = coordinator.media_generation()
    started_search = first_dialog.search_button.click()
    entered = False
    end = time.time() + 8
    while time.time() < end and not entered:
        app.processEvents()
        entered = gate["entered"].wait(0.05)
    mark("MARK_SEARCH_START",
         f"entered={entered} status={first_dialog.status_text()!r}")
    if not entered:
        failures.append("search_worker_did_not_start")
    first_dialog.close()
    pump_until(app, lambda: coordinator.dialog is None, 5000)
    mark("MARK_RETIRED",
         f"draining={coordinator.draining_count()} idle={coordinator.is_idle()}")
    if coordinator.draining_count() != 1:
        failures.append(f"draining={coordinator.draining_count()}")
    if coordinator.is_idle():
        failures.append("idle_while_worker_runs")

    # --- 2) Medyayi degistir, hemen yeniden ac ---
    player.open_path(media_b)
    deadline = time.time() + 20
    while time.time() < deadline and not (player.mpv_player.duration or 0):
        app.processEvents()
        time.sleep(0.05)
    action.trigger()
    pump(app, 300)
    second_dialog = coordinator.dialog
    second_generation = coordinator.media_generation()
    mark("MARK_REOPENED",
         f"new_generation={second_generation != first_generation} "
         f"media_is_b={os.path.basename(second_dialog.media['file_name'])}")
    if second_generation == first_generation:
        failures.append("generation_not_advanced")
    if os.path.abspath(second_dialog.media["file_name"]) != os.path.abspath(media_b):
        failures.append("dialog_media_not_switched")

    got_hash = pump_until(
        app, lambda: bool(second_dialog.media.get("movie_hash")), 10000)
    mark("MARK_HASH",
         f"computed={got_hash} value_len={len(second_dialog.media.get('movie_hash') or '')}")
    if not got_hash:
        failures.append("new_media_hash_missing")

    # --- 3) Eski aramayi serbest birak: yeni dialoga YAZMAMALI ---
    cards_before = len(second_dialog.result_cards())
    gate["release"].set()
    drained = pump_until(app, lambda: coordinator.draining_count() == 0, 15000)
    pump(app, 300)
    cards_after = len(second_dialog.result_cards())
    mark("MARK_DRAINED",
         f"drained={drained} draining={coordinator.draining_count()} "
         f"cards_before={cards_before} cards_after={cards_after}")
    if not drained:
        failures.append("draining_never_emptied")
    if cards_after != cards_before:
        failures.append("stale_worker_wrote_into_new_dialog")

    # --- 4) Aktif worker varken player kapanisi ERTELENMELI ---
    gate["release"].clear()
    gate["entered"].clear()
    second_dialog.search_button.click()
    if not gate["entered"].wait(8):
        failures.append("second_search_did_not_start")

    if TIMEOUT_MODE:
        # ZAMAN ASIMI KOLU: deadline COK kisa; dolsa bile kapanma OLMAMALI.
        composition.CLOSE_TIMEOUT_MS = 300

    ticks = {"n": 0}
    ui_timer = QTimer()
    ui_timer.setTimerType(Qt.TimerType.PreciseTimer)
    ui_timer.setInterval(10)
    ui_timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    ui_timer.start()

    # Kanonik sira: once mpv durdurulur, sonra pencere kapatilir.
    try:
        player.mpv_player.stop()
    except Exception as exc:
        print(f"STOP_WARNING {exc}", flush=True)
    started = time.monotonic()
    player.close()
    blocked = time.monotonic() - started
    still_open = player.isVisible()
    mark("MARK_CLOSE_DEFERRED",
         f"blocked={blocked:.3f}s still_open={still_open}")
    if blocked >= 1.0:
        failures.append(f"close_blocked_ui={blocked:.2f}s")
    if not still_open:
        failures.append("close_not_deferred_while_worker_ran")

    if TIMEOUT_MODE:
        # Deadline'in (300 ms) COKTAN dolmasi icin bekle; UI islemeye devam.
        pump(app, 1500)
        mpv_owned = player.mpv_player is not None
        mark("MARK_AFTER_DEADLINE",
             f"visible={player.isVisible()} mpv_owned={mpv_owned} "
             f"draining={coordinator.draining_count()} "
             f"idle={coordinator.is_idle()} ui_ticks={ticks['n']}")
        if not player.isVisible():
            failures.append("closed_after_deadline_while_worker_ran")
        if not mpv_owned:
            failures.append("mpv_released_after_deadline")
        if coordinator.is_idle():
            failures.append("work_untracked_after_deadline")
        if ticks["n"] <= 3:
            failures.append("ui_frozen_after_deadline")

    pump(app, 200)
    gate["release"].set()
    closed = pump_until(app, lambda: not player.isVisible(), 15000)
    ui_timer.stop()
    mark("MARK_CLOSED",
         f"closed={closed} ui_ticks={ticks['n']} "
         f"dialogs={len(dialogs(app))} draining={coordinator.draining_count()}")
    if not closed:
        failures.append("deferred_close_never_completed")
    if ticks["n"] <= 3:
        failures.append(f"ui_frozen_during_close ticks={ticks['n']}")

    # --- 5) Artik yok ---
    pump(app, 500)
    leftover = len(dialogs(app))
    if leftover:
        failures.append(f"dialog_leak={leftover}")
    if coordinator.draining_count():
        failures.append(f"draining_leak={coordinator.draining_count()}")
    if not coordinator.is_idle():
        failures.append("coordinator_not_idle")
    threads_after = threading.active_count()
    mark("MARK_THREADS", f"before={threads_before} after={threads_after}")
    if threads_after > threads_before:
        failures.append(f"thread_leak={threads_after - threads_before}")

    try:
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_WORKSPACE_CLEANED", str(not os.path.exists(WORKSPACE)))
    except Exception as exc:
        print(f"CLEANUP_WARNING {exc}", flush=True)

    print(f"RESULTS: failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


def run_connection_branch(app, player, coordinator, gate):
    """Ayar penceresi + baglanti testi drenaj kolu."""
    action = getattr(player, "subtitle_find_action", None)
    action.trigger()
    pump(app, 300)
    if coordinator.dialog is None:
        failures.append("center_not_opened")
        print(f"RESULTS: failures={','.join(failures)}", flush=True)
        return 1

    coordinator.open_settings()
    pump(app, 300)
    settings = coordinator.settings_dialog
    if settings is None:
        failures.append("settings_not_opened")
        print(f"RESULTS: failures={','.join(failures)}", flush=True)
        return 1

    ticks = {"n": 0}
    ui_timer = QTimer()
    ui_timer.setTimerType(Qt.TimerType.PreciseTimer)
    ui_timer.setInterval(10)
    ui_timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    ui_timer.start()

    # 1) Gecikmis baglanti testi baslat
    settings.api_key_field.setText("SMOKE-API-KEY")
    settings.connection_test_requested.emit()
    if not gate["entered"].wait(8):
        failures.append("connection_test_did_not_start")
    mark("MARK_TEST_STARTED", f"entered={gate['entered'].is_set()}")

    # 2) Ayar penceresini kapat: UI BLOKE OLMAMALI
    started = time.monotonic()
    settings.close()
    blocked = time.monotonic() - started
    pump(app, 300)
    mark("MARK_SETTINGS_CLOSED",
         f"blocked={blocked:.3f}s draining={coordinator.draining_count()} "
         f"idle={coordinator.is_idle()} ui_ticks={ticks['n']}")
    if blocked >= 0.25:
        failures.append(f"settings_close_blocked={blocked:.2f}s")
    if coordinator.is_idle():
        failures.append("running_tester_untracked")
    if coordinator.draining_count() < 1:
        failures.append("tester_not_in_draining")
    if ticks["n"] <= 3:
        failures.append("ui_frozen_during_settings_close")

    # 3) Hemen yeniden ac; eski sonuc yeni pencereye YAZMAMALI
    coordinator.open_settings()
    pump(app, 300)
    fresh = coordinator.settings_dialog
    before_status = fresh.status_text() if fresh else "<none>"
    mark("MARK_SETTINGS_REOPENED", f"visible={bool(fresh and fresh.isVisible())}")

    # 4) Player kapanisi iste: calisan test varken kapanmamali
    try:
        player.mpv_player.stop()
    except Exception as exc:
        print(f"STOP_WARNING {exc}", flush=True)
    player.close()
    pump(app, 400)
    mpv_owned = player.mpv_player is not None
    mark("MARK_CLOSE_DEFERRED",
         f"visible={player.isVisible()} mpv_owned={mpv_owned}")
    if not player.isVisible():
        failures.append("closed_while_test_running")
    if not mpv_owned:
        failures.append("mpv_released_while_test_running")

    # 5) Serbest birak: tek sefer kapanmali
    gate["release"].set()
    closed = pump_until(app, lambda: not player.isVisible(), 15000)
    pump(app, 400)
    ui_timer.stop()
    after_status = "<destroyed>"
    try:
        after_status = fresh.status_text() if fresh else "<none>"
    except RuntimeError:
        after_status = "<destroyed>"
    mark("MARK_CLOSED",
         f"closed={closed} ui_ticks={ticks['n']} "
         f"draining={coordinator.draining_count()} "
         f"dialogs={len(dialogs(app))}")
    # Yeni pencereye BAYAT sonuc yazilmamali. Pencere kapanis sirasinda yok
    # edilmisse ("<destroyed>") zaten hicbir widget'a dokunulmamis demektir.
    mark("MARK_STALE_RESULT",
         f"dialog={'destroyed' if after_status == '<destroyed>' else 'alive'} "
         f"wrote_into_new_dialog="
         f"{after_status not in (before_status, '<destroyed>')}")
    if not closed:
        failures.append("deferred_close_never_completed")
    if after_status != before_status and after_status != "<destroyed>":
        failures.append("stale_result_wrote_into_new_dialog")
    if coordinator.draining_count():
        failures.append(f"draining_leak={coordinator.draining_count()}")
    if dialogs(app):
        failures.append(f"dialog_leak={len(dialogs(app))}")

    shutil.rmtree(WORKSPACE, ignore_errors=True)
    mark("MARK_WORKSPACE_CLEANED", str(not os.path.exists(WORKSPACE)))
    print(f"RESULTS: failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
