# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kalıcı, opt-in native Windows overlay smoke child.

Bu script raporlanan native crash akışını birebir yeniden üretmek içindir.
Normal pytest paketine dahil değildir (dosya adı ``test_`` ile başlamaz) ve
``MLC_NATIVE_SMOKE=1`` verilmeden hiçbir Qt penceresi veya native MPV örneği
oluşturmaz.

Ortam değişkenleri
------------------
MLC_NATIVE_SMOKE          "1" olmalı; aksi halde script SKIPPED ile çıkar.
MLC_FOREGROUND_ATTEMPTS   Foreground önkoşulu için bounded retry sayısı (12).
MLC_FOREGROUND_RETRY_MS   Denemeler arası bekleme (120 ms).
MLC_NATIVE_TEST_VIDEO     Opsiyonel video yolu. Verilmezse videosuz mod.
MLC_NATIVE_FOCUS_HANDOFF  "1" ise gerçek ayrı Qt süreciyle foreground devri.
MLC_NATIVE_SYNTHETIC      "1" ise devir gerçek foreground yerine sentetik
                          QApplication.setActiveWindow()/QEvent gönderimiyle
                          yapılır. Bu yalnızca karşılaştırma içindir; gerçek
                          Windows aktivasyonu gibi sunulmamalıdır.
MLC_NATIVE_VARIANT        İzolasyon varyantı (bkz. VARIANTS). Varsayılan "none".
MLC_NATIVE_IDLE_MS        Video açmadan önce boşta bekleme (varsayılan 5000).
MLC_NATIVE_PLAY_MS        Video açıldıktan sonra oynatma süresi (varsayılan 4000).
MLC_FOCUS_CHILD_MS        Odak penceresinin yaşam süresi (varsayılan 2500).
MLC_NATIVE_SETTINGS       QSettings INI dizini (gerçek HKCU kullanılmaz).
MLC_NATIVE_PROJECT_ROOT   Proje kökü (baseline worktree karşılaştırması için).

Marker akışı
------------
MARK_PLAYER_CREATED, MARK_SHOWN, MARK_PLAY, MARK_OVERLAY_VISIBLE,
MARK_FOCUS_CHILD_STARTED, MARK_DEACTIVATED, MARK_ACTIVE_READ, MARK_BUTTONS,
RESULTS, MARK_STOP, MARK_TERMINATE, MARK_CLOSE, MARK_DONE

