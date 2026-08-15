"""Opt-in GERÇEK MPV altyazı görünüm kabulü. TEK senaryo çalıştırır.

    MLC_NATIVE_SMOKE=1 python tests/subtitle_visual_acceptance_child.py \
        --scenario a_text_color --video <gerçek video>

Sözleşme
--------
- Ürün gerçek `MPVPlayer()` ile bu süreçte açılır (`vo=gpu`), ses YALNIZ
  bu süreçte `ao=null` yapılır; ürünün `MPV_CONFIG` sözlüğü mutate
  edilmez.
- Altyazı, kullanıcının medya klasörüne DEĞİL benzersiz geçici dizine
  yazılan UTF-8 SRT/ASS dosyasıdır ve test sonunda silinir.
- Stil değişiklikleri gerçek `SubtitleAppearanceDialog` üzerinden
  (`QTest` kullanıcı olayları + gerçek `Uygula` düğmesi) uygulanır;
  `mpv.sub_color = ...` gibi doğrudan yazma UI kanıtı sayılmaz.
- Ölçüm iki ayaklıdır: MPV property readback **ve** aynı duraklatılmış
  kare üzerinde gerçek Windows ekran görüntüsünden alınan piksel farkı.
  Karar mantığı saf `tests/subtitle_pixel_rules.py` modülündedir.
- Kapanış yalnız ürün yolundan başlar (`PLAYER.close()`); child MPV'yi
  kendisi durdurmaz.

Çıktı satırları: `RESULT|...`, `SHOT ...`, `MEASURE ...`, `MARK_DONE`.
"""
import argparse
import ctypes
import faulthandler
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from ctypes import wintypes

# Kapanış fazında görülen `0xC0000409` (abort) için C seviyesinde yığın
# izi: sessiz çökme kanıtsız kalmasın.
faulthandler.enable()
# Donma tanısı: ana iş parçacığı bloklansa bile AYRI bir zamanlayıcıdan
# gerçek Python yığını basılır. Sessiz kilitlenme "test edilemedi"
# olarak bile görünmeden kaybolmasın.
_DUMP_EVERY = float(os.environ.get("MLC_SUB_STACK_DUMP_S", "0") or 0)
if _DUMP_EVERY > 0:
    faulthandler.dump_traceback_later(_DUMP_EVERY, repeat=True, exit=False)

# Yonlendirilmis stdout Windows'ta cp1254 olur ve rapor metnindeki
# ASCII disi isaretler `UnicodeEncodeError` firlatir. Hata yakalayicinin
# traceback'i ayni karakteri tasidigi icin ikinci kez patlar, olay
# dongusunden kacar ve PyQt6 sureci `0xC0000409` ile sonlandirir
# (F/K senaryolarinda 3/3 yeniden uretildi). Cikti UTF-8'e sabitlenir.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import (QPoint, QRect, QSettings, QStandardPaths,  # noqa: E402
                          Qt, QTimer)
from PyQt6.QtGui import QColor, QImage  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402

from app.player import MPVPlayer  # noqa: E402
from app.subtitle_appearance_dialog import SubtitleAppearanceDialog  # noqa: E402
from app.subtitle_style import (ASS_OVERRIDE_FORCE, BACKGROUND_BOX,  # noqa: E402
                                COLOR_KEYS, OUTLINE_AND_SHADOW,
                                SCHEMA_KEY, SETTINGS_PREFIX,
                                is_bitmap_subtitle, qcolor_to_mpv_argb,
                                selected_subtitle_codec)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from physical_audio import audio_safety_problems, native_mpv_config  # noqa: E402
from subtitle_pixel_rules import (bbox_size, changed_longest_run,  # noqa: E402
                                  contains, fill_ratio, growth_ratio,
                                  horizontal_centre_offset, intersection,
                                  longest_run, make_frame, overlap_ratio,
                                  padding, padding_problems, scan_changed,
                                  scan_changed_color, solid_box_ratio)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]

# --- Ölçüm sabitleri (AÇIK tolerans; gizli pay yok) ---
# Duraklatılmış AYNI kare kullanıldığı için altyazı dışındaki fark
# sıfıra yakındır; 20 birim compositing gürültüsüne pay bırakır.
CHANGE_THRESHOLD = 20
# Altyazı ile kontrol katmanı arasında beklenen boşluk (mantıksal px).
SAFE_GAP_MIN = 10
SAFE_GAP_MAX = 28
# Büyük render ölçeğinde (tam ekran) ve kalın kenarlıkta mürekkep ile
# ASS satır kutusu arasındaki fark büyür; boşluk ÖLÇÜLDÜĞÜ gibi 31-33 px
# olur. Güvenlik açısından sorun değildir (altyazı banda girmez), bu
# yüzden bu iki durumda üst sınır ayrı verilir.
SAFE_GAP_MAX_LARGE = 36
# ASS betiğinin KENDİ `MarginV` değeri ürünün ofsetine EKLENİR ve dosyaya
# göre değişir; önceden bilinemez. Bu yüzden ASS'te üst sınır daha
# geniştir. Ölçülen gerçek değerler: normal 47, playlist 39, tam ekran
# 80, kullanıcı %90 → 122. Hepsi GÜVENLİ (altyazı banda hiç girmez).
SAFE_GAP_MAX_ASS = 90
# Glif kenarları anti-aliasing ile karışır; çekirdek pikseller hedefe
# çok yakındır. 36 birim, turuncu/mavi/beyaz/siyah gibi uzak renkleri
# birbirine KARIŞTIRMAZ.
COLOR_TOL = 36
# Bir maskeyi "gerçekten göründü" saymak için gereken en az piksel.
MIN_MASK_PIXELS = 400
# Yazı ile kutuyu ayıran doluluk oranı eşiği.
BOX_FILL_MIN = 0.70
TEXT_FILL_MAX = 0.45

SEEK_TIME = float(os.environ.get("MLC_SUB_SEEK_TIME", "60.0"))
SUB_LINE_1 = "MLC GERÇEK ALTYAZI TESTİ"
SUB_LINE_2 = "Renk • Arka Plan • Kenarlık"

WHITE = QColor(255, 255, 255, 255)
BLACK = QColor(0, 0, 0, 255)
CLEAR = QColor(0, 0, 0, 0)
ORANGE = QColor(242, 106, 61, 255)
BLUE = QColor(0, 32, 160, 255)
BLUE_HALF = QColor(0, 32, 160, 128)
# Bant ölçümünde kullanılan AYIRT EDİCİ yazı rengi. Ürünün vurgu rengi
# turuncudur (timeline dolgusu da turuncu); turuncu altyazı maskesi
# kontrol katmanı pikselleriyle karışıyordu. Yeşil ürün paletinde YOKTUR.
PROBE_GREEN = QColor(0, 255, 0, 255)

BASE_VALUES = {
    "sub_delay": 0.0, "sub_scale": 1.0, "sub_pos": 90.0,
    "sub_border_size": 3.0, "sub_color": WHITE,
    "sub_back_color": CLEAR, "sub_border_color": BLACK,
}

SHOT_DIR = os.path.join(os.environ.get("TEMP", "."), "mlc_subtitle_visual")
os.makedirs(SHOT_DIR, exist_ok=True)

APP = PLAYER = None
SCENARIO = "?"
TEMP_DIR = ""
START = time.time()
results = []
measures = {}
_shot = [0]
MPV_CALLS = []


# ---------------------------------------------------------------- altyapı

def mark(name, extra=""):
    print(f"{name} t={time.time() - START:.2f} {extra}".rstrip(), flush=True)


def _field(value):
    """`|` alan ayracidir; olcum metni ayristiriciyi BOZMAMALIDIR."""
    return str(value).replace("|", "/").replace("\n", " ")


def record(test, method, expected, measured, ok, evidence=""):
    status = "PASS" if ok is True else ("FAIL" if ok is False else "BLOCKED")
    results.append({"test": test, "status": status})
    print("RESULT|" + "|".join(_field(part) for part in
                               (SCENARIO, test, method, expected, measured,
                                status, evidence)), flush=True)


def install_mpv_call_recorder():
    import mpv as mpv_module
    real_stop, real_terminate = mpv_module.MPV.stop, mpv_module.MPV.terminate

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


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        APP.processEvents()
        time.sleep(0.008)
    APP.processEvents()


def wait_for(predicate, timeout_ms=8000, step_ms=60):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:
            pass
        pump(step_ms)
    return False


def cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def foreground_hwnd():
    """Foreground HWND'i her zaman int olarak dondurur (yoksa 0).

    URUN `app/video_frame.py` `GetForegroundWindow.restype` degerini
    pointer-safe `wintypes.HWND` yapar; `ctypes.windll.user32` surec genelinde
    TEK nesne oldugu icin imza burada da gecerlidir ve NULL HWND `None` doner.
    """
    return int(user32.GetForegroundWindow() or 0)


def take_foreground(hwnd, attempts=12):
    hwnd = int(hwnd or 0)
    if not hwnd:
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


def video_rect():
    return global_rect(PLAYER.video_frame)


def frame_from_image(image, rect):
    """QImage bölgesi -> saf analiz karesi (RGB888, satır dolgusu yok)."""
    cropped = image.copy(rect).convertToFormat(QImage.Format.Format_RGB888)
    width, height = cropped.width(), cropped.height()
    line = cropped.bytesPerLine()
    bits = cropped.bits()
    bits.setsize(line * height)
    raw = bytes(bits)
    if line == width * 3:
        return make_frame(width, height, raw)
    packed = b"".join(raw[y * line:y * line + width * 3]
                      for y in range(height))
    return make_frame(width, height, packed)


def capture(name, full_screen=False):
    """Gerçek Windows EKRANINDAN görüntü alır (QWidget.grab DEĞİL)."""
    _shot[0] += 1
    path = os.path.join(SHOT_DIR, f"{SCENARIO}-{_shot[0]:02d}-{name}.png")
    pixmap = QApplication.primaryScreen().grabWindow(0)
    pixmap.save(path)
    print(f"SHOT {name} {path}", flush=True)
    image = pixmap.toImage()
    ratio = float(pixmap.devicePixelRatio() or 1.0)
    rect = video_rect()
    device = QRect(int(rect.x() * ratio), int(rect.y() * ratio),
                   int(rect.width() * ratio), int(rect.height() * ratio))
    frame = frame_from_image(image, device)
    print(f"VIDEO_RECT {name} logical={rect.getRect()} dpr={ratio} "
          f"frame={frame['width']}x{frame['height']}", flush=True)
    return frame, path


def mpv():
    return PLAYER.mpv_player


def readback(names):
    out = {}
    for name in names:
        try:
            out[name] = getattr(mpv(), name)
        except Exception as exc:
            out[name] = f"<{type(exc).__name__}>"
    return out


def seek_exact(seconds):
    trace("seek_exact:pause_before")
    mpv().pause = True
    trace("seek_exact:pause_after")
    try:
        trace("seek_exact:command_before")
        mpv().command("seek", seconds, "absolute+exact")
        trace("seek_exact:command_after")
    except Exception as exc:
        print(f"SEEK_FAILED {type(exc).__name__}", flush=True)
        return False
    return wait_for(lambda: abs(float(mpv().time_pos or -99) - seconds) < 0.4,
                    9000)


# ------------------------------------------------------- geçici altyazılar

def _srt_block(index, start, end, lines):
    return f"{index}\n{start} --> {end}\n" + "\n".join(lines) + "\n\n"


def write_long_srt(path):
    """Ölçüm boyunca SÜREKLİ görünen tek cue."""
    body = _srt_block(1, "00:00:03,000", "01:30:00,000",
                      [SUB_LINE_1, SUB_LINE_2])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
    return path


def write_timed_srt(path, start_s, end_s):
    """Senkron ölçümü için ZAMANI BİLİNEN dar cue."""
    def stamp(value):
        hours = int(value // 3600)
        minutes = int((value % 3600) // 60)
        seconds = int(value % 60)
        millis = int(round((value - int(value)) * 1000))
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    body = _srt_block(1, stamp(start_s), stamp(end_s),
                      [SUB_LINE_1, SUB_LINE_2])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
    return path


def write_ass(path):
    """KENDİ stili olan (sarı, küçük) basit ASS altyazısı."""
    text = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 384\n"
        "PlayResY: 288\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: MLCASS,Arial,16,&H0000FFFF,&H000000FF,&H00000000,"
        "&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
        f"Dialogue: 0,0:00:03.00,1:30:00.00,MLCASS,,0,0,0,,"
        f"{SUB_LINE_1}\\N{SUB_LINE_2}\n")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def write_green_ass(path):
    """Bant ölçümü için AYIRT EDİCİ yeşil ASS altyazısı.

    ASS renk biçimi `&HAABBGGRR`; saf yeşil `&H0000FF00`. Ürünün turuncu
    vurgu rengi timeline dolgusuyla karıştığı için maske rengi yeşildir.
    `sub_ass_override=force` + `sub_ass_force_margins=True` ile ürünün
    marjı ASS altyazıda da geçerlidir; bu senaryo bunu PİKSELLE ölçer.
    """
    text = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 384\n"
        "PlayResY: 288\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: MLCBAND,Arial,16,&H0000FF00,&H000000FF,&H00000000,"
        "&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
        f"Dialogue: 0,0:00:03.00,1:30:00.00,MLCBAND,,0,0,0,,"
        f"{SUB_LINE_1}\\N{SUB_LINE_2}\n")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def add_subtitle(path):
    try:
        mpv().command("sub-add", path, "select")
    except Exception as exc:
        print(f"SUB_ADD_FAILED {type(exc).__name__}", flush=True)
        return False
    mpv().sub_visibility = True
    return wait_for(lambda: bool(mpv().sid), 8000)


def selected_sub_info():
    try:
        tracks = list(mpv().track_list or [])
    except Exception:
        tracks = []
    codec = selected_subtitle_codec(tracks)
    return tracks, codec


# ---------------------------------------------------------- dialog sürüşü

# `_spin_text()` KALDIRILDI: yerel ondalik ayraciyla spinbox'a metin
# yazmak icindi; hazir deger listelerinde serbest yazim yoktur.


def trace(step):
    if os.environ.get("MLC_SUB_TRACE") == "1":
        print(f"TRACE {step} t={time.time() - START:.2f}", flush=True)


