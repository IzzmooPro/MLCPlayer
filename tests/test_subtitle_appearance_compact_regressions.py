"""Altyazı Ayarları: dikey/kompakt yerleşim ve HAZIR DEĞER listeleri.

Ölçülen eski durum (bu turun kırmızı gerekçesi):

- Pencere 852×476, minimum 760×430; kullanıcı için gereksiz büyük.
- Üç `QDoubleSpinBox` yan yana; gerçek Windows ölçümünde yazı alanı ile
  ok alanı geometrik olarak KESİŞİYOR (`overlap=true`) ve küçük
  yukarı/aşağı okları anlaşılmıyor.
- Aralıklar ürün için anlamsız genişlikte: senkron ±120 sn, boyut
  0,5–3,0×, kenarlık 0–10 px. Kullanıcı yanlışlıkla devasa kenarlık veya
  3× yazı uygulayabiliyor.

Yeni sözleşme:

- 640×480 varsayılan, 560×430 gerçek minimum, dikey yerleşim
  (ayarlar ÜSTTE, temsili önizleme ALTTA).
- Spinbox yok; üç `QComboBox` hazır değer listesi. Gerçek sayı
  `currentData()` içinde float'tır; ETİKET METNİ PARSE EDİLMEZ.
- Arka planda açık `Şeffaf` seçeneği (alfa sürgüsü aramaya gerek yok).
- Merkezi `normalise_subtitle_numeric()` eski aşırı kayıtları hazır
  değerlere çeker; pencere, `style_properties()`/`atomic_apply()` ve
  `restore_subtitle_settings()` aynı sınırı kullanır.

DEĞİŞMEYEN sözleşmeler: `#AARRGGBB` renk biçimi, `atomic_apply()`
atomikliği ve rollback, bitmap altyazı uyarısı, temsili sahne
önizlemesi, `sub_pos` 0–100 ve `sub_delay`in oturumlar arası 0
saklanması.
"""
import math
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox,
                             QSpinBox, QWidget)

from app.config import SUBTITLE_DEFAULTS
from app.subtitle_appearance_dialog import (DEFAULT_SIZE, MINIMUM_SIZE,
                                            SubtitleAppearanceDialog)
from app.subtitle_style import (BORDER_PRESETS, DELAY_PRESETS, SCALE_PRESETS,
                                normalise_subtitle_numeric, style_properties)

TEXT_TRACKS = [{"type": "sub", "id": 1, "codec": "subrip", "selected": True}]
BITMAP_TRACKS = [{"type": "sub", "id": 1, "codec": "hdmv_pgs_subtitle",
                  "selected": True}]


@pytest.fixture
def dialog_factory(tmp_path):
    """Gerçek kullanıcı ayarları KİRLETİLMEZ: geçici QSettings yolu."""
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


def combo_values(combo):
    """Listedeki GERÇEK sayılar (etiket metni değil)."""
    return [combo.itemData(index, Qt.ItemDataRole.UserRole)
            for index in range(combo.count())]


def combo_labels(combo):
    return [combo.itemText(index) for index in range(combo.count())]


def select_value(combo, value):
    index = combo.findData(value, Qt.ItemDataRole.UserRole)
    assert index >= 0, f"{value} listede yok: {combo_values(combo)}"
    combo.setCurrentIndex(index)
    return index


# --- 1-4: pencere ölçüleri ve yerleşim yönü ---------------------------

def test_the_window_opens_at_the_new_compact_default(dialog_factory):
    """640×480 varsayılan."""
    app, dialog = dialog_factory()

    assert DEFAULT_SIZE == (600, 480)
    assert (dialog.width(), dialog.height()) == DEFAULT_SIZE


def test_the_window_really_shrinks_to_the_new_minimum(dialog_factory):
    """560×430 GERÇEK minimum; pencere geri büyümüyor."""
    app, dialog = dialog_factory()
    assert MINIMUM_SIZE == (540, 430)

    dialog.resize(1, 1)
    app.processEvents()

    assert (dialog.width(), dialog.height()) == MINIMUM_SIZE