Her marker flush=True ile yazılır; böylece native crash anında son başarılı
aşama kesin olarak bilinir.
"""
import os
import subprocess
import sys
import time
import ctypes

# --- 1. Opt-in güvenliği: bu noktadan önce Qt/mpv/pencere oluşturulmaz. ---
if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    print("Bu native smoke yalnizca MLC_NATIVE_SMOKE=1 ile calisir.", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import Qt, QEvent, QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from app.player import MPVPlayer  # noqa: E402

VARIANTS = (
    "none",
    "no_stay_on_top",
    "no_tool",
    "no_owner",
    "no_translucent",
    "no_show_without_activating",
    "accepts_focus",
    "no_event_filter",
    "empty_content",
)

VARIANT = os.environ.get("MLC_NATIVE_VARIANT", "none")
if VARIANT not in VARIANTS:
    print(f"SKIPPED: UNKNOWN_VARIANT {VARIANT}", flush=True)
    raise SystemExit(2)

VIDEO_PATH = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
FOCUS_HANDOFF = os.environ.get("MLC_NATIVE_FOCUS_HANDOFF") == "1"
SYNTHETIC = os.environ.get("MLC_NATIVE_SYNTHETIC") == "1"
IDLE_MS = int(os.environ.get("MLC_NATIVE_IDLE_MS", "5000"))
PLAY_MS = int(os.environ.get("MLC_NATIVE_PLAY_MS", "4000"))
FOCUS_CHILD_MS = int(os.environ.get("MLC_FOCUS_CHILD_MS", "2500"))

START = time.time()
focus_child = None


def _excepthook(exc_type, exc_value, exc_tb):
    """Python istisnalarını native crash'ten kesin olarak ayırır.

    PyQt6, bir slot içindeki yakalanmamış Python istisnasında varsayılan olarak
    abort() çağırır; Windows bunu 0xC0000409 (STATUS_STACK_BUFFER_OVERRUN) ile
    raporlar. Bu, gerçek bir native bellek hatasıyla birebir aynı görünür.
    Aşağıdaki hook, böyle bir durumu PYTHON_EXCEPTION olarak işaretler.
    """
    import traceback
    print("PYTHON_EXCEPTION " + "".join(
        traceback.format_exception(exc_type, exc_value, exc_tb)).strip(), flush=True)
    sys.stderr.flush()
    # Aksi halde event loop hiçbir adım planlanmadan sonsuza kadar döner.
    # Ayrı bir çıkış kodu, harness hatasını native crash'ten ayırır.
    app_instance = QApplication.instance()
    if app_instance is not None:
        app_instance.exit(90)


# MLC_NATIVE_NO_EXCEPTHOOK=1 ile PyQt6'nın varsayılan davranışı (abort) korunur;
# bu, "sahte native crash" mekanizmasını göstermek için kullanılır.
if os.environ.get("MLC_NATIVE_NO_EXCEPTHOOK") != "1":
    sys.excepthook = _excepthook


def mark(name, extra=""):
    elapsed = time.time() - START
    suffix = f" {extra}" if extra else ""
    print(f"{name} t={elapsed:.2f}{suffix}", flush=True)


def apply_variant(player):
    """İzolasyon varyantını yalnızca test tarafında, ürün koduna dokunmadan uygular.

    Her varyant üründeki overlay'e göre tek bir fark içerir.
    """
    frame = player.video_frame
    overlay = frame.control_overlay
    if overlay is None or VARIANT == "none":
        return

    base_flags = (
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
    )
    owner = player

    if VARIANT == "no_stay_on_top":
        overlay.setParent(owner, base_flags & ~Qt.WindowType.WindowStaysOnTopHint)
    elif VARIANT == "no_tool":
        overlay.setParent(
            owner,
            (base_flags & ~Qt.WindowType.Tool) | Qt.WindowType.Window,
        )
    elif VARIANT == "no_owner":
        overlay.setParent(None, base_flags)
    elif VARIANT == "no_translucent":
        overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    elif VARIANT == "no_show_without_activating":
        overlay.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
    elif VARIANT == "accepts_focus":
        overlay.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
    elif VARIANT == "no_event_filter":
        player.removeEventFilter(frame)
        frame.removeEventFilter(frame)
    elif VARIANT == "empty_content":
        # Ürün overlay'i canlı tutulur (widget referansları geçerli kalsın diye)
        # ama gösterilmez; video üzerinde yalnızca içeriksiz bir QWidget durur.
        overlay.hide()
        globals()["_retained_product_overlay"] = overlay
        empty = QWidget(owner, base_flags)
        empty.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        empty.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        empty.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)
        empty.setStyleSheet("background: rgba(18, 24, 30, 225);")
        empty.setFixedHeight(44)
        frame.control_overlay = empty

    print(f"VARIANT_APPLIED {VARIANT}", flush=True)


synthetic_window = None


def start_synthetic_activation():
    """Aynı süreç içinde sentetik aktivasyon devri.

    UYARI: Bu gerçek Windows foreground değişimi DEĞİLDİR. Yalnızca eski
    harness davranışıyla karşılaştırma amacıyla vardır.
    """
    global synthetic_window
    synthetic_window = QWidget()
    synthetic_window.setWindowTitle("MLC Synthetic Activation Window")
    synthetic_window.setGeometry(80, 80, 400, 240)
    synthetic_window.show()
    QApplication.setActiveWindow(synthetic_window)
    app.sendEvent(player, QEvent(QEvent.Type.WindowDeactivate))
    app.sendEvent(player.video_frame, QEvent(QEvent.Type.WindowDeactivate))
    mark("MARK_FOCUS_CHILD_STARTED", "mode=SYNTHETIC pid=self")


def start_focus_child():
    """Gerçek, ayrı Qt top-level süreci başlatır (sentetik QEvent değil)."""
    global focus_child
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "native_focus_child.py")
    env = dict(os.environ)
    env["MLC_NATIVE_SMOKE"] = "1"
    env["MLC_FOCUS_CHILD_MS"] = str(FOCUS_CHILD_MS)
    # NOT: Burada eskiden MLCPLAYER_CLASSIC_UI=1 veriliyordu. Odak child'ı
    # zaten sade bir QWidget'tir ve MPVPlayer oluşturmaz; bayrağın tek etkisi
    # legacy klasik kabuğu miras olarak taşımaktı. Kaldırıldı.
    env.pop("MLCPLAYER_CLASSIC_UI", None)
    focus_child = subprocess.Popen([sys.executable, script], env=env)
    if os.name == "nt":
        try:
            # Foreground süreç olan player, yalnız kendi başlattığı child'a
            # foreground alma izni verir. Başka hiçbir PID hedeflenmez.
            ctypes.windll.user32.AllowSetForegroundWindow(focus_child.pid)
        except Exception:
            pass
    mark("MARK_FOCUS_CHILD_STARTED", f"pid={focus_child.pid}")


def kill_focus_child():
    """Yalnızca bu testin başlattığı PID'i kesin olarak temizler."""
    global focus_child
    if focus_child is None:
        print("FOCUS_CHILD_CHECK=NONE", flush=True)
        return
    try:
        if focus_child.poll() is None:
            focus_child.terminate()
            try:
                focus_child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                focus_child.kill()
                focus_child.wait(timeout=5)
        print(f"FOCUS_CHILD_CHECK=CLEANED pid={focus_child.pid} rc={focus_child.returncode}",
              flush=True)
    except Exception as exc:  # pragma: no cover - tanılama scripti
        print(f"FOCUS_CHILD_CHECK=ERROR {exc}", flush=True)
    finally:
        focus_child = None