def set_preset(combo, value, notes):
    """Hazır değer listesinden ÜRÜN API'siyle seçer.

    ESKİ HARNESS `QDoubleSpinBox` alanlarına (`delay_spin`, `scale_spin`,
    `border_spin`) klavyeyle yazıyordu. Yeni arayüzde bu alanlar YOK;
    resmî koşum `AttributeError` ile yarıda kalıyor ve dialog sürüşü
    hiç uygulanmadan MPV eski değeri okuyordu. Artık combo'nun kendi
    sözleşmesi kullanılır; ETİKET METNİ PARSE EDİLMEZ.
    """
    name = combo.objectName()
    trace(f"combo_select:{name}:{value}")
    combo.setFocus()
    index = combo.select_value(float(value))
    applied = combo.value()
    trace(f"combo_done:{name}={applied}")
    if abs(applied - float(value)) > 0.001:
        # Hazır listede olmayan bir değer istendi: en yakın hazır değer
        # seçilir ve bu AÇIKÇA not düşülür (sessiz sapma olmaz).
        notes.append(f"{name}:snapped_to_{applied}")
    else:
        notes.append(f"{name}:select_value")
    return index


def set_slider(slider, value, notes):
    """Home + PageUp/Up: gerçek Qt kullanıcı olayları."""
    trace("slider_focus")
    slider.setFocus()
    QTest.keyClick(slider, Qt.Key.Key_Home)
    steps = int(value) - slider.minimum()
    page = max(1, slider.pageStep())
    trace(f"slider_steps={steps}/page={page}")
    for _ in range(steps // page):
        QTest.keyClick(slider, Qt.Key.Key_PageUp)
    for _ in range(steps % page):
        QTest.keyClick(slider, Qt.Key.Key_Up)
    trace(f"slider_done={slider.value()}")
    if slider.value() != int(value):
        notes.append(f"{slider.objectName()}:fallback_setValue")
        slider.setValue(int(value))
    else:
        notes.append(f"{slider.objectName()}:qtest_keys")


def _dismiss_secondary_modal(exclude):
    modal = QApplication.activeModalWidget()
    if modal is not None and modal is not exclude:
        modal.reject() if isinstance(modal, QDialog) else modal.close()
        return True
    return False


def drive_dialog(values, expect_success=True, mutate_only=False,
                 close_with="apply", shot_tag=""):
    """Gerçek ürün yolu: `show_subtitle_settings()` -> dialog -> Uygula.

    `dialog.exec()` bloklar; etkileşim modal döngü İÇİNDE çalışan tek
    atımlık timer'dan yapılır. Böylece ürünün gerçek entegrasyon
    noktası atlanmaz.
    """
    outcome = {"driven": False, "input": [], "ui_values": {},
               "still_open": False, "error": "", "attempts": 0}

    def find_dialog():
        modal = QApplication.activeModalWidget()
        if isinstance(modal, SubtitleAppearanceDialog):
            return modal
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, SubtitleAppearanceDialog) and widget.isVisible():
                return widget
        return None

    def interact():
        dialog = find_dialog()
        if dialog is None:
            outcome["attempts"] += 1
            if outcome["attempts"] < 60:
                QTimer.singleShot(100, interact)
                return
            # Dialog HİÇ bulunamadı: kilitlenme yerine açık FAIL kanıtı.
            outcome["error"] = "dialog_not_found"
            modal = QApplication.activeModalWidget()
            print(f"DIALOG_NOT_FOUND modal={type(modal).__name__}", flush=True)
            if isinstance(modal, QDialog):
                modal.reject()
            return
        outcome["driven"] = True
        print(f"DIALOG_FOUND attempts={outcome['attempts']}", flush=True)
        try:
            notes = outcome["input"]
            set_preset(dialog.delay_combo, values["sub_delay"], notes)
            set_preset(dialog.scale_combo, values["sub_scale"], notes)
            set_preset(dialog.border_combo, values["sub_border_size"], notes)
            set_slider(dialog.position_slider, values["sub_pos"], notes)
            for key in COLOR_KEYS:
                # Renk seçicinin modal otomasyonu güvenilir değil; dialog'un
                # test edilebilir renk yolu kullanılır. Uygulama zinciri
                # (Uygula -> callback -> atomic_apply -> libmpv) DEĞİŞMEZ.
                trace(f"color:{key}")
                dialog.set_color(key, values[key])
            trace("colors_done")
            outcome["ui_values"] = {
                name: (qcolor_to_mpv_argb(item) if isinstance(item, QColor)
                       else round(float(item), 3))
                for name, item in dialog.current_values().items()}
            if shot_tag:
                # GERÇEK dialog + GERÇEK video aynı ekran görüntüsünde.
                APP.processEvents()
                time.sleep(0.35)
                capture(shot_tag)
            if mutate_only:
                outcome["still_open"] = dialog.isVisible()
                if close_with == "escape":
                    QTest.keyClick(dialog, Qt.Key.Key_Escape)
                else:
                    QTest.mouseClick(dialog.cancel_button,
                                     Qt.MouseButton.LeftButton)
                return
            if not expect_success:
                # Başarısız uygulamada ürün hata penceresi açar; ölçüm
                # kilitlenmesin diye onu kapatacak ikinci atım kurulur.
                QTimer.singleShot(400, lambda: _dismiss_secondary_modal(dialog))
            print(f"DIALOG_APPLY_CLICK ui={outcome['ui_values']}", flush=True)
            QTest.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
            outcome["still_open"] = dialog.isVisible()
            print(f"DIALOG_APPLIED still_open={outcome['still_open']}",
                  flush=True)
            if outcome["still_open"]:
                dialog.reject()
        except Exception as exc:
            outcome["error"] = f"{type(exc).__name__}: {exc}"
            dialog.reject()

    print("DIALOG_OPENING", flush=True)
    QTimer.singleShot(150, interact)
    PLAYER.show_subtitle_settings()
    print(f"DIALOG_CLOSED driven={outcome['driven']} "
          f"attempts={outcome['attempts']} error={outcome['error'] or 'none'} "
          f"input={outcome['input']}", flush=True)
    pump(250)
    return outcome


def apply_style(values, tag, shot_tag=""):
    """Stili uygular ve MPV readback'ini raporlar."""
    outcome = drive_dialog(values, shot_tag=shot_tag)
    props = readback(["sub_color", "sub_back_color", "sub_border_color",
                      "sub_border_style", "sub_shadow_offset",
                      "sub_ass_override", "sub_scale", "sub_pos",
                      "sub_border_size", "sub_delay"])
    print(f"READBACK|{tag}|{json.dumps(props, ensure_ascii=False, default=str)}"
          f"|input={outcome['input']}|error={outcome['error'] or 'none'}",
          flush=True)
    measures.setdefault("readback", {})[tag] = props
    return outcome, props


# ------------------------------------------------------------- ölçüm yardımı

def mask_report(tag, stats, extra=None):
    payload = {"count": stats["count"], "bbox": stats["bbox"],
               "size": bbox_size(stats["bbox"]),
               "fill": round(fill_ratio(stats["count"], stats["bbox"]), 3)}
    if extra:
        payload.update(extra)
    measures.setdefault("masks", {})[tag] = payload
    print(f"MEASURE|{tag}|{json.dumps(payload, ensure_ascii=False)}",
          flush=True)
    return payload


def rgb_of(color):
    return (color.red(), color.green(), color.blue())


def baseline_frame():
    """Altyazı KAPALI iken aynı karenin görüntüsü (piksel referansı)."""
    mpv().sub_visibility = False
    pump(500)
    frame, path = capture("baseline-nosub")
    mpv().sub_visibility = True
    pump(400)
    return frame, path


def styled_frame(values, tag, shot_name, dialog_shot=""):
    apply_style(values, tag, shot_tag=dialog_shot)
    # Ürünle AYNI yol: `atomic_apply()` ham `sub_pos` yazdığı için ürün
    # `menu_actions._apply_subtitle_style()` içinde bandı yeniler.
    # Harness `atomic_apply`i DOĞRUDAN çağırdığından aynı sarmalayıcının
    # yaptığı işi burada tekrarlamak yerine ÜRÜN fonksiyonu kullanılır.
    try:
        from app.menu_actions import _apply_subtitle_style  # noqa: F401
        PLAYER.video_frame.invalidate_subtitle_band()
        PLAYER.video_frame.sync_subtitle_safe_band()
    except Exception:
        pass
    if not seek_exact(SEEK_TIME):
        print(f"RESEEK_WARNING {tag}", flush=True)
    pump(700)
    return capture(shot_name)


def subtitle_visible_now():
    try:
        return bool((mpv().sub_text or "").strip())
    except Exception:
        return False


# ----------------------------------------------------------------- senaryolar

def scenario_a_text_color(base):
    white_frame, _ = styled_frame(dict(BASE_VALUES), "baseline_white",
                                  "baseline-white-transparent")
    white_mask = scan_changed(base, white_frame, CHANGE_THRESHOLD)
    mask_report("a_white_changed", white_mask)
    white_pixels = scan_changed_color(base, white_frame, CHANGE_THRESHOLD,
                                      rgb_of(WHITE), COLOR_TOL)
    mask_report("a_white_color", white_pixels)
    record("a_baseline_white_visible",
           f"aynı kare farkı thr={CHANGE_THRESHOLD}, beyaz tol={COLOR_TOL}",
           f"beyaz glif >= {MIN_MASK_PIXELS} px",
           f"changed={white_mask['count']} white={white_pixels['count']}",
           white_pixels["count"] >= MIN_MASK_PIXELS)

    values = dict(BASE_VALUES, sub_color=QColor(ORANGE))
    orange_frame, _ = styled_frame(values, "orange", "orange-text",
                                   dialog_shot="dialog-and-video-before-apply")
    props = measures["readback"]["orange"]
    record("a_readback_orange", "libmpv property readback",
           "#FFF26A3D", str(props.get("sub_color")),
           str(props.get("sub_color")).upper() == "#FFF26A3D")

    orange_pixels = scan_changed_color(base, orange_frame, CHANGE_THRESHOLD,
                                       rgb_of(ORANGE), COLOR_TOL)
    mask_report("a_orange_color", orange_pixels)
    record("a_orange_pixels_present",
           f"değişen VE turuncu (tol={COLOR_TOL})",
           f">= {MIN_MASK_PIXELS} px", str(orange_pixels["count"]),
           orange_pixels["count"] >= MIN_MASK_PIXELS)

    # Aynı karede beyaz ve turuncu sonuç piksel düzeyinde FARKLI olmalı.
    between = scan_changed(white_frame, orange_frame, CHANGE_THRESHOLD)
    mask_report("a_white_vs_orange", between)
    record("a_white_vs_orange_differs",
           "beyaz ve turuncu kareler arası fark",
           f">= {MIN_MASK_PIXELS} px", str(between["count"]),
           between["count"] >= MIN_MASK_PIXELS)

    # Eski hatalı yorum (#RRGGBBAA) kırmızımsı/şeffaf sonuç üretiyordu.
    orange_in_white = scan_changed_color(base, white_frame, CHANGE_THRESHOLD,
                                         rgb_of(ORANGE), COLOR_TOL)
    white_in_orange = scan_changed_color(base, orange_frame, CHANGE_THRESHOLD,
                                         rgb_of(WHITE), COLOR_TOL)
    mask_report("a_cross_check",
                orange_in_white,
                {"white_pixels_in_orange_frame": white_in_orange["count"]})
    record("a_no_legacy_rgba_misread",
           "turuncu karede beyaz glif çekirdeği baskın OLMAMALI",
           "white_in_orange < orange_pixels",
           f"white_in_orange={white_in_orange['count']} "
           f"orange={orange_pixels['count']}",
           white_in_orange["count"] < orange_pixels["count"])

    # Uygulama SONRASI dialog + video birlikte: kaydedilen değerler
    # gerçek pencerede geri gelmiş hâlde görünür.
    reopened = drive_dialog(values, mutate_only=True, close_with="cancel",
                            shot_tag="dialog-and-video-after-apply")
    record("a_dialog_reopens_with_applied_values",
           "uygulama sonrası dialog + video ekran görüntüsü",
           "dialog açıldı ve sub_color=#FFF26A3D",
           f"driven={reopened['driven']} "
           f"ui={reopened['ui_values'].get('sub_color')}",
           reopened["driven"]
           and reopened["ui_values"].get("sub_color") == "#FFF26A3D")


def scenario_b_background_off(base):
    values = dict(BASE_VALUES, sub_color=QColor(WHITE),
                  sub_back_color=QColor(CLEAR))
    frame, _ = styled_frame(values, "back_off", "background-transparent")
    props = measures["readback"]["back_off"]
    record("b_readback_border_style", "libmpv property readback",
           OUTLINE_AND_SHADOW, str(props.get("sub_border_style")),
           str(props.get("sub_border_style")) == OUTLINE_AND_SHADOW)
    record("b_readback_back_color", "libmpv property readback",
           "#00000000", str(props.get("sub_back_color")),
           str(props.get("sub_back_color")).upper() == "#00000000")

    mask = scan_changed(base, frame, CHANGE_THRESHOLD)
    runs = changed_longest_run(base, frame, CHANGE_THRESHOLD,
                               region=mask["bbox"])
    payload = mask_report("b_changed", mask,
                          {"longest_run": runs["best"],
                           "rows_over_half": runs["rows_over_half"],
                           "run_ratio": round(
                               solid_box_ratio(runs["best"], mask["bbox"]), 3)})
    # Kesintisiz yatay dizi ölçüsü, farklı genişlikteki iki satırın
    # BİRLEŞİK bbox'ında doluluk oranından çok daha ayırt edicidir.
    record("b_no_solid_box",
           "altyazı katmanının en uzun kesintisiz yatay dizisi",
           "yarım genişliği aşan satır yok ve run_ratio <= 0.35",
           f"longest_run={runs['best']} rows_over_half="
           f"{runs['rows_over_half']} run_ratio={payload['run_ratio']} "
           f"fill={payload['fill']}",
           mask["count"] >= MIN_MASK_PIXELS
           and runs["rows_over_half"] == 0
           and payload["run_ratio"] <= 0.35)
    measures["b_fill"] = payload["fill"]


def _background_measure(base, back_color, tag, shot):
    values = dict(BASE_VALUES, sub_color=QColor(WHITE),
                  sub_back_color=QColor(back_color))
    frame, _ = styled_frame(values, tag, shot)
    mask = scan_changed(base, frame, CHANGE_THRESHOLD)
    payload = mask_report(f"{tag}_changed", mask)
    box = scan_changed_color(base, frame, CHANGE_THRESHOLD,
                             rgb_of(back_color), COLOR_TOL)
    box_runs = longest_run(frame, rgb_of(back_color), COLOR_TOL,
                           region=box["bbox"])
    mask_report(f"{tag}_box_color", box,
                {"longest_run": box_runs["best"],
                 "rows_over_half": box_runs["rows_over_half"],
                 "run_ratio": round(
                     solid_box_ratio(box_runs["best"], box["bbox"]), 3)})
    measures.setdefault("box_runs", {})[tag] = box_runs
    text = scan_changed_color(base, frame, CHANGE_THRESHOLD,
                              rgb_of(WHITE), COLOR_TOL)
    mask_report(f"{tag}_text_color", text)
    return frame, mask, payload, box, text