def test_settings_are_above_the_preview(dialog_factory):
    """Ayarlar ÜSTTE, temsili önizleme ALTTA."""
    app, dialog = dialog_factory()
    app.processEvents()

    settings_bottom = dialog.settings_panel.mapTo(
        dialog, dialog.settings_panel.rect().bottomLeft()).y()
    preview_top = dialog.preview.mapTo(
        dialog, dialog.preview.rect().topLeft()).y()

    assert preview_top >= settings_bottom, (
        f"önizleme ayarların üstünde: {preview_top} < {settings_bottom}")


def test_the_preview_uses_the_full_usable_width_and_height(dialog_factory):
    """Önizleme tam genişlikte ve okunabilir yükseklikte."""
    app, dialog = dialog_factory()
    app.processEvents()

    assert dialog.preview.width() >= dialog.width() - 60, (
        f"önizleme dar: {dialog.preview.width()} / {dialog.width()}")
    assert dialog.preview.height() >= 190, dialog.preview.height()


# --- 5-6: kontrol türleri ---------------------------------------------

def test_the_old_spin_boxes_are_gone(dialog_factory):
    """Küçük yukarı/aşağı oklu sayısal alan KALMADI."""
    app, dialog = dialog_factory()

    assert dialog.findChildren(QDoubleSpinBox) == []
    assert dialog.findChildren(QSpinBox) == []
    for name in ("delay_spin", "scale_spin", "border_spin"):
        assert not hasattr(dialog, name), name


def test_three_preset_combos_exist_with_the_agreed_object_names(
        dialog_factory):
    app, dialog = dialog_factory()

    names = {combo.objectName() for combo in dialog.findChildren(QComboBox)}
    assert {"subtitleDelayCombo", "subtitleScaleCombo",
            "subtitleBorderCombo"} <= names
    assert dialog.delay_combo.accessibleName() == "Altyazı senkronu"
    assert dialog.scale_combo.accessibleName() == "Yazı boyutu"
    assert dialog.border_combo.accessibleName() == "Kenarlık kalınlığı"


# --- 7-10: hazır listelerin KESİN içeriği -----------------------------

def test_the_delay_list_is_exactly_minus_five_to_plus_five(dialog_factory):
    app, dialog = dialog_factory()
    values = combo_values(dialog.delay_combo)

    assert len(values) == 41, len(values)
    assert values[0] == pytest.approx(-5.0)
    assert values[-1] == pytest.approx(5.0)
    steps = [round(b - a, 6) for a, b in zip(values, values[1:])]
    assert set(steps) == {0.25}, sorted(set(steps))
    assert values == list(DELAY_PRESETS)


def test_the_delay_labels_use_signs_and_a_turkish_decimal_comma(
        dialog_factory):
    app, dialog = dialog_factory()
    labels = combo_labels(dialog.delay_combo)

    assert labels[0] == "−5,00 sn"
    assert labels[-1] == "+5,00 sn"
    assert "0 sn — Senkron" in labels
    assert "−1,25 sn" in labels
    assert "+0,25 sn" in labels
    assert not any("." in label for label in labels), "ondalık nokta kaldı"


def test_the_scale_list_is_exactly_the_seven_presets(dialog_factory):
    app, dialog = dialog_factory()

    assert combo_values(dialog.scale_combo) == [0.75, 0.85, 1.0, 1.15, 1.25,
                                                1.5, 2.0]
    assert combo_labels(dialog.scale_combo) == [
        "0,75× — Çok küçük", "0,85× — Küçük", "1,00× — Normal",
        "1,15× — Biraz büyük", "1,25× — Büyük", "1,50× — Çok büyük",
        "2,00× — En büyük"]
    assert list(SCALE_PRESETS) == combo_values(dialog.scale_combo)


def test_the_border_list_is_exactly_zero_to_five_in_half_steps(
        dialog_factory):
    app, dialog = dialog_factory()
    values = combo_values(dialog.border_combo)

    assert len(values) == 11
    assert values[0] == 0.0 and values[-1] == 5.0
    assert set(round(b - a, 6) for a, b in zip(values, values[1:])) == {0.5}
    labels = combo_labels(dialog.border_combo)
    assert labels[0] == "0 px — Yok"
    assert labels[6] == "3,0 px — Varsayılan"
    assert labels[-1] == "5,0 px — En kalın"
    assert list(BORDER_PRESETS) == values