def active_window_name():
    active = QApplication.activeWindow()
    if active is None:
        return "None"
    return f"{type(active).__name__}:{active.windowTitle() or active.objectName()}"


def native_foreground_pid():
    """Windows foreground HWND'sinin süreç kimliğini döndürür."""
    if os.name != "nt":
        return None
    try:
        hwnd = native_foreground_hwnd()
        pid = ctypes.c_ulong(0)
        if hwnd:
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return None


def native_foreground_hwnd():
    """Foreground HWND'i int olarak dondurur; foreground yoksa 0.

    URUN `app/video_frame.py` `GetForegroundWindow.restype` degerini
    pointer-safe `wintypes.HWND` yapar ve `ctypes.windll.user32` surec
    genelinde TEK nesnedir; NULL HWND Python'da `None` doner.
    """
    if os.name != "nt":
        return None
    try:
        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except Exception:
        return None


def activate_player_native():
    """Qt isteğini native foreground çağrısıyla güçlendirir."""
    player.raise_()
    player.activateWindow()
    if os.name == "nt":
        user32 = ctypes.windll.user32
        hwnd = int(player.winId())
        foreground = native_foreground_hwnd() or 0
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


# Foreground önkoşulu için sınırlı deneme bütçesi (periyodik timer DEĞİL;
# yalnızca ölçüm anında çalışan bounded retry).
FOREGROUND_ATTEMPTS = int(os.environ.get("MLC_FOREGROUND_ATTEMPTS", "12"))
FOREGROUND_RETRY_MS = int(os.environ.get("MLC_FOREGROUND_RETRY_MS", "120"))


