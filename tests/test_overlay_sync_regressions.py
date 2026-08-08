from types import SimpleNamespace

from PyQt6.QtCore import QPoint, QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from app.video_frame import VideoFrame


def make_sync_window(monkeypatch, tmp_path):
    monkeypatch.setenv("MLCPLAYER_OVERLAY_PREVIEW", "1")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.central_widget = QWidget(window)
    window.setCentralWidget(window.central_widget)
    window.main_layout = QVBoxLayout(window.central_widget)
    window.duration = 100.0
    window.position = 10.0
    window.is_paused = True
    window.seek_calls = []
    window.play_previous = lambda: None
    window.play_next = lambda: None
    window.toggle_fullscreen = lambda: None
    window.seek_position = lambda value: window.seek_calls.append(value)
    frame = VideoFrame(window)
    window.video_frame = frame

    def play_pause():
        window.is_paused = not window.is_paused
        frame.update_overlay_play_state()

    window.play_pause = play_pause
    window.main_layout.addWidget(frame)
    window.resize(900, 600)
    window.show()
    app.processEvents()
    return app, window, frame


def test_overlay_timeline_and_time_labels_follow_position_and_duration(monkeypatch, tmp_path):
    app, window, frame = make_sync_window(monkeypatch, tmp_path)
    window.position = 65.0
    window.duration = 130.0

    frame.update_overlay_state()

    assert frame.overlay_timeline.value() == 500
    assert frame.overlay_current_time_label.text() == "01:05"
    assert frame.overlay_total_time_label.text() == "02:10"
    window.close()
    app.processEvents()


def test_overlay_invalid_duration_resets_timeline_and_time_labels(monkeypatch, tmp_path):
    app, window, frame = make_sync_window(monkeypatch, tmp_path)
    window.position = 65.0
    window.duration = 0

    frame.update_overlay_state()

    assert frame.overlay_timeline.value() == 0
    assert frame.overlay_current_time_label.text() == "00:00"
    assert frame.overlay_total_time_label.text() == "00:00"
    window.close()
    app.processEvents()


def test_overlay_time_format_has_unpadded_hours(monkeypatch, tmp_path):
    app, window, frame = make_sync_window(monkeypatch, tmp_path)
    cases = ((0, "00:00"), (65, "01:05"), (3661, "1:01:01"),
             (None, "00:00"), ("invalid", "00:00"))

    for seconds, expected in cases:
        window.position = seconds
        window.duration = 7200 if isinstance(seconds, (int, float)) else 0
        frame.update_overlay_state()
        assert frame.overlay_current_time_label.text() == expected

    window.close()
    app.processEvents()


def test_overlay_programmatic_timeline_update_does_not_seek(monkeypatch, tmp_path):
    app, window, frame = make_sync_window(monkeypatch, tmp_path)
    window.position = 50.0
    window.duration = 100.0

    frame.update_overlay_state()

    assert frame.overlay_timeline.value() == 500
    assert window.seek_calls == []
    window.close()
    app.processEvents()


def test_overlay_drag_seeks_and_timer_does_not_snap_back(monkeypatch, tmp_path):
    app, window, frame = make_sync_window(monkeypatch, tmp_path)
    slider = frame.overlay_timeline
    slider.resize(500, slider.height())
    start = QPoint(100, slider.height() // 2)
    end = QPoint(350, slider.height() // 2)

    QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    pressed_value = slider.value()
    QTest.mouseMove(slider, end, 50)
    moved_value = slider.value()
    assert slider.isSliderDown()
    assert moved_value != pressed_value
    assert window.seek_calls

    window.position = 10.0
    frame.update_overlay_state()
    assert slider.value() == moved_value

    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    assert not slider.isSliderDown()
    window.position = 75.0
    frame.update_overlay_state()
    assert slider.value() == 750
    window.close()
    app.processEvents()


def test_overlay_play_pause_text_follows_player_state(monkeypatch, tmp_path):
    app, window, frame = make_sync_window(monkeypatch, tmp_path)

    frame.update_overlay_play_state()
    assert frame.overlay_play_pause_button.text() == "Oynat"

    window.play_pause()
    assert frame.overlay_play_pause_button.text() == "Duraklat"

    window.play_pause()
    assert frame.overlay_play_pause_button.text() == "Oynat"
    window.close()
    app.processEvents()
