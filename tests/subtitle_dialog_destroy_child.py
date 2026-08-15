"""Senaryo B: dialog GERCEKTEN deleteLater ile yok edilirken arama suruyor.

Adimlar:
  1. Uzun suren sahte arama baslatilir (gercek aga cikilmaz).
  2. Thread'in gercekten calistigi dogrulanir.
  3. dialog.deleteLater() cagrilir ve DeferredDelete kuyrugu akitilir.
  4. Dialog'un gercekten `destroyed` sinyali verdigi dogrulanir.
  5. O anda worker HENUZ BITMEMIS olmalidir.
  6. Controller thread/worker referanslarini `finished` gelene kadar korur.
  7. Dialog yok olduktan sonra gelen sinyaller UI'a DOKUNMAZ.
  8. Worker kooperatif olarak tamamlanir.

Basari sarti: gercek EXIT=0 ve stderr'de "QThread: Destroyed while thread is
still running", "wrapped C/C++ object has been deleted", traceback veya native
crash bulunmamasi.
"""
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from app.subtitle_center import SubtitleCenterDialog  # noqa: E402
from app.subtitle_search_controller import SubtitleSearchController  # noqa: E402

MEDIA = {
    "file_name": "Resident.Alien.S01E01.Pilot.1080p-NTb.mkv",
    "title": "Resident Alien", "season": 1, "episode": 1, "is_series": True,
    "target_name": "Resident.Alien.S01E01.Pilot.1080p-NTb.srt",
    "movie_hash": "abc123", "file_size": 123456,
}
DELAY = float(os.environ.get("MLC_FAKE_SEARCH_DELAY", "1.5"))
failures = []


class SlowFakeClient:
    """Gecikmeli sahte istemci; GERCEK AGA CIKMAZ."""

    def __init__(self, delay):
        self.delay = delay
        self.calls = 0

    def search(self, **params):
        self.calls += 1
        end = time.time() + self.delay
        while time.time() < end:
            time.sleep(0.02)
        return []


def mark(name, extra=""):
    print(f"{name} {extra}".rstrip(), flush=True)


def flush(app, milliseconds):
    end = time.time() + milliseconds / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)


def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.show()

    dialog = SubtitleCenterDialog(window, media=MEDIA)
    dialog.show()
    destroyed = {"seen": False}
    dialog.destroyed.connect(lambda *_: destroyed.__setitem__("seen", True))

    client = SlowFakeClient(DELAY)
    # Controller ACIKCA daha uzun yasayan owner'a (ana pencere) baglanir.
    controller = SubtitleSearchController(dialog, client=client, owner=window)
    app.processEvents()
    mark("MARK_DIALOG_READY")

    controller.start_search()
    app.processEvents()
    time.sleep(0.15)
    app.processEvents()
    running_before = controller.thread_is_running()
    mark("MARK_SEARCH_RUNNING", f"running={running_before}")
    if not running_before:
        failures.append("thread_not_running_before_destroy")

    # 3-4. Dialog GERCEKTEN yok edilir.
    dialog.deleteLater()
    end = time.time() + 3.0
    while time.time() < end and not destroyed["seen"]:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)
    mark("MARK_DIALOG_DESTROYED",
         f"destroyed_signal={destroyed['seen']} "
         f"controller_dialog_is_none={controller.dialog is None}")
    if not destroyed["seen"]:
        failures.append("dialog_destroyed_signal_missing")
    if controller.dialog is not None:
        failures.append("controller_dialog_reference_not_cleared")

    # 5-6. Worker HENUZ bitmemis olmali; referanslar korunmali.
    still_running = controller.thread_is_running()
    mark("MARK_THREAD_STILL_RUNNING",
         f"running={still_running} thread_ref={controller._thread is not None} "
         f"worker_ref={controller._worker is not None}")
    if not still_running:
        failures.append("thread_finished_too_early")
    if controller._thread is None or controller._worker is None:
        failures.append("references_dropped_before_finished")

    # 8. Kooperatif tamamlanma beklenir (zorla sonlandirma yok).
    end = time.time() + 8.0
    while time.time() < end and not controller.is_idle():
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)
    mark("MARK_THREAD_FINISHED_NATURALLY",
         f"idle={controller.is_idle()} running={controller.thread_is_running()}")
    if not controller.is_idle():
        failures.append("thread_did_not_finish_naturally")

    window.close()
    flush(app, 300)
    del controller
    flush(app, 200)

    print(f"RESULTS: searches={client.calls} "
          f"failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