def pump(milliseconds):
    """Event loop'u bloklamadan kısa ve sınırlı süre işletir."""
    deadline = time.time() + milliseconds / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def ensure_player_foreground(tag):
    """Player'ı GERÇEK Windows foreground penceresi yapar ve PID ile doğrular.

    Ölçüm önkoşuludur: player foreground değilken ürünün fail-closed kuralı
    overlay'i haklı olarak gizli tutar. Bu durumu ürün hatası gibi raporlamak
    yanlış olur; bu yüzden önkoşul ayrı ölçülür.

    Bounded retry kullanır; sonsuz döngü veya periyodik timer yoktur.
    """
    if os.name != "nt":
        return True, None
    own_pid = os.getpid()
    foreground_pid = None
    for attempt in range(1, FOREGROUND_ATTEMPTS + 1):
        activate_player_native()
        pump(FOREGROUND_RETRY_MS)
        foreground_pid = native_foreground_pid()
        if foreground_pid == own_pid:
            print(f"FOREGROUND_OK {tag} attempt={attempt} pid={foreground_pid} "
                  f"hwnd={native_foreground_hwnd()}", flush=True)
            return True, foreground_pid
    print(f"FOREGROUND_FAILED {tag} attempts={FOREGROUND_ATTEMPTS} "
          f"foreground_pid={foreground_pid} own_pid={own_pid} "
          f"hwnd={native_foreground_hwnd()}", flush=True)
    return False, foreground_pid


def confirm_focus_child_foreground():
    """Odak child'ının GERÇEKTEN foreground olduğunu PID/HWND ile doğrular."""
    if SYNTHETIC:
        return True, None
    if focus_child is None:
        return False, None
    foreground_pid = None
    for attempt in range(1, FOREGROUND_ATTEMPTS + 1):
        foreground_pid = native_foreground_pid()
        if foreground_pid == focus_child.pid:
            print(f"FOCUS_CHILD_CONFIRMED attempt={attempt} "
                  f"pid={foreground_pid} hwnd={native_foreground_hwnd()}",
                  flush=True)
            return True, foreground_pid
        pump(FOREGROUND_RETRY_MS)
    print(f"FOCUS_CHILD_NOT_FOREGROUND attempts={FOREGROUND_ATTEMPTS} "
          f"foreground_pid={foreground_pid} child_pid={focus_child.pid}",
          flush=True)
    return False, foreground_pid


# --- Qt başlatma ---
app = QApplication(sys.argv)
# Kapanış markerları (MARK_CLOSE/MARK_DONE) çalışabilsin diye son pencere
# kapandığında event loop otomatik sonlanmamalı.
app.setQuitOnLastWindowClosed(False)
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
settings_dir = os.environ.get(
    "MLC_NATIVE_SETTINGS",
    os.path.join(os.environ.get("TEMP", PROJECT_ROOT), "MLCPlayer-native-smoke"),
)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_dir)

player = MPVPlayer()
# NOT: Etiket ENV'den DEĞİL, gerçek ürün durumundan üretilir. Legacy anahtar
# verilse bile ürün sinematik açıldığı için rapor da ui=cinematic olmalıdır.
ACTUAL_UI = ("cinematic" if getattr(player, "cinematic_ui_enabled", True)
             else "classic")
mark("MARK_PLAYER_CREATED", f"ui={ACTUAL_UI} variant={VARIANT}")
apply_variant(player)

player.show()
player.raise_()
player.activateWindow()
mark("MARK_SHOWN")

results = {
    "ui": ACTUAL_UI,
    "variant": VARIANT,
    "video": bool(VIDEO_PATH),
    "focus_handoff": FOCUS_HANDOFF,
}


# --- Aşama zinciri: her adım QTimer ile sıralanır, event loop canlı kalır. ---
def step_open_video():
    if VIDEO_PATH and os.path.isfile(VIDEO_PATH):
        player.open_path(VIDEO_PATH)
        mark("MARK_PLAY", "video=<test-video>")
        QTimer.singleShot(PLAY_MS, step_overlay_visible)
    else:
        print("SKIP_PLAY no-video", flush=True)
        QTimer.singleShot(500, step_overlay_visible)


