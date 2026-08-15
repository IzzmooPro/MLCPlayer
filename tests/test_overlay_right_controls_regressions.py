"""Overlay sağ kontrol grubu (CC, ayarlar, ses, ses slider'ı, tam ekran) testleri.

Gerçek widget geometrisi, gerçek QIcon pixmap'i ve gerçek ses akışı ölçülür.
Modal Video Ayarları penceresi açılmaz; bağlantı geçici test fonksiyonuyla ölçülür.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QRect, QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QSlider, QVBoxLayout, QWidget)

from app.config import MAX_VOLUME
from app.video_frame import VideoFrame

RIGHT_ORDER = ("overlaySubtitles", "overlaySettings", "overlayVolume",
               "overlayVolumeSlider", "overlayFullscreen")


@pytest.fixture
def video_window(monkeypatch, tmp_path):
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(enabled=True, size=(1280, 720)):
        if enabled:
            monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
        else:
            monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", "1")
        # Kullanıcının gerçek ses ayarlarına dokunmamak için.
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          str(tmp_path))
        app = qt_app()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(0, 0, 0, 0)
        window.is_paused = True
        window.duration = 0
        window.position = 0
        window.is_muted = False
        window.calls = []
        # Klasik ses çubuğu ürünle aynı aralıkta; valueChanged ürünün
        # set_volume akışını temsil eder.
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.volume_slider.setRange(0, MAX_VOLUME)
        window.volume_slider.valueChanged.connect(
            lambda value: window.calls.append(("set_volume", value)))
        window.volume_slider.setValue(70)
        window.toggle_subtitles = lambda: window.calls.append(("toggle_subtitles",))
        window.toggle_mute = lambda: window.calls.append(("toggle_mute",))
        window.setup_video_adjustments = lambda: window.calls.append(
            ("setup_video_adjustments",))
        window.toggle_fullscreen = lambda: window.calls.append(("toggle_fullscreen",))
        window.play_previous = lambda: window.calls.append(("play_previous",))
        window.play_next = lambda: window.calls.append(("play_next",))
        window.play_pause = lambda: window.calls.append(("play_pause",))
        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(*size)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
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


def widget_by_name(overlay, name):
    return next(w for w in overlay.findChildren(QWidget)
                if w.objectName() == name)


def centre_x(overlay, widget):
    return widget.mapTo(overlay, widget.rect().center()).x()


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


# --- Sıralama ve yerleşim ---

def test_right_group_visual_order_matches_reference(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    positions = [centre_x(overlay, widget_by_name(overlay, name))
                 for name in RIGHT_ORDER]
    assert positions == sorted(positions), dict(zip(RIGHT_ORDER, positions))


def test_right_group_sits_right_of_the_centre_controls(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    play_right = widget_by_name(overlay, "overlayPlayPause").mapTo(
        overlay, widget_by_name(overlay, "overlayPlayPause").rect().topRight()).x()
    assert centre_x(overlay, widget_by_name(overlay, "overlaySubtitles")) > play_right


def test_centre_play_button_keeps_true_horizontal_centre_at_1280(video_window):
    app, window, frame = video_window(size=(1280, 720))
    overlay = frame.control_overlay
    play = widget_by_name(overlay, "overlayPlayPause")
    assert abs(centre_x(overlay, play) - overlay.width() // 2) <= 6


def test_volume_slider_width_is_in_reference_range(video_window):
    app, window, frame = video_window()
    slider = frame.overlay_volume_slider
    assert 80 <= slider.width() <= 110
    assert slider.minimumWidth() < 80, "dar pencerede küçülebilmeli"


def test_right_controls_stay_inside_overlay_at_minimum_window(video_window):
    app, window, frame = video_window(size=(400, 300))
    app.processEvents()
    frame.update_overlay_geometry()
    overlay = frame.control_overlay
    overlay_rect = overlay.geometry()

    for name in RIGHT_ORDER:
        rect = global_rect(widget_by_name(overlay, name))
        assert overlay_rect.contains(rect), f"{name} {rect} overlay dışına taştı"
        assert rect.width() > 0 and rect.height() > 0


def test_right_control_icons_do_not_overlap(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    rects = [global_rect(widget_by_name(overlay, name)) for name in RIGHT_ORDER]
    for first, second in zip(rects, rects[1:]):
        assert not first.intersects(second)


# --- Metin, ikon, erişilebilirlik ---

def test_new_right_buttons_have_no_visible_text(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    for name in ("overlaySubtitles", "overlayVolume", "overlaySettings"):
        assert widget_by_name(overlay, name).text() == ""


def test_new_right_buttons_carry_non_null_icons(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    for name in ("overlaySubtitles", "overlayVolume", "overlaySettings"):
        button = widget_by_name(overlay, name)
        assert not button.icon().isNull()
        assert not button.icon().pixmap(button.iconSize()).isNull()


def test_new_right_buttons_expose_tooltip_and_accessible_name(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    expected = {
        # CC etiketi artık gerçek altyazı durumunu yansıtır
        # (bkz. test_overlay_subtitle_state_regressions).
        "overlaySubtitles": "Altyazıları Aç",
        "overlayVolume": "Sessiz",
        "overlaySettings": "Video Ayarları",
    }
    for name, label in expected.items():
        button = widget_by_name(overlay, name)
        assert button.toolTip() == label
        assert button.accessibleName() == label


# --- Gerçek bağlantılar ---

def test_subtitles_button_calls_real_toggle_subtitles(video_window):
    app, window, frame = video_window()
    QTest.mouseClick(widget_by_name(frame.control_overlay, "overlaySubtitles"),
                     Qt.MouseButton.LeftButton)
    assert ("toggle_subtitles",) in window.calls


def test_settings_button_calls_real_setup_video_adjustments(video_window):
    app, window, frame = video_window()
    QTest.mouseClick(widget_by_name(frame.control_overlay, "overlaySettings"),
                     Qt.MouseButton.LeftButton)
    assert ("setup_video_adjustments",) in window.calls


def test_volume_button_calls_real_toggle_mute(video_window):
    app, window, frame = video_window()
    QTest.mouseClick(widget_by_name(frame.control_overlay, "overlayVolume"),
                     Qt.MouseButton.LeftButton)
    assert ("toggle_mute",) in window.calls


def test_volume_button_icon_and_label_follow_is_muted(video_window):
    app, window, frame = video_window()
    button = frame.overlay_volume_button

    window.is_muted = False
    frame.update_overlay_state()
    loud_key = button.icon().pixmap(button.iconSize()).cacheKey()
    assert button.accessibleName() == "Sessiz"

    window.is_muted = True
    frame.update_overlay_state()
    muted_key = button.icon().pixmap(button.iconSize()).cacheKey()
    assert button.accessibleName() == "Sesi Aç"
    assert button.toolTip() == "Sesi Aç"
    assert loud_key != muted_key


def test_zero_volume_switches_to_muted_icon(video_window):
    app, window, frame = video_window()
    button = frame.overlay_volume_button
    window.volume_slider.setValue(0)
    frame.update_overlay_state()
    assert button.accessibleName() == "Sesi Aç"


# --- Ses senkronizasyonu ---

def test_overlay_volume_uses_the_product_volume_range(video_window):
    app, window, frame = video_window()
    assert frame.overlay_volume_slider.minimum() == 0
    assert frame.overlay_volume_slider.maximum() == MAX_VOLUME


def test_overlay_volume_starts_in_sync_with_classic_slider(video_window):
    app, window, frame = video_window()
    assert frame.overlay_volume_slider.value() == window.volume_slider.value()


def test_user_change_on_overlay_reaches_the_real_volume_flow(video_window):
    app, window, frame = video_window()
    window.calls.clear()

    frame.overlay_volume_slider.setValue(130)
    app.processEvents()

    assert window.volume_slider.value() == 130
    assert ("set_volume", 130) in window.calls


def test_amplification_above_100_is_preserved(video_window):
    app, window, frame = video_window()
    frame.overlay_volume_slider.setValue(MAX_VOLUME)
    app.processEvents()
    assert window.volume_slider.value() == MAX_VOLUME


def test_classic_volume_change_updates_overlay_slider(video_window):
    app, window, frame = video_window()
    window.volume_slider.setValue(45)
    frame.update_overlay_state()
    assert frame.overlay_volume_slider.value() == 45


def test_programmatic_overlay_sync_does_not_repeat_set_volume(video_window):
    app, window, frame = video_window()
    window.volume_slider.setValue(45)
    app.processEvents()
    window.calls.clear()

    for _ in range(3):
        frame.update_overlay_state()
    app.processEvents()

    assert [call for call in window.calls if call[0] == "set_volume"] == []
    assert frame.overlay_volume_slider.value() == 45


def test_overlay_volume_slider_is_not_overwritten_while_dragged(video_window):
    app, window, frame = video_window()
    slider = frame.overlay_volume_slider
    slider.setSliderDown(True)
    slider.setValue(150)
    window.volume_slider.blockSignals(True)
    window.volume_slider.setValue(20)
    window.volume_slider.blockSignals(False)

    frame.update_overlay_state()
    assert slider.value() == 150
    slider.setSliderDown(False)


# --- Korunan davranışlar ---

def test_fullscreen_button_is_last_and_keeps_its_connection(video_window):
    app, window, frame = video_window()
    overlay = frame.control_overlay
    positions = {name: centre_x(overlay, widget_by_name(overlay, name))
                 for name in RIGHT_ORDER}
    assert positions["overlayFullscreen"] == max(positions.values())

    QTest.mouseClick(widget_by_name(overlay, "overlayFullscreen"),
                     Qt.MouseButton.LeftButton)
    assert ("toggle_fullscreen",) in window.calls


def test_right_controls_exist_even_with_legacy_classic_env(video_window):
    """Legacy klasik anahtar sağ kontrol grubunu artık kaldıramaz."""
    app, window, frame = video_window(enabled=False)
    assert frame.control_overlay is not None
    assert hasattr(frame, "overlay_volume_slider")
    assert hasattr(frame, "overlay_volume_button")


def test_fullscreen_enter_and_exit_still_work(video_window):
    app, window, frame = video_window()
    frame.enter_fullscreen()
    app.processEvents()
    assert frame.is_video_fullscreen is True
    assert frame.control_overlay.isVisible()

    frame.exit_fullscreen()
    app.processEvents()
    assert frame.is_video_fullscreen is False
    assert frame.control_overlay.isVisible()
