# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in GERCEK Windows olcumu: overlay kontrollerinin NATIVE input hit'i.

Kanitlanan sorun: overlay gorsel olarak MPV video yuzeyinin uzerinde ama
`WindowFromPoint` dugme merkezinde VideoFrame (mpv `wid`) HWND'sini
donduruyor; bu yuzden gercek `SendInput` tiklamalari dugmeye HIC ulasmiyor.

Bu child:
1) Win32 pencere durumunu (style/exstyle/owner/z-order komsulari) OLCER,
2) Gercek tiklamalarla press/release/clicked/action/product sayaclarini
   toplar,
3) Playlist kapali/acik ve fullscreen kollarini ayri raporlar.

Urun metodlari kullanici hareketi taklidi icin CAGRILMAZ; yalniz sonuc
dogrulamasi icin durum okunur. Kapanis yalnizca `PLAYER.close()` ile
baslar; `os._exit` main.py politikasiyla en sonda kullanilir.

    MLC_NATIVE_SMOKE=1 MLC_NATIVE_TEST_VIDEO=<mkv> \
        python tests/native_overlay_input_zorder_child.py
"""
import ctypes
import os
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
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import (QEvent, QObject, QPoint, QRect, QSettings,  # noqa: E402
                          QStandardPaths, QTimer)
from PyQt6.QtGui import QImage, QRegion  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from app.player import MPVPlayer  # noqa: E402

user32 = ctypes.windll.user32
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetWindowLongW.restype = wintypes.LONG
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]

GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
GW_HWNDPREV, GW_HWNDNEXT, GW_OWNER = 3, 2, 4
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

APP = PLAYER = None
results = []
MPV_CALLS = []
VIDEO = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
SHOT_DIR = os.path.join(os.environ.get("TEMP", "."), "mlc_overlay_input")
os.makedirs(SHOT_DIR, exist_ok=True)


def mark(text):
    print(text, flush=True)


def record(test, expected, measured, ok, evidence=""):
    status = "PASS" if ok is True else ("FAIL" if ok is False else "BLOCKED")
    results.append({"test": test, "status": status})
    print(f"RESULT|overlay_input|{test}|SendInput/Win32|{expected}|{measured}|"
          f"{status}|{evidence}", flush=True)


def install_mpv_call_recorder():
    import mpv as mpv_module

    real_stop, real_terminate = mpv_module.MPV.stop, mpv_module.MPV.terminate

    def recording_stop(self, *a, **k):
        MPV_CALLS.append("stop")
        return real_stop(self, *a, **k)

    def recording_terminate(self, *a, **k):
        MPV_CALLS.append("terminate")
        return real_terminate(self, *a, **k)

    mpv_module.MPV.stop = recording_stop
    mpv_module.MPV.terminate = recording_terminate


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        APP.processEvents()
        time.sleep(0.008)
    APP.processEvents()


def wait_for(predicate, timeout_ms=5000, step_ms=60):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:
            pass
        pump(step_ms)
    return False


def send(*items):
    array = (INPUT * len(items))(*items)
    user32.SendInput(len(items), array, ctypes.sizeof(INPUT))


def click(x, y, settle=350):
    user32.SetCursorPos(int(x), int(y))
    pump(120)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0))))
    pump(70)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0))))
    pump(settle)


def hwnd_of(widget):
    try:
        return int(widget.winId()) if widget is not None else 0
    except Exception:
        return 0


def window_from_point(x, y):
    return int(user32.WindowFromPoint(wintypes.POINT(int(x), int(y))) or 0)


def style_info(hwnd):
    style = int(user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_STYLE)) & 0xFFFFFFFF
    exstyle = int(user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)) & 0xFFFFFFFF
    return {
        "style": hex(style), "exstyle": hex(exstyle),
        "TRANSPARENT": bool(exstyle & WS_EX_TRANSPARENT),
        "NOACTIVATE": bool(exstyle & WS_EX_NOACTIVATE),
        "TOPMOST": bool(exstyle & WS_EX_TOPMOST),
        "LAYERED": bool(exstyle & WS_EX_LAYERED),
        "TOOLWINDOW": bool(exstyle & WS_EX_TOOLWINDOW),
    }


def window_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def centre(widget):
    rect = global_rect(widget)
    return rect.center().x(), rect.center().y()


class Probe(QObject):
    """Yalniz gozlem: press/release/clicked/action/product sayaclari."""

    def __init__(self, widget, product_method=None):
        super().__init__(widget)
        self.widget = widget
        self.press = self.release = self.clicked = 0
        self.overlay_action = self.product_calls = 0
        self._restores = []
        widget.installEventFilter(self)
        try:
            widget.clicked.connect(self._clicked)
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

            def counting_method(*a, **k):
                self.product_calls += 1
                return real_method(*a, **k)

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

    def _clicked(self, *args):
        self.clicked += 1

    def counters(self):
        return (f"press={self.press} release={self.release} "
                f"clicked={self.clicked} overlay_action={self.overlay_action} "
                f"product_calls={self.product_calls}")

    def close(self):
        for restore in self._restores:
            try:
                restore()
            except Exception:
                pass
        try:
            self.widget.removeEventFilter(self)
        except Exception:
            pass


def overlay_button(name):
    overlay = PLAYER.video_frame.control_overlay
    for child in overlay.findChildren(QObject):
        if child.objectName() == name:
            return child
    return None


def ensure_player_front(attempts=6):
    """Olcum oncesi oynatici GERCEKTEN foreground olmali.

    Baska bir uygulama one gecerse Win32 girdisi ona gider ve olcum kirlenir
    (`hit=other(...)`). Yalniz KENDI penceremiz one alinir; baska uygulama
    kapatilmaz.
    """
    target = hwnd_of(PLAYER)
    for _ in range(attempts):
        current = int(user32.GetForegroundWindow() or 0)
        if current == target:
            return True
        user32.SetForegroundWindow(wintypes.HWND(target))
        pump(250)
    ok = int(user32.GetForegroundWindow() or 0) == target
    if not ok:
        mark("FOREGROUND_LOST expected=" + str(target) + " actual="
             + str(int(user32.GetForegroundWindow() or 0)))
    return ok


def wake_overlay():
    ensure_player_front()
    frame = PLAYER.video_frame
    rect = global_rect(frame)
    user32.SetCursorPos(rect.center().x(), rect.center().y() - 40)
    pump(150)
    frame.show_overlay_for_interaction()
    pump(250)


def measure_native_state(tag):
    """ADIM 1: urun degistirilmeden Win32 durumu."""
    frame = PLAYER.video_frame
    overlay = frame.control_overlay
    window_hwnd, frame_hwnd = hwnd_of(PLAYER), hwnd_of(frame)
    overlay_hwnd = hwnd_of(overlay)
    owner = int(user32.GetWindow(wintypes.HWND(overlay_hwnd), GW_OWNER) or 0)
    parent = int(user32.GetParent(wintypes.HWND(overlay_hwnd)) or 0)
    prev = int(user32.GetWindow(wintypes.HWND(overlay_hwnd), GW_HWNDPREV) or 0)
    nxt = int(user32.GetWindow(wintypes.HWND(overlay_hwnd), GW_HWNDNEXT) or 0)
    fg = int(user32.GetForegroundWindow() or 0)
    fg_pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(fg), ctypes.byref(fg_pid))
    active = QApplication.activeWindow()
    mark(f"NATIVE_STATE[{tag}] window_hwnd={window_hwnd} frame_hwnd={frame_hwnd} "
         f"overlay_hwnd={overlay_hwnd} overlay_owner={owner} "
         f"overlay_parent={parent} prev={prev} next={nxt} "
         f"overlay_style={style_info(overlay_hwnd)} "
         f"frame_style={style_info(frame_hwnd)} "
         f"overlay_rect={window_rect(overlay_hwnd)} "
         f"frame_rect={window_rect(frame_hwnd)} "
         f"overlay_visible={overlay.isVisible()} "
         f"overlay_opacity={overlay.windowOpacity():.2f} "
         f"flags={int(overlay.windowFlags().value):#x} "
         f"foreground_hwnd={fg} foreground_pid={int(fg_pid.value)} "
         f"own_pid={os.getpid()} active_window={type(active).__name__}")
    return {"window": window_hwnd, "frame": frame_hwnd, "overlay": overlay_hwnd}


def hit_name(x, y, hwnds):
    hwnd = window_from_point(x, y)
    which = ("overlay" if hwnd == hwnds["overlay"] else
             "video_frame" if hwnd == hwnds["frame"] else
             "main_window" if hwnd == hwnds["window"] else f"other({hwnd})")
    return hwnd, which


def hit_map(hwnds, tag):
    """Overlay uzerinde nokta nokta WindowFromPoint haritasi.

    Layered pencerede hit-test PIKSEL ALFASINA gore yapilir; tamamen
    saydam pikseller alttaki pencereye duser. Bu harita "z-order" ile
    "piksel saydamligi" ayrimini kanitlar.
    """
    overlay = PLAYER.video_frame.control_overlay
    rect = global_rect(overlay)
    samples = []
    for name in ("overlayPlayPause", "overlayFullscreen", "overlayVolume",
                 "overlaySubtitles"):
        button = overlay_button(name)
        if button is None:
            continue
        brect = global_rect(button)
        cx, cy = brect.center().x(), brect.center().y()
        for label, (x, y) in (
                ("centre", (cx, cy)),
                ("centre+6y", (cx, cy + 6)),
                ("left+4", (brect.left() + 4, cy)),
                ("top+3", (cx, brect.top() + 3)),
                ("bottom-3", (cx, brect.bottom() - 3))):
            samples.append((f"{name}.{label}", x, y))
    samples.append(("overlay.bottom_strip", rect.center().x(),
                    rect.bottom() - 4))
    samples.append(("overlay.top_strip", rect.center().x(), rect.top() + 3))
    samples.append(("overlay.middle_gap", rect.left() + 40,
                    rect.center().y()))
    for label, x, y in samples:
        hwnd, which = hit_name(x, y, hwnds)
        mark(f"HITMAP[{tag}] {label} point=({x},{y}) -> {which} hwnd={hwnd}")


def zorder_timeline(hwnds, tag):
    """AYNI noktayi zaman icinde ornekler: z-order kayiyor mu?

    `raise_()` sonrasi overlay uste geliyor ama mpv render dongusu yeniden
    one gecerse ayni nokta kisa sure sonra video_frame'e duser.
    """
    button = overlay_button("overlayPlayPause")
    if button is None:
        return
    overlay = PLAYER.video_frame.control_overlay
    x, y = centre(button)
    overlay.raise_()
    pump(60)
    for delay in (0, 60, 150, 400, 900, 1800):
        pump(delay)
        hwnd, which = hit_name(x, y, hwnds)
        mark(f"ZORDER[{tag}] after_raise+{delay}ms point=({x},{y}) -> {which}")
    # Bir de dogrudan native SetWindowPos ile owner-relative one alma:
    HWND_TOP = 0
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
    user32.SetWindowPos(wintypes.HWND(hwnds["overlay"]), wintypes.HWND(HWND_TOP),
                        0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
    pump(80)
    for delay in (0, 200, 800):
        pump(delay)
        hwnd, which = hit_name(x, y, hwnds)
        mark(f"ZORDER[{tag}] after_setwindowpos+{delay}ms -> {which}")



# ---------------------------------------------------------------------
# GERCEK ALFA HARITASI + HWND DOGRULAMASI + GECERLI ALFA A/B MATRISI
# ---------------------------------------------------------------------

CONTROLS = ("overlayTimeline", "overlayPrevious", "overlayPlayPause",
            "overlayNext", "overlaySubtitles", "overlaySettings",
            "overlayVolume", "overlayVolumeSlider", "overlayFullscreen")

BUTTON_SELECTORS = ", ".join(
    "QPushButton#" + name for name in
    ("overlayPrevious", "overlayPlayPause", "overlayNext", "overlaySubtitles",
     "overlaySettings", "overlayVolume", "overlayFullscreen"))
SLIDER_SELECTORS = "QSlider#overlayTimeline, QSlider#overlayVolumeSlider"
DIAG_BASE_STYLE = [""]


def render_overlay_image():
    """Overlay'i SAYDAM QImage uzerine cizer: gercek ARGB alfa kaynagi."""
    overlay = PLAYER.video_frame.control_overlay
    image = QImage(overlay.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    overlay.render(image, QPoint(), QRegion(overlay.rect()),
                   QWidget.RenderFlag.DrawChildren)
    return image, global_rect(overlay).topLeft()


def alpha_at(image, origin, x, y):
    local_x, local_y = int(x - origin.x()), int(y - origin.y())
    if not (0 <= local_x < image.width() and 0 <= local_y < image.height()):
        return -1
    return (image.pixel(local_x, local_y) >> 24) & 0xFF


def alpha_block(image, origin, x, y, size=9):
    half = size // 2
    values = []
    for dx in range(-half, half + 1):
        for dy in range(-half, half + 1):
            value = alpha_at(image, origin, x + dx, y + dy)
            if value >= 0:
                values.append(value)
    if not values:
        return (-1, -1, 0)
    return (min(values), max(values), sum(1 for v in values if v > 0))


def control_points(widget):
    rect = global_rect(widget)
    cx, cy = rect.center().x(), rect.center().y()
    return [
        ("centre", cx, cy),
        ("centre-6y", cx, cy - 6),
        ("centre+6y", cx, cy + 6),
        ("left+4", rect.left() + 4, cy),
        ("right-4", rect.right() - 4, cy),
        ("top+4", cx, rect.top() + 4),
        ("bottom-4", cx, rect.bottom() - 4),
    ]


def alpha_hit_map(hwnds, tag):
    """ADIM 1: gercek alfa + WindowFromPoint iliskisi (ayni satirda)."""
    image, origin = render_overlay_image()
    rows = []
    for name in CONTROLS:
        widget = overlay_button(name)
        if widget is None:
            mark("ALPHAMAP[" + tag + "] " + name + " MISSING")
            continue
        # Auto-hide (2500 ms) olcumu bozmasin: her kontrolden ONCE uyandir.
        wake_overlay()
        image, origin = render_overlay_image()
        overlay = PLAYER.video_frame.control_overlay
        qt_visible = overlay.isVisible()
        win_visible = bool(user32.IsWindowVisible(
            wintypes.HWND(hwnds["overlay"])))
        opacity = overlay.windowOpacity()
        for label, x, y in control_points(widget):
            alpha = alpha_at(image, origin, x, y)
            low, high, nonzero = alpha_block(image, origin, x, y)
            hwnd, which = hit_name(x, y, hwnds)
            mark(f"ALPHAMAP[{tag}] {name}.{label} point=({x},{y}) "
                 f"alpha={alpha} block9(min={low},max={high},nonzero={nonzero}) "
                 f"hit={which} hwnd={hwnd} qt_visible={qt_visible} "
                 f"win_visible={win_visible} opacity={opacity:.2f}")
            rows.append((name, label, alpha, which))
    return rows


def verify_hwnd(hwnds):
    """ADIM 2: WindowFromPoint HWND kimligi + VideoFrame child pencereleri."""
    button = overlay_button("overlayPlayPause")
    x, y = centre(button)
    hwnd = window_from_point(x, y)
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buffer, 256)
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    chain = []
    current = hwnd
    for _ in range(6):
        current = int(user32.GetParent(wintypes.HWND(current)) or 0)
        if not current:
            break
        chain.append(current)
    owner = int(user32.GetWindow(wintypes.HWND(hwnd), GW_OWNER) or 0)
    mark(f"HWNDCHECK point=({x},{y}) hwnd={hwnd} class={buffer.value!r} "
         f"pid={int(pid.value)} own_pid={os.getpid()} parents={chain} "
         f"owner={owner} rect={window_rect(hwnd)} "
         f"equals_video_frame={hwnd == hwnds['frame']} "
         f"equals_overlay={hwnd == hwnds['overlay']}")

    children = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def collect(child_hwnd, _param):
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wintypes.HWND(child_hwnd), name, 256)
        children.append((int(child_hwnd), name.value,
                         window_rect(int(child_hwnd))))
        return True

    user32.EnumChildWindows(wintypes.HWND(hwnds["frame"]), collect, 0)
    mark(f"HWNDCHECK video_frame_children={children}")


