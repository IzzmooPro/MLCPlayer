# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in GERCEK FIZIKSEL Windows kabul child'i. TEK grup calistirir.

Butun kullanici hareketleri gercek Win32 girdisiyle uretilir
(`SetCursorPos` + `SendInput`). Urun metodlari kullanici hareketi taklidi
icin CAGRILMAZ; yalnizca sonuc DOGRULAMASI icin urun durumu okunur.

Urun, main.py ile ayni sekilde (`MPVPlayer()`) bu surecte olusturulur; boylece
gercek pencereye fiziksel girdi gonderilirken ic durum da olculebilir.

Her calistirma TEK grup kosar ve MARK_DONE ile biter. Bir grup kilitlenirse
yalnizca o child duser; runner digerlerini surdurur.

    python tests/native_physical_acceptance_child.py --group buttons
"""
import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import (QEvent, QObject, QPoint, QRect, QSettings,  # noqa: E402
                          QStandardPaths, Qt, QTimer)
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QPushButton  # noqa: E402

from app.player import MPVPlayer  # noqa: E402
from app.i18n import tr  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from physical_tolerances import (slider_value_tolerance,  # noqa: E402
                                 seek_time_tolerance)
from physical_targets import (candidate_values, pick_far_target,  # noqa: E402
                              target_x_for_value, value_tolerance_for_width)
from physical_audio import (audio_safety_problems,  # noqa: E402
                            native_mpv_config)
from physical_buttons_contract import (MODAL_DISMISS_DELAY_MS,  # noqa: E402
                                       arm_modal_dismissal,
                                       has_subtitle_track,
                                       playlist_step_available)
from physical_tracks_contract import (StableSelection,  # noqa: E402
                                      alternate_track_id,
                                      fixture_block_code,
                                      fixture_problems,
                                      normalise_track_id,
                                      unique_target_index,
                                      track_snapshot)
from physical_menu_watchdog import (PopupChainWatchdog,  # noqa: E402
                                    popup_completion_decision)
from physical_layout import (resize_problems,  # noqa: E402
                             zorder_after_resize_problems)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
KEYEVENTF_KEYUP, KEYEVENTF_EXTENDEDKEY = 0x0002, 0x0001
VK_ESCAPE, VK_MENU, VK_TAB, VK_V = 0x1B, 0x12, 0x09, 0x56
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND

APP = PLAYER = None
# `mpv.MPV.stop/terminate` cagrilarinin SINIF duzeyinde saydam kaydi:
# MPV nesnesine fazladan referans tutulmaz, olcum kapanis sirasini
# etkilemez.
MPV_CALLS = []


def install_mpv_call_recorder():
    import mpv as mpv_module

    real_stop = mpv_module.MPV.stop
    real_terminate = mpv_module.MPV.terminate

    def recording_stop(self, *args, **kwargs):
        MPV_CALLS.append("stop")
        print(f"MARK_STOP_CALLED count={MPV_CALLS.count('stop')}", flush=True)
        return real_stop(self, *args, **kwargs)

    def recording_terminate(self, *args, **kwargs):
        MPV_CALLS.append("terminate")
        print(f"MARK_TERMINATE_CALLED count={MPV_CALLS.count('terminate')}",
              flush=True)
        return real_terminate(self, *args, **kwargs)

    mpv_module.MPV.stop = recording_stop
    mpv_module.MPV.terminate = recording_terminate
SHOT_DIR = os.path.join(os.environ.get("TEMP", "."), "mlc_physical")
os.makedirs(SHOT_DIR, exist_ok=True)
GROUP = "?"
results = []
_shot = [0]


def _send(*items):
    array = (INPUT * len(items))(*items)
    if user32.SendInput(len(items), array, ctypes.sizeof(INPUT)) != len(items):
        raise OSError("SendInput failed")


def mouse_button(down, right=False):
    if right:
        flag = MOUSEEVENTF_RIGHTDOWN if down else MOUSEEVENTF_RIGHTUP
    else:
        flag = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
    _send(INPUT(type=INPUT_MOUSE, u=_U(mi=MOUSEINPUT(0, 0, 0, flag, 0, 0))))


def key(vk, down, extended=False):
    flags = (0 if down else KEYEVENTF_KEYUP) | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    _send(INPUT(type=INPUT_KEYBOARD, u=_U(ki=KEYBDINPUT(vk, 0, flags, 0, 0))))


def tap(vk):
    key(vk, True)
    time.sleep(0.05)
    key(vk, False)


def cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def foreground_hwnd():
    """Foreground HWND'i her zaman int olarak dondurur (yoksa 0).

    URUN `app/video_frame.py` icinde `GetForegroundWindow.restype` degerini
    pointer-safe `wintypes.HWND` yapar ve `ctypes.windll.user32` surec
    genelinde TEK nesne oldugu icin bu imza harness'te de gecerlidir. NULL
    HWND Python'da `None` doner; urun penceresi kapandiktan hemen sonra kisa
    sure foreground pencere OLMAYABILIR. Normalizasyon yalniz burada yapilir.
    """
    return int(user32.GetForegroundWindow() or 0)


def foreground_info():
    hwnd = foreground_hwnd()
    pid = ctypes.c_ulong(0)
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return hwnd, int(pid.value)


def widget_alive(widget):
    """Silinmis C++ nesnesini ham `RuntimeError` uretmeden yoklar."""
    if widget is None:
        return False
    try:
        widget.objectName()
    except RuntimeError:
        return False
    return True


def live_overlay_widget(frame, name):
    """Kareden O ANKI overlay widget'ini verir; yok/silinmisse None.

    Urun katmani calisma sirasinda yeniden URETILMEZ
    (`VideoFrame._create_control_overlay()` korumalidir), ancak URUN KAPANISI
    `release_overlay_surfaces()` ile widget'lari siler ve referanslari
    `None`'a ceker. Grup basinda bir kez baglanan referans bu andan sonra
    kullanilirsa child ham `RuntimeError` ile (`exit=90`) duser; olcum
    BLOCKED sayilmalidir.
    """
    widget = getattr(frame, name, None)
    return widget if widget_alive(widget) else None


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        APP.processEvents()
        time.sleep(0.008)
    APP.processEvents()


def wait_for(predicate, timeout_ms=6000, step_ms=60):
    """Bounded polling: anlik okuma yerine durum degisimini bekler."""
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:
            pass
        pump(step_ms)
    return False


def shot(name):
    _shot[0] += 1
    path = os.path.join(SHOT_DIR, f"{GROUP}-{_shot[0]:02d}-{name}.png")
    try:
        QApplication.primaryScreen().grabWindow(0).save(path)
        return path
    except Exception as exc:
        print(f"SHOT_FAILED {name} {exc}", flush=True)
        return ""


def record(test, method, expected, measured, ok, evidence=""):
    status = "PASS" if ok is True else ("FAIL" if ok is False else "BLOCKED")
    results.append({"test": test, "status": status})
    print(f"RESULT|{GROUP}|{test}|{method}|{expected}|{measured}|{status}|{evidence}",
          flush=True)


class ClickProbe(QObject):
    """YALNIZ GOZLEM: hedef dugmede olay/sinyal sayaci.

    Urunu bypass etmez, aksiyon calistirmaz; yalnizca press/release/clicked
    sayar ve `_run_overlay_action` ile urun metodunun cagrilip
    cagrilmadigini kaydeder.
    """

    def __init__(self, widget, product_method=None):
        super().__init__(widget)
        self.widget = widget
        self.press = 0
        self.release = 0
        self.clicked = 0
        self.overlay_action = 0
        self.product_calls = 0
        self._restores = []
        widget.installEventFilter(self)
        try:
            widget.clicked.connect(self._on_clicked)
        except Exception:
            pass
        frame_cls = type(PLAYER.video_frame)
        real_action = frame_cls._run_overlay_action

        def counting_action(frame_self, action):
            self.overlay_action += 1
            return real_action(frame_self, action)

        frame_cls._run_overlay_action = counting_action
        self._restores.append(
            lambda: setattr(frame_cls, "_run_overlay_action", real_action))

        if product_method:
            real_method = getattr(PLAYER, product_method)

            def counting_method(*args, **kwargs):
                self.product_calls += 1
                return real_method(*args, **kwargs)

            setattr(PLAYER, product_method, counting_method)
            self._restores.append(
                lambda: setattr(PLAYER, product_method, real_method))

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            self.press += 1
        elif kind == QEvent.Type.MouseButtonRelease:
            self.release += 1
        return False

    def _on_clicked(self, *args):
        self.clicked += 1

    def release_probe(self):
        for restore in self._restores:
            try:
                restore()
            except Exception:
                pass
        try:
            self.widget.removeEventFilter(self)
        except Exception:
            pass

    def summary(self, x=None, y=None):
        hwnd = pid = None
        widget_at = None
        if x is not None:
            point = wintypes.POINT(int(x), int(y))
            hwnd = int(user32.WindowFromPoint(point) or 0)
            owner = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            pid = int(owner.value)
            widget_at = type(QApplication.widgetAt(QPoint(int(x), int(y)))).__name__
        frame = PLAYER.video_frame
        overlay = frame.control_overlay
        try:
            overlay_hwnd = int(overlay.winId()) if overlay is not None else 0
        except Exception:
            overlay_hwnd = 0
        try:
            frame_hwnd = int(frame.winId())
        except Exception:
            frame_hwnd = 0
        try:
            window_hwnd = int(PLAYER.winId())
        except Exception:
            window_hwnd = 0
        which = ("overlay" if hwnd == overlay_hwnd else
                 "video_frame" if hwnd == frame_hwnd else
                 "main_window" if hwnd == window_hwnd else "other")
        return (f"hit_hwnd_is={which} overlay_hwnd={overlay_hwnd} "
                f"frame_hwnd={frame_hwnd} window_hwnd={window_hwnd} "
                f"press={self.press} release={self.release} "
                f"clicked={self.clicked} overlay_action={self.overlay_action} "
                f"product_calls={self.product_calls} hwnd={hwnd} pid={pid} "
                f"own_pid={os.getpid()} widget_at={widget_at}")


def take_foreground(hwnd, attempts=15):
    hwnd = int(hwnd or 0)
    if not hwnd:
        # Hedef pencere yok: ShowWindow/SetForegroundWindow(0) anlamsizdir.
        return False
    for _ in range(attempts):
        fg = foreground_hwnd()
        fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        cur = kernel32.GetCurrentThreadId()
        attached = False
        try:
            if fg_thread and fg_thread != cur:
                attached = bool(user32.AttachThreadInput(cur, fg_thread, True))
            user32.ShowWindow(hwnd, 9)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(cur, fg_thread, False)
        pump(120)
        if foreground_hwnd() == hwnd:
            return True
    return False


def player_front():
    return take_foreground(int(PLAYER.winId()))


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def global_centre(widget):
    point = widget.mapToGlobal(widget.rect().center())
    return int(point.x()), int(point.y())


def overlay_button(name):
    return PLAYER.video_frame.control_overlay.findChild(QPushButton, name)


def wake_overlay():
    """Overlay'i GERCEK fare hareketiyle uyandirir (urun metodu cagrilmaz)."""
    frame = PLAYER.video_frame
    rect = global_rect(frame)
    cx = rect.left() + rect.width() // 2
    cy = rect.top() + rect.height() // 2
    for dx in (0, 14, -14, 6):
        user32.SetCursorPos(cx + dx, cy + dx)
        pump(60)
    overlay = frame.control_overlay
    if overlay is not None:
        ox, oy = global_centre(overlay)
        user32.SetCursorPos(ox, oy - 8)
        pump(200)


def click_ready(widget, label):
    """Tiklama ONKOSULU: foreground + overlay gorunur + fade tamam + hit dogru."""
    frame = PLAYER.video_frame
    overlay = frame.control_overlay
    if not player_front():
        record(label, "onkosul", "player foreground", str(foreground_info()), False)
        return None
    wake_overlay()
    if not wait_for(lambda: overlay.isVisible(), 4000):
        record(label, "onkosul", "overlay visible", "gorunmedi", False)
        return None
    if not wait_for(lambda: overlay.windowOpacity() >= 0.95, 3000):
        record(label, "onkosul", "fade opacity>=0.95",
               f"opacity={overlay.windowOpacity():.2f}", False)
        return None
    x, y = global_centre(widget)
    inside = global_rect(widget).contains(QPoint(x, y))
    hit = QApplication.widgetAt(QPoint(x, y))
    owner = hit
    while owner is not None and owner is not widget:
        owner = owner.parent()
    if not (inside and owner is widget):
        record(label, "onkosul", "widgetAt hedefe ait",
               f"inside={inside} hit={hit}", False)
        return None
    return x, y, f"opacity={overlay.windowOpacity():.2f} hit_ok=True"


def physical_click(x, y, settle=250, target=None, label=""):
    """Gercek SendInput tiklamasi.

    `target` verilirse tiklama GONDERILMEDEN hemen once imlecin altindaki
    widget'in gercekten hedef (veya cocugu) oldugu DOGRULANIR. Overlay
    kaydiysa hedefin guncel merkezi yeniden hesaplanir. Hedef dogrulanamazsa
    tiklama gonderilmez ve `False` dondurulur: yanlis yere giden tiklama
    "test edildi" sayilamaz.
    """
    user32.SetCursorPos(int(x), int(y))
    pump(90)
    if target is not None:
        for attempt in range(4):
            point = QPoint(int(x), int(y))
            owner = QApplication.widgetAt(point)
            while owner is not None and owner is not target:
                owner = owner.parent()
            if owner is target:
                break
            wake_overlay()
            x, y = global_centre(target)
            user32.SetCursorPos(int(x), int(y))
            pump(120)
        else:
            print(f"CLICK_TARGET_LOST label={label} point=({int(x)},{int(y)}) "
                  f"widget_at={type(QApplication.widgetAt(QPoint(int(x), int(y)))).__name__}",
                  flush=True)
            return False
    mouse_button(True)
    pump(70)
    mouse_button(False)
    pump(settle)
    return True


def _plain_menu_text(value):
    return str(value or "").replace("&", "").strip()


def _menu_action(menu, text):
    wanted = _plain_menu_text(text)
    matches = [action for action in menu.actions()
               if _plain_menu_text(action.text()) == wanted]
    return matches[0] if len(matches) == 1 else None


def _menu_target_action(menu, target_id):
    actions = [action for action in menu.actions()
               if action.isEnabled() and action.isCheckable()]
    index = unique_target_index([action.data() for action in actions],
                                target_id)
    return actions[index] if index is not None else None


def _menu_action_point(menu, action):
    """Gorunen QAction merkezi ve hit/PID onkosulu; aksi halde None."""
    if not isinstance(menu, QMenu) or not menu.isVisible() or action is None:
        return None
    rect = menu.actionGeometry(action)
    if not rect.isValid() or rect.isEmpty():
        return None
    local = rect.center()
    if menu.actionAt(local) is not action:
        return None
    point = menu.mapToGlobal(local)
    hwnd = int(user32.WindowFromPoint(
        wintypes.POINT(int(point.x()), int(point.y()))) or 0)
    pid = ctypes.c_ulong(0)
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if int(pid.value) != os.getpid():
        return None
    return int(point.x()), int(point.y())


