"""Altyazı Ayarları penceresinin GERÇEK responsive yerleşimi.

Bu dosya ilk yazıldığında YATAY tasarımı ölçüyordu (varsayılan 852×476):

    sol  = (16, 14, 320, 412)
    sağ  = (352, 14, 500, 412)   -> sağ kenar 852 = pencere kenarı
    sağ iç marj = 0

ÜRÜN KARARI İLE ESKİYEN SÖZLEŞMELER (sessizce silinmedi, dönüştürüldü):

- `test_the_gap_between_the_two_panels_is_preserved`,
  `test_default_geometry_splits_the_window_as_designed`,
  `test_the_preview_keeps_its_share_in_the_normal_view`,
  `test_the_right_inner_margin_is_not_eaten_by_the_preview`:
  ikisi YAN YANA iki panelin arasındaki boşluğu ve genişlik payını
  ölçüyordu. Yeni tasarım DİKEY: ayarlar üstte, önizleme altta. Aynı
  kullanıcı garantisi (paneller kesişmez, pencere içinde kalır, iç marj
  korunur, her boyutta kullanılabilir) dikey biçimde ölçülür.
- `test_spinboxes_keep_their_stepper_arrows`,
  `test_the_widest_value_fits_beside_the_stepper_arrows`,
  `test_a_click_on_the_stepper_changes_the_value_by_one_step`,
  `test_the_three_spinboxes_fit_the_compact_column`: dördü de
  `QDoubleSpinBox` ok düğmelerinin korunmasını ŞART koşuyordu. Ok
  düğmeleri ürün kararıyla kaldırıldı (kullanıcı anlamıyordu ve gerçek
  Windows ölçümünde yazı alanı ile ok alanı kesişiyordu). Yerine hazır
  değer listelerinin gerçekten kullanılabilir olduğu ölçülür: en uzun
  etiket kırpılmaz, açılır liste çalışır, seçim değeri değiştirir.

Testler yalnız genişlik sayılarına değil, gerçek widget
dikdörtgenlerinin kesişmediğine ve pencere içinde kaldığına bakar.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication, QComboBox, QWidget

from app.subtitle_appearance_dialog import (DEFAULT_SIZE, MINIMUM_SIZE,
                                            SubtitleAppearanceDialog)

MARGIN_MIN, MARGIN_MAX = 10, 18
COMBO_NAMES = ("subtitleDelayCombo", "subtitleScaleCombo",
               "subtitleBorderCombo")


@pytest.fixture
def dialog_factory(tmp_path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(size=None, track_list=None):
        dialog = SubtitleAppearanceDialog(track_list=track_list)
        created.append(dialog)
        dialog.show()
        app.processEvents()
        if size:
            dialog.resize(*size)
            app.processEvents()
        return app, dialog

    yield factory

    for dialog in created:
        dialog.close()
        dialog.deleteLater()
    app.processEvents()


def panels(dialog):
    top = dialog.findChild(QWidget, "subtitleAppearanceSettings")
    bottom = dialog.findChild(QWidget, "subtitleAppearancePreview")
    assert top is not None and bottom is not None
    return top.geometry(), bottom.geometry()


def margins(dialog):
    top, bottom = panels(dialog)
    return {
        "left_margin": top.x(),
        "right_margin": dialog.width() - (top.x() + top.width()),
        "vertical_gap": bottom.y() - top.bottom() - 1,
        "settings_height": top.height(),
        "preview_height": bottom.height(),
        "preview_width": bottom.width(),
    }


# --- 1-4. Varsayilan gorunum (DIKEY) ---

def test_the_side_margins_are_not_eaten_by_any_panel(dialog_factory):
    app, dialog = dialog_factory()

    measured = margins(dialog)
    assert MARGIN_MIN <= measured["left_margin"] <= MARGIN_MAX, measured
    assert MARGIN_MIN <= measured["right_margin"] <= MARGIN_MAX, measured


def test_the_gap_between_settings_and_preview_is_preserved(dialog_factory):
    app, dialog = dialog_factory()

    measured = margins(dialog)
    assert 4 <= measured["vertical_gap"] <= MARGIN_MAX, measured


@pytest.mark.parametrize("size", [DEFAULT_SIZE, MINIMUM_SIZE, (900, 620),
                                  (1100, 700), (640, 480)])
def test_panels_never_overlap_and_stay_inside_the_window(dialog_factory, size):
    app, dialog = dialog_factory(size=size)

    top, bottom = panels(dialog)
    assert not top.intersects(bottom), (
        f"paneller kesisiyor: top={top.getRect()} bottom={bottom.getRect()}")
    assert dialog.rect().contains(top), f"ayarlar pencere disinda: {top.getRect()}"
    assert dialog.rect().contains(bottom), (
        f"onizleme pencere disinda: {bottom.getRect()} "
        f"dialog={dialog.rect().getRect()}")


def test_default_geometry_stacks_the_window_as_designed(dialog_factory):
    app, dialog = dialog_factory()

    measured = margins(dialog)
    assert measured["preview_width"] >= dialog.width() - 2 * MARGIN_MAX
    assert measured["preview_height"] >= 190, measured
    assert measured["settings_height"] < measured["preview_height"], measured


# --- 5-8. Kucultme ---

def test_the_window_really_shrinks_to_the_declared_minimum(dialog_factory):
    app, dialog = dialog_factory()

    dialog.resize(1, 1)
    app.processEvents()

    assert (dialog.width(), dialog.height()) == MINIMUM_SIZE


def test_the_minimum_size_hint_fits_the_declared_minimum(dialog_factory):
    app, dialog = dialog_factory()

    hint = dialog.minimumSizeHint()

    assert hint.width() <= MINIMUM_SIZE[0], hint.width()
    assert hint.height() <= MINIMUM_SIZE[1], hint.height()


def test_the_minimum_view_keeps_every_control_usable(dialog_factory):
    app, dialog = dialog_factory(size=MINIMUM_SIZE)

    # NOT: ayrı "Şeffaf" düğmesi KALDIRILDI; şeffaflık arka plan
    # paletinin içindedir. Yerine üç renk kutusu ölçülür.
    for name in COMBO_NAMES + ("subtitlePositionSlider",
                               "subtitleColorSwatch_sub_color",
                               "subtitleColorSwatch_sub_back_color",
                               "subtitleColorSwatch_sub_border_color",
                               "subtitleResetButton", "subtitleCancelButton",
                               "subtitleApplyButton",
                               "subtitlePreviewSurface"):
        widget = dialog.findChild(QWidget, name)
        assert widget is not None, f"{name} bulunamadi"
        assert widget.isVisible(), f"{name} gorunmuyor"
        hint = widget.minimumSizeHint()
        assert widget.width() >= hint.width(), f"{name} yatayda kirpildi"
        assert widget.height() >= hint.height(), f"{name} dikeyde kirpildi"


@pytest.mark.parametrize("size", [DEFAULT_SIZE, MINIMUM_SIZE, (1100, 700)])
def test_preview_content_stays_inside_the_preview_panel(dialog_factory, size):
    app, dialog = dialog_factory(size=size)
    dialog.preview.set_sample_text("Cok uzun bir altyazi satiri " * 5)
    app.processEvents()

    rect = dialog.preview.text_rect()

    assert dialog.preview.rect().contains(rect), (
        f"onizleme metni yuzeyden tasti: {rect.getRect()} / "
        f"{dialog.preview.rect().getRect()}")


# --- 9-12. Hazir deger listelerinin kullanilabilirligi ---
#
# (Eski spinbox/stepper testlerinin yerini alan sozlesme.)

def test_the_preset_combos_are_real_combo_boxes(dialog_factory):
    app, dialog = dialog_factory()

    for name in COMBO_NAMES:
        combo = dialog.findChild(QComboBox, name)
        assert combo is not None, f"{name} bulunamadi"
        assert combo.count() > 0, f"{name} bos"
        assert combo.isEditable() is False, (
            f"{name} duzenlenebilir: kullanici serbest deger yazabilir")


@pytest.mark.parametrize("size", [DEFAULT_SIZE, MINIMUM_SIZE])
def test_the_closed_box_shows_the_value_without_clipping(dialog_factory, size):
    """KAPALI kutudaki kisa bicim her boyutta tam gorunur.

    Olculen kirmizi kanit: tam aciklamali etiket ("0 sn - Senkron",
    168 px) uc listenin paylastigi satirda 560 px'lik pencerede 144 px
    alana sigmiyordu. Urun kapali kutuda KISA bicimi cizer; tam etiket
    acilir listede kalir (asagidaki test).
    """
    app, dialog = dialog_factory(size=size)

    for name in COMBO_NAMES:
        combo = dialog.findChild(QComboBox, name)
        widest = max(
            (combo._short(combo.itemData(i, Qt.ItemDataRole.UserRole))
             for i in range(combo.count())),
            key=lambda text: combo.fontMetrics().horizontalAdvance(text))
        advance = combo.fontMetrics().horizontalAdvance(widest)
        room = combo.width() - 26        # acilir ok alani + ic bosluk
        assert advance <= room, (
            f"{name}: en uzun kisa bicim {widest!r} ({advance}px) "
            f"{room}px alana sigmiyor")


def test_the_popup_list_is_wide_enough_for_the_full_labels(dialog_factory):
    """Acilir listede TAM aciklamali etiket kirpilmaz."""
    app, dialog = dialog_factory(size=MINIMUM_SIZE)

    for name in COMBO_NAMES:
        combo = dialog.findChild(QComboBox, name)
        longest = max((combo.itemText(i) for i in range(combo.count())),
                      key=lambda text: combo.fontMetrics()
                      .horizontalAdvance(text))
        advance = combo.fontMetrics().horizontalAdvance(longest)
        assert combo.view().minimumWidth() >= advance, (
            f"{name}: acilir liste {combo.view().minimumWidth()}px, "
            f"en uzun etiket {longest!r} {advance}px")


def test_the_three_combos_share_one_row_without_overlapping(dialog_factory):
    app, dialog = dialog_factory(size=MINIMUM_SIZE)

    rects = []
    for name in COMBO_NAMES:
        combo = dialog.findChild(QComboBox, name)
        top_left = combo.mapTo(dialog, combo.rect().topLeft())
        rects.append(combo.rect().translated(top_left))
    tops = {rect.y() for rect in rects}
    assert len(tops) == 1, f"listeler ayri satirlara yayildi: {tops}"
    for first, second in zip(rects, rects[1:]):
        assert not first.intersects(second), (
            f"listeler kesisiyor: {first.getRect()} {second.getRect()}")


def test_selecting_an_item_changes_the_value(dialog_factory):
    """Seçim GERÇEK değeri değiştirir; etiket metni parse edilmez."""
    app, dialog = dialog_factory()
    combo = dialog.findChild(QComboBox, "subtitleBorderCombo")

    before = combo.currentData(Qt.ItemDataRole.UserRole)
    combo.setCurrentIndex(combo.count() - 1)
    app.processEvents()
    after = combo.currentData(Qt.ItemDataRole.UserRole)

    assert before != after
    assert after == pytest.approx(5.0)
    assert dialog.current_values()["sub_border_size"] == pytest.approx(5.0)