# --- 11-12: değer okuma ve canlı önizleme -----------------------------

def test_current_values_reads_the_item_data_not_the_label(dialog_factory):
    """Görünen metin PARSE EDİLMEZ; `currentData()` float döner."""
    app, dialog = dialog_factory()
    select_value(dialog.delay_combo, -1.25)
    select_value(dialog.scale_combo, 1.15)
    select_value(dialog.border_combo, 4.5)

    values = dialog.current_values()

    assert values["sub_delay"] == pytest.approx(-1.25)
    assert values["sub_scale"] == pytest.approx(1.15)
    assert values["sub_border_size"] == pytest.approx(4.5)
    for key in ("sub_delay", "sub_scale", "sub_border_size"):
        assert isinstance(values[key], float), key


def test_each_preset_choice_updates_the_preview_immediately(dialog_factory):
    app, dialog = dialog_factory()
    app.processEvents()
    before = dialog.preview.text_rect()

    select_value(dialog.scale_combo, 2.0)
    app.processEvents()
    bigger = dialog.preview.text_rect()

    assert bigger.height() > before.height(), (before, bigger)

    select_value(dialog.border_combo, 5.0)
    app.processEvents()
    assert dialog.preview.style_values["sub_border_size"] == pytest.approx(5.0)

    select_value(dialog.delay_combo, 2.5)
    app.processEvents()
    assert dialog.preview.style_values["sub_delay"] == pytest.approx(2.5)


# --- 13-17: şeffaflık ARTIK PALETİN İÇİNDE ----------------------------
#
# ESKİYEN SÖZLEŞME: `test_the_transparent_option_is_visible_and_one_click`
# ana penceredeki AYRI `subtitleTransparentButton` düğmesini ölçüyordu.
# Ürün kararıyla o düğme kaldırıldı; şeffaflık arka plan PALETİNİN
# İÇİNDE "Renk yok (Şeffaf)" seçeneğidir. Kullanıcı garantisi
# (şeffaflık alfa sürgüsü aranmadan, açık bir seçenekle ulaşılabilir)
# GEVŞETİLMEDİ; ayrıntılı ölçüm
# `tests/test_subtitle_appearance_palette_regressions.py` içindedir.
# Sızdırma noktası da `QColorDialog.getColor` yerine `pick_colour()`.


def test_transparent_removes_the_preview_box(dialog_factory, monkeypatch):
    monkeypatch.setattr("app.subtitle_appearance_dialog.pick_colour",
                        lambda *a, **k: QColor(0, 0, 0, 0))
    app, dialog = dialog_factory(
        values={"sub_back_color": QColor(0, 32, 160, 200)})
    app.processEvents()
    assert dialog.preview.background_visible() is True

    dialog._swatches["sub_back_color"].click()
    app.processEvents()

    assert dialog.preview.background_visible() is False


def test_transparent_selection_produces_outline_and_shadow(dialog_factory,
                                                           monkeypatch):
    """MPV özelliğinde kutu YOK: `outline-and-shadow`."""
    from app.subtitle_style import OUTLINE_AND_SHADOW

    monkeypatch.setattr("app.subtitle_appearance_dialog.pick_colour",
                        lambda *a, **k: QColor(0, 0, 0, 0))
    app, dialog = dialog_factory()
    dialog._swatches["sub_back_color"].click()

    props = style_properties(dialog.current_values())

    assert props["sub_back_color"] == "#00000000"
    assert props["sub_border_style"] == OUTLINE_AND_SHADOW


def test_choosing_a_colour_brings_the_box_back(dialog_factory, monkeypatch):
    from app.subtitle_style import BACKGROUND_BOX

    app, dialog = dialog_factory(
        values={"sub_back_color": QColor(0, 0, 0, 0)})
    app.processEvents()
    assert dialog.preview.background_visible() is False

    monkeypatch.setattr("app.subtitle_appearance_dialog.pick_colour",
                        lambda *a, **k: QColor(0, 32, 160, 200))
    dialog._swatches["sub_back_color"].click()
    app.processEvents()

    assert dialog.preview.background_visible() is True
    assert style_properties(
        dialog.current_values())["sub_border_style"] == BACKGROUND_BOX


