# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Indirme SIRASINDA dialog kapatma / gercek deleteLater yasam dongusu child'i.

Kullanim:
    python tests/subtitle_download_lifecycle_child.py --mode close
    python tests/subtitle_download_lifecycle_child.py --mode destroy

GERCEK AGA CIKILMAZ: sahte gecikmeli client kullanilir. Hedef dosya benzersiz
bir %TEMP% calisma dizinindedir; kullanicinin medya dizinine DOKUNULMAZ.

Basari sarti: gercek EXIT=0 ve stderr'de "QThread: Destroyed while thread is
still running", "wrapped C/C++ object has been deleted", traceback veya native
crash bulunmamasi.
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

from PyQt6.QtCore import QEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from app.subtitle_center import SubtitleCenterDialog  # noqa: E402
from app.subtitle_download_controller import SubtitleDownloadController  # noqa: E402

VIDEO_NAME = "Resident.Alien.S01E01.Pilot.1080p-NTb.mkv"
TARGET_NAME = "Resident.Alien.S01E01.Pilot.1080p-NTb.srt"
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba\n"
DELAY = float(os.environ.get("MLC_FAKE_DOWNLOAD_DELAY", "1.5"))
failures = []


class SlowFakeClient:
    def __init__(self, delay):
        self.delay = delay
        self.download_calls = 0

    def download_link(self, file_id):
        self.download_calls += 1
        end = time.time() + self.delay
        while time.time() < end:
            time.sleep(0.02)
        return "https://dl.opensubtitles.com/download/x.srt"

    def fetch(self, url):
        return SRT


class FakeMpv:
    def __init__(self):
        self.track_list = []
        self.sid = "no"
        self.sub_visibility = False
        self._next = 1

    def sub_add(self, path, *args):
        self.track_list.append({"type": "sub", "id": self._next,
                                "external-filename": path})
        self._next += 1

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

    workspace = tempfile.mkdtemp(prefix="mlc-dl-life-")
    video = os.path.join(workspace, VIDEO_NAME)
    with open(video, "wb") as handle:
        handle.write(b"video")
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

    client = SlowFakeClient(DELAY)
    player = SimpleNamespace(mpv_player=FakeMpv(), video_frame=None)
    controller = SubtitleDownloadController(
        dialog, client=client, player=player, owner=window)
    dialog.show_results([{"file_id": 7135238, "name": "Test", "language": "Türkçe",
                          "format": "srt", "moviehash_match": True,
                          "downloads": 1, "ratings": 1.0,
                          "hearing_impaired": False}])
    dialog.select_result(dialog.result_cards()[0])
    app.processEvents()
    mark("MARK_READY")

    started = controller.download_and_apply()
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    mark("MARK_DOWNLOAD_RUNNING",
         f"started={started} running={controller.thread_is_running()}")
    if not controller.thread_is_running():
        failures.append("thread_not_running")

    if args.mode == "close":
        dialog.close()
        app.processEvents()
        mark("MARK_DIALOG_CLOSED",
             f"visible={dialog.isVisible()} "
             f"running={controller.thread_is_running()}")
    else:
        dialog.deleteLater()
        end = time.time() + 3.0
        while time.time() < end and not destroyed["seen"]:
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
            time.sleep(0.01)
        mark("MARK_DIALOG_DESTROYED",
             f"destroyed_signal={destroyed['seen']} "
             f"dialog_ref_none={controller.dialog is None} "
             f"running={controller.thread_is_running()}")
        if not destroyed["seen"]:
            failures.append("destroyed_signal_missing")
        if controller.dialog is not None:
            failures.append("dialog_reference_not_cleared")
        if not controller.thread_is_running():
            failures.append("thread_finished_too_early")
        if controller._thread is None or controller._worker is None:
            failures.append("references_dropped_before_finished")

    end = time.time() + 10.0
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