def apply_diagnostic_alpha(alpha):
    """Teshis: YALNIZ hedef selector'lere notr siyah arka plan."""
    overlay = PLAYER.video_frame.control_overlay
    rule = (BUTTON_SELECTORS + " { background: rgba(0, 0, 0, "
            + str(alpha) + "); } " + SLIDER_SELECTORS
            + " { background: rgba(0, 0, 0, " + str(alpha) + "); }")
    overlay.setStyleSheet(DIAG_BASE_STYLE[0] + " " + rule)
    for name in CONTROLS:
        widget = overlay_button(name)
        if widget is None:
            continue
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    overlay.update()
    pump(350)


def alpha_matrix(hwnds):
    """ADIM 3: alfa 0..32 icin RENDER EDILEN alfa + hit + gercek tiklama."""
    overlay = PLAYER.video_frame.control_overlay
    DIAG_BASE_STYLE[0] = overlay.styleSheet()
    working = []
    try:
        for alpha in (2, 3, 4, 6, 8, 12, 16):
            apply_diagnostic_alpha(alpha)
            wake_overlay()
            image, origin = render_overlay_image()
            line = []
            for name in ("overlayPlayPause", "overlayFullscreen",
                         "overlaySubtitles", "overlayTimeline"):
                widget = overlay_button(name)
                if widget is None:
                    continue
                x, y = centre(widget)
                rendered = alpha_at(image, origin, x, y)
                hwnd, which = hit_name(x, y, hwnds)
                line.append(name + "(rendered=" + str(rendered)
                            + ",hit=" + which + ")")
            mark("ALPHAMATRIX requested=" + str(alpha) + " " + " ".join(line))
            button = overlay_button("overlayPlayPause")
            x, y = centre(button)
            wake_overlay()
            if hit_name(x, y, hwnds)[1] == "overlay":
                probe = Probe(button, product_method="play_pause")
                before = bool(PLAYER.mpv_player.pause)
                click(x, y)
                changed = wait_for(
                    lambda: bool(PLAYER.mpv_player.pause) != before, 4000)
                mark("ALPHAMATRIX_CLICK alpha=" + str(alpha) + " "
                     + probe.counters() + " pause " + str(before) + "->"
                     + str(PLAYER.mpv_player.pause) + " changed="
                     + str(changed))
                probe.close()
                if changed:
                    click(x, y)
                    wait_for(lambda: bool(PLAYER.mpv_player.pause) == before,
                             4000)
                    working.append(alpha)
    finally:
        overlay.setStyleSheet(DIAG_BASE_STYLE[0])
        for name in CONTROLS:
            widget = overlay_button(name)
            if widget is not None:
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        overlay.update()
        pump(300)
    return min(working) if working else None