def physical_menu_action(root_text, track_text, target_id, inspect_only=False):
    """Sag-tik menusu yolunu gercek Win32 girdisiyle acar ve hedefler.

    Qt nesneleri yalniz gorunen popup/action geometrisini okumak icin
    kullanilir. Secim ``QAction.trigger`` veya player metodu ile uretilmez.
    ``inspect_only`` ikinci bir fiziksel menu acilisinda checked read-back
    yapar ve menuyu gercek Esc ile kapatir.
    """
    state = {"done": False, "delivered": False, "checked": False,
             "reason": "menu_sequence_incomplete", "pending": None,
             "timed_out": False, "root_popup": None}
    frame = PLAYER.video_frame

    def phase(name, **fields):
        details = " ".join(f"{key}={value}" for key, value in fields.items())
        print(f"TRACK_MENU_PHASE name={name} inspect={int(inspect_only)} "
              f"target={target_id} {details}".rstrip(), flush=True)

    def active_popup():
        popup = QApplication.activePopupWidget()
        return popup if isinstance(popup, QMenu) and popup.isVisible() else None

    def close_visible_menus():
        """Last-resort cleanup only; it can never produce acceptance."""
        menus = []
        popup = active_popup()
        if popup is not None:
            menus.append(popup)
        menus.extend(widget for widget in QApplication.topLevelWidgets()
                     if isinstance(widget, QMenu) and widget.isVisible())
        closed = 0
        unique = []
        seen = set()
        for menu in menus:
            if id(menu) not in seen:
                unique.append(menu)
                seen.add(id(menu))
        for menu in reversed(unique):
            try:
                menu.close()
                closed += 1
            except RuntimeError:
                pass
        return closed

    def root_popup_closed():
        root = state.get("root_popup")
        if root is None:
            return False
        try:
            return not root.isVisible()
        except RuntimeError:
            return True

    def finish(reason, delivered=False, checked=False):
        state.update(done=True, reason=reason, delivered=delivered,
                     checked=checked)

    def abort(reason):
        state["pending"] = ("abort", reason, False)
        phase("abort", reason=reason)
        watchdog.dismiss()

    def watchdog_timeout():
        state["timed_out"] = True
        phase("watchdog_timeout")

    def popup_cleanup_complete(closed, forced):
        root_closed = root_popup_closed()
        phase("popup_cleanup_complete", closed=int(closed),
              root_closed=int(root_closed), forced=int(forced))
        decision = popup_completion_decision(
            pending=state.get("pending"), timed_out=state["timed_out"],
            closed=closed, forced=forced, root_closed=root_closed)
        finish(decision["reason"], delivered=decision["delivered"],
               checked=decision["checked"])

    watchdog = PopupChainWatchdog(
        active_popup=active_popup,
        send_escape=lambda: tap(VK_ESCAPE),
        close_visible=close_visible_menus,
        marker=phase,
        timeout_ms=4000,
        escape_interval_ms=90,
        max_escapes=5)

    def hover(action_menu, action, next_step):
        point = _menu_action_point(action_menu, action)
        if point is None:
            abort("action_hit_or_pid_mismatch")
            return
        user32.SetCursorPos(*point)
        QTimer.singleShot(350, next_step)

    def target_step(track_action):
        target_menu = track_action.menu()
        target = (_menu_target_action(target_menu, target_id)
                  if target_menu is not None else None)
        point = (_menu_action_point(target_menu, target)
                 if target is not None else None)
        if point is None:
            abort("target_action_missing_or_ambiguous")
            return
        user32.SetCursorPos(*point)
        phase("target_visible")
        if inspect_only:
            state["action"] = target
            checked = bool(target.isChecked())
            state["pending"] = ("inspect", "checked_readback", checked)
            phase("checked_read", checked=int(checked))
            watchdog.dismiss()
            return
        mouse_button(True)
        mouse_button(False)
        state["pending"] = (
            "click", "physical_action_click", bool(target.isChecked()))
        phase("target_click_sent")

    def track_step(root_action):
        root_menu = root_action.menu()
        track_action = (_menu_action(root_menu, track_text)
                        if root_menu is not None else None)
        if track_action is None or track_action.menu() is None:
            abort("track_submenu_missing_or_ambiguous")
            return
        phase("track_submenu_visible")
        hover(root_menu, track_action,
              lambda: target_step(track_action))

    def root_step():
        root_menu = QApplication.activePopupWidget()
        if not isinstance(root_menu, QMenu):
            abort("root_popup_not_visible")
            return
        state["root_popup"] = root_menu
        watchdog.note_popup_seen()
        phase("root_popup_visible")
        root_action = _menu_action(root_menu, root_text)
        if root_action is None or root_action.menu() is None:
            abort("root_action_missing_or_ambiguous")
            return
        hover(root_menu, root_action,
              lambda: track_step(root_action))

    if not player_front():
        state["reason"] = "player_not_foreground"
        return state
    point = frame.mapToGlobal(frame.rect().center())
    hwnd = int(user32.WindowFromPoint(
        wintypes.POINT(int(point.x()), int(point.y()))) or 0)
    pid = ctypes.c_ulong(0)
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if int(pid.value) != os.getpid():
        state["reason"] = "video_surface_pid_mismatch"
        return state

    # This timer is armed BEFORE input which can synchronously enter the
    # product's nested QMenu.exec() loop.  The outer pump cannot bound that
    # loop because APP.processEvents() itself may not return.
    watchdog.arm(watchdog_timeout, popup_cleanup_complete)
    phase("context_open_start")
    QTimer.singleShot(250, root_step)
    user32.SetCursorPos(int(point.x()), int(point.y()))
    mouse_button(True, right=True)
    mouse_button(False, right=True)
    phase("context_open_sent")
    # Sag-tik QMenu.exec() nested loop'una girer. Yukaridaki timer zinciri
    # gorunen action'lari hedefleyip final click/Esc ile bu donguyu kapatir.
    pump(5000)
    state["menu_closed"] = root_popup_closed()
    if not state["done"]:
        if state["menu_closed"] and state.get("pending") is not None:
            popup_cleanup_complete(True, False)
        else:
            watchdog.dismiss()
            pump(800)
    watchdog.cancel()
    return state


PRODUCT_MENU_FAILURES = {
    "root_action_missing_or_ambiguous",
    "track_submenu_missing_or_ambiguous",
    "target_action_missing_or_ambiguous",
}


def menu_failure_result(reason):
    """Gecerli fixture sonrasi urun menusu bozuksa FAIL, erisim yoksa BLOCKED."""
    return False if reason in PRODUCT_MENU_FAILURES else None


def physical_drag(x0, y0, x1, y1, steps=14, hold=0.014, release=True):
    user32.SetCursorPos(int(x0), int(y0))
    pump(90)
    mouse_button(True)
    pump(80)
    for i in range(1, steps + 1):
        user32.SetCursorPos(int(x0 + (x1 - x0) * i / steps),
                            int(y0 + (y1 - y0) * i / steps))
        APP.processEvents()
        time.sleep(hold)
        APP.processEvents()
    pump(80)
    if release:
        mouse_button(False)
        pump(220)



# Resize icin AYRI THREAD'li girdi: `startSystemResize()` Windows'un native
# modal dongusune girdigi icin fiziksel girdi Qt GUI thread'inden
# gonderilirse press'ler gecikir/yanlis koordinatta gelir. Girdi yalnizca
# Win32 cagirisi yapan worker thread'den gonderilir; Qt thread'i bu sirada
# yalnizca olay isler. DIGER gruplar `physical_drag()` kullanmaya devam eder.
VK_LBUTTON = 0x01


def _button_down():
    return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)


def threaded_drag(x0, y0, x1, y1, steps=24, hold=0.02, expected_hwnd=None):
    """Girdiyi worker thread'den gonderir ve INPUT SOZLESMESINI olcer.

    Worker HICBIR Qt nesnesine dokunmaz. Rapor; imlec konumu, fare tusu
    durumu, baslangic HWND'si ve thread tamamlanmasini icerir; caginan
    taraf bunlari dogrulamadan PASS yazmamalidir.
    """
    import threading

    report = {"done": False}

    def worker():
        try:
            report["button_before"] = _button_down()
            user32.SetCursorPos(int(x0), int(y0))
            time.sleep(0.30)
            report["cursor_after_move"] = cursor_pos()
            if expected_hwnd is not None:
                point = wintypes.POINT(int(x0), int(y0))
                report["hwnd_at_start"] = int(user32.WindowFromPoint(point) or 0)
                report["hwnd_expected"] = int(expected_hwnd)
            mouse_button(True)
            time.sleep(0.25)
            report["button_after_down"] = _button_down()
            for index in range(1, steps + 1):
                user32.SetCursorPos(int(x0 + (x1 - x0) * index / steps),
                                    int(y0 + (y1 - y0) * index / steps))
                time.sleep(hold)
            time.sleep(0.25)
            mouse_button(False)
            time.sleep(0.30)
            report["button_after_up"] = _button_down()
            report["cursor_final"] = cursor_pos()
            report["ok"] = True
        except Exception as exc:
            report["error"] = type(exc).__name__
            report["ok"] = False
        finally:
            report["done"] = True

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    deadline = time.time() + 30
    while not report["done"] and time.time() < deadline:
        APP.processEvents()
        time.sleep(0.01)
    thread.join(timeout=5)
    pump(900)
    report["joined"] = not thread.is_alive()
    start = report.get("cursor_after_move")
    final = report.get("cursor_final")
    if start and final:
        report["cursor_delta"] = (final[0] - start[0], final[1] - start[1])
    report["intended_delta"] = (int(x1 - x0), int(y1 - y0))
    return report


def input_contract_problems(report):
    """Sozlesme ihlalleri; bos liste ise fiziksel girdi GUVENILIR."""
    problems = []
    if not report.get("ok"):
        problems.append(f"worker_error={report.get('error')}")
    if not report.get("joined"):
        problems.append("thread_not_joined")
    if report.get("button_before"):
        problems.append("button_down_before_press")
    if not report.get("button_after_down"):
        problems.append("button_not_down_after_press")
    if report.get("button_after_up"):
        problems.append("button_still_down_after_release")
    start = report.get("cursor_after_move")
    intended = report.get("intended_delta")
    final = report.get("cursor_final")
    if not start or not final:
        problems.append("cursor_not_measured")
    else:
        actual = report.get("cursor_delta")
        if abs(actual[0] - intended[0]) > 2 or abs(actual[1] - intended[1]) > 2:
            problems.append(f"cursor_delta={actual}!={intended}")
    if "hwnd_at_start" in report and             report["hwnd_at_start"] != report.get("hwnd_expected"):
        problems.append(f"hwnd_at_start={report['hwnd_at_start']}"
                        f"!={report.get('hwnd_expected')}")
    return problems


def playlist_button():
    widgets = []
    bar = getattr(PLAYER, "title_bar", None)
    if bar is not None:
        widgets.extend(bar.findChildren(QPushButton))
    overlay = PLAYER.video_frame.control_overlay
    if overlay is not None:
        widgets.extend(overlay.findChildren(QPushButton))
    for button in widgets:
        blob = ((button.objectName() or "") + "|" + (button.toolTip() or "")
                + "|" + (button.accessibleName() or "")).lower()
        if "playlist" in blob or "oynatma listesi" in blob:
            return button
    return None


def toggle_playlist_physical(label="playlist_toggle"):
    button = playlist_button()
    if button is None:
        record(label, "-", "playlist dugmesi", "dugme bulunamadi", None,
               "BLOCKED: playlist dugmesi yok")
        return False
    ready = click_ready(button, label + "_precondition")
    if ready is None:
        return False
    physical_click(ready[0], ready[1], settle=900)
    return True


def close_modal_dialogs():
    """Acik modal dialog'u GERCEK Esc ile kapatir (urun metodu cagrilmaz)."""
    dialogs = [w for w in QApplication.topLevelWidgets()
               if isinstance(w, QDialog) and w.isVisible()]
    if not dialogs:
        return []
    names = [w.windowTitle() or type(w).__name__ for w in dialogs]
    for _ in range(3):
        tap(VK_ESCAPE)
        time.sleep(0.35)
        if not [w for w in QApplication.topLevelWidgets()
                if isinstance(w, QDialog) and w.isVisible()]:
            break
    return names


# ================= GRUP 1 - overlay dugmeleri =================

def audio_output_safe():
    """Yuksek ses olcumu icin gercek MPV cikisi null mu?"""
    try:
        current = getattr(PLAYER.mpv_player, "current_ao", None)
    except Exception:
        current = None
    problems = audio_safety_problems(current)
    print(f"AUDIO_SAFETY requested=null actual={current} "
          f"safe={not problems} problems={problems}", flush=True)
    return not problems, current, problems


