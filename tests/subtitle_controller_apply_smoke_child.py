# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in GERCEK MPV + GERCEK controller apply smoke'u.

Farki: `subtitle_track_lifecycle_smoke_child.py` yalnizca
`SubtitleSession.apply()` cekirdegini olcuyordu. Burada tam controller yolu
kullanilir: `SubtitleDownloadController.download_and_apply()` -> sahte
OpenSubtitles client -> SRT kaydi -> gercek MPV'ye apply. Boylece yeni Qt
dostu `_qt_wait()` beklemesi GERCEK MPV'nin gecikmeli `track_list`
guncellemesiyle sinanir.

GUVENLIK KURALI
---------------
Kullanicinin medya dizinine HICBIR SEKILDE yazilmaz:

- MPV GERCEK videoyu oynatir (yalnizca okuma),
- ama dialog'un `media["file_name"]` degeri benzersiz %TEMP% icindeki
  SAHTE bir video yoludur; bu yuzden `subtitle_target_path()` hedefi de
  yalnizca o gecici dizindedir,
- kosum oncesi/sonrasi medya dizini snapshot'i karsilastirilir.

MEDYA KAYNAGI
-------------
`MLC_NATIVE_TEST_VIDEO` gecerli bir dosyaysa GERCEK video kullanilir
(`MARK_MEDIA_KIND real_video`). Video yapilandirilmamissa smoke atlanmak
yerine %TEMP% icinde kisa bir sessiz WAV URETILIR
(`MARK_MEDIA_KIND generated_wav`): libmpv, `wid` yuzeyi ve gecikmeli
`track_list` guncellemesi yine GERCEKTIR, yalnizca goruntu yoktur.
Gorsel kabul icin gercek video ile kosum ayrica gereklidir.

Kapanis TEK SAHIPLIDIR: `service.shutdown_player()` stop+close yapar;
`terminate()` yalnizca urunun closeEvent'i tarafindan cagrilir.

MLC_NATIVE_SMOKE=1 verilmeden hicbir Qt/MPV nesnesi olusturmaz.
"""
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
# MPV native `wid` yuzeyi GERCEK pencere ister; offscreen 0xC0000005 uretiyor.
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from app import subtitle_service as service  # noqa: E402
from app.player import MPVPlayer  # noqa: E402
from app.subtitle_center import SubtitleCenterDialog  # noqa: E402
from app.subtitle_download_controller import (  # noqa: E402
    STATUS_APPLIED, SubtitleDownloadController)

VIDEO = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
FAKE_VIDEO_NAME = "MLC.Apply.Smoke.S01E01.1080p-TEST.mkv"
SRT = ("1\n00:00:01,000 --> 00:00:05,000\nMLC controller apply smoke\n\n"
       "2\n00:00:06,000 --> 00:00:09,000\nIkinci satir\n").encode("utf-8")
RESULT = {"file_id": 7135238, "name": "Uzak.Ad.turkish", "language": "Türkçe",
          "format": "srt", "moviehash_match": True, "downloads": 1,
          "ratings": 9.0, "hearing_impaired": False}
failures = []


class FakeClient:
    """Gercek aga CIKMAZ; guvenilir gorunumlu OpenSubtitles yaniti taklit eder."""

    def __init__(self):
        self.download_calls = 0

    def download_link(self, file_id):
        self.download_calls += 1
        return "https://dl.opensubtitles.com/download/mlc-smoke.srt"

    def fetch(self, url):
        return SRT


def mark(name, extra=""):
    print(f"{name} {extra}".rstrip(), flush=True)


def generate_wav(path, seconds=3, rate=8000):
    """Gercek video yoksa GERCEK libmpv'yi besleyecek kisa sessiz WAV uretir."""
    import wave

    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * (rate * seconds))
    return path


def snapshot_media_dir(video):
    directory = os.path.dirname(os.path.abspath(video))
    state = {}
    for entry in os.scandir(directory):
        if entry.is_file():
            info = entry.stat()
            state[entry.name] = (info.st_size, int(info.st_mtime))
    return directory, state


def external_track_for(mpv, path):
    wanted = os.path.normcase(os.path.abspath(path))
    for track in (mpv.track_list or []):
        if not isinstance(track, dict) or track.get("type") != "sub":
            continue
        name = track.get("external-filename")
        if name and os.path.normcase(os.path.abspath(str(name))) == wanted:
            return track
    return None


