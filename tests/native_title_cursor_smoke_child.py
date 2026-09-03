# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in Windows smoke for the post-transparency title-button cursor.

No installer, media file or user setting is touched.  The child creates one
temporary MLC window, opens/closes the transparency control through real
Windows mouse input, then compares the visible cursor handle at a title
button before and immediately after that close.
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OPT_IN_VARIABLE = "MLC_NATIVE_TITLE_CURSOR_SMOKE"
OPT_IN_VALUE = "1"
MEDIA_VARIABLE = "MLC_NATIVE_TITLE_CURSOR_MEDIA"

if os.environ.get(OPT_IN_VARIABLE) != OPT_IN_VALUE:
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

if os.name != "nt":
    print("SKIPPED: WINDOWS_REQUIRED", flush=True)
    raise SystemExit(0)

os.environ["PATH"] = os.path.join(ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QCursor  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.player import MPVPlayer  # noqa: E402


class CURSORINFO(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HCURSOR),
        ("ptScreenPos", wintypes.POINT),
    )


user32 = ctypes.windll.user32
user32.GetCursorInfo.argtypes = (ctypes.POINTER(CURSORINFO),)
user32.GetCursorInfo.restype = wintypes.BOOL
user32.LoadCursorW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR)
user32.LoadCursorW.restype = wintypes.HCURSOR
user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
user32.SetCursorPos.restype = wintypes.BOOL

IDC_ARROW = 32512
IDC_HAND = 32649
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def integer_resource(identifier):
    return ctypes.cast(ctypes.c_void_p(identifier), wintypes.LPCWSTR)


def pump(app, seconds):
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def cursor_handle():
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(info)):
        return 0
    return int(info.hCursor or 0)


def move_to(widget, app):
    point = widget.mapToGlobal(widget.rect().center())
    if not user32.SetCursorPos(point.x(), point.y()):
        raise RuntimeError("SetCursorPos failed")
    pump(app, 0.18)


def physical_click(widget, app):
    point = widget.mapToGlobal(widget.rect().center())
    physical_click_point(point, app)


def physical_click_point(point, app):
    if not user32.SetCursorPos(point.x(), point.y()):
        raise RuntimeError("SetCursorPos failed")
    pump(app, 0.18)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    pump(app, 0.06)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    pump(app, 0.22)


def main():
    app = QApplication.instance() or QApplication([])
    original_cursor = QCursor.pos()
    player = MPVPlayer()
    player.show()
    player.raise_()
    player.activateWindow()
    pump(app, 0.45)
    media_path = os.environ.get(MEDIA_VARIABLE, "")
    video_submitted = True
    if media_path:
        if not os.path.isfile(media_path):
            print("BLOCKED invalid_explicit_media", flush=True)
            player.close()
            return 2
        # Cursor senaryosu, mpv'nin video yüzeyi açıkken başlık çubuğunun
        # Windows cursor'unu nasıl güncellediğini ölçer. Duration callback'i
        # bu kısa native child'ta geç gelebilir; medya komutunun kabulü ve
        # native yüzeyin varlığı bu senaryo için yeterli ve ölçülebilirdir.
        player.open_path(media_path)
        pump(app, 0.35)
        video_submitted = player.current_file == media_path
    title = player.title_bar
    opener = title.transparency_button
    # Kullanıcı davranışında sol taraftaki Dosya Aç da ilk kapanıştan sonra
    # ok imlecine düşebildiği için sağ pencere düğmesiyle yetinmeyiz.
    target = title.open_button
    hand = int(user32.LoadCursorW(None, integer_resource(IDC_HAND)) or 0)
    arrow = int(user32.LoadCursorW(None, integer_resource(IDC_ARROW)) or 0)

    try:
        physical_click(opener, app)
        opened = bool(title.transparency_popup.isVisible())
        title.transparency_slider.setValue(58)
        pump(app, 0.25)
        opacity_applied = abs(player.windowOpacity() - 0.58) < 0.03
        # Kullanıcının ekran görüntüsündeki asıl yol: sürgüyle yeniden %100
        # yap, panel hâlâ açıkken başlık düğmesine dön ve sonra kapat.
        title.transparency_slider.setValue(100)
        pump(app, 0.25)
        opacity_restored = abs(player.windowOpacity() - 1.0) < 0.03
        move_to(target, app)
        open_cursor = cursor_handle()

        physical_click(opener, app)
        closed = not bool(title.transparency_popup.isVisible())
        move_to(target, app)
        first_close_cursor = cursor_handle()
        pump(app, 0.35)
        settled_close_cursor = cursor_handle()

        physical_click(opener, app)
        outside_point = player.video_frame.mapToGlobal(
            player.video_frame.rect().center())
        physical_click_point(outside_point, app)
        outside_closed = not bool(title.transparency_popup.isVisible())
        move_to(target, app)
        outside_close_cursor = cursor_handle()

        print(f"CURSOR_OPEN={open_cursor}", flush=True)
        print(f"CURSOR_FIRST_AFTER_CLOSE={first_close_cursor}", flush=True)
        print(f"CURSOR_SETTLED_AFTER_CLOSE={settled_close_cursor}", flush=True)
        print(f"CURSOR_AFTER_OUTSIDE_CLOSE={outside_close_cursor}", flush=True)
        print(f"CURSOR_HAND={hand}", flush=True)
        print(f"CURSOR_ARROW={arrow}", flush=True)
        print(f"PANEL_OPENED={opened}", flush=True)
        print(f"OPACITY_APPLIED={opacity_applied}", flush=True)
        print(f"OPACITY_RESTORED={opacity_restored}", flush=True)
        print(f"VIDEO_SUBMITTED={video_submitted}", flush=True)
        print(f"PANEL_CLOSED={closed}", flush=True)
        print(f"PANEL_OUTSIDE_CLOSED={outside_closed}", flush=True)
        passed = (video_submitted and opened and opacity_applied
                  and opacity_restored and closed and hand != 0
                  and open_cursor == hand
                  and first_close_cursor == hand
                  and settled_close_cursor == hand
                  and outside_closed and outside_close_cursor == hand)
        print("MARK_DONE" if passed else "MARK_FAILED", flush=True)
        return 0 if passed else 3
    finally:
        try:
            player.set_window_opacity_percent(100)
            player.close()
            pump(app, 0.2)
        finally:
            user32.SetCursorPos(original_cursor.x(), original_cursor.y())


raise SystemExit(main())