def group_buttons():
    frame, mpv = PLAYER.video_frame, PLAYER.mpv_player
    audio_safe, current_ao, audio_problems = audio_output_safe()
    for phase in ("closed", "open"):
        if phase == "open" and not frame.playlist_panel.is_open:
            toggle_playlist_physical()
            wait_for(lambda: frame.playlist_panel.is_open, 4000)
        shot(f"{phase}-start")

        # --- CC ONCE olculur (medya degistirmeden, track listesi kararliyken) ---
        wait_for(lambda: (mpv.duration or 0) > 0, 8000)
        subtitle_tracks_ready = wait_for(
            lambda: has_subtitle_track(mpv.track_list), 8000)
        # Fixture'ın gömülü altyazısı başlangıçta açık kalabilir. Testin
        # "cc_on" başlangıç sözleşmesini varsaymak yerine önce gerçek native
        # durumu kapalıya getir ve readback ile doğrula.
        if subtitle_tracks_ready and bool(mpv.sub_visibility):
            try:
                mpv.sub_visibility = False
            except Exception:
                pass
            wait_for(lambda: bool(mpv.sub_visibility) is False, 3000)
            frame._update_overlay_subtitle_state()
        if not subtitle_tracks_ready:
            record(f"cc_on[{phase}]", "on kosul",
                   "en az bir gercek altyazi track'i",
                   f"track_list={mpv.track_list}", None,
                   "BLOCKED: SUBTITLE_TRACK")
        else:
            cc = overlay_button("overlaySubtitles")
            ready = click_ready(cc, f"cc_on[{phase}]")
        if subtitle_tracks_ready and ready:
            before_icon = frame.overlay_subtitles_active
            physical_click(ready[0], ready[1], settle=300)
            turned_on = wait_for(lambda: bool(mpv.sub_visibility) is True, 5000)
            wait_for(lambda: frame.overlay_subtitles_active is True, 3000)
            record(f"cc_on[{phase}]", "SendInput click",
                   "sub_visibility False->True, ikon beyaz->turuncu",
                   f"visibility={mpv.sub_visibility} "
                   f"icon_active {before_icon}->{frame.overlay_subtitles_active}",
                   turned_on and frame.overlay_subtitles_active is True,
                   ready[2])
            ready2 = click_ready(cc, f"cc_off[{phase}]")
            if ready2:
                physical_click(ready2[0], ready2[1], settle=300)
                turned_off = wait_for(lambda: bool(mpv.sub_visibility) is False, 5000)
                wait_for(lambda: frame.overlay_subtitles_active is False, 3000)
                record(f"cc_off[{phase}]", "SendInput click",
                       "sub_visibility True->False, ikon turuncu->beyaz",
                       f"visibility={mpv.sub_visibility} "
                       f"icon_active={frame.overlay_subtitles_active}",
                       turned_off and frame.overlay_subtitles_active is False)

        # --- Play / pause (bounded polling) ---
        button = overlay_button("overlayPlayPause")
        ready = click_ready(button, f"play_pause[{phase}]")
        if ready:
            before = bool(mpv.pause)
            before_paused = bool(getattr(PLAYER, "is_paused", None))
            before_pos = mpv.time_pos or 0
            probe = ClickProbe(button, product_method="play_pause")
            delivered = physical_click(ready[0], ready[1], settle=200,
                                       target=button, label=f"play_pause[{phase}]")
            toggled = wait_for(lambda: bool(mpv.pause) != before, 5000)
            pump(400)
            after_pos = mpv.time_pos or 0
            print(f"DIAG|play_pause[{phase}]|{probe.summary(ready[0], ready[1])}|"
                  f"is_paused={before_paused}->{getattr(PLAYER, 'is_paused', None)} "
                  f"mpv_pause={before}->{mpv.pause} "
                  f"accessible={button.accessibleName()} "
                  f"position {before_pos:.2f}->{after_pos:.2f} "
                  f"delivered={delivered} "
                  f"geo={global_rect(button).getRect()}", flush=True)
            probe.release_probe()
            record(f"play_pause[{phase}]", "SendInput click",
                   "mpv.pause degisir (bounded polling)",
                   f"{before}->{mpv.pause}", toggled, ready[2])
            ready = click_ready(button, f"play_pause_restore[{phase}]")
            if ready:
                physical_click(ready[0], ready[1], settle=200)
                wait_for(lambda: bool(mpv.pause) == before, 5000)

        # --- Ses / mute ---
        vol = overlay_button("overlayVolume")
        if not audio_safe:
            record(f"mute[{phase}]", "on kosul", "ses cikisi null",
                   f"current_ao={current_ao} problems={audio_problems}", None,
                   "BLOCKED: AUDIO_SAFETY")
            ready = None
        else:
            ready = click_ready(vol, f"mute[{phase}]")
        if ready:
            before = bool(getattr(PLAYER, "is_muted", False))
            physical_click(ready[0], ready[1], settle=200)
            toggled = wait_for(
                lambda: bool(getattr(PLAYER, "is_muted", False)) != before, 4000)
            record(f"mute[{phase}]", "SendInput click", "is_muted degisir",
                   f"{before}->{getattr(PLAYER, 'is_muted', None)}", toggled,
                   ready[2])
            ready = click_ready(vol, f"mute_restore[{phase}]")
            if ready:
                physical_click(ready[0], ready[1], settle=200)
                wait_for(lambda: bool(getattr(PLAYER, "is_muted", False)) == before,
                         4000)

        # --- Ses slider'i ---
        # Sabit `%25` hedefi mevcut degere (0-175 araliginda ~44) denk
        # geldiginde tiklama calissa bile deger degismiyor ve olcum sahte
        # FAIL uretiyordu. Hedef artik mevcut degerden UZAK olacak sekilde
        # dinamik secilir; basari overlay + klasik slider + gercek
        # `mpv.volume` senkronuyla dogrulanir.
        slider = frame.overlay_volume_slider
        classic = PLAYER.volume_slider
        if getattr(PLAYER, "is_muted", False):
            # Onceki mute testinin geri yuklemesi eksik kaldiysa olcum
            # yanlis durumda baslamasin.
            mute_button = overlay_button("overlayVolume")
            ready_mute = click_ready(mute_button, f"volume_unmute[{phase}]")
            if ready_mute:
                physical_click(ready_mute[0], ready_mute[1], settle=300,
                               target=mute_button, label="volume_unmute")
                wait_for(lambda: not getattr(PLAYER, "is_muted", False), 4000)
        if not audio_safe:
            record(f"volume_slider[{phase}]", "on kosul", "ses cikisi null",
                   f"current_ao={current_ao} problems={audio_problems}", None,
                   "BLOCKED: AUDIO_SAFETY")
            ready = None
        else:
            ready = click_ready(slider, f"volume_slider[{phase}]")
        if ready:
            rect = global_rect(slider)
            before = slider.value()
            low, high = candidate_values(slider.minimum(), slider.maximum())
            target = pick_far_target(slider.minimum(), slider.maximum(), before)
            tolerance = value_tolerance_for_width(
                slider.minimum(), slider.maximum(), slider.width())
            local_x = target_x_for_value(target, slider.minimum(),
                                         slider.maximum(), slider.width())
            gx = rect.left() + local_x
            gy = rect.top() + rect.height() // 2

            # Hedef dogrulamasi: tiklama GONDERILMEDEN once.
            problems = []
            if not rect.contains(QPoint(int(gx), int(gy))):
                problems.append(f"point_outside rect={rect.getRect()}")
            widget = QApplication.widgetAt(QPoint(int(gx), int(gy)))
            owner = widget
            while owner is not None and owner is not slider:
                owner = owner.parent()
            if owner is not slider:
                problems.append(
                    f"widget_at={type(widget).__name__ if widget else None}")
            hwnd = int(user32.WindowFromPoint(
                wintypes.POINT(int(gx), int(gy))) or 0)
            overlay = frame.control_overlay
            expected_hwnds = {int(overlay.winId()) if overlay else 0,
                              int(frame.winId()), int(PLAYER.winId())}
            if hwnd not in expected_hwnds:
                problems.append(f"hwnd={hwnd}")
            if overlay is None or not overlay.isVisible():
                problems.append("overlay_hidden")
            elif overlay.windowOpacity() <= 0.0:
                problems.append("overlay_opacity=0")
            if not player_front():
                problems.append("player_not_foreground")

            if problems:
                record(f"volume_slider[{phase}]", "hedef dogrulamasi",
                       "nokta overlayVolumeSlider'a ait", str(problems), None,
                       "BLOCKED: CLICK_TARGET")
            else:
                physical_click(gx, gy, settle=300)

                def synced():
                    try:
                        mpv_volume = float(PLAYER.mpv_player.volume)
                    except Exception:
                        return False
                    return (abs(slider.value() - target) <= tolerance
                            and abs(classic.value() - target) <= tolerance
                            and abs(mpv_volume - target) <= max(1.0, tolerance))

                reached = wait_for(synced, 5000)
                try:
                    mpv_volume = float(PLAYER.mpv_player.volume)
                except Exception:
                    mpv_volume = -1.0
                record(f"volume_slider[{phase}]", "SendInput click",
                       f"overlay+klasik+mpv ~{target} (+-{tolerance}), "
                       "baslangictan farkli, down=False",
                       f"before={before} low_candidate={low} "
                       f"high_candidate={high} chosen_target={target} "
                       f"target_x={gx} overlay_value={slider.value()} "
                       f"classic_value={classic.value()} "
                       f"mpv_volume={mpv_volume:.1f} "
                       f"value_tolerance={tolerance} "
                       f"amplified={target > 100} hwnd={hwnd} "
                       f"widget_at_ok=True down={slider.isSliderDown()}",
                       reached and abs(slider.value() - before) > tolerance
                       and not slider.isSliderDown(), ready[2])

                # Baslangic sesini GERCEK fiziksel tiklamayla geri yukle.
                restore_x = rect.left() + target_x_for_value(
                    before, slider.minimum(), slider.maximum(), slider.width())
                if click_ready(slider, f"volume_restore[{phase}]"):
                    physical_click(restore_x, gy, settle=300)
                    wait_for(lambda: abs(slider.value() - before) <= tolerance,
                             4000)
                record(f"volume_state_clean[{phase}]", "durum temizligi",
                       "down=False, overlay/klasik/mpv senkron",
                       f"overlay={slider.value()} classic={classic.value()} "
                       f"muted={getattr(PLAYER, 'is_muted', None)} "
                       f"down={slider.isSliderDown()} "
                       f"playlist_open={frame.playlist_panel.is_open} "
                       f"overlay_visible={frame.control_overlay.isVisible()}",
                       not slider.isSliderDown()
                       and abs(slider.value() - classic.value()) <= tolerance)

        # --- Ayarlar: modal dialog bounded kapatma ile ---
        settings = overlay_button("overlaySettings")
        ready = click_ready(settings, f"settings[{phase}]")
        if ready:
            seen = {"dialogs": [], "hwnds": []}

            def probe():
                dialogs = [w for w in QApplication.topLevelWidgets()
                           if isinstance(w, QDialog) and w.isVisible()]
                if dialogs:
                    seen["dialogs"] = [w.windowTitle() or type(w).__name__
                                       for w in dialogs]
                    seen["hwnds"] = [int(w.winId()) for w in dialogs]
                    for _ in range(3):
                        tap(VK_ESCAPE)
                        time.sleep(0.4)
                        if not [w for w in QApplication.topLevelWidgets()
                                if isinstance(w, QDialog) and w.isVisible()]:
                            break

            # Modal exec() ic ice event loop calistirir; QTimer orada da atesler.
            QTimer.singleShot(1400, probe)
            pause_before = bool(mpv.pause)
            vol_before = slider.value()
            physical_click(ready[0], ready[1], settle=2600)
            close_modal_dialogs()
            pump(400)
            still_open = [w for w in QApplication.topLevelWidgets()
                          if isinstance(w, QDialog) and w.isVisible()]
            record(f"settings[{phase}]", "SendInput click + gercek Esc",
                   "dialog acilir (HWND ile dogrulanir) ve kapanir",
                   f"dialogs={seen['dialogs']} hwnds={seen['hwnds']} "
                   f"still_open={len(still_open)} "
                   f"pause_same={bool(mpv.pause) == pause_before} "
                   f"vol_same={slider.value() == vol_before}",
                   bool(seen["dialogs"]) and not still_open
                   and bool(mpv.pause) == pause_before
                   and slider.value() == vol_before, ready[2])

        # --- Sonraki / Onceki (medya yuklemesi beklenir) ---
        before_i = PLAYER.current_playlist_index
        next_available = playlist_step_available(
            len(PLAYER.playlist), before_i, 1)
        if not next_available:
            record(f"next[{phase}]", "on kosul",
                   "olculebilir sonraki playlist ogesi",
                   f"index={before_i} size={len(PLAYER.playlist)} ", None,
                   "BLOCKED: PLAYLIST_NEXT_ITEM")
        else:
            nxt = overlay_button("overlayNext")
            ready = click_ready(nxt, f"next[{phase}]")
        if next_available and ready:
            before_file = PLAYER.current_file
            modal_seen = []

            def dismiss_next_modal():
                modal_seen.extend(close_modal_dialogs())

            arm_modal_dismissal(QTimer.singleShot, dismiss_next_modal)
            physical_click(ready[0], ready[1],
                           settle=MODAL_DISMISS_DELAY_MS + 700)
            if modal_seen:
                advanced = loaded = False
            else:
                advanced = wait_for(
                    lambda: PLAYER.current_playlist_index == before_i + 1,
                    8000)
                loaded = wait_for(lambda: PLAYER.current_file != before_file
                                  and (mpv.duration or 0) > 0, 15000)
            record(f"next[{phase}]", "SendInput click",
                   "index +1 ve yeni medya yuklenir",
                   f"{before_i}->{PLAYER.current_playlist_index} "
                   f"loaded={loaded} duration={mpv.duration} "
                   f"modal_seen={modal_seen}",
                   advanced and loaded, ready[2])

        mid_i = PLAYER.current_playlist_index
        previous_available = playlist_step_available(
            len(PLAYER.playlist), mid_i, -1)
        if not previous_available:
            record(f"previous[{phase}]", "on kosul",
                   "olculebilir onceki playlist ogesi",
                   f"index={mid_i} size={len(PLAYER.playlist)}", None,
                   "BLOCKED: PLAYLIST_PREVIOUS_ITEM")
        else:
            prev = overlay_button("overlayPrevious")
            ready = click_ready(prev, f"previous[{phase}]")
        if previous_available and ready:
            mid_file = PLAYER.current_file
            modal_seen = []

            def dismiss_previous_modal():
                modal_seen.extend(close_modal_dialogs())

            arm_modal_dismissal(QTimer.singleShot,
                                dismiss_previous_modal)
            physical_click(ready[0], ready[1],
                           settle=MODAL_DISMISS_DELAY_MS + 700)
            if modal_seen:
                back = loaded2 = False
            else:
                back = wait_for(
                    lambda: PLAYER.current_playlist_index == mid_i - 1,
                    8000)
                loaded2 = wait_for(lambda: PLAYER.current_file != mid_file
                                   and (mpv.duration or 0) > 0, 15000)
            record(f"previous[{phase}]", "SendInput click",
                   "index -1 ve yeni medya yuklenir",
                   f"{mid_i}->{PLAYER.current_playlist_index} "
                   f"loaded={loaded2} modal_seen={modal_seen}",
                   back and loaded2, ready[2])

        # --- Fullscreen (gercek tiklama + gercek Esc) ---
        fs = overlay_button("overlayFullscreen")
        ready = click_ready(fs, f"fullscreen[{phase}]")
        if ready:
            physical_click(ready[0], ready[1], settle=400)
            entered = wait_for(lambda: frame.is_video_fullscreen, 5000)
            path = shot(f"{phase}-fullscreen")
            tap(VK_ESCAPE)
            exited = wait_for(lambda: not frame.is_video_fullscreen, 5000)
            record(f"fullscreen[{phase}]", "SendInput click + gercek Esc",
                   "fullscreen acilir ve Esc ile kapanir",
                   f"entered={entered} exited={exited}", entered and exited, path)
        shot(f"{phase}-end")


# ================= DAR WIN-P0-04 - playback + seek =================

def group_playback_seek():
    """Pause/resume ve temel seek davranisini tek dar native grupta olcer."""
    frame, mpv = PLAYER.video_frame, PLAYER.mpv_player
    timeline = live_overlay_widget(frame, "overlay_timeline")
    button = overlay_button("overlayPlayPause")
    if (timeline is None or button is None
            or click_ready(timeline, "playback_seek_timeline") is None):
        record("playback_seek_precondition", "on kosul",
               "timeline widget'i yasiyor ve tiklanabilir",
               "timeline yok veya tiklanamaz", None,
               "BLOCKED: PRECONDITION")
        return
    ready = click_ready(button, "playback_seek_play_pause")
    duration = float(mpv.duration or 0)
    if ready is None or duration <= 0:
        record("playback_seek_precondition", "on kosul",
               "play/pause tiklanabilir ve duration > 0",
               f"button_ready={ready is not None} duration={duration}", None,
               "BLOCKED: PRECONDITION")
        return

    initial_pause = bool(mpv.pause)
    if initial_pause:
        physical_click(ready[0], ready[1], settle=200, target=button,
                       label="playback_seek_initial_resume")
        if not wait_for(lambda: not bool(mpv.pause), 5000):
            record("initial_resume", "SendInput click", "mpv.pause=False",
                   f"mpv.pause={mpv.pause}", False)
            return

    ready = click_ready(button, "pause")
    if ready is None:
        return
    physical_click(ready[0], ready[1], settle=200, target=button, label="pause")
    paused = wait_for(lambda: bool(mpv.pause)
                      and bool(getattr(PLAYER, "is_paused", False)), 5000)
    record("pause", "SendInput click", "mpv.pause ve PLAYER.is_paused True",
           f"mpv.pause={mpv.pause} PLAYER.is_paused={PLAYER.is_paused}", paused)

    ready = click_ready(button, "resume")
    if ready is None:
        return
    physical_click(ready[0], ready[1], settle=200, target=button, label="resume")
    resumed = wait_for(lambda: not bool(mpv.pause)
                       and not bool(getattr(PLAYER, "is_paused", True)), 5000)
    before_progress = float(mpv.time_pos or 0)
    pump(1200)
    after_progress = float(mpv.time_pos or 0)
    progressed = resumed and after_progress > before_progress + 0.20
    record("resume", "SendInput click + state/time read-back",
           "pause False ve time_pos ilerler",
           f"mpv.pause={mpv.pause} PLAYER.is_paused={PLAYER.is_paused} "
           f"time_pos={before_progress:.3f}->{after_progress:.3f}", progressed)

    span = max(1, timeline.maximum() - timeline.minimum())
    value_tolerance = slider_value_tolerance(span, timeline.width())
    time_tolerance = seek_time_tolerance(duration)

    def target(ratio):
        rect = global_rect(timeline)
        x = rect.left() + int(rect.width() * ratio)
        y = rect.top() + rect.height() // 2
        value = int(round(timeline.minimum() + span * ratio))
        return x, y, value, (value * duration) / 1000.0

    def seek_ratio(ratio, label):
        wake_overlay()
        x, y, wanted, wanted_time = target(ratio)
        physical_click(x, y, settle=350, target=timeline, label=label)
        reached = wait_for(
            lambda: abs(timeline.value() - wanted) <= value_tolerance
            and abs(float(mpv.time_pos or 0) - wanted_time) <= time_tolerance,
            8000)
        return reached, wanted, wanted_time

    for ratio in (0.10, 0.50, 0.90):
        start_ratio = 0.90 if ratio < 0.50 else 0.10
        start_ok, _, _ = seek_ratio(start_ratio, f"seek_start_{ratio:.2f}")
        before_value = timeline.value()
        reached, wanted, wanted_time = seek_ratio(ratio, f"seek_{ratio:.2f}")
        value_now = timeline.value()
        pos_now = float(mpv.time_pos or 0)
        record(f"seek_{int(ratio * 100)}", "SendInput click",
               f"value={wanted}(+-{value_tolerance}) time={wanted_time:.1f}"
               f"(+-{time_tolerance:.1f}) ve down=False",
               f"start_ok={start_ok} start={before_value} value={value_now} "
               f"time_pos={pos_now:.2f} down={timeline.isSliderDown()}",
               start_ok and reached
               and abs(value_now - before_value) > value_tolerance
               and not timeline.isSliderDown())

    start_ok, _, _ = seek_ratio(0.10, "drag_start")
    wake_overlay()
    x0, y0, _, _ = target(0.20)
    x1, _, wanted, wanted_time = target(0.70)
    report = threaded_drag(x0, y0, x1, y0, steps=12, hold=0.02)
    problems = input_contract_problems(report)
    reached = wait_for(
        lambda: abs(timeline.value() - wanted) <= value_tolerance
        and abs(float(mpv.time_pos or 0) - wanted_time) <= time_tolerance,
        8000)
    record("seek_drag", "SendInput worker-thread drag",
           f"value={wanted}(+-{value_tolerance}) time={wanted_time:.1f}"
           f"(+-{time_tolerance:.1f}) ve down=False",
           f"start_ok={start_ok} problems={problems} value={timeline.value()} "
           f"time_pos={float(mpv.time_pos or 0):.2f} "
           f"down={timeline.isSliderDown()}",
           start_ok and not problems and reached and not timeline.isSliderDown())

    if initial_pause and not bool(mpv.pause):
        ready = click_ready(button, "playback_seek_restore_pause")
        if ready:
            physical_click(ready[0], ready[1], settle=200, target=button,
                           label="playback_seek_restore_pause")
            wait_for(lambda: bool(mpv.pause), 5000)