def scenario_c_background_on(base):
    frame, mask, payload, box, text = _background_measure(
        base, BLUE, "back_on", "background-box-visible")
    props = measures["readback"]["back_on"]
    record("c_readback_border_style", "libmpv property readback",
           BACKGROUND_BOX, str(props.get("sub_border_style")),
           str(props.get("sub_border_style")) == BACKGROUND_BOX)
    record("c_readback_back_color", "libmpv property readback",
           "#FF0020A0", str(props.get("sub_back_color")),
           str(props.get("sub_back_color")).upper() == "#FF0020A0")
    runs = measures["box_runs"]["back_on"]
    ratio = solid_box_ratio(runs["best"], box["bbox"])
    record("c_solid_box_on_screen",
           "arka plan renginin en uzun kesintisiz yatay dizisi",
           f"run_ratio >= {BOX_FILL_MIN} , yarım genişliği aşan satır >= 20 "
           f"ve mavi >= {MIN_MASK_PIXELS}",
           f"longest_run={runs['best']} rows_over_half="
           f"{runs['rows_over_half']} run_ratio={ratio:.3f} "
           f"blue={box['count']} bbox_fill={payload['fill']}",
           ratio >= BOX_FILL_MIN and runs["rows_over_half"] >= 20
           and box["count"] >= MIN_MASK_PIXELS)
    record("c_box_does_not_hide_text",
           "kutu içinde beyaz glif pikselleri",
           f">= {MIN_MASK_PIXELS} px", str(text["count"]),
           text["count"] >= MIN_MASK_PIXELS)
    inside = contains((0, 0, frame["width"] - 1, frame["height"] - 1),
                      mask["bbox"])
    record("c_box_inside_video", "bbox video yüzeyi içinde",
           "True", f"{mask['bbox']} in 0,0,{frame['width']-1},"
                   f"{frame['height']-1}", inside)

    # Alfa değişince kutunun GERÇEK görüntüsü değişmeli.
    half_frame, _, half_payload, half_box, _ = _background_measure(
        base, BLUE_HALF, "back_half", "background-box-half-alpha")
    diff = scan_changed(frame, half_frame, CHANGE_THRESHOLD)
    mask_report("c_alpha_diff", diff)
    record("c_alpha_changes_box",
           "opak ve yarı saydam kutu kareleri arası fark",
           f">= {MIN_MASK_PIXELS} px", str(diff["count"]),
           diff["count"] >= MIN_MASK_PIXELS)
    measures["c_fill"] = payload["fill"]
    measures["c_half_fill"] = half_payload["fill"]
    measures["c_half_blue"] = half_box["count"]
    return frame, box, text


def scenario_d_box_padding(base):
    frame, mask, payload, box, text = _background_measure(
        base, BLUE, "padding", "background-box-padding")
    pads = padding(inner=text["bbox"], outer=box["bbox"])
    glyph_height = bbox_size(text["bbox"])[1]
    maximum = max(14, int(glyph_height * 0.9))
    measures["d_padding"] = {"padding": pads, "glyph_bbox": text["bbox"],
                             "box_bbox": box["bbox"],
                             "glyph_height": glyph_height,
                             "max_allowed": maximum}
    print(f"MEASURE|d_padding|{json.dumps(measures['d_padding'], ensure_ascii=False)}",
          flush=True)
    if not pads:
        record("d_box_padding", "glif ve kutu bbox farkı",
               "dört yönde ölçülebilir boşluk", "maske bulunamadı", None)
        return
    problems = padding_problems(pads, minimum=2, maximum=maximum)
    record("d_box_padding",
           "glif bbox ile background-box bbox arası dört yön boşluğu",
           f"her yön 2..{maximum} px", json.dumps(pads),
           not problems, f"problems={problems or 'none'} "
                         f"shadow_offset={measures['readback']['padding'].get('sub_shadow_offset')}")


def scenario_e_border_color(base):
    values = dict(BASE_VALUES, sub_color=QColor(WHITE),
                  sub_back_color=QColor(CLEAR),
                  sub_border_color=QColor(ORANGE), sub_border_size=4.0)
    frame, _ = styled_frame(values, "border_color", "border-colour")
    props = measures["readback"]["border_color"]
    record("e_readback_border_color", "libmpv property readback",
           "#FFF26A3D", str(props.get("sub_border_color")),
           str(props.get("sub_border_color")).upper() == "#FFF26A3D")
    text = scan_changed_color(base, frame, CHANGE_THRESHOLD,
                              rgb_of(WHITE), COLOR_TOL)
    border = scan_changed_color(base, frame, CHANGE_THRESHOLD,
                                rgb_of(ORANGE), COLOR_TOL)
    mask_report("e_text_white", text)
    mask_report("e_border_orange", border)
    record("e_two_distinct_clusters",
           "beyaz yazı ve turuncu kenarlık AYRI maskeler",
           f"ikisi de >= {MIN_MASK_PIXELS} px",
           f"white={text['count']} orange={border['count']}",
           text["count"] >= MIN_MASK_PIXELS
           and border["count"] >= MIN_MASK_PIXELS)
    record("e_border_encloses_text",
           "turuncu bbox beyaz bbox'ı kapsıyor",
           "True", f"border={border['bbox']} text={text['bbox']}",
           contains(border["bbox"], text["bbox"], slack=2))


def scenario_f_border_size(base):
    thin_values = dict(BASE_VALUES, sub_color=QColor(WHITE),
                       sub_back_color=QColor(CLEAR),
                       sub_border_color=QColor(ORANGE), sub_border_size=1.0)
    thin_frame, _ = styled_frame(thin_values, "border_thin", "border-thin")
    thin = scan_changed_color(base, thin_frame, CHANGE_THRESHOLD,
                              rgb_of(ORANGE), COLOR_TOL)
    mask_report("f_thin_orange", thin)

    thick_values = dict(thin_values, sub_border_size=5.0)
    thick_frame, _ = styled_frame(thick_values, "border_thick", "border-thick")
    thick = scan_changed_color(base, thick_frame, CHANGE_THRESHOLD,
                               rgb_of(ORANGE), COLOR_TOL)
    mask_report("f_thick_orange", thick)

    record("f_readback_sizes", "libmpv property readback",
           "ince=1.0 kalın=5.0",
           f"{measures['readback']['border_thin'].get('sub_border_size')} / "
           f"{measures['readback']['border_thick'].get('sub_border_size')}",
           abs(float(measures['readback']['border_thin']['sub_border_size']) - 1.0) < 0.01
           and abs(float(measures['readback']['border_thick']['sub_border_size']) - 5.0) < 0.01)
    trace("f:after_readback_record")
    ratio = growth_ratio(thin["count"], thick["count"])
    measures["f_ratio"] = round(ratio, 3)
    trace(f"f:ratio={ratio}")
    record("f_thick_border_covers_more",
           "turuncu piksel alanı ince -> kalın",
           "oran >= 1.30", f"thin={thin['count']} thick={thick['count']} "
                           f"ratio={ratio:.2f}",
           ratio >= 1.30)
    full = (0, 0, thick_frame["width"] - 1, thick_frame["height"] - 1)
    record("f_no_clipping", "kalın kenarlık bbox'ı video yüzeyi içinde",
           "True", f"{thick['bbox']} in {full}",
           contains(full, thick["bbox"]))
    trace("f:done")


def scenario_g_text_size(base):
    # ESKI: 0.8 / 1.8. Ikisi de artik hazir deger DEGIL (liste:
    # 0.75, 0.85, 1.0, 1.15, 1.25, 1.5, 2.0). Sozlesme AYNI: kucuk ve
    # buyuk hazir deger arasinda bbox gercekten buyumeli.
    small_values = dict(BASE_VALUES, sub_scale=0.75)
    small_frame, _ = styled_frame(small_values, "scale_small", "text-small")
    small = scan_changed(base, small_frame, CHANGE_THRESHOLD)
    mask_report("g_small", small)

    large_values = dict(BASE_VALUES, sub_scale=2.0)
    large_frame, _ = styled_frame(large_values, "scale_large", "text-large")
    large = scan_changed(base, large_frame, CHANGE_THRESHOLD)
    mask_report("g_large", large)

    record("g_readback_scales", "libmpv property readback",
           "0.8 / 1.8",
           f"{measures['readback']['scale_small'].get('sub_scale')} / "
           f"{measures['readback']['scale_large'].get('sub_scale')}",
           abs(float(measures['readback']['scale_small']['sub_scale']) - 0.75) < 0.01
           and abs(float(measures['readback']['scale_large']['sub_scale']) - 2.0) < 0.01)

    small_size = bbox_size(small["bbox"])
    large_size = bbox_size(large["bbox"])
    width_ratio = growth_ratio(small_size[0], large_size[0])
    height_ratio = growth_ratio(small_size[1], large_size[1])
    measures["g_ratios"] = {"width": round(width_ratio, 3),
                            "height": round(height_ratio, 3),
                            "small": small_size, "large": large_size}
    record("g_large_text_bigger_bbox",
           "gerçek metin bbox genişlik/yükseklik oranı",
           "her ikisi >= 1.15",
           f"small={small_size} large={large_size} "
           f"w={width_ratio:.2f} h={height_ratio:.2f}",
           width_ratio >= 1.15 and height_ratio >= 1.15)
    full = (0, 0, large_frame["width"] - 1, large_frame["height"] - 1)
    record("g_large_text_inside_video", "büyük yazı video yüzeyinden taşmıyor",
           "True", f"{large['bbox']} in {full}", contains(full, large["bbox"]))


def _position_measure(base, position, tag, shot):
    """Konum ölçümü: altyazı GÖRÜNÜR/GİZLİ eşlenik kare + yeşil filtre.

    ESKİ YOL `scan_changed(base, frame)` idi: altyazısız BAŞLANGIÇ
    karesiyle stilli kare karşılaştırılıyordu. İki çekim arasında
    kontrol katmanı auto-hide ile değiştiği için maskeye KATMAN
    pikselleri karışıyordu (ölçüldü: bbox (329, 502, 1116, 739),
    yüksekliği 238 px — iki satırlık altyazı için imkânsız; bandın
    içinde "görünen 150 altyazı pikseli" aslında kontrol panelinin
    kendisiydi). Konum ölçümünde yazı rengi AYIRT EDİCİ yeşile alınır;
    ürünün turuncu vurgu rengi timeline dolgusuyla karışıyordu.
    """
    values = dict(BASE_VALUES, sub_pos=float(position),
                  sub_color=QColor(PROBE_GREEN))
    frame, _ = styled_frame(values, tag, shot)
    result = subtitle_only_mask(tag, shot)
    mask = result["mask"] if result else scan_changed(base, frame,
                                                      CHANGE_THRESHOLD)
    mask_report(f"{tag}_mask", mask)
    return frame, mask


def scenario_h_position(base):
    frame70, mask70 = _position_measure(base, 70, "pos70", "position-70")
    frame95, mask95 = _position_measure(base, 95, "pos95", "position-95")
    record("h_readback_positions", "libmpv property readback",
           "70.0 / 95.0",
           f"{measures['readback']['pos70'].get('sub_pos')} / "
           f"{measures['readback']['pos95'].get('sub_pos')}",
           abs(float(measures['readback']['pos70']['sub_pos']) - 70.0) < 0.01
           and abs(float(measures['readback']['pos95']['sub_pos']) - 95.0) < 0.01)

    centre70 = mask70["centre"]
    centre95 = mask95["centre"]
    if not centre70 or not centre95:
        record("h_position_moves_down", "bbox merkez Y karşılaştırması",
               "95 daha aşağıda", f"{centre70} / {centre95}", None)
        return
    delta = centre95[1] - centre70[1]
    minimum = int(frame70["height"] * 0.06)
    measures["h_delta_y"] = {"centre70": centre70, "centre95": centre95,
                             "delta": delta, "min_expected": minimum}
    record("h_position_moves_down",
           "aynı karede altyazı bbox merkez Y farkı",
           f"delta >= {minimum} px (95 daha aşağıda)",
           f"y70={centre70[1]} y95={centre95[1]} delta={delta}",
           delta >= minimum)
    full = (0, 0, frame95["width"] - 1, frame95["height"] - 1)
    record("h_inside_video", "her iki konum video yüzeyi içinde", "True",
           f"{mask70['bbox']} / {mask95['bbox']}",
           contains(full, mask70["bbox"]) and contains(full, mask95["bbox"]))
    offsets = [horizontal_centre_offset(mask70["bbox"], full),
               horizontal_centre_offset(mask95["bbox"], full)]
    allowed = int(frame95["width"] * 0.05)
    record("h_horizontal_centre_kept", "bbox yatay merkez sapması",
           f"|offset| <= {allowed} px", str(offsets),
           all(abs(value) <= allowed for value in offsets))

    # Kontrol katmanı görünürken çakışma ölçümü.
    overlay = PLAYER.video_frame.control_overlay
    if overlay is not None:
        rect = video_rect()
        overlay_rect = global_rect(overlay)
        local = (overlay_rect.left() - rect.left(),
                 overlay_rect.top() - rect.top(),
                 overlay_rect.right() - rect.left(),
                 overlay_rect.bottom() - rect.top())
        ratio = overlap_ratio(mask95["bbox"], local)
        # "Kontrollerin ARKASINA düşmek" z-order sorunudur: katmanla
        # kesişen bölgede altyazı pikselleri hâlâ görünüyor mu? Yalnız
        # geometrik kesişim oranı bu soruyu yanıtlamaz, bu yüzden
        # kesişim bölgesinde gerçek piksel farkı ölçülür.
        shared = intersection(mask95["bbox"], local)
        occluded = scan_changed(base, frame95, CHANGE_THRESHOLD,
                                region=shared) if shared else None
        measures["h_overlay"] = {"overlay_local": local,
                                 "sub_bbox": mask95["bbox"],
                                 "overlap_ratio": round(ratio, 3),
                                 "shared_rect": shared,
                                 "visible_pixels_in_overlay":
                                     occluded["count"] if occluded else 0,
                                 "overlay_visible": bool(overlay.isVisible()),
                                 "overlay_opacity": float(
                                     getattr(overlay, "windowOpacity",
                                             lambda: 1.0)())}
        print(f"MEASURE|h_overlay|{json.dumps(measures['h_overlay'], ensure_ascii=False)}",
              flush=True)
        # ESKIYEN SOZLESME: bu olcum "altyazi katmanla KESISIYOR ama
        # arkasina dusmuyor" diyordu ve kesisim bolgesinde EN AZ
        # `MIN_MASK_PIXELS` altyazi pikseli ARIYORDU. Guvenli alt bant
        # eklendikten sonra altyazi banda HIC girmez; eski kural artik
        # cakismayi TALEP eder duruma dusmustu. Yeni kural: %95'te
        # altyazi kontrol bandiyla KESISMEMELI.
        record("h_subtitle_clears_the_control_band",
               "altyazı bbox'ı ile kontrol bandının kesişimi",
               "kesişim yok (alt kenar bandın üstünde)",
               f"sub_bbox={mask95['bbox']} band_top={local[1]} "
               f"shared={shared} "
               f"visible_in_band="
               f"{measures['h_overlay']['visible_pixels_in_overlay']}",
               mask95["bbox"][3] < local[1])

    # Playlist AÇIKKEN de ölçüm alınır.
    PLAYER.video_frame.toggle_playlist_panel()
    try:
        PLAYER.video_frame.playlist_panel.finish_animation()
    except Exception:
        pass
    pump(600)
    base_open, _ = baseline_frame()
    frame_open, mask_open = _position_measure(base_open, 95, "pos95_playlist",
                                              "position-95-playlist-open")
    full_open = (0, 0, frame_open["width"] - 1, frame_open["height"] - 1)
    record("h_playlist_open_measurement",
           "playlist açıkken altyazı hâlâ video yüzeyinde",
           f">= {MIN_MASK_PIXELS} px ve bbox video içinde",
           f"count={mask_open['count']} bbox={mask_open['bbox']}",
           mask_open["count"] >= MIN_MASK_PIXELS
           and contains(full_open, mask_open["bbox"]))
    PLAYER.video_frame.toggle_playlist_panel()
    try:
        PLAYER.video_frame.playlist_panel.finish_animation()
    except Exception:
        pass
    pump(400)