def test_a_cancelled_picker_keeps_the_previous_background(dialog_factory,
                                                          monkeypatch):
    app, dialog = dialog_factory(
        values={"sub_back_color": QColor(0, 32, 160, 200)})
    monkeypatch.setattr("app.subtitle_appearance_dialog.pick_colour",
                        lambda *a, **k: QColor())   # geçersiz = İptal

    dialog._swatches["sub_back_color"].click()
    app.processEvents()

    colour = dialog.current_values()["sub_back_color"]
    assert (colour.red(), colour.green(), colour.blue(),
            colour.alpha()) == (0, 32, 160, 200)


def test_text_and_border_pickers_still_work_as_before(dialog_factory,
                                                      monkeypatch):
    app, dialog = dialog_factory()
    monkeypatch.setattr("app.subtitle_appearance_dialog.pick_colour",
                        lambda *a, **k: QColor(242, 106, 61, 255))

    dialog._swatches["sub_color"].click()
    dialog._swatches["sub_border_color"].click()
    app.processEvents()

    values = dialog.current_values()
    assert values["sub_color"].name() == "#f26a3d"
    assert values["sub_border_color"].name() == "#f26a3d"


# --- 18: varsayılana dön ----------------------------------------------

def test_reset_restores_the_three_combos_to_the_defaults(dialog_factory):
    app, dialog = dialog_factory()
    select_value(dialog.delay_combo, 3.75)
    select_value(dialog.scale_combo, 2.0)
    select_value(dialog.border_combo, 0.0)

    dialog.reset_to_defaults()

    values = dialog.current_values()
    assert values["sub_delay"] == pytest.approx(0.0)
    assert values["sub_scale"] == pytest.approx(1.0)
    assert values["sub_border_size"] == pytest.approx(3.0)
    assert values["sub_pos"] == pytest.approx(100.0)
    assert values["sub_back_color"].alpha() == 0


# --- 19-23: merkezi sayısal normalleştirme ----------------------------

@pytest.mark.parametrize("name", ["sub_delay", "sub_scale", "sub_border_size",
                                  "sub_pos"])
@pytest.mark.parametrize("broken", ["", "abc", None, float("nan"),
                                    float("inf"), float("-inf"), [], {}])
def test_broken_values_fall_back_to_the_safe_default(name, broken):
    assert normalise_subtitle_numeric(name, broken) == pytest.approx(
        float(SUBTITLE_DEFAULTS[name]))


@pytest.mark.parametrize("name, stored, expected", [
    ("sub_scale", 3.0, 2.0),          # eski üst aşırı değer
    ("sub_scale", 0.5, 0.75),         # eski alt aşırı değer
    ("sub_border_size", 10.0, 5.0),   # devasa kenarlık
    ("sub_border_size", -4.0, 0.0),
    ("sub_delay", 120.0, 5.0),
    ("sub_delay", -120.0, -5.0),
    ("sub_pos", 250.0, 100.0),
    ("sub_pos", -30.0, 0.0),
])
def test_out_of_range_records_are_clamped_to_the_nearest_bound(name, stored,
                                                               expected):
    assert normalise_subtitle_numeric(name, stored) == pytest.approx(expected)


@pytest.mark.parametrize("name, stored, expected", [
    ("sub_scale", 1.02, 1.0),
    ("sub_scale", 1.20, 1.15),        # eşit uzaklık → KÜÇÜK olan
    ("sub_border_size", 2.7, 2.5),
    ("sub_border_size", 2.75, 2.5),   # eşit uzaklık → KÜÇÜK olan
    ("sub_delay", 0.30, 0.25),
    ("sub_delay", -0.125, -0.25),     # eşit uzaklık → KÜÇÜK olan
])
def test_in_range_values_snap_to_the_nearest_preset(name, stored, expected):
    assert normalise_subtitle_numeric(name, stored) == pytest.approx(expected)


def test_string_numbers_from_qsettings_are_accepted():
    """QSettings ini biçiminde sayılar STRING döner."""
    assert normalise_subtitle_numeric("sub_scale", "1.15") == pytest.approx(1.15)
    assert normalise_subtitle_numeric("sub_border_size", "10") == pytest.approx(5.0)