# ================= GRUP 2 - timeline =================

def group_timeline():
    """Timeline fiziksel kabulu: HER nokta bagimsiz olculur.

    Eski surum ayni x oranina once `on`, sonra `above`, sonra `below`
    tikliyor ve her seferinde deger DEGISMESINI bekliyordu; ikinci ve
    ucuncu tiklama zaten ayni orandaki konuma dustugu icin 36 sahte FAIL
    uretiyordu. Artik her olcumden once timeline UZAK bir orana gercek
    tiklamayla goturuluyor ve basari, hedef x'ten HESAPLANAN slider degeri
    ile gercek `mpv.time_pos` hedefine yakinlikla dogrulaniyor.
    """
    frame, mpv = PLAYER.video_frame, PLAYER.mpv_player
    # Referans HER faz ve HER olcum oncesinde yenilenir: urun kapanisi
    # widget'i silerse eski referans ham `RuntimeError` uretirdi.
    timeline = live_overlay_widget(frame, "overlay_timeline")
    if timeline is None:
        record("timeline_precondition", "on kosul", "timeline widget'i yasiyor",
               "overlay_timeline yok veya silinmis", None,
               "BLOCKED: WIDGET_GONE")
        return
    duration = float(mpv.duration or 0)
    if duration <= 0:
        record("timeline_precondition", "on kosul", "duration > 0",
               f"duration={duration}", None, "BLOCKED: PRECONDITION")
        return

    span = max(1, timeline.maximum() - timeline.minimum())
    # Toleranslar TEK kaynaktan (tests/physical_tolerances.py):
    # slider toleransi PIKSEL cozunurlugunden, zaman toleransi ise sureyle
    # hafif olceklenip 15 sn ile sinirlanir. Urun gercek `time_pos`
    # hedefini izler; olculen sapma bir saniyenin altindadir.
    value_tolerance = slider_value_tolerance(span, timeline.width())
    time_tolerance = seek_time_tolerance(duration)
    print(f"TIMELINE_TOLERANCE span={span} width={timeline.width()} "
          f"value_tolerance={value_tolerance} "
          f"time_tolerance={time_tolerance:.2f} duration={duration:.1f}",
          flush=True)

    def line_centre_y():
        rect = global_rect(timeline)
        return rect.top() + rect.height() // 2

    def expected_value(global_x):
        rect = global_rect(timeline)
        local_x = global_x - rect.left()
        ratio = min(1.0, max(0.0, local_x / max(1, timeline.width())))
        return int(round(timeline.minimum() + span * ratio))

    def expected_time(value):
        return (value * duration) / 1000.0

    def target_problems(gx, gy):
        """Tiklama GONDERILMEDEN once hedefin gercekten timeline oldugu."""
        problems = []
        rect = global_rect(timeline)
        if not rect.contains(QPoint(int(gx), int(gy))):
            problems.append(f"point_outside_timeline rect={rect.getRect()}")
        widget = QApplication.widgetAt(QPoint(int(gx), int(gy)))
        owner = widget
        while owner is not None and owner is not timeline:
            owner = owner.parent()
        if owner is not timeline:
            problems.append(f"widget_at={type(widget).__name__ if widget else None}")
        hwnd = int(user32.WindowFromPoint(
            wintypes.POINT(int(gx), int(gy))) or 0)
        overlay = frame.control_overlay
        expected_hwnds = {int(overlay.winId()) if overlay else 0,
                          int(frame.winId()), int(PLAYER.winId())}
        if hwnd not in expected_hwnds:
            problems.append(f"hwnd={hwnd} not in {sorted(expected_hwnds)}")
        if overlay is None or not overlay.isVisible():
            problems.append("overlay_hidden")
        elif overlay.windowOpacity() <= 0.0:
            problems.append("overlay_opacity=0")
        if not player_front():
            problems.append("player_not_foreground")
        return problems, hwnd

    def seek_to_ratio(ratio, label):
        """Baslangic konumunu GERCEK tiklamayla kurar (setValue kullanilmaz)."""
        # Widget olcum SIRASINDA da silinebilir (urun kapanisi); `wait_for`
        # istisnayi yuttugu icin cokme raporlama satirinda olurdu.
        if not widget_alive(timeline):
            return None, "BLOCKED: WIDGET_GONE"
        wake_overlay()
        rect = global_rect(timeline)
        gx = rect.left() + int(rect.width() * ratio)
        gy = line_centre_y()
        problems, _ = target_problems(gx, gy)
        if problems:
            return None, f"target={problems}"
        wanted = expected_value(gx)
        physical_click(gx, gy, settle=350)
        ok = wait_for(lambda: abs(timeline.value() - wanted) <= value_tolerance
                      and abs(float(mpv.time_pos or 0)
                              - expected_time(wanted)) <= time_tolerance, 8000)
        if not ok:
            if not widget_alive(timeline):
                return None, "BLOCKED: WIDGET_GONE"
            return None, (f"start_value={timeline.value()}(beklenen~{wanted}) "
                          f"time_pos={float(mpv.time_pos or 0):.1f}"
                          f"(beklenen~{expected_time(wanted):.1f})")
        return wanted, ""

    for phase in ("closed", "open", "fullscreen"):
        if phase == "open" and not frame.playlist_panel.is_open:
            toggle_playlist_physical()
            wait_for(lambda: frame.playlist_panel.is_open, 4000)
        if phase == "fullscreen":
            fs = overlay_button("overlayFullscreen")
            ready = click_ready(fs, f"fs_for_timeline[{phase}]")
            if ready:
                physical_click(ready[0], ready[1], settle=600, target=fs,
                               label="fs_for_timeline")
                wait_for(lambda: frame.is_video_fullscreen, 5000)
            if not frame.is_video_fullscreen:
                record(f"timeline_precondition[{phase}]", "on kosul",
                       "fullscreen acilir", "acilamadi", None,
                       "BLOCKED: PRECONDITION")
                continue
        # Faz gecisi (playlist, fullscreen) sonrasi GUNCEL referans.
        timeline = live_overlay_widget(frame, "overlay_timeline")
        if timeline is None:
            record(f"timeline_precondition[{phase}]", "on kosul",
                   "timeline widget'i yasiyor", "overlay_timeline silinmis",
                   None, "BLOCKED: WIDGET_GONE")
            return
        if click_ready(timeline, f"timeline_precondition[{phase}]") is None:
            continue

        for ratio in (0.10, 0.25, 0.50, 0.75, 0.90):
            for dy, where in ((0, "on"), (-17, "above"), (17, "below")):
                name = f"click_{int(ratio * 100)}_{where}[{phase}]"
                timeline = live_overlay_widget(frame, "overlay_timeline")
                if timeline is None:
                    record(name, "on kosul", "timeline widget'i yasiyor",
                           "overlay_timeline silinmis", None,
                           "BLOCKED: WIDGET_GONE")
                    return
                # BAGIMSIZLIK: hedeften UZAK bir orandan basla.
                start_ratio = 0.90 if ratio < 0.50 else 0.10
                start_value, detail = seek_to_ratio(start_ratio, name)
                if start_value is None:
                    record(name, "on kosul",
                           f"baslangic ~%{int(start_ratio * 100)} kurulur",
                           detail, None, "BLOCKED: PRECONDITION")
                    continue
                wake_overlay()
                rect = global_rect(timeline)
                gx = rect.left() + int(rect.width() * ratio)
                gy = line_centre_y() + dy
                problems, hwnd = target_problems(gx, gy)
                if problems:
                    record(name, "hedef dogrulamasi",
                           "nokta timeline'a ait", str(problems), None,
                           "BLOCKED: CLICK_TARGET")
                    continue
                wanted = expected_value(gx)
                wanted_time = expected_time(wanted)
                before_value = timeline.value()
                physical_click(gx, gy, settle=350)
                reached = wait_for(
                    lambda: abs(timeline.value() - wanted) <= value_tolerance
                    and abs(float(mpv.time_pos or 0) - wanted_time)
                    <= time_tolerance, 8000)
                value_now = timeline.value()
                pos_now = float(mpv.time_pos or 0)
                record(name, "SendInput click",
                       f"expected_value={wanted}(+-{value_tolerance}), "
                       f"expected_time={wanted_time:.1f}"
                       f"(+-{time_tolerance:.1f}), baslangictan farkli, "
                       "down=False",
                       f"expected_value={wanted} actual_value={value_now} "
                       f"value_error={value_now - wanted} "
                       f"expected_time={wanted_time:.1f} "
                       f"actual_time={pos_now:.1f} "
                       f"time_error={pos_now - wanted_time:.2f} "
                       f"value_tolerance={value_tolerance} "
                       f"time_tolerance={time_tolerance:.2f} "
                       f"start={before_value} hwnd={hwnd} "
                       f"down={timeline.isSliderDown()}",
                       reached and abs(value_now - before_value) > value_tolerance
                       and not timeline.isSliderDown())

        # --- Suruklemeler: worker-thread girdi ---
        for speed, hold in (("fast", 0.006), ("slow", 0.03)):
            name = f"drag_{speed}[{phase}]"
            timeline = live_overlay_widget(frame, "overlay_timeline")
            if timeline is None:
                record(name, "on kosul", "timeline widget'i yasiyor",
                       "overlay_timeline silinmis", None,
                       "BLOCKED: WIDGET_GONE")
                return
            start_value, detail = seek_to_ratio(0.10, name)
            if start_value is None:
                record(name, "on kosul", "baslangic ~%10 kurulur", detail,
                       None, "BLOCKED: PRECONDITION")
                continue
            wake_overlay()
            rect = global_rect(timeline)
            cy = line_centre_y()
            x0 = rect.left() + int(rect.width() * 0.20)
            x1 = rect.left() + int(rect.width() * 0.70)
            problems, _ = target_problems(x0, cy)
            if problems:
                record(name, "hedef dogrulamasi", "nokta timeline'a ait",
                       str(problems), None, "BLOCKED: CLICK_TARGET")
                continue
            wanted = expected_value(x1)
            wanted_time = expected_time(wanted)
            report = threaded_drag(x0, cy, x1, cy, steps=12, hold=hold)
            input_problems = input_contract_problems(report)
            if input_problems:
                record(name, "SendInput (worker thread)",
                       "input sozlesmesi saglanir",
                       f"report={report} problems={input_problems}", None,
                       "BLOCKED: INPUT_CONTRACT")
                continue
            reached = wait_for(
                lambda: abs(timeline.value() - wanted) <= value_tolerance
                and abs(float(mpv.time_pos or 0) - wanted_time)
                <= time_tolerance, 8000)
            value_now = timeline.value()
            pos_now = float(mpv.time_pos or 0)
            record(name, "SendInput (worker thread)",
                   f"expected_value={wanted}(+-{value_tolerance}), "
                   f"expected_time={wanted_time:.1f}(+-{time_tolerance:.1f}), "
                   "down=False",
                   f"expected_value={wanted} actual_value={value_now} "
                   f"value_error={value_now - wanted} "
                   f"expected_time={wanted_time:.1f} actual_time={pos_now:.1f} "
                   f"time_error={pos_now - wanted_time:.2f} "
                   f"value_tolerance={value_tolerance} "
                   f"time_tolerance={time_tolerance:.2f} "
                   f"cursor_delta={report.get('cursor_delta')} "
                   f"down={timeline.isSliderDown()}",
                   reached and not timeline.isSliderDown())

        # --- Overlay disina birakma ---
        name = f"drag_out[{phase}]"
        timeline = live_overlay_widget(frame, "overlay_timeline")
        if timeline is None:
            record(name, "on kosul", "timeline widget'i yasiyor",
                   "overlay_timeline silinmis", None, "BLOCKED: WIDGET_GONE")
            return
        start_value, detail = seek_to_ratio(0.90, name)
        if start_value is None:
            record(name, "on kosul", "baslangic ~%90 kurulur", detail, None,
                   "BLOCKED: PRECONDITION")
        else:
            wake_overlay()
            rect = global_rect(timeline)
            cy = line_centre_y()
            x0 = rect.left() + int(rect.width() * 0.60)
            problems, _ = target_problems(x0, cy)
            if problems:
                record(name, "hedef dogrulamasi", "basis timeline uzerinde",
                       str(problems), None, "BLOCKED: CLICK_TARGET")
            else:
                report = threaded_drag(x0, cy,
                                       rect.left() + int(rect.width() * 0.30),
                                       rect.top() - 240, steps=12)
                input_problems = input_contract_problems(report)
                if input_problems:
                    record(name, "SendInput (worker thread)",
                           "input sozlesmesi saglanir",
                           f"report={report} problems={input_problems}", None,
                           "BLOCKED: INPUT_CONTRACT")
                else:
                    released = not timeline.isSliderDown()
                    # Birakma sonrasi NORMAL tiklama hala calismali.
                    follow, follow_detail = seek_to_ratio(0.50, name)
                    record(name, "SendInput (worker thread)",
                           "surukleme durumu temizlenir ve sonraki tiklama "
                           "calisir",
                           f"down={timeline.isSliderDown()} "
                           f"follow_up_value={timeline.value()} "
                           f"detail={follow_detail}",
                           released and follow is not None
                           and not timeline.isSliderDown())

        shot(f"timeline-{phase}")
        record(f"timeline_state_clean[{phase}]", "durum temizligi",
               "down=False, fullscreen yalniz kendi phase'inde",
               f"down={timeline.isSliderDown()} "
               f"fullscreen={frame.is_video_fullscreen} "
               f"playlist_open={frame.playlist_panel.is_open} "
               f"overlay_visible={frame.control_overlay.isVisible()}",
               not timeline.isSliderDown()
               and (frame.is_video_fullscreen == (phase == "fullscreen")))
        if phase == "fullscreen":
            tap(VK_ESCAPE)
            wait_for(lambda: not frame.is_video_fullscreen, 5000)


# ================= GRUP 3 - ayirac =================

