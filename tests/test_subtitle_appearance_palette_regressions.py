# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Şeffaflık RENK PALETİNİN İÇİNDE + eşit renk satırı + dar pencere.

Bu turun kırmızı gerekçeleri (mevcut üründe ölçüldü):

1. Şeffaflık ana pencerede AYRI bir `subtitleTransparentButton`
   düğmesindeydi. Kullanıcının beklediği yer renk penceresidir; ayrı
   düğme renk satırını da bozuyordu.
2. `sub_back_color` hücresine ÇİFT genişlik payı verilmişti
   (`colors_row.addLayout(cell, 2)`) ve içindeki `addStretch(1)`
   yüzünden "Kenarlık" kutusu sağ kenara yapışıyordu; üç renk kutusu
   ne eşit ne de yan yanaydı.
3. Pencere 640×480 / 560×430 ile hâlâ gereğinden geniş.
4. **Açılış çökmesi:** combo değerleri merkezî
   `normalise_subtitle_numeric()` üzerinden geçerken `sub_pos` hâlâ
   doğrudan `int(values.get("sub_pos", ...))` ile okunuyordu; `None`,
   `"bozuk"`, `NaN`, `±inf` değerlerinde pencere AÇILIRKEN çöküyordu.

DEĞİŞMEYEN sözleşmeler: `#AARRGGBB` renk biçimi, `atomic_apply()`
atomikliği ve rollback, bitmap uyarısı, temsili sahne önizlemesi,
`sub_pos` 0-100 ve `sub_delay`in oturumlar arası 0 saklanması.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                             QPushButton, QWidget)

from app.config import SUBTITLE_DEFAULTS
from app import subtitle_appearance_dialog as dialog_module
from app.subtitle_appearance_dialog import (DEFAULT_SIZE, MINIMUM_SIZE,
                                            NO_COLOUR_TEXT,
                                            SubtitleAppearanceDialog,
                                            SubtitleColourDialog)
from app.subtitle_style import (BACKGROUND_BOX, OUTLINE_AND_SHADOW,
                                qcolor_to_mpv_argb, style_properties)

COLOUR_NAMES = ("subtitleColorSwatch_sub_color",
                "subtitleColorSwatch_sub_back_color",
                "subtitleColorSwatch_sub_border_color")


@pytest.fixture
def dialog_factory(tmp_path):
    """Gerçek kullanıcı ayarları KİRLETİLMEZ."""
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(values=None, track_list=None, apply_callback=None,
                error_reporter=None, show=True):
        dialog = SubtitleAppearanceDialog(
            values=values, track_list=track_list,
            apply_callback=apply_callback, error_reporter=error_reporter)
        created.append(dialog)
        if show:
            dialog.show()
            app.processEvents()
        return app, dialog

    yield factory

    for dialog in created:
        dialog.close()
        dialog.deleteLater()
    app.processEvents()


def swatch_rects(dialog):
    """Üç renk kutusunun PENCEREYE göre dikdörtgenleri."""
    rects = []
    for name in COLOUR_NAMES:
        widget = dialog.findChild(QWidget, name)
        assert widget is not None, name
        top_left = widget.mapTo(dialog, widget.rect().topLeft())
        rects.append(widget.rect().translated(top_left))
    return rects


# --- 1. Ana penceredeki ayrı Şeffaf düğmesi KALKTI --------------------

def test_the_standalone_transparent_button_is_gone(dialog_factory):
    app, dialog = dialog_factory()

    assert dialog.findChild(QWidget, "subtitleTransparentButton") is None
    assert not hasattr(dialog, "transparent_button")
    assert "subtitleTransparentButton" not in dialog.tab_order_names()


def test_the_tab_order_goes_straight_through_the_three_swatches(
        dialog_factory):
    app, dialog = dialog_factory()

    order = dialog.tab_order_names()

    assert order[:4] == ["subtitleDelayCombo", "subtitleScaleCombo",
                         "subtitleBorderCombo", "subtitlePositionSlider"]
    assert order[4:7] == list(COLOUR_NAMES)
    assert order[-3:] == ["subtitleResetButton", "subtitleCancelButton",
                          "subtitleApplyButton"]


# --- 2. "Renk yok (Şeffaf)" PALETİN İÇİNDE ---------------------------