def check_button(name, product_method, expect_state, tag, hwnds):
    """Bir overlay dugmesinin GERCEK tiklanabilirligini olcer."""
    button = overlay_button(name)
    if button is None:
        record(f"{name}[{tag}]", "dugme bulunur", "bulunamadi", False)
        return
    wake_overlay()
    if not wait_for(lambda: PLAYER.video_frame.control_overlay.isVisible(), 3000):
        record(f"{name}[{tag}]", "overlay gorunur", "gorunmedi", None)
        return
    x, y = centre(button)
    hwnd, which = hit_name(x, y, hwnds)
    probe = Probe(button, product_method=product_method)
    before = expect_state()
    click(x, y)
    changed = wait_for(lambda: expect_state() != before, 4000)
    counters = probe.counters()
    after = expect_state()
    probe.close()
    record(f"{name}[{tag}]",
           "WindowFromPoint=overlay; press=1 release=1 clicked=1 "
           "overlay_action=1 product_calls=1; urun state degisir",
           f"hit={which} hwnd={hwnd} {counters} state={before}->{after}",
           which == "overlay" and probe.press == 1 and probe.release == 1
           and probe.clicked == 1 and probe.overlay_action == 1
           and probe.product_calls == 1 and changed)
    return changed



# ---------------------------------------------------------------------
# TAM KONTROL MATRISI (gercek SendInput)
# ---------------------------------------------------------------------

