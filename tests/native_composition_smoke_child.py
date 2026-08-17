# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in gerçek Windows kompozisyon smoke'u (playlist + overlay + OSD).

Kullanıcının iki hata ekran görüntüsünü native seviyede ölçer:

1. Başka uygulama öne geldiğinde playlist kaybolurken alt kontrol yüzeyi
   görünür kalıyor mu?
2. Taşıma/boyutlandırma sonrası playlist bayat global geometriyle videonun
   üstüne biniyor mu?

Qt dikdörtgenleri yeterli kanıt değildir; bu yüzden her yüzey için gerçek
HWND, parent, owner, görünürlük ve ekran dikdörtgeni okunur. Ölçüm üç anda
yapılır: devir öncesi, dış uygulama öndeyken, oynatıcıya dönünce.

Normal pytest paketine dahil değildir (dosya adı ``test_`` ile başlamaz) ve
``MLC_NATIVE_SMOKE=1`` verilmeden hiçbir Qt/MPV nesnesi oluşturmaz.

Ortam değişkenleri
------------------
MLC_NATIVE_SMOKE        "1" olmalı.
MLC_NATIVE_TEST_VIDEO   Gerçek video yolu (önerilir).
MLC_FOCUS_CHILD_MS      Dış odak penceresinin yaşam süresi (varsayılan 3000).
MLC_NATIVE_SETTINGS     QSettings INI dizini (gerçek HKCU kirletilmez).
MLC_COMPOSITION_SHOTS   "1" ise %TEMP% altına ekran görüntüsü kaydeder.