def group_separator():
    frame = PLAYER.video_frame
    if not frame.playlist_panel.is_open:
        toggle_playlist_physical()
        wait_for(lambda: frame.playlist_panel.is_open, 5000)
    panel = frame.playlist_panel
    handle = panel.resize_handle
    if not player_front():
        record("separator", "onkosul", "foreground", str(foreground_info()), False)
        return
    hx, hy = global_centre(handle)
    user32.SetCursorPos(hx, hy)
    pump(400)
    shape = handle.cursor().shape()
    hit = QApplication.widgetAt(QPoint(hx, hy))
    record("resize_cursor", "gercek imlec konumu",
           "SizeHorCursor + hedef ayirac", f"shape={shape} widgetAt={hit}",
           shape == Qt.CursorShape.SizeHorCursor)

    before = panel.width()
    physical_drag(hx, hy, hx - 120, hy, steps=14, hold=0.02)
    widened = panel.width()
    overlap = global_rect(panel).intersected(global_rect(frame))
    record("drag_left", "SendInput press/move/release",
           "panel genisler, kesisme yok, panel gorunur",
           f"{before}->{widened} overlap="
           f"{overlap.getRect() if not overlap.isEmpty() else None} "
           f"visible={panel.isVisible()} open={panel.is_open}",
           widened > before and overlap.isEmpty() and panel.isVisible()
           and panel.is_open)

    hx, hy = global_centre(handle)
    physical_drag(hx, hy, hx + 90, hy, steps=14, hold=0.02)
    narrowed = panel.width()
    record("drag_right", "SendInput press/move/release",
           "panel daralir, >=320", f"{widened}->{narrowed}",
           narrowed < widened and narrowed >= 320)

    hx, hy = global_centre(handle)
    physical_drag(hx, hy, hx - 4000, hy, steps=18, hold=0.006)
    maxed = panel.width()
    hx, hy = global_centre(handle)
    physical_drag(hx, hy, hx + 4000, hy, steps=18, hold=0.006)
    minned = panel.width()
    record("drag_limits", "SendInput asiri surukleme",
           "sinirlar korunur, panel kapanmaz",
           f"max={maxed} min={minned} open={panel.is_open} "
           f"press_state={panel._split_press_global_x}",
           minned >= 320 and maxed > minned and panel.is_open
           and panel._split_press_global_x is None)

    # NOT: Medya yuklu DEGILKEN urun play_pause() modal dosya secici acar ve
    # event loop'u bloklar. Bu kontrol yalnizca gercek dosya varken yapilir.
    play = overlay_button("overlayPlayPause")
    ready = click_ready(play, "post_drag_click") if PLAYER.current_file else None
    ok = False
    if not PLAYER.current_file:
        record("normal_click_after_drag", "-", "surukleme sonrasi tiklama",
               "medya yuklu degil", None, "BLOCKED: video yolu verilmedi")
    if ready:
        before_pause = bool(PLAYER.mpv_player.pause)
        physical_click(ready[0], ready[1], settle=200)
        ok = wait_for(lambda: bool(PLAYER.mpv_player.pause) != before_pause, 5000)
        if ok:
            physical_click(ready[0], ready[1], settle=200)
    record("normal_click_after_drag", "SendInput click",
           "surukleme sonrasi normal tiklama calisir", f"toggled={ok}", ok)
    shot("separator")


# ================= GRUP 4 - pencere kenar/kose resize =================

def group_window_resize():
    """Sekiz yon: her olcum KONUM+BOYUT sifirlanmis ve BAGIMSIZ.

    Eski surum sekiz yonu ayni oturumda art arda deniyor, yalnizca
    `resize()` ile boyutu geri aliyor (konumu degil) ve girdiyi GUI
    thread'inden gonderiyordu; bu yuzden yanlis koordinatli press'ler ve
    70 px hareket icin 400-900 px degisim gibi anlamsiz sonuclar cikiyordu.
    """
    frame = PLAYER.video_frame
    if frame.playlist_panel.is_open:
        toggle_playlist_physical()
        wait_for(lambda: not frame.playlist_panel.is_open, 4000)

    start_x, start_y, start_w, start_h = 300, 200, 1200, 720
    distance = 70
    tolerance = 20
    stable = 12

    def reset_window():
        PLAYER.showNormal()
        pump(200)
        PLAYER.setGeometry(start_x, start_y, start_w, start_h)
        pump(400)
        return wait_for(lambda: (abs(PLAYER.geometry().x() - start_x) <= 2
                                 and abs(PLAYER.geometry().y() - start_y) <= 2
                                 and abs(PLAYER.geometry().width() - start_w) <= 2
                                 and abs(PLAYER.geometry().height() - start_h) <= 2),
                        4000)

    def edges_of(rect):
        return {"left": rect[0], "top": rect[1],
                "right": rect[0] + rect[2], "bottom": rect[1] + rect[3]}

    directions = {
        "left": (lambda r: (r.left() + 3, r.center().y()), (-distance, 0),
                 {"left": -distance, "right": 0}),
        "right": (lambda r: (r.right() - 3, r.center().y()), (distance, 0),
                  {"right": distance, "left": 0}),
        "top": (lambda r: (r.center().x(), r.top() + 3), (0, -distance),
                {"top": -distance, "bottom": 0}),
        "bottom": (lambda r: (r.center().x(), r.bottom() - 3), (0, distance),
                   {"bottom": distance, "top": 0}),
        "top_left": (lambda r: (r.left() + 3, r.top() + 3),
                     (-distance, -distance),
                     {"left": -distance, "top": -distance,
                      "right": 0, "bottom": 0}),
        "top_right": (lambda r: (r.right() - 3, r.top() + 3),
                      (distance, -distance),
                      {"right": distance, "top": -distance,
                       "left": 0, "bottom": 0}),
        "bottom_left": (lambda r: (r.left() + 3, r.bottom() - 3),
                        (-distance, distance),
                        {"left": -distance, "bottom": distance,
                         "right": 0, "top": 0}),
        "bottom_right": (lambda r: (r.right() - 3, r.bottom() - 3),
                         (distance, distance),
                         {"right": distance, "bottom": distance,
                          "left": 0, "top": 0}),
    }

    for name, (point_fn, delta, expectations) in directions.items():
        if not reset_window():
            record(f"resize_{name}", "on kosul",
                   "olcum oncesi geometri sifirlanir",
                   f"geo={PLAYER.geometry().getRect()}", None,
                   "BLOCKED: baslangic geometrisi kurulamadi")
            continue
        if not player_front():
            record(f"resize_{name}", "on kosul", "player foreground",
                   "alinamadi", None, "BLOCKED: INPUT_CONTRACT foreground")
            continue
        before = PLAYER.frameGeometry().getRect()
        rect = PLAYER.frameGeometry()
        px, py = point_fn(rect)
        expected_hwnd = int(user32.WindowFromPoint(
            wintypes.POINT(int(px), int(py))) or 0)
        report = threaded_drag(px, py, px + delta[0], py + delta[1],
                               expected_hwnd=expected_hwnd)
        after = PLAYER.frameGeometry().getRect()
        before_edges, after_edges = edges_of(before), edges_of(after)
        deltas = {key: after_edges[key] - before_edges[key]
                  for key in before_edges}
        problems = []
        for edge, wanted in expectations.items():
            actual = deltas[edge]
            if wanted == 0:
                if abs(actual) > stable:
                    problems.append(f"{edge}={actual}(sabit olmali)")
            elif abs(actual - wanted) > max(tolerance, abs(wanted) * 0.25):
                problems.append(f"{edge}={actual}(beklenen~{wanted})")
        input_problems = input_contract_problems(report)
        if input_problems:
            record(f"resize_{name}", "SendInput (worker thread)",
                   "input sozlesmesi saglanir",
                   f"report={report} problems={input_problems}", None,
                   "BLOCKED: INPUT_CONTRACT")
            continue
        record(f"resize_{name}", "SendInput (worker thread)",
               f"kenar degisimi {expectations} (+-{tolerance} px)",
               f"before={before} after={after} deltas={deltas} "
               f"intended={delta} cursor_delta={report.get('cursor_delta')} "
               f"problems={problems}", not problems)
    reset_window()
    shot("window-resize")

    toggle_playlist_physical()
    wait_for(lambda: frame.playlist_panel.is_open, 4000)
    # Playlist açıkken de ana pencerenin tüm dış kenar/köşelerini ölç. Sağ
    # orta ortak sınır playlist'e ait kalır; sağ köşelerde çapraz bileşen
    # korunur. Sol/üst/alt yüzeyler ana pencerenin bağımsız sınırlarıdır.
    for name in ("left", "right", "top", "bottom", "top_left",
                 "top_right", "bottom_left", "bottom_right"):
        if not reset_window():
            record(f"resize_{name}_playlist_open", "on kosul",
                   "olcum oncesi geometri sifirlanir",
                   f"geo={PLAYER.geometry().getRect()}", None,
                   "BLOCKED: baslangic geometrisi kurulamadi")
            continue
        point_fn, delta, expectations = directions[name]
        # Yapışık playlist ana pencerenin sağ orta sınırını sahiplenir. Ana
        # pencerenin gerçek köşesinde ise çapraz resize korunur; sağ köşeler
        # hem sağ hem dikey bileşeni uygular. Deterministik title-bar
        # sözleşmesi (`_effective_resize_edges`) ile fiziksel ölçüm aynı
        # politikayı taşır.
        if name == "right":
            expectations = {"right": 0, "left": 0}
        elif name == "top_right":
            expectations = {"right": delta[0], "top": delta[1],
                            "left": 0, "bottom": 0}
        elif name == "bottom_right":
            expectations = {"right": delta[0], "bottom": delta[1],
                            "left": 0, "top": 0}
        before = PLAYER.frameGeometry().getRect()
        rect = PLAYER.frameGeometry()
        px, py = point_fn(rect)
        expected_hwnd = int(user32.WindowFromPoint(
            wintypes.POINT(int(px), int(py))) or 0)
        report = threaded_drag(px, py, px + delta[0], py + delta[1],
                               expected_hwnd=expected_hwnd)
        after = PLAYER.frameGeometry().getRect()
        input_problems = input_contract_problems(report)
        if input_problems:
            record(f"resize_{name}_playlist_open", "SendInput (worker thread)",
                   "input sozlesmesi saglanir",
                   f"report={report} problems={input_problems}", None,
                   "BLOCKED: INPUT_CONTRACT")
            continue
        before_edges, after_edges = edges_of(before), edges_of(after)
        deltas = {key: after_edges[key] - before_edges[key]
                  for key in before_edges}
        # Resize GERCEKTEN olmali: yalnizca `overlap.isEmpty()` kontrolu,
        # hic resize olmadigi durumda da PASS uretirdi.
        problems = []
        for edge, wanted in expectations.items():
            actual = deltas[edge]
            if wanted == 0:
                if abs(actual) > stable:
                    problems.append(f"{edge}={actual}(sabit olmali)")
            elif abs(actual - wanted) > max(tolerance, abs(wanted) * 0.25):
                problems.append(f"{edge}={actual}(beklenen~{wanted})")
        overlap = global_rect(frame.playlist_panel).intersected(global_rect(frame))
        if not overlap.isEmpty():
            problems.append(f"overlap={overlap.getRect()}")
        record(f"resize_{name}_playlist_open", "SendInput (worker thread)",
               f"kenar degisimi {expectations} (+-{tolerance} px) VE "
               "video/playlist ic ice girmez",
               f"before={before} after={after} deltas={deltas} "
               f"intended={delta} cursor_delta={report.get('cursor_delta')} "
               f"overlap={overlap.getRect() if not overlap.isEmpty() else None} "
               f"problems={problems}", not problems)
    shot("window-resize-playlist-open")


# ================= GRUP 5 - gercek Alt+Tab =================

def alt_tab():
    key(VK_MENU, True)
    time.sleep(0.06)
    tap(VK_TAB)
    time.sleep(0.30)
    key(VK_MENU, False)
    pump(1000)


def group_alttab():
    frame = PLAYER.video_frame
    for phase in ("closed", "open", "fullscreen"):
        if phase == "open" and not frame.playlist_panel.is_open:
            toggle_playlist_physical()
            wait_for(lambda: frame.playlist_panel.is_open, 4000)
        if phase == "closed" and frame.playlist_panel.is_open:
            toggle_playlist_physical()
            wait_for(lambda: not frame.playlist_panel.is_open, 4000)
        if phase == "fullscreen":
            fs = overlay_button("overlayFullscreen")
            ready = click_ready(fs, "fs_for_alttab")
            if ready:
                physical_click(ready[0], ready[1], settle=500)
                wait_for(lambda: frame.is_video_fullscreen, 5000)
        player_front()
        before_open = frame.playlist_panel.is_open
        shot(f"alttab-{phase}-before")

        alt_tab()
        hwnd, pid = foreground_info()
        external = pid != os.getpid()
        overlay_vis = frame.control_overlay.isVisible()
        osd_vis = frame.osd_label.isVisible()
        path = shot(f"alttab-{phase}-away")
        record(f"alt_tab_away[{phase}]", "gercek Alt+Tab",
               "player arkada; overlay/timeline/OSD ustte kalmaz",
               f"fg_pid={pid} own={os.getpid()} overlay={overlay_vis} "
               f"osd={osd_vis}", external and not overlay_vis and not osd_vis,
               path)

        alt_tab()
        pump(700)
        _, pid2 = foreground_info()
        if pid2 != os.getpid():
            player_front()
            pump(400)
            _, pid2 = foreground_info()
        wake_overlay()
        back_ok = wait_for(lambda: frame.control_overlay.isVisible(), 4000)
        path = shot(f"alttab-{phase}-back")
        record(f"alt_tab_back[{phase}]", "gercek Alt+Tab",
               "player onde, playlist durumu korunur, overlay doner",
               f"fg_pid={pid2} playlist_open={frame.playlist_panel.is_open} "
               f"(onceki={before_open}) overlay={frame.control_overlay.isVisible()}",
               pid2 == os.getpid() and frame.playlist_panel.is_open == before_open
               and back_ok, path)
        if phase == "fullscreen":
            tap(VK_ESCAPE)
            wait_for(lambda: not frame.is_video_fullscreen, 5000)


# ================= GRUP 6 - 10 kez ac/kapat akiciligi =================

def group_toggle():
    frame = PLAYER.video_frame
    for context in ("normal", "after_fullscreen"):
        if context == "after_fullscreen":
            fs = overlay_button("overlayFullscreen")
            ready = click_ready(fs, "fs_for_toggle")
            if ready:
                physical_click(ready[0], ready[1], settle=600)
                wait_for(lambda: frame.is_video_fullscreen, 5000)
                tap(VK_ESCAPE)
                wait_for(lambda: not frame.is_video_fullscreen, 5000)
        durations, overlaps = [], 0
        resize_count = {"n": 0}
        original_resize = type(frame).resizeEvent

        def counting(self, event, _orig=original_resize):
            if self is frame:
                resize_count["n"] += 1
            return _orig(self, event)

        type(frame).resizeEvent = counting
        try:
            for index in range(10):
                start = time.time()
                if not toggle_playlist_physical(f"toggle_{context}_{index}"):
                    break
                target = not frame.playlist_panel.is_open
                wait_for(lambda: frame.playlist_panel.animation.state().name
                         != "Running", 4000)
                durations.append(round((time.time() - start) * 1000))
                host = PLAYER.playlist_dock_host
                visible = global_rect(frame.playlist_panel).intersected(
                    global_rect(host))
                if not visible.intersected(global_rect(frame)).isEmpty():
                    overlaps += 1
                if index in (0, 4, 9):
                    shot(f"toggle-{context}-{index}")
        finally:
            type(frame).resizeEvent = original_resize
        per_transition = round(resize_count["n"] / max(1, len(durations)), 2)
        record(f"toggle_x10[{context}]", "gercek playlist dugmesi tiklamasi",
               "gecis basina ~1 video resize, kesisme yok",
               f"transitions={len(durations)} "
               f"avg_ms={round(sum(durations)/max(1,len(durations)))} "
               f"max_ms={max(durations) if durations else 0} "
               f"video_resizes={resize_count['n']} per_transition={per_transition} "
               f"overlaps={overlaps} open_at_end={frame.playlist_panel.is_open} "
               f"width={frame.playlist_panel.width()}",
               len(durations) >= 10 and overlaps == 0 and per_transition <= 3)


