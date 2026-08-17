# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazi Merkezi dialog/thread yasam dongusu child'i.

Senaryo:
  1. Dialog acilir.
  2. GECIKMELI sahte arama baslatilir (gercek aga cikilmaz).
  3. Arama SURERKEN dialog kapatilir.
  4. Worker iptal istemi alir ve DOGAL olarak biter.
  5. Qt event loop temiz kapanir.

Basari sarti: gercek EXIT=0 ve stderr'de "QThread: Destroyed while thread is
still running" veya native crash bulunmamasi.

Normal pytest paketine dahil degildir (dosya adi test_ ile baslamaz).
"""
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from app.subtitle_center import SubtitleCenterDialog  # noqa: E402
from app.subtitle_search_controller import SubtitleSearchController  # noqa: E402

MEDIA = {
    "file_name": "Resident.Alien.S01E01.Pilot.1080p-NTb.mkv",
    "title": "Resident Alien", "season": 1, "episode": 1, "is_series": True,
    "target_name": "Resident.Alien.S01E01.Pilot.1080p-NTb.srt",
    "movie_hash": "abc123", "file_size": 123456,
}

DELAY = float(os.environ.get("MLC_FAKE_SEARCH_DELAY", "1.2"))


class SlowFakeClient:
    """Gecikmeli sahte istemci; GERCEK AGA CIKMAZ."""

    def __init__(self, delay):
        self.delay = delay
        self.calls = 0

    def search(self, **params):
        self.calls += 1
        # Iptal edilebilir olsun diye kucuk dilimlerle bekler.
        end = time.time() + self.delay
        while time.time() < end:
            time.sleep(0.02)
        return []


def mark(name, extra=""):
    print(f"{name} {extra}".rstrip(), flush=True)


def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.show()

    dialog = SubtitleCenterDialog(window, media=MEDIA)
    dialog.show()
    client = SlowFakeClient(DELAY)
    controller = SubtitleSearchController(dialog, client=client)
    app.processEvents()
    mark("MARK_DIALOG_READY")

    started = controller.start_search()
    app.processEvents()
    mark("MARK_SEARCH_STARTED", f"started={started} "
         f"running={controller.thread_is_running()}")

    # Arama SURERKEN kapat.
    time.sleep(0.2)
    app.processEvents()
    dialog.close()
    app.processEvents()
    mark("MARK_DIALOG_CLOSED",
         f"cancelled={controller.is_cancelled()} "
         f"visible={dialog.isVisible()} running={controller.thread_is_running()}")

    # Thread DOGAL olarak bitmeli; zorla sonlandirma yok.
    finished = controller.shutdown(wait_ms=8000)
    app.processEvents()
    mark("MARK_THREAD_FINISHED",
         f"finished={finished} running={controller.thread_is_running()} "
         f"idle={controller.is_idle()}")

    failures = []
    if not finished:
        failures.append("thread_did_not_finish")
    if controller.thread_is_running():
        failures.append("thread_still_running")
    if not controller.is_cancelled():
        failures.append("cancel_not_requested")

    # Sahipler ancak thread bittikten SONRA yok edilir.
    window.close()
    app.processEvents()
    del dialog
    del controller
    app.processEvents()

    print(f"RESULTS: searches={client.calls} "
          f"failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
