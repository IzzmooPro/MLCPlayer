# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in Windows smoke: pencere modları, köşeler ve GUI-thread tepkisi."""
import ctypes
import os
import sys
import tempfile
import threading
import time

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["PATH"] = os.path.join(ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import QPoint, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QCursor  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.player import MPVPlayer  # noqa: E402
from app.settings_store import user_settings  # noqa: E402


def pump(app, seconds):
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def physical_click(widget):
    point = widget.mapToGlobal(widget.rect().center())
    user32 = ctypes.windll.user32
    app = QApplication.instance()
    user32.SetCursorPos(point.x(), point.y())
    pump(app, 0.12)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    pump(app, 0.07)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    pump(app, 0.2)


def physical_drag(widget, local_point, delta):
    start = widget.mapToGlobal(local_point)
    app = QApplication.instance()

    def inject_drag():
        user32 = ctypes.windll.user32
        user32.SetCursorPos(start.x(), start.y())
        time.sleep(0.12)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.08)
        for step in range(1, 9):
            user32.SetCursorPos(
                start.x() + delta.x() * step // 8,
                start.y() + delta.y() * step // 8)
            time.sleep(0.025)
        user32.mouse_event(0x0004, 0, 0, 0, 0)

    # startSystemMove, fare birakilana kadar UI thread'inde yerel Windows
    # dongusune girer. Gercek kullanicinin eli gibi giris ayri thread'den
    # akmali; aksi halde smoke kendi kendini kilitler.
    worker = threading.Thread(target=inject_drag, daemon=True)
    worker.start()
    deadline = time.perf_counter() + 5.0
    while worker.is_alive() and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)
    worker.join(timeout=0.2)
    pump(app, 0.25)
    return not worker.is_alive()


def window_at_widget_center(widget):
    class POINT(ctypes.Structure):
        _fields_ = (("x", ctypes.c_long), ("y", ctypes.c_long))

    point = widget.mapToGlobal(widget.rect().center())
    user32 = ctypes.windll.user32
    user32.WindowFromPoint.argtypes = [POINT]
    user32.WindowFromPoint.restype = ctypes.c_void_p
    return int(user32.WindowFromPoint(POINT(point.x(), point.y())) or 0), point