PLAYLIST = [p for p in os.environ.get("MLC_PLAYLIST_VIDEOS", "").split("|")
            if p and os.path.isfile(p)]


def drag(x0, y0, x1, y1, steps=12):
    user32.SetCursorPos(int(x0), int(y0))
    pump(90)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0))))
    pump(70)
    for index in range(1, steps + 1):
        user32.SetCursorPos(int(x0 + (x1 - x0) * index / steps),
                            int(y0 + (y1 - y0) * index / steps))
        APP.processEvents()
        time.sleep(0.014)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0))))
    pump(300)


def sub_tracks():
    try:
        return [t for t in (PLAYER.mpv_player.track_list or [])
                if isinstance(t, dict) and t.get("type") == "sub"]
    except Exception:
        return []


def check_timeline(tag, hwnds):
    """Timeline: cizgi ustu/merkez/alti tiklamasi + surukleme."""
    timeline = overlay_button("overlayTimeline")
    if timeline is None:
        record("timeline[" + tag + "]", "timeline bulunur", "yok", False)
        return
    mpv = PLAYER.mpv_player
    rect_all = {}
    for label, offset in (("above", -14), ("centre", 0), ("below", 14)):
        wake_overlay()
        rect = global_rect(timeline)
        x = rect.left() + int(rect.width() * (0.35 if label == "above"
                                              else 0.5 if label == "centre"
                                              else 0.65))
        y = rect.center().y() + offset
        hwnd, which = hit_name(x, y, hwnds)
        probe = Probe(timeline, product_method="seek_position")
        before = float(mpv.time_pos or 0)
        click(x, y, settle=900)
        changed = wait_for(
            lambda: abs(float(mpv.time_pos or 0) - before) > 5, 6000)
        rect_all[label] = which
        record("timeline_" + label + "[" + tag + "]",
               "hit=overlay, press/release=1, seek gerceklesir",
               "hit=" + which + " " + probe.counters() + " pos "
               + str(round(before, 2)) + "->" + str(round(float(mpv.time_pos or 0), 2)),
               which == "overlay" and probe.press == 1 and probe.release == 1
               and changed)
        probe.close()
    # Surukleme
    wake_overlay()
    rect = global_rect(timeline)
    y = rect.center().y()
    start = rect.left() + int(rect.width() * 0.3)
    end = rect.left() + int(rect.width() * 0.6)
    before = float(mpv.time_pos or 0)
    drag(start, y, end, y)
    moved = wait_for(lambda: abs(float(mpv.time_pos or 0) - before) > 5, 6000)
    record("timeline_drag[" + tag + "]", "surukleme ile seek",
           "pos " + str(round(before, 2)) + "->"
           + str(round(float(mpv.time_pos or 0), 2)), moved)


