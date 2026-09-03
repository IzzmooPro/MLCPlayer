# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Overlay timeline tıklama/sürükleme güvenilirliği regresyon testleri.

Gerçek QTest fare olayları, gerçek ClickableSlider ve ürünün gerçek
seek_position akışı (mpv_player.time_pos) ölçülür.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect, QSettings, Qt
from PyQt6.QtGui import QRegion
from PyQt6.QtGui import QColor, QEnterEvent, QPainter, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QSlider, QVBoxLayout, QWidget)

from app import media_controls
from app.config import MAX_VOLUME
from app.video_frame import VideoFrame

# Kullanıcı çizgiyi ~15-20 px kaçırsa bile tıklama seek olmalı.
MIN_HIT_HEIGHT = 44
TARGET_HIT_HEIGHT = 48


@pytest.fixture
def product_window(monkeypatch, tmp_path):
    created = []
    app_ref = []

    def qt_app():
        app = QApplication.instance() or QApplication([])
        if not app_ref:
            app_ref.append(app)
        return app

    def factory(size=(1280, 720)):
        monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          str(tmp_path))
        app = qt_app()
        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.main_layout.setContentsMargins(0, 0, 0, 0)

        window.duration = 600.0
        window.position = 0.0
        window.is_paused = False
        window.is_muted = False
        window.current_file = "<test-video>"
        window._updating_position_slider = False
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.volume_slider.setRange(0, MAX_VOLUME)
        window.volume_slider.setValue(70)
        window.position_slider = QSlider()
        window.position_slider.setRange(0, 1000)
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(time_pos=0.0, pause=False,
                                            track_list=[], stop=lambda: None)
        # Gerçek ürün seek akışı
        window.seek_position = lambda value: media_controls.seek_position(
            window, value)
        for name in ("play_previous", "play_next", "play_pause", "toggle_mute",
                     "toggle_subtitles", "toggle_fullscreen",
                     "setup_video_adjustments"):
            setattr(window, name, lambda: None)

        frame = VideoFrame(window)
        window.video_frame = frame
        window.main_layout.addWidget(frame)
        window.resize(*size)
        window.show()
        app.processEvents()
        frame.update_overlay_geometry()
        frame.show_overlay_for_interaction()
        finish_fade(app, frame)
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


def finish_fade(app, frame):
    animation = getattr(frame, "overlay_fade", None)
    if animation is None:
        return
    if animation.state().name == "Running":
        animation.setCurrentTime(animation.duration())
    app.processEvents()


def send_enter(widget, app):
    centre = widget.rect().center().toPointF()
    event = QEnterEvent(centre, centre,
                        widget.mapToGlobal(widget.rect().center()).toPointF())
    app.sendEvent(widget, event)
    app.processEvents()


def click_at(app, slider, ratio, y):
    """Slider'ın yatay `ratio` konumuna, `y` yüksekliğinde gerçek tıklama."""
    x = max(0, min(slider.width() - 1, int(slider.width() * ratio)))
    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier(0),
                     QPoint(x, y))
    app.processEvents()
    return x


# --- 1. Hit alanı ölçümü ---