def main():
    settings = os.environ.get("MLC_NATIVE_SETTINGS")
    if settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, settings)
    # Hedef YALNIZCA bu gecici dizinde olusur.
    workspace = tempfile.mkdtemp(prefix="mlc-apply-smoke-")

    real_video = bool(VIDEO and os.path.isfile(VIDEO))
    if real_video:
        playable = VIDEO
        media_dir, before_state = snapshot_media_dir(VIDEO)
        mark("MARK_MEDIA_KIND", "real_video")
        mark("MARK_MEDIA_SNAPSHOT", f"dir={media_dir} files={len(before_state)}")
    else:
        playable = generate_wav(os.path.join(workspace, "mlc-smoke-tone.wav"))
        before_state = None
        mark("MARK_MEDIA_KIND", "generated_wav")
        mark("MARK_MEDIA_NOTE",
             f"MLC_NATIVE_TEST_VIDEO yok ({VIDEO!r}); libmpv gercek, goruntu yok")

    fake_video = os.path.join(workspace, FAKE_VIDEO_NAME)
    with open(fake_video, "wb") as handle:
        handle.write(b"placeholder")
    expected_target = service.subtitle_target_path(fake_video)
    mark("MARK_WORKSPACE", workspace)
    mark("MARK_TARGET", expected_target)
    if os.path.dirname(os.path.abspath(expected_target)) != os.path.abspath(workspace):
        failures.append("target_outside_workspace")
        print(f"RESULTS: failures={','.join(failures)}", flush=True)
        return 1

    app = QApplication(sys.argv)
    player = MPVPlayer()
    player.show()
    app.processEvents()
    player.open_path(playable)

    deadline = time.time() + 25
    while time.time() < deadline and not (player.mpv_player.duration or 0):
        app.processEvents()
        time.sleep(0.05)
    mark("MARK_PLAY", f"duration={player.mpv_player.duration}")
    if not (player.mpv_player.duration or 0):
        failures.append("media_did_not_start")

    window = QMainWindow()
    window.show()
    app.processEvents()

    media = {"file_name": fake_video, "title": "MLC Apply Smoke",
             "season": 1, "episode": 1, "is_series": True,
             "target_name": os.path.basename(expected_target),
             "movie_hash": "abc", "file_size": 11}
    dialog = SubtitleCenterDialog(window, media=media)
    dialog.show()
    client = FakeClient()
    controller = SubtitleDownloadController(
        dialog, client=client, player=player, owner=window)
    dialog.show_results([RESULT])
    dialog.select_result(dialog.result_cards()[0])
    app.processEvents()
    mark("MARK_READY")

    try:
        started = controller.download_and_apply()
        mark("MARK_STARTED", f"started={started}")
        if not started:
            failures.append("download_did_not_start")

        elapsed_start = time.monotonic()
        end = time.time() + 20
        while time.time() < end and not (controller.is_idle()
                                         and not controller.is_applying()):
            app.processEvents()
            time.sleep(0.01)
        elapsed = time.monotonic() - elapsed_start
        app.processEvents()

        mpv = player.mpv_player
        track = external_track_for(mpv, expected_target)
        selected = mpv.sid
        status = dialog.status_text()
        mark("MARK_APPLY",
             f"elapsed={elapsed:.3f}s track_id={track and track.get('id')} "
             f"sid={selected} visibility={mpv.sub_visibility} "
             f"status={status!r}")

        if track is None:
            failures.append("external_track_missing")
        elif selected != track.get("id"):
            failures.append(f"wrong_track_selected sid={selected}")
        if not mpv.sub_visibility:
            failures.append("subtitle_not_visible")
        if status != STATUS_APPLIED:
            failures.append(f"status_not_applied status={status!r}")
        if not os.path.isfile(expected_target):
            failures.append("target_file_missing")

        leftovers = controller.findChildren(type(controller))
        if controller.is_applying():
            failures.append("apply_flag_stuck")
        mark("MARK_RESIDUE", f"children={len(leftovers)}")
    finally:
        try:
            dialog.close()
            window.close()
            app.processEvents()
        except Exception as exc:
            print(f"CLOSE_WARNING {exc}", flush=True)
        # TEK SAHIPLI kapanis: stop + close. terminate yalniz closeEvent'te.
        service.shutdown_player(player)
        app.processEvents()
        mark("MARK_SHUTDOWN", "stop+close (terminate closeEvent'e ait)")
        try:
            shutil.rmtree(workspace, ignore_errors=True)
            mark("MARK_WORKSPACE_CLEANED", str(not os.path.exists(workspace)))
        except Exception as exc:
            print(f"CLEANUP_WARNING {exc}", flush=True)

    if before_state is not None:
        after_dir, after_state = snapshot_media_dir(VIDEO)
        if after_state != before_state:
            changed = set(after_state.items()) ^ set(before_state.items())
            failures.append(f"media_dir_modified={sorted(n for n, _ in changed)}")
        mark("MARK_MEDIA_UNCHANGED", str(after_state == before_state))
    else:
        # Oynatilan medya da %TEMP% icindeydi: kullanici medya dizini hic
        # dokunulmadi cunku hic hesaplanmadi.
        mark("MARK_MEDIA_UNCHANGED", "n/a (medya %TEMP% icinde uretildi)")

    print(f"RESULTS: downloads={client.download_calls} "
          f"failures={','.join(failures) or 'none'}", flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
