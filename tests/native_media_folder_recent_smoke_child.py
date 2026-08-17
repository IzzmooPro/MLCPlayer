# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in gerçek Windows kabulü: `Klasör Aç` + `Son Açılanlar`.

Gerçek `MPVPlayer` penceresinde, kendi geçici test klasöründe ölçülenler:

- ana `Ortam` ve sağ-tık `Medya Aç` satır sırası (ekran görüntüleriyle);
- klasör seçildikten sonra playlist sırasının `Bölüm 1, 2, 10` olması;
- alt klasördeki medyanın, altyazının ve metin dosyasının ALINMAMASI;
- ilk dosyanın oynatılması ve playlist panelinin ANINDA aynı modeli
  göstermesi (thumbnail akışı mevcut panel yolundan devam eder);
- `Son Açılanlar`ın iki menüde de aynı içerikle güncellenmesi;
- eksik yerel girdinin listeden ve QSettings'ten güvenli temizlenmesi;
- URL girdisinin yerel dosya sanılmaması;
- menü kapandıktan sonra overlay bastırma ve pencere odağının normale
  dönmesi.

``MLC_NATIVE_SMOKE=1`` verilmeden hiçbir Qt/MPV nesnesi oluşturmaz.
Yalnız KENDİ oluşturduğu geçici klasörü siler; kullanıcının dosyalarına
veya süreçlerine dokunmaz.
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

from PyQt6.QtCore import QPoint, QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from app.player import MPVPlayer  # noqa: E402
from app.playlist_panel import PATH_ROLE  # noqa: E402

VIDEO_PATH = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
RECENT_URL = "https://ornek.test/yayin.m3u8"
SHOT_DIR = os.environ.get("TEMP", ".")

START = time.time()
failures = []


def mark(name, extra=""):
    print(f"{name} t={time.time() - START:.2f} {extra}".rstrip(), flush=True)


def _excepthook(exc_type, exc_value, exc_tb):
    import traceback
    print("PYTHON_EXCEPTION " + "".join(
        traceback.format_exception(exc_type, exc_value, exc_tb)).strip(),
        flush=True)
    instance = QApplication.instance()
    if instance is not None:
        instance.exit(90)


sys.excepthook = _excepthook


def rows(menu):
    return ["---" if action.isSeparator() else action.text()
            for action in menu.actions()]


def submenu(menu, title):
    for action in menu.actions():
        if action.text() == title and action.menu() is not None:
            return action.menu()
    return None


def find_action(menu, title):
    for action in menu.actions():
        if action.text() == title:
            return action
    return None


def capture(app, name, widget=None):
    """Ekranı ve istenirse widget'ın KENDİSİNİ kaydeder.

    Tam ekran yakalama başka bir uygulama öne geçtiğinde menüyü
    gösteremeyebilir; `widget.grab()` menüyü her durumda kanıtlar.
    """
    app.processEvents()
    path = os.path.join(SHOT_DIR, f"MLCPlayer-{name}.png")
    try:
        QApplication.primaryScreen().grabWindow(0).save(path)
        print(f"SHOT {name} {path}", flush=True)
    except Exception as exc:
        print(f"SHOT_FAILED {name} {exc}", flush=True)
        path = ""
    if widget is not None:
        widget_path = os.path.join(SHOT_DIR, f"MLCPlayer-{name}-widget.png")
        try:
            widget.grab().save(widget_path)
            print(f"SHOT {name}-widget {widget_path}", flush=True)
        except Exception as exc:
            print(f"SHOT_FAILED {name}-widget {exc}", flush=True)
    return path


def build_workspace():
    """Spec'teki içerikle KENDİ geçici test klasörümüz."""
    workspace = tempfile.mkdtemp(prefix="mlc_media_folder_smoke_")
    folder = os.path.join(workspace, "Dizi")
    nested = os.path.join(folder, "alt-klasör")
    os.makedirs(nested)
    suffix = ".mkv"
    if VIDEO_PATH and os.path.isfile(VIDEO_PATH):
        suffix = os.path.splitext(VIDEO_PATH)[1] or ".mkv"

    def media(path):
        if VIDEO_PATH and os.path.isfile(VIDEO_PATH):
            shutil.copyfile(VIDEO_PATH, path)
        else:
            with open(path, "wb") as handle:
                handle.write(b"\x00" * 64)

    for name in ("Bölüm 10", "Bölüm 2", "Bölüm 1"):
        media(os.path.join(folder, name + suffix))
    media(os.path.join(nested, "İçeride" + suffix))
    with open(os.path.join(folder, "not.txt"), "w", encoding="utf-8") as f:
        f.write("x")
    with open(os.path.join(folder, "altyazi.srt"), "w", encoding="utf-8") as f:
        f.write("x")
    expected = [f"Bölüm {index}{suffix}" for index in (1, 2, 10)]
    return workspace, folder, expected


