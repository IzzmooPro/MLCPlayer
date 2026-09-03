# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QMimeData, QPoint, QRect, Qt, QUrl
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import pytest

from app.media_controls import append_media_paths, open_path, show_playlist
from app.player import MPVPlayer
from app.playlist_panel import PANEL_MAX_WIDTH
from app.video_frame import VideoFrame


@pytest.fixture
def playlist_window(monkeypatch):
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    # Ürün değişikliği öncesindeki modal QDialog test sürecini bloklamasın.
    # Yeni sinematik yol QDialog.exec() çağırmadığı için bu yama son davranışı
    # sahtelemez; yalnızca ilk başarısızlığın okunabilir olmasını sağlar.
    monkeypatch.setattr("app.media_controls.QDialog.exec", lambda self: 0)
    monkeypatch.setattr(
        "app.media_controls.QMessageBox.information", lambda *args: 0)
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.cinematic_ui_enabled = True
    window.playlist = [
        r"C:\media\first.mkv",
        r"C:\media\same.mkv",
        r"C:\media\same.mkv",
        r"C:\media\last.mp4",
    ]
    window.current_playlist_index = 2
    window.current_file = window.playlist[2]
    window.is_paused = True
    window.played = []
    window.removed_batches = []
    window.play_from_playlist = lambda index: window.played.append(index)
    window.add_to_playlist = lambda: None
    window.remove_from_playlist = lambda index: None
    def remove_many(indices):
        ordered = sorted(set(indices), reverse=True)
        window.removed_batches.append(sorted(ordered))
        for index in ordered:
            window.playlist.pop(index)
        return True
    window.remove_many_from_playlist = remove_many
    window.clear_playlist = lambda: None

    central = QWidget(window)
    window.setCentralWidget(central)
    layout = QVBoxLayout(central)
    window.media_container = QWidget(central)
    media_layout = QHBoxLayout(window.media_container)
    media_layout.setContentsMargins(0, 0, 0, 0)
    media_layout.setSpacing(0)
    window.playlist_dock_host = QWidget(window.media_container)
    window.playlist_dock_host.setFixedWidth(0)
    frame = VideoFrame(window)
    window.video_frame = frame
    media_layout.addWidget(frame, 1)
    media_layout.addWidget(window.playlist_dock_host, 0)
    layout.addWidget(window.media_container)
    window.resize(1000, 700)
    window.show()
    app.processEvents()

    yield app, window, frame

    window.close()
    app.processEvents()


def _open(app, window, frame):
    show_playlist(window)
    app.processEvents()
    panel = frame.playlist_panel
    panel.finish_animation()
    app.processEvents()
    return panel


def test_cinematic_playlist_uses_integrated_panel_not_modal_dialog(
        playlist_window, monkeypatch):
    app, window, frame = playlist_window
    monkeypatch.setattr(
        "app.media_controls.QMessageBox.information",
        lambda *args: pytest.fail("Sinematik playlist QMessageBox kullanmamalı"),
    )

    panel = _open(app, window, frame)

    assert panel.isVisible()
    # Panel artık ana pencerenin SAHİPLİ top-level penceresidir; modal
    # dialog da, `Tool` da değildir (bkz.
    # tests/test_playlist_window_regressions.py).
    assert panel.parent() is window
    assert panel.isWindow()
    # `Tool` bileşik bir bayraktır; maskesiz `&` sıradan `Window` için de
    # doğru çıkar. Tür karşılaştırması maskeyle yapılır.
    assert (panel.windowFlags() & Qt.WindowType.WindowType_Mask) \
        != Qt.WindowType.Tool


def test_empty_playlist_still_opens_drop_ready_panel(playlist_window):
    app, window, frame = playlist_window
    window.playlist = []
    window.current_playlist_index = -1

    panel = _open(app, window, frame)

    assert panel.isVisible()
    assert panel.empty_label.isVisible()
    assert "sürükley" in panel.empty_label.text().lower()
    assert panel.playlist_view.count() == 0


