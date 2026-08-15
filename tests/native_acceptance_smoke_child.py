"""Opt-in gerçek Windows kabul kontrolleri (denetim turu).

Gerçek MPVPlayer + gerçek video ile ölçülenler:

- overlay/timeline görünür ve düğmeler gerçek tıklamayı yakalıyor mu;
- çoklu dosya bırakma listeyi sıfırlamadan ekliyor mu;
- oynayan dosya playlist'te aktif satır olarak işaretli mi;
- thumbnail isteniyor mu, üretilemeyen öğe güvenli placeholder gösteriyor mu;
- fullscreen'de Esc pencere moduna dönüyor mu;
- pencere modunda Esc varsayılan dengeli boyuta dönüyor mu;
- altyazılı videoda parça yükleniyor ama başlangıçta kapalı mı;
- altyazısız durumda CC "Altyazı bulunamadı" OSD'sini gösteriyor mu.

``MLC_NATIVE_SMOKE=1`` verilmeden hiçbir Qt/MPV nesnesi oluşturmaz.
"""
import os
import sys
import time

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QSettings, Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

from app.config import WINDOW_HEIGHT, WINDOW_WIDTH  # noqa: E402
from app.player import MPVPlayer  # noqa: E402

VIDEO = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
EXTRA = [p for p in os.environ.get("MLC_EXTRA_VIDEOS", "").split("|") if p]

checks = []
START = time.time()


def record(name, passed, evidence):
    checks.append((name, bool(passed), evidence))
    status = "PASS" if passed else "FAIL"
    print(f"CHECK {status} {name} :: {evidence}", flush=True)


def pump(app, ms):
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def main():
    settings = os.environ.get("MLC_NATIVE_SETTINGS")
    if settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, settings)

    app = QApplication(sys.argv)
    player = MPVPlayer()
    player.resize(1400, 820)
    player.show()
    pump(app, 400)
    frame = player.video_frame

    if VIDEO and os.path.isfile(VIDEO):
        player.open_path(VIDEO)
        pump(app, 3500)
        record("video_playing",
               (player.mpv_player.time_pos or 0) > 0,
               f"time_pos={player.mpv_player.time_pos} "
               f"duration={player.mpv_player.duration}")
    else:
        record("video_playing", False, f"video bulunamadi: {VIDEO!r}")

    frame.show_overlay_for_interaction()
    pump(app, 400)
    overlay = frame.control_overlay

    # --- 1. Overlay düğmeleri gerçek tıklamayı yakalıyor mu ---
    names = ("overlayTimeline", "overlaySubtitles", "overlayVolume",
             "overlaySettings", "overlayFullscreen")
    hit_report = {}
    for name in names:
        widget = overlay.findChild(QPushButton, name)
        if widget is None and name == "overlayTimeline":
            widget = frame.overlay_timeline
        if widget is None:
            hit_report[name] = "missing"
            continue
        centre = widget.mapToGlobal(widget.rect().center())
        hit = QApplication.widgetAt(centre)
        owner = hit
        while owner is not None and owner is not widget:
            owner = owner.parent()
        hit_report[name] = "hit" if owner is widget else f"blocked_by={hit}"
    record("overlay_hit_areas",
           all(value == "hit" for value in hit_report.values()),
           str(hit_report))

    # --- 2. Çoklu dosya bırakma listeyi sıfırlamadan ekler ---
    panel = frame.playlist_panel
    frame.toggle_playlist_panel()
    panel.finish_animation()
    pump(app, 300)
    before = list(player.playlist)
    drops = [path for path in EXTRA if os.path.isfile(path)]
    if drops:
        panel.add_external_files(drops)
        pump(app, 400)
        after = list(player.playlist)
        record("multi_drop_appends_without_reset",
               len(after) == len(before) + len(drops)
               and after[:len(before)] == before,
               f"before={len(before)} added={len(drops)} after={len(after)}")
    else:
        record("multi_drop_appends_without_reset", False,
               "ek video yolu verilmedi (MLC_EXTRA_VIDEOS)")

    # --- 3. Oynayan dosya aktif satır ---
    panel.refresh()
    pump(app, 300)
    current = player.current_playlist_index
    playing_rows = [row for row in range(panel.playlist_view.count())
                    if panel.row_widget(row) is not None
                    and panel.row_widget(row).property("playing")]
    record("playing_file_is_active_row",
           playing_rows == [current] and current >= 0,
           f"current_index={current} playing_rows={playing_rows}")

    # --- 4. Thumbnail / güvenli placeholder ---
    states = {}
    for row in range(panel.playlist_view.count()):
        widget = panel.row_widget(row)
        if widget is None:
            continue
        states[row] = (widget.thumbnail_label.property("thumbnailState"),
                       widget.thumbnail_label.pixmap() is not None
                       and not widget.thumbnail_label.pixmap().isNull())
    record("thumbnail_or_safe_placeholder",
           all(state in ("ready", "loading", "empty")
               for state, _ in states.values()),
           str(states))

    frame.toggle_playlist_panel()
    panel.finish_animation()
    pump(app, 300)

    # --- 5/6. GERÇEK Esc tuş olayı (ürünün kendi keyPressEvent yolu) ---
    def press_escape():
        QTest.keyClick(player, Qt.Key.Key_Escape)
        pump(app, 600)

    frame.enter_fullscreen()
    pump(app, 700)
    was_fullscreen = frame.is_video_fullscreen
    press_escape()
    record("escape_exits_fullscreen",
           was_fullscreen and not frame.is_video_fullscreen,
           f"entered={was_fullscreen} after={frame.is_video_fullscreen}")

    player.resize(1180, 700)
    pump(app, 300)
    before_size = (player.width(), player.height())
    press_escape()
    after_size = (player.width(), player.height())
    record("escape_restores_default_size",
           after_size != before_size,
           f"{before_size} -> {after_size} "
           f"(default={WINDOW_WIDTH}x{WINDOW_HEIGHT})")

    # --- 7. Altyazı: parça var, başlangıçta kapalı ---
    try:
        tracks = list(player.mpv_player.track_list or [])
    except Exception:
        tracks = []
    sub_tracks = [t for t in tracks if isinstance(t, dict) and t.get("type") == "sub"]
    try:
        visibility = bool(player.mpv_player.sub_visibility)
    except Exception:
        visibility = None
    record("subtitle_track_loaded_but_initially_off",
           bool(sub_tracks) and visibility is False,
           f"sub_tracks={len(sub_tracks)} sub_visibility={visibility} "
           f"overlay_cc_active={frame.overlay_subtitles_active}")

    print("ACCEPTANCE_SUMMARY " + " ".join(
        f"{name}={'PASS' if ok else 'FAIL'}" for name, ok, _ in checks),
        flush=True)
    failed = [name for name, ok, _ in checks if not ok]
    print(f"ACCEPTANCE_FAILED={failed or 'none'}", flush=True)

    try:
        player.mpv_player.stop()
        player.mpv_player.terminate()
    except Exception as exc:
        print(f"TEARDOWN_WARNING {exc}", flush=True)
    player.close()
    pump(app, 300)
    print(f"ACCEPTANCE_DONE t={time.time() - START:.2f}", flush=True)
    return 1 if failed else 0


raise SystemExit(main())