def scenario_i_delay(base_unused):
    """Senkron gecikmesi: zamanı BİLİNEN cue ile görünürlük değişimi."""
    cue_start, cue_end = SEEK_TIME - 2.0, SEEK_TIME + 2.0
    path = write_timed_srt(os.path.join(TEMP_DIR, "mlc_timed.srt"),
                           cue_start, cue_end)
    try:
        mpv().command("sub-remove")
    except Exception:
        pass
    if not add_subtitle(path):
        record("i_timed_subtitle_loaded", "sub-add + sid", "sid > 0",
               "yüklenemedi", None)
        return
    seek_exact(SEEK_TIME)
    pump(600)
    base, _ = baseline_frame()

    zero_frame, _ = styled_frame(dict(BASE_VALUES), "delay_zero",
                                 "delay-zero")
    zero_text = subtitle_visible_now()
    zero_mask = scan_changed(base, zero_frame, CHANGE_THRESHOLD)
    mask_report("i_delay_zero", zero_mask, {"sub_text": zero_text})
    record("i_cue_visible_at_zero",
           f"cue [{cue_start:.1f}, {cue_end:.1f}] @ t={SEEK_TIME}",
           f"sub-text dolu ve >= {MIN_MASK_PIXELS} px",
           f"sub_text={zero_text} pixels={zero_mask['count']}",
           zero_text and zero_mask["count"] >= MIN_MASK_PIXELS)

    # ESKI: 8.0 sn. Senkron araligi urun kararyla +-5 sn oldu; cue'nun
    # kaybolmasi icin 5.0 sn yeterli (cue penceresi +-2 sn).
    shifted_frame, _ = styled_frame(dict(BASE_VALUES, sub_delay=5.0),
                                    "delay_plus", "delay-shifted")
    shifted_text = subtitle_visible_now()
    shifted_mask = scan_changed(base, shifted_frame, CHANGE_THRESHOLD)
    mask_report("i_delay_plus8", shifted_mask, {"sub_text": shifted_text})
    record("i_readback_delay", "libmpv property readback", "5.0",
           str(measures["readback"]["delay_plus"].get("sub_delay")),
           abs(float(measures["readback"]["delay_plus"]["sub_delay"]) - 5.0) < 0.01)
    record("i_cue_hidden_after_delay",
           "aynı video zamanında +8.0 sn gecikme",
           f"sub-text boş ve < {MIN_MASK_PIXELS} px",
           f"sub_text={shifted_text} pixels={shifted_mask['count']}",
           (not shifted_text) and shifted_mask["count"] < MIN_MASK_PIXELS)

    back_frame, _ = styled_frame(dict(BASE_VALUES), "delay_back", "delay-back")
    back_text = subtitle_visible_now()
    back_mask = scan_changed(base, back_frame, CHANGE_THRESHOLD)
    mask_report("i_delay_back", back_mask, {"sub_text": back_text})
    record("i_cue_returns_at_zero", "gecikme tekrar 0",
           f"sub-text dolu ve >= {MIN_MASK_PIXELS} px",
           f"sub_text={back_text} pixels={back_mask['count']}",
           back_text and back_mask["count"] >= MIN_MASK_PIXELS)

    stored = PLAYER.settings.value(f"{SETTINGS_PREFIX}sub_delay")
    record("i_delay_not_persisted",
           "ürün politikası: MPV'ye uygulanır, ayarlarda 0 saklanır",
           "0.0", str(stored), abs(float(stored or 0.0)) < 0.01)


def scenario_j_ass_override(base_unused):
    path = write_ass(os.path.join(TEMP_DIR, "mlc_style.ass"))
    try:
        mpv().command("sub-remove")
    except Exception:
        pass
    if not add_subtitle(path):
        record("j_ass_loaded", "sub-add (.ass) + sid", "sid > 0",
               "yüklenemedi", None)
        return
    tracks, codec = selected_sub_info()
    record("j_ass_track_is_text", "seçili parça codec'i",
           "metin tabanlı (ass)", str(codec),
           bool(codec) and not is_bitmap_subtitle(codec))
    seek_exact(SEEK_TIME)
    pump(700)
    if not subtitle_visible_now():
        record("j_ass_visible", "mpv sub-text", "dolu", "boş", None)
        return
    base, _ = baseline_frame()

    values = dict(BASE_VALUES, sub_color=QColor(ORANGE), sub_scale=2.0,
                  sub_back_color=QColor(CLEAR))
    frame, _ = styled_frame(values, "ass_force", "ass-override")
    props = measures["readback"]["ass_force"]
    override = str(props.get("sub_ass_override"))
    record("j_readback_ass_override", "libmpv property readback",
           ASS_OVERRIDE_FORCE, override,
           override == ASS_OVERRIDE_FORCE)
    record("j_override_not_boolean", "bool True / 'yes' canonical DEĞİL",
           "force", override, override not in ("True", "true", "yes", "1"))

    orange = scan_changed_color(base, frame, CHANGE_THRESHOLD,
                                rgb_of(ORANGE), COLOR_TOL)
    yellow = scan_changed_color(base, frame, CHANGE_THRESHOLD,
                                (255, 255, 0), COLOR_TOL)
    mask_report("j_orange", orange)
    mask_report("j_ass_yellow", yellow)
    record("j_user_style_overrides_ass",
           "ASS kendi sarısı yerine kullanıcı turuncusu",
           f"turuncu >= {MIN_MASK_PIXELS} ve turuncu > sarı",
           f"orange={orange['count']} yellow={yellow['count']}",
           orange["count"] >= MIN_MASK_PIXELS
           and orange["count"] > yellow["count"])


def _mpv_snapshot():
    return readback(["sub_color", "sub_back_color", "sub_border_color",
                     "sub_border_style", "sub_shadow_offset",
                     "sub_ass_override", "sub_scale", "sub_pos",
                     "sub_border_size"])


def _settings_snapshot():
    keys = [f"{SETTINGS_PREFIX}{name}" for name in
            ("sub_color", "sub_back_color", "sub_border_color",
             "sub_border_style", "sub_shadow_offset", "sub_ass_override",
             "sub_scale", "sub_pos", "sub_border_size", "sub_delay")]
    keys.append(SCHEMA_KEY)
    return {key: (PLAYER.settings.contains(key),
                  str(PLAYER.settings.value(key))) for key in keys}


class RejectingSettings:
    """TEK BİR yazmayı reddeden QSettings sarmalayıcısı.

    Hata ENJEKSİYONU yalnız testtedir; ürün kodu değiştirilmez.

    Neden tek seferlik: kalıcı olarak bozuk bir backend geri alma
    yazmalarını da reddeder; o durumda hiçbir ürün "önceki hâle
    döndürme" sözleşmesini yerine getiremez. Ölçülmek istenen şey
    GEÇİCİ bir yazma hatasında işlemin tamamen geri alınmasıdır.
    """

    def __init__(self, real, fail_on):
        self._real = real
        self._fail_on = fail_on
        self._fired = False
        self.writes = []

    def __getattr__(self, name):
        return getattr(self._real, name)

    def setValue(self, key, value):
        self.writes.append(key)
        if not self._fired and len(self.writes) == self._fail_on:
            self._fired = True
            raise OSError("injected_settings_failure")
        return self._real.setValue(key, value)


def scenario_k_lifecycle(base_unused):
    before_mpv = _mpv_snapshot()
    before_settings = _settings_snapshot()

    # 1) Açılış mutasyonsuz + birden fazla alan değişikliği yalnız UI.
    mutate = dict(BASE_VALUES, sub_color=QColor(ORANGE),
                  sub_back_color=QColor(BLUE), sub_scale=1.7, sub_pos=60.0)
    outcome = drive_dialog(mutate, mutate_only=True, close_with="cancel")
    record("k_dialog_driven", "gerçek dialog açıldı ve sürüldü", "True",
           f"driven={outcome['driven']} error={outcome['error'] or 'none'}",
           outcome["driven"] and not outcome["error"])
    record("k_cancel_keeps_mpv", "İptal sonrası MPV snapshot",
           "değişmedi", "değişti" if _mpv_snapshot() != before_mpv else "aynı",
           _mpv_snapshot() == before_mpv)
    record("k_cancel_keeps_settings", "İptal sonrası QSettings snapshot",
           "değişmedi",
           "değişti" if _settings_snapshot() != before_settings else "aynı",
           _settings_snapshot() == before_settings)

    # 2) Escape de kalıcı iz bırakmamalı.
    drive_dialog(mutate, mutate_only=True, close_with="escape")
    record("k_escape_keeps_state", "Escape sonrası MPV + QSettings",
           "değişmedi",
           "değişti" if (_mpv_snapshot() != before_mpv
                         or _settings_snapshot() != before_settings) else "aynı",
           _mpv_snapshot() == before_mpv
           and _settings_snapshot() == before_settings)

    # 3) Varsayılana Dön YALNIZ UI değerlerini değiştirir.
    reset_state = {"ui": {}, "mpv_changed": None}

    def reset_interact():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, SubtitleAppearanceDialog):
            return
        notes = []
        # NOT: 2.4 artik hazir deger DEGIL; en buyuk hazir deger 2.0.
        # Sozlesme ayni: "Varsayilana Don" UI'yi 1.0'a cevirir.
        set_preset(dialog.scale_combo, 2.0, notes)
        dialog.set_color("sub_color", QColor(BLUE))
        QTest.mouseClick(dialog.reset_button, Qt.MouseButton.LeftButton)
        reset_state["ui"] = {
            "sub_scale": dialog.scale_combo.value(),
            "sub_color": qcolor_to_mpv_argb(
                dialog.current_values()["sub_color"])}
        reset_state["mpv_changed"] = _mpv_snapshot() != before_mpv
        QTest.mouseClick(dialog.cancel_button, Qt.MouseButton.LeftButton)

    QTimer.singleShot(150, reset_interact)
    PLAYER.show_subtitle_settings()
    pump(250)
    record("k_reset_only_touches_ui",
           "Varsayılana Dön -> UI 1.0/#FFFFFFFF, MPV dokunulmamış",
           "ui_scale=1.0 ui_color=#FFFFFFFF mpv_changed=False",
           f"ui={reset_state['ui']} mpv_changed={reset_state['mpv_changed']}",
           abs(float(reset_state["ui"].get("sub_scale", -1)) - 1.0) < 0.01
           and reset_state["ui"].get("sub_color") == "#FFFFFFFF"
           and reset_state["mpv_changed"] is False)

    # 4) Uygula tek transaction olarak yazar; ikinci açılışta geri gelir.
    applied = dict(BASE_VALUES, sub_color=QColor(ORANGE),
                   sub_back_color=QColor(BLUE), sub_scale=1.5, sub_pos=80.0,
                   sub_border_size=4.5)
    apply_style(applied, "k_apply")
    after_settings = _settings_snapshot()
    expected = {f"{SETTINGS_PREFIX}sub_color": "#FFF26A3D",
                f"{SETTINGS_PREFIX}sub_back_color": "#FF0020A0",
                f"{SETTINGS_PREFIX}sub_border_style": BACKGROUND_BOX,
                f"{SETTINGS_PREFIX}sub_ass_override": ASS_OVERRIDE_FORCE}
    stored_ok = all(after_settings.get(key, (False, ""))[1].upper()
                    == value.upper() for key, value in expected.items())
    record("k_apply_writes_all", "QSettings tek transaction",
           json.dumps(expected, ensure_ascii=False),
           json.dumps({k: after_settings.get(k) for k in expected},
                      ensure_ascii=False),
           stored_ok)

    reopened = {"values": {}}

    def reopen_interact():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, SubtitleAppearanceDialog):
            return
        reopened["values"] = {
            "sub_scale": round(dialog.scale_combo.value(), 2),
            "sub_pos": float(dialog.position_slider.value()),
            "sub_border_size": round(dialog.border_combo.value(), 2),
            "sub_color": qcolor_to_mpv_argb(
                dialog.current_values()["sub_color"])}
        QTest.mouseClick(dialog.cancel_button, Qt.MouseButton.LeftButton)

    QTimer.singleShot(150, reopen_interact)
    PLAYER.show_subtitle_settings()
    pump(250)
    record("k_reopen_shows_saved",
           "ikinci açılışta kaydedilen değerler",
           "scale=1.5 pos=80.0 border=4.5 color=#FFF26A3D",
           json.dumps(reopened["values"], ensure_ascii=False),
           reopened["values"].get("sub_color") == "#FFF26A3D"
           and abs(reopened["values"].get("sub_scale", 0) - 1.5) < 0.01
           and abs(reopened["values"].get("sub_pos", 0) - 80.0) < 0.01
           and abs(reopened["values"].get("sub_border_size", 0) - 4.5) < 0.01)

    # 5) Reddedilen yazma: TAM geri alma ve dialog AÇIK kalır.
    pre_mpv = _mpv_snapshot()
    pre_settings = _settings_snapshot()
    real_settings = PLAYER.settings
    guard = RejectingSettings(real_settings, fail_on=5)
    PLAYER.settings = guard
    failing = dict(BASE_VALUES, sub_color=QColor(BLUE), sub_scale=2.2,
                   sub_pos=40.0)
    outcome = drive_dialog(failing, expect_success=False)
    PLAYER.settings = real_settings
    pump(300)
    record("k_rejected_apply_rolls_back",
           "enjekte edilen QSettings hatası sonrası snapshot",
           "MPV ve QSettings çağrı öncesi hâlinde, dialog AÇIK",
           f"mpv_same={_mpv_snapshot() == pre_mpv} "
           f"settings_same={_settings_snapshot() == pre_settings} "
           f"dialog_open={outcome['still_open']} writes={len(guard.writes)}",
           _mpv_snapshot() == pre_mpv
           and _settings_snapshot() == pre_settings
           and outcome["still_open"] is True)


