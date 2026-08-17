# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""APPLY POLLING SIRASINDA dialog kapatma / gercek deleteLater child'i.

Kullanim:
    python tests/subtitle_apply_lifecycle_child.py --mode close
    python tests/subtitle_apply_lifecycle_child.py --mode destroy

Fark: `subtitle_download_lifecycle_child.py` indirme QThread'i SURERKEN
kapatiyordu. Burada indirme ANINDA biter; kapanis MPV apply beklemesinin
IC ICE event loop'u calisirken tetiklenir. Bu, `_qt_wait()` gercek Qt
beklemesi yaptigi icin ortaya cikan yeni yasam dongusu yoludur.

GERCEK AGA CIKILMAZ: gecikmesiz sahte client kullanilir. Hedef dosya
benzersiz bir %TEMP% calisma dizinindedir; kullanicinin medya dizinine
DOKUNULMAZ. Gercek MPV kullanilmaz (bunun icin
`subtitle_controller_apply_smoke_child.py`).

Basari sarti: gercek EXIT=0 ve stderr'de "QThread: Destroyed while thread is
still running", "wrapped C/C++ object has been deleted", traceback veya
native crash bulunmamasi.
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt, QEvent, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from app.subtitle_center import SubtitleCenterDialog  # noqa: E402
from app.subtitle_download_controller import (  # noqa: E402
    STATUS_APPLIED, SubtitleDownloadController)

VIDEO_NAME = "Resident.Alien.S01E01.Pilot.1080p-NTb.mkv"
TARGET_NAME = "Resident.Alien.S01E01.Pilot.1080p-NTb.srt"
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba\n"
# Track apply butcesinden (~400 ms) SONRA gelir: iptal polling sirasinda olur.
TRACK_DELAY_MS = int(os.environ.get("MLC_FAKE_TRACK_DELAY_MS", "600"))
CLOSE_AFTER_MS = int(os.environ.get("MLC_FAKE_CLOSE_AFTER_MS", "100"))
failures = []


class InstantClient:
    def __init__(self):
        self.download_calls = 0

    def download_link(self, file_id):
        self.download_calls += 1
        return "https://dl.opensubtitles.com/download/x.srt"

    def fetch(self, url):
        return SRT


class DelayedTrackMpv:
    """Gercek MPV gibi track_list'i GECIKMELI gunceller."""

    def __init__(self, delay_ms):
        self.track_list = [{"type": "sub", "id": 1}]
        self.sid = "no"
        self.sub_visibility = False
        self.delay_ms = delay_ms
        self._next = 2

    def sub_add(self, path, *args):
        track = {"type": "sub", "id": self._next, "external-filename": path}
        self._next += 1
        QTimer.singleShot(self.delay_ms, Qt.TimerType.PreciseTimer,
                          lambda: self.track_list.append(track))

    def sub_remove(self, sid):
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


def mark(name, extra=""):
    print(f"{name} {extra}".rstrip(), flush=True)


def flush(app, milliseconds):
    end = time.time() + milliseconds / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("close", "destroy"), default="close")
    args = parser.parse_args()

    workspace = tempfile.mkdtemp(prefix="mlc-apply-life-")
    video = os.path.join(workspace, VIDEO_NAME)
    with open(video, "wb") as handle:
        handle.write(b"video")
    target = os.path.join(workspace, TARGET_NAME)
    mark("MARK_WORKSPACE", workspace)

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.show()

    media = {"file_name": video, "title": "Resident Alien", "season": 1,
             "episode": 1, "is_series": True, "target_name": TARGET_NAME,
             "movie_hash": "abc", "file_size": 5}
    dialog = SubtitleCenterDialog(window, media=media)
    dialog.show()
    destroyed = {"seen": False}
    dialog.destroyed.connect(lambda *_: destroyed.__setitem__("seen", True))

    client = InstantClient()
    mpv = DelayedTrackMpv(TRACK_DELAY_MS)
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    controller = SubtitleDownloadController(
        dialog, client=client, player=player, owner=window)
    dialog.show_results([{"file_id": 7135238, "name": "Test",
                          "language": "Türkçe", "format": "srt",
                          "moviehash_match": True, "downloads": 1,
                          "ratings": 1.0, "hearing_impaired": False}])
    dialog.select_result(dialog.result_cards()[0])
    app.processEvents()
    mark("MARK_READY", f"mode={args.mode} track_delay_ms={TRACK_DELAY_MS}")

    observed = {"applying": False}

    def watch():
        # Kapanis GERCEKTEN apply beklemesi sirasinda olmali.
        observed["applying"] = controller.is_applying()
        if args.mode == "close":
            dialog.close()
        else:
            dialog.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    QTimer.singleShot(CLOSE_AFTER_MS, Qt.TimerType.PreciseTimer, watch)
    started = controller.download_and_apply()
    mark("MARK_STARTED", f"started={started}")
    if not started:
        failures.append("download_did_not_start")

    end = time.time() + 10.0
    while time.time() < end and not (controller.is_idle()
                                     and not controller.is_applying()):
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)

    mark("MARK_INTERRUPT_DURING_APPLY", f"applying_when_closed={observed['applying']}")
    if not observed["applying"]:
        failures.append("close_did_not_happen_during_apply")

    mark("MARK_SETTLED",
         f"idle={controller.is_idle()} applying={controller.is_applying()} "
         f"cancelled={controller.is_cancelled()} "
         f"running={controller.thread_is_running()}")
    if not controller.is_idle():
        failures.append("thread_did_not_finish_naturally")
    if controller.is_applying():
        failures.append("apply_flag_stuck")
    if not controller.is_cancelled():
        failures.append("cancel_not_recorded")

    # Iptalden sonra track ZORLA secilmez, gorunurluk zorlanmaz.
    mark("MARK_MPV", f"sid={mpv.sid!r} visibility={mpv.sub_visibility}")
    if mpv.sid != "no":
        failures.append(f"track_forced_after_cancel sid={mpv.sid!r}")
    if mpv.sub_visibility:
        failures.append("visibility_forced_after_cancel")

    # Kayit basariyla tamamlandi: indirilen dosya KORUNUR.
    saved = os.path.isfile(target) and open(target, "rb").read() == SRT
    mark("MARK_FILE_PRESERVED", str(saved))
    if not saved:
        failures.append("downloaded_file_missing")

    if args.mode == "destroy":
        mark("MARK_DIALOG_DESTROYED",
             f"destroyed_signal={destroyed['seen']} "
             f"dialog_ref_none={controller.dialog is None}")
        if not destroyed["seen"]:
            failures.append("destroyed_signal_missing")
        if controller.dialog is not None:
            failures.append("dialog_reference_not_cleared")
    else:
        status = ""
        try:
            status = dialog.status_text()
        except RuntimeError:
            status = "<destroyed>"
        mark("MARK_STATUS", repr(status))
        if STATUS_APPLIED in status:
            failures.append("success_reported_after_cancel")

    # Bekleme timer'i/loop artigi kalmamali.
    leftovers = controller.findChildren(QTimer)
    mark("MARK_TIMER_RESIDUE", str(len(leftovers)))
    if leftovers:
        failures.append(f"timer_residue={len(leftovers)}")

    window.close()
    flush(app, 300)
    del controller
    flush(app, 200)

    try:
        shutil.rmtree(workspace, ignore_errors=True)
        mark("MARK_WORKSPACE_CLEANED", str(not os.path.exists(workspace)))
    except Exception as exc:
        print(f"CLEANUP_WARNING {exc}", flush=True)

    print(f"RESULTS: mode={args.mode} downloads={client.download_calls} "
          f"failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
