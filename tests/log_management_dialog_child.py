"""Opt-in GERÇEK Windows kabulü: "Günlük Yönetimi" penceresi.

    MLC_NATIVE_SMOKE=1 MLC_DIALOG_REAL_PLATFORM=1 \
        python tests/log_management_dialog_child.py --scenario default \
            --logs <gecici_dizin> --shot <yol.png>

Senaryolar: default, small, cancel, confirm.
`cancel`/`confirm` senaryolarında onay penceresi GERÇEK açılmaz; ürünün
onay yolu tek atımlık bir dublörle sürülür ve dosya sistemi sonucu
ölçülür. Sonuç tek satır JSON: `LOGUI_JSON {...}`.
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
if os.environ.get("MLC_DIALOG_REAL_PLATFORM") != "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (QApplication, QLabel,  # noqa: E402
                             QPushButton)

from app import errors  # noqa: E402


def seed_logs():
    """Sentetik günlükler + ilgisiz dosya + alt klasör."""
    path = errors.get_log_path()
    directory = os.path.dirname(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("SENTETIK aktif kayit\n" * 200)
    with open(path + ".1", "w", encoding="utf-8") as handle:
        handle.write("SENTETIK yedek kayit\n" * 100)
    unrelated = os.path.join(directory, "unrelated.txt")
    with open(unrelated, "w", encoding="utf-8") as handle:
        handle.write("DOKUNMA")
    sub = os.path.join(directory, "altklasor")
    os.makedirs(sub, exist_ok=True)
    with open(os.path.join(sub, "keep.log"), "w", encoding="utf-8") as handle:
        handle.write("DOKUNMA")
    return path, unrelated, sub


class ConfirmStub:
    """Onay penceresinin dublörü: gerçek modal açılmaz."""

    accept = False
    seen = {}

    class Icon:
        Warning = 1

    class StandardButton:
        Yes = 1
        Cancel = 2

    def __init__(self, parent=None):
        self._handles = {}

    def setIcon(self, icon):
        pass

    def setWindowTitle(self, title):
        ConfirmStub.seen["title"] = title

    def setText(self, text):
        ConfirmStub.seen["text"] = text

    def setStandardButtons(self, buttons):
        pass

    def button(self, which):
        return self._handles.setdefault(which, object())

    def setDefaultButton(self, button):
        ConfirmStub.seen["default_is_cancel"] = (
            button is self.button(ConfirmStub.StandardButton.Cancel))

    def setEscapeButton(self, button):
        ConfirmStub.seen["escape_is_cancel"] = (
            button is self.button(ConfirmStub.StandardButton.Cancel))

    def exec(self):
        return 0

    def clickedButton(self):
        return self.button(ConfirmStub.StandardButton.Yes if
                           ConfirmStub.accept else
                           ConfirmStub.StandardButton.Cancel)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="default")
    parser.add_argument("--logs", required=True)
    parser.add_argument("--shot", default="")
    args = parser.parse_args()

    os.environ["APPDATA"] = args.logs
    os.environ["LOCALAPPDATA"] = args.logs
    log_path, unrelated, sub = seed_logs()

    app = QApplication(sys.argv)
    from app import log_management_dialog as module

    dialog = module.LogManagementDialog()
    if args.scenario == "small":
        dialog.resize(460, 280)
    dialog.show()
    app.processEvents()

    before = {
        "log": os.path.exists(log_path),
        "backup": os.path.exists(log_path + ".1"),
        "unrelated": os.path.exists(unrelated),
        "subfolder": os.path.isdir(sub),
    }
    usage_before = errors.get_log_usage()["total_bytes"]

    if args.scenario in ("cancel", "confirm"):
        ConfirmStub.accept = args.scenario == "confirm"
        ConfirmStub.seen = {}
        module.QMessageBox = ConfirmStub
        dialog.clear_button.click()
        app.processEvents()

    labels = dialog.findChildren(QLabel)
    buttons = dialog.findChildren(QPushButton)
    rect = dialog.frameGeometry()
    screen = app.primaryScreen().availableGeometry()
    clipped = []
    for widget in labels + buttons:
        hint = widget.minimumSizeHint()
        if widget.width() < hint.width() or widget.height() < hint.height():
            clipped.append(f"{widget.objectName() or type(widget).__name__}:"
                           f"{widget.width()}x{widget.height()}<"
                           f"{hint.width()}x{hint.height()}")

    blob = dialog.visible_text()
    report = {
        "scenario": args.scenario,
        "scale": os.environ.get("QT_SCALE_FACTOR", "1"),
        "title": dialog.windowTitle(),
        "size": [dialog.width(), dialog.height()],
        "inside_screen": screen.contains(rect),
        "clipped": clipped,
        "buttons": [button.text() for button in buttons],
        "buttons_visible": all(button.isVisible() for button in buttons),
        "confirm": dict(ConfirmStub.seen),
        "before": before,
        "after": {
            "log": os.path.exists(log_path),
            "backup": os.path.exists(log_path + ".1"),
            "unrelated": os.path.exists(unrelated),
            "subfolder": os.path.isdir(sub),
        },
        "usage_before": usage_before,
        "usage_after": errors.get_log_usage()["total_bytes"],
        "status": dialog.status_label.text(),
        "shows_log_content": "SENTETIK" in blob,
        "shows_absolute_path": args.logs in blob,
    }
    if args.shot:
        os.makedirs(os.path.dirname(args.shot), exist_ok=True)
        dialog.grab().save(args.shot)
        report["shot"] = args.shot
    print("LOGUI_JSON " + json.dumps(report, ensure_ascii=False), flush=True)
    dialog.close()
    return 0


if __name__ == "__main__":
    os._exit(main())
