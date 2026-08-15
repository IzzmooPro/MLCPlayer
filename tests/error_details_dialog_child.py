"""Opt-in GERÇEK Windows kabulü: "Hata Ayrıntıları" penceresi.

Offscreen test tek başına yeterli değildir (Türkçe glifler offscreen'de
kare çizilir). Bu child gerçek Windows platformunda pencereyi açar,
ekran görüntüsü alır ve geometri ölçer.

    MLC_NATIVE_SMOKE=1 python tests/error_details_dialog_child.py \
        --scenario default --shot <yol.png>

Senaryolar: default, long_summary, huge_traceback, empty_detail,
small_screen. Sonuç tek satır JSON: `DETAILS_JSON {...}`.
"""
import argparse
import json
import os
import sys

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# Gerçek Windows platformu: `MLC_DIALOG_REAL_PLATFORM=1` verilmezse
# offscreen kullanılır.
if os.environ.get("MLC_DIALOG_REAL_PLATFORM") != "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (QApplication, QLabel,  # noqa: E402
                             QPlainTextEdit, QPushButton)

from app import errors  # noqa: E402
from app.error_details_dialog import ErrorDetailsDialog  # noqa: E402

# Sentetik hassas değerler.
WIN_PATH = r"C:\Users\Gercek Kullanici\Private Folder\film.mkv"
UNC_PATH = r"\\server\share\Private Folder\film.mkv"
FILE_URI = "file://server/share/Private Folder/film.mkv"
TOKEN_URL = "https://cdn.test/v.m3u8?token=SENTETIK123"
AUTH_LINE = "Authorization: Digest SENTETIK456"
PASSWORD = 'password="SENTETIK789"'
RAW_MARKERS = ("Gercek Kullanici", "Private Folder", "film.mkv", "server",
               "share", "SENTETIK123", "SENTETIK456", "SENTETIK789")


def build_event(scenario):
    if scenario == "empty_detail":
        return errors.build_error_event(
            "Dosya Açılamadı", "Dosya açılamadı. Tekrar deneyin.")
    payload = (f"acilamadi: {WIN_PATH} | {UNC_PATH} | {FILE_URI} | "
               f"{TOKEN_URL} | {AUTH_LINE} | {PASSWORD}")
    if scenario == "huge_traceback":
        payload = payload + "\n" + "\n".join(
            f'  File "{ROOT}\\app\\derin_modul_{index}.py", line {index}, '
            f'in fonksiyon_{index}' for index in range(120))
    try:
        raise OSError(payload)
    except OSError as exc:
        title = "Dosya Açılamadı"
        message = "Dosya açılamadı. Tekrar deneyin."
        if scenario == "long_summary":
            title = ("Çok Uzun Bir Hata Başlığı — Oynatıcı Bileşeni "
                     "Beklenmedik Biçimde Yanıt Vermedi")
            message = ("Bu işlem tamamlanamadı. Lütfen dosyayı kontrol edip "
                       "tekrar deneyin; sorun sürerse programı yeniden "
                       "başlatın ve destek ekibine kayıt numarasını "
                       "iletin.")
        return errors.build_error_event(title, message, exc=exc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="default")
    parser.add_argument("--shot", default="")
    parser.add_argument("--screen", default="")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    event = build_event(args.scenario)
    dialog = ErrorDetailsDialog(event)
    if args.scenario == "small_screen":
        dialog.resize(*[int(part) for part in (args.screen or "560,380")
                        .split(",")])
    dialog.show()
    app.processEvents()

    labels = dialog.findChildren(QLabel)
    buttons = dialog.findChildren(QPushButton)
    detail = dialog.findChild(QPlainTextEdit)
    rect = dialog.frameGeometry()
    screen = app.primaryScreen().availableGeometry()

    clipped = []
    for widget in labels + buttons + [detail]:
        if widget is None:
            continue
        hint = widget.minimumSizeHint()
        if widget.width() < hint.width() or widget.height() < hint.height():
            clipped.append(f"{type(widget).__name__}:"
                           f"{widget.objectName() or widget.__class__.__name__}"
                           f":{widget.width()}x{widget.height()}"
                           f"<{hint.width()}x{hint.height()}")

    blob = dialog.intro_text() + "\n" + dialog.detail_text()
    for label, value in dialog.fields():
        blob += f"\n{label}: {value}"
    leaks = [marker for marker in RAW_MARKERS
             if marker in blob.replace(errors.MASK, "")
             .replace(errors.MASK_PATH, "")]

    scrollbar = detail.verticalScrollBar() if detail is not None else None
    report = {
        "scenario": args.scenario,
        "scale": os.environ.get("QT_SCALE_FACTOR", "1"),
        "platform": os.environ.get("QT_QPA_PLATFORM", "windows"),
        "title": dialog.windowTitle(),
        "size": [dialog.width(), dialog.height()],
        "frame": list(rect.getRect()),
        "screen": list(screen.getRect()),
        "inside_screen": screen.contains(rect),
        "clipped": clipped,
        "buttons": [button.text() for button in buttons],
        "buttons_visible": all(button.isVisible() for button in buttons),
        "detail_read_only": bool(detail.isReadOnly()) if detail else None,
        "detail_lines": len(dialog.detail_text().splitlines()),
        "detail_scrollable": bool(scrollbar.maximum() > 0) if scrollbar
                             else None,
        "record_id": event.record_id,
        "record_id_visible": event.record_id in blob,
        "raw_leaks": leaks,
        "mask_seen": errors.MASK_PATH in blob or errors.MASK in blob,
    }
    if args.shot:
        os.makedirs(os.path.dirname(args.shot), exist_ok=True)
        dialog.grab().save(args.shot)
        report["shot"] = args.shot
    print("DETAILS_JSON " + json.dumps(report, ensure_ascii=False), flush=True)
    dialog.close()
    return 0


if __name__ == "__main__":
    os._exit(main())