# ================= GRUP 7 - Explorer drag/drop =================

def group_dragdrop():
    record("explorer_multi_drop", "Explorer OLE surukle-birak",
           "Explorer'dan coklu dosya birakma", "otomasyon uygulanmadi", None,
           "BLOCKED: Explorer OLE drag/drop guvenilir otomasyonu yok; "
           "add_external_files() cagirmak fiziksel PASS sayilmaz")


# ================= GRUP 8 - thumbnail =================

def group_thumbnails():
    frame = PLAYER.video_frame
    if not frame.playlist_panel.is_open:
        toggle_playlist_physical()
        wait_for(lambda: frame.playlist_panel.is_open, 4000)
    panel = frame.playlist_panel
    wait_for(lambda: all(panel.row_widget(r) is not None
                         for r in range(panel.playlist_view.count())), 4000)
    wait_for(lambda: all(
        (panel.row_widget(r).thumbnail_label.property("thumbnailState") == "ready")
        for r in range(panel.playlist_view.count())), 25000)
    rows = {}
    ratio_ok = True
    for row in range(panel.playlist_view.count()):
        widget = panel.row_widget(row)
        if widget is None:
            continue
        pixmap = widget.thumbnail_label.pixmap()
        size = (pixmap.width(), pixmap.height()) if pixmap else None
        rows[row] = {
            "file": os.path.basename(widget.toolTip()),
            "state": widget.thumbnail_label.property("thumbnailState"),
            "pixmap": size,
        }
        if size and size != (82, 50):
            ratio_ok = False
    path = shot("thumbnails")
    record("thumbnail_rows", "gercek playlist gorunumu (goz+durum)",
           "her satirda thumbnail veya guvenli placeholder",
           str(rows), all(r["state"] in ("ready", "loading", "empty")
                          for r in rows.values()) and ratio_ok, path)
    # Satir/dosya eslesmesi NESNEL olculur: her satirin pixmap'i, o
    # satirin PATH_ROLE yolundan turetilen cache JPEG'ine AYNI
    # scale/crop uygulanarak karsilastirilir. Ekran goruntusu yalnizca
    # ek gorsel kanittir; RESULT uretmez.
    from PyQt6.QtCore import Qt as _Qt
    from PyQt6.QtGui import QPixmap as _QPixmap
    from app.playlist_panel import PATH_ROLE as _PATH_ROLE
    from app.thumbnail_service import thumbnail_cache_path as _cache_path

    def expected_image(media_path, target_size):
        cache = _cache_path(media_path, panel.thumbnail_service.cache_dir)
        if not (os.path.isfile(cache) and os.path.getsize(cache) > 0):
            return None, cache
        source_pixmap = _QPixmap(cache)
        if source_pixmap.isNull():
            return None, cache
        scaled = source_pixmap.scaled(
            target_size, _Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            _Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - target_size.width()) // 2)
        y = max(0, (scaled.height() - target_size.height()) // 2)
        return scaled.copy(x, y, target_size.width(),
                           target_size.height()).toImage(), cache

    mapping = {}
    mapping_ok = True
    for row in range(panel.playlist_view.count()):
        item = panel.playlist_view.item(row)
        widget = panel.row_widget(row)
        if item is None or widget is None:
            continue
        media_path = str(item.data(_PATH_ROLE) or "")
        pixmap = widget.thumbnail_label.pixmap()
        expected, cache = expected_image(media_path,
                                         widget.thumbnail_label.size())
        actual = pixmap.toImage() if pixmap is not None else None
        matches = (expected is not None and actual is not None
                   and expected == actual)
        # Yanlis satira baglanmadigini dogrula: baska satirin karesiyle
        # eslesmemeli.
        cross = []
        for other in range(panel.playlist_view.count()):
            if other == row:
                continue
            other_item = panel.playlist_view.item(other)
            if other_item is None:
                continue
            other_expected, _ = expected_image(
                str(other_item.data(_PATH_ROLE) or ""),
                widget.thumbnail_label.size())
            if other_expected is not None and actual is not None \
                    and other_expected == actual:
                cross.append(other)
        mapping[row] = {
            "file": os.path.basename(media_path),
            "cache_exists": os.path.isfile(cache),
            "cache_size": os.path.getsize(cache) if os.path.isfile(cache) else 0,
            "pixel_match": matches,
            "cross_match_rows": cross,
        }
        if not matches or cross:
            mapping_ok = False
    record("thumbnail_row_mapping",
           "satir pixmap'i ile o dosyanin cache JPEG'i PIKSEL karsilastirmasi",
           "her satir KENDI dosyasinin karesini gosterir", str(mapping),
           mapping_ok and bool(mapping), path)


# ================= GRUP 9 - fullscreen + iki asamali Esc =================

def group_fullscreen_esc():
    frame = PLAYER.video_frame
    PLAYER.showNormal()
    pump(400)
    fs = overlay_button("overlayFullscreen")
    ready = click_ready(fs, "fullscreen_button")
    if ready is None:
        return
    probe = ClickProbe(fs, product_method="toggle_fullscreen")
    before_state = int(PLAYER.windowState().value)
    delivered = physical_click(ready[0], ready[1], settle=500, target=fs,
                               label="fullscreen_button")
    entered = wait_for(lambda: frame.is_video_fullscreen, 5000)
    pump(600)
    print(f"DIAG|fullscreen_button|{probe.summary(ready[0], ready[1])}|"
          f"is_video_fullscreen={frame.is_video_fullscreen} "
          f"windowState={before_state}->{int(PLAYER.windowState().value)} "
          f"frameGeometry={PLAYER.frameGeometry().getRect()} "
          f"delivered={delivered}", flush=True)
    probe.release_probe()
    screen = QApplication.primaryScreen().geometry()
    covers = PLAYER.frameGeometry().width() >= screen.width() - 6
    path = shot("fullscreen")
    record("fullscreen_button", "SendInput click",
           "native geometri ekrani kaplar",
           f"entered={entered} geo={PLAYER.frameGeometry().getRect()} "
           f"screen={screen.getRect()}", entered and covers, path)

    tap(VK_ESCAPE)
    exited = wait_for(lambda: not frame.is_video_fullscreen, 5000)
    record("esc_exits_fullscreen", "gercek Esc", "pencere moduna doner",
           f"fullscreen={frame.is_video_fullscreen}", exited)

    PLAYER.resize(1180, 700)
    pump(500)
    tap(VK_ESCAPE)
    pump(1000)
    geo = PLAYER.geometry()
    available = QApplication.primaryScreen().availableGeometry()
    centred = (abs(geo.center().x() - available.center().x()) <= 40
               and abs(geo.center().y() - available.center().y()) <= 40)
    path = shot("esc-default")
    record("esc_default_size", "gercek Esc",
           "960x600 ve ekranda ortali",
           f"size={geo.width()}x{geo.height()} centre=({geo.center().x()},"
           f"{geo.center().y()}) screen_centre=({available.center().x()},"
           f"{available.center().y()}) playlist_open="
           f"{frame.playlist_panel.is_open} overlay="
           f"{frame.control_overlay.isVisible()}",
           (geo.width(), geo.height()) == (960, 600) and centred, path)


# ================= GRUP 10 - altyazi =================

def track_counts(mpv):
    tracks = list(mpv.track_list or [])
    return {kind: len([t for t in tracks
                       if isinstance(t, dict) and t.get("type") == kind])
            for kind in ("video", "audio", "sub")}


def stable_track_counts(mpv, timeout_ms=8000, samples=3, step_ms=300):
    """`track_list` stabil hale gelene kadar BOUNDED bekler.

    Ardarda `samples` olcumde ayni sayilar gorulurse o sonucu dondurur;
    sure dolarsa son olcumu `stable=False` ile dondurur.
    """
    end = time.time() + timeout_ms / 1000.0
    history = []
    counts = track_counts(mpv)
    while time.time() < end:
        counts = track_counts(mpv)
        history.append(tuple(sorted(counts.items())))
        if len(history) >= samples and len(set(history[-samples:])) == 1:
            counts["stable"] = True
            return counts
        pump(step_ms)
    counts["stable"] = False
    return counts


def group_subtitles(no_sub_video):
    frame, mpv = PLAYER.video_frame, PLAYER.mpv_player
    wait_for(lambda: (mpv.duration or 0) > 0, 10000)
    tracks = [t for t in (mpv.track_list or [])
              if isinstance(t, dict) and t.get("type") == "sub"]
    record("tracks_loaded_off", "gercek video acilisi",
           "sub track var, baslangicta kapali",
           f"tracks={len(tracks)} visibility={mpv.sub_visibility} "
           f"cc_active={frame.overlay_subtitles_active}",
           bool(tracks) and not mpv.sub_visibility
           and frame.overlay_subtitles_active is False)

    cc = overlay_button("overlaySubtitles")
    ready = click_ready(cc, "cc_on")
    if ready:
        physical_click(ready[0], ready[1], settle=300)
        on = wait_for(lambda: bool(mpv.sub_visibility), 5000)
        wait_for(lambda: frame.overlay_subtitles_active is True, 3000)
        path = shot("cc-on")
        record("cc_on", "SendInput click", "altyazi acilir, ikon turuncu",
               f"visibility={mpv.sub_visibility} "
               f"icon={frame.overlay_subtitles_active}",
               on and frame.overlay_subtitles_active is True, path)
        ready = click_ready(cc, "cc_off")
        if ready:
            physical_click(ready[0], ready[1], settle=300)
            off = wait_for(lambda: not mpv.sub_visibility, 5000)
            wait_for(lambda: frame.overlay_subtitles_active is False, 3000)
            record("cc_off", "SendInput click", "altyazi kapanir, ikon beyaz",
                   f"visibility={mpv.sub_visibility} "
                   f"icon={frame.overlay_subtitles_active}",
                   off and frame.overlay_subtitles_active is False)

    # Eski medyanin altyazi durumu, yeni medyaya sizinti olculebilsin diye
    # gecisten ONCE kaydedilir.
    prev_sid = getattr(mpv, "sid", None)
    prev_visibility = mpv.sub_visibility
    prev_path = str(getattr(mpv, "path", "") or "")

    if not str(no_sub_video or "").strip():
        record("no_subtitle_osd", "-", "Altyazi bulunamadi OSD",
               "MLC_NO_SUB_VIDEO verilmedi", None,
               "BLOCKED: NO_REAL_SUBTITLE_FREE_VIDEO")
        return
    if not os.path.isfile(no_sub_video):
        record("no_subtitle_osd", "-", "Altyazi bulunamadi OSD",
               "MLC_NO_SUB_VIDEO gercek bir dosya degil", None,
               "BLOCKED: NO_REAL_SUBTITLE_FREE_VIDEO")
        return

    PLAYER.open_path(no_sub_video)
    target = os.path.normcase(os.path.abspath(no_sub_video))
    loaded = wait_for(
        lambda: (os.path.normcase(os.path.abspath(str(getattr(mpv, "path", "")
                                                      or ""))) == target
                 and (mpv.duration or 0) > 0), 25000)
    counts = stable_track_counts(mpv)
    player_front()
    # SOZLESME: dosyanin var olmasi YETMEZ. Gercek video track > 0 ve
    # gomulu altyazi track == 0 olmadan bu kabul PASS uretemez.
    if not loaded or counts["video"] <= 0 or counts["sub"] != 0:
        record("no_subtitle_osd", "libmpv track_list",
               "gercek video track>0, sub track=0",
               f"loaded={loaded} video={counts['video']} audio={counts['audio']} "
               f"sub={counts['sub']} stable={counts['stable']} "
               f"duration={mpv.duration} file={os.path.basename(no_sub_video)}",
               None, "BLOCKED: NO_REAL_SUBTITLE_FREE_VIDEO")
        return
    record("no_subtitle_media_contract", "libmpv track_list",
           "yeni medya yuklendi, video>0, sub=0, duration>0",
           f"file={os.path.basename(no_sub_video)} video={counts['video']} "
           f"audio={counts['audio']} sub={counts['sub']} "
           f"stable={counts['stable']} duration={round(mpv.duration or 0, 1)} "
           f"path_changed={prev_path != str(getattr(mpv, 'path', '') or '')}",
           bool(counts["stable"]))

    # Eski medyanin altyazi state'i yeni medyaya TASINMAMALI.
    new_sid = getattr(mpv, "sid", None)
    new_visibility = mpv.sub_visibility
    sid_clean = new_sid in (None, False, "no") or str(new_sid).lower() in (
        "", "0", "no", "none", "false")
    record("subtitle_state_leak", "medya gecisi olcumu",
           "yeni medyada sid pasif, sub_visibility False, CC beyaz, sub track 0",
           f"prev_sid={prev_sid} prev_visibility={prev_visibility} "
           f"new_sid={new_sid} new_visibility={new_visibility} "
           f"new_sub_tracks={counts['sub']} "
           f"overlay_subtitles_active={frame.overlay_subtitles_active}",
           sid_clean and not new_visibility and counts["sub"] == 0
           and frame.overlay_subtitles_active is False)

    cc = overlay_button("overlaySubtitles")
    ready = click_ready(cc, "cc_no_subtitle")
    if ready is None:
        record("no_subtitle_osd", "onkosul", "CC dugmesi tiklanabilir",
               "click_ready onkosulu saglanmadi", None, "BLOCKED: CLICK_TARGET")
        return
    # Ek onkosul: imlecin altindaki NATIVE pencere gercekten overlay HWND'si mi?
    point = wintypes.POINT(int(ready[0]), int(ready[1]))
    hwnd_at = int(user32.WindowFromPoint(point) or 0)
    overlay_hwnd = int(frame.control_overlay.winId())
    if hwnd_at != overlay_hwnd:
        record("no_subtitle_osd", "WindowFromPoint", "overlay HWND",
               f"hwnd_at={hwnd_at} overlay_hwnd={overlay_hwnd}", None,
               "BLOCKED: CLICK_TARGET")
        return

    paused_before = bool(mpv.pause)
    time_before = float(mpv.time_pos or 0.0)
    if not physical_click(ready[0], ready[1], settle=200, target=cc,
                          label="cc_no_subtitle"):
        record("no_subtitle_osd", "SendInput click", "tiklama hedefe gitti",
               "hedef tiklama aninda dogrulanamadi", None,
               "BLOCKED: CLICK_TARGET")
        return

    shown = wait_for(lambda: frame.osd_label.isVisible(), 4000)
    text = frame.osd_label.text()
    osd_rect = global_rect(frame.osd_label)
    video_rect = global_rect(frame)
    overlay_rect = global_rect(frame.control_overlay)
    path = shot("no-subtitle-osd")
    modal = QApplication.activeModalWidget()
    after_counts = track_counts(mpv)
    cc_active = frame.overlay_subtitles_active
    visibility_after = mpv.sub_visibility
    faded = wait_for(lambda: not frame.osd_label.isVisible(), 6000)
    pump(400)
    paused_after = bool(mpv.pause)
    time_after = float(mpv.time_pos or 0.0)
    playback_ok = (paused_after == paused_before
                   and (paused_before or time_after >= time_before))
    record("no_subtitle_osd", "SendInput click",
           "'Altyazi bulunamadi' OSD gorunur, CC pasif kalir, yeni sub track "
           "olusmaz, mesaj kaybolur, oynatma durumu korunur, modal yok",
           f"shown={shown} text={text!r} faded={faded} cc_active={cc_active} "
           f"sub_visibility={visibility_after} sub_tracks={after_counts['sub']} "
           f"modal={type(modal).__name__ if modal else None} "
           f"pause {paused_before}->{paused_after} "
           f"time {round(time_before, 2)}->{round(time_after, 2)}",
           shown and "bulunamad" in text.lower() and faded
           and cc_active is False and not visibility_after
           and after_counts["sub"] == 0 and modal is None and playback_ok,
           path)

    # Konum olcumu ayri satirda: gorsel dogrulama goz kontrolune degil
    # olculen dikdortgenlere baglidir.
    osd_layout_check("no_subtitle_osd_layout", osd_rect, video_rect,
                     overlay_rect, path)

    # Ayni geometri kurali playlist acik, tam ekran ve resize sonrasi da
    # gecerli olmali. Her durumda OSD YINE GERCEK CC tiklamasiyla acilir.
    osd_layout_state("osd_layout_playlist_open", enter_playlist_state)
    osd_layout_state("osd_layout_fullscreen", enter_fullscreen_state)
    osd_layout_state("osd_layout_after_resize", enter_resized_state)


OSD_GAP_MIN, OSD_GAP_MAX = 12, 16


def osd_layout_check(name, osd_rect, video_rect, overlay_rect, path,
                     extra=""):
    centred = abs(osd_rect.center().x() - video_rect.center().x()) <= 40
    inside = video_rect.contains(osd_rect)
    overlap = osd_rect.intersects(overlay_rect)
    gap = overlay_rect.top() - osd_rect.bottom()
    gap_ok = OSD_GAP_MIN <= gap <= OSD_GAP_MAX
    record(name, "global dikdortgen olcumu",
           f"OSD video alaninda, yatay merkezde, kontrol overlay'i ile "
           f"cakismaz, ustunden {OSD_GAP_MIN}-{OSD_GAP_MAX}px yukarida",
           f"osd={osd_rect.getRect()} video={video_rect.getRect()} "
           f"overlay={overlay_rect.getRect()} centred={centred} "
           f"inside={inside} overlay_overlap={overlap} gap={gap}{extra}",
           centred and inside and not overlap and gap_ok, path)


def enter_playlist_state():
    frame = PLAYER.video_frame
    if not frame.playlist_panel.is_open:
        if not toggle_playlist_physical("osd_layout_playlist_toggle"):
            return False
        if not wait_for(lambda: frame.playlist_panel.is_open, 5000):
            return False
    pump(600)
    return True


def enter_fullscreen_state():
    frame = PLAYER.video_frame
    fs = overlay_button("overlayFullscreen")
    ready = click_ready(fs, "osd_layout_fullscreen_toggle")
    if ready is None:
        return False
    if not physical_click(ready[0], ready[1], settle=600, target=fs,
                          label="osd_layout_fullscreen_toggle"):
        return False
    if not wait_for(lambda: frame.is_video_fullscreen, 6000):
        return False
    pump(800)
    return True


def enter_resized_state():
    frame = PLAYER.video_frame
    if frame.is_video_fullscreen:
        tap(VK_ESCAPE)
        if not wait_for(lambda: not frame.is_video_fullscreen, 6000):
            return False
        pump(600)
    if frame.playlist_panel.is_open:
        if not toggle_playlist_physical("osd_layout_resize_playlist_toggle"):
            return False
        wait_for(lambda: not frame.playlist_panel.is_open, 5000)
    before = frame.width()
    PLAYER.resize(1120, 700)
    if not wait_for(lambda: frame.width() != before, 5000):
        return False
    pump(800)
    return player_front()


def osd_layout_state(name, enter):
    """Verilen durumda GERCEK CC tiklamasiyla OSD acar ve geometriyi olcer."""
    frame = PLAYER.video_frame
    if not enter():
        record(name, "durum hazirligi", "durum kuruldu",
               "durum fiziksel olarak kurulamadi", None, "BLOCKED: CLICK_TARGET")
        return
    cc = overlay_button("overlaySubtitles")
    ready = click_ready(cc, name + "_precondition")
    if ready is None:
        record(name, "onkosul", "CC dugmesi tiklanabilir",
               "click_ready onkosulu saglanmadi", None, "BLOCKED: CLICK_TARGET")
        return
    if not physical_click(ready[0], ready[1], settle=250, target=cc,
                          label=name):
        record(name, "SendInput click", "tiklama hedefe gitti",
               "hedef tiklama aninda dogrulanamadi", None,
               "BLOCKED: CLICK_TARGET")
        return
    if not wait_for(lambda: frame.osd_label.isVisible(), 4000):
        record(name, "SendInput click", "OSD gorunur",
               "OSD gorunmedi", False)
        return
    osd_rect = global_rect(frame.osd_label)
    video_rect = global_rect(frame)
    overlay_rect = global_rect(frame.control_overlay)
    path = shot(name)
    osd_layout_check(name, osd_rect, video_rect, overlay_rect, path,
                     extra=f" fullscreen={frame.is_video_fullscreen} "
                           f"playlist_open={frame.playlist_panel.is_open}")
    wait_for(lambda: not frame.osd_label.isVisible(), 6000)


# ================= GRUP 13 - ses / altyazi parcasi gecisi =================

def _track_inventory(mpv):
    tracks = [track for track in (mpv.track_list or [])
              if isinstance(track, dict)]
    audio = track_snapshot(tracks, "audio", getattr(mpv, "aid", None))
    subtitles = track_snapshot(
        tracks, "sub", getattr(mpv, "sid", None),
        getattr(mpv, "sub_visibility", False))
    signature = tuple(
        (track.get("type"), normalise_track_id(track.get("id")),
         bool(track.get("selected")), str(track.get("lang") or ""),
         str(track.get("title") or ""),
         os.path.basename(str(track.get("external-filename") or "")))
        for track in tracks if track.get("type") in ("video", "audio", "sub"))
    return {
        "tracks": tracks,
        "audio": audio,
        "subtitles": subtitles,
        "video_count": len([track for track in tracks
                            if track.get("type") == "video"]),
        "signature": (signature, audio["signature"], subtitles["signature"]),
    }


def _stable_track_inventory(mpv, timeout_ms=10000, samples=3):
    end = time.time() + timeout_ms / 1000.0
    history = []
    latest = _track_inventory(mpv)
    while time.time() < end:
        latest = _track_inventory(mpv)
        history.append(latest["signature"])
        if len(history) >= samples and len(set(history[-samples:])) == 1:
            latest["stable"] = True
            return latest
        pump(250)
    latest["stable"] = False
    return latest


def _wait_track_selection(mpv, kind, target, expected_ids,
                          require_visible=False, timeout_ms=8000):
    stabilizer = StableSelection(target, require_visible=require_visible,
                                 required=3, expected_ids=expected_ids)
    latest = {"snapshot": track_snapshot(
        [], kind, None, False if kind == "sub" else None)}

    def matches():
        tracks = list(mpv.track_list or [])
        snapshot = track_snapshot(
            tracks, kind,
            getattr(mpv, "aid" if kind == "audio" else "sid", None),
            getattr(mpv, "sub_visibility", False) if kind == "sub" else None)
        latest["snapshot"] = snapshot
        return stabilizer.observe(snapshot)

    return wait_for(matches, timeout_ms, step_ms=180), latest["snapshot"]


def _checked_after_reopen(root_text, track_text, target_id):
    result = physical_menu_action(root_text, track_text, target_id,
                                  inspect_only=True)
    action = result.get("action")
    try:
        checked = bool(action is not None and action.isChecked())
    except RuntimeError:
        checked = False
    return result, checked


def group_tracks():
    frame, mpv = PLAYER.video_frame, PLAYER.mpv_player
    wait_for(lambda: (mpv.duration or 0) > 0, 10000)
    inventory = _stable_track_inventory(mpv)
    audio_tracks = [track for track in inventory["tracks"]
                    if track.get("type") == "audio"]
    subtitle_tracks = [track for track in inventory["tracks"]
                       if track.get("type") == "sub"]
    problems = fixture_problems(
        inventory["audio"], inventory["subtitles"],
        inventory["video_count"], mpv.duration)
    if len(audio_tracks) < 2 or len(subtitle_tracks) < 2:
        problems.append("MULTI_TRACK_MEDIA_REQUIRED")
    if not inventory.get("stable"):
        problems.append("TRACK_INVENTORY_UNSTABLE")
    ao_problems = audio_safety_problems(getattr(mpv, "current_ao", None))
    problems.extend(ao_problems)
    if problems:
        block_code = fixture_block_code(problems)
        record("track_fixture_contract", "libmpv stable track inventory",
               "video>0, duration>0, 2 unique audio, 2 unique sub, exact "
               "selected/current, ao=null",
               f"video={inventory['video_count']} audio={len(audio_tracks)} "
               f"sub={len(subtitle_tracks)} stable={inventory.get('stable')} "
               f"audio_ids={inventory['audio']['ids']} "
               f"sub_ids={inventory['subtitles']['ids']} problems={problems}",
               None, f"BLOCKED: {block_code}")
        return
    record("track_fixture_contract", "libmpv stable track inventory",
           "video>0, duration>0, 2 unique audio, 2 unique sub, exact "
           "selected/current, ao=null",
           f"video={inventory['video_count']} audio={len(audio_tracks)} "
           f"sub={len(subtitle_tracks)} stable=True "
           f"audio_ids={inventory['audio']['ids']} "
           f"sub_ids={inventory['subtitles']['ids']} ao={mpv.current_ao}", True)

    audio_a = inventory["audio"]["current"]
    audio_b = alternate_track_id(inventory["audio"])
    audio_click = physical_menu_action(
        tr("Ses"), tr("Ses Parçası"), audio_b)
    if not (audio_click["delivered"] and audio_click.get("menu_closed")):
        record("audio_track_switch", "gercek sag-tik menu SendInput",
               "A->B hedef tiklamasi", f"a={audio_a} b={audio_b} "
               f"reason={audio_click.get('reason')} "
               f"closed={audio_click.get('menu_closed')}",
               menu_failure_result(audio_click.get("reason")),
               "TRACK_MENU_TARGET")
        return
    audio_ok, audio_after = _wait_track_selection(
        mpv, "audio", audio_b, inventory["audio"]["ids"])
    audio_check, audio_checked = _checked_after_reopen(
        tr("Ses"), tr("Ses Parçası"), audio_b)
    record("audio_track_switch", "gercek sag-tik menu SendInput + libmpv",
           "A!=B, aid=B, exact selected B, yeniden acilan menude B checked",
           f"a={audio_a} b={audio_b} current={audio_after['current']} "
           f"selected={audio_after['selected']} checked={audio_checked} "
           f"reopen={audio_check.get('reason')}",
           audio_a != audio_b and audio_ok and audio_checked
           and audio_check["delivered"] and audio_check.get("menu_closed"))

    subtitle_s1 = inventory["subtitles"]["current"]
    subtitle_s2 = alternate_track_id(inventory["subtitles"])
    s2_click = physical_menu_action(
        tr("Altyazı"), tr("Altyazı Parçası"), subtitle_s2)
    if not (s2_click["delivered"] and s2_click.get("menu_closed")):
        record("subtitle_track_switch_1", "gercek sag-tik menu SendInput",
               "S1->S2 hedef tiklamasi",
               f"s1={subtitle_s1} s2={subtitle_s2} "
               f"reason={s2_click.get('reason')} "
               f"closed={s2_click.get('menu_closed')}",
               menu_failure_result(s2_click.get("reason")),
               "TRACK_MENU_TARGET")
        return
    if not bool(mpv.sub_visibility):
        cc = overlay_button("overlaySubtitles")
        ready = click_ready(cc, "tracks_subtitle_visibility")
        if ready is None or not physical_click(
                ready[0], ready[1], settle=250, target=cc,
                label="tracks_subtitle_visibility"):
            record("subtitle_track_switch_1", "gercek CC SendInput",
                   "altyazi gorunur", "CC hedeflenemedi", None,
                   "BLOCKED: CLICK_TARGET")
            return
    s2_ok, s2_after = _wait_track_selection(
        mpv, "sub", subtitle_s2, inventory["subtitles"]["ids"],
        require_visible=True)
    s2_check, s2_checked = _checked_after_reopen(
        tr("Altyazı"), tr("Altyazı Parçası"), subtitle_s2)
    record("subtitle_track_switch_1",
           "gercek sag-tik menu/CC SendInput + libmpv",
           "S1!=S2, sid=S2, exact selected S2, gorunur, ikon aktif, menu checked",
           f"s1={subtitle_s1} s2={subtitle_s2} "
           f"current={s2_after['current']} selected={s2_after['selected']} "
           f"visible={mpv.sub_visibility} icon={frame.overlay_subtitles_active} "
           f"checked={s2_checked}",
           subtitle_s1 != subtitle_s2 and s2_ok and s2_checked
           and frame.overlay_subtitles_active is True and s2_check["delivered"]
           and s2_check.get("menu_closed"))

    s1_click = physical_menu_action(
        tr("Altyazı"), tr("Altyazı Parçası"), subtitle_s1)
    if not (s1_click["delivered"] and s1_click.get("menu_closed")):
        record("subtitle_track_switch_2", "gercek sag-tik menu SendInput",
               "S2->S1 hedef tiklamasi",
               f"s1={subtitle_s1} s2={subtitle_s2} "
               f"reason={s1_click.get('reason')} "
               f"closed={s1_click.get('menu_closed')}",
               menu_failure_result(s1_click.get("reason")),
               "TRACK_MENU_TARGET")
        return
    s1_ok, s1_after = _wait_track_selection(
        mpv, "sub", subtitle_s1, inventory["subtitles"]["ids"],
        require_visible=True)
    s1_check, s1_checked = _checked_after_reopen(
        tr("Altyazı"), tr("Altyazı Parçası"), subtitle_s1)
    record("subtitle_track_switch_2",
           "gercek sag-tik menu SendInput + libmpv",
           "S2!=S1, sid=S1, exact selected S1, gorunur, ikon aktif, menu checked",
           f"s1={subtitle_s1} s2={subtitle_s2} "
           f"current={s1_after['current']} selected={s1_after['selected']} "
           f"visible={mpv.sub_visibility} icon={frame.overlay_subtitles_active} "
           f"checked={s1_checked}",
           subtitle_s2 != subtitle_s1 and s1_ok and s1_checked
           and frame.overlay_subtitles_active is True and s1_check["delivered"]
           and s1_check.get("menu_closed"))


# ================= GRUP 11 - z-order / goruntu bozulmasi =================

def group_zorder(focus_child_geometry):
    frame = PLAYER.video_frame
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "native_focus_child.py")
    env = dict(os.environ)
    env["MLC_FOCUS_CHILD_MS"] = "45000"
    env["MLC_FOCUS_CHILD_GEOMETRY"] = focus_child_geometry
    child = subprocess.Popen([sys.executable, script], env=env)
    print(f"FOCUS_CHILD_PID={child.pid}", flush=True)
    try:
        pump(2000)
        for phase in ("closed", "open"):
            if phase == "open" and not frame.playlist_panel.is_open:
                player_front()
                toggle_playlist_physical()
                wait_for(lambda: frame.playlist_panel.is_open, 4000)
            if phase == "closed" and frame.playlist_panel.is_open:
                player_front()
                toggle_playlist_physical()
                wait_for(lambda: not frame.playlist_panel.is_open, 4000)
            player_front()
            wake_overlay()
            pump(500)
            take_foreground(int(child._handle) if False else
                            find_child_hwnd(child.pid) or 0)
            pump(900)
            _, pid = foreground_info()
            overlay_vis = frame.control_overlay.isVisible()
            osd_vis = frame.osd_label.isVisible()
            panel_top = topmost_pid_at(global_rect(frame.playlist_panel).center()) \
                if frame.playlist_panel.is_open else None
            path = shot(f"zorder-{phase}-other-front")
            record(f"zorder_other_front[{phase}]",
                   "gercek foreground devri + ekran goruntusu",
                   "overlay/OSD ustte kalmaz, playlist floating degil",
                   f"fg_pid={pid} own={os.getpid()} overlay={overlay_vis} "
                   f"osd={osd_vis} playlist_topmost_pid={panel_top}",
                   pid != os.getpid() and not overlay_vis and not osd_vis,
                   path)
            player_front()
            wake_overlay()
            pump(600)
            path = shot(f"zorder-{phase}-player-front")
            record(f"zorder_player_front[{phase}]",
                   "gercek foreground geri alma",
                   "overlay doner, playlist durumu korunur",
                   f"overlay={frame.control_overlay.isVisible()} "
                   f"playlist_open={frame.playlist_panel.is_open}",
                   frame.control_overlay.isVisible(), path)
        # --- GERCEK fiziksel resize + NESNEL yerlesim degerlendirmesi ---
        # Eskiden `PLAYER.resize()` cagriliyordu (programatik; fiziksel
        # kabul sayilmaz) ve karar goz kontrolune birakiliyordu.
        if not frame.playlist_panel.is_open:
            toggle_playlist_physical()
            wait_for(lambda: frame.playlist_panel.is_open, 4000)
        player_front()
        wake_overlay()
        PLAYER.showNormal()
        PLAYER.setGeometry(300, 200, 1200, 720)
        pump(500)
        before_rect = PLAYER.frameGeometry().getRect()
        corner = PLAYER.frameGeometry()
        px, py = corner.right() - 3, corner.bottom() - 3
        expected_hwnd = int(user32.WindowFromPoint(
            wintypes.POINT(int(px), int(py))) or 0)
        drag_report = threaded_drag(px, py, px + 70, py + 70,
                                    expected_hwnd=expected_hwnd)
        input_problems = input_contract_problems(drag_report)
        after_rect = PLAYER.frameGeometry().getRect()
        pump(700)
        wake_overlay()
        path = shot("zorder-after-resize")

        if input_problems:
            record("zorder_after_resize", "SendInput (worker thread)",
                   "input sozlesmesi saglanir",
                   f"report={drag_report} problems={input_problems}", None,
                   "BLOCKED: INPUT_CONTRACT", path)
        else:
            geometry_problems = resize_problems(
                before_rect, after_rect,
                {"right": 70, "bottom": 70, "left": 0, "top": 0})

            def rect_of(widget):
                r = global_rect(widget)
                return (r.x(), r.y(), r.width(), r.height())

            client_origin = PLAYER.mapToGlobal(QPoint(0, 0))
            client = (client_origin.x(), client_origin.y(),
                      PLAYER.width(), PLAYER.height())
            panel = frame.playlist_panel
            host = getattr(PLAYER, "playlist_dock_host", None)
            overlay = frame.control_overlay
            controls = {}
            for name in ("overlayTimeline", "overlayPlayPause",
                         "overlaySubtitles", "overlayVolume",
                         "overlayFullscreen"):
                widget = overlay_button(name)
                if widget is not None:
                    controls[name] = rect_of(widget)

            def hit_kind(x, y):
                hwnd = int(user32.WindowFromPoint(
                    wintypes.POINT(int(x), int(y))) or 0)
                table = {
                    int(overlay.winId()) if overlay else 0: "overlay",
                    int(frame.winId()): "video_frame",
                    int(PLAYER.winId()): "main_window",
                }
                return table.get(hwnd, "other")

            control_hits = {}
            for name in ("overlayPlayPause", "overlaySubtitles",
                         "overlayVolume", "overlayFullscreen"):
                widget = overlay_button(name)
                if widget is None:
                    continue
                centre = global_rect(widget).center()
                control_hits[name] = hit_kind(centre.x(), centre.y())
            panel_centre = global_rect(panel).center()
            panel_hit = hit_kind(panel_centre.x(), panel_centre.y())
            if panel_hit == "other":
                # Gomulu panel kendi surecimizdeki host/panel HWND'sine
                # dusebilir; belirleyici olan SUREC sahipligidir.
                panel_hwnd = int(user32.WindowFromPoint(wintypes.POINT(
                    int(panel_centre.x()), int(panel_centre.y()))) or 0)
                owner_pid = wintypes.DWORD(0)
                user32.GetWindowThreadProcessId(wintypes.HWND(panel_hwnd),
                                                ctypes.byref(owner_pid))
                panel_hit = ("own_process" if int(owner_pid.value) == os.getpid()
                             else "other_process")
            widget_at_ok = {}
            for name in ("overlayPlayPause", "overlayFullscreen"):
                widget = overlay_button(name)
                if widget is None:
                    continue
                centre = global_rect(widget).center()
                found = QApplication.widgetAt(centre)
                owner = found
                while owner is not None and owner is not widget:
                    owner = owner.parent()
                widget_at_ok[name] = owner is widget
            fg_pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(
                wintypes.HWND(foreground_hwnd()),
                ctypes.byref(fg_pid))

            snapshot = {
                "client": client,
                "title_bar": rect_of(PLAYER.title_bar),
                "media_container": rect_of(PLAYER.media_container),
                "video_frame": rect_of(frame),
                "playlist_host": rect_of(host) if host is not None
                else rect_of(panel),
                "playlist_panel": rect_of(panel),
                "control_overlay": rect_of(overlay),
                "panel_is_top_level": panel.isWindow(),
                "panel_inside_host_chain": (host is not None
                                            and panel.parent() is host),
                "overlay_visible": overlay.isVisible(),
                "overlay_opacity": overlay.windowOpacity(),
                "controls": controls,
                "control_hits": control_hits,
                "panel_hit": panel_hit,
                "foreground_is_player": int(fg_pid.value) == os.getpid(),
            }
            layout_problems = zorder_after_resize_problems(snapshot)
            if not all(widget_at_ok.values()):
                layout_problems.append(f"widget_at={widget_at_ok}")
            print(f"ZORDER_SNAPSHOT {snapshot}", flush=True)
            record("zorder_after_resize",
                   "gercek fiziksel resize (worker thread) + nesnel yerlesim",
                   "sag/alt ~+70, sol/ust sabit; video-playlist bitisik ve "
                   "kesismiyor; overlay video icinde ve alta hizali; kontrol "
                   "merkezleri overlay HWND'sinde",
                   f"before={before_rect} after={after_rect} "
                   f"cursor_delta={drag_report.get('cursor_delta')} "
                   f"split_gap={snapshot['playlist_host'][0] - (snapshot['video_frame'][0] + snapshot['video_frame'][2])} "
                   f"panel_top_level={snapshot['panel_is_top_level']} "
                   f"panel_hit={panel_hit} control_hits={control_hits} "
                   f"widget_at={widget_at_ok} "
                   f"overlay={snapshot['control_overlay']} "
                   f"video={snapshot['video_frame']} "
                   f"geometry_problems={geometry_problems} "
                   f"layout_problems={layout_problems}",
                   not geometry_problems and not layout_problems, path)


    finally:
        if child.poll() is None:
            try:
                child.terminate()
                child.wait(timeout=5)
            except Exception:
                try:
                    child.kill()
                except Exception:
                    pass
        print(f"FOCUS_CHILD_CLEANED pid={child.pid}", flush=True)