def check_prev_next(tag, hwnds):
    """Onceki/Sonraki: en az uc girdili playlist ile index degisimi."""
    if len(PLAYER.playlist) < 3:
        record("prev_next[" + tag + "]", "en az 3 girdi",
               "playlist=" + str(len(PLAYER.playlist)), None,
               "BLOCKED: ORTAM EKSIGI (MLC_PLAYLIST_VIDEOS)")
        return
    for name, method, delta in (("overlayNext", "play_next", 1),
                                ("overlayPrevious", "play_previous", -1)):
        button = overlay_button(name)
        wake_overlay()
        x, y = centre(button)
        hwnd, which = hit_name(x, y, hwnds)
        probe = Probe(button, product_method=method)
        before = PLAYER.current_playlist_index
        click(x, y, settle=900)
        changed = wait_for(
            lambda: PLAYER.current_playlist_index != before, 12000)
        record(name + "[" + tag + "]",
               "hit=overlay, sayaclar=1, index degisir",
               "hit=" + which + " " + probe.counters() + " index "
               + str(before) + "->" + str(PLAYER.current_playlist_index),
               which == "overlay" and probe.press == 1 and probe.clicked == 1
               and probe.overlay_action == 1 and probe.product_calls == 1
               and changed)
        probe.close()
        wait_for(lambda: (PLAYER.mpv_player.duration or 0) > 0, 15000)


def check_subtitles(tag, hwnds):
    """CC: altyazi parcasi yoksa state degisimi BEKLENMEZ."""
    button = overlay_button("overlaySubtitles")
    tracks = sub_tracks()
    wake_overlay()
    x, y = centre(button)
    hwnd, which = hit_name(x, y, hwnds)
    probe = Probe(button, product_method="toggle_subtitles")
    before_visibility = bool(PLAYER.mpv_player.sub_visibility)
    click(x, y, settle=800)
    pump(600)
    counters = probe.counters()
    after_visibility = bool(PLAYER.mpv_player.sub_visibility)
    probe.close()
    if tracks:
        ok = (which == "overlay" and probe.press == 1 and probe.clicked == 1
              and probe.product_calls == 1
              and after_visibility != before_visibility)
        detail = "tracks=" + str(len(tracks))
    else:
        # Altyazi yoksa: cagri TAM BIR KEZ ulasir, gorunurluk KAPALI kalir.
        ok = (which == "overlay" and probe.press == 1 and probe.clicked == 1
              and probe.product_calls == 1 and after_visibility is False)
        detail = "tracks=0 (state degisimi beklenmiyor)"
    record("overlaySubtitles[" + tag + "]",
           "hit=overlay, toggle_subtitles TAM BIR KEZ, guvenli davranis",
           "hit=" + which + " " + counters + " visibility "
           + str(before_visibility) + "->" + str(after_visibility) + " "
           + detail, ok)


def check_settings(tag, hwnds):
    """Ayarlar: gercek pencere acilir; YALNIZ testin actigi pencere kapatilir."""
    from PyQt6.QtWidgets import QDialog

    button = overlay_button("overlaySettings")
    wake_overlay()
    x, y = centre(button)
    hwnd, which = hit_name(x, y, hwnds)
    probe = Probe(button, product_method="setup_video_adjustments")
    opened = []
    dialog_hit = {}

    def watch():
        # Dialog MODAL `exec()` acar: ana dongu bloklanir. Tespit ve
        # kapatma bu yuzden timer icinden (modal dongude) yapilir.
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                if widget not in opened:
                    opened.append(widget)
                    drect = global_rect(widget)
                    dialog_hit["overlay_above"] = (
                        hit_name(drect.center().x(),
                                 drect.center().y(), hwnds)[1] == "overlay")
                    QTimer.singleShot(500, widget.close)
    timer = QTimer()
    timer.timeout.connect(watch)
    timer.start(80)
    # Dialog modal exec() acar; tiklamayi gonderip dialogu ayri kapatiriz.
    user32.SetCursorPos(int(x), int(y))
    pump(120)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0))))
    pump(70)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0))))
    deadline = time.time() + 12
    while time.time() < deadline and (not opened
                                      or any(w.isVisible() for w in opened)):
        APP.processEvents()
        time.sleep(0.05)
    timer.stop()
    dialog_titles = [w.windowTitle() for w in opened]
    # Dialog acikken overlay onune GECMEMELI
    overlay_above_dialog = None
    if opened:
        overlay_above_dialog = bool(dialog_hit.get("overlay_above"))
        for widget in list(opened):
            if widget.isVisible():
                widget.close()
        pump(500)
    counters = probe.counters()
    probe.close()
    record("overlaySettings[" + tag + "]",
           "hit=overlay, sayaclar=1, gercek dialog acilir, overlay dialogun "
           "onune gecmez",
           "hit=" + which + " " + counters + " dialogs=" + str(dialog_titles)
           + " overlay_above_dialog=" + str(overlay_above_dialog)
           + " still_open=" + str(sum(1 for w in opened if w.isVisible())),
           which == "overlay" and probe.press == 1 and probe.clicked == 1
           and bool(dialog_titles) and overlay_above_dialog is False
           and not any(w.isVisible() for w in opened))


def check_volume_slider(tag, hwnds):
    """Ses cubugu: mevcut degerden UZAK dinamik hedefe tiklama."""
    slider = overlay_button("overlayVolumeSlider")
    classic = PLAYER.volume_slider
    wake_overlay()
    rect = global_rect(slider)
    before = classic.value()
    span = max(1, slider.maximum() - slider.minimum())
    ratio = 0.75 if (before - slider.minimum()) / span < 0.5 else 0.25
    x = rect.left() + int(rect.width() * ratio)
    y = rect.center().y()
    hwnd, which = hit_name(x, y, hwnds)
    probe = Probe(slider)
    click(x, y, settle=700)
    changed = wait_for(lambda: abs(classic.value() - before) >= 30, 5000)
    try:
        mpv_volume = float(PLAYER.mpv_player.volume)
    except Exception:
        mpv_volume = -1
    counters = probe.counters()
    probe.close()
    record("overlayVolumeSlider[" + tag + "]",
           "hit=overlay, press/release=1, overlay+klasik+mpv yeni degere gecer",
           "hit=" + which + " " + counters + " classic " + str(before) + "->"
           + str(classic.value()) + " overlay=" + str(slider.value())
           + " mpv=" + str(round(mpv_volume, 1)) + " target_ratio="
           + str(ratio), which == "overlay" and probe.press == 1
           and probe.release == 1 and changed
           and abs(slider.value() - classic.value()) <= 2
           and abs(mpv_volume - classic.value()) <= 2)
    # Eski degeri geri yukle
    PLAYER.volume_slider.setValue(before)
    pump(200)