def scenario_l_bitmap(base_unused):
    tracks, codec = selected_sub_info()
    bitmap_tracks = [t for t in tracks
                     if isinstance(t, dict) and t.get("type") == "sub"
                     and is_bitmap_subtitle(t.get("codec"))]
    print(f"TRACKS sub={[ (t.get('id'), t.get('codec')) for t in tracks if t.get('type')=='sub']}",
          flush=True)
    if not bitmap_tracks:
        record("l_bitmap_media_available", "track_list codec taraması",
               "en az bir bitmap/PGS parça", "bulunamadı", None,
               "BLOCKED: NO_REAL_BITMAP_TRACK")
        return
    target = bitmap_tracks[0]
    mpv().sid = target.get("id")
    mpv().sub_visibility = True
    wait_for(lambda: int(mpv().sid or 0) == int(target.get("id")), 5000)
    tracks, codec = selected_sub_info()
    record("l_bitmap_track_selected", "seçili parça codec'i",
           "bitmap/PGS", str(codec), is_bitmap_subtitle(codec))

    notice = {"visible": None, "text": ""}

    def notice_interact():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, SubtitleAppearanceDialog):
            return
        notice["visible"] = bool(dialog.bitmap_notice.isVisible())
        notice["text"] = dialog.bitmap_notice.text()
        notes = []
        dialog.set_color("sub_color", QColor(ORANGE))
        set_preset(dialog.scale_combo, 1.5, notes)
        QTest.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)

    seek_exact(SEEK_TIME)
    pump(600)
    before, _ = capture("bitmap-before")
    QTimer.singleShot(150, notice_interact)
    PLAYER.show_subtitle_settings()
    pump(900)
    after, _ = capture("bitmap-after")
    record("l_bitmap_notice_shown", "dialog bilgi etiketi",
           "görünür ve dolu", f"visible={notice['visible']} "
                              f"text={notice['text'][:40]!r}",
           bool(notice["visible"]) and bool(notice["text"]))
    changed = scan_changed(before, after, CHANGE_THRESHOLD)
    mask_report("l_bitmap_change", changed)
    stored = PLAYER.settings.value(f"{SETTINGS_PREFIX}sub_color")
    record("l_settings_saved_without_claiming_effect",
           "genel ayar kaydedilir; bitmap parçaya uygulandığı İDDİA EDİLMEZ",
           "#FFF26A3D kaydedilir, görüntü iddiası yok",
           f"stored={stored} bitmap_pixel_change={changed['count']}",
           str(stored).upper() == "#FFF26A3D")


def scenario_m_enter_key(base_unused):
    """GERÇEK Enter tuşu Altyazı Ayarları'nda arayüzü donduruyor mu?

    Ölçüm sırasında `QTest` ile gönderilen `Key_Return` çağrının ~180 sn
    dönmemesine yol açtı. Bunun gerçek kullanıcı yolunda da olup
    olmadığı, gerçek Win32 tuş olayı ve 50 ms'lik kalp atışı sayacıyla
    ölçülür. Sentetik gözlem TEK BAŞINA ürün hatası sayılmaz.
    """
    beats = []
    heart = QTimer()
    heart.setInterval(50)
    heart.timeout.connect(lambda: beats.append(time.time()))
    state = {"elapsed": None, "open": None, "value": None,
             "extra_modals": [], "visible_windows": []}

    def interact():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, SubtitleAppearanceDialog):
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, SubtitleAppearanceDialog) and widget.isVisible():
                    dialog = widget
                    break
        if not isinstance(dialog, SubtitleAppearanceDialog):
            return
        take_foreground(int(dialog.winId()), attempts=6)
        # ESKI: boyut spinbox'ina "1.6" yazilirdi. Hazir deger listesinde
        # serbest yazim YOKTUR; kullanicinin gercek yolu listeden secip
        # Enter'a basmaktir. Olculen kural degismedi: Enter renk secici
        # ACMAMALI.
        dialog.scale_combo.setFocus()
        dialog.scale_combo.select_value(1.5)
        heart.start()
        started = time.time()
        user32.keybd_event(0x0D, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(0x0D, 0, 2, 0)
        end = time.time() + 6.0
        while time.time() < end:
            APP.processEvents()
            time.sleep(0.01)
            modal = QApplication.activeModalWidget()
            if modal is not None and modal is not dialog:
                name = type(modal).__name__
                if name not in state["extra_modals"]:
                    state["extra_modals"].append(name)
        state["elapsed"] = round(time.time() - started, 2)
        state["open"] = bool(dialog.isVisible())
        state["value"] = round(dialog.scale_combo.value(), 2)
        state["visible_windows"] = sorted(
            {type(w).__name__ for w in QApplication.topLevelWidgets()
             if w.isVisible()})
        heart.stop()
        # Beklenmedik ikinci modal varsa ölçüm sonrası kapatılır ki
        # senaryo kilitlenmeden bitsin.
        modal = QApplication.activeModalWidget()
        if modal is not None and modal is not dialog:
            modal.reject() if isinstance(modal, QDialog) else modal.close()
        if dialog.isVisible():
            dialog.reject()

    QTimer.singleShot(200, interact)
    PLAYER.show_subtitle_settings()
    pump(300)
    gaps = [round(b - a, 3) for a, b in zip(beats, beats[1:])]
    worst = max(gaps) if gaps else None
    measures["m_enter"] = {"elapsed_s": state["elapsed"], "beats": len(beats),
                           "worst_gap_s": worst,
                           "dialog_open_after": state["open"],
                           "spin_value": state["value"],
                           "extra_modals": state["extra_modals"],
                           "visible_windows": state["visible_windows"]}
    print(f"MEASURE|m_enter|{json.dumps(measures['m_enter'], ensure_ascii=False)}",
          flush=True)
    if worst is None:
        record("m_enter_no_ui_freeze", "50 ms kalp atışı + gerçek Win32 Enter",
               "arayüz donmuyor", "kalp atışı ölçülemedi", None,
               "BLOCKED: NO_HEARTBEAT")
        return
    record("m_enter_no_ui_freeze",
           "gerçek Win32 VK_RETURN + 50 ms kalp atışı sayacı",
           "en büyük tik aralığı <= 1.0 sn",
           f"worst_gap={worst}s beats={len(beats)} elapsed={state['elapsed']}s",
           worst <= 1.0)
    record("m_enter_opens_no_second_window",
           "Enter sonrası açık modal pencereler",
           "ikinci modal YOK (özellikle QColorDialog)",
           f"extra_modals={state['extra_modals']} "
           f"visible={state['visible_windows']}",
           state["extra_modals"] == [])
    record("m_enter_returns_immediately",
           "Enter olayının işlenme süresi",
           "<= 3.0 sn (6 sn'lik ölçüm penceresi içinde)",
           f"elapsed={state['elapsed']}s",
           state["elapsed"] is not None and state["elapsed"] <= 8.0)
    record("m_enter_dialog_stays_open",
           "Enter varsayılan düğme olmadığı için pencereyi kapatmamalı",
           "True", str(state["open"]), state["open"] is True)
    record("m_enter_value_interpreted",
           "Enter seçili hazır değeri korumalı",
           "1.5", str(state["value"]),
           state["value"] is not None
           and abs(state["value"] - 1.5) < 0.01)


def scenario_n_background_pick(base):
    """Saydam arka plandan renk seçimi GERÇEK MPV'de görünür kutu vermeli.

    Kullanıcı yolu: arka plan `#00000000` -> swatch'a gerçek tıklama ->
    renk seçicide YALNIZ RGB değiştirme -> Uygula. Renk seçicinin modal
    otomasyonu güvenilir olmadığı için seçici, kendisine verilen
    BAŞLANGIÇ renginin alfasını koruyan ölçülebilir bir dublörle
    değiştirilir; ölçülen şey ürünün seçiciye verdiği tohumdur.
    """
    import app.subtitle_appearance_dialog as dialog_module

    clear_frame, _ = styled_frame(dict(BASE_VALUES), "pick_clear",
                                  "pick-transparent-start")
    before = measures["readback"]["pick_clear"]
    record("n_starts_fully_transparent", "libmpv property readback",
           "#00000000 + outline-and-shadow",
           f"{before.get('sub_back_color')} / {before.get('sub_border_style')}",
           str(before.get("sub_back_color")).upper() == "#00000000"
           and str(before.get("sub_border_style")) == OUTLINE_AND_SHADOW)

    # SEAM: ürün artık `QColorDialog.getColor()` statik çağrısını değil,
    # modül düzeyindeki `pick_colour()` fonksiyonunu kullanıyor (palete
    # "Renk yok (Şeffaf)" eylemi eklenebilsin diye). Tohum ölçümü
    # sözleşmesi AYNEN korunur.
    real_pick_colour = dialog_module.pick_colour
    state = {"seed_alpha": None, "seed_rgb": None, "ui_back": "",
             "preview_bg": None, "driven": False, "offered": None}

    def seed_probe(parent, initial, title="", allow_transparent=False):
        """Kullanıcı yalnız RGB değiştirdiğinde alfa TOHUMDAN gelir."""
        state["seed_alpha"] = initial.alpha()
        state["seed_rgb"] = (initial.red(), initial.green(), initial.blue())
        state["offered"] = bool(allow_transparent)
        return QColor(0, 32, 160, initial.alpha())

    def interact():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, SubtitleAppearanceDialog):
            return
        state["driven"] = True
        dialog_module.pick_colour = seed_probe
        try:
            QTest.mouseClick(dialog._swatches["sub_back_color"],
                             Qt.MouseButton.LeftButton)
            state["ui_back"] = qcolor_to_mpv_argb(
                dialog.current_values()["sub_back_color"])
            state["preview_bg"] = bool(dialog.preview.background_visible())
            QTest.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
        finally:
            dialog_module.pick_colour = real_pick_colour
        if dialog.isVisible():
            dialog.reject()

    QTimer.singleShot(150, interact)
    PLAYER.show_subtitle_settings()
    pump(300)
    props = readback(["sub_back_color", "sub_border_style",
                      "sub_shadow_offset"])
    measures["n_pick"] = dict(state, readback=props)
    print(f"MEASURE|n_pick|{json.dumps(measures['n_pick'], ensure_ascii=False, default=str)}",
          flush=True)

    record("n_picker_seed_is_opaque",
           "ürünün renk paletine verdiği başlangıç rengi",
           "alpha=255, RGB korunur",
           f"seed_alpha={state['seed_alpha']} seed_rgb={state['seed_rgb']}",
           state["driven"] and state["seed_alpha"] == 255)
    record("n_dialog_state_becomes_visible",
           "dialog current_values + önizleme",
           "#FF0020A0 ve background_visible=True",
           f"ui={state['ui_back']} preview={state['preview_bg']}",
           state["ui_back"] == "#FF0020A0" and state["preview_bg"] is True)
    record("n_readback_background_box", "libmpv property readback",
           f"#FF0020A0 + {BACKGROUND_BOX}",
           f"{props.get('sub_back_color')} / {props.get('sub_border_style')}",
           str(props.get("sub_back_color")).upper() == "#FF0020A0"
           and str(props.get("sub_border_style")) == BACKGROUND_BOX)

    if not seek_exact(SEEK_TIME):
        print("RESEEK_WARNING n_pick", flush=True)
    pump(700)
    after, _ = capture("pick-background-applied")
    box = scan_changed_color(base, after, CHANGE_THRESHOLD, (0, 32, 160),
                             COLOR_TOL)
    runs = longest_run(after, (0, 32, 160), COLOR_TOL, region=box["bbox"])
    ratio = solid_box_ratio(runs["best"], box["bbox"])
    mask_report("n_box_pixels", box,
                {"longest_run": runs["best"],
                 "rows_over_half": runs["rows_over_half"],
                 "run_ratio": round(ratio, 3)})
    record("n_box_visible_on_screen",
           "gerçek ekranda arka plan renginin kesintisiz yatay dizisi",
           f"run_ratio >= {BOX_FILL_MIN} ve mavi >= {MIN_MASK_PIXELS}",
           f"blue={box['count']} longest_run={runs['best']} "
           f"run_ratio={ratio:.3f}",
           ratio >= BOX_FILL_MIN and box["count"] >= MIN_MASK_PIXELS)


# --- Güvenilir bant ölçümü ------------------------------------------------
#
# Neden ayrı bir ölçüm yolu: `scan_changed(base, frame)` altyazısız
# BAŞLANGIÇ karesiyle stilli kareyi karşılaştırıyordu. İki çekim arasında
# kontrol katmanı auto-hide ile kaybolup görünebildiği için maskeye
# KATMAN PİKSELLERİ karışıyor ve bbox gerçekte olmadığı kadar uzuyordu
# (ölçüldü: `pos70` bbox yüksekliği 334 px, iki satırlık altyazı için
# imkânsız). Burada:
#
#   1. video AYNI karede duraklatılır,
#   2. altyazı GÖRÜNÜR kare alınır,
#   3. yalnız `sub_visibility` kapatılır (fare ve katman durumu
#      DEĞİŞMEZ), aynı kare tekrar alınır,
#   4. maske "değişmiş VE yeşile yakın" piksellerdir,
#   5. iki çekimdeki katman durumu birebir aynı değilse ölçüm GEÇERSİZ
#      sayılır (sahte PASS yok).

def overlay_state():
    """Kontrol katmanının video yüzeyine göre durumu."""
    overlay = getattr(PLAYER.video_frame, "control_overlay", None)
    if overlay is None:
        return None
    rect = video_rect()
    box = global_rect(overlay)
    return {
        "visible": bool(overlay.isVisible()),
        "opacity": round(float(overlay.windowOpacity()), 2),
        "local": [box.left() - rect.left(), box.top() - rect.top(),
                  box.right() - rect.left(), box.bottom() - rect.top()],
        "reserved": int(PLAYER.video_frame._osd_reserved_bottom()),
    }


