from types import SimpleNamespace

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QSlider, QVBoxLayout, QWidget

from app.media_controls import open_path, play_pause, stop
from app.player import MPVPlayer
from app.video_frame import VideoFrame


def make_product_window(monkeypatch, tmp_path):
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.central_widget = QWidget(window)
    window.setCentralWidget(window.central_widget)
    window.main_layout = QVBoxLayout(window.central_widget)
    window.duration = 100.0
    window.position = 50.0
    window.is_paused = True
    window.current_file = ""
    window.playlist = []
    window.current_playlist_index = -1
    window._core_idle = False
    window._load_started_at = 0
    window._audio_menu_file = ""
    window._chapter_menu_file = ""
    window._pending_subs = []
    window._updating_position_slider = False
    window.position_slider = QSlider()
    window.position_slider.setRange(0, 1000)
    window.current_time_label = QLabel()
    window.total_time_label = QLabel()
    window.play_button = SimpleNamespace(setIcon=lambda icon: None)
    window.play_icon = object()
    window.pause_icon = object()
    window.settings = QSettings()
    window.last_dir = ""
    window.mpv_player = SimpleNamespace(
        track_list=[], time_pos=0.0, pause=False,
        play=lambda path: None, stop=lambda: None,
    )
    window.set_title = lambda: None
    window.add_recent_file = lambda path: None
    window.update_time_label = lambda: None
    frame = VideoFrame(window)
    window.video_frame = frame
    window.main_layout.addWidget(frame)
    window.resize(900, 600)
    window.show()
    app.processEvents()
    return app, window, frame


def test_product_update_ui_clears_overlay_when_duration_becomes_zero(monkeypatch, tmp_path):
    app, window, frame = make_product_window(monkeypatch, tmp_path)
    frame.update_overlay_state()
    window.position = 0
    window.duration = 0

    MPVPlayer.update_ui(window)

    assert frame.overlay_timeline.value() == 0
    assert frame.overlay_current_time_label.text() == "00:00"
    assert frame.overlay_total_time_label.text() == "00:00"
    window.close()
    app.processEvents()


def test_product_file_open_and_stop_states_reach_overlay_on_update(monkeypatch, tmp_path):
    app, window, frame = make_product_window(monkeypatch, tmp_path)
    open_path(window, "video.mkv")
    window.duration = 100
    window.position = 0
    window._audio_menu_file = window.current_file
    window._chapter_menu_file = window.current_file
    MPVPlayer.update_ui(window)
    assert frame.overlay_play_pause_button.accessibleName() == "Duraklat"

    window.is_paused = False
    frame.update_overlay_play_state()
    stop(window)
    MPVPlayer.update_ui(window)
    assert frame.overlay_play_pause_button.accessibleName() == "Oynat"
    window.close()
    app.processEvents()


def test_product_play_pause_keeps_instant_overlay_update(monkeypatch, tmp_path):
    app, window, frame = make_product_window(monkeypatch, tmp_path)
    window.current_file = "video.mkv"
    window.is_paused = True

    play_pause(window)
    assert frame.overlay_play_pause_button.accessibleName() == "Duraklat"

    play_pause(window)
    assert frame.overlay_play_pause_button.accessibleName() == "Oynat"
    window.close()
    app.processEvents()