def find_child_hwnd(pid):
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetParent(hwnd):
            return True
        owner = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if int(owner.value) == pid:
            found.append(hwnd)
        return True

    user32.EnumWindows(proc(cb), 0)
    return found[0] if found else None


def topmost_pid_at(point):
    # NOT: `wintypes.POINT` kullanilir. Yerel bir POINT sinifi tanimlamak
    # `user32.WindowFromPoint.argtypes` degerini bozuyor ve ayni surecteki
    # diger olcumler "expected POINT instead of POINT" hatasi aliyordu.
    hwnd = user32.WindowFromPoint(
        wintypes.POINT(int(point.x()), int(point.y())))
    pid = ctypes.c_ulong(0)
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


# ================= Ana akis =================

def main():
    global APP, PLAYER, GROUP

    parser = argparse.ArgumentParser()
    parser.add_argument("--group", required=True)
    parser.add_argument("--video", default=os.environ.get("MLC_NATIVE_TEST_VIDEO", ""))
    parser.add_argument("--playlist", default=os.environ.get("MLC_PLAYLIST_VIDEOS", ""))
    parser.add_argument("--no-sub-video", default=os.environ.get("MLC_NO_SUB_VIDEO", ""))
    args = parser.parse_args()
    GROUP = args.group

    # IZOLASYON: her grup KENDI benzersiz ayar ve cache dizinini kullanir.
    # Gercek HKCU ayarlari ve gercek thumbnail cache'i KIRLETILMEZ.
    QStandardPaths.setTestModeEnabled(True)
    settings_root = os.environ.get(
        "MLC_NATIVE_SETTINGS",
        os.path.join(os.environ.get("TEMP", "."), "mlc_phys_settings"))
    settings = os.path.join(settings_root, f"{GROUP}-{os.getpid()}")
    os.makedirs(settings, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat,
                      QSettings.Scope.UserScope, settings)
    print(f"CHILD_ISOLATION settings={settings} qt_test_mode=True", flush=True)
    install_mpv_call_recorder()

    original_cursor = cursor_pos()
    original_foreground = foreground_hwnd()
    print(f"CHILD_SAVED cursor={original_cursor} fg={original_foreground}", flush=True)

    APP = QApplication(sys.argv)
    # GUVENLIK: fiziksel gruplar ses seviyesini veya ses parcasi secimini
    # degistirebilir. Gercek hoparlorden ses cikmasin diye bu test child
    # surecinde `ao=null` kullanilir. Urunun MPV_CONFIG sozlugu mutate
    # EDILMEZ; yalnizca bu surecteki modul referansi degistirilir.
    import app.player as _player_module
    _player_module.MPV_CONFIG = native_mpv_config(_player_module.MPV_CONFIG,
                                                  silent_audio=True)
    print(f"AUDIO_ISOLATION ao={_player_module.MPV_CONFIG.get('ao')} "
          f"audio={_player_module.MPV_CONFIG.get('audio')} "
          f"mute={_player_module.MPV_CONFIG.get('mute')}", flush=True)
    PLAYER = MPVPlayer()
    PLAYER.resize(1400, 820)
    PLAYER.show()
    pump(800)
    body_status = {"code": 0}

    def run_body():
        try:
            body_status["code"] = run_group_body(args, original_cursor,
                                                 original_foreground)
        except SystemExit as exc:
            body_status["code"] = int(exc.code or 0)
        except Exception:
            import traceback
            print("PYTHON_EXCEPTION " + traceback.format_exc().strip(),
                  flush=True)
            body_status["code"] = 90
        finally:
            # Son pencere kapandiktan sonra exec GERCEKTEN donsun.
            APP.quit()

    # Grup isi, event loop BASLADIKTAN sonra calisir; boylece timer,
    # animasyon ve native olaylar gercek dongude islenir.
    QTimer.singleShot(0, run_body)
    exec_code = APP.exec()
    print(f"MARK_APP_EXEC_RETURNED group={GROUP} code={exec_code}", flush=True)

    failed = [r for r in results if r["status"] == "FAIL"]
    blocked = [r for r in results if r["status"] == "BLOCKED"]
    print(f"GROUP_SUMMARY group={GROUP} total={len(results)} "
          f"pass={len(results)-len(failed)-len(blocked)} fail={len(failed)} "
          f"blocked={len(blocked)}", flush=True)
    print(f"MARK_DONE group={GROUP}", flush=True)
    if body_status["code"] not in (0, 1):
        return body_status["code"]
    return 1 if failed else 0


