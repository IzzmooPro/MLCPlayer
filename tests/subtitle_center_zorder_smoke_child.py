# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in GERCEK Windows z-order / pencere sahipligi smoke'u.

Kullanicinin ekran goruntusundeki hata: cinematic oynatma katmani Altyazi
Merkezi'nin USTUNE ciziliyordu. Katman ayri bir top-level Tool penceresidir
ve `_player_owns_foreground()` yalnizca SUREC (PID) sahipligini olctugu icin
aynı surecteki dialog one geldiginde bile kendini diriltip `raise_()`
ediyordu.

Olculenler:
  CENTER_ABOVE_PLAYER
  PLAYBACK_OVERLAY_HIDDEN_WHILE_CENTER_ACTIVE
  SETTINGS_ABOVE_CENTER
  FOREIGN_APP_ABOVE_ALL_PLAYER_WINDOWS
  CENTER_RESTORED
  WINDOW_STAYS_ON_TOP
  CHILD_CLEANED

GUVENLIK: Notepad veya kullanicinin uygulamalari ACILMAZ; testin kendi Qt
penceresi ayri surecte calisir ve YALNIZ kaydedilen PID try/finally ile
temizlenir. Genis surec taramasi YOKTUR. Gercek aga cikilmaz.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from types import SimpleNamespace

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.pop("QT_QPA_PLATFORM", None)

WORKSPACE = tempfile.mkdtemp(prefix="mlc-zorder-")

from PyQt6.QtCore import QEvent, QSettings, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.player import MPVPlayer  # noqa: E402
from app.subtitle_center_composition import (  # noqa: E402
    SubtitleCenterCoordinator)
from app.subtitle_settings import SubtitleSettingsStore  # noqa: E402

failures = []
user32 = ctypes.WinDLL("user32", use_last_error=True)


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


def mark(name, value=""):
    print(f"{name}={value}" if value != "" else name, flush=True)


def make_media(name, seconds=30, rate=8000):
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


# --- Z-order olcumu (kucuk index = daha ONDE) ---

GW_HWNDNEXT = 2


def zorder_map():
    order = {}
    hwnd = user32.GetTopWindow(None)
    index = 0
    while hwnd:
        order[int(hwnd)] = index
        index += 1
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
    return order


def above(order, first, second):
    """`first` z-order'da `second`'un ONUNDE mi?"""
    if first not in order or second not in order:
        return None
    return order[first] < order[second]


def hwnd_of(widget):
    try:
        return int(widget.winId())
    except Exception:
        return 0


def visible(hwnd):
    return bool(user32.IsWindowVisible(hwnd)) if hwnd else False


