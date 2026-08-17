# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in gerçek Windows kabul testi: playlist aç/kapat akıcılığı + dış boşluk.

Gerçek video oynarken playlist her pencere durumunda 10 kez art arda açılıp
kapatılır. Ölçülenler:

- `VideoFrame.resizeEvent` sayısı (MPV native wid yüzeyinin yeniden
  boyutlandırılma maliyeti);
- animasyon sırasında video/playlist kesişmesi (kare kare);
- Qt event loop'un cevap verirliği (0 ms timer tick sayısı);
- geçiş sonunda panelin doğru son durumda kalması;
- pencerenin sol/sağ/alt kenarında görünür dış boşluk kalmaması.

``MLC_NATIVE_SMOKE=1`` verilmeden hiçbir Qt/MPV nesnesi oluşturmaz.
"""
import os
import sys
import time
import ctypes

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QPoint, QRect, QSettings, Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.player import MPVPlayer  # noqa: E402
from app.title_bar import RESIZE_MARGIN, resize_edges_at  # noqa: E402
from app.video_frame import VideoFrame  # noqa: E402

VIDEO_PATH = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
TOGGLES = int(os.environ.get("MLC_TOGGLE_COUNT", "10"))
SHOT_DIR = os.environ.get("TEMP", ".")

START = time.time()
failures = []
stats = {}

# --- VideoFrame.resizeEvent sayacı (ürün kodu değiştirilmez) ---
_resize_counter = {"count": 0}
_original_resize = VideoFrame.resizeEvent


def _counting_resize(self, event):
    _resize_counter["count"] += 1
    return _original_resize(self, event)


VideoFrame.resizeEvent = _counting_resize


def mark(name, extra=""):
    print(f"{name} t={time.time() - START:.2f} {extra}".rstrip(), flush=True)


def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    print("PYTHON_EXCEPTION " + "".join(
        traceback.format_exception(exc_type, exc_value, exc_tb)).strip(),
        flush=True)
    instance = QApplication.instance()
    if instance is not None:
        instance.exit(90)


sys.excepthook = _excepthook


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def capture(name):
    try:
        path = os.path.join(SHOT_DIR, f"MLCPlayer-toggle-{name}.png")
        QApplication.primaryScreen().grabWindow(0).save(path)
        print(f"SHOT {name} {path}", flush=True)
        return path
    except Exception as exc:  # pragma: no cover
        print(f"SHOT_FAILED {name} {exc}", flush=True)
        return ""


def main():
    settings_dir = os.environ.get("MLC_NATIVE_SETTINGS")
    if settings_dir:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, settings_dir)

    app = QApplication(sys.argv)
    player = MPVPlayer()
    player.resize(1400, 820)
    player.show()
    app.processEvents()
    frame = player.video_frame
    mark("MARK_SHOWN")

    if VIDEO_PATH and os.path.isfile(VIDEO_PATH):
        player.open_path(VIDEO_PATH)
        mark("MARK_PLAY", os.path.basename(VIDEO_PATH))
    else:
        mark("MARK_PLAY", "no_video")
    app.processEvents()
    time.sleep(1.2)
    app.processEvents()

    # --- A) Görünür dış boşluk ölçümü ---
    def measure_edges(tag):
        """Sol/alt kenarı video, sağ kenarı ise açıkken PANEL üzerinden ölçer."""
        window_rect = global_rect(player)
        video_rect = global_rect(frame)
        panel = getattr(frame, "playlist_panel", None)
        panel_open = bool(getattr(panel, "is_open", False))
        right_widget_rect = global_rect(panel) if panel_open else video_rect
        gaps = {
            "left": video_rect.left() - window_rect.left(),
            "right": window_rect.right() - right_widget_rect.right(),
            "bottom": window_rect.bottom() - video_rect.bottom(),
            "panel_bottom": (window_rect.bottom() - right_widget_rect.bottom()
                             if panel_open else 0),
        }
        gaps["playlist_open"] = panel_open
        margins = player.main_layout.contentsMargins()
        mark(f"MARK_EDGES_{tag.upper()}",
             f"gaps={gaps} layout_margins=("
             f"{margins.left()},{margins.top()},{margins.right()},"
             f"{margins.bottom()})")
        for side, value in gaps.items():
            if side != "playlist_open" and value != 0:
                failures.append(f"EDGE_GAP_{tag}_{side}={value}")
        return gaps

    measure_edges("closed")
    capture("edges-closed")

    # --- Kenar/köşe resize hit-test'i hâlâ çalışmalı ---
    rect = player.rect()
    checks = {
        "left": (QPoint(2, rect.height() // 2), Qt.Edge.LeftEdge),
        "right": (QPoint(rect.width() - 2, rect.height() // 2), Qt.Edge.RightEdge),
        "bottom": (QPoint(rect.width() // 2, rect.height() - 2), Qt.Edge.BottomEdge),
        "bottom_left": (QPoint(2, rect.height() - 2),
                        Qt.Edge.LeftEdge | Qt.Edge.BottomEdge),
        "bottom_right": (QPoint(rect.width() - 2, rect.height() - 2),
                         Qt.Edge.RightEdge | Qt.Edge.BottomEdge),
        "top_left": (QPoint(2, 2), Qt.Edge.LeftEdge | Qt.Edge.TopEdge),
        "top_right": (QPoint(rect.width() - 2, 2),
                      Qt.Edge.RightEdge | Qt.Edge.TopEdge),
    }
    bad = [name for name, (point, expected) in checks.items()
           if resize_edges_at(rect, point) != expected]
    mark("MARK_RESIZE_HITTEST",
         f"margin={RESIZE_MARGIN} checked={len(checks)} failed={bad}")
    if bad:
        failures.append(f"RESIZE_HITTEST_FAILED={bad}")

    # --- B) Aç/kapat stresi ---
    def toggle_cycle(tag, cycles):
        panel = frame.playlist_panel
        _resize_counter["count"] = 0
        ticks = {"n": 0}
        heartbeat = QTimer()
        heartbeat.setInterval(0)
        heartbeat.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
        heartbeat.start()

        overlaps = []
        sampled = 0
        try:
            for index in range(cycles):
                for opening in (True, False):
                    frame.toggle_playlist_panel()
                    animation = panel.animation
                    duration = max(1, animation.duration())
                    deadline = time.time() + 1.5
                    while (animation.state().name == "Running"
                           and time.time() < deadline):
                        app.processEvents()
                        sampled += 1
                        host_rect = global_rect(player.playlist_dock_host)
                        visible = global_rect(panel).intersected(host_rect)
                        hit = visible.intersected(global_rect(frame))
                        if not hit.isEmpty():
                            overlaps.append((tag, index, opening,
                                             hit.getRect()))
                        time.sleep(0.004)
                    app.processEvents()
        finally:
            heartbeat.stop()

        panel.finish_animation()
        app.processEvents()
        stats[tag] = {
            "cycles": cycles,
            "video_resizes": _resize_counter["count"],
            "resizes_per_transition": round(
                _resize_counter["count"] / max(1, cycles * 2), 2),
            "event_loop_ticks": ticks["n"],
            "animation_frames_sampled": sampled,
            "overlaps": len(overlaps),
            "panel_open_at_end": bool(panel.is_open),
            "panel_width_at_end": panel.width(),
        }
        mark(f"MARK_TOGGLE_{tag.upper()}", str(stats[tag]))
        if overlaps:
            failures.append(f"TOGGLE_OVERLAP_{tag}={overlaps[:3]}")
        if ticks["n"] == 0:
            failures.append(f"EVENT_LOOP_STALLED_{tag}")

    toggle_cycle("normal", TOGGLES)
    # Kenar ölçümü playlist GERÇEKTEN açıkken yapılmalı.
    if not frame.playlist_panel.is_open:
        frame.toggle_playlist_panel()
    frame.playlist_panel.finish_animation()
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    capture("edges-open")
    measure_edges("open")

    player.resize(960, 600)
    app.processEvents()
    toggle_cycle("960x600", 3)

    player.showMaximized()
    app.processEvents()
    toggle_cycle("maximized", 3)

    player.showNormal()
    app.processEvents()
    frame.enter_fullscreen()
    app.processEvents()
    toggle_cycle("fullscreen", 3)
    capture("fullscreen-open")
    frame.exit_fullscreen()
    app.processEvents()
    player.resize(1400, 820)
    app.processEvents()
    toggle_cycle("after_fullscreen", 3)
    measure_edges("after_fullscreen")

    # --- Fiziksel ayraç (gerçek Win32 fare) ---
    panel = frame.playlist_panel
    if not panel.is_open:
        frame.toggle_playlist_panel()
        panel.finish_animation()
        app.processEvents()
    handle = panel.resize_handle
    centre = handle.mapToGlobal(handle.rect().center())
    user32 = ctypes.windll.user32
    from ctypes import wintypes

    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p]
    original = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(original))
    before = panel.width()
    down = False
    try:
        user32.SetCursorPos(int(centre.x()), int(centre.y()))
        app.processEvents()
        time.sleep(0.08)
        user32.mouse_event(0x0002, 0, 0, 0, None)
        down = True
        for step in range(1, 10):
            user32.SetCursorPos(int(centre.x()) - step * 10, int(centre.y()))
            app.processEvents()
            time.sleep(0.012)
        widened = panel.width()
        for step in range(1, 8):
            user32.SetCursorPos(int(centre.x()) - 90 + step * 14,
                                int(centre.y()))
            app.processEvents()
            time.sleep(0.012)
        narrowed = panel.width()
        user32.mouse_event(0x0004, 0, 0, 0, None)
        down = False
    finally:
        if down:
            user32.mouse_event(0x0004, 0, 0, 0, None)
        user32.SetCursorPos(original.x, original.y)
        app.processEvents()
    restored = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(restored))
    cursor_ok = (abs(restored.x - original.x) <= 2
                 and abs(restored.y - original.y) <= 2)
    mark("MARK_SEPARATOR",
         f"before={before} widened={widened} narrowed={narrowed} "
         f"cursor_restored={cursor_ok}")
    if widened <= before or narrowed >= widened:
        failures.append(
            f"SEPARATOR_DRAG_FAILED {before}->{widened}->{narrowed}")
    if not cursor_ok:
        failures.append("SEPARATOR_CURSOR_NOT_RESTORED")

    print("RESULTS: " + " ".join(
        [f"failures={','.join(failures) or 'none'}"]
        + [f"{tag}_resizes_per_transition={data['resizes_per_transition']}"
           for tag, data in stats.items()]), flush=True)

    try:
        player.mpv_player.stop()
        player.mpv_player.terminate()
    except Exception as exc:
        print(f"TEARDOWN_WARNING {exc}", flush=True)
    player.close()
    mark("MARK_DONE", f"failures={len(failures)}")
    return 1 if failures else 0


raise SystemExit(main())