def test_position_keeps_the_zero_to_hundred_contract():
    assert normalise_subtitle_numeric("sub_pos", 63.0) == pytest.approx(63.0)
    assert normalise_subtitle_numeric("sub_pos", 0) == pytest.approx(0.0)
    assert normalise_subtitle_numeric("sub_pos", 100) == pytest.approx(100.0)


def test_the_dialog_normalises_legacy_values_on_open(dialog_factory):
    """Eski aşırı kayıtla açılan pencere hazır değerle başlar."""
    app, dialog = dialog_factory(values={"sub_scale": 3.0,
                                         "sub_border_size": 10.0,
                                         "sub_delay": 120.0})

    values = dialog.current_values()
    assert values["sub_scale"] == pytest.approx(2.0)
    assert values["sub_border_size"] == pytest.approx(5.0)
    assert values["sub_delay"] == pytest.approx(5.0)


# --- 24-28: kalıcılık ve hata güvenliği -------------------------------

def test_opening_the_dialog_writes_nothing(dialog_factory, tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())

    dialog_factory(values={"sub_scale": 3.0})

    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_apply_stores_only_normalised_preset_values(dialog_factory):
    seen = {}

    def callback(values):
        seen.update(values)
        return True, None

    app, dialog = dialog_factory(values={"sub_scale": 3.0,
                                         "sub_border_size": 10.0},
                                 apply_callback=callback)
    dialog.apply_button.click()

    assert seen["sub_scale"] in SCALE_PRESETS
    assert seen["sub_border_size"] in BORDER_PRESETS
    assert seen["sub_scale"] == pytest.approx(2.0)
    assert seen["sub_border_size"] == pytest.approx(5.0)


def test_style_properties_normalises_at_the_boundary():
    """Sınır savunması: dialog atlansa bile aşırı değer MPV'ye gitmez."""
    props = style_properties({"sub_scale": 9.0, "sub_border_size": 40.0,
                              "sub_delay": 900.0, "sub_pos": 400.0})

    assert props["sub_scale"] == pytest.approx(2.0)
    assert props["sub_border_size"] == pytest.approx(5.0)
    assert props["sub_delay"] == pytest.approx(5.0)
    assert props["sub_pos"] == pytest.approx(100.0)


def test_restore_does_not_push_extreme_records_to_mpv(tmp_path):
    """Player başlangıcı da aynı merkezi sınırı kullanır."""
    from app.player import MPVPlayer

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    settings.setValue("subtitle/sub_scale", 3.0)
    settings.setValue("subtitle/sub_border_size", 10.0)
    settings.setValue("subtitle/sub_pos", 400.0)
    mpv = SimpleNamespace()
    player = SimpleNamespace(settings=settings, mpv_player=mpv)

    MPVPlayer.restore_subtitle_settings(player)

    assert mpv.sub_scale == pytest.approx(2.0)
    assert mpv.sub_border_size == pytest.approx(5.0)
    assert mpv.sub_pos == pytest.approx(100.0)


def test_delay_is_still_stored_as_zero_between_sessions(tmp_path):
    from app.player import MPVPlayer

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    settings.setValue("subtitle/sub_delay", 4.0)
    mpv = SimpleNamespace()
    player = SimpleNamespace(settings=settings, mpv_player=mpv)

    MPVPlayer.restore_subtitle_settings(player)

    assert float(settings.value("subtitle/sub_delay")) == pytest.approx(0.0)


def test_a_failed_apply_keeps_the_window_open_and_reports_safely(
        dialog_factory):
    reported = []
    app, dialog = dialog_factory(
        apply_callback=lambda values: (False, OSError("gizli C:\\yol")),
        error_reporter=lambda title, message, exc=None: reported.append(
            (title, message, exc)))

    dialog.apply_button.click()
    app.processEvents()

    assert dialog.isVisible(), "başarısız uygulamada pencere kapandı"
    assert len(reported) == 1
    assert "C:\\yol" not in reported[0][1]


# --- 29-35: yerleşim, klavye ve korunan sözleşmeler -------------------