def run_control_matrix(tag, hwnds, include_playlist=True):
    """Bir durum icin BUTUN kontrolleri olcer."""
    mpv = PLAYER.mpv_player
    frame = PLAYER.video_frame
    check_button("overlayPlayPause", "play_pause", lambda: bool(mpv.pause),
                 tag, hwnds)
    if bool(mpv.pause):
        wake_overlay()
        button = overlay_button("overlayPlayPause")
        x, y = centre(button)
        click(x, y, settle=500)
        wait_for(lambda: not bool(mpv.pause), 4000)
    check_button("overlayVolume", "toggle_mute",
                 lambda: bool(getattr(PLAYER, "is_muted", False)), tag, hwnds)
    if getattr(PLAYER, "is_muted", False):
        wake_overlay()
        button = overlay_button("overlayVolume")
        x, y = centre(button)
        click(x, y, settle=400)
        wait_for(lambda: not getattr(PLAYER, "is_muted", False), 4000)
    check_volume_slider(tag, hwnds)
    check_subtitles(tag, hwnds)
    check_settings(tag, hwnds)
    check_timeline(tag, hwnds)
    if include_playlist:
        check_prev_next(tag, hwnds)


def check_fade_states(hwnds):
    """Fade/auto-hide: opacity=1 tiklanabilir, gizli overlay islem uretmez."""
    frame = PLAYER.video_frame
    overlay = frame.control_overlay
    wake_overlay()
    ok_visible = wait_for(lambda: overlay.windowOpacity() >= 0.99, 4000)
    targets = {}
    for name in ("overlayPlayPause", "overlayFullscreen", "overlaySubtitles",
                 "overlayTimeline", "overlayVolume"):
        widget = overlay_button(name)
        if widget is None:
            continue
        x, y = centre(widget)
        targets[name] = hit_name(x, y, hwnds)[1]
    record("fade_opacity_full", "opacity>=0.99 iken TUM hedefler overlay",
           "opacity=" + str(round(overlay.windowOpacity(), 2)) + " "
           + str(targets),
           ok_visible and set(targets.values()) == {"overlay"})

    # Auto-hide: imlec VIDEO alanina park edilir (overlay uzerinde degil;
    # kontrol uzerinde beklemek urunun `_overlay_interaction_blocked`
    # kuralina gore auto-hide'i BILINCLI olarak engeller).
    frame_rect = global_rect(frame)
    user32.SetCursorPos(frame_rect.center().x(), frame_rect.top() + 60)
    pump(300)
    hidden = wait_for(lambda: not overlay.isVisible()
                      or overlay.windowOpacity() <= 0.01, 12000)
    record("fade_auto_hide",
           "etkilesim yokken overlay gizlenir",
           "hidden=" + str(hidden) + " visible=" + str(overlay.isVisible())
           + " opacity=" + str(round(overlay.windowOpacity(), 2)), hidden)
    # DOGAL fiziksel senaryo: overlay auto-hide ile gizlendikten SONRA
    # imlec HAREKET ETTIRILMEDEN, bulundugu VIDEO noktasinda tiklanir.
    # Beklenen: hicbir overlay kontrolu tetiklenmez.
    mark("INFO fade_hidden_click: 'gizli dugmenin eski koordinatina dogal "
         "fare hareketi olmadan tiklama' senaryosu fiziksel olarak anlamsiz "
         "(imlecin hedefe gitmesi overlay'i mesru sekilde uyandirir); "
         "bunun yerine video alanindaki hareketsiz tiklama olculur")
    watchers = []
    for name in ("overlayTimeline", "overlayPrevious", "overlayPlayPause",
                 "overlayNext", "overlaySubtitles", "overlaySettings",
                 "overlayVolume", "overlayVolumeSlider", "overlayFullscreen"):
        widget = overlay_button(name)
        if widget is not None:
            watchers.append((name, Probe(widget)))
    product_counts = {}
    product_restores = []
    for method in ("play_pause", "toggle_mute", "toggle_subtitles",
                   "setup_video_adjustments", "toggle_fullscreen",
                   "play_previous", "play_next"):
        real = getattr(PLAYER, method, None)
        if real is None:
            continue
        product_counts[method] = 0

        def make(method_name, real_method):
            def counting(*args, **kwargs):
                product_counts[method_name] += 1
                return real_method(*args, **kwargs)
            return counting

        setattr(PLAYER, method, make(method, real))
        product_restores.append((method, real))

    before_pause = bool(PLAYER.mpv_player.pause)
    before_muted = bool(getattr(PLAYER, "is_muted", False))
    before_index = PLAYER.current_playlist_index
    before_fullscreen = bool(frame.is_video_fullscreen)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0))))
    pump(80)
    send(INPUT(type=INPUT_MOUSE,
               u=_U(mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0))))
    pump(900)
    clicked_counts = {name: probe.clicked for name, probe in watchers}
    for _name, probe in watchers:
        probe.close()
    for method, real in product_restores:
        setattr(PLAYER, method, real)
    state_same = (bool(PLAYER.mpv_player.pause) == before_pause
                  and bool(getattr(PLAYER, "is_muted", False)) == before_muted
                  and PLAYER.current_playlist_index == before_index
                  and bool(frame.is_video_fullscreen) == before_fullscreen)
    record("hidden_video_click_does_not_trigger_overlay_action",
           "gizli overlay iken video uzerindeki hareketsiz tiklama hicbir "
           "kontrolu tetiklemez (clicked=0, urun cagrisi=0)",
           "clicked=" + str(clicked_counts) + " product=" + str(product_counts)
           + " state_same=" + str(state_same)
           + " overlay_visible_after=" + str(overlay.isVisible()),
           all(value == 0 for value in clicked_counts.values())
           and all(value == 0 for value in product_counts.values())
           and state_same)


    # Fareyle geri getir: yeniden tiklanabilir olmali
    wake_overlay()
    wait_for(lambda: overlay.windowOpacity() >= 0.99, 5000)
    check_button("overlayPlayPause", "play_pause",
                 lambda: bool(PLAYER.mpv_player.pause), "after_fade_in", hwnds)
    if bool(PLAYER.mpv_player.pause):
        wake_overlay()
        click(x, y, settle=400)
        wait_for(lambda: not bool(PLAYER.mpv_player.pause), 4000)