def main():
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      WORKSPACE)
    media = make_media("MLC.ZOrder.S01E01.1080p-TEST.wav")
    mark("MARK_WORKSPACE", WORKSPACE)

    app = QApplication([sys.argv[0]])
    player = MPVPlayer()
    player.show()
    app.processEvents()

    store = SubtitleSettingsStore(
        settings=QSettings(os.path.join(WORKSPACE, "center.ini"),
                           QSettings.Format.IniFormat),
        credentials=FakeCredentialStore())
    coordinator = SubtitleCenterCoordinator(
        player, client_factory=lambda **kwargs: SimpleNamespace(),
        settings_store=store)
    player._subtitle_center = coordinator

    player.open_path(media)
    deadline = time.time() + 20
    while time.time() < deadline and not (player.mpv_player.duration or 0):
        app.processEvents()
        time.sleep(0.05)
    mark("MARK_PLAY", f"duration={player.mpv_player.duration}")

    foreign = None
    try:
        # Katmani gorunur hale getir: hata ancak katman canliyken olculur.
        player.video_frame.show_overlay_for_interaction()
        pump(app, 400)
        overlay = player.video_frame.control_overlay
        mark("MARK_OVERLAY_BEFORE",
             f"visible={overlay is not None and overlay.isVisible()}")

        # --- 1) Altyazi Merkezi'ni ac ---
        action = getattr(player, "subtitle_find_action", None)
        if action is None:
            failures.append("menu_action_missing")
            raise RuntimeError("menu action yok")
        action.trigger()
        pump(app, 700)
        center = coordinator.dialog
        if center is None:
            failures.append("center_not_opened")
            raise RuntimeError("dialog acilmadi")

        overlay_hidden = not (overlay is not None and overlay.isVisible())
        mark("PLAYBACK_OVERLAY_HIDDEN_WHILE_CENTER_ACTIVE", str(overlay_hidden))
        if not overlay_hidden:
            failures.append("overlay_visible_over_center")

        # Katman o an zaten gizli olabilir (ses dosyasinda etkilesim yok);
        # bu yuzden MEKANIZMA dogrudan olculur: bastirma acik olmali ve
        # owner olaylari katmani DIRILTMEMELI.
        suppressed = player.video_frame.overlay_suppressed()
        mark("OVERLAY_SUPPRESSION_ACTIVE", str(suppressed))
        if not suppressed:
            failures.append("overlay_not_suppressed")
        player.video_frame.show_overlay_for_interaction()
        player.video_frame.update_overlay_geometry()
        pump(app, 400)
        revived = overlay is not None and overlay.isVisible()
        mark("OVERLAY_REVIVED_BY_OWNER_EVENTS", str(revived))
        if revived:
            failures.append("overlay_revived_while_center_open")

        order = zorder_map()
        center_hwnd = hwnd_of(center)
        player_hwnd = hwnd_of(player)
        overlay_hwnd = hwnd_of(overlay) if overlay is not None else 0
        center_above = above(order, center_hwnd, player_hwnd)
        mark("CENTER_ABOVE_PLAYER", str(bool(center_above)))
        if not center_above:
            failures.append("center_below_player")
        if overlay_hwnd and visible(overlay_hwnd):
            if above(order, overlay_hwnd, center_hwnd):
                failures.append("overlay_above_center")

        stays_on_top = bool(
            center.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

        # --- 2) Ayar penceresi ---
        coordinator.open_settings()
        pump(app, 600)
        settings = coordinator.settings_dialog
        settings_hwnd = hwnd_of(settings) if settings else 0
        order = zorder_map()
        settings_above = above(order, settings_hwnd, center_hwnd)
        mark("SETTINGS_ABOVE_CENTER", str(bool(settings_above)))
        if not settings_above:
            failures.append("settings_below_center")
        if settings is not None:
            stays_on_top = stays_on_top or bool(
                settings.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        mark("WINDOW_STAYS_ON_TOP", str(stays_on_top))
        if stays_on_top:
            failures.append("stays_on_top_used")

        # --- 3) BASKA uygulama one gelince hicbir pencere ustte kalmamali ---
        child_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "foreign_app_window_child.py")
        foreign = subprocess.Popen([sys.executable, child_path],
                                   stdout=subprocess.PIPE, text=True)
        mark("MARK_FOREIGN_PID", str(foreign.pid))
        foreign_hwnd = 0
        end = time.time() + 15
        while time.time() < end and not foreign_hwnd:
            line = foreign.stdout.readline()
            if line.startswith("FOREIGN_HWND="):
                foreign_hwnd = int(line.split("=", 1)[1].strip())
            app.processEvents()
        pump(app, 1200)

        order = zorder_map()
        ours = [h for h in (player_hwnd, center_hwnd, settings_hwnd,
                            overlay_hwnd) if h and visible(h)]
        results = [above(order, foreign_hwnd, h) for h in ours]
        foreign_top = bool(foreign_hwnd) and all(bool(r) for r in results)
        mark("FOREIGN_APP_ABOVE_ALL_PLAYER_WINDOWS", str(foreign_top))
        if not foreign_top:
            failures.append(f"player_window_above_foreign windows={len(ours)}")

        # --- 4) Geri donuldugunde dogru dialog aktif olmali ---
        center.raise_()
        center.activateWindow()
        pump(app, 800)
        restored = center.isVisible() and QApplication.activeWindow() in (
            center, coordinator.settings_dialog)
        mark("CENTER_RESTORED", str(bool(restored)))
        if not restored:
            failures.append("center_not_restored")

        # --- 5) Kapaninca katman geri gelmeli ---
        if coordinator.settings_dialog is not None:
            coordinator.settings_dialog.close()
            pump(app, 300)
        center.close()
        pump(app, 600)
        mark("MARK_OVERLAY_SUPPRESSED_AFTER_CLOSE",
             str(player.video_frame.overlay_suppressed()))
        if player.video_frame.overlay_suppressed():
            failures.append("overlay_still_suppressed_after_close")
    except Exception as exc:
        failures.append(f"exception={type(exc).__name__}")
        print(f"SMOKE_ERROR {type(exc).__name__}", flush=True)
    finally:
        cleaned = True
        if foreign is not None:
            # YALNIZ kaydedilen PID; genis surec taramasi YOK.
            try:
                foreign.terminate()
                foreign.wait(timeout=10)
            except Exception:
                try:
                    foreign.kill()
                    foreign.wait(timeout=10)
                except Exception:
                    cleaned = False
            try:
                if foreign.stdout is not None:
                    foreign.stdout.close()
            except Exception:
                pass
        mark("CHILD_CLEANED", str(cleaned))
        if not cleaned:
            failures.append("foreign_child_not_cleaned")

        from app import subtitle_service as service

        try:
            service.shutdown_player(player)
        except Exception as exc:
            print(f"CLOSE_WARNING {exc}", flush=True)
        pump(app, 500)
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_WORKSPACE_CLEANED", str(not os.path.exists(WORKSPACE)))

    print(f"RESULTS: failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
