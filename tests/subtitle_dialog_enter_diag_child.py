"""Tanı: Altyazı Ayarları penceresinde Enter tuşu neyi bloklar?

Gerçek MPV kabul koşumunda `Key_Return` çağrısının dakikalarca dönmediği
ölçüldü. Bu child, aynı davranışı MPV, video ve ürün penceresi OLMADAN
yeniden üretmeye çalışır; böylece sorunun dialog'a mı yoksa oynatıcı
yüzeyine mi ait olduğu ayrılır.

Ölçülenler:
- `QTest.keyClick(..., Key_Return)` çağrısının dönüş süresi,
- blok sırasında Qt zamanlayıcılarının çalışıp çalışmadığı (kalp atışı),
- blok sırasında AÇIK olan modal/üst düzey pencerelerin sınıf adları.

Opt-in: `MLC_NATIVE_SMOKE=1`.
"""
import faulthandler
import os
import sys
import time

faulthandler.enable()

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402

from app.subtitle_appearance_dialog import SubtitleAppearanceDialog  # noqa: E402

START = time.time()
BEATS = []
STATE = {"block_s": None, "modal_during": [], "top_level_during": []}


def snapshot(tag):
    modal = QApplication.activeModalWidget()
    tops = [type(w).__name__ for w in QApplication.topLevelWidgets()
            if w.isVisible()]
    print(f"SNAPSHOT|{tag}|modal={type(modal).__name__ if modal else None}"
          f"|visible={tops}", flush=True)
    return modal, tops


def main():
    app = QApplication(sys.argv)
    dialog = SubtitleAppearanceDialog(None, values={}, track_list=[],
                                      apply_callback=lambda values: (True, None))

    heartbeat = QTimer()
    heartbeat.setInterval(50)
    heartbeat.timeout.connect(lambda: BEATS.append(time.time()))
    heartbeat.start()

    def press():
        dialog.scale_spin.setFocus()
        QTest.keyClick(dialog.scale_spin, Qt.Key.Key_A,
                       Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(dialog.scale_spin, "1")
        print("PRESS_ENTER_START", flush=True)
        started = time.time()
        QTest.keyClick(dialog.scale_spin, Qt.Key.Key_Return)
        STATE["block_s"] = round(time.time() - started, 2)
        print(f"PRESS_ENTER_RETURNED after={STATE['block_s']}s", flush=True)
        snapshot("after_enter")
        if dialog.isVisible():
            dialog.reject()

    # Blok sırasında (Enter çağrısı dönmeden) durumu görebilmek için
    # bağımsız bir zamanlayıcı kullanılır.
    probe = QTimer()
    probe.setInterval(1500)
    probe_state = {"count": 0}

    def probe_tick():
        probe_state["count"] += 1
        if STATE["block_s"] is None and probe_state["count"] <= 6:
            modal, tops = snapshot(f"during_block_{probe_state['count']}")
            STATE["modal_during"].append(
                type(modal).__name__ if modal else None)
            STATE["top_level_during"].append(tops)
        if probe_state["count"] == 6 and STATE["block_s"] is None:
            print("PROBE_UNBLOCK: ikinci modal kapatiliyor", flush=True)
            modal = QApplication.activeModalWidget()
            if modal is not None and modal is not dialog:
                modal.reject() if isinstance(modal, QDialog) else modal.close()
            for widget in QApplication.topLevelWidgets():
                if widget is not dialog and widget.isVisible() \
                        and isinstance(widget, QDialog):
                    widget.reject()

    probe.timeout.connect(probe_tick)
    probe.start()

    QTimer.singleShot(400, press)
    QTimer.singleShot(30000, app.quit)
    dialog.exec()
    app.processEvents()
    heartbeat.stop()
    probe.stop()

    gaps = [round(b - a, 3) for a, b in zip(BEATS, BEATS[1:])]
    print(f"HEARTBEAT beats={len(BEATS)} worst_gap={max(gaps) if gaps else None}"
          f" total={round(time.time() - START, 2)}s", flush=True)
    print(f"STATE block_s={STATE['block_s']} modal_during="
          f"{STATE['modal_during']} tops_during={STATE['top_level_during']}",
          flush=True)
    print("MARK_DONE enter_diag", flush=True)
    return 0


if __name__ == "__main__":
    os._exit(main())