def run_group_body(args, original_cursor, original_foreground):
    """Grup olcumleri + URUN kapanisi. Event loop ICINDE calisir."""
    try:
        if args.video and os.path.isfile(args.video):
            PLAYER.open_path(args.video)
            wait_for(lambda: (PLAYER.mpv_player.duration or 0) > 0, 20000)
        for path in [p for p in args.playlist.split("|") if p and os.path.isfile(p)]:
            if path not in PLAYER.playlist:
                PLAYER.playlist.append(path)
        print(f"PLAYLIST_LEN={len(PLAYER.playlist)} "
              f"duration={PLAYER.mpv_player.duration}", flush=True)
        if not player_front():
            record("foreground_precondition", "AttachThreadInput",
                   "player foreground", str(foreground_info()), False)
            raise SystemExit(2)

        if GROUP == "buttons":
            group_buttons()
        elif GROUP == "playback_seek":
            group_playback_seek()
        elif GROUP == "timeline":
            group_timeline()
        elif GROUP == "separator":
            group_separator()
        elif GROUP == "window_resize":
            group_window_resize()
        elif GROUP == "alttab":
            group_zorder_focus = PLAYER.geometry()
            group_alttab_child = subprocess.Popen(
                [sys.executable,
                 os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "native_focus_child.py")],
                env={**os.environ, "MLC_FOCUS_CHILD_MS": "60000",
                     "MLC_FOCUS_CHILD_GEOMETRY":
                         f"{group_zorder_focus.x()+120},"
                         f"{group_zorder_focus.y()+120},600,420"})
            print(f"FOCUS_CHILD_PID={group_alttab_child.pid}", flush=True)
            try:
                pump(1800)
                group_alttab()
            finally:
                if group_alttab_child.poll() is None:
                    group_alttab_child.terminate()
                    try:
                        group_alttab_child.wait(timeout=5)
                    except Exception:
                        group_alttab_child.kill()
                print(f"FOCUS_CHILD_CLEANED pid={group_alttab_child.pid}", flush=True)
        elif GROUP == "toggle":
            group_toggle()
        elif GROUP == "dragdrop":
            group_dragdrop()
        elif GROUP == "thumbnails":
            group_thumbnails()
        elif GROUP == "fullscreen":
            group_fullscreen_esc()
        elif GROUP == "subtitles":
            # Sozlesme dogrulamasi (dosya var mi, video>0, sub=0) grubun
            # kendi icinde yapilir; burada deger oldugu gibi gecirilir.
            group_subtitles(args.no_sub_video)
        elif GROUP == "tracks":
            group_tracks()
        elif GROUP == "zorder":
            rect = PLAYER.geometry()
            group_zorder(f"{rect.x()+140},{rect.y()+140},640,460")
        else:
            print(f"UNKNOWN_GROUP {GROUP}", flush=True)
            return 3
    finally:
        # KAPANIS yalnizca URUN yolundan baslar. Child MPV'yi kendi
        # DURDURMAZ/SONLANDIRMAZ; aksi halde cift stop/terminate olur ve
        # urun kapanis sozlesmesi olculemez.
        accepted = False
        try:
            accepted = bool(PLAYER.close())
        except Exception as exc:
            print(f"TEARDOWN_WARNING {type(exc).__name__}", flush=True)
        APP.processEvents()
        stops = MPV_CALLS.count("stop")
        terminates = MPV_CALLS.count("terminate")
        released = PLAYER.mpv_player is None
        order_ok = MPV_CALLS[:2] == ["stop", "terminate"]
        record("product_shutdown_path",
               "yalniz PLAYER.close(); mpv.stop/terminate sinif duzeyinde sayildi",
               "stop=1 terminate=1 sira=stop->terminate close=accepted "
               "mpv_player=None",
               f"stop={stops} terminate={terminates} order={MPV_CALLS[:3]} "
               f"close_accepted={accepted} mpv_released={released}",
               stops == 1 and terminates == 1 and order_ok and accepted
               and released)
        user32.SetCursorPos(*original_cursor)
        if original_foreground:
            take_foreground(original_foreground, attempts=4)
        back = cursor_pos()
        print(f"CHILD_RESTORED cursor={back} "
              f"ok={abs(back[0]-original_cursor[0])<=2 and abs(back[1]-original_cursor[1])<=2}",
              flush=True)
    return 0


# URUN CIKIS POLITIKASI: `main.py` gibi, butun sonuc satirlari ve marker'lar
# flush edildikten SONRA `os._exit`. Python yorumlayici finalizasyonu bu
# kabulun parcasi degildir (Qt + libmpv + `audio-device-list` icin ayri bir
# tani riskidir). Urun kodunda os._exit KULLANILMAZ.
if __name__ == "__main__":
    os._exit(main())