def test_the_background_palette_offers_a_visible_no_colour_action(tmp_path):
    """Palette açık, görünür ve erişilebilir bir seçenek eklenir."""
    app = QApplication.instance() or QApplication([])
    picker = SubtitleColourDialog(QColor(0, 32, 160, 200), title="Arka plan",
                                  allow_transparent=True)
    try:
        button = picker.findChild(QPushButton, "subtitleNoColourButton")
        assert button is not None, "palette 'Renk yok' eylemi yok"
        assert button.text() == NO_COLOUR_TEXT == "Renk yok (Şeffaf)"
        assert button.accessibleName().strip() != ""
        # Sistem renk penceresi kendi düğmelerini gizler; seçenek ancak
        # NON-NATIVE pencerede gerçekten görünür.
        from PyQt6.QtWidgets import QColorDialog

        assert picker.testOption(
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        assert picker.testOption(
            QColorDialog.ColorDialogOption.ShowAlphaChannel)
        assert picker.findChild(QDialogButtonBox) is not None
    finally:
        picker.deleteLater()
        app.processEvents()


def test_the_no_colour_action_produces_a_fully_transparent_colour(tmp_path):
    app = QApplication.instance() or QApplication([])
    picker = SubtitleColourDialog(QColor(0, 32, 160, 200),
                                  allow_transparent=True)
    try:
        picker.findChild(QPushButton, "subtitleNoColourButton").click()
        app.processEvents()

        assert picker.result() == QDialog.DialogCode.Accepted
        assert picker.selected_colour().alpha() == 0
    finally:
        picker.deleteLater()
        app.processEvents()


def test_text_and_border_palettes_have_no_no_colour_action(tmp_path):
    """Yazı ve kenarlık için "renk yok" ANLAMSIZDIR; eklenmez."""
    app = QApplication.instance() or QApplication([])
    picker = SubtitleColourDialog(QColor(255, 255, 255, 255),
                                  allow_transparent=False)
    try:
        assert picker.findChild(QPushButton, "subtitleNoColourButton") is None
    finally:
        picker.deleteLater()
        app.processEvents()


def test_only_the_background_swatch_opens_a_palette_with_no_colour(
        dialog_factory, monkeypatch):
    seen = []

    def fake_pick(parent, initial, title="", allow_transparent=False):
        seen.append((title, allow_transparent))
        return QColor()

    monkeypatch.setattr(dialog_module, "pick_colour", fake_pick)
    app, dialog = dialog_factory()

    for key in ("sub_color", "sub_back_color", "sub_border_color"):
        dialog._swatches[key].click()
    app.processEvents()

    assert [flag for _title, flag in seen] == [False, True, False]


def test_choosing_no_colour_clears_the_preview_box(dialog_factory,
                                                   monkeypatch):
    monkeypatch.setattr(dialog_module, "pick_colour",
                        lambda *a, **k: QColor(0, 0, 0, 0))
    app, dialog = dialog_factory(
        values={"sub_back_color": QColor(0, 32, 160, 200)})
    app.processEvents()
    assert dialog.preview.background_visible() is True

    dialog._swatches["sub_back_color"].click()
    app.processEvents()

    assert dialog.current_values()["sub_back_color"].alpha() == 0
    assert dialog.preview.background_visible() is False


def test_no_colour_produces_the_outline_and_shadow_contract(dialog_factory,
                                                            monkeypatch):
    monkeypatch.setattr(dialog_module, "pick_colour",
                        lambda *a, **k: QColor(0, 0, 0, 0))
    app, dialog = dialog_factory()
    dialog._swatches["sub_back_color"].click()

    props = style_properties(dialog.current_values())

    assert props["sub_back_color"] == "#00000000"
    assert props["sub_border_style"] == OUTLINE_AND_SHADOW


def test_cancelling_the_palette_keeps_the_previous_colour_exactly(
        dialog_factory, monkeypatch):
    monkeypatch.setattr(dialog_module, "pick_colour",
                        lambda *a, **k: QColor())      # geçersiz = İptal
    app, dialog = dialog_factory(
        values={"sub_back_color": QColor(0, 32, 160, 200)})

    dialog._swatches["sub_back_color"].click()
    app.processEvents()

    colour = dialog.current_values()["sub_back_color"]
    assert (colour.red(), colour.green(), colour.blue(),
            colour.alpha()) == (0, 32, 160, 200)
    assert qcolor_to_mpv_argb(colour) == "#C80020A0"


@pytest.mark.parametrize("chosen, expected_style", [
    (QColor(0, 32, 160, 255), BACKGROUND_BOX),
    (QColor(0, 32, 160, 150), BACKGROUND_BOX),
])
def test_normal_and_translucent_choices_still_work(dialog_factory, monkeypatch,
                                                   chosen, expected_style):
    monkeypatch.setattr(dialog_module, "pick_colour",
                        lambda *a, **k: QColor(chosen))
    app, dialog = dialog_factory()

    dialog._swatches["sub_back_color"].click()
    app.processEvents()

    values = dialog.current_values()
    assert values["sub_back_color"].alpha() == chosen.alpha()
    assert dialog.preview.background_visible() is True
    assert style_properties(values)["sub_border_style"] == expected_style


def test_text_and_border_colours_are_unaffected(dialog_factory, monkeypatch):
    monkeypatch.setattr(dialog_module, "pick_colour",
                        lambda *a, **k: QColor(242, 106, 61, 255))
    app, dialog = dialog_factory()

    dialog._swatches["sub_color"].click()
    dialog._swatches["sub_border_color"].click()
    app.processEvents()

    values = dialog.current_values()
    assert qcolor_to_mpv_argb(values["sub_color"]) == "#FFF26A3D"
    assert qcolor_to_mpv_argb(values["sub_border_color"]) == "#FFF26A3D"


def test_the_palette_is_shown_in_turkish_like_the_rest_of_the_product(
        dialog_factory):
    """Non-native pencere Qt'nin İngilizce metinleriyle GELMEMELİ.

    Sistem renk penceresini Windows yerelleştiriyordu. Palete kendi
    seçeneğimizi ekleyebilmek için non-native pencereye geçildi ve
    "Basic colors / OK / Cancel" İngilizce çıkıyordu; ürünün tamamı
    Türkçe olduğu için Qt'nin kendi çevirisi `pick_colour()` içinde,
    YALNIZ pencere yaşarken kurulur.
    """
    translator = dialog_module._turkish_translator()
    if translator is None:
        pytest.skip("Qt Türkçe çeviri dosyası (qtbase_tr.qm) bu ortamda yok")

    app, dialog = dialog_factory()
    application = QApplication.instance()
    application.installTranslator(translator)
    try:
        picker = SubtitleColourDialog(QColor(0, 32, 160, 200), dialog,
                                      "Arka plan", allow_transparent=True)
        box = picker.findChild(QDialogButtonBox)
        texts = [button.text().replace("&", "") for button in box.buttons()]
        picker.deleteLater()
    finally:
        application.removeTranslator(translator)
    app.processEvents()

    assert "Tamam" in texts, texts
    assert "İptal" in texts, texts
    assert "OK" not in texts and "Cancel" not in texts, texts


def test_the_translator_is_not_left_installed_after_picking(monkeypatch):
    """Çeviri uygulamanın geri kalanına SIZMAZ.

    NOT: gerçek pencere açılmaz. `SubtitleColourDialog` yerine ölçülebilir
    bir vekil konur; `pick_colour()` çeviriyi kurar, vekili çalıştırır ve
    çıkarken çeviriyi KALDIRMALIDIR.
    """
    if dialog_module._turkish_translator() is None:
        pytest.skip("Qt Türkçe çeviri dosyası yok")

    app = QApplication.instance() or QApplication([])
    seen = {}

    class StubPicker:
        def __init__(self, initial, parent=None, title="",
                     allow_transparent=False):
            probe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            seen["inside"] = probe.button(
                QDialogButtonBox.StandardButton.Ok).text().replace("&", "")
            probe.deleteLater()

        def exec(self):
            return QDialog.DialogCode.Rejected

        def selected_colour(self):
            return QColor()

        def deleteLater(self):
            pass

    monkeypatch.setattr(dialog_module, "SubtitleColourDialog", StubPicker)

    result = dialog_module.pick_colour(None, QColor(0, 0, 0, 0), "Arka plan",
                                       allow_transparent=True)

    assert result.isValid() is False, "iptal geçersiz renk döndürmeli"
    assert seen["inside"] == "Tamam", "çeviri pencere kurulurken YOK"
    probe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    try:
        after = probe.button(
            QDialogButtonBox.StandardButton.Ok).text().replace("&", "")
    finally:
        probe.deleteLater()
    assert after == "OK", "çeviri pencereden sonra kurulu kaldı"


# --- 3. Üç renk kutusu EŞİT ve YAN YANA -------------------------------

def test_the_three_colour_swatches_are_equal_and_adjacent(dialog_factory):
    app, dialog = dialog_factory()
    app.processEvents()

    rects = swatch_rects(dialog)

    widths = {rect.width() for rect in rects}
    assert len(widths) == 1, f"kutular eşit değil: {widths}"
    tops = {rect.y() for rect in rects}
    assert len(tops) == 1, f"kutular ayrı satırlarda: {tops}"
    gaps = [second.left() - first.right() - 1
            for first, second in zip(rects, rects[1:])]
    assert all(8 <= gap <= 12 for gap in gaps), f"boşluklar: {gaps}"


def test_the_border_swatch_is_not_pushed_to_the_right_edge(dialog_factory):
    """Kenarlık kutusu sağ kenara TEK BAŞINA yapışmaz."""
    app, dialog = dialog_factory()
    app.processEvents()

    rects = swatch_rects(dialog)
    right_gap = dialog.width() - rects[-1].right()
    row_span = rects[-1].right() - rects[0].left()

    assert right_gap >= 20, f"kenarlık sağ kenara yapıştı: {right_gap}"
    assert row_span <= dialog.width() * 0.75, (
        f"renk satırı gereksiz yayıldı: {row_span}/{dialog.width()}")


def test_the_colour_row_keeps_its_order(dialog_factory):
    app, dialog = dialog_factory()

    rects = swatch_rects(dialog)

    assert rects[0].left() < rects[1].left() < rects[2].left()


# --- 4. Daha dar pencere ----------------------------------------------

def test_the_window_opens_at_the_narrower_default(dialog_factory):
    app, dialog = dialog_factory()

    assert DEFAULT_SIZE == (600, 480)
    assert (dialog.width(), dialog.height()) == DEFAULT_SIZE


def test_the_minimum_is_the_proven_safe_width(dialog_factory):
    """Hedef 540×430; ölçülen kırpılma varsa KANITLANAN en küçük değer."""
    app, dialog = dialog_factory()
    dialog.resize(1, 1)
    app.processEvents()

    assert (dialog.width(), dialog.height()) == MINIMUM_SIZE
    assert MINIMUM_SIZE[0] <= 560, MINIMUM_SIZE
    assert MINIMUM_SIZE[1] == 430


def test_nothing_is_clipped_at_the_minimum(dialog_factory):
    app, dialog = dialog_factory()
    dialog.resize(1, 1)
    app.processEvents()

    for name in ("subtitleDelayCombo", "subtitleScaleCombo",
                 "subtitleBorderCombo", "subtitlePositionSlider",
                 "subtitleResetButton", "subtitleCancelButton",
                 "subtitleApplyButton", "subtitlePreviewSurface") \
            + COLOUR_NAMES:
        widget = dialog.findChild(QWidget, name)
        assert widget is not None, name
        assert widget.isVisible(), name
        hint = widget.minimumSizeHint()
        assert widget.width() >= hint.width(), f"{name} yatayda kırpıldı"
        assert widget.height() >= hint.height(), f"{name} dikeyde kırpıldı"


# --- 5. `sub_pos` açılış çökmesi --------------------------------------

@pytest.mark.parametrize("broken", [None, "bozuk", float("nan"),
                                    float("inf"), float("-inf"), [], {}])
def test_a_broken_sub_pos_never_crashes_the_window(dialog_factory, broken):
    """Ölçülen kusur: bu değerlerde pencere AÇILIRKEN çöküyordu."""
    app, dialog = dialog_factory(values={"sub_pos": broken})

    assert dialog.isVisible()
    assert dialog.current_values()["sub_pos"] == pytest.approx(
        float(SUBTITLE_DEFAULTS["sub_pos"]))


@pytest.mark.parametrize("stored, expected", [
    (-50, 0.0), (150, 100.0), (250.0, 100.0), (63, 63.0), ("42", 42.0),
])
def test_out_of_range_sub_pos_is_clamped_on_open(dialog_factory, stored,
                                                 expected):
    app, dialog = dialog_factory(values={"sub_pos": stored})

    assert dialog.current_values()["sub_pos"] == pytest.approx(expected)
    assert dialog.position_slider.value() == int(expected)


def test_the_position_label_matches_the_normalised_value(dialog_factory):
    app, dialog = dialog_factory(values={"sub_pos": 150})

    assert dialog.position_value.text() == "%100"


# --- 6. Klavye kullanımı ----------------------------------------------

def test_enter_does_not_open_a_palette(dialog_factory, monkeypatch):
    from PyQt6.QtTest import QTest

    opened = []
    monkeypatch.setattr(dialog_module, "pick_colour",
                        lambda *a, **k: opened.append(1) or QColor())
    app, dialog = dialog_factory()
    dialog.scale_combo.setFocus()
    app.processEvents()
    QTest.keyClick(dialog.scale_combo, Qt.Key.Key_Return)
    app.processEvents()

    assert opened == []


def test_every_swatch_is_keyboard_reachable(dialog_factory):
    app, dialog = dialog_factory()

    for name in COLOUR_NAMES:
        widget = dialog.findChild(QWidget, name)
        assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus, name
        assert widget.accessibleName().strip() != "", name