def native_window_rect(hwnd):
    class RECT(ctypes.Structure):
        _fields_ = (("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long))

    rect = RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right - rect.left,
            rect.bottom - rect.top)


def main():
    app = QApplication.instance() or QApplication([])
    real_settings = user_settings()
    recent = real_settings.value("recent_files", []) or []
    if isinstance(recent, str):
        recent = [recent]
    media = next((item for item in recent
                  if isinstance(item, str) and os.path.isfile(item)), "")
    if not media:
        print("BLOCKED no_local_recent_media", flush=True)
        return 2

    checks = []

    def record(name, passed, evidence):
        checks.append(bool(passed))
        print(f"CHECK {'PASS' if passed else 'FAIL'} {name} :: {evidence}",
              flush=True)

    old_cursor = QCursor.pos()
    with tempfile.TemporaryDirectory(prefix="mlc-feature-smoke-") as isolated:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, isolated)
        player = MPVPlayer()
        player.setGeometry(220, 140, 1000, 650)
        player.show()
        pump(app, 0.4)

        # Başlık düğmesi iki yönde gerçek pencere durumunu değiştirmeli.
        QTest.mouseClick(player.title_bar.maximize_button,
                         Qt.MouseButton.LeftButton)
        pump(app, 0.2)
        entered = player.isMaximized()
        QTest.mouseClick(player.title_bar.maximize_button,
                         Qt.MouseButton.LeftButton)
        pump(app, 0.2)
        record("maximize_toggle", entered and not player.isMaximized(),
               f"entered={entered} restored={not player.isMaximized()}")

        # PiP yalniz normal pencereden degil, buyutulmus ve tam ekran
        # durumlarindan da kesin olarak kucuk pencereye gecmelidir.
        player.showMaximized()
        pump(app, 0.2)
        player.toggle_picture_in_picture(True)
        pump(app, 0.2)
        record("pip_from_maximized_is_compact",
               not player.isMaximized() and not player.isFullScreen()
               and player.size().width() == 480
               and player.size().height() == 270,
               f"max={player.isMaximized()} full={player.isFullScreen()} "
               f"size={player.width()}x{player.height()}")
        player.toggle_picture_in_picture(False)
        pump(app, 0.2)
        record("pip_restores_maximized",
               player.isMaximized(), f"max={player.isMaximized()}")
        player.showNormal()
        player.setGeometry(220, 140, 1000, 650)
        pump(app, 0.2)

        player.toggle_fullscreen()
        pump(app, 0.2)
        player.toggle_picture_in_picture(True)
        pump(app, 0.2)
        record("pip_from_fullscreen_is_compact",
               not player.isMaximized() and not player.isFullScreen()
               and player.size().width() == 480
               and player.size().height() == 270,
               f"max={player.isMaximized()} full={player.isFullScreen()} "
               f"size={player.width()}x{player.height()}")
        player.toggle_picture_in_picture(False)
        player.showNormal()
        player.setGeometry(220, 140, 1000, 650)
        pump(app, 0.2)

        # Gerçek Windows imleci iki alt köşeye taşınır; ürünün görünür
        # QApplication override şekli çapraz resize olmalıdır.
        expected = {
            "bottom_left": Qt.CursorShape.SizeBDiagCursor,
            "bottom_right": Qt.CursorShape.SizeFDiagCursor,
        }
        rect = player.frameGeometry()
        for name, point in (
                ("bottom_left", QPoint(rect.left() + 3, rect.bottom() - 3)),
                ("bottom_right", QPoint(rect.right() - 3, rect.bottom() - 3))):
            QCursor.setPos(point)
            pump(app, 0.18)
            player.resize_filter._refresh_resize_cursor_from_global()
            cursor = QApplication.overrideCursor()
            actual = None if cursor is None else cursor.shape()
            record(name + "_cursor", actual == expected[name],
                   f"actual={actual} expected={expected[name]}")

        # Köşe override'ını bırakıp iki yeni başlık modunu gerçek HWND'de dene.
        QCursor.setPos(player.mapToGlobal(player.rect().center()))
        pump(app, 0.15)
        QTest.mouseClick(player.title_bar.transparency_button,
                         Qt.MouseButton.LeftButton)
        pump(app, 0.1)
        popup_visible = player.title_bar.transparency_popup.isVisible()
        player.title_bar.transparency_slider.setValue(58)
        pump(app, 0.1)
        record("transparency_adjustable",
               popup_visible and abs(player.windowOpacity() - 0.58) < 0.03,
               f"popup={popup_visible} opacity={player.windowOpacity():.2f}")
        player.title_bar.transparency_slider.setValue(100)
        player.title_bar.hide_transparency_control()

        # PiP goruntusu yer tutucuyla degil, gercek video yuzeyiyle kabul
        # edilir. Ayni medya asagida dispatch suresi icin yeniden acilabilir.
        player.open_path(media)
        deadline = time.perf_counter() + 5.0
        while player.duration <= 0 and time.perf_counter() < deadline:
            pump(app, 0.05)

        physical_click(player.title_bar.picture_in_picture_button)
        pump(app, 0.2)
        hwnd = int(player.winId())
        exstyle = int(ctypes.windll.user32.GetWindowLongW(hwnd, -20))
        native_rect = native_window_rect(hwnd)
        record("picture_in_picture",
               player.picture_in_picture_enabled
               and not player.isFullScreen() and not player.isMaximized()
               and player.width() == 480 and player.height() == 270
               and native_rect is not None
               and native_rect[2:] == (480, 270)
               and not player.title_bar.isVisible()
               and player.video_frame.control_overlay.height() <= 56
               and player.video_frame.overlay_timeline.height() == 18
               and bool(exstyle & 0x00000008),
               f"enabled={player.picture_in_picture_enabled} "
               f"qt={player.width()}x{player.height()} native={native_rect} "
               f"full={player.isFullScreen()} max={player.isMaximized()} "
               f"topmost={bool(exstyle & 8)} "
               f"title={player.title_bar.isVisible()} "
               f"overlay_h={player.video_frame.control_overlay.height()}")
        physical_click(player.video_frame.overlay_pip_exit_button)
        pump(app, 0.2)
        record("picture_in_picture_initial_mouse_exit",
               not player.picture_in_picture_enabled,
               f"enabled={player.picture_in_picture_enabled}")
        player.toggle_picture_in_picture(True)
        pump(app, 0.2)
        before_drag = player.geometry()
        drag_finished = physical_drag(
            player.video_frame,
            QPoint(player.video_frame.width() // 2,
                   player.video_frame.height() // 3),
            QPoint(-260, -160))
        after_drag = player.geometry()
        record("picture_in_picture_drag_from_video",
               drag_finished
               and abs((after_drag.x() - before_drag.x()) + 260) <= 12
               and abs((after_drag.y() - before_drag.y()) + 160) <= 12,
               f"before={before_drag.x()},{before_drag.y()} "
               f"after={after_drag.x()},{after_drag.y()}")
        # Sonraki ekran-siniri resize kabulunu yine sag-alt baslangicindan
        # olcmek icin PiP'yi bir kez normal moda dondurup yeniden ac.
        player.toggle_picture_in_picture(False)
        player.toggle_picture_in_picture(True)
        pump(app, 0.2)
        screenshot_path = os.environ.get("MLC_NATIVE_SCREENSHOT")
        if screenshot_path:
            screen = player.screen() or QApplication.primaryScreen()
            rect = player.frameGeometry()
            saved = bool(screen and screen.grabWindow(
                0, rect.x(), rect.y(), rect.width(), rect.height()
            ).save(screenshot_path))
            record("picture_in_picture_screenshot", saved,
                   f"path={screenshot_path}")
        player.resize(560, 315)
        pump(app, 0.15)
        record("picture_in_picture_resizable",
               player.width() == 560 and player.height() == 315,
               f"size={player.width()}x{player.height()}")
        target_hwnd, target_point = window_at_widget_center(
            player.video_frame.overlay_pip_exit_button)
        record("picture_in_picture_exit_hit_target",
               target_hwnd == int(player.video_frame.control_overlay.winId()),
               f"target={target_hwnd} overlay="
               f"{int(player.video_frame.control_overlay.winId())} "
               f"point={target_point.x()},{target_point.y()} "
               f"visible={player.video_frame.overlay_pip_exit_button.isVisible()} "
               f"opacity={player.video_frame.control_overlay.windowOpacity():.2f}")
        physical_click(player.video_frame.overlay_pip_exit_button)
        pump(app, 0.2)
        record("picture_in_picture_mouse_exit",
               not player.picture_in_picture_enabled,
               f"enabled={player.picture_in_picture_enabled}")

        # Asenkron load sayesinde open_path UI'yi bekletmez ve timeline
        # süre metadatasından önce dahi görünür yüzeydedir.
        started = time.perf_counter()
        player.open_path(media)
        dispatch_ms = (time.perf_counter() - started) * 1000
        pump(app, 0.05)
        timeline_visible = player.video_frame.overlay_timeline.isVisible()
        record("timeline_immediate", dispatch_ms < 200 and timeline_visible,
               f"dispatch_ms={dispatch_ms:.1f} visible={timeline_visible}")

        deadline = time.perf_counter() + 5.0
        while player.duration <= 0 and time.perf_counter() < deadline:
            pump(app, 0.05)
        record("duration_arrived", player.duration > 0,
               f"duration_ready={player.duration > 0}")

        # Gerçek libmpv doğal-son akışı: sona yaklaş, oynat ve ürünün
        # update_ui kuralının başa sarıp duraklatmasını bekle.
        if player.duration > 1:
            player.mpv_player.pause = True
            player.mpv_player.command_async(
                "seek", max(0.0, player.duration - 0.35), "absolute+exact")
            pump(app, 0.3)
            player.mpv_player.pause = False
            player.is_paused = False
            player._eof_rewound = False
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline:
                pump(app, 0.05)
                if player.is_paused and player.position < 1.0:
                    break
            record("natural_end_rewinds_and_pauses",
                   player.is_paused and player.position < 1.0
                   and player.current_playlist_index == 0,
                   f"paused={player.is_paused} position={player.position:.3f} "
                   f"index={player.current_playlist_index}")
        else:
            record("natural_end_rewinds_and_pauses", False,
                   "media_duration_too_short")

        started = time.perf_counter()
        player.stop()
        stop_ms = (time.perf_counter() - started) * 1000
        cursor = QApplication.overrideCursor()
        busy = cursor is not None and cursor.shape() == Qt.CursorShape.BusyCursor
        record("stop_non_blocking", stop_ms < 200 and not busy,
               f"stop_ms={stop_ms:.1f} busy_cursor={busy}")

        player.close()
        pump(app, 0.5)
        QCursor.setPos(old_cursor)

    print(f"RESULT failures={checks.count(False)}", flush=True)
    print("MARK_DONE", flush=True)
    return 1 if not all(checks) else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