def main():
    settings_dir = os.environ.get("MLC_NATIVE_SETTINGS")
    if settings_dir:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, settings_dir)

    workspace, folder, expected_order = build_workspace()
    app = QApplication(sys.argv)
    player = MPVPlayer()
    player.resize(1280, 760)
    player.show()
    app.processEvents()
    frame = player.video_frame
    mark("MARK_SHOWN")

    # --- A) Menü satırları ---
    file_rows = rows(player.menuBar().actions()[0].menu())
    mark("MARK_MAIN_MENU", str(file_rows))
    if ("Klasör Aç" not in file_rows
            or file_rows.index("Klasör Aç") != file_rows.index("Dosya Aç") + 1):
        failures.append(f"MAIN_MENU_ORDER={file_rows}")

    media_rows = rows(submenu(frame.build_context_menu(), "Medya Aç"))
    expected_media = ["Dosya Aç", "Klasör Aç", "Bağlantıdan Oynat", "---",
                      "Son Açılanlar"]
    mark("MARK_CONTEXT_MEDIA", str(media_rows))
    if media_rows != expected_media:
        failures.append(f"CONTEXT_MEDIA_ROWS={media_rows}")

    # --- B) Gerçek popup + ekran görüntüleri ---
    popup = frame.build_context_menu()
    state = {"media": None}

    def show_media_submenu():
        action = find_action(popup, "Medya Aç")
        popup.setActiveAction(action)
        media = action.menu()
        state["media"] = media
        media.popup(popup.mapToGlobal(QPoint(popup.width() - 8, 40)))
        app.processEvents()
        capture(app, "media-menu", media)

    def show_recent_submenu():
        media = state["media"]
        recent_action = find_action(media, "Son Açılanlar")
        media.setActiveAction(recent_action)
        recent_menu = recent_action.menu()
        recent_menu.popup(media.mapToGlobal(QPoint(media.width() - 8, 70)))
        app.processEvents()
        capture(app, "recent-menu", recent_menu)

    QTimer.singleShot(350, show_media_submenu)
    QTimer.singleShot(800, show_recent_submenu)
    QTimer.singleShot(1400, popup.close)
    popup.popup(player.mapToGlobal(QPoint(140, 140)))
    deadline = time.time() + 4.0
    while popup.isVisible() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    if popup.isVisible():
        failures.append("CONTEXT_MENU_STUCK_VISIBLE")
        popup.close()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()
    mark("MARK_POPUP_CLOSED",
         f"overlay_suppressed={frame.overlay_suppressed()} "
         f"window_active={player.isActiveWindow()}")
    if frame.overlay_suppressed():
        failures.append("OVERLAY_STILL_SUPPRESSED_AFTER_MENU")

    # --- C) Playlist paneli açık: anlık güncelleme ölçülebilsin ---
    if not frame.playlist_panel.is_open:
        frame.toggle_playlist_panel()
    frame.playlist_panel.finish_animation()
    app.processEvents()

    # --- D) Klasör Aç ---
    original_dialog = QFileDialog.getExistingDirectory
    original_warning = QMessageBox.warning
    warnings = []
    try:
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: folder)
        QMessageBox.warning = staticmethod(
            lambda *a, **k: warnings.append(a[1:3]))
        find_action(submenu(frame.build_context_menu(), "Medya Aç"),
                    "Klasör Aç").trigger()
        app.processEvents()
        time.sleep(0.8)
        app.processEvents()

        names = [os.path.basename(path) for path in player.playlist]
        view = frame.playlist_panel.playlist_view
        panel_names = [os.path.basename(str(view.item(row).data(PATH_ROLE)))
                       for row in range(view.count())]
        mark("MARK_FOLDER",
             f"playlist={names} panel={panel_names} "
             f"index={player.current_playlist_index} "
             f"current={os.path.basename(player.current_file)} "
             f"last_dir_ok={os.path.normpath(player.last_dir) == os.path.normpath(folder)}")
        if names != expected_order:
            failures.append(f"FOLDER_ORDER={names}")
        if panel_names != names:
            failures.append(f"PANEL_MODEL_MISMATCH={panel_names}")
        if any(name in names for name in ("not.txt", "altyazi.srt")):
            failures.append("FOLDER_INCLUDED_NON_MEDIA")
        if any("İçeride" in name for name in names):
            failures.append("FOLDER_INCLUDED_SUBFOLDER_MEDIA")
        if player.current_playlist_index != 0:
            failures.append(f"FOLDER_INDEX={player.current_playlist_index}")
        if os.path.basename(player.current_file) != expected_order[0]:
            failures.append(f"FOLDER_CURRENT={player.current_file}")
        if len(set(player.playlist)) != len(player.playlist):
            failures.append("FOLDER_DUPLICATE_ENTRY")
        capture(app, "folder-playlist", frame.playlist_panel)

        # --- E) Son Açılanlar iki menüde de güncel ---
        player.add_recent_file(RECENT_URL)
        app.processEvents()
        main_recent = rows(player.recent_menu)
        context_recent = rows(submenu(
            submenu(frame.build_context_menu(), "Medya Aç"), "Son Açılanlar"))
        mark("MARK_RECENT", f"main={main_recent[:3]} context={context_recent[:3]}")
        if main_recent != context_recent:
            failures.append("RECENT_MENUS_DIVERGED")
        if main_recent[:2] != ["yayin.m3u8", expected_order[0]]:
            failures.append(f"RECENT_HEAD={main_recent[:2]}")
        if len(main_recent) > 10:
            failures.append(f"RECENT_OVER_LIMIT={len(main_recent)}")
        for text in main_recent:
            if "/" in text or os.sep in text:
                failures.append(f"RECENT_RAW_PATH_IN_LABEL={text}")

        # --- F) URL girdisi yerel dosya sanılmamalı ---
        # NOT: URL'i açmak `current_file`/`playlist`i MEŞRU biçimde
        # değiştirir (mevcut `open_path` akışı). Eksik-dosya kontrolü bu
        # yüzden kendi anlık state'ini referans alır.
        url_action = find_action(player.recent_menu, "yayin.m3u8")
        if url_action is None or url_action.data() != RECENT_URL:
            failures.append("RECENT_URL_DATA_MISSING")
        else:
            before_warnings = len(warnings)
            recent_before = list(player.recent_files)
            url_action.trigger()
            app.processEvents()
            time.sleep(0.4)
            app.processEvents()
            mark("MARK_RECENT_URL",
                 f"warnings={len(warnings) - before_warnings} "
                 f"still_listed={RECENT_URL in player.recent_files}")
            if len(warnings) != before_warnings:
                failures.append("RECENT_URL_TREATED_AS_MISSING_FILE")
            if RECENT_URL not in player.recent_files:
                failures.append("RECENT_URL_DROPPED")
            if len(recent_before) != len(player.recent_files):
                failures.append("RECENT_URL_CHANGED_MODEL_SIZE")

        # --- G) Eksik yerel girdi güvenle temizlenmeli ---
        missing = os.path.join(folder, "Silinmis" + os.path.splitext(
            expected_order[0])[1])
        with open(missing, "wb") as handle:
            handle.write(b"\x00" * 64)
        player.add_recent_file(missing)
        os.remove(missing)
        app.processEvents()
        playlist_before = list(player.playlist)
        index_before = player.current_playlist_index
        current_before = player.current_file
        before_warnings = len(warnings)
        find_action(player.recent_menu,
                    os.path.basename(missing)).trigger()
        app.processEvents()
        time.sleep(0.3)
        app.processEvents()
        stored = list(player.settings.value("recent_files", []) or [])
        mark("MARK_RECENT_MISSING",
             f"warned={len(warnings) - before_warnings} "
             f"in_model={missing in player.recent_files} "
             f"in_settings={missing in stored} "
             f"playlist_kept={player.playlist == playlist_before}")
        if len(warnings) - before_warnings != 1:
            failures.append("MISSING_RECENT_NOT_WARNED")
        elif warnings[-1][1] != ("Dosya artık mevcut değil. "
                                 "Son Açılanlar listesinden kaldırıldı."):
            failures.append(f"MISSING_RECENT_MESSAGE={warnings[-1][1]}")
        if missing in player.recent_files:
            failures.append("MISSING_RECENT_KEPT_IN_MODEL")
        if missing in stored:
            failures.append("MISSING_RECENT_KEPT_IN_SETTINGS")
        if (player.playlist != playlist_before
                or player.current_playlist_index != index_before
                or player.current_file != current_before):
            failures.append("MISSING_RECENT_DISTURBED_PLAYBACK")
        context_after = rows(submenu(
            submenu(frame.build_context_menu(), "Medya Aç"), "Son Açılanlar"))
        if os.path.basename(missing) in context_after:
            failures.append("MISSING_RECENT_STILL_IN_CONTEXT_MENU")
    finally:
        QFileDialog.getExistingDirectory = original_dialog
        QMessageBox.warning = original_warning

    print(f"RESULTS: failures={','.join(failures) or 'none'} "
          f"video={'real' if VIDEO_PATH and os.path.isfile(VIDEO_PATH) else 'none'}",
          flush=True)

    try:
        player.mpv_player.stop()
        player.mpv_player.terminate()
    except Exception as exc:
        print(f"TEARDOWN_WARNING {exc}", flush=True)
    player.close()
    # Yalnız KENDİ oluşturduğumuz geçici workspace silinir.
    if os.path.basename(workspace).startswith("mlc_media_folder_smoke_"):
        shutil.rmtree(workspace, ignore_errors=True)
    mark("MARK_DONE", f"failures={len(failures)}")
    return 1 if failures else 0


raise SystemExit(main())
