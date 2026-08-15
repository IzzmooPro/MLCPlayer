"""Altyazı Merkezi — KOMPAKT görsel kabuk regresyonları.

Bu tur YALNIZCA görsel kabuk ve pencere yaşam döngüsüdür: ağ yok, indirme yok,
MPV yok, menü entegrasyonu yok. Testler sahte veriyle çalışır.

Tasarım kararı: büyük yönetim ekranı DEĞİL, kompakt ve hızlı kullanılan
yardımcı pencere. Kaldırılan teknik medya özeti, arama türü radio düğmeleri
ve uzun hedef dosya açıklaması geri gelmemeli.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QLineEdit, QMainWindow, QPushButton, QRadioButton,
    QScrollArea)

from app.subtitle_center import SubtitleCenterDialog, sample_results

MEDIA = {
    "file_name": "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv",
    "title": "Resident Alien",
    "season": 1,
    "episode": 1,
    "is_series": True,
    "target_name": "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.srt",
}

MOVIE = {
    "file_name": "Supergirl.2026.2160p.WEB-DL.H265.mkv",
    "title": "Supergirl",
    "season": None,
    "episode": None,
    "is_series": False,
    "target_name": "Supergirl.2026.2160p.WEB-DL.H265.srt",
}


@pytest.fixture
def dialog_factory():
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(media=None, size=None):
        window = QMainWindow()
        window.resize(1280, 720)
        window.show()
        dialog = SubtitleCenterDialog(window, media=media or MEDIA)
        if size:
            dialog.resize(*size)
        dialog.show()
        app.processEvents()
        created.append((window, dialog))
        return app, window, dialog

    yield factory

    for window, dialog in created:
        dialog.close()
        window.close()
    app.processEvents()


# --- Pencere yapısı ve KOMPAKT ölçüler ---

def test_dialog_is_a_qdialog_owned_by_the_player(dialog_factory):
    app, window, dialog = dialog_factory()

    assert isinstance(dialog, QDialog)
    assert dialog.parent() is window
    assert dialog.windowTitle() == "Altyazı Merkezi"


def test_default_size_is_compact(dialog_factory):
    app, window, dialog = dialog_factory()

    assert 640 <= dialog.width() <= 680, f"varsayilan genislik {dialog.width()}"
    assert 425 <= dialog.height() <= 455, f"varsayilan yukseklik {dialog.height()}"


def test_four_results_leave_no_large_empty_area(dialog_factory):
    """Dort sonucta listenin altinda buyuk anlamsiz bosluk kalmamali."""
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()

    gap = dialog.results_gap()
    assert gap <= 80, f"sonuclarin altinda {gap} px bos alan kaldi"


def test_window_never_shrinks_below_minimum_with_few_results(dialog_factory):
    app, window, dialog = dialog_factory()

    for payload in ([], sample_results()[:1]):
        dialog.show_results(payload)
        app.processEvents()
        assert dialog.height() >= 420, f"pencere {dialog.height()} px'e dustu"
        assert dialog.width() >= 620


def test_many_results_do_not_grow_the_window_beyond_default(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results() * 8)
    app.processEvents()

    assert dialog.height() <= 455, f"cok sonucta pencere buyudu: {dialog.height()}"
    assert dialog.results_area.verticalScrollBar().maximum() > 0, "scroll yok"


def test_minimum_size_is_compact(dialog_factory):
    app, window, dialog = dialog_factory()

    assert 600 <= dialog.minimumWidth() <= 640
    assert 400 <= dialog.minimumHeight() <= 440


def test_dialog_fits_1366x768_and_common_dpi(dialog_factory):
    app, window, dialog = dialog_factory()

    # 150% DPI'da bile 1366x768 ekrana sigmali.
    assert dialog.width() * 1.5 <= 1366
    assert dialog.height() * 1.5 <= 768


def test_dialog_is_resizable_down_to_minimum(dialog_factory):
    app, window, dialog = dialog_factory()

    dialog.resize(dialog.minimumWidth(), dialog.minimumHeight())
    app.processEvents()
    assert dialog.width() == dialog.minimumWidth()
    assert dialog.height() == dialog.minimumHeight()


def test_dialog_does_not_use_global_always_on_top(dialog_factory):
    app, window, dialog = dialog_factory()

    assert not (dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    assert dialog.parent() is window


def test_many_results_do_not_grow_the_window(dialog_factory):
    app, window, dialog = dialog_factory()
    before = dialog.height()

    dialog.show_results(sample_results() * 6)
    app.processEvents()

    assert dialog.height() == before, "sonuc sayisi pencereyi uzatti"


def test_results_use_a_scroll_area(dialog_factory):
    app, window, dialog = dialog_factory()

    assert isinstance(dialog.results_area, QScrollArea)
    assert dialog.results_area.widgetResizable() is True


# --- KOMPAKT yerleşim: kaldırılanlar geri gelmemeli ---

def test_no_search_mode_radio_buttons(dialog_factory):
    app, window, dialog = dialog_factory()

    assert dialog.findChildren(QRadioButton) == [], (
        "arama turu radio dugmeleri kaldirilmaliydi")


def test_no_technical_media_summary_block(dialog_factory):
    app, window, dialog = dialog_factory()

    assert not hasattr(dialog, "summary_label"), "teknik medya ozeti geri geldi"
    texts = " ".join(w.text() for w in dialog.findChildren(type(dialog.title_field))
                     if hasattr(w, "text"))
    assert MEDIA["file_name"] not in texts


def test_no_long_target_description_label(dialog_factory):
    app, window, dialog = dialog_factory()

    assert not hasattr(dialog, "target_label"), (
        "uzun hedef dosya aciklamasi geri geldi")


def test_no_large_settings_button_in_action_row(dialog_factory):
    app, window, dialog = dialog_factory()

    labels = [b.text() for b in dialog.findChildren(QPushButton)]
    assert "Ayarlar" not in labels, (
        "alt kosede buyuk Ayarlar dugmesi olmamali")


def test_header_has_title_and_gear_icon(dialog_factory):
    app, window, dialog = dialog_factory()

    assert dialog.heading_label.text() == "Altyazı Merkezi"
    assert dialog.settings_icon_button.icon().isNull() is False
    assert dialog.settings_icon_button.text() == ""
    assert dialog.settings_icon_button.accessibleName().strip() != ""


# --- Tek yatay arama satırı ---

def test_search_row_holds_every_control(dialog_factory):
    app, window, dialog = dialog_factory()

    for name in ("title_field", "season_field", "episode_field",
                 "language_box", "search_button"):
        assert hasattr(dialog, name), f"arama satirinda {name} yok"
    row = dialog.search_row_widgets()
    assert dialog.search_button in row
    assert dialog.language_box in row


def test_series_fields_visible_only_for_series(dialog_factory):
    app, window, dialog = dialog_factory()
    assert dialog.season_field.isVisibleTo(dialog)
    assert dialog.season_field.text() == "1"
    assert dialog.episode_field.text() == "1"

    app2, window2, movie = dialog_factory(media=MOVIE)
    assert not movie.season_field.isVisibleTo(movie)
    assert not movie.episode_field.isVisibleTo(movie)


def test_series_fields_are_narrow(dialog_factory):
    app, window, dialog = dialog_factory()

    assert dialog.season_field.maximumWidth() <= 70
    assert dialog.episode_field.maximumWidth() <= 70


def test_no_single_letter_season_episode_labels(dialog_factory):
    """'S' ve 'B' tek harfleri kullaniciya anlamsiz."""
    app, window, dialog = dialog_factory()

    assert dialog.season_label.text().strip() not in ("S", "s")
    assert dialog.episode_label.text().strip() not in ("B", "b")


def test_season_and_episode_are_spelled_out_for_the_user(dialog_factory):
    app, window, dialog = dialog_factory()

    visible = (dialog.season_label.text() + " " + dialog.episode_label.text()
               + " " + dialog.season_field.placeholderText() + " "
               + dialog.episode_field.placeholderText())
    assert "Sezon" in visible, "Sezon metni kullaniciya gorunmuyor"
    assert "Bölüm" in visible, "Bolum metni kullaniciya gorunmuyor"


def test_title_field_expands_when_series_fields_are_hidden(dialog_factory):
    app, window, dialog = dialog_factory(size=(660, 440))
    app.processEvents()
    series_width = dialog.title_field.width()

    app2, window2, movie = dialog_factory(media=MOVIE, size=(660, 440))
    app2.processEvents()

    assert not movie.season_field.isVisibleTo(movie)
    assert not movie.episode_field.isVisibleTo(movie)
    assert not movie.season_label.isVisibleTo(movie)
    assert not movie.episode_label.isVisibleTo(movie)
    # ARTIK DAHA GÜÇLÜ GARANTİ: başlık kendi satırında tam genişlik alır,
    # bu yüzden dizi/film farkı onu daraltmaz. Eski beklenti "film modunda
    # genişlesin"di; yeni kural her iki modda da kullanılabilir genişliktir.
    assert movie.title_field.width() == series_width
    assert series_width >= 240, series_width


def test_language_defaults_to_turkish_without_codes(dialog_factory):
    app, window, dialog = dialog_factory()

    assert dialog.language_box.currentText() == "Türkçe"
    for index in range(dialog.language_box.count()):
        assert len(dialog.language_box.itemText(index)) > 2


def test_search_button_is_the_primary_orange_action(dialog_factory):
    app, window, dialog = dialog_factory()

    assert dialog.search_button.objectName() == "subtitlePrimaryAction"
    assert "#F26A3D" in dialog.styleSheet()
    assert dialog.search_button.isDefault() is True


def test_indicators_are_themed_not_default_qt(dialog_factory):
    app, window, dialog = dialog_factory()
    style = dialog.styleSheet()

    assert "QCheckBox::indicator" in style
    assert "QCheckBox::indicator:checked" in style


# --- Sonuç kartları ---

def test_sample_results_cover_the_required_states():
    results = sample_results()
    assert any(item["moviehash_match"] for item in results)
    assert any(not item["moviehash_match"] for item in results)
    assert any(item["hearing_impaired"] for item in results)
    assert any(len(item["name"]) > 70 for item in results)


def test_cards_are_compact_two_line_rows(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()

    cards = dialog.result_cards()
    assert len(cards) == len(sample_results())
    for card in cards:
        assert 50 <= card.height() <= 62, f"kart yuksekligi {card.height()}"
        assert card.line_count() == 2, "kart en fazla iki satir olmali"


def test_card_first_line_is_name_second_line_is_meta(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()
    card = dialog.result_cards()[0]

    assert card.result["name"].startswith(card.name_label.text()[:20])
    meta = card.meta_text()
    assert "Tam eşleşme" in meta
    assert "Türkçe" in meta
    assert "indirme" in meta
    assert "Puan" in meta


def test_hearing_impaired_marker_is_shown(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()

    hi = [c for c in dialog.result_cards() if c.result["hearing_impaired"]]
    assert hi and "İşitme engelli" in hi[0].meta_text()


def test_selected_card_gets_orange_highlight(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()
    card = dialog.result_cards()[1]

    dialog.select_result(card)
    app.processEvents()

    assert card.property("selected") is True
    assert all(o.property("selected") is False
               for o in dialog.result_cards() if o is not card)


def test_long_name_is_elided_with_full_tooltip(dialog_factory):
    app, window, dialog = dialog_factory(size=(620, 420))
    dialog.show_results(sample_results())
    app.processEvents()

    longest = max(dialog.result_cards(), key=lambda c: len(c.result["name"]))
    assert longest.name_label.text() != longest.result["name"], "elide yok"
    assert longest.name_label.toolTip() == longest.result["name"]
    assert dialog.width() == 620, "uzun isim pencereyi buyuttu"


def test_cards_stay_readable_at_minimum_size(dialog_factory):
    app, window, dialog = dialog_factory(size=(620, 420))
    dialog.show_results(sample_results())
    app.processEvents()

    for card in dialog.result_cards():
        assert card.height() >= 50
        assert card.name_label.text().strip() != ""


# --- Durumlar ve alt satır ---

def test_status_line_shows_result_count(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()

    assert "4" in dialog.status_text()


def test_empty_state(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results([])
    app.processEvents()

    assert "bulunamadı" in dialog.status_text().lower()
    assert dialog.result_cards() == []


def test_loading_state(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_loading()
    app.processEvents()

    assert "aran" in dialog.status_text().lower()


def test_error_state_is_safe_text(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_error("Bağlantı zaman aşımına uğradı.")
    app.processEvents()

    assert "zaman" in dialog.status_text().lower()
    assert "Traceback" not in dialog.status_text()


def test_the_single_download_action_is_disabled_until_selection(dialog_factory):
    """ESKİ AD: `test_download_buttons_disabled_until_selection`.

    "Yalnızca İndir" düğmesi kaldırıldı; çoğul sözleşme geçersiz.
    """
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()
    assert dialog.apply_button.isEnabled() is False

    dialog.select_result(dialog.result_cards()[0])
    app.processEvents()
    assert dialog.apply_button.isEnabled() is True
    assert not hasattr(dialog, "download_button")


def test_target_name_is_available_as_tooltip_not_a_big_label(dialog_factory):
    app, window, dialog = dialog_factory()

    assert MEDIA["target_name"] in dialog.apply_button.toolTip()


def test_overwrite_warning_appears_in_the_status_line(dialog_factory):
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    dialog.set_overwrite_warning(True)
    app.processEvents()

    assert "üzerine yaz" in dialog.status_text().lower()


def test_action_row_button_order(dialog_factory):
    app, window, dialog = dialog_factory()

    labels = [b.text() for b in dialog.action_row_buttons()]
    assert labels == ["İndir ve Uygula", "Kapat"]


# --- Ayar çekmecesi (dişli ikonundan) ---

def test_gear_only_requests_settings_without_resizing(dialog_factory):
    """Dişli ARTIK içeride çekmece açmaz; ayrı pencere ister.

    Eski sağdan açılan çekmece ana arama alanını 35 px'e kadar
    daraltıyordu (kullanıcı raporu). Görsel kabuk artık ayar alanlarını
    hiç barındırmaz; bkz. `app/subtitle_center_settings_dialog.py`.
    """
    app, window, dialog = dialog_factory()
    dialog.show_results(sample_results())
    app.processEvents()
    before = (dialog.width(), dialog.height())
    title_before = dialog.title_field.width()
    seen = []
    dialog.settings_requested.connect(lambda: seen.append(True))

    dialog.settings_icon_button.click()
    app.processEvents()

    assert seen == [True], "disli ayar istegini yayinlamadi"
    assert (dialog.width(), dialog.height()) == before
    assert dialog.title_field.width() == title_before


def test_visual_shell_no_longer_owns_settings_fields(dialog_factory):
    app, window, dialog = dialog_factory()

    for name in ("settings_drawer", "settings_language_box", "api_key_field",
                 "username_field", "password_field", "after_download_box",
                 "settings_save_button", "settings_cancel_button",
                 "show_password_box", "credential_hint"):
        assert not hasattr(dialog, name), f"kaldirilan alan duruyor: {name}"


def test_no_persistence_in_this_round():
    import inspect

    from app import subtitle_center

    source = inspect.getsource(subtitle_center)
    for forbidden in ("QSettings", "CredentialStore", "OpenSubtitlesClient"):
        assert forbidden not in source


# --- Erişilebilirlik ---

def test_all_buttons_use_pointing_hand_cursor(dialog_factory):
    app, window, dialog = dialog_factory()
    app.processEvents()

    for button in dialog.findChildren(QPushButton):
        assert button.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_key_controls_have_accessible_names(dialog_factory):
    app, window, dialog = dialog_factory()

    for widget in (dialog.search_button, dialog.apply_button,
                   dialog.close_button,
                   dialog.language_box, dialog.settings_icon_button):
        assert widget.accessibleName().strip() != ""


def test_escape_closes_the_dialog(dialog_factory):
    from PyQt6.QtTest import QTest

    app, window, dialog = dialog_factory()
    assert dialog.isVisible()

    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    app.processEvents()

    assert not dialog.isVisible()


# --- Bağımsızlık ---

def test_no_legacy_env_flags():
    import inspect

    from app import subtitle_center

    source = inspect.getsource(subtitle_center)
    assert "MLCPLAYER_CLASSIC_UI" not in source
    assert "MLCPLAYER_OVERLAY_PREVIEW" not in source


def test_no_external_image_assets():
    import inspect

    from app import subtitle_center

    source = inspect.getsource(subtitle_center)
    for forbidden in (".png", ".svg", ".ico"):
        assert forbidden not in source