def step_overlay_visible():
    # ÖNKOŞUL: ilk görünürlük ölçümünden ÖNCE player gerçek foreground olmalı.
    # Aksi halde ürünün (doğru) fail-closed kuralı overlay'i gizli tutar ve
    # bu, ürün hatası gibi görünür.
    ok, foreground_pid = ensure_player_foreground("before_overlay_measure")
    results["foreground_precondition"] = ok
    results["foreground_pid_before_measure"] = foreground_pid
    if ok:
        # Aktivasyon olaylarının işlenmesi için kısa, sınırlı süre.
        pump(250)

    overlay = player.video_frame.control_overlay
    if overlay is None:
        mark("MARK_OVERLAY_VISIBLE", "overlay=NONE")
    else:
        mark("MARK_OVERLAY_VISIBLE",
             f"visible={overlay.isVisible()} "
             f"foreground_ok={ok} foreground_pid={foreground_pid} "
             f"geo={overlay.geometry().getRect()}")
    results["overlay_visible"] = overlay is not None and overlay.isVisible()
    if FOCUS_HANDOFF:
        if SYNTHETIC:
            start_synthetic_activation()
        else:
            start_focus_child()
        QTimer.singleShot(1500, step_deactivated)
    else:
        print("SKIP_FOCUS_HANDOFF", flush=True)
        QTimer.singleShot(300, step_buttons)


def step_deactivated():
    overlay = player.video_frame.control_overlay
    # Child'ın gerçekten foreground olduğunu bounded retry ile doğrula.
    focus_confirmed, foreground_pid = confirm_focus_child_foreground()
    if foreground_pid is None:
        foreground_pid = native_foreground_pid()
    mark("MARK_DEACTIVATED",
         f"active={active_window_name()} "
         f"foreground_pid={foreground_pid} "
         f"focus_confirmed={focus_confirmed} "
         f"overlay_visible={None if overlay is None else overlay.isVisible()}")
    results["focus_foreground_confirmed"] = focus_confirmed
    results["overlay_hidden_on_deactivate"] = (
        overlay is None or not overlay.isVisible())
    # Odak penceresi kendi ömrü bitince kapanır; ardından foreground'u geri al.
    QTimer.singleShot(max(400, FOCUS_CHILD_MS - 1200), step_return_focus)


def step_return_focus():
    if SYNTHETIC and synthetic_window is not None:
        synthetic_window.close()
        QApplication.setActiveWindow(player)
        app.sendEvent(player, QEvent(QEvent.Type.WindowActivate))
        app.sendEvent(player.video_frame, QEvent(QEvent.Type.WindowActivate))
    # Child kapandıktan sonra foreground AÇIKÇA geri alınır ve doğrulanır.
    ok, foreground_pid = ensure_player_foreground("after_focus_child")
    results["foreground_regained_after_return"] = ok
    results["foreground_pid_after_return"] = foreground_pid
    if player.video_frame.is_video_fullscreen:
        player.video_frame.raise_()
        player.video_frame.activateWindow()
    if ok:
        # Gerçek foreground geri alındıktan sonra WindowActivate ve event
        # loop işlerine KISA ve SINIRLI süre tanınır.
        pump(400)
    QTimer.singleShot(600, step_active_read)


def step_active_read():
    overlay = player.video_frame.control_overlay
    foreground_pid = native_foreground_pid()
    own = os.getpid()
    # Player PID foreground DEĞİLKEN overlay_visible_after_return
    # değerlendirilmez; aksi halde harness eksikliği ürün hatası gibi görünür.
    evaluated = (foreground_pid == own)
    mark("MARK_ACTIVE_READ",
         f"active={active_window_name()} "
         f"foreground_pid={foreground_pid} own_pid={own} "
         f"evaluated={evaluated} "
         f"overlay_visible={None if overlay is None else overlay.isVisible()} "
         f"geo={None if overlay is None else overlay.geometry().getRect()}")
    results["overlay_return_evaluated"] = evaluated
    if evaluated:
        results["overlay_visible_after_return"] = (
            overlay is not None and overlay.isVisible())
    else:
        results["overlay_visible_after_return"] = None
    QTimer.singleShot(400, step_buttons)