def test_timeline_hit_height_is_large_enough_for_real_clicks(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    assert timeline.height() >= MIN_HIT_HEIGHT, (
        f"timeline hit yüksekliği {timeline.height()} px, "
        f"en az {MIN_HIT_HEIGHT} px olmalı")


def test_timeline_visual_groove_stays_thin(product_window):
    app, window, frame = product_window()
    style = frame.control_overlay.styleSheet().lower()
    assert "height: 3px" in style
    assert "#f26a3d" in style


def test_timeline_hit_height_stays_in_reference_range(product_window):
    app, window, frame = product_window()
    assert 44 <= frame.overlay_timeline.height() <= 48


def test_timeline_uses_the_preferred_hit_height(product_window):
    app, window, frame = product_window()
    assert frame.overlay_timeline.height() == TARGET_HIT_HEIGHT


def test_timeline_handle_keeps_its_visual_size(product_window):
    app, window, frame = product_window()
    style = frame.control_overlay.styleSheet().lower()
    assert "width: 11px" in style
    assert "height: 11px" in style


# --- 2/3. Dikey ve yatay noktalarda gerçek tıklama ---

def vertical_point(timeline, y_kind):
    return {"top": 1,
            "near_top": 4,
            "middle": timeline.height() // 2,
            "near_bottom": timeline.height() - 5,
            "bottom": timeline.height() - 2}[y_kind]


Y_KINDS = ("top", "near_top", "middle", "near_bottom", "bottom")


@pytest.mark.parametrize("ratio", (0.10, 0.25, 0.50, 0.75, 0.90))
@pytest.mark.parametrize("y_kind", Y_KINDS)
def test_clicks_across_the_line_seek_reliably(product_window, ratio, y_kind):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    y = vertical_point(timeline, y_kind)

    window.mpv_player.time_pos = 0.0
    timeline.setValue(0)
    before_value = timeline.value()
    before_time = window.mpv_player.time_pos

    click_at(app, timeline, ratio, y)

    assert timeline.value() != before_value, (
        f"ratio={ratio} y={y}: slider değeri değişmedi")
    assert window.mpv_player.time_pos != before_time, (
        f"ratio={ratio} y={y}: MPV time_pos değişmedi")
    expected = (timeline.value() * window.duration) / 1000.0
    assert window.mpv_player.time_pos == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("y_kind", Y_KINDS)
def test_click_value_follows_horizontal_position(product_window, y_kind):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    y = vertical_point(timeline, y_kind)

    values = []
    for ratio in (0.10, 0.50, 0.90):
        click_at(app, timeline, ratio, y)
        values.append(timeline.value())

    assert values == sorted(values), values
    assert values[0] < values[-1]


# --- 4. Sürükleme ---

def test_drag_from_top_edge_to_bottom_edge_keeps_seeking(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    bottom_y = timeline.height() - 2

    QTest.mousePress(timeline, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier(0),
                     QPoint(int(timeline.width() * 0.20), 1))
    app.processEvents()
    assert timeline.isSliderDown() is True
    first = timeline.value()

    QTest.mouseMove(timeline, QPoint(int(timeline.width() * 0.70), bottom_y))
    app.processEvents()
    second = timeline.value()

    assert second > first, f"{first} -> {second}"
    assert window.mpv_player.time_pos == pytest.approx(
        (second * window.duration) / 1000.0, abs=0.01)

    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier(0),
                       QPoint(int(timeline.width() * 0.70), bottom_y))
    app.processEvents()
    assert timeline.isSliderDown() is False


# --- 6/7. Programatik güncelleme ve sürükleme koruması ---

def test_programmatic_update_does_not_seek(product_window):
    app, window, frame = product_window()
    window.mpv_player.time_pos = 42.0
    window.position = 300.0

    frame.update_overlay_state()
    app.processEvents()

    assert window.mpv_player.time_pos == 42.0


def test_update_while_dragging_does_not_pull_the_handle_back(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline

    QTest.mousePress(timeline, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier(0),
                     QPoint(int(timeline.width() * 0.80),
                            timeline.height() // 2))
    app.processEvents()
    dragged = timeline.value()

    window.position = 1.0
    frame.update_overlay_state()
    app.processEvents()

    assert timeline.value() == dragged
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier(0),
                       QPoint(int(timeline.width() * 0.80),
                              timeline.height() // 2))
    app.processEvents()


# --- 8. Fade sonrası ilk tıklama ---

def test_first_click_after_fade_in_still_seeks(product_window):
    app, window, frame = product_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)
    assert not frame.control_overlay.isVisible()

    frame.show_overlay_for_interaction()
    finish_fade(app, frame)
    timeline = frame.overlay_timeline
    window.mpv_player.time_pos = 0.0
    timeline.setValue(0)

    click_at(app, timeline, 0.60, timeline.height() // 2)

    assert timeline.value() > 0
    assert window.mpv_player.time_pos > 0


# --- 9. Minimum pencere ---

def test_minimum_window_keeps_timeline_and_controls_inside(product_window):
    app, window, frame = product_window(size=(400, 300))
    app.processEvents()
    frame.update_overlay_geometry()
    overlay = frame.control_overlay
    overlay_rect = overlay.geometry()

    names = ("overlayTimeline", "overlayPrevious", "overlayPlayPause",
             "overlayNext", "overlaySubtitles", "overlayVolume",
             "overlaySettings", "overlayVolumeSlider", "overlayFullscreen")
    for name in names:
        widget = next(w for w in overlay.findChildren(QWidget)
                      if w.objectName() == name)
        rect = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())
        assert overlay_rect.contains(rect), f"{name} overlay dışına taştı"


def test_overlay_height_is_unchanged(product_window):
    app, window, frame = product_window()
    assert frame.control_overlay.height() == 110


# --- 10. Ses slider'ı değişmemeli ---

def test_volume_slider_geometry_is_unchanged(product_window):
    app, window, frame = product_window()
    slider = frame.overlay_volume_slider
    assert slider.height() == 14
    assert 80 <= slider.width() <= 110


def test_volume_slider_click_still_changes_volume(product_window):
    app, window, frame = product_window()
    slider = frame.overlay_volume_slider
    before = window.volume_slider.value()

    click_at(app, slider, 0.90, slider.height() // 2)

    assert slider.value() != before
    assert window.volume_slider.value() == slider.value()


def test_classic_position_slider_is_untouched(product_window):
    app, window, frame = product_window()
    assert window.position_slider.maximum() == 1000


# --- Geniş hit alanı yerleşimi bozmamalı ---

def test_bottom_control_row_does_not_move(product_window):
    """Timeline büyürken alt medya satırı yerinde kalmalı."""
    app, window, frame = product_window()
    overlay = frame.control_overlay
    play = next(w for w in overlay.findChildren(QWidget)
                if w.objectName() == "overlayPlayPause")
    centre_y = play.mapTo(overlay, QPoint(0, 0)).y() + play.height() // 2
    assert centre_y == 73, f"kontrol satırı kaydı: {centre_y}"


def test_timeline_hit_area_does_not_cover_the_buttons(product_window):
    app, window, frame = product_window()
    overlay = frame.control_overlay
    timeline_rect = QRect(
        frame.overlay_timeline.mapToGlobal(QPoint(0, 0)),
        frame.overlay_timeline.size())

    names = ("overlayPrevious", "overlayPlayPause", "overlayNext",
             "overlaySubtitles", "overlayVolume", "overlaySettings",
             "overlayVolumeSlider", "overlayFullscreen")
    for name in names:
        widget = next(w for w in overlay.findChildren(QWidget)
                      if w.objectName() == name)
        rect = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())
        assert not timeline_rect.intersects(rect), (
            f"{name} timeline hit alanıyla çakışıyor")


def test_bottom_buttons_still_receive_their_clicks(product_window):
    app, window, frame = product_window()
    calls = []
    window.play_pause = lambda: calls.append("play_pause")
    window.toggle_fullscreen = lambda: calls.append("fullscreen")
    overlay = frame.control_overlay

    for name, expected in (("overlayPlayPause", "play_pause"),
                           ("overlayFullscreen", "fullscreen")):
        button = next(w for w in overlay.findChildren(QWidget)
                      if w.objectName() == name)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert expected in calls


def test_drag_from_bottom_edge_to_top_edge_keeps_seeking(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    bottom_y = timeline.height() - 2

    QTest.mousePress(timeline, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier(0),
                     QPoint(int(timeline.width() * 0.25), bottom_y))
    app.processEvents()
    assert timeline.isSliderDown() is True
    first = timeline.value()

    QTest.mouseMove(timeline, QPoint(int(timeline.width() * 0.80), 1))
    app.processEvents()
    second = timeline.value()

    assert second > first, f"{first} -> {second}"
    assert window.mpv_player.time_pos == pytest.approx(
        (second * window.duration) / 1000.0, abs=0.01)

    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier(0),
                       QPoint(int(timeline.width() * 0.80), 1))
    app.processEvents()
    assert timeline.isSliderDown() is False


def test_hidden_overlay_does_not_seek(product_window):
    app, window, frame = product_window()
    frame.hide_overlay_for_inactivity()
    finish_fade(app, frame)
    assert not frame.control_overlay.isVisible()

    window.mpv_player.time_pos = 12.0
    frame.update_overlay_state()
    app.processEvents()

    assert window.mpv_player.time_pos == 12.0


# --- Hover görsel geri bildirimi ---

def overlay_style(frame):
    return frame.control_overlay.styleSheet().lower().replace(" ", "")


def test_timeline_has_a_hover_style_scoped_to_itself(product_window):
    app, window, frame = product_window()
    style = overlay_style(frame)
    # NOT: Qt'nin ::groove:hover durumu yalnızca 3 px'lik çizgide tetikleniyor;
    # geniş hit alanının tamamı için dinamik property kullanılır.
    assert 'qslider#overlaytimeline[timelinehover="true"]::groove:horizontal'         in style
    assert 'qslider#overlaytimeline[timelinehover="true"]::handle:horizontal'         in style


def test_hover_style_grows_groove_and_handle(product_window):
    app, window, frame = product_window()
    style = overlay_style(frame)
    hover_groove = style.split(
        'qslider#overlaytimeline[timelinehover="true"]::groove:horizontal'
    )[1].split("}")[0]
    hover_handle = style.split(
        'qslider#overlaytimeline[timelinehover="true"]::handle:horizontal'
    )[1].split("}")[0]
    assert "height:5px" in hover_groove
    assert "width:15px" in hover_handle
    assert "height:15px" in hover_handle


def test_normal_style_keeps_thin_groove_and_small_handle(product_window):
    app, window, frame = product_window()
    style = overlay_style(frame)
    base_groove = style.split("qslider::groove:horizontal")[1].split("}")[0]
    base_handle = style.split("qslider::handle:horizontal")[1].split("}")[0]
    assert "height:3px" in base_groove
    assert "width:11px" in base_handle
    assert "height:11px" in base_handle


def test_hover_style_does_not_touch_the_volume_slider(product_window):
    app, window, frame = product_window()
    style = overlay_style(frame)
    assert "qslider#overlayvolumeslider" not in style
    # Ses slider'ı ölçüleri değişmemeli
    assert frame.overlay_volume_slider.height() == 14


def test_timeline_uses_pointing_hand_cursor(product_window):
    app, window, frame = product_window()
    assert frame.overlay_timeline.cursor().shape() ==         Qt.CursorShape.PointingHandCursor


def test_hover_does_not_change_widget_geometry(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    overlay = frame.control_overlay
    play = next(w for w in overlay.findChildren(QWidget)
                if w.objectName() == "overlayPlayPause")
    before_timeline = timeline.geometry()
    before_play = play.geometry()

    send_enter(timeline, app)

    assert timeline.geometry() == before_timeline
    assert play.geometry() == before_play
    assert frame.control_overlay.height() == 110


def test_hover_does_not_seek(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    timeline.setValue(400)
    window.mpv_player.time_pos = 240.0

    send_enter(timeline, app)

    assert timeline.value() == 400
    assert window.mpv_player.time_pos == 240.0


def test_leaving_the_timeline_restores_normal_geometry(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    before = timeline.geometry()

    send_enter(timeline, app)
    app.sendEvent(timeline, QEvent(QEvent.Type.Leave))
    app.processEvents()

    assert timeline.geometry() == before
    assert timeline.height() == TARGET_HIT_HEIGHT


def test_hover_on_timeline_keeps_overlay_visible_and_defers_auto_hide(
        product_window):
    app, window, frame = product_window()
    send_enter(frame.overlay_timeline, app)

    frame.hide_overlay_for_inactivity()
    app.processEvents()

    assert frame.control_overlay.isVisible()


def test_timeline_enables_hover_attribute(product_window):
    """QSS :hover için WA_Hover şart; olmadan hover görünümü hiç çizilmez."""
    app, window, frame = product_window()
    assert frame.overlay_timeline.testAttribute(Qt.WidgetAttribute.WA_Hover)


def test_volume_slider_appearance_is_unaffected_by_the_hover_work(product_window):
    """Hover yalnızca timeline'a özgüdür; ses çubuğu ölçüleri değişmez."""
    app, window, frame = product_window()
    slider = frame.overlay_volume_slider
    assert slider.height() == 14
    assert 80 <= slider.width() <= 110
    assert slider.property("timelineHover") is None


def test_hover_property_covers_the_whole_hit_area(product_window):
    """Çizginin 20 px üstü/altı da hover görünümünü tetiklemeli."""
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    assert timeline.property("timelineHover") == "false"

    frame.set_timeline_hover(True)
    assert timeline.property("timelineHover") == "true"

    frame.set_timeline_hover(False)
    assert timeline.property("timelineHover") == "false"


def test_hover_property_does_not_change_geometry(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    before = timeline.geometry()
    overlay_height = frame.control_overlay.height()

    frame.set_timeline_hover(True)
    app.processEvents()

    assert timeline.geometry() == before
    assert timeline.height() == TARGET_HIT_HEIGHT
    assert frame.control_overlay.height() == overlay_height


def test_hover_property_does_not_seek(product_window):
    app, window, frame = product_window()
    frame.overlay_timeline.setValue(300)
    window.mpv_player.time_pos = 180.0

    frame.set_timeline_hover(True)
    frame.set_timeline_hover(False)
    app.processEvents()

    assert frame.overlay_timeline.value() == 300
    assert window.mpv_player.time_pos == 180.0


def test_volume_slider_has_no_hover_property(product_window):
    app, window, frame = product_window()
    assert frame.overlay_volume_slider.property("timelineHover") is None


# --- Deterministik görsel render (video gürültüsü yok) ---

RENDER_BG = "#101418"


def render_timeline(frame):
    """Timeline'ı sabit koyu zemine çizip QImage döndürür."""
    timeline = frame.overlay_timeline
    pixmap = QPixmap(timeline.width(), timeline.height())
    pixmap.fill(QColor(RENDER_BG))
    painter = QPainter(pixmap)
    try:
        timeline.render(painter, QPoint(), QRegion(timeline.rect()))
    finally:
        painter.end()
    return pixmap.toImage()


def column_rows_differing_from_background(image, x, tolerance=10):
    base = QColor(RENDER_BG)
    rows = []
    for y in range(image.height()):
        colour = image.pixelColor(x, y)
        delta = (abs(colour.red() - base.red())
                 + abs(colour.green() - base.green())
                 + abs(colour.blue() - base.blue()))
        if delta > tolerance:
            rows.append(y)
    return rows


# Zemin #101418 üzerinde beklenen delta'lar:
#   glow en yoğun nokta  ~70   (rgba(255,160,120,38))
#   groove (add-page)    ~195  (rgba(255,255,255,70))
#   handle / sub-page    ~350+ (dolgun turuncu)
GROOVE_TOLERANCE = 130
HANDLE_TOLERANCE = 250
EDGE_TOLERANCE = 12


def groove_rows(frame, image):
    """Boş (add-page) bölgede çizginin kapladığı satırlar (glow hariç)."""
    timeline = frame.overlay_timeline
    x = int(timeline.width() * 0.92)
    return column_rows_differing_from_background(
        image, x, tolerance=GROOVE_TOLERANCE)


def handle_rows(frame, image):
    timeline = frame.overlay_timeline
    ratio = timeline.value() / max(1, timeline.maximum())
    best = []
    for dx in range(-12, 13):
        x = max(0, min(timeline.width() - 1,
                       int((timeline.width() - 18) * ratio) + 9 + dx))
        rows = column_rows_differing_from_background(
            image, x, tolerance=HANDLE_TOLERANCE)
        if len(rows) > len(best):
            best = rows
    return best


@pytest.fixture
def render_pair(product_window):
    app, window, frame = product_window()
    frame.overlay_timeline.setValue(500)
    app.processEvents()

    frame.set_timeline_hover(False)
    app.processEvents()
    normal = render_timeline(frame)

    frame.set_timeline_hover(True)
    app.processEvents()
    hover = render_timeline(frame)

    frame.set_timeline_hover(False)
    app.processEvents()
    restored = render_timeline(frame)
    return app, window, frame, normal, hover, restored


def test_hover_widget_selector_has_a_translucent_gradient(product_window):
    app, window, frame = product_window()
    style = overlay_style(frame)
    marker = 'qslider#overlaytimeline[timelinehover="true"]{'
    assert marker in style, "ana widget selector'ında hover kuralı yok"
    block = style.split(marker)[1].split("}")[0]
    assert "qlineargradient" in block
    assert "rgba(" in block
    # Tam opak renk olmamalı
    assert "stop:0rgba" in block or "stop:0 rgba" in style


def test_hover_halo_uses_only_neutral_low_alpha_colours(product_window):
    """Turuncu yalnızca groove/handle'da kalmalı; çevre halesi nötrdür."""
    app, window, frame = product_window()
    style = overlay_style(frame)
    marker = 'qslider#overlaytimeline[timelinehover="true"]{'
    block = style.split(marker)[1].split("}")[0]
    compact = block.replace(" ", "")

    assert "rgba(255,255,255," in compact
    assert "rgba(242,106,61," not in compact
    assert "rgba(255,160,120," not in compact


def test_hover_halo_render_is_neutral_and_subtle(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    timeline = frame.overlay_timeline
    x = int(timeline.width() * 0.70)
    y = timeline.height() // 2 - 10
    before = normal.pixelColor(x, y)
    after = hover.pixelColor(x, y)
    changes = (
        after.red() - before.red(),
        after.green() - before.green(),
        after.blue() - before.blue(),
    )

    assert min(changes) > 0
    assert max(changes) - min(changes) <= 4
    assert sum(changes) <= 75


def test_normal_timeline_background_is_invisible(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    timeline = frame.overlay_timeline
    # Çizgiden uzak satırlar zemin rengiyle aynı kalmalı
    x = int(timeline.width() * 0.92)
    base = QColor(RENDER_BG)
    for y in (1, 6, timeline.height() - 7, timeline.height() - 2):
        colour = normal.pixelColor(x, y)
        delta = (abs(colour.red() - base.red())
                 + abs(colour.green() - base.green())
                 + abs(colour.blue() - base.blue()))
        assert delta <= EDGE_TOLERANCE,             f"y={y} normalde arka plan görünür (delta={delta})"


def test_groove_is_three_px_normally_and_five_px_on_hover(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    assert len(groove_rows(frame, normal)) == 3
    # Hover groove 5 px; border-radius nedeniyle bir kenar satırı
    # anti-aliasing ile eşiği geçebiliyor.
    assert len(groove_rows(frame, hover)) in (5, 6)


def test_handle_is_eleven_px_normally_and_fifteen_px_on_hover(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    assert 10 <= len(handle_rows(frame, normal)) <= 12
    assert 14 <= len(handle_rows(frame, hover)) <= 16


def test_hover_changes_pixels_well_above_and_below_the_groove(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    timeline = frame.overlay_timeline
    centre = timeline.height() // 2
    x = int(timeline.width() * 0.70)

    for offset in (-12, -10, -8, 8, 10, 12):
        y = centre + offset
        before = normal.pixelColor(x, y)
        after = hover.pixelColor(x, y)
        assert before != after, f"y={y} (merkeze {offset}) hover'da değişmedi"


def test_hover_edges_are_fully_transparent(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    timeline = frame.overlay_timeline
    x = int(timeline.width() * 0.70)
    base = QColor(RENDER_BG)
    for y in (0, timeline.height() - 1):
        colour = hover.pixelColor(x, y)
        delta = (abs(colour.red() - base.red())
                 + abs(colour.green() - base.green())
                 + abs(colour.blue() - base.blue()))
        assert delta <= EDGE_TOLERANCE,             f"y={y} kenarı şeffaf değil (delta={delta})"


def test_hover_is_not_a_solid_block(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    timeline = frame.overlay_timeline
    x = int(timeline.width() * 0.70)
    colours = {hover.pixelColor(x, y).rgb() for y in range(timeline.height())}
    assert len(colours) >= 6, f"tek renk blok gibi görünüyor: {len(colours)} ton"

    # Hiçbir satır tam/dolgun turuncu olmamalı (glow yarı saydam)
    for y in range(timeline.height()):
        colour = hover.pixelColor(x, y)
        assert not (colour.red() > 200 and colour.green() < 150
                    and colour.blue() < 120), f"y={y} dolgun turuncu"


def test_leaving_restores_the_normal_render(render_pair):
    app, window, frame, normal, hover, restored = render_pair
    timeline = frame.overlay_timeline
    x = int(timeline.width() * 0.70)
    for y in range(timeline.height()):
        assert normal.pixelColor(x, y) == restored.pixelColor(x, y),             f"y={y} leave sonrası normale dönmedi"


# --- Enter/Leave anlık tepki ---

def test_enter_event_sets_hover_without_waiting_for_the_poll(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    assert timeline.property("timelineHover") == "false"

    send_enter(timeline, app)

    assert timeline.property("timelineHover") == "true"


def test_leave_event_clears_hover_immediately(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    send_enter(timeline, app)
    assert timeline.property("timelineHover") == "true"

    app.sendEvent(timeline, QEvent(QEvent.Type.Leave))
    app.processEvents()

    assert timeline.property("timelineHover") == "false"


def test_enter_and_leave_do_not_seek(product_window):
    app, window, frame = product_window()
    timeline = frame.overlay_timeline
    timeline.setValue(250)
    window.mpv_player.time_pos = 150.0

    send_enter(timeline, app)
    app.sendEvent(timeline, QEvent(QEvent.Type.Leave))
    app.processEvents()

    assert timeline.value() == 250
    assert window.mpv_player.time_pos == 150.0


def test_volume_slider_has_no_gradient_or_growth(product_window):
    app, window, frame = product_window()
    style = overlay_style(frame)
    assert "overlayvolumeslider" not in style
    assert frame.overlay_volume_slider.property("timelineHover") is None
    assert frame.overlay_volume_slider.height() == 14