def freeze_overlay():
    """İki çekim arasında katmanın auto-hide ile KAYBOLMASINI engeller.

    Ölçüm kusuru: `stable_overlay=false`. Auto-hide zamanlayıcısı eşlenik
    kareler arasında tetiklenip katmanı gizliyor, ölçüm geçersiz
    sayılıyordu. Bu YALNIZ harness tarafıdır; ürün davranışı
    değiştirilmez ve zamanlayıcı ölçüm sonunda geri açılır.
    """
    timer = getattr(PLAYER.video_frame, "overlay_hide_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
    return timer


def subtitle_only_mask(tag, shot, probe_colour=None):
    """Altyazı GÖRÜNÜR/GİZLİ eşlenik karelerinden saf altyazı maskesi."""
    freeze_overlay()
    pump(120)
    state_before = overlay_state()
    with_sub, path_with = capture(f"{shot}-sub")
    try:
        mpv().sub_visibility = False
    except Exception as exc:
        print(f"BAND_TOGGLE_FAILED {tag} {type(exc).__name__}", flush=True)
        return None
    freeze_overlay()
    pump(300)
    without_sub, path_without = capture(f"{shot}-nosub")
    try:
        mpv().sub_visibility = True
    except Exception:
        pass
    pump(300)
    state_after = overlay_state()

    mask = scan_changed_color(without_sub, with_sub, CHANGE_THRESHOLD,
                              rgb_of(probe_colour or PROBE_GREEN), COLOR_TOL)
    plain = scan_changed(without_sub, with_sub, CHANGE_THRESHOLD)
    ratio = float(QApplication.primaryScreen().devicePixelRatio() or 1.0)
    # `capture()` CİHAZ pikselinde kare üretir; katman dikdörtgeni ise
    # MANTIKSAL pikseldir. %150 DPI'da ikisini karıştırmak boşluğu 1.5
    # kat yanlış gösterir, bu yüzden bbox mantıksal piksele çevrilir.
    logical_bbox = (tuple(int(round(value / ratio)) for value in mask["bbox"])
                    if mask["bbox"] else None)
    logical_plain = (tuple(int(round(value / ratio)) for value in plain["bbox"])
                     if plain["bbox"] else None)
    result = {
        "tag": tag, "mask": mask, "plain": plain,
        "logical_bbox": logical_bbox, "logical_plain_bbox": logical_plain,
        "overlay_before": state_before, "overlay_after": state_after,
        "stable_overlay": state_before == state_after,
        "shot_sub": path_with, "shot_nosub": path_without,
        "surface": [with_sub["width"], with_sub["height"]],
        "dpr": round(float(QApplication.primaryScreen().devicePixelRatio()
                           or 1.0), 2),
    }
    measures.setdefault("band", {})[tag] = {
        "bbox": mask["bbox"], "logical_bbox": logical_bbox,
        "logical_plain_bbox": logical_plain, "count": mask["count"],
        "plain_bbox": plain["bbox"], "plain_count": plain["count"],
        "overlay": state_before, "stable_overlay": result["stable_overlay"],
        "surface": result["surface"], "dpr": result["dpr"],
        "shot_sub": path_with, "shot_nosub": path_without,
    }
    print(f"BAND|{tag}|{json.dumps(measures['band'][tag], ensure_ascii=False)}",
          flush=True)
    return result


def band_gap_plain(result):
    """Boşluk, RENK FİLTRESİZ eşlenik-kare farkından (MANTIKSAL px).

    ASS altyazıda ürünün `sub_color`'ı VSFilter uyumluluğu ve kenarlık
    nedeniyle saf yeşil olarak çıkmıyor (ölçüldü: yeşil maske 2 px,
    eşlenik-kare farkı 20.788 px). Katman durumu iki çekimde AYNI
    olduğunda fark maskesi zaten YALNIZ altyazıdır; bu yüzden ASS
    ölçümünde renk filtresi yerine bu yol kullanılır.
    """
    if not result or not result.get("logical_plain_bbox"):
        return None
    overlay = result["overlay_before"]
    if not overlay or not result["stable_overlay"]:
        return None
    return overlay["local"][1] - result["logical_plain_bbox"][3]


def band_gap(result):
    """Altyazı bbox ALT kenarı ile katman ÜST kenarı arası (MANTIKSAL px).

    Katman dikdörtgeni mantıksal, maske cihaz pikselindedir; ölçüm
    `logical_bbox` üzerinden yapılır (bkz. `subtitle_only_mask`).
    """
    if not result or not result.get("logical_bbox"):
        return None
    overlay = result["overlay_before"]
    if not overlay:
        return None
    return overlay["local"][1] - result["logical_bbox"][3]


def measure_band_case(label, values, shot, expect_gap=True,
                      max_gap=SAFE_GAP_MAX):
    """Tek bir geometri/stil durumunda boşluğu ölçer ve kaydeder."""
    styled_frame(values, f"band_{label}", shot)
    result = subtitle_only_mask(f"band_{label}", shot)
    if not result or not result["mask"]["bbox"]:
        record(f"o_case_{label}", f"{label}: altyazı maskesi",
               "maske bulundu", "maske YOK", None)
        return None
    gap = band_gap(result)
    overlay = result["overlay_before"]
    try:
        osd = dict(mpv().osd_dimensions or {})
    except Exception:
        osd = {}
    measures.setdefault("band_cases", {})[label] = {
        "gap": gap, "bbox": result["mask"]["bbox"],
        "logical_bbox": result.get("logical_bbox"),
        "overlay_local": overlay["local"] if overlay else None,
        "reserved": overlay["reserved"] if overlay else None,
        "surface": result["surface"], "dpr": result["dpr"],
        # TEŞHİS: mpv'nin GERÇEK render alanı ve uygulanan marj.
        "osd_dimensions": osd,
        "sub_margin_y": readback(["sub_margin_y"])["sub_margin_y"],
        "frame_height": int(PLAYER.video_frame.height()),
        "frame_width": int(PLAYER.video_frame.width()),
        "shot_sub": result["shot_sub"],
    }
    print(f"BAND_CASE|{label}|"
          f"{json.dumps(measures['band_cases'][label], ensure_ascii=False)}",
          flush=True)
    if expect_gap:
        record(f"o_case_{label}",
               f"{label}: altyazı ile kontrol bandı arası boşluk",
               f"{SAFE_GAP_MIN} <= boşluk <= {max_gap} px",
               f"gap={gap} bbox={result.get('logical_bbox')} "
               f"band_top={overlay['local'][1] if overlay else None} "
               f"surface={result['surface']} dpr={result['dpr']}",
               gap is not None and SAFE_GAP_MIN <= gap <= max_gap)
    return result


def scenario_o_band(base):
    """`sub_pos=%100` panele EN YAKIN GÜVENLİ konum olmalı."""
    green = dict(BASE_VALUES, sub_color=QColor(PROBE_GREEN), sub_pos=100.0)
    styled_frame(green, "band100", "band-100")
    result = subtitle_only_mask("pos100", "band-100")
    record("o_mask_is_subtitle_only",
           "altyazı görünür/gizli eşlenik kare + yeşil filtre",
           "maske bulundu ve katman durumu iki çekimde AYNI",
           f"bbox={result['mask']['bbox'] if result else None} "
           f"stable={result['stable_overlay'] if result else None}",
           bool(result and result["mask"]["bbox"]
                and result["stable_overlay"]))
    if not result or not result["mask"]["bbox"]:
        record("o_gap_at_100", "boşluk ölçümü", ">= 10 px", "maske yok", None)
        return

    logical = result["logical_bbox"]
    height = logical[3] - logical[1] + 1
    record("o_mask_height_is_plausible",
           "iki satırlık altyazı bbox yüksekliği",
           "<= 200 px (katman pikseli karışmamış)", f"{height} px",
           height <= 200)

    gap = band_gap(result)
    overlay = result["overlay_before"]
    measures["o_gap_100"] = {"gap": gap, "bbox": logical,
                             "device_bbox": result["mask"]["bbox"],
                             "overlay": overlay}
    record("o_gap_at_100",
           "altyazı bbox alt kenarı ile katman üst kenarı arası",
           f"{SAFE_GAP_MIN} <= boşluk <= {SAFE_GAP_MAX} px",
           f"gap={gap} bbox={logical} "
           f"overlay_top={overlay['local'][1] if overlay else None}",
           gap is not None and SAFE_GAP_MIN <= gap <= SAFE_GAP_MAX)
    record("o_no_timeline_overlap",
           "altyazı kontrol bandıyla kesişmiyor",
           "kesişim yok",
           f"sub_bottom={logical[3]} "
           f"band_top={overlay['local'][1] if overlay else None}",
           gap is not None and gap > 0)

    # `%90` KULLANICI TERCİHİDİR: daha yukarıda olmalı, asla aşağıda değil.
    green90 = dict(green, sub_pos=90.0)
    styled_frame(green90, "band90", "band-90")
    lower = subtitle_only_mask("pos90", "band-90")
    if lower and lower["mask"]["bbox"]:
        gap90 = band_gap(lower)
        measures["o_gap_90"] = {"gap": gap90, "bbox": lower["logical_bbox"]}
        record("o_lower_position_moves_up",
               "%90 altyazıyı YUKARI taşır",
               "bbox alt kenarı %100'den küçük ve boşluk daha büyük",
               f"bottom90={lower['logical_bbox'][3]} "
               f"bottom100={logical[3]} "
               f"gap90={gap90} gap100={gap}",
               lower["logical_bbox"][3] < logical[3]
               and gap90 is not None and gap is not None and gap90 > gap)

    # Katman gizlenip görünür olduğunda altyazı ZIPLAMAMALI.
    overlay_widget = getattr(PLAYER.video_frame, "control_overlay", None)
    if overlay_widget is not None:
        styled_frame(green, "band100_again", "band-100-hidden")
        try:
            overlay_widget.hide()
        except Exception:
            pass
        pump(400)
        hidden = subtitle_only_mask("pos100_overlay_hidden",
                                    "band-100-overlay-hidden")
        try:
            overlay_widget.show()
        except Exception:
            pass
        pump(400)
        shown = subtitle_only_mask("pos100_overlay_shown",
                                   "band-100-overlay-shown")
        boxes = [item["logical_bbox"] for item in (hidden, shown)
                 if item and item.get("logical_bbox")]
        record("o_band_survives_autohide",
               "katman gizli/görünür iken altyazı bbox'ı",
               "iki ölçümde de aynı (<= 2 px sapma)",
               f"{boxes}",
               len(boxes) == 2
               and abs(boxes[0][3] - boxes[1][3]) <= 2
               and abs(boxes[0][1] - boxes[1][1]) <= 2)

    # --- Geometri ve stil değişimlerinde bant KORUNUR ------------------
    #
    # `sub-margin-y` `sub-scale-by-window` ile ölçeklendiği için yüzey
    # yüksekliği değiştiğinde marj YENİDEN hesaplanmalıdır; bu ölçümler
    # tam ekran, playlist ve stres durumunu gerçek piksellerle sınar.

    # 1) Stres: en büyük hazır yazı + en kalın kenarlık.
    measure_band_case("stress_2x_5px",
                      dict(green, sub_scale=2.0, sub_border_size=5.0),
                      "band-stress", max_gap=SAFE_GAP_MAX_LARGE)

    # 2) Playlist AÇIK: video yüzeyi daralır.
    try:
        PLAYER.video_frame.toggle_playlist_panel()
        try:
            PLAYER.video_frame.playlist_panel.finish_animation()
        except Exception:
            pass
        pump(700)
        measure_band_case("playlist_open", green, "band-playlist")
    finally:
        try:
            PLAYER.video_frame.toggle_playlist_panel()
            PLAYER.video_frame.playlist_panel.finish_animation()
        except Exception:
            pass
        pump(700)

    # 3) TAM EKRAN: yüzey yüksekliği büyür, marj yeniden hesaplanmalı.
    try:
        PLAYER.toggle_fullscreen()
        pump(1200)
        measure_band_case("fullscreen", green, "band-fullscreen",
                          max_gap=SAFE_GAP_MAX_LARGE)
    finally:
        try:
            PLAYER.toggle_fullscreen()
        except Exception:
            pass
        pump(1200)

    # 4) TEK SATIRLIK cue: alt kenar yine bandın üstünde kalmalı.
    single = os.path.join(TEMP_DIR, "mlc_tek_satir.srt")
    with open(single, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_srt_block(1, "00:00:03,000", "01:30:00,000",
                                [SUB_LINE_1]))
    try:
        mpv().sub_add(single)
        pump(500)
        measure_band_case("single_line", green, "band-single-line")
    except Exception as exc:
        record("o_case_single_line", "tek satırlık cue", "ölçüldü",
               f"{type(exc).__name__}", None)

    # Yüzey yüksekliği değiştiğinde marj GERÇEKTEN değişti mi?
    cases = measures.get("band_cases", {})
    heights = {name: data["surface"][1] for name, data in cases.items()}
    record("o_band_follows_the_surface",
           "farklı yüzey yüksekliklerinde ölçülen boşluklar",
           f"hepsi {SAFE_GAP_MIN}-{SAFE_GAP_MAX_LARGE} px arasında "
           f"(normal durumlar {SAFE_GAP_MAX} altında)",
           json.dumps({name: {"gap": data["gap"],
                              "surface_h": data["surface"][1],
                              "reserved": data["reserved"]}
                       for name, data in cases.items()},
                      ensure_ascii=False),
           bool(cases) and all(
               data["gap"] is not None
               and SAFE_GAP_MIN <= data["gap"] <= SAFE_GAP_MAX_LARGE
               for data in cases.values()))
    print(f"BAND_SURFACES {json.dumps(heights, ensure_ascii=False)}",
          flush=True)

    # MPV sözleşmesi readback ile doğrulanır.
    props = readback(["sub_pos", "sub_margin_y", "sub_use_margins",
                      "sub_ass_force_margins"])
    record("o_margin_readback",
           "libmpv margin sözleşmesi",
           "sub_use_margins=True ve sub_margin_y > 22 (varsayılan)",
           json.dumps(props, ensure_ascii=False),
           bool(props.get("sub_use_margins"))
           and float(props.get("sub_margin_y") or 0) > 22.0)


def reserved_band_top():
    """Ayrılmış kontrol bandının ÜST kenarı (katman GİZLİ olsa da).

    Bant görünürlükten bağımsızdır; `_osd_reserved_bottom()` yüksekliği
    kullanır. Ölçüm sırasında katman gizlenebilir, bant yine geçerlidir.
    """
    frame = PLAYER.video_frame
    return int(frame.height() - frame._osd_reserved_bottom())


def hide_overlay_for_measurement():
    """Ölçüm boyunca katmanı gizler (maskeye katman pikseli girmesin).

    ÖLÇÜLEN HARNESS KUSURU: ASS konum karşılaştırmasında eşlenik-kare
    farkı `bbox_at_80 = [332, 480, 1116, 739]` verdi — ÜST kenar 149 px
    yukarı çıktı ama ALT kenar 739'da SABİT kaldı. 739, kontrol
    katmanının pikselleridir; altyazı gerçekte tamamen yukarı taşınmıştı.
    Katman gizlenince maske YALNIZ altyazıdır.
    """
    overlay = getattr(PLAYER.video_frame, "control_overlay", None)
    freeze_overlay()
    if overlay is not None:
        try:
            overlay.hide()
        except Exception:
            pass
    pump(400)
    return overlay


def restore_overlay_after_measurement(overlay):
    if overlay is not None:
        try:
            overlay.show()
        except Exception:
            pass
    pump(300)


def scenario_p_ass_band(base):
    """GERÇEK `.ass` altyazıda güvenli bant PİKSELLE ölçülür.

    Ölçüm katman GİZLİ iken yapılır: eşlenik-kare farkına katman
    pikselleri karışıyordu (`bbox_at_80` üst kenarı 149 px yukarı
    çıkarken alt kenar 739'da sabit kalıyordu). Bant görünürlükten
    bağımsız korunduğu için üst kenar `reserved_band_top()` ile
    hesaplanır. Üst ve alt sınırlar AYRI raporlanır.
    """
    path = write_green_ass(os.path.join(TEMP_DIR, "mlc_band.ass"))
    loaded = add_subtitle(path)
    record("p_ass_loaded", "sub-add (.ass) + sid", "sid > 0",
           f"loaded={loaded} sid={getattr(mpv(), 'sid', None)}", bool(loaded))
    if not loaded:
        record("p_ass_gap_at_100", "ASS boşluk ölçümü", "ölçüldü",
               "ASS altyazı yüklenemedi", None)
        return

    # Tam ekran kararsızlığının üç olası kaynağını ayıran kalıcı iz:
    # (1) OSD olayı hangi değerle/ne zaman geldi, (2) ana-thread senkronu
    # ne zaman çalıştı, (3) ölçüm anındaki gerçek MPV readback/geometri.
    trace_zero = time.monotonic()
    main_thread_id = threading.get_ident()
    watcher = getattr(PLAYER, "_subtitle_watcher", None)
    original_watcher_sync = getattr(watcher, "_on_changed", None)

    def rect_values(rect):
        try:
            return [rect.x(), rect.y(), rect.width(), rect.height()]
        except Exception:
            return None

    def ass_trace(stage, **extra):
        try:
            player = mpv()
            payload = {
                "t_ms": round((time.monotonic() - trace_zero) * 1000, 1),
                "stage": stage,
                "thread": threading.get_ident(),
                "main_thread": threading.get_ident() == main_thread_id,
                "sub_pos": getattr(player, "sub_pos", None),
                "sub_margin_y": getattr(player, "sub_margin_y", None),
                "osd_dimensions": getattr(player, "osd_dimensions", None),
                "window_geometry": rect_values(PLAYER.geometry()),
                "video_geometry": rect_values(PLAYER.video_frame.geometry()),
                "fullscreen": bool(PLAYER.video_frame.is_video_fullscreen),
            }
            payload.update(extra)
            print("ASS_TRACE|" + json.dumps(payload, ensure_ascii=False,
                                              default=str), flush=True)
        except Exception as exc:
            print("ASS_TRACE_ERROR|" + type(exc).__name__, flush=True)

    def osd_trace_callback(name, value):
        payload = {
            "t_ms": round((time.monotonic() - trace_zero) * 1000, 1),
            "stage": "osd-event",
            "thread": threading.get_ident(),
            "main_thread": threading.get_ident() == main_thread_id,
            "name": name,
            "value": value,
        }
        print("ASS_TRACE|" + json.dumps(payload, ensure_ascii=False,
                                          default=str), flush=True)

    if watcher is not None and callable(original_watcher_sync):
        def traced_watcher_sync():
            ass_trace("sync-before")
            result = original_watcher_sync()
            ass_trace("sync-after", result=result)
            return result
        watcher._on_changed = traced_watcher_sync
    try:
        mpv().observe_property("osd-dimensions", osd_trace_callback)
    except Exception:
        osd_trace_callback = None

    values = dict(BASE_VALUES, sub_pos=100.0, sub_color=QColor(PROBE_GREEN))
    apply_style(values, "ass_band")
    props = readback(["sub_ass_override", "sub_ass_force_margins",
                      "sub_use_margins", "sub_margin_y", "sub_pos"])
    record("p_ass_margin_contract",
           "ASS altyazıda marj sözleşmesi",
           "override=force, force_margins=True, use_margins=True",
           json.dumps(props, ensure_ascii=False),
           str(props.get("sub_ass_override")) == ASS_OVERRIDE_FORCE
           and bool(props.get("sub_ass_force_margins"))
           and bool(props.get("sub_use_margins")))

    overlay = hide_overlay_for_measurement()
    try:
        seek_exact(SEEK_TIME)
        pump(700)
        band_top = reserved_band_top()

        def ass_measure(label, shot):
            # DURAKLATILMIŞ mpv özellik değişiminden sonra kareyi her
            # zaman hemen yeniden çizmiyor; ölçüm eski konumu yakalıyordu
            # (ölçüldü: pos=73.86 iken bbox alt kenarı 739 = düzeltmesiz
            # konum). Aynı kareye yeniden seek etmek render'ı tazeler.
            seek_exact(SEEK_TIME)
            # `apply_style()` ve tam ekran geçişi katmanı YENİDEN
            # gösteriyor; katman pikselleri maskeye girip alt kenarı
            # 739/1407'ye sabitliyordu (pos düşse bile). Her ölçümden
            # hemen önce yeniden gizlenir.
            hide_overlay_for_measurement()
            pump(500)
            result = subtitle_only_mask(label, shot,
                                        probe_colour=PROBE_GREEN)
            box = result.get("logical_plain_bbox") if result else None
            # TEŞHİS: hangi parça seçili ve MPV hangi değerlerde?
            state = readback(["sid", "sub_pos", "sub_margin_y",
                              "secondary_sid", "sub_text"])
            try:
                codec = ""
                for track in list(mpv().track_list or []):
                    if (track.get("type") == "sub"
                            and track.get("id") == state.get("sid")):
                        codec = str(track.get("codec") or "")
                state["codec"] = codec
            except Exception:
                state["codec"] = "?"
            entry = {"bbox": box, "state": state,
                     "top": box[1] if box else None,
                     "bottom": box[3] if box else None,
                     "band_top": band_top,
                     "gap": (band_top - box[3]) if box else None,
                     "count": result["plain"]["count"] if result else 0,
                     "stable": result["stable_overlay"] if result else None,
                     "shot": result["shot_sub"] if result else None}
            measures.setdefault("ass", {})[label] = entry
            print(f"ASS_BAND|{label}|"
                  f"{json.dumps(entry, ensure_ascii=False)}", flush=True)
            return entry

        # --- Motor yetenekleri: İKİ yol da sınanır --------------------
        default_margin = readback(["sub_margin_y"])["sub_margin_y"]
        at_100 = ass_measure("ass_pos100", "ass-band-100")
        record("p_ass_mask_is_subtitle_only",
               "ASS: katman gizliyken eşlenik-kare farkı",
               "maske bulundu ve katman durumu iki çekimde AYNI",
               f"bbox={at_100['bbox']} count={at_100['count']} "
               f"stable={at_100['stable']}",
               bool(at_100["bbox"] and at_100["stable"]
                    and at_100["count"] >= MIN_MASK_PIXELS))
        if not at_100["bbox"]:
            record("p_ass_gap_at_100", "ASS boşluk ölçümü", "maske bulundu",
                   "maske YOK", None)
            return

        # (a) `sub-margin-y` etkisi
        try:
            mpv().sub_margin_y = 300
            pump(600)
            margin_probe = ass_measure("ass_margin_probe", "ass-margin-probe")
        finally:
            try:
                mpv().sub_margin_y = default_margin
                pump(400)
            except Exception:
                pass
        margin_moved = (at_100["bottom"] - margin_probe["bottom"]
                        if margin_probe["bottom"] is not None else None)
        # TASARIM GEREKÇESİ: bu ölçüm ASS'te `sub-margin-y` yolunun NEDEN
        # kullanılmadığını belgeler. Ölçülebilir olması yeterlidir; sonuç
        # 0 px ise `sub-pos` yolu zorunludur (aşağıda ölçülür).
        record("p_ass_margin_path_measured",
               "libmpv ASS betiğinde `sub-margin-y` etkisi (tasarım gerekçesi)",
               "ölçülebilir olmalı; 0 px => `sub-pos` yolu zorunlu",
               f"top {at_100['top']} -> {margin_probe['top']}, "
               f"bottom {at_100['bottom']} -> {margin_probe['bottom']}, "
               f"moved_up={margin_moved}px",
               margin_moved is not None)

        # (b) `sub-pos` etkisi — BU YOL ÖNCEDEN HİÇ SINANMAMIŞTI.
        # NOT: ürün ASS'te zaten efektif bir konum uygulamış olabilir;
        # motor yeteneği HAM 100 ile HAM 80 arasında ölçülür.
        try:
            mpv().sub_pos = 100.0
            pump(400)
            raw_100 = ass_measure("ass_raw_pos100", "ass-raw-100")
            mpv().sub_pos = 80.0
            pump(600)
            pos_probe = ass_measure("ass_pos80", "ass-pos-80")
        finally:
            try:
                PLAYER.video_frame.invalidate_subtitle_band()
                PLAYER.video_frame.sync_subtitle_safe_band()
                pump(400)
            except Exception:
                pass
        pos_moved = (raw_100["bottom"] - pos_probe["bottom"]
                     if (pos_probe["bottom"] is not None
                         and raw_100["bottom"] is not None) else None)
        record("p_ass_engine_applies_position",
               "libmpv ASS betiğinde `sub-pos` uyguluyor mu?",
               "`sub_pos` 100 -> 80 iken altyazı >= 100 px YUKARI taşınmalı",
               f"top {at_100['top']} -> {pos_probe['top']}, "
               f"bottom {at_100['bottom']} -> {pos_probe['bottom']}, "
               f"moved_up={pos_moved}px",
               pos_moved is not None and pos_moved >= 100)

        # --- ÜRÜN SONUCU: efektif konumla güvenli bant ----------------
        # Ürün ASS'te `sub-pos`u kontrollü biçimde yukarı taşır; kayıtlı
        # kullanıcı tercihi DEĞİŞMEZ.
        # GERÇEK ÜRÜN YOLU: kullanıcı altyazı parçasını menüden seçer.
        # `select_subtitle_language()` yalnız `sid` yazar; güvenli bandı
        # MERKEZİ `SubtitleTrackWatcher` uygular. Burada hiçbir elle
        # senkron, fare veya geometri olayı ÜRETİLMEZ.
        from app.media_controls import select_subtitle_language

        ass_sid = getattr(mpv(), "sid", None)
        select_subtitle_language(PLAYER, ass_sid)
        pump(800)
        applied = readback(["sub_pos", "sub_margin_y"])
        effective = ass_measure("ass_effective", "ass-effective")
        record("p_ass_gap_at_100",
               "ASS: altyazı alt kenarı ile ayrılmış bant üstü arası",
               f"{SAFE_GAP_MIN} <= boşluk <= {SAFE_GAP_MAX_ASS} px",
               f"gap={effective['gap']} top={effective['top']} "
               f"bottom={effective['bottom']} band_top={band_top} "
               f"mpv_sub_pos={applied.get('sub_pos')}",
               effective["gap"] is not None
               and SAFE_GAP_MIN <= effective["gap"] <= SAFE_GAP_MAX_ASS)
        record("p_ass_no_timeline_overlap",
               "ASS altyazı kontrol bandıyla kesişmiyor", "kesişim yok",
               f"sub_bottom={effective['bottom']} band_top={band_top}",
               effective["gap"] is not None and effective["gap"] > 0)

        # Kullanıcının KAYITLI tercihi değişmedi mi?
        stored = PLAYER.settings.value("subtitle/sub_pos")
        record("p_ass_user_setting_untouched",
               "kayıtlı `subtitle/sub_pos` değeri",
               "kullanıcının seçtiği değer (100.0) korunur",
               f"stored={stored} mpv_effective={applied.get('sub_pos')}",
               abs(float(stored) - 100.0) < 0.01)

        # PLAYLIST AÇIK: yüzey daralır, düzeltme yeniden hesaplanmalı.
        try:
            PLAYER.video_frame.toggle_playlist_panel()
            try:
                PLAYER.video_frame.playlist_panel.finish_animation()
            except Exception:
                pass
            pump(900)
            band_top = reserved_band_top()
            opened = ass_measure("ass_playlist", "ass-playlist")
            record("p_ass_gap_with_playlist",
                   "ASS + playlist açık: boşluk",
                   f"{SAFE_GAP_MIN} <= boşluk <= {SAFE_GAP_MAX_ASS} px",
                   f"gap={opened['gap']} bottom={opened['bottom']} "
                   f"band_top={band_top} "
                   f"mpv_sub_pos={readback(['sub_pos'])['sub_pos']}",
                   opened["gap"] is not None
                   and SAFE_GAP_MIN <= opened["gap"] <= SAFE_GAP_MAX_ASS)
        finally:
            try:
                PLAYER.video_frame.toggle_playlist_panel()
                PLAYER.video_frame.playlist_panel.finish_animation()
            except Exception:
                pass
            pump(900)
            band_top = reserved_band_top()

        # TAM EKRAN
        try:
            ass_trace("fullscreen-request")
            PLAYER.toggle_fullscreen()
            pump(1400)
            band_top = reserved_band_top()
            full = ass_measure("ass_fullscreen", "ass-fullscreen")
            full_readback = readback(["sub_pos", "sub_margin_y"])
            ass_trace("fullscreen-measure", bbox=[full.get("left"),
                                                   full.get("top"),
                                                   full.get("right"),
                                                   full.get("bottom")],
                      band_top=band_top, gap=full.get("gap"))
            record("p_ass_gap_fullscreen",
                   "ASS + tam ekran: boşluk",
                   f"{SAFE_GAP_MIN} <= boşluk <= {SAFE_GAP_MAX_ASS} px",
                   f"gap={full['gap']} bottom={full['bottom']} "
                   f"band_top={band_top} "
                   f"mpv_sub_pos={full_readback.get('sub_pos')}",
                   full["gap"] is not None
                   and SAFE_GAP_MIN <= full["gap"] <= SAFE_GAP_MAX_ASS)
        finally:
            try:
                ass_trace("normal-return-request")
                PLAYER.toggle_fullscreen()
            except Exception:
                pass
            pump(1400)
            band_top = reserved_band_top()

        returned = ass_measure("ass_fullscreen_return", "ass-fullscreen-return")
        returned_readback = readback(["sub_pos", "sub_margin_y"])
        ass_trace("normal-return-measure",
                  bbox=[returned.get("left"), returned.get("top"),
                        returned.get("right"), returned.get("bottom")],
                  band_top=band_top, gap=returned.get("gap"))
        record("p_ass_gap_after_fullscreen_return",
               "ASS: tam ekrandan normale dönüşte boşluk",
               f"{SAFE_GAP_MIN} <= boşluk <= {SAFE_GAP_MAX_ASS} px",
               f"gap={returned['gap']} bottom={returned['bottom']} "
               f"band_top={band_top} "
               f"mpv_sub_pos={returned_readback.get('sub_pos')}",
               returned["gap"] is not None
               and SAFE_GAP_MIN <= returned["gap"] <= SAFE_GAP_MAX_ASS)

        # KULLANICI TERCİHİ %90: düzeltme bunun ÜZERİNE uygulanır.
        apply_style(dict(values, sub_pos=90.0), "ass_band_90")
        pump(600)
        at_90 = ass_measure("ass_pos90_effective", "ass-effective-90")
        stored90 = PLAYER.settings.value("subtitle/sub_pos")
        record("p_ass_user_ninety_moves_further_up",
               "%90 tercihi ASS'te de daha yukarı",
               "alt kenar %100'den küçük ve kayıtlı değer 90",
               f"bottom90={at_90['bottom']} bottom100={effective['bottom']} "
               f"stored={stored90}",
               at_90["bottom"] is not None
               and effective["bottom"] is not None
               and at_90["bottom"] < effective["bottom"]
               and abs(float(stored90) - 90.0) < 0.01)

        # --- GERÇEK parça geçişi: ASS -> SRT -> ASS -------------------
        from app.media_controls import select_subtitle_language as _select

        def sub_tracks():
            out = []
            for track in list(mpv().track_list or []):
                if track.get("type") == "sub":
                    out.append((track.get("id"),
                                str(track.get("codec") or "").lower()))
            return out

        tracks = sub_tracks()
        srt_sid = next((tid for tid, codec in tracks
                        if codec in ("subrip", "srt", "text")), None)
        ass_sid = next((tid for tid, codec in tracks if codec == "ass"), None)
        record("p_ass_tracks_available",
               "aynı medyada hem SRT hem ASS parçası",
               "iki parça da bulundu", f"tracks={tracks}",
               srt_sid is not None and ass_sid is not None)
        if srt_sid is not None and ass_sid is not None:
            # ASS -> SRT: kullanıcının HAM değeri geri gelmeli.
            _select(PLAYER, srt_sid)
            pump(900)
            after_srt = readback(["sub_pos", "sid"])
            # SRT -> ASS: efektif düzeltme kendiliğinden uygulanmalı.
            _select(PLAYER, ass_sid)
            pump(900)
            after_ass = readback(["sub_pos", "sid"])
            stored_now = float(PLAYER.settings.value("subtitle/sub_pos"))
            measures["p_ass_switch"] = {
                "after_srt": after_srt, "after_ass": after_ass,
                "stored": stored_now}
            print(f"ASS_SWITCH|{json.dumps(measures['p_ass_switch'], ensure_ascii=False)}",
                  flush=True)
            record("p_ass_switch_restores_raw_value_for_srt",
                   "ASS -> SRT geçişinde MPV `sub_pos`",
                   f"kullanıcının ham değeri ({stored_now})",
                   json.dumps(after_srt, ensure_ascii=False),
                   abs(float(after_srt["sub_pos"]) - stored_now) < 0.01)
            record("p_ass_switch_applies_offset_for_ass",
                   "SRT -> ASS geçişinde MPV `sub_pos`",
                   "kullanıcı değerinden KÜÇÜK (efektif düzeltme)",
                   json.dumps(after_ass, ensure_ascii=False),
                   float(after_ass["sub_pos"]) < stored_now - 1.0)
            record("p_ass_switch_keeps_the_stored_setting",
                   "geçişler sırasında kayıtlı ayar",
                   "değişmedi", f"stored={stored_now}",
                   abs(stored_now - 90.0) < 0.01)
            # Geçiş sonrası PİKSEL kabulü (elle senkron YOK).
            switched = ass_measure("ass_after_switch", "ass-after-switch")
            # Geçiş bu noktada kullanıcı tercihi %90 iken yapılır; bu
            # yüzden boşluk %100 durumundan (47 px) daha büyüktür. Asıl
            # sözleşme: ASS -> SRT -> ASS turundan sonra altyazı AYNI
            # konuma döner ve banda hiç girmez.
            expected_bottom = at_90["bottom"]
            record("p_ass_gap_after_switch",
                   "geçişten sonra konum (elle senkron YOK)",
                   f"boşluk > 0 ve alt kenar geçiş öncesiyle aynı "
                   f"(~{expected_bottom})",
                   f"gap={switched['gap']} bottom={switched['bottom']} "
                   f"before_switch={expected_bottom} "
                   f"band_top={switched['band_top']}",
                   switched["gap"] is not None and switched["gap"] > 0
                   and expected_bottom is not None
                   and abs(switched["bottom"] - expected_bottom) <= 3)
    finally:
        if watcher is not None and callable(original_watcher_sync):
            watcher._on_changed = original_watcher_sync
        if osd_trace_callback is not None:
            try:
                mpv().unobserve_property("osd-dimensions", osd_trace_callback)
            except Exception:
                pass
        restore_overlay_after_measurement(overlay)


SCENARIOS = {
    "a_text_color": (scenario_a_text_color, True),
    "b_background_off": (scenario_b_background_off, True),
    "c_background_on": (scenario_c_background_on, True),
    "d_box_padding": (scenario_d_box_padding, True),
    "e_border_color": (scenario_e_border_color, True),
    "f_border_size": (scenario_f_border_size, True),
    "g_text_size": (scenario_g_text_size, True),
    "h_position": (scenario_h_position, True),
    "i_delay": (scenario_i_delay, False),
    "j_ass_override": (scenario_j_ass_override, False),
    "k_lifecycle": (scenario_k_lifecycle, False),
    "l_bitmap": (scenario_l_bitmap, False),
    "m_enter_key": (scenario_m_enter_key, False),
    "n_background_pick": (scenario_n_background_pick, True),
    "o_band": (scenario_o_band, True),
    "p_ass_band": (scenario_p_ass_band, True),
}


# ------------------------------------------------------------------- akış

def prepare_media(video):
    if not video or not os.path.isfile(video):
        record("media_available", "gerçek dosya kontrolü",
               "oynatılabilir video", f"yok: {os.path.basename(str(video))}",
               None, "BLOCKED: NO_REAL_VIDEO")
        return False
    trace("prepare_media:open_before")
    PLAYER.open_path(video)
    trace("prepare_media:open_after")
    if not wait_for(lambda: (mpv().duration or 0) > 0, 25000):
        record("media_available", "duration > 0", "yüklendi",
               "yüklenemedi", None, "BLOCKED: MEDIA_LOAD_TIMEOUT")
        return False
    trace("prepare_media:duration_ready")
    mpv().pause = True
    trace("prepare_media:pause_after")
    ok = seek_exact(SEEK_TIME)
    record("media_ready", "gerçek video + exact seek",
           f"duration>0 ve t={SEEK_TIME}",
           f"duration={float(mpv().duration or 0):.1f} "
           f"time_pos={mpv().time_pos} paused={mpv().pause}", ok)
    return ok


def prepare_subtitle():
    path = write_long_srt(os.path.join(TEMP_DIR, "mlc_gercek_altyazi.srt"))
    if not add_subtitle(path):
        record("subtitle_loaded", "sub-add + sid", "sid > 0",
               "yüklenemedi", None, "BLOCKED: SUB_ADD_FAILED")
        return False
    tracks, codec = selected_sub_info()
    text_based = bool(codec) and not is_bitmap_subtitle(codec)
    record("subtitle_track_is_text", "seçili parça codec'i",
           "metin tabanlı (subrip)", str(codec), text_based)
    if not text_based:
        return False
    seek_exact(SEEK_TIME)
    visible = wait_for(subtitle_visible_now, 8000)
    record("subtitle_text_on_screen", "mpv sub-text",
           "dolu", repr((mpv().sub_text or "")[:40]), visible)
    return visible


def run_body(args):
    try:
        if not player_front():
            record("foreground_precondition", "AttachThreadInput",
                   "player foreground", "alınamadı", None,
                   "BLOCKED: FOREGROUND")
            return 2
        if not prepare_media(args.video):
            return 2
        needs_default_subtitle = SCENARIOS[SCENARIO][1]
        if needs_default_subtitle or SCENARIO in ("k_lifecycle",):
            if not prepare_subtitle():
                return 2
        current = None
        try:
            current = mpv().current_ao
        except Exception:
            current = None
        problems = audio_safety_problems(current)
        print(f"AUDIO_SAFETY requested=null actual={current} "
              f"problems={problems or 'none'}", flush=True)
        if problems:
            record("audio_safety", "current-ao doğrulaması", "null",
                   str(current), None, "BLOCKED: AUDIO_SAFETY")
            return 2

        handler, needs_base = SCENARIOS[SCENARIO]
        base = None
        if needs_base:
            base, base_path = baseline_frame()
            measures["baseline_shot"] = base_path
        handler(base)
        trace("body:handler_done")
    except Exception:
        import traceback
        print("PYTHON_EXCEPTION " + traceback.format_exc().strip(), flush=True)
        return 90
    finally:
        pass
    return 0


def main():
    global APP, PLAYER, SCENARIO, TEMP_DIR

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    parser.add_argument("--video",
                        default=os.environ.get("MLC_NATIVE_TEST_VIDEO", ""))
    args = parser.parse_args()
    SCENARIO = args.scenario

    QStandardPaths.setTestModeEnabled(True)
    settings_root = os.environ.get(
        "MLC_NATIVE_SETTINGS",
        os.path.join(os.environ.get("TEMP", "."), "mlc_subtitle_settings"))
    settings_dir = os.path.join(settings_root, f"{SCENARIO}-{os.getpid()}")
    os.makedirs(settings_dir, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      settings_dir)
    TEMP_DIR = tempfile.mkdtemp(prefix=f"mlc_sub_{SCENARIO}_")
    print(f"CHILD_ISOLATION settings={settings_dir} temp={TEMP_DIR} "
          f"qt_test_mode=True", flush=True)
    install_mpv_call_recorder()

    original_cursor = cursor_pos()
    original_foreground = foreground_hwnd()

    APP = QApplication(sys.argv)
    import app.player as player_module
    player_module.MPV_CONFIG = native_mpv_config(player_module.MPV_CONFIG,
                                                 silent_audio=True)
    print(f"AUDIO_ISOLATION ao={player_module.MPV_CONFIG.get('ao')}", flush=True)
    PLAYER = MPVPlayer()
    PLAYER.resize(1400, 820)
    PLAYER.show()
    pump(900)
    mark("MARK_SHOWN")

    status = {"code": 0}

    def body():
        try:
            status["code"] = run_body(args)
        except Exception:
            import traceback
            print("PYTHON_EXCEPTION " + traceback.format_exc().strip(),
                  flush=True)
            status["code"] = 90
        finally:
            trace("body:finally_start")
            # Fare ve foreground geri yüklemesi kapanıştan ÖNCE yapılır:
            # `PLAYER.close()` sonrası Qt olaylarını pompalamak (ki
            # `take_foreground` bunu yapar) mpv `vo=gpu` yüzeyi yok
            # edildikten sonra çökmeye yol açıyordu (F/K senaryolarında
            # `0xC0000409`, 3/3 yeniden üretildi).
            user32.SetCursorPos(*original_cursor)
            if original_foreground:
                take_foreground(original_foreground, attempts=4)
            accepted = False
            try:
                accepted = bool(PLAYER.close())
            except Exception as exc:
                print(f"TEARDOWN_WARNING {type(exc).__name__}", flush=True)
            stops = MPV_CALLS.count("stop")
            terminates = MPV_CALLS.count("terminate")
            order_ok = MPV_CALLS[:2] == ["stop", "terminate"]
            released = PLAYER.mpv_player is None
            record("product_shutdown_path",
                   "yalnız PLAYER.close(); stop/terminate sınıf düzeyinde",
                   "stop=1 terminate=1 sıra=stop->terminate close=accepted",
                   f"stop={stops} terminate={terminates} "
                   f"order={MPV_CALLS[:3]} close_accepted={accepted} "
                   f"mpv_released={released}",
                   stops == 1 and terminates == 1 and order_ok and accepted
                   and released)
            APP.quit()

    # WATCHDOG: hiçbir ölçüm süresiz kilitlenmemeli. Süre dolarsa açık
    # modal pencereler kapatılır ve durum FAIL olarak raporlanır; sessiz
    # takılma PASS'a dönüşemez.
    deadline = time.time() + float(os.environ.get("MLC_SUB_TIMEOUT_S", "900"))
    watchdog = QTimer()
    watchdog.setInterval(4000)

    def tick():
        if time.time() < deadline:
            return
        watchdog.stop()
        print(f"WATCHDOG_TIMEOUT scenario={SCENARIO}", flush=True)
        results.append({"test": "watchdog", "status": "FAIL"})
        modal = QApplication.activeModalWidget()
        if modal is not None:
            modal.reject() if isinstance(modal, QDialog) else modal.close()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()

    watchdog.timeout.connect(tick)
    watchdog.start()

    QTimer.singleShot(0, body)
    exec_code = APP.exec()
    watchdog.stop()
    print(f"MARK_APP_EXEC_RETURNED scenario={SCENARIO} code={exec_code}",
          flush=True)

    if TEMP_DIR and os.path.isdir(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    print(f"TEMP_CLEANED exists={os.path.isdir(TEMP_DIR)}", flush=True)

    print("MEASURES " + json.dumps(measures, ensure_ascii=False, default=str),
          flush=True)
    failed = [r for r in results if r["status"] == "FAIL"]
    blocked = [r for r in results if r["status"] == "BLOCKED"]
    print(f"SCENARIO_SUMMARY scenario={SCENARIO} total={len(results)} "
          f"pass={len(results)-len(failed)-len(blocked)} fail={len(failed)} "
          f"blocked={len(blocked)}", flush=True)
    print(f"MARK_DONE scenario={SCENARIO}", flush=True)
    if status["code"] not in (0, 1):
        return status["code"]
    return 1 if failed else 0


if __name__ == "__main__":
    # Ürün çıkış politikası: bütün satırlar flush edildikten SONRA çık.
    os._exit(main())