def check_focus_child(hwnds):
    """Testin KENDI Qt focus child'i one gecince overlay gizlenmeli."""
    import subprocess

    frame = PLAYER.video_frame
    overlay = frame.control_overlay
    rect = PLAYER.geometry()
    child = None
    try:
        child = subprocess.Popen(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "native_focus_child.py")],
            env={**os.environ, "MLC_FOCUS_CHILD_MS": "20000",
                 "MLC_FOCUS_CHILD_GEOMETRY":
                     str(rect.x() + 120) + "," + str(rect.y() + 120)
                     + ",640,460"})
        mark("FOCUS_CHILD_PID=" + str(child.pid))
        pump(2500)
        hidden = wait_for(lambda: not overlay.isVisible(), 6000)
        osd = frame.osd_label
        osd_hidden = osd is None or not osd.isVisible()
        exstyle = int(user32.GetWindowLongW(
            wintypes.HWND(hwnds["overlay"]), GWL_EXSTYLE)) & 0xFFFFFFFF
        record("focus_child_hides_overlay",
               "baska pencere ondeyken overlay ve OSD gizli, TOPMOST yok",
               "overlay_visible=" + str(overlay.isVisible())
               + " osd_hidden=" + str(osd_hidden)
               + " TOPMOST=" + str(bool(exstyle & WS_EX_TOPMOST)),
               hidden and osd_hidden and not (exstyle & WS_EX_TOPMOST))
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except Exception:
                child.kill()
            mark("FOCUS_CHILD_CLEANED pid=" + str(child.pid))
    user32.SetForegroundWindow(wintypes.HWND(hwnds["window"]))
    pump(900)
    wake_overlay()
    back = wait_for(lambda: overlay.isVisible(), 5000)
    playlist_state = PLAYER.video_frame.playlist_panel.is_open
    check_button("overlayPlayPause", "play_pause",
                 lambda: bool(PLAYER.mpv_player.pause), "after_focus_return",
                 hwnds)
    record("focus_return_restores_overlay",
           "player one gelince overlay gorunur ve playlist durumu korunur",
           "overlay_visible=" + str(back) + " playlist_open="
           + str(playlist_state), back)
    if bool(PLAYER.mpv_player.pause):
        button = overlay_button("overlayPlayPause")
        x, y = centre(button)
        wake_overlay()
        click(x, y, settle=400)
        wait_for(lambda: not bool(PLAYER.mpv_player.pause), 4000)


def visual_ab(hwnds):
    """Tani A/B: alfa=0 yuzey ile urunun alfa=2 yuzeyi PIKSEL farki."""
    from PyQt6.QtGui import QColor

    frame = PLAYER.video_frame
    overlay = frame.control_overlay
    PLAYER.mpv_player.pause = True
    pump(700)
    wake_overlay()
    product_path = os.path.join(SHOT_DIR, "visual-product-alpha2.png")
    product_image = QApplication.primaryScreen().grabWindow(0)
    product_image.save(product_path)

    base = overlay.styleSheet()
    diag = base.replace("rgba(0, 0, 0, 2)", "rgba(0, 0, 0, 0)")
    overlay.setStyleSheet(diag)
    for child in overlay.findChildren(QWidget):
        child.style().unpolish(child)
        child.style().polish(child)
    overlay.update()
    pump(600)
    wake_overlay()
    diag_path = os.path.join(SHOT_DIR, "visual-diag-alpha0.png")
    diag_image = QApplication.primaryScreen().grabWindow(0)
    diag_image.save(diag_path)
    overlay.setStyleSheet(base)
    for child in overlay.findChildren(QWidget):
        child.style().unpolish(child)
        child.style().polish(child)
    overlay.update()
    pump(400)
    PLAYER.mpv_player.pause = False

    rect = global_rect(overlay)
    a = product_image.toImage()
    b = diag_image.toImage()
    max_diff = 0
    changed = 0
    for x in range(rect.left(), rect.right(), 3):
        for y in range(rect.top(), rect.bottom(), 3):
            ca = QColor(a.pixel(x, y))
            cb = QColor(b.pixel(x, y))
            delta = max(abs(ca.red() - cb.red()), abs(ca.green() - cb.green()),
                        abs(ca.blue() - cb.blue()))
            if delta > max_diff:
                max_diff = delta
            if delta > 0:
                changed += 1
    total = len(range(rect.left(), rect.right(), 3)) * len(
        range(rect.top(), rect.bottom(), 3))
    mark("VISUAL_AB product=" + product_path + " diag=" + diag_path
         + " max_rgb_diff=" + str(max_diff) + " changed_px=" + str(changed)
         + "/" + str(total))
    record("visual_alpha_difference",
           "alfa=2 yuzeyi gorunur kutu URETMEZ (max RGB farki <= 3)",
           "max_rgb_diff=" + str(max_diff) + " changed_samples=" + str(changed)
           + "/" + str(total), max_diff <= 3)