def test_panel_matches_second_concept_structure(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    assert panel.findChild(QLabel, "playlistHeading").text() == "Oynatma Listesi"
    assert panel.findChild(QLabel, "playlistCount").text() == "4 öğe"
    assert panel.findChild(QLineEdit, "playlistSearch").placeholderText() == "Listede ara"
    assert panel.findChild(QListWidget, "playlistView") is panel.playlist_view
    assert panel.findChild(QPushButton, "playlistAdd").text() == "Dosya Ekle"
    assert panel.findChild(QPushButton, "playlistRemove").text() == "Kaldır"
    assert panel.findChild(QPushButton, "playlistClear").text() == "Listeyi Temizle"


def test_panel_sits_beside_the_window_without_covering_video_surface(
        playlist_window):
    """Panel ana pencerenin SAĞINDA durur; videoyu örtmez.

    Eski sürüm panelin `media_container`ın sağ kenarına OTURDUĞUNU ölçüyordu
    (`panel_rect.right() + 1 == container_right`). Panel artık pencerenin
    İÇİNDE değil YANINDA olduğu için o eşitliğin karşılığı yoktur; kesişmeme
    ve sağda durma sözleşmesi KORUNDU.
    """
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    video_rect = QRect(frame.mapToGlobal(QPoint(0, 0)), frame.size())
    panel_rect = QRect(panel.mapToGlobal(QPoint(0, 0)), panel.size())
    owner_rect = window.frameGeometry()

    assert not panel_rect.intersects(video_rect)
    assert panel_rect.left() >= owner_rect.left() + owner_rect.width() - 2, (
        "panel ana pencerenin saginda degil")
    assert abs(panel_rect.top() - owner_rect.top()) <= 2
    assert abs(panel.height() - owner_rect.height()) <= 2
    assert 360 <= panel.width() <= 600


def test_panel_exposes_horizontal_split_handle_and_resizes_only_itself(
        playlist_window):
    """Genişletme artık videodan yer ÇALMAZ — sözleşme güçlendi.

    Eski adı `..._resizes_both_surfaces`tı ve `frame.width()`in tam olarak
    aynı kadar DARALMASINI şart koşuyordu. Bağımsız pencerede video alanı
    hiç değişmez; beklenti gevşetilmedi, tersine çevrildi.
    """
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    handle = panel.resize_handle
    initial_panel = panel.width()
    initial_video = frame.width()

    assert handle.cursor().shape() == Qt.CursorShape.SizeHorCursor
    assert handle.width() >= 8
    panel.set_panel_width(initial_panel + 90)
    app.processEvents()
    panel.finish_animation()

    assert panel.width() == initial_panel + 90
    assert frame.width() == initial_video, "playlist videodan yer caldi"


def test_real_mouse_drag_on_split_handle_changes_panel_width(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    initial = panel.width()
    start = QPoint(7, panel.height() // 2)

    # Gerçek Windows layered/tool penceresinde native hit-test child handle
    # yerine top-level paneli hedefler; ürün bu gerçek yolu da işlemelidir.
    QTest.mousePress(panel, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(panel, QPoint(start.x() - 70, start.y()), delay=120)
    QTest.mouseRelease(panel, Qt.MouseButton.LeftButton,
                       pos=QPoint(start.x() - 70, start.y()))
    app.processEvents()
    panel.finish_animation()

    assert panel.width() >= initial + 60


def test_split_handle_child_receives_synthetic_qt_drag(playlist_window):
    """SENTETİK (QTest) sürükleme: ayraç artık gerçek child olduğu için
    olaylar doğrudan ona teslim edilir.

    NOT: Bu bir Qt sentetik jestidir, fiziksel Windows fare yolu DEĞİLDİR.
    Gerçek Win32 imleç + sol tuş sürüklemesi
    `tests/native_composition_smoke_child.py::separator_drag` içindedir.

    Eskiden panel top-level Tool penceresi olduğu için native hit-test olayı
    `playlist_dock_host`'a teslim ediyordu ve ürün geçici bir ikinci fare
    yönlendirmesi taşıyordu. Embedding sonrası o yol gereksizdir; bu test
    gerçek handle yolunun iki yöne de çalıştığını ölçer.
    """
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    handle = panel.resize_handle
    initial = panel.width()
    start = QPoint(handle.width() // 2, handle.height() // 2)

    # Sola sürükleme paneli genişletir.
    QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(handle, QPoint(start.x() - 80, start.y()), delay=60)
    QTest.mouseRelease(handle, Qt.MouseButton.LeftButton,
                       pos=QPoint(start.x() - 80, start.y()))
    app.processEvents()
    panel.finish_animation()
    widened = panel.width()
    assert widened >= initial + 70

    # Sağa sürükleme paneli daraltır.
    QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(handle, QPoint(start.x() + 60, start.y()), delay=60)
    QTest.mouseRelease(handle, Qt.MouseButton.LeftButton,
                       pos=QPoint(start.x() + 60, start.y()))
    app.processEvents()
    panel.finish_animation()

    assert panel.width() < widened
    assert panel.width() >= 320


def test_split_handle_stays_visible_and_hit_testable_after_owner_restore(
        playlist_window):
    """Gerçek owner yaşam döngüsü: pencere gizlenip geri gösterilir.

    Eski `hide_for_owner`/`restore_for_owner` makyajı embedding sonrası
    kaldırıldı; görünürlük artık ana pencereyle birlikte Qt tarafından
    yönetilir.
    """
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    handle = panel.resize_handle
    assert handle.isVisible()
    assert handle.width() >= 12
    assert panel.childAt(handle.geometry().center()) is handle

    window.hide()
    app.processEvents()
    window.show()
    app.processEvents()

    assert panel.is_open
    assert handle.isVisible()
    assert panel.childAt(handle.geometry().center()) is handle


def test_playlist_close_button_is_keyboard_reachable(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    assert panel.close_button.focusPolicy() == Qt.FocusPolicy.TabFocus


def test_transient_owner_deactivate_does_not_hide_panel_before_it_activates(
        playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    QApplication.setActiveWindow(None)
    frame.eventFilter(window, QEvent(QEvent.Type.WindowDeactivate))
    QApplication.setActiveWindow(panel)
    app.processEvents()

    assert panel.isVisible()
    assert panel.resize_handle.isVisible()

def test_panel_split_width_is_clamped_to_keep_video_and_playlist_usable(
        playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    # ÜRÜNÜN GERÇEK yolu kullanılır. Eskiden burada
    # `frame.set_playlist_panel_width()` çağrılıyordu; o dock yoludur ve
    # pencere modelinde etkisizdir, yani test BOŞUNA geçerdi.
    panel.set_panel_width(10_000)
    app.processEvents()
    panel.finish_animation()
    assert panel.width() <= PANEL_MAX_WIDTH

    panel.set_panel_width(1)
    app.processEvents()
    panel.finish_animation()
    assert panel.width() >= 320


def test_owned_overlay_windows_are_not_global_always_on_top(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    assert not (panel.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    assert not (frame.control_overlay.windowFlags()
                & Qt.WindowType.WindowStaysOnTopHint)
    assert not (frame.osd_label.windowFlags()
                & Qt.WindowType.WindowStaysOnTopHint)


def test_panel_follows_resize_and_never_leaves_small_video(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    window.resize(400, 300)
    app.processEvents()
    frame.update_playlist_panel_geometry()
    panel.finish_animation()

    container = window.media_container
    origin = container.mapToGlobal(QPoint(0, 0))
    container_rect = QRect(origin, container.size())
    video_rect = QRect(frame.mapToGlobal(QPoint(0, 0)), frame.size())
    panel_rect = QRect(panel.mapToGlobal(QPoint(0, 0)), panel.size())
    assert not container_rect.intersects(panel_rect), (
        "panel artik pencerenin YANINDA; icine girmemeli")
    assert not panel_rect.intersects(video_rect)
    # ESKI BEKLENTI: dar pencerede playlist icerik alanini DEVRALIR ve
    # video genisligi 0'a duserdi (`frame.width() == 0`). Bagimsiz
    # pencerede playlist videodan yer ALMADIGI icin video kucuk pencerede
    # de tam genisligini korur. Beklenti gevsetilmedi, tersine cevrildi.
    assert frame.width() > 0, "kucuk pencerede video yok oldu"


def test_rows_show_filename_and_unique_current_marker(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    assert panel.playlist_view.count() == 4
    row_names = [panel.row_widget(i).filename_label.text() for i in range(4)]
    assert row_names == ["first.mkv", "same.mkv", "same.mkv", "last.mp4"]
    active_rows = [
        i for i in range(4)
        if panel.row_widget(i).property("playing") is True
    ]
    assert active_rows == [2]
    assert all(panel.row_widget(i).findChild(
        QLabel, "playlistPlayingIndicator") is None for i in range(4))


def test_row_children_do_not_block_real_list_mouse_gestures(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    row = panel.row_widget(0)

    assert row.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert row.drag_handle.text() == "⠿"
    assert "sırala" in panel.playlist_view.item(0).toolTip().lower()

    hit = panel.playlist_view.viewport().childAt(
        panel.playlist_view.viewport().rect().center())
    assert hit is None, "satir cocuklari listenin faresini engelliyor"


def test_thumbnail_is_not_a_second_fake_play_button(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    row = panel.row_widget(window.current_playlist_index)

    assert row.findChild(QLabel, "playlistPlayingIndicator") is None
    assert row.thumbnail_label.property("thumbnailState") in {"empty", "loading"}
    assert row.thumbnail_label.accessibleName() == "Video küçük resmi"


def test_reorder_preserves_duplicates_and_moves_current_index(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    panel.move_playlist_item(2, 0)

    assert window.playlist == [
        r"C:\media\same.mkv",
        r"C:\media\first.mkv",
        r"C:\media\same.mkv",
        r"C:\media\last.mp4",
    ]
    assert window.current_playlist_index == 0
    assert panel.row_widget(0).property("playing") is True


def test_list_exposes_real_drag_drop_reordering_surface(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view

    assert view.dragEnabled()
    assert view.acceptDrops()
    assert view.showDropIndicator()
    assert view.defaultDropAction() == Qt.DropAction.MoveAction
    assert (view.selectionMode()
            == QAbstractItemView.SelectionMode.ExtendedSelection)


def test_playlist_rows_do_not_inherit_a_stale_horizontal_resize_cursor(
        playlist_window):
    """Leaving the 14 px resize band must not paint its cursor over rows."""
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view

    # Windows can deliver the edge event to the frameless top-level panel.
    # Reproduce the resulting parent cursor before entering the row viewport.
    panel.setCursor(Qt.CursorShape.SizeHorCursor)

    assert view.viewport().cursor().shape() == Qt.CursorShape.ArrowCursor


def test_top_level_playlist_never_owns_the_horizontal_resize_cursor(
        playlist_window):
    """Only the dedicated 14 px handle may own SizeHorCursor."""
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    panel.unsetCursor()

    QTest.mouseMove(panel, QPoint(7, panel.height() // 2))
    app.processEvents()

    assert not panel.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
    assert panel.resize_handle.cursor().shape() == Qt.CursorShape.SizeHorCursor


def test_real_mouse_drag_reorders_without_starting_playback(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view
    original = list(window.playlist)
    start = view.visualItemRect(view.item(0)).center()
    end = view.visualItemRect(view.item(2)).center()

    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end, delay=180)
    app.processEvents()
    assert panel.row_widget(2).property("dragTarget") is True
    assert view._drag_preview_pixmap is not None
    assert view._drag_preview_pixmap.isNull() is False
    assert view.cursor().shape() != Qt.CursorShape.SizeHorCursor
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()

    assert window.playlist != original
    assert sorted(window.playlist) == sorted(original)
    assert window.played == []
    assert view._drag_preview_pixmap is None
    assert all(panel.row_widget(row).property("dragTarget") is False
               for row in range(panel.playlist_view.count()))


def test_last_row_has_a_real_after_drop_zone(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view
    original = list(window.playlist)
    start = view.visualItemRect(view.item(0)).center()
    last_row = view.count() - 1
    last_rect = view.visualItemRect(view.item(last_row))
    end = QPoint(last_rect.center().x(), last_rect.bottom() + 12)
    assert end.y() < view.viewport().height(), "son satır altında test alanı yok"

    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end, delay=180)
    app.processEvents()

    last_widget = panel.row_widget(last_row)
    assert last_widget.property("dragTarget") is True
    assert last_widget.property("dragAfter") is True

    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()

    assert window.playlist == original[1:] + original[:1]
    assert window.played == []


def test_reorder_around_current_item_updates_index_without_playing(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    panel.move_playlist_item(0, 3)

    assert window.playlist == [
        r"C:\media\same.mkv",
        r"C:\media\same.mkv",
        r"C:\media\last.mp4",
        r"C:\media\first.mkv",
    ]
    assert window.current_playlist_index == 1
    assert window.played == []


def test_single_click_selects_item_without_playing_it(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view
    point = view.visualItemRect(view.item(1)).center()

    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)

    assert view.currentRow() == 1
    assert window.played == []
    assert panel.row_widget(1).property("selected") is True
    assert panel.row_widget(1).property("playing") is False
    assert panel.row_widget(2).property("playing") is True
    assert all(panel.row_widget(row).property("selected") is False
               for row in (0, 2, 3))


def test_double_click_plays_selected_item(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view
    point = view.visualItemRect(view.item(1)).center()

    # QtTest's mouseDClick emits the double-click event itself; establish the
    # preceding first click that a real desktop double-click sequence has.
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)

    assert window.played == [1]


def test_ctrl_click_selects_multiple_rows_and_remove_deletes_one_batch(
        playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view
    first = view.visualItemRect(view.item(0)).center()
    third = view.visualItemRect(view.item(2)).center()

    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.ControlModifier, pos=third)
    app.processEvents()

    assert sorted(view.row(item) for item in view.selectedItems()) == [0, 2]
    assert panel.row_widget(0).property("selected") is True
    assert panel.row_widget(2).property("selected") is True
    assert window.played == []

    panel.remove_button.click()

    assert window.removed_batches == [[0, 2]]
    assert window.playlist == [r"C:\media\same.mkv", r"C:\media\last.mp4"]


def test_drag_reorder_does_not_play_selected_item(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    view = panel.playlist_view
    source = view.visualItemRect(view.item(0)).center()
    target = view.visualItemRect(view.item(2)).center()

    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=source)
    QTest.mouseMove(view.viewport(), target, delay=20)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=target)

    assert window.played == []


def test_search_filters_without_mutating_playlist(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    original = list(window.playlist)

    panel.search_field.setText("last")
    app.processEvents()

    visible = [
        panel.row_widget(i).filename_label.text()
        for i in range(panel.playlist_view.count())
        if not panel.playlist_view.item(i).isHidden()
    ]
    assert visible == ["last.mp4"]
    assert window.playlist == original


def test_footer_actions_use_existing_player_flows(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    calls = []
    window.add_to_playlist = lambda: calls.append(("add", None))
    window.remove_many_from_playlist = (
        lambda indexes: calls.append(("remove_many", list(indexes))) or True)
    window.clear_playlist = lambda: calls.append(("clear", None))
    panel.playlist_view.setCurrentRow(1)

    panel.add_button.click()
    panel.remove_button.click()
    panel.clear_button.click()

    assert calls == [
        ("add", None), ("remove_many", [1]), ("clear", None)]


def test_playlist_toggle_and_escape_close_the_panel(playlist_window):
    app, window, frame = playlist_window
    video_width_before = frame.width()
    panel = _open(app, window, frame)

    show_playlist(window)
    panel.finish_animation()
    app.processEvents()
    assert not panel.isVisible()
    # Eskiden `playlist_dock_host.width() == 0` olcuurdu; host yok. Kapanisin
    # gorunur sonucu: video alani hic degismemis olmali.
    assert frame.width() == video_width_before
    assert frame.isVisible()


def test_repeated_panel_toggle_survives_owner_resize_cycles(playlist_window):
    app, window, frame = playlist_window
    sizes = ((400, 300), (760, 480), (1200, 800), (520, 340),
             (1000, 700), (400, 300), (1000, 700))

    for width, height in sizes:
        window.resize(width, height)
        app.processEvents()

        panel = _open(app, window, frame)
        frame.update_playlist_panel_geometry()
        panel.finish_animation()
        app.processEvents()
        assert panel.is_open
        assert panel.isVisible()
        assert panel.resize_handle.isVisible()
        assert frame.isVisible()

        show_playlist(window)
        panel.finish_animation()
        app.processEvents()
        assert not panel.is_open
        assert not panel.isVisible()
        assert frame.isVisible()


def test_closing_panel_resumes_overlay_autohide(playlist_window):
    app, window, frame = playlist_window
    window.current_file = r"C:\media\same.mkv"
    window.is_paused = False
    panel = _open(app, window, frame)
    assert not frame.overlay_hide_timer.isActive()

    panel.close_animated()
    panel.finish_animation()

    assert frame.overlay_hide_timer.isActive()


def test_external_media_drop_appends_and_starts_empty_playlist(
        playlist_window, tmp_path, monkeypatch):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    video = tmp_path / "dropped.mkv"
    video.write_bytes(b"test")
    ignored = tmp_path / "note.txt"
    ignored.write_text("test", encoding="utf-8")
    window.playlist = []
    window.current_playlist_index = -1
    window.current_file = ""
    window.played.clear()
    def successful_play(owner, index):
        owner.play_from_playlist(index)
        owner.video_frame.refresh_playlist_panel()
        return True

    monkeypatch.setattr("app.media_controls.play_from_playlist",
                        successful_play)

    panel.add_external_files([str(video), str(ignored)])

    assert window.playlist == [os.path.normpath(str(video))]
    assert window.played == [0]
    assert panel.playlist_view.count() == 1

    panel = _open(app, window, frame)
    QTest.keyClick(panel, Qt.Key.Key_Escape)
    panel.finish_animation()
    app.processEvents()
    assert not panel.isVisible()


def test_external_multi_drop_appends_without_resetting_existing_playlist(
        playlist_window, tmp_path):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    first = tmp_path / "one.mkv"
    second = tmp_path / "two.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    original = list(window.playlist)

    panel.add_external_files([str(first), str(second)])

    assert window.playlist == original + [os.path.normpath(str(first)),
                                          os.path.normpath(str(second))]
    assert window.current_playlist_index == 2
    assert panel.playlist_view.count() == len(original) + 2


def test_player_surface_multi_drop_appends_without_replacing_current_playlist(
        monkeypatch):
    played = []
    refreshed = []
    player = SimpleNamespace(
        playlist=["current.mkv"], current_file="current.mkv",
        current_playlist_index=0,
        video_frame=SimpleNamespace(
            refresh_playlist_panel=lambda: refreshed.append(True)),
    )
    monkeypatch.setattr("app.media_controls.play_from_playlist",
                        lambda owner, index: played.append(index))

    append_media_paths(player, ["second.mkv", "third.mkv"])

    assert player.playlist == ["current.mkv", "second.mkv", "third.mkv"]
    assert player.current_playlist_index == 0
    assert played == []
    assert refreshed == [True]


def test_real_player_drop_event_keeps_all_selected_files(
        playlist_window, tmp_path):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    panel.thumbnail_service.request = lambda path: None
    first = tmp_path / "selected-one.mkv"
    second = tmp_path / "selected-two.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    original = list(window.playlist)
    mime = QMimeData()
    dropped_urls = [QUrl.fromLocalFile(str(first)), QUrl.fromLocalFile(str(second))]
    mime.setUrls(dropped_urls)

    class DropEvent:
        def mimeData(self):
            return mime

        def acceptProposedAction(self):
            self.accepted = True

    event = DropEvent()
    MPVPlayer.dropEvent(window, event)

    assert event.accepted is True
    assert window.playlist == original + [url.toLocalFile() for url in dropped_urls]
    assert window.current_playlist_index == 2


def test_real_player_drop_event_uses_the_media_extension_allowlist(
        playlist_window, tmp_path):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    panel.thumbnail_service.request = lambda path: None
    media = tmp_path / "modern.WEBM"
    ignored = tmp_path / "notes.txt"
    media.write_bytes(b"media")
    ignored.write_text("not media", encoding="utf-8")
    original = list(window.playlist)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(media)),
                  QUrl.fromLocalFile(str(ignored))])

    class DropEvent:
        def mimeData(self):
            return mime

        def acceptProposedAction(self):
            self.accepted = True

    event = DropEvent()
    MPVPlayer.dropEvent(window, event)

    assert event.accepted is True
    assert window.playlist == original + [
        QUrl.fromLocalFile(str(media)).toLocalFile()]


def test_open_panel_blocks_control_overlay_autohide(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    assert panel.isVisible()
    assert frame._overlay_interaction_blocked()


def test_main_window_close_closes_playlist_panel(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)

    window.close()
    app.processEvents()

    assert not panel.isVisible()


def test_refresh_keeps_selection_when_model_changes(playlist_window):
    app, window, frame = playlist_window
    panel = _open(app, window, frame)
    panel.playlist_view.setCurrentRow(1)
    window.playlist.append(r"C:\media\new.mp4")

    panel.refresh()

    assert panel.playlist_view.count() == 5
    assert panel.playlist_view.currentRow() == 1
    assert panel.count_label.text() == "5 öğe"


def test_directly_opened_local_video_becomes_the_single_playlist_item():
    played = []
    refreshed = []

    class Settings:
        def contains(self, key):
            return False

        def value(self, key, default=None):
            return default

        def setValue(self, key, value):
            pass

        def remove(self, key):
            pass

    player = SimpleNamespace(
        duration=0, position=0, _core_idle=False, _audio_menu_file="",
        _chapter_menu_file="", _pending_subs=[], playlist=["old.mkv"],
        current_playlist_index=0, current_file="", _load_started_at=0,
        last_dir="", is_paused=True, settings=Settings(),
        mpv_player=SimpleNamespace(play=lambda path: played.append(path),
                                   sub_delay=0.0),
        play_button=SimpleNamespace(setIcon=lambda icon: None),
        pause_icon=object(),
        video_frame=SimpleNamespace(
            control_overlay=None,
            placeholder_label=SimpleNamespace(hide=lambda: None,
                                              show=lambda: None),
            refresh_playlist_panel=lambda: refreshed.append(True),
        ),
        clear_title_bar_raise_pending=lambda: None,
        mark_title_bar_raise_pending=lambda: None,
        set_title=lambda: None,
        add_recent_file=lambda path: None,
    )

    open_path(player, r"C:\media\opened.mkv")

    assert played == [r"C:\media\opened.mkv"]
    assert player.playlist == [r"C:\media\opened.mkv"]
    assert player.current_playlist_index == 0
    assert refreshed == [True]
