"""Sekmeli Medya Bilgisi penceresi (2. uygulama turu).

Dialog YALNIZ hazir `MediaInfoSnapshot` alir ve cizer: player veya mpv
nesnesi okumaz, ham MPV anahtari veya metadata yorumlamaz. Menu, QAction,
singleton sahipligi, `update_ui` ve `closeEvent` bagi bu turda YOKTUR.

Kilitlenen sozlesmeler
----------------------
- Modeless (`exec()` yok). SEKME YOKTUR: tek kaydirilabilir sayfada
  yukaridan asagiya Genel -> Video -> Ses -> Altyazi bolumleri.
- Satirlar snapshot'in hazir `InfoRow.label/value` degerlerinden birebir cizilir.
- Bos bolumde builder'in `empty_message` metni gorunur.
- Her sekme kaydirilabilir; cok sayida track pencereyi buyutmez.
- Snapshot'tan gelen her metin DUZ METINDIR: `<b>`, `<script>` bicimlendirme
  olarak yorumlanmaz ve deger etiketleri link acmaz.
- `copy_value` hicbir QLabel, tooltip, accessibleName, objectName, statusTip
  veya whatsThis metnine yazilmaz; yalniz acik tiklamayla panoya gider.
- `set_snapshot()` ayni pencereyi tamamen yeniler; eski medya metni, eski grup
  ve eski `copy_value` kalmaz.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (QApplication, QLabel, QPushButton, QScrollArea,
                             QTabWidget, QWidget)  # noqa: F401

from app.media_info import build_media_info
from app.media_info_dialog import MediaInfoDialog

SECRET_URL = ("https://user:s3cret@cdn.example.com:8443/videos/bolum-1.mkv"
              "?token=abcdef123456#t=42")
SECTION_TITLES = ["Genel", "Video", "Ses", "Altyazı"]


def tracks(video=1, audio=1, sub=1):
    made = []
    for index in range(video):
        made.append({"id": index + 1, "type": "video", "selected": index == 0,
                     "codec": "h264", "demux-w": 1920, "demux-h": 1080,
                     "demux-fps": 24.0, "demux-bitrate": 8_000_000})
    for index in range(audio):
        made.append({"id": index + 1, "type": "audio", "selected": index == 0,
                     "lang": "tur", "codec": "eac3",
                     "demux-channels": "5.1(side)",
                     "demux-samplerate": 48000, "demux-bitrate": 640000})
    for index in range(sub):
        made.append({"id": index + 1, "type": "sub", "selected": index == 0,
                     "lang": "tur", "codec": "subrip", "external": False})
    return made


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def local_snapshot(tmp_path):
    """GERCEK builder ciktisi; builder davranisi burada YENIDEN test edilmez."""
    folder = tmp_path / "Diziler" / "Seri 2"
    folder.mkdir(parents=True)
    path = folder / "Bolum 1.mkv"
    path.write_bytes(b"0" * 4096)
    snapshot = build_media_info(str(path), duration=3725.0,
                                track_list=tracks())
    return snapshot, str(path)


@pytest.fixture
def make_dialog(qt_app):
    created = []

    def factory(snapshot, **kwargs):
        dialog = MediaInfoDialog(snapshot, **kwargs)
        dialog.show()
        qt_app.processEvents()
        created.append(dialog)
        return dialog

    yield factory

    for dialog in created:
        try:
            dialog.close()
        except RuntimeError:
            pass
    qt_app.processEvents()


# --- olcum yardimcilari: gercek widget agacini gezer ---

def body_of(dialog):
    """Tek kaydırma alanının gövdesi."""
    area = dialog.findChild(QScrollArea)
    assert area is not None, "kaydırma alanı yok"
    return area.widget()


def section_titles(dialog):
    """Sayfadaki bölüm başlıkları, GÖRÜNÜM sırasıyla."""
    return [label.text() for label in labels_in(dialog)
            if label.objectName() == "mediaInfoSectionTitle"]


def labels_in(widget):
    return [label for label in widget.findChildren(QLabel)]


def texts_in(widget):
    return [label.text() for label in labels_in(widget)]


def every_widget_string(dialog):
    """Kullaniciya ULASABILECEK butun metinler (erisilebilirlik dahil)."""
    values = [dialog.windowTitle()]
    for widget in dialog.findChildren(QWidget):
        values.extend([widget.toolTip(), widget.accessibleName(),
                       widget.accessibleDescription(), widget.objectName(),
                       widget.statusTip(), widget.whatsThis()])
        if isinstance(widget, (QLabel, QPushButton)):
            values.append(widget.text())
    return [value for value in values if value]


def button_named(dialog, text):
    for button in dialog.findChildren(QPushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"düğme yok: {text}")


# =====================================================================
# 1. Yapi: modeless + dort sekme
# =====================================================================

def test_the_dialog_is_modeless(local_snapshot, make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert dialog.isModal() is False
    assert dialog.windowModality() == Qt.WindowModality.NonModal


def test_there_are_no_tabs_at_all(local_snapshot, make_dialog):
    """KULLANICI KARARI: sekmeli görünüm kaldırıldı."""
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert dialog.findChild(QTabWidget) is None, "sekme widget'ı hâlâ var"


def test_a_single_scroll_area_holds_the_whole_page(local_snapshot,
                                                   make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert len(dialog.findChildren(QScrollArea)) == 1


def test_the_sections_follow_one_top_to_bottom_order(local_snapshot,
                                                     make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert section_titles(dialog) == SECTION_TITLES


def test_the_window_title_names_the_media(local_snapshot, make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert dialog.windowTitle() == "Medya Bilgisi — Bolum 1.mkv"


def test_the_dialog_can_be_parented_to_the_main_window(qt_app, local_snapshot):
    snapshot, _path = local_snapshot
    parent = QWidget()
    dialog = MediaInfoDialog(snapshot, parent=parent)

    assert dialog.parent() is parent
    dialog.close()
    parent.close()


# =====================================================================
# 2. Satirlar snapshot'tan BIREBIR
# =====================================================================

@pytest.mark.parametrize("key", ("general", "video", "audio", "subtitle"))
def test_every_snapshot_row_is_drawn(local_snapshot, make_dialog, key):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)
    drawn = texts_in(dialog)

    for group in snapshot.section(key).groups:
        for row in group.rows:
            assert row.label in drawn, f"etiket cizilmedi: {row.label}"
            assert row.value in drawn, f"deger cizilmedi: {row.value}"


def test_each_track_becomes_its_own_group(qt_app, tmp_path, make_dialog):
    path = tmp_path / "Cok.mkv"
    path.write_bytes(b"0")
    snapshot = build_media_info(str(path), duration=90.0,
                                track_list=tracks(video=1, audio=3, sub=2))
    dialog = make_dialog(snapshot)
    drawn = texts_in(dialog)

    for group in snapshot.section("audio").groups:
        assert group.title in drawn, f"grup basligi yok: {group.title}"


def test_empty_sections_show_the_builder_message(qt_app, tmp_path,
                                                 make_dialog):
    path = tmp_path / "Bos.mkv"
    path.write_bytes(b"0")
    snapshot = build_media_info(str(path), duration=90.0, track_list=[])
    dialog = make_dialog(snapshot)

    drawn = texts_in(dialog)
    for key in ("video", "audio", "subtitle"):
        assert snapshot.section(key).empty_message in drawn


# =====================================================================
# 3. Kaydirma: cok track pencereyi buyutmez
# =====================================================================

def test_the_page_is_scrollable(local_snapshot, make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert dialog.findChild(QScrollArea) is not None
    assert body_of(dialog) is not None


def test_many_tracks_do_not_grow_the_window(qt_app, tmp_path, make_dialog):
    path = tmp_path / "Cok.mkv"
    path.write_bytes(b"0")
    small = build_media_info(str(path), duration=90.0, track_list=tracks())
    huge = build_media_info(str(path), duration=90.0,
                            track_list=tracks(video=8, audio=20, sub=20))

    modest = make_dialog(small).sizeHint()
    crowded = make_dialog(huge).sizeHint()

    assert crowded.height() <= modest.height() + 40, (
        f"pencere buyudu: {modest.height()} -> {crowded.height()}")
    assert crowded.width() <= modest.width() + 40


def test_the_default_and_minimum_sizes_are_reasonable(local_snapshot,
                                                      make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert 560 <= dialog.width() <= 900
    assert 380 <= dialog.height() <= 700
    assert dialog.minimumWidth() >= 520
    assert dialog.minimumHeight() >= 360


# =====================================================================
# 4. DUZ METIN guvenligi
# =====================================================================

def test_metadata_markup_is_never_interpreted(qt_app, tmp_path, make_dialog):
    path = tmp_path / "Kotu.mkv"
    path.write_bytes(b"0")
    reader = {"file-format": "matroska",
              "metadata": {"title": "<b>Kalin</b> <script>x</script>"}}
    snapshot = build_media_info(str(path), duration=90.0,
                                property_reader=lambda name: reader[name])
    dialog = make_dialog(snapshot)
    drawn = texts_in(dialog)

    assert "<b>Kalin</b> <script>x</script>" in drawn, (
        f"metin degistirildi: {drawn}")


def test_every_snapshot_label_is_plain_text(local_snapshot, make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    for label in labels_in(dialog):
        assert label.textFormat() == Qt.TextFormat.PlainText, (
            f"düz metin degil: {label.text()!r}")
        assert label.openExternalLinks() is False


def test_value_labels_may_be_selected_but_never_open_links(local_snapshot,
                                                           make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)
    links = (Qt.TextInteractionFlag.LinksAccessibleByMouse
             | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)

    for label in labels_in(dialog):
        assert not (label.textInteractionFlags() & links)


# =====================================================================
# 5. Tam yol widget agacina GIRMEZ
# =====================================================================

def test_the_full_local_path_is_absent_from_every_widget_string(
        local_snapshot, make_dialog):
    snapshot, path = local_snapshot
    dialog = make_dialog(snapshot)

    for value in every_widget_string(dialog):
        assert path not in value, f"tam yol sizdi: {value!r}"
        assert os.path.dirname(path) not in value, f"klasor sizdi: {value!r}"


def test_the_url_secrets_are_absent_from_every_widget_string(make_dialog):
    snapshot = build_media_info(SECRET_URL, duration=90.0)
    dialog = make_dialog(snapshot)

    for value in every_widget_string(dialog):
        for secret in ("s3cret", "token", "abcdef123456", "user:", "videos"):
            assert secret not in value, f"sir sizdi: {value!r}"


# =====================================================================
# 6. Kopyalama YALNIZ acik tiklamayla
# =====================================================================

def test_the_copy_callback_is_not_called_while_opening(local_snapshot,
                                                       make_dialog):
    snapshot, _path = local_snapshot
    copied = []
    make_dialog(snapshot, copy_text=copied.append)

    assert copied == [], "acilista pano yazildi"


def test_one_click_copies_the_full_path_exactly_once(local_snapshot,
                                                     make_dialog):
    snapshot, path = local_snapshot
    copied = []
    dialog = make_dialog(snapshot, copy_text=copied.append)

    button = button_named(dialog, "Yolu Kopyala")
    button.click()

    assert copied == [path]


def test_a_url_copies_only_the_sanitized_address(make_dialog):
    snapshot = build_media_info(SECRET_URL, duration=90.0)
    copied = []
    dialog = make_dialog(snapshot, copy_text=copied.append)

    button_named(dialog, "Adresi Kopyala").click()

    assert copied == ["https://cdn.example.com:8443/bolum-1.mkv"]
    assert "token" not in copied[0] and "s3cret" not in copied[0]


def test_a_failing_copy_never_crashes_or_leaks_raw_text(local_snapshot,
                                                        make_dialog):
    snapshot, _path = local_snapshot

    def angry(_value):
        raise RuntimeError("pano kilitli: C:\\gizli\\yol")

    dialog = make_dialog(snapshot, copy_text=angry)
    button_named(dialog, "Yolu Kopyala").click()

    assert dialog.isVisible() is True
    for value in every_widget_string(dialog):
        assert "RuntimeError" not in value
        assert "pano kilitli" not in value
        assert "gizli" not in value


# =====================================================================
# 7. `set_snapshot()` ayni pencereyi yeniler
# =====================================================================

def test_set_snapshot_replaces_every_trace_of_the_old_media(qt_app, tmp_path,
                                                            make_dialog):
    first_dir = tmp_path / "Eski"
    first_dir.mkdir()
    first_path = first_dir / "Eski Film.mkv"
    first_path.write_bytes(b"0")
    first = build_media_info(str(first_path), duration=90.0,
                             track_list=tracks(audio=3))

    second_path = tmp_path / "Yeni Film.mkv"
    second_path.write_bytes(b"0")
    second = build_media_info(str(second_path), duration=120.0,
                              track_list=tracks(audio=1))

    dialog = make_dialog(first)
    area = dialog.findChild(QScrollArea)
    dialog.set_snapshot(second)
    qt_app.processEvents()

    assert dialog.findChild(QScrollArea) is area, "yeni kaydırma alanı üretildi"
    assert dialog.windowTitle() == "Medya Bilgisi — Yeni Film.mkv"
    strings = every_widget_string(dialog)
    for value in strings:
        assert "Eski Film.mkv" not in value
        assert str(first_path) not in value
    assert len(second.section("audio").groups) == 1
    assert sum(1 for text in texts_in(dialog)
               if text.startswith("2. Ses Parçası")) == 0
    assert section_titles(dialog) == SECTION_TITLES


def test_set_snapshot_replaces_the_copy_target(qt_app, tmp_path, make_dialog):
    first_path = tmp_path / "Eski.mkv"
    first_path.write_bytes(b"0")
    first = build_media_info(str(first_path), duration=90.0)
    second = build_media_info(SECRET_URL, duration=90.0)

    copied = []
    dialog = make_dialog(first, copy_text=copied.append)
    dialog.set_snapshot(second)
    qt_app.processEvents()

    button_named(dialog, "Adresi Kopyala").click()
    assert copied == ["https://cdn.example.com:8443/bolum-1.mkv"]
    assert str(first_path) not in copied


def test_set_snapshot_keeps_the_scroll_position_contract(
        qt_app, local_snapshot, make_dialog, tmp_path):
    """Sekme yok; yenileme aynı kaydırma alanını yeniden kullanır."""
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)
    area = dialog.findChild(QScrollArea)
    old_body = body_of(dialog)

    other = tmp_path / "Baska.mkv"
    other.write_bytes(b"0")
    dialog.set_snapshot(build_media_info(str(other), duration=10.0,
                                         track_list=tracks()))
    qt_app.processEvents()

    assert dialog.findChild(QScrollArea) is area
    assert body_of(dialog) is not old_body, "gövde yenilenmedi"


# =====================================================================
# 8. Kapanis
# =====================================================================

def test_the_action_buttons_stay_outside_the_scroll_area(local_snapshot,
                                                         make_dialog):
    """Kopyalama ve Kapat kaydırmayla kaybolmamalı."""
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)
    area = dialog.findChild(QScrollArea)

    for text in (snapshot.copy_label, "Kapat"):
        button = button_named(dialog, text)
        assert button.isVisible() is True
        assert area.isAncestorOf(button) is False, (
            f"{text} kaydırma alanının içinde")


def test_the_dialog_deletes_itself_on_close(local_snapshot, make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)

    assert dialog.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) is True


def test_the_close_button_closes_the_dialog(qt_app, local_snapshot,
                                            make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)
    closed = []
    dialog.finished.connect(lambda code: closed.append(code))

    button_named(dialog, "Kapat").click()
    qt_app.processEvents()

    assert closed, "Kapat düğmesi pencereyi kapatmadı"


def test_escape_closes_the_dialog(qt_app, local_snapshot, make_dialog):
    snapshot, _path = local_snapshot
    dialog = make_dialog(snapshot)
    closed = []
    dialog.finished.connect(lambda code: closed.append(code))

    qt_app.sendEvent(dialog, QKeyEvent(QEvent.Type.KeyPress,
                                       Qt.Key.Key_Escape,
                                       Qt.KeyboardModifier.NoModifier))
    qt_app.processEvents()

    assert closed, "Escape pencereyi kapatmadı"


# =====================================================================
# 9. Yasak altyapi
# =====================================================================

def test_the_dialog_owns_no_timer_thread_network_or_exec():
    import app.media_info_dialog as module

    with open(module.__file__, encoding="utf-8") as handle:
        source = handle.read()

    for forbidden in ("QTimer", "QThread", "threading", "socket", "requests",
                      "urllib.request", "subprocess", ".exec(", "QProcess"):
        assert forbidden not in source, f"yasak altyapi: {forbidden}"


def test_the_dialog_never_reads_a_player_or_mpv_object():
    import app.media_info_dialog as module

    with open(module.__file__, encoding="utf-8") as handle:
        source = handle.read()

    for forbidden in ("mpv_player", "current_file", "track_list",
                      "property_reader", "app.player", "app.video_frame"):
        assert forbidden not in source, f"player/mpv bagi: {forbidden}"