def main():
    global APP, PLAYER

    if not (VIDEO and os.path.isfile(VIDEO)):
        print("RESULTS: failures=no_real_video (ORTAM EKSIGI)", flush=True)
        os._exit(2)

    QStandardPaths.setTestModeEnabled(True)
    settings = os.path.join(os.environ.get("TEMP", "."),
                            f"mlc_overlay_input_settings-{os.getpid()}")
    os.makedirs(settings, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      settings)
    install_mpv_call_recorder()

    original_cursor = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(original_cursor))
    original_fg = int(user32.GetForegroundWindow() or 0)

    APP = QApplication([sys.argv[0]])
    PLAYER = MPVPlayer()
    PLAYER.resize(1400, 820)
    PLAYER.show()
    pump(700)
    exit_state = {"code": 0}

    def body():
        try:
            PLAYER.open_path(VIDEO)
            wait_for(lambda: (PLAYER.mpv_player.duration or 0) > 0, 20000)
            mark(f"MARK_MEDIA_READY duration={PLAYER.mpv_player.duration}")
            user32.SetForegroundWindow(wintypes.HWND(hwnd_of(PLAYER)))
            pump(400)
            wake_overlay()

            for path in PLAYLIST:
                if path not in PLAYER.playlist:
                    PLAYER.playlist.append(path)
            mark("PLAYLIST_LEN=" + str(len(PLAYER.playlist)))

            hwnds = measure_native_state("playlist_closed")
            alpha_hit_map(hwnds, "product")
            if os.environ.get("MLC_OVERLAY_DIAG") == "1":
                hit_map(hwnds, "diag")
                zorder_timeline(hwnds, "diag")
                verify_hwnd(hwnds)
                mark("ALPHA_ROOT_CAUSE minimum_working_alpha="
                     + str(alpha_matrix(hwnds)))
            frame = PLAYER.video_frame

            # --- A) Normal pencere, playlist kapali ---
            run_control_matrix("closed", hwnds)

            # --- B) Playlist acik ---
            if not frame.playlist_panel.is_open:
                frame.toggle_playlist_panel()
                frame.playlist_panel.finish_animation()
                pump(500)
            wake_overlay()
            hwnds_open = measure_native_state("playlist_open")
            run_control_matrix("playlist_open", hwnds_open,
                               include_playlist=False)
            if frame.playlist_panel.is_open:
                frame.toggle_playlist_panel()
                frame.playlist_panel.finish_animation()
                pump(500)

            # --- C) Fullscreen ---
            wake_overlay()
            check_button("overlayFullscreen", "toggle_fullscreen",
                         lambda: bool(frame.is_video_fullscreen), "enter",
                         hwnds)
            if frame.is_video_fullscreen:
                pump(800)
                wake_overlay()
                hwnds_fs = measure_native_state("fullscreen")
                run_control_matrix("fullscreen", hwnds_fs,
                                   include_playlist=False)
                shot_fs = os.path.join(SHOT_DIR, "fullscreen.png")
                QApplication.primaryScreen().grabWindow(0).save(shot_fs)
                mark("SHOT " + shot_fs)
                # --- D) Fullscreen'den donus ---
                wake_overlay()
                check_button("overlayFullscreen", "toggle_fullscreen",
                             lambda: bool(frame.is_video_fullscreen), "exit",
                             hwnds_fs)
                pump(800)
                if frame.is_video_fullscreen:
                    frame.exit_fullscreen()
                    pump(600)
                wake_overlay()
                hwnds = measure_native_state("after_fullscreen")
                check_button("overlayPlayPause", "play_pause",
                             lambda: bool(PLAYER.mpv_player.pause),
                             "after_fullscreen", hwnds)
                if bool(PLAYER.mpv_player.pause):
                    button = overlay_button("overlayPlayPause")
                    x, y = centre(button)
                    wake_overlay()
                    click(x, y, settle=400)
                    wait_for(lambda: not bool(PLAYER.mpv_player.pause), 4000)
            else:
                record("fullscreen_arm", "fullscreen acilir",
                       "acilamadi", None, "BLOCKED: fullscreen'e girilemedi")

            # --- E) Fade / auto-hide ---
            check_fade_states(hwnds)

            # --- F) Focus child ve donus ---
            check_focus_child(hwnds)

            # --- G) Gorsel A/B ---
            visual_ab(hwnds)

            path = os.path.join(SHOT_DIR, "overlay-input.png")
            QApplication.primaryScreen().grabWindow(0).save(path)
            mark(f"SHOT {path}")
        except Exception:
            import traceback
            print("PYTHON_EXCEPTION " + traceback.format_exc().strip(),
                  flush=True)
            exit_state["code"] = 90
        finally:
            try:
                accepted = bool(PLAYER.close())
            except Exception as exc:
                accepted = False
                print(f"TEARDOWN_WARNING {type(exc).__name__}", flush=True)
            record("product_shutdown_path",
                   "stop=1 terminate=1 sira=stop->terminate close=accepted",
                   f"stop={MPV_CALLS.count('stop')} "
                   f"terminate={MPV_CALLS.count('terminate')} "
                   f"order={MPV_CALLS[:3]} close_accepted={accepted} "
                   f"mpv_released={PLAYER.mpv_player is None}",
                   MPV_CALLS.count("stop") == 1
                   and MPV_CALLS.count("terminate") == 1
                   and MPV_CALLS[:2] == ["stop", "terminate"] and accepted
                   and PLAYER.mpv_player is None)
            user32.SetCursorPos(original_cursor.x, original_cursor.y)
            if original_fg:
                user32.SetForegroundWindow(wintypes.HWND(original_fg))
            APP.quit()

    QTimer.singleShot(0, body)
    exec_code = APP.exec()
    mark(f"MARK_APP_EXEC_RETURNED code={exec_code}")

    failed = [r for r in results if r["status"] == "FAIL"]
    blocked = [r for r in results if r["status"] == "BLOCKED"]
    print(f"RESULTS: failures={','.join(r['test'] for r in failed) or 'none'} "
          f"blocked={','.join(r['test'] for r in blocked) or 'none'}", flush=True)
    print("MARK_DONE", flush=True)
    code = exit_state["code"] or (1 if failed or blocked else 0)
    os._exit(code)


if __name__ == "__main__":
    main()
