"""Kalıcı, opt-in native Windows overlay smoke child.

Bu script raporlanan native crash akışını birebir yeniden üretmek içindir.
Normal pytest paketine dahil değildir (dosya adı ``test_`` ile başlamaz) ve
``MLC_NATIVE_SMOKE=1`` verilmeden hiçbir Qt penceresi veya native MPV örneği
oluşturmaz.

Ortam değişkenleri
------------------
MLC_NATIVE_SMOKE          "1" olmalı; aksi halde script SKIPPED ile çıkar.
MLCPLAYER_OVERLAY_PREVIEW "1" overlay preview açık, "0" kapalı.
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
os.environ.setdefault("MLCPLAYER_OVERLAY_PREVIEW", "1")

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
    env.pop("MLCPLAYER_OVERLAY_PREVIEW", None)
    focus_child = subprocess.Popen([sys.executable, script], env=env)
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
mark("MARK_PLAYER_CREATED",
     f"preview={os.environ.get('MLCPLAYER_OVERLAY_PREVIEW')} variant={VARIANT}")
apply_variant(player)

player.show()
player.raise_()
player.activateWindow()
mark("MARK_SHOWN")

results = {
    "preview": os.environ.get("MLCPLAYER_OVERLAY_PREVIEW"),
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
    overlay = player.video_frame.control_overlay
    if overlay is None:
        mark("MARK_OVERLAY_VISIBLE", "overlay=NONE(preview-off)")
    else:
        mark("MARK_OVERLAY_VISIBLE",
             f"visible={overlay.isVisible()} geo={overlay.geometry().getRect()}")
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
    mark("MARK_DEACTIVATED",
         f"active={active_window_name()} "
         f"overlay_visible={None if overlay is None else overlay.isVisible()}")
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
    player.raise_()
    player.activateWindow()
    if player.video_frame.is_video_fullscreen:
        player.video_frame.raise_()
        player.video_frame.activateWindow()
    QTimer.singleShot(1200, step_active_read)


def step_active_read():
    overlay = player.video_frame.control_overlay
    mark("MARK_ACTIVE_READ",
         f"active={active_window_name()} "
         f"overlay_visible={None if overlay is None else overlay.isVisible()} "
         f"geo={None if overlay is None else overlay.geometry().getRect()}")
    results["overlay_visible_after_return"] = (
        overlay is not None and overlay.isVisible())
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
    print("RESULTS: " + " ".join(f"{k}={v}" for k, v in results.items()), flush=True)
    QTimer.singleShot(200, step_shutdown)


def step_shutdown():
    if player.mpv_player is not None:
        player.mpv_player.stop()
    mark("MARK_STOP")
    try:
        if player.mpv_player is not None:
            player.mpv_player.terminate()
            player.mpv_player = None
        mark("MARK_TERMINATE")
    except Exception as exc:
        print(f"TERMINATE_ERROR {exc}", flush=True)
    QTimer.singleShot(300, step_close)


def step_close():
    player.close()
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
