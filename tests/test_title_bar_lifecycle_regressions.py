"""Başlık çubuğu yaşam döngüsü regresyon testleri.

1) Fullscreen çıkışında z-order yardımcısının çağrıldığı anda
   is_video_fullscreen kesin olarak False olmalı.
2) Gerçek oynatma yollarının hepsi (Dosya Aç, doğrudan path/drag-drop, URL,
   playlist) tek seferlik z-order yenilemesini işaretlemeli.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QInputDialog, QLabel, QMainWindow, QSlider,
    QVBoxLayout, QWidget)

from app import media_controls
from app.video_frame import VideoFrame


@pytest.fixture
def product_window(monkeypatch, tmp_path):
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(preview=True, play_fails=False, pending=False):
        if preview:
            monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
        else:
            monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          str(tmp_path))
        app = qt_app()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(0, 0, 0, 0)

        window.duration = 0
        window.position = 0
        window.is_paused = True
        window.is_muted = False
        window.current_file = ""
        window.playlist = []
        window.current_playlist_index = -1
        window._core_idle = False
        window._load_started_at = 0
        window._audio_menu_file = ""
        window._chapter_menu_file = ""
        window._pending_subs = []
        window._updating_position_slider = False
        window.last_dir = ""
        window.recent_files = []
        window.settings = QSettings()
        window.position_slider = QSlider()
        window.position_slider.setRange(0, 1000)
        window.volume_slider = QSlider()
        window.volume_slider.setRange(0, 175)
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.set_title = lambda: None
        window.add_recent_file = lambda path: None
        window.update_time_label = lambda: None

        def play(path):
            window.played.append(path)
            if play_fails:
                raise RuntimeError("mpv play failed")

        window.played = []
        window.mpv_player = SimpleNamespace(
            track_list=[], time_pos=0.0, pause=False, play=play,
            stop=lambda: None)

        # Ürün tarafındaki z-order yaşam döngüsü bağlantısı
        window.preview_mode = preview
        window.title_bar_raise_marks = []
        window._title_bar_raise_pending = pending

        def clear():
            window._title_bar_raise_pending = False

        window.clear_title_bar_raise_pending = clear

        def mark():
            window.title_bar_raise_marks.append(True)
            if window.preview_mode:
                window._title_bar_raise_pending = True

        window.mark_title_bar_raise_pending = mark

        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(900, 600)
        window.show()
        app.processEvents()
        created.append((window, frame))
        return app, window, frame

    yield factory

    app = qt_app()
    for window, frame in created:
        if frame.is_video_fullscreen:
            frame.exit_fullscreen()
        frame.close_control_overlay()
        window.close()
        window.deleteLater()
    app.processEvents()


# --- 1. Fullscreen çıkışında çağrı sırası ---

def test_exit_fullscreen_calls_helper_after_clearing_the_flag(product_window):
    app, window, frame = product_window()
    seen = []
    window.ensure_title_bar_on_top = lambda: seen.append(
        frame.is_video_fullscreen)

    frame.enter_fullscreen()
    app.processEvents()
    seen.clear()

    frame.exit_fullscreen()

    assert seen, "exit_fullscreen içinden ensure_title_bar_on_top çağrılmadı"
    # Yardımcının çağrıldığı ANDA bayrak False olmalı; aksi halde helper
    # erken dönüyor ve öne alma tesadüfi Qt olaylarına kalıyor.
    assert seen[0] is False, f"helper çağrıldığında flag={seen[0]}"


def test_exit_fullscreen_helper_runs_exactly_once_from_exit_path(product_window):
    app, window, frame = product_window()
    seen = []
    window.ensure_title_bar_on_top = lambda: seen.append(
        frame.is_video_fullscreen)

    frame.enter_fullscreen()
    seen.clear()
    frame.exit_fullscreen()

    assert len(seen) == 1, f"{len(seen)} kez çağrıldı"


def test_exit_fullscreen_still_restores_window_state(product_window):
    app, window, frame = product_window()
    window.ensure_title_bar_on_top = lambda: None
    before = window.geometry()

    frame.enter_fullscreen()
    app.processEvents()
    frame.exit_fullscreen()
    app.processEvents()

    assert frame.is_video_fullscreen is False
    assert window.isFullScreen() is False
    assert window.geometry() == before
    assert frame.control_overlay.isVisible()


def test_preview_disabled_exit_fullscreen_is_unchanged(product_window):
    app, window, frame = product_window(preview=False)
    calls = []
    window.ensure_title_bar_on_top = lambda: calls.append(True)

    frame.enter_fullscreen()
    frame.exit_fullscreen()

    assert frame.is_video_fullscreen is False
    # Ürün kararı: legacy anahtar sinematik overlay'i kaldıramaz.
    assert frame.control_overlay is not None
    assert window._title_bar_raise_pending is False


# --- 2. Gerçek oynatma yolları ---

def test_direct_open_path_marks_pending(product_window, tmp_path):
    app, window, frame = product_window()
    media = tmp_path / "video.mkv"
    media.write_bytes(b"x")

    media_controls.open_path(window, str(media))

    assert window.played == [str(media)]
    assert window.title_bar_raise_marks, "open_path pending işaretlemedi"
    assert window._title_bar_raise_pending is True


def test_open_file_dialog_flow_marks_pending(product_window, tmp_path,
                                             monkeypatch):
    app, window, frame = product_window()
    media = tmp_path / "dialog.mkv"
    media.write_bytes(b"x")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(media), "")))

    media_controls.open_file(window)

    assert window.played == [str(media)]
    assert window._title_bar_raise_pending is True


def test_open_url_flow_marks_pending(product_window, monkeypatch):
    app, window, frame = product_window()
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *args, **kwargs: ("https://example.com/a.mp4", True)))

    media_controls.open_url(window)

    assert window.played == ["https://example.com/a.mp4"]
    assert window._title_bar_raise_pending is True


def test_play_from_playlist_marks_pending(product_window, tmp_path):
    app, window, frame = product_window()
    media = tmp_path / "list.mkv"
    media.write_bytes(b"x")
    window.playlist = [str(media)]

    media_controls.play_from_playlist(window, 0)

    assert window.played == [str(media)]
    assert window._title_bar_raise_pending is True


@pytest.mark.parametrize("flow", ("open_path", "open_url", "play_from_playlist"))
def test_failed_play_leaves_no_stale_pending(product_window, tmp_path,
                                             monkeypatch, flow):
    app, window, frame = product_window(play_fails=True)
    media = tmp_path / "broken.mkv"
    media.write_bytes(b"x")
    # Ürünün hata yolu modal uyarı açıyor; testte engellememesi için izole et.
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda *args, **kwargs: None)

    if flow == "open_path":
        media_controls.open_path(window, str(media))
    elif flow == "open_url":
        monkeypatch.setattr(
            QInputDialog, "getText",
            staticmethod(lambda *args, **kwargs: ("https://x/y.mp4", True)))
        media_controls.open_url(window)
    else:
        window.playlist = [str(media)]
        media_controls.play_from_playlist(window, 0)

    assert window.played, "play çağrılmadı"
    assert window._title_bar_raise_pending is False, "stale pending kaldı"


def test_preview_disabled_flows_do_not_set_pending(product_window, tmp_path):
    app, window, frame = product_window(preview=False)
    media = tmp_path / "video.mkv"
    media.write_bytes(b"x")

    media_controls.open_path(window, str(media))

    assert window.played == [str(media)]
    assert window._title_bar_raise_pending is False


# --- 3. Önceki medyadan kalan pending tüketilmeden yeni oynatma ---

@pytest.mark.parametrize("flow", ("open_path", "open_url", "play_from_playlist"))
def test_failed_play_clears_pending_left_from_previous_media(
        product_window, tmp_path, monkeypatch, flow):
    """İlk medya pending bıraktı, duration henüz 0; ikinci medya patlıyor."""
    app, window, frame = product_window(play_fails=True, pending=True)
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda *args, **kwargs: None)
    media = tmp_path / "second.mkv"
    media.write_bytes(b"x")
    assert window._title_bar_raise_pending is True

    if flow == "open_path":
        media_controls.open_path(window, str(media))
    elif flow == "open_url":
        monkeypatch.setattr(
            QInputDialog, "getText",
            staticmethod(lambda *args, **kwargs: ("https://x/second.mp4", True)))
        media_controls.open_url(window)
    else:
        window.playlist = [str(media)]
        media_controls.play_from_playlist(window, 0)

    assert window.played, "play çağrılmadı"
    assert window._title_bar_raise_pending is False, "eski pending taşındı"


@pytest.mark.parametrize("flow", ("open_path", "open_url", "play_from_playlist"))
def test_successful_play_sets_pending_again_after_clear(
        product_window, tmp_path, monkeypatch, flow):
    app, window, frame = product_window(pending=True)
    media = tmp_path / "again.mkv"
    media.write_bytes(b"x")

    if flow == "open_path":
        media_controls.open_path(window, str(media))
    elif flow == "open_url":
        monkeypatch.setattr(
            QInputDialog, "getText",
            staticmethod(lambda *args, **kwargs: ("https://x/again.mp4", True)))
        media_controls.open_url(window)
    else:
        window.playlist = [str(media)]
        media_controls.play_from_playlist(window, 0)

    assert window.played
    assert window._title_bar_raise_pending is True


def test_preview_disabled_stays_false_after_failed_play(
        product_window, tmp_path, monkeypatch):
    app, window, frame = product_window(preview=False, play_fails=True)
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda *args, **kwargs: None)
    media = tmp_path / "off.mkv"
    media.write_bytes(b"x")

    media_controls.open_path(window, str(media))

    assert window._title_bar_raise_pending is False


@pytest.mark.parametrize("flow", ("empty_path", "cancelled_dialog",
                                  "cancelled_url", "invalid_index"))
def test_cancelled_or_invalid_attempts_do_not_touch_pending(
        product_window, monkeypatch, flow):
    """Gerçek bir yükleme girişimi başlamadıysa mevcut pending korunmalı."""
    app, window, frame = product_window(pending=True)

    if flow == "empty_path":
        media_controls.open_path(window, "")
    elif flow == "cancelled_dialog":
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
                            staticmethod(lambda *args, **kwargs: ("", "")))
        media_controls.open_file(window)
    elif flow == "cancelled_url":
        monkeypatch.setattr(QInputDialog, "getText",
                            staticmethod(lambda *args, **kwargs: ("", False)))
        media_controls.open_url(window)
    else:
        window.playlist = []
        media_controls.play_from_playlist(window, 5)

    assert window.played == [], "oynatma girişimi olmamalıydı"
    assert window._title_bar_raise_pending is True, "mevcut pending bozuldu"