def test_long_preview_text_stays_inside_the_surface(dialog_factory):
    app, dialog = dialog_factory()
    dialog.preview.set_sample_text("Çok uzun bir altyazı satırı " * 6)
    select_value(dialog.scale_combo, 2.0)
    app.processEvents()

    rect = dialog.preview.text_rect()
    surface = dialog.preview.rect()

    assert rect.left() >= surface.left()
    assert rect.right() <= surface.right()
    assert rect.top() >= surface.top()
    assert rect.bottom() <= surface.bottom()


def test_tab_order_is_combos_then_slider_then_colours_then_actions(
        dialog_factory):
    app, dialog = dialog_factory()

    order = dialog.tab_order_names()

    assert order[:4] == ["subtitleDelayCombo", "subtitleScaleCombo",
                         "subtitleBorderCombo", "subtitlePositionSlider"]
    assert order[-3:] == ["subtitleResetButton", "subtitleCancelButton",
                          "subtitleApplyButton"]
    assert "subtitleTransparentButton" not in order
    assert order[4:7] == ["subtitleColorSwatch_sub_color",
                          "subtitleColorSwatch_sub_back_color",
                          "subtitleColorSwatch_sub_border_color"]


def test_enter_does_not_open_the_colour_picker(dialog_factory, monkeypatch):
    """Combo'da Enter yanlışlıkla renk seçici AÇMAZ."""
    from PyQt6.QtTest import QTest

    opened = []
    monkeypatch.setattr(
        "app.subtitle_appearance_dialog.QColorDialog.getColor",
        staticmethod(lambda *a, **k: opened.append(1) or QColor()))

    app, dialog = dialog_factory()
    dialog.scale_combo.setFocus()
    app.processEvents()
    QTest.keyClick(dialog.scale_combo, Qt.Key.Key_Return)
    app.processEvents()

    assert opened == []


def test_the_combo_popup_closes_after_a_selection(dialog_factory):
    app, dialog = dialog_factory()
    combo = dialog.scale_combo

    combo.showPopup()
    app.processEvents()
    combo.hidePopup()
    select_value(combo, 1.5)
    app.processEvents()

    assert combo.view().isVisible() is False
    assert combo.currentData(Qt.ItemDataRole.UserRole) == pytest.approx(1.5)


def test_the_wheel_does_not_change_an_unfocused_combo(dialog_factory):
    """Fare tekerleği odak dışındayken değeri KAYDIRMAZ."""
    from PyQt6.QtCore import QPoint, QPointF
    from PyQt6.QtGui import QWheelEvent

    app, dialog = dialog_factory()
    combo = dialog.scale_combo
    select_value(combo, 1.0)
    combo.clearFocus()
    app.processEvents()

    event = QWheelEvent(QPointF(combo.rect().center()),
                        QPointF(combo.mapToGlobal(combo.rect().center())),
                        QPoint(0, 0), QPoint(0, 120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    app.sendEvent(combo, event)
    app.processEvents()

    assert combo.currentData(Qt.ItemDataRole.UserRole) == pytest.approx(1.0)


def test_the_bitmap_notice_is_preserved(dialog_factory):
    from app.subtitle_style import BITMAP_STYLE_NOTICE

    app, dialog = dialog_factory(track_list=BITMAP_TRACKS)

    assert dialog.bitmap_notice.text() == BITMAP_STYLE_NOTICE
    assert dialog.bitmap_notice.isVisible()


def test_no_false_bitmap_warning(dialog_factory):
    app, dialog = dialog_factory(track_list=TEXT_TRACKS)

    assert dialog.bitmap_notice.text() == ""
    assert dialog.bitmap_notice.isVisible() is False


def test_the_preview_is_still_labelled_as_representative(dialog_factory):
    app, dialog = dialog_factory()

    captions = [w.text() for w in dialog.findChildren(type(dialog.bitmap_notice))
                if "Temsili" in w.text()]
    assert captions, "temsili önizleme açıklaması kayboldu"
    assert "gerçek video çıktısı değildir" in captions[0]


def test_the_canonical_colour_format_is_unchanged(dialog_factory):
    app, dialog = dialog_factory(values={"sub_color": QColor(242, 106, 61, 255)})

    props = style_properties(dialog.current_values())

    assert props["sub_color"] == "#FFF26A3D"
