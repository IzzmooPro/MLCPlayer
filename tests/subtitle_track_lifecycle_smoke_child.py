# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in GERCEK MPV altyazi track yasam dongusu smoke'u.

GUVENLIK KURALI
---------------
Bu harness kullanicinin medya dizinine HICBIR SEKILDE yazmaz, silmez veya
yedeklemez. Urunun gercek hedef adlandirma/uzerine yazma davranisi
unit/regresyon testlerinde olculur; burada YALNIZCA MPV track yasam dongusu
olculur.

Bu yuzden:
- her kosum kendi benzersiz %TEMP% dizinini olusturur,
- altyazi dosyasi yalnizca o dizinde yaratilir,
- `subtitle_target_path()` KULLANILMAZ,
- medya dizinine giden hicbir yol hesaplanmaz.

Kapanis TEK SAHIPLIDIR: `service.shutdown_player()` stop+close yapar,
`terminate()` yalnizca urunun closeEvent'i tarafindan cagrilir.

MLC_NATIVE_SMOKE=1 verilmeden hicbir Qt/MPV nesnesi olusturmaz.
"""
import os
import shutil
import sys
import tempfile
import time

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
# NOT: MPV native `wid` yuzeyi GERCEK pencere ister; offscreen platform
# 0xC0000005 uretiyor. Bu smoke bilincli olarak gercek pencerede kosar.
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import subtitle_service as service  # noqa: E402
from app.player import MPVPlayer  # noqa: E402

VIDEO = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
ROUNDS = int(os.environ.get("MLC_TRACK_ROUNDS", "5"))
failures = []

SRT_TEMPLATE = ("1\n00:00:01,000 --> 00:00:05,000\nMLC test altyazisi {n}\n\n"
                "2\n00:00:06,000 --> 00:00:09,000\nIkinci satir {n}\n")


def mark(name, extra=""):
    print(f"{name} {extra}".rstrip(), flush=True)


def external_subs(mpv, path):
    wanted = os.path.normcase(os.path.abspath(path))
    found = []
    for track in (mpv.track_list or []):
        if not isinstance(track, dict) or track.get("type") != "sub":
            continue
        name = track.get("external-filename")
        if name and os.path.normcase(os.path.abspath(str(name))) == wanted:
            found.append(track)
    return found


def snapshot_media_dir(video):
    """Medya dizinindeki dosya adi -> (boyut, mtime) haritasi."""
    directory = os.path.dirname(os.path.abspath(video))
    state = {}
    for entry in os.scandir(directory):
        if entry.is_file():
            info = entry.stat()
            state[entry.name] = (info.st_size, int(info.st_mtime))
    return directory, state


def main():
    settings = os.environ.get("MLC_NATIVE_SETTINGS")
    if settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, settings)
    if not (VIDEO and os.path.isfile(VIDEO)):
        print(f"SKIPPED: VIDEO_REQUIRED {VIDEO!r}", flush=True)
        return 0

    media_dir, before_state = snapshot_media_dir(VIDEO)
    mark("MARK_MEDIA_SNAPSHOT", f"dir={media_dir} files={len(before_state)}")

    # Altyazi YALNIZCA benzersiz gecici dizinde yaratilir.
    workspace = tempfile.mkdtemp(prefix="mlc-sub-smoke-")
    temp_srt = os.path.join(workspace, "mlc-track-lifecycle-test.srt")
    mark("MARK_WORKSPACE", workspace)

    app = QApplication(sys.argv)
    player = MPVPlayer()
    player.show()
    app.processEvents()
    player.open_path(VIDEO)

    deadline = time.time() + 25
    while time.time() < deadline and not (player.mpv_player.duration or 0):
        app.processEvents()
        time.sleep(0.05)
    mark("MARK_PLAY", f"duration={player.mpv_player.duration}")

    store = service.SubtitleStore()
    try:
        for index in range(1, ROUNDS + 1):
            store.save(temp_srt, SRT_TEMPLATE.format(n=index).encode("utf-8"))
            # HER TURDA YENI SubtitleSession: bellekteki sid yok, temizlik
            # track_list uzerinden yapilmali.
            session = service.SubtitleSession(store=store)
            applied = session.apply(
                player, temp_srt,
                wait=lambda: (app.processEvents(), time.sleep(0.02)))
            app.processEvents()
            time.sleep(0.3)
            app.processEvents()

            tracks = external_subs(player.mpv_player, temp_srt)
            selected = player.mpv_player.sid
            chosen = [t for t in tracks if t.get("id") == selected]
            mark(f"MARK_ROUND_{index}",
                 f"applied={applied} external_tracks={len(tracks)} "
                 f"sid={selected} sid_is_ours={bool(chosen)} "
                 f"visibility={player.mpv_player.sub_visibility}")
            if not applied:
                failures.append(f"round{index}_not_applied")
            if len(tracks) != 1:
                failures.append(f"round{index}_track_count={len(tracks)}")
            if not chosen:
                failures.append(f"round{index}_wrong_track_selected")
            if not player.mpv_player.sub_visibility:
                failures.append(f"round{index}_not_visible")
    finally:
        # TEK SAHIPLI kapanis: stop + close. terminate yalniz closeEvent'te.
        service.shutdown_player(player)
        app.processEvents()
        mark("MARK_SHUTDOWN", "stop+close (terminate closeEvent'e ait)")
        try:
            shutil.rmtree(workspace, ignore_errors=True)
            mark("MARK_WORKSPACE_CLEANED", str(not os.path.exists(workspace)))
        except Exception as exc:
            print(f"CLEANUP_WARNING {exc}", flush=True)

    after_dir, after_state = snapshot_media_dir(VIDEO)
    if after_state != before_state:
        changed = set(after_state.items()) ^ set(before_state.items())
        failures.append(f"media_dir_modified={sorted(n for n, _ in changed)}")
    mark("MARK_MEDIA_UNCHANGED", str(after_state == before_state))

    print(f"RESULTS: rounds={ROUNDS} failures={','.join(failures) or 'none'}",
          flush=True)
    mark("MARK_DONE")
    return 1 if failures else 0


raise SystemExit(main())