Marker akışı
------------
MARK_PLAYER_CREATED, MARK_SHOWN, MARK_PLAY, MARK_PLAYLIST_OPEN,
MARK_HWNDS, MARK_MOVED, MARK_SAMPLE_ACTIVE, MARK_FOCUS_CHILD_STARTED,
MARK_SAMPLE_INACTIVE, MARK_SAMPLE_RETURNED, RESULTS, MARK_STOP,
MARK_TERMINATE, MARK_CLOSE, MARK_DONE
"""
import os
import subprocess
import sys
import time
import ctypes

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    print("Bu smoke yalnizca MLC_NATIVE_SMOKE=1 ile calisir.", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QRect, QSettings, Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.player import MPVPlayer  # noqa: E402

VIDEO_PATH = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
FOCUS_CHILD_MS = int(os.environ.get("MLC_FOCUS_CHILD_MS", "3000"))
WANT_SHOTS = os.environ.get("MLC_COMPOSITION_SHOTS", "1") == "1"
SHOT_DIR = os.environ.get("TEMP", ".")

START = time.time()
focus_child = None
failures = []
samples = {}
# Dış odak penceresinin ekran konumu; oynatıcı geometrisi bilindikten sonra
# playlist ve kontrol katmanını örtecek şekilde ayarlanır.
_player_geometry_for_focus_child = None


def mark(name, extra=""):
    elapsed = time.time() - START
    suffix = f" {extra}" if extra else ""
    print(f"{name} t={elapsed:.2f}{suffix}", flush=True)


def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    print("PYTHON_EXCEPTION " + "".join(
        traceback.format_exception(exc_type, exc_value, exc_tb)).strip(),
        flush=True)
    instance = QApplication.instance()
    if instance is not None:
        instance.exit(90)


sys.excepthook = _excepthook

if os.name == "nt":
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    # dwExtraInfo ULONG_PTR'dir; c_void_p ile 32/64-bit uyumlu kalır.
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p]
    user32.mouse_event.restype = None
else:  # pragma: no cover - ürün yalnızca Windows'ta çalışır
    wintypes = None
    user32 = None
GW_OWNER = 4
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def hwnd_of(widget):
    if widget is None:
        return 0
    try:
        return int(widget.winId())
    except Exception:
        return 0


def native_info(widget, label):
    """Bir yüzeyin gerçek HWND, parent, owner, görünürlük ve rect bilgisi."""
    if widget is None:
        return {"label": label, "hwnd": 0, "exists": False}
    hwnd = hwnd_of(widget)
    info = {"label": label, "hwnd": hwnd, "exists": bool(hwnd),
            "qt_visible": bool(widget.isVisible())}
    if user32 is None or not hwnd:
        return info
    info["parent"] = int(user32.GetParent(hwnd))
    info["owner"] = int(user32.GetWindow(hwnd, GW_OWNER))
    info["native_visible"] = bool(user32.IsWindowVisible(hwnd))
    # Child pencere (parent != 0) parent'ının z-order'ına bağlıdır ve başka
    # bir sürecin penceresinin üstünde duramaz. Yalnızca floating (top-level)
    # yüzeyler "üstte kaldı mı?" sorusuna tabidir.
    info["floating"] = info["parent"] == 0
    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        info["rect"] = (rect.left, rect.top,
                        rect.right - rect.left, rect.bottom - rect.top)
        # Gerçek z-order kanıtı: yüzeyin merkezinde EKRANDA hangi pencere var?
        centre_x = (rect.left + rect.right) // 2
        centre_y = (rect.top + rect.bottom) // 2
        top_hwnd = int(user32.WindowFromPoint(
            wintypes.POINT(centre_x, centre_y)))
        top_pid = ctypes.c_ulong(0)
        if top_hwnd:
            user32.GetWindowThreadProcessId(top_hwnd, ctypes.byref(top_pid))
        info["topmost_at_centre_hwnd"] = top_hwnd
        info["topmost_at_centre_pid"] = int(top_pid.value)
    else:
        info["rect"] = (0, 0, 0, 0)
    return info


def foreground_hwnd():
    """Foreground HWND'i her zaman int olarak dondurur (yoksa 0).

    URUN `app/video_frame.py` `GetForegroundWindow.restype` degerini
    pointer-safe `wintypes.HWND` yapar; `ctypes.windll.user32` surec genelinde
    TEK nesne oldugu icin imza burada da gecerlidir ve NULL HWND `None` doner.
    """
    if user32 is None:
        return 0
    return int(user32.GetForegroundWindow() or 0)


def foreground_state():
    if user32 is None:
        return {"hwnd": 0, "pid": 0}
    hwnd = foreground_hwnd()
    pid = ctypes.c_ulong(0)
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"hwnd": hwnd, "pid": int(pid.value)}


def take_foreground(hwnd):
    """Ölçümden önce oynatıcıyı gerçekten foreground yapar.

    Konsoldan çalıştırıldığında terminal penceresi foreground kalır; bu
    durumda "dış uygulama öndeyken" ölçümü anlamsız olur. Bu yüzden aktif
    örnek alınmadan önce foreground açıkça oynatıcıya verilir.
    """
    if user32 is None or not hwnd:
        return False
    foreground = foreground_hwnd()
    foreground_thread = (user32.GetWindowThreadProcessId(foreground, None)
                         if foreground else 0)
    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    attached = False
    try:
        if foreground_thread and foreground_thread != current_thread:
            attached = bool(user32.AttachThreadInput(
                current_thread, foreground_thread, True))
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(current_thread, foreground_thread, False)
    return foreground_hwnd() == hwnd


def qt_rect(widget):
    if widget is None or not widget.isVisible():
        return QRect()
    from PyQt6.QtCore import QPoint
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def capture(name):
    if not WANT_SHOTS:
        return ""
    try:
        screen = QApplication.primaryScreen()
        pixmap = screen.grabWindow(0)
        path = os.path.join(SHOT_DIR, f"MLCPlayer-composition-{name}.png")
        pixmap.save(path)
        return path
    except Exception as exc:  # pragma: no cover - ortam bağımlı
        print(f"SHOT_FAILED {name} {exc}", flush=True)
        return ""


def sample(player, phase):
    """Bir andaki bütün yüzeylerin native + Qt durumunu toplar."""
    frame = player.video_frame
    panel = getattr(frame, "playlist_panel", None)
    overlay = getattr(frame, "control_overlay", None)
    osd = getattr(frame, "osd_label", None)

    data = {
        "phase": phase,
        "foreground": foreground_state(),
        "main": native_info(player, "main"),
        "video": native_info(frame, "video"),
        "playlist": native_info(panel, "playlist"),
        "overlay": native_info(overlay, "overlay"),
        "osd": native_info(osd, "osd"),
        "playlist_open": bool(getattr(panel, "is_open", False)),
        "playlist_width": int(panel.width()) if panel is not None else 0,
        "video_rect": qt_rect(frame).getRect(),
        "playlist_rect": qt_rect(panel).getRect() if panel is not None else (0, 0, 0, 0),
    }
    overlap = qt_rect(panel).intersected(qt_rect(frame)) if panel is not None else QRect()
    data["playlist_video_overlap"] = overlap.getRect() if not overlap.isEmpty() else None
    data["shot"] = capture(phase)
    samples[phase] = data
    mark(f"MARK_SAMPLE_{phase.upper()}",
         f"fg_pid={data['foreground']['pid']} "
         f"playlist_open={data['playlist_open']} "
         f"playlist_visible={data['playlist'].get('native_visible')} "
         f"overlay_visible={data['overlay'].get('native_visible')} "
         f"osd_visible={data['osd'].get('native_visible')} "
         f"playlist_topmost_pid={data['playlist'].get('topmost_at_centre_pid')} "
         f"overlap={data['playlist_video_overlap']}")
    return data


def start_focus_child():
    global focus_child
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "native_focus_child.py")
    env = dict(os.environ)
    env["MLC_FOCUS_CHILD_MS"] = str(FOCUS_CHILD_MS)
    # Dış pencere, oynatıcının playlist ve kontrol katmanı bölgesini gerçekten
    # örtmelidir; aksi halde "üstte kaldı mı?" ölçümü boş yere geçer.
    geometry = _player_geometry_for_focus_child
    if geometry is not None:
        env["MLC_FOCUS_CHILD_GEOMETRY"] = geometry
    focus_child = subprocess.Popen(
        [sys.executable, script], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    mark("MARK_FOCUS_CHILD_STARTED", f"pid={focus_child.pid}")
    return focus_child.pid


def evaluate(own_pid):
    """Kabul koşullarını ölçülen örnekler üzerinden değerlendirir."""
    active = samples.get("active", {})
    inactive = samples.get("inactive", {})
    returned = samples.get("returned", {})

    # 1. Aktif durumda playlist görünür ve videoyla kesişmiyor olmalı.
    if not active.get("playlist_open"):
        failures.append("ACTIVE_PLAYLIST_NOT_OPEN")
    if active.get("playlist_video_overlap"):
        failures.append(f"ACTIVE_OVERLAP={active['playlist_video_overlap']}")

    # 2. Taşıma/boyutlandırma sonrası bayat geometri olmamalı.
    if returned.get("playlist_video_overlap"):
        failures.append(f"RETURNED_OVERLAP={returned['playlist_video_overlap']}")

    # 3. Dış uygulama öndeyken oynatıcıya ait yüzen yüzeyler üstte kalmamalı.
    # Bu kural yalnızca "inactive" anına değil, foreground'un dışarıda olduğu
    # HER ana uygulanır. Kullanıcının 1. ekran görüntüsü tam olarak budur:
    # başka bir süreç öndeyken kontrol/timeline yüzeyi görünür kalıyor.
    if inactive.get("foreground", {}).get("pid", 0) in (0, own_pid):
        failures.append("FOREGROUND_HANDOFF_NOT_OBSERVED")
    for phase, data in samples.items():
        pid = data.get("foreground", {}).get("pid", 0)
        if pid in (0, own_pid):
            continue
        for key in ("overlay", "osd", "playlist"):
            info = data.get(key, {})
            if not info.get("native_visible"):
                continue
            if not info.get("floating"):
                # Child yüzey parent ile birlikte örtülür; kural uygulanmaz.
                continue
            failures.append(
                f"{phase.upper()}_{key.upper()}_ABOVE_EXTERNAL_PID_{pid}")

    # 4. Dönüşte açık durum ve kullanıcı genişliği korunmalı.
    if not returned.get("playlist_open"):
        failures.append("RETURN_PLAYLIST_STATE_LOST")
    if (active.get("playlist_width") and returned.get("playlist_width")
            and active["playlist_width"] != returned["playlist_width"]):
        failures.append(
            f"RETURN_WIDTH_CHANGED {active['playlist_width']}->"
            f"{returned['playlist_width']}")


def main():
    settings_dir = os.environ.get("MLC_NATIVE_SETTINGS")
    if settings_dir:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, settings_dir)

    app = QApplication(sys.argv)
    own_pid = os.getpid()
    player = MPVPlayer()
    mark("MARK_PLAYER_CREATED")
    player.resize(1400, 820)
    player.show()
    app.processEvents()
    mark("MARK_SHOWN", f"hwnd={hwnd_of(player)}")

    steps = []

    def step(fn):
        steps.append(fn)
        return fn

    @step
    def play_video():
        if VIDEO_PATH and os.path.isfile(VIDEO_PATH):
            player.open_path(VIDEO_PATH)
            mark("MARK_PLAY", f"file={os.path.basename(VIDEO_PATH)}")
        else:
            mark("MARK_PLAY", "no_video")

    @step
    def open_playlist():
        frame = player.video_frame
        frame.toggle_playlist_panel()
        panel = frame.playlist_panel
        if panel is not None:
            panel.finish_animation()
        app.processEvents()
        mark("MARK_PLAYLIST_OPEN",
             f"open={getattr(panel, 'is_open', None)} "
             f"width={panel.width() if panel else 0}")

    @step
    def record_hwnds():
        frame = player.video_frame
        for widget, label in (
                (player, "main"), (frame, "video"),
                (getattr(frame, "playlist_panel", None), "playlist"),
                (getattr(frame, "control_overlay", None), "overlay"),
                (getattr(frame, "osd_label", None), "osd")):
            info = native_info(widget, label)
            print(f"HWND {label} hwnd={info.get('hwnd')} "
                  f"parent={info.get('parent')} owner={info.get('owner')} "
                  f"visible={info.get('native_visible')} "
                  f"rect={info.get('rect')}", flush=True)
        mark("MARK_HWNDS")

    @step
    def move_and_resize():
        player.move(player.x() + 60, player.y() + 40)
        player.resize(1080, 680)
        app.processEvents()
        player.video_frame.update_playlist_panel_geometry()
        app.processEvents()
        mark("MARK_MOVED", f"geometry={player.geometry().getRect()}")

    @step
    def acquire_foreground():
        ok = take_foreground(hwnd_of(player))
        state = foreground_state()
        mark("MARK_FOREGROUND_ACQUIRED",
             f"ok={ok} fg_pid={state['pid']} own_pid={own_pid}")
        if state["pid"] != own_pid:
            failures.append(
                f"PLAYER_NEVER_FOREGROUND fg_pid={state['pid']}")

    @step
    def sample_active():
        sample(player, "active")

    @step
    def hand_off():
        # Dış pencereyi oynatıcının sağ-alt bölgesine (playlist + kontrol
        # katmanı) oturt; z-order ölçümü ancak böyle anlamlı olur.
        global _player_geometry_for_focus_child
        rect = player.geometry()
        _player_geometry_for_focus_child = ",".join(str(value) for value in (
            rect.x() + rect.width() // 3,
            rect.y() + rect.height() // 3,
            max(420, rect.width() // 2),
            max(300, rect.height() // 2)))
        start_focus_child()

    @step
    def sample_inactive():
        sample(player, "inactive")

    @step
    def return_focus():
        player.raise_()
        player.activateWindow()
        if user32 is not None:
            user32.SetForegroundWindow(hwnd_of(player))
        app.processEvents()

    @step
    def sample_returned():
        sample(player, "returned")

    def check_no_overlap(tag):
        """Bir pencere durumunda playlist/video kesişmesini ölçer."""
        frame = player.video_frame
        panel = getattr(frame, "playlist_panel", None)
        overlap = qt_rect(panel).intersected(qt_rect(frame))
        open_state = bool(getattr(panel, "is_open", False))
        mark(f"MARK_STATE_{tag.upper()}",
             f"open={open_state} width={panel.width() if panel else 0} "
             f"overlap={overlap.getRect() if not overlap.isEmpty() else None}")
        if not overlap.isEmpty():
            failures.append(f"{tag.upper()}_OVERLAP={overlap.getRect()}")
        if not open_state:
            failures.append(f"{tag.upper()}_PLAYLIST_STATE_LOST")

    @step
    def state_minimize_restore():
        player.showMinimized()
        app.processEvents()
        player.showNormal()
        app.processEvents()
        player.video_frame.update_playlist_panel_geometry()
        app.processEvents()
        check_no_overlap("minimize_restore")

    @step
    def state_maximize_restore():
        player.showMaximized()
        app.processEvents()
        player.video_frame.update_playlist_panel_geometry()
        app.processEvents()
        check_no_overlap("maximized")
        player.showNormal()
        app.processEvents()
        player.video_frame.update_playlist_panel_geometry()
        app.processEvents()
        check_no_overlap("restored")

    @step
    def state_fullscreen():
        frame = player.video_frame
        frame.enter_fullscreen()
        app.processEvents()
        frame.update_playlist_panel_geometry()
        app.processEvents()
        capture("fullscreen")
        check_no_overlap("fullscreen")
        frame.exit_fullscreen()
        app.processEvents()
        frame.update_playlist_panel_geometry()
        app.processEvents()
        capture("fullscreen-exit")
        check_no_overlap("fullscreen_exit")

    @step
    def state_small_window():
        player.resize(960, 600)
        app.processEvents()
        player.video_frame.update_playlist_panel_geometry()
        app.processEvents()
        capture("small-960x600")
        check_no_overlap("small_960x600")

    @step
    def separator_drag():
        """FİZİKSEL ayraç sürüklemesi: gerçek Win32 imleç + sol tuş girdisi.

        QTest.mouse* bir Qt sentetik jestidir ve native fare yolunu kanıtlamaz.
        Burada imleç gerçekten `SetCursorPos` ile taşınır ve sol tuş
        `mouse_event` ile basılır/bırakılır; olaylar Windows girdi kuyruğundan
        uygulamaya ulaşır.

        Kullanıcının imleç konumu kaydedilir ve `finally` içinde MUTLAKA geri
        yüklenir; sol tuş da `finally` içinde bırakılır.
        """
        frame = player.video_frame
        panel = frame.playlist_panel
        handle = panel.resize_handle
        before = panel.width()

        centre = handle.mapToGlobal(handle.rect().center())
        target_x, target_y = int(centre.x()), int(centre.y())

        player_rect = player.geometry()
        if not player_rect.contains(target_x, target_y):
            mark("MARK_SEPARATOR_DRAG", "SKIPPED target_outside_player_rect "
                 f"point=({target_x},{target_y}) player={player_rect.getRect()}")
            failures.append("SEPARATOR_TARGET_OUTSIDE_PLAYER")
            return

        # Native girdi ancak oynatıcı ön plandayken ve hedef nokta gerçekten
        # BİZE ait bir pencereye denk geldiğinde anlamlıdır. Odak devri
        # adımından sonra ön plan başka süreçte kalabiliyor; o durumda
        # sürükleme sessizce hiçbir şey yapmadan "başarısız" görünüyordu.
        take_foreground(hwnd_of(player))
        app.processEvents()
        time.sleep(0.15)
        app.processEvents()

        hit_hwnd = int(user32.WindowFromPoint(
            wintypes.POINT(target_x, target_y)))
        hit_pid = ctypes.c_ulong(0)
        if hit_hwnd:
            user32.GetWindowThreadProcessId(hit_hwnd, ctypes.byref(hit_pid))
        if int(hit_pid.value) != own_pid:
            mark("MARK_SEPARATOR_DRAG",
                 f"SKIPPED point_covered_by_other_process point=({target_x},"
                 f"{target_y}) hit_pid={hit_pid.value} own_pid={own_pid}")
            failures.append("SEPARATOR_TARGET_COVERED")
            return

        original = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(original))
        button_down = False
        widened = narrowed = before

        def glide(from_x, to_x, y, steps=9):
            """İmleci küçük adımlarla taşır ve Qt olay döngüsünü pompalar."""
            for index in range(1, steps + 1):
                x = int(from_x + (to_x - from_x) * index / steps)
                user32.SetCursorPos(x, y)
                app.processEvents()
                time.sleep(0.012)
                app.processEvents()

        try:
            user32.SetCursorPos(target_x, target_y)
            app.processEvents()
            time.sleep(0.05)
            app.processEvents()

            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
            button_down = True
            app.processEvents()

            # Sola: panel genişler.
            glide(target_x, target_x - 90, target_y)
            widened = panel.width()

            # Sağa: panel daralır (tuş hâlâ basılı, tek sürükleme).
            glide(target_x - 90, target_x + 20, target_y)
            narrowed = panel.width()

            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
            button_down = False
            app.processEvents()
        finally:
            if button_down:
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
            # Kullanıcının imleci her koşulda eski yerine döner.
            user32.SetCursorPos(original.x, original.y)
            app.processEvents()

        restored = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(restored))
        cursor_restored = (abs(restored.x - original.x) <= 2
                           and abs(restored.y - original.y) <= 2)

        capture("separator-drag")
        mark("MARK_SEPARATOR_DRAG",
             f"mode=native_win32 before={before} widened={widened} "
             f"narrowed={narrowed} visible={panel.isVisible()} "
             f"cursor_restored={cursor_restored} "
             f"cursor=({original.x},{original.y})->({restored.x},{restored.y})")
        if widened <= before:
            failures.append(f"SEPARATOR_LEFT_DRAG_FAILED {before}->{widened}")
        if narrowed >= widened:
            failures.append(f"SEPARATOR_RIGHT_DRAG_FAILED {widened}->{narrowed}")
        if not panel.isVisible():
            failures.append("SEPARATOR_DRAG_HID_PANEL")
        if not cursor_restored:
            failures.append("SEPARATOR_CURSOR_NOT_RESTORED")
        check_no_overlap("after_separator_drag")

    @step
    def capture_moved():
        player.move(player.x() + 120, player.y() + 80)
        player.resize(1240, 760)
        app.processEvents()
        player.video_frame.update_playlist_panel_geometry()
        app.processEvents()
        capture("moved-resized")
        check_no_overlap("moved_resized")

    @step
    def finish():
        evaluate(own_pid)
        print("RESULTS: " + " ".join(
            f"{key}={value}" for key, value in (
                ("failures", ",".join(failures) or "none"),
                ("active_overlap", samples.get("active", {}).get(
                    "playlist_video_overlap")),
                ("returned_overlap", samples.get("returned", {}).get(
                    "playlist_video_overlap")),
                ("inactive_overlay_visible", samples.get("inactive", {}).get(
                    "overlay", {}).get("native_visible")),
                ("inactive_osd_visible", samples.get("inactive", {}).get(
                    "osd", {}).get("native_visible")),
                ("inactive_playlist_visible", samples.get("inactive", {}).get(
                    "playlist", {}).get("native_visible")),
                ("playlist_open_after_return", samples.get("returned", {}).get(
                    "playlist_open")),
            )), flush=True)
        for phase, data in samples.items():
            if data.get("shot"):
                print(f"SHOT {phase} {data['shot']}", flush=True)
        try:
            player.mpv_player.stop()
            mark("MARK_STOP")
            player.mpv_player.terminate()
            mark("MARK_TERMINATE")
        except Exception as exc:
            print(f"TEARDOWN_WARNING {exc}", flush=True)
        player.close()
        mark("MARK_CLOSE")
        app.exit(1 if failures else 0)

    # NOT: Sabit gecikmeler, bloklayan open_path yüzünden adımları sırasız
    # tetikliyordu. Her adım bir sonrakini kendisi planlar; sıra garanti.
    gaps = {"hand_off": FOCUS_CHILD_MS // 2,
            "sample_inactive": 900,
            "return_focus": FOCUS_CHILD_MS,
            "sample_returned": 900}

    def run_chain(index=0):
        if index >= len(steps):
            return
        fn = steps[index]
        fn()
        QTimer.singleShot(gaps.get(fn.__name__, 400),
                          lambda: run_chain(index + 1))

    QTimer.singleShot(1200, run_chain)

    code = app.exec()
    mark("MARK_DONE", f"exit={code}")
    return code


try:
    EXIT_CODE = main()
finally:
    # Yalnızca kaydedilen kesin PID temizlenir; geniş süreç taraması yapılmaz.
    if focus_child is not None and focus_child.poll() is None:
        try:
            focus_child.terminate()
            focus_child.wait(timeout=5)
        except Exception:
            try:
                focus_child.kill()
            except Exception:
                pass
        print(f"FOCUS_CHILD_CLEANED pid={focus_child.pid}", flush=True)

raise SystemExit(EXIT_CODE)