def step_buttons():
    frame = player.video_frame
    overlay = frame.control_overlay

    if os.environ.get("MLC_NATIVE_FORCE_PYEXC") == "1":
        # Kontrollü gösterim: bir Qt slot'u içindeki yakalanmamış Python
        # istisnası PyQt6 tarafından abort()'a çevrilir ve süreç 0xC0000409
        # ile ölür. Bu, gerçek bir native bellek hatasından ayırt edilemez
        # göründüğü için teşhiste ilk elenmesi gereken olasılıktır.
        print("FORCING_PYTHON_EXCEPTION_IN_SLOT", flush=True)
        frame.this_attribute_does_not_exist_in_this_build
    if overlay is None or VARIANT == "empty_content":
        mark("MARK_BUTTONS", "buttons=NONE")
        results["buttons"] = None
        QTimer.singleShot(400, step_results)
        return

    # NOT: Overlay widget referansları sürümler arasında değişebilir. Baseline
    # ile güncel ağacı aynı harness'le karşılaştırabilmek için öznitelikler
    # getattr ile okunur; eksik öznitelik harness hatasıdır, ürün crash'i değil.
    button = getattr(frame, "overlay_play_pause_button", None)
    timeline = getattr(frame, "overlay_timeline", None)
    current_label = getattr(frame, "overlay_current_time_label", None)
    total_label = getattr(frame, "overlay_total_time_label", None)

    if button is None:
        mark("MARK_BUTTONS", "buttons=NO_NAMED_PLAY_BUTTON(baseline-overlay)")
        results["buttons"] = "unavailable"
    else:
        before = button.text()
        # NOT: Dosya yüklü değilken ürünün play_pause() akışı modal bir dosya
        # gezgini açar. Bu, otomatik harness'i kullanıcı etkileşimine bağlar;
        # bu nedenle tıklama yalnızca gerçekten yüklü medya varken yapılır.
        if player.current_file:
            button.click()
            app.processEvents()
        else:
            print("SKIP_BUTTON_CLICK no-file", flush=True)
        after = button.text()
        mark("MARK_BUTTONS",
             f"play_text_before={before} play_text_after={after} "
             f"timeline={None if timeline is None else timeline.value()} "
             f"current={None if current_label is None else current_label.text()} "
             f"total={None if total_label is None else total_label.text()}")
        results["buttons"] = f"{before}->{after}"
    QTimer.singleShot(400, step_results)


def step_results():
    # Gerçek oynatma KANITI: matris, adı "video" olan senaryonun gerçekten
    # video açtığını bu alanlardan doğrular (bkz. requires_video).
    duration = time_pos = None
    try:
        mpv = player.mpv_player
        duration = mpv.duration
        time_pos = mpv.time_pos
    except Exception as exc:
        print(f"PLAYBACK_READ_FAILED {exc}", flush=True)
    results["playback_duration"] = 0 if duration is None else round(
        float(duration), 3)
    results["playback_time_pos"] = 0 if time_pos is None else round(
        float(time_pos), 3)
    mark("MARK_PLAYBACK_EVIDENCE",
         f"duration={results['playback_duration']} "
         f"time_pos={results['playback_time_pos']}")
    print("RESULTS: " + " ".join(f"{k}={v}" for k, v in results.items()), flush=True)
    QTimer.singleShot(200, step_shutdown)


def step_shutdown():
    # MPV'yi burada elle stop/terminate etmek ürünün timer, observer ve yüzen
    # yüzey temizliğini atlıyordu. Gerçek videolu Windows koşumunda timer 300
    # ms daha `mpv_player=None` durumunu okuyup child kapanışını 0xC0000005 ile
    # bitirdi. Tek kapanış sahibi ürünün senkron `closeEvent` yoludur.
    player.close()
    mark("MARK_STOP")
    mark("MARK_TERMINATE")
    mark("MARK_CLOSE")
    QTimer.singleShot(300, step_done)


def step_done():
    mark("MARK_DONE")
    app.quit()


QTimer.singleShot(IDLE_MS, step_open_video)

try:
    exit_code = app.exec()
finally:
    kill_focus_child()

# exit_code 90: harness tarafında yakalanmamış Python istisnası (ürün crash'i değil).
raise SystemExit(exit_code)
