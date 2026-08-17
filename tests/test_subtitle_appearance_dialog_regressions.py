# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Ayarları penceresinin KOMPAKT tasarımı ve davranış güvenliği.

Eski tasarım: `menu_actions.show_subtitle_settings()` içinde tek sütunlu
`QFormLayout`; her kısa ayar ayrı uzun satır, renkler "Renk seç" yazan
geniş düğmeler, canlı önizleme YOK.

Hedef (2 numaralı tasarım): solda ~310-330 px kompakt ayar alanı, sağda
~480-520 px canlı önizleme, yaklaşık %38/%62 oran.

GÜNCELLEME — DİKEY TASARIM: pencere 640×480'e küçüldü; ayarlar ÜSTTE,
önizleme ALTTA. Yatay sütun oranı ölçen testler ürün kararıyla ESKİDİ ve
dikey karşılıklarıyla değiştirildi (ayrıntılı yeni sözleşme:
tests/test_subtitle_appearance_compact_regressions.py). Renk, alfa,
önizleme, atomic_apply ve rollback testleri GEVŞETİLMEDİ; yalnız kontrol
adları hazır değer listelerinin adlarıyla güncellendi.

Kalıcılık sözleşmesi `app/subtitle_style.py` içindedir ve bu turda
DEĞİŞMEZ; dialog yalnız `atomic_apply()` çağıran ince bir yüzeydir.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QSettings, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                             QFormLayout, QPushButton, QSlider, QWidget)

from app.config import SUBTITLE_DEFAULTS
from app.subtitle_style import BITMAP_STYLE_NOTICE, qcolor_to_mpv_argb
from app.subtitle_appearance_dialog import (DEFAULT_SIZE, MINIMUM_SIZE,
                                            SubtitleAppearanceDialog)

TEXT_TRACKS = [{"type": "sub", "id": 1, "codec": "subrip", "selected": True}]
BITMAP_TRACKS = [{"type": "sub", "id": 1, "codec": "hdmv_pgs_subtitle",
                  "selected": True}]


@pytest.fixture
def dialog_factory(tmp_path):
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


def child(dialog, name):
    found = dialog.findChild(QWidget, name)
    assert found is not None, f"{name} bulunamadi"
    return found


def swatch(dialog, key):
    return child(dialog, f"subtitleColorSwatch_{key}")


class SpyApply:
    def __init__(self, ok=True, error=None):
        self.ok = ok
        self.error = error
        self.calls = []

    def __call__(self, values):
        self.calls.append(dict(values))
        return self.ok, self.error


# --- 1-3. Yerlesim olculeri ---

# ESKIYEN TESTLER (yatay tasarim): `test_settings_column_stays_compact`,
# `test_preview_column_is_large_enough_to_be_readable` ve
# `test_preview_is_clearly_wider_than_the_settings_column`. Ucu de SOL/SAG
# sutun genislik oranini olcuyordu; dikey tasarimda sutun yoktur. Ayni
# kullanici sozlesmesi (ayar alani kompakt, onizleme genis ve okunabilir)
# asagida dikey bicimde ve DAHA SIKI olculur.

def test_settings_block_stays_compact_above_the_preview(dialog_factory):
    """Ayar blogu pencerenin UST kisminda kompakt kalir."""
    app, dialog = dialog_factory()

    settings = child(dialog, "subtitleAppearanceSettings")
    preview = child(dialog, "subtitleAppearancePreview")
    assert settings.height() <= dialog.height() * 0.45, settings.height()
    settings_bottom = settings.mapTo(dialog,
                                     QPoint(0, settings.height())).y()
    assert preview.mapTo(dialog, QPoint(0, 0)).y() >= settings_bottom


def test_preview_is_large_enough_to_be_readable(dialog_factory):
    app, dialog = dialog_factory()

    preview = child(dialog, "subtitleAppearancePreview")
    assert preview.width() >= dialog.width() - 60, preview.width()
    assert preview.height() >= 190, preview.height()


def test_default_window_is_compact(dialog_factory):
    app, dialog = dialog_factory()

    assert (dialog.width(), dialog.height()) == DEFAULT_SIZE == (600, 480)
    assert MINIMUM_SIZE == (540, 430)


# --- 4-5. Kompakt gruplar, eski form duzeni geri gelmiyor ---

def test_short_settings_share_one_compact_row(dialog_factory):
    app, dialog = dialog_factory()

    row = child(dialog, "subtitleQuickRow")
    for name in ("subtitleDelayCombo", "subtitleScaleCombo",
                 "subtitleBorderCombo"):
        widget = child(dialog, name)
        assert widget.parent() is row or row.isAncestorOf(widget), (
            f"{name} kompakt satirda degil")
    tops = {child(dialog, n).mapTo(row, QPoint(0, 0)).y()
            for n in ("subtitleDelayCombo", "subtitleScaleCombo",
                      "subtitleBorderCombo")}
    assert len(tops) == 1, "kisa ayarlar ayri satirlara yayilmis"


def test_the_old_single_column_form_layout_is_gone(dialog_factory):
    app, dialog = dialog_factory()

    forms = dialog.findChildren(QFormLayout)
    assert not forms, "eski QFormLayout duzeni geri gelmis"


def test_colour_controls_are_swatches_not_wide_buttons(dialog_factory):
    app, dialog = dialog_factory()

    # NOT: ust sinir 96 -> 120. Uc kutuya ORTAK genislik verildi
    # ("Arka plan" etiketi 108 px olcuoldugu icin kutular esitsiz
    # goruunuyordu); kural yine "genis metin dugmesi degil, kompakt
    # kutu"dur ve kutular birbirine esittir.
    widths = set()
    for key in ("sub_color", "sub_back_color", "sub_border_color"):
        button = swatch(dialog, key)
        assert button.width() <= 120, f"{key} swatch'i {button.width()}px"
        assert "Renk seç" not in button.text()
        widths.add(button.width())
    assert len(widths) == 1, f"kutular esit degil: {widths}"


def test_position_row_shows_a_slider_and_its_percentage(dialog_factory):
    app, dialog = dialog_factory()

    slider = child(dialog, "subtitlePositionSlider")
    label = child(dialog, "subtitlePositionValue")
    assert isinstance(slider, QSlider)
    slider.setValue(64)
    app.processEvents()
    assert "64" in label.text()


# --- 6. Renk kontrolleri ---

def test_each_swatch_shows_the_canonical_value_in_its_tooltip(dialog_factory):
    app, dialog = dialog_factory(values={
        "sub_color": QColor(242, 106, 61, 255),
        "sub_back_color": QColor(0, 0, 0, 128),
        "sub_border_color": QColor(0, 0, 0, 255)})

    assert "#FFF26A3D" in swatch(dialog, "sub_color").toolTip()
    assert "#80000000" in swatch(dialog, "sub_back_color").toolTip()
    assert "#FF000000" in swatch(dialog, "sub_border_color").toolTip()


def test_colour_picker_is_opened_with_the_alpha_channel(dialog_factory,
                                                        monkeypatch):
    """Alfa sürgüsü HÂLÂ görünür.

    ESKİ SEAM: `QColorDialog.getColor(...)` statik çağrısı ve `options`
    bayrağı. Palete "Renk yok (Şeffaf)" eylemi eklenebilmesi için ürün
    artık `SubtitleColourDialog` ÖRNEĞİ kuruyor; sızdırma noktası
    modül düzeyindeki `pick_colour()` fonksiyonudur. Alfa kanalı
    sözleşmesi gevşetilmedi, pencerenin kendi seçeneğinden ölçülür.
    """
    from PyQt6.QtWidgets import QColorDialog

    from app.subtitle_appearance_dialog import SubtitleColourDialog

    app, dialog = dialog_factory()
    picker = SubtitleColourDialog(QColor(1, 2, 3, 4), dialog)
    try:
        assert picker.testOption(
            QColorDialog.ColorDialogOption.ShowAlphaChannel)
    finally:
        picker.deleteLater()

    monkeypatch.setattr("app.subtitle_appearance_dialog.pick_colour",
                        lambda *a, **k: QColor(1, 2, 3, 4))
    swatch(dialog, "sub_color").click()
    app.processEvents()

    assert qcolor_to_mpv_argb(dialog.current_values()["sub_color"]) == "#04010203"


def test_a_cancelled_colour_picker_keeps_the_previous_colour(dialog_factory,
                                                             monkeypatch):
    app, dialog = dialog_factory(values={"sub_color": QColor(242, 106, 61,
                                                             255)})
    monkeypatch.setattr("app.subtitle_appearance_dialog.pick_colour",
                        lambda *a, **k: QColor())

    swatch(dialog, "sub_color").click()
    app.processEvents()

    assert qcolor_to_mpv_argb(dialog.current_values()["sub_color"]) == "#FFF26A3D"


def test_swatches_expose_the_alpha_state(dialog_factory):
    app, dialog = dialog_factory(values={
        "sub_back_color": QColor(0, 0, 0, 0)})

    button = swatch(dialog, "sub_back_color")
    assert button.property("hasAlpha") is True
    assert "saydam" in button.toolTip().lower()


# --- 7-8. Onizleme canli, ama kalicilik yok ---

def test_every_control_updates_the_preview(dialog_factory):
    app, dialog = dialog_factory()
    preview = child(dialog, "subtitlePreviewSurface")

    # NOT: kenarlik artik 5 px ile sinirlidir (eski 6.0 urun kararyla
    # gecersiz); ayni sozlesme gecerli hazir degerle olculur.
    dialog.scale_combo.select_value(2.0)
    dialog.border_combo.select_value(5.0)
    child(dialog, "subtitlePositionSlider").setValue(40)
    dialog.set_color("sub_color", QColor(242, 106, 61, 255))
    dialog.set_color("sub_back_color", QColor(0, 0, 0, 200))
    dialog.set_color("sub_border_color", QColor(255, 0, 0, 255))
    app.processEvents()

    style = preview.style_values
    assert style["sub_scale"] == 2.0
    assert style["sub_border_size"] == 5.0
    assert style["sub_pos"] == 40.0
    assert qcolor_to_mpv_argb(style["sub_color"]) == "#FFF26A3D"
    assert qcolor_to_mpv_argb(style["sub_back_color"]) == "#C8000000"
    assert qcolor_to_mpv_argb(style["sub_border_color"]) == "#FFFF0000"


def test_the_preview_never_touches_mpv_or_settings(dialog_factory):
    spy = SpyApply()
    app, dialog = dialog_factory(apply_callback=spy)

    dialog.scale_combo.select_value(1.15)
    dialog.set_color("sub_back_color", QColor(0, 0, 0, 255))
    app.processEvents()

    assert spy.calls == [], "onizleme kalici yazma tetikledi"
    for name in vars(dialog):
        assert "mpv" not in name.lower(), "dialog MPV referansi tutuyor"
        assert "settings" not in name.lower() or name.endswith("_panel"), (
            "dialog QSettings referansi tutuyor")


def test_opening_the_dialog_writes_nothing(dialog_factory):
    spy = SpyApply()
    app, dialog = dialog_factory(apply_callback=spy)

    assert spy.calls == []


def test_transparent_background_hides_the_preview_box(dialog_factory):
    app, dialog = dialog_factory()
    preview = child(dialog, "subtitlePreviewSurface")

    dialog.set_color("sub_back_color", QColor(0, 0, 0, 0))
    app.processEvents()
    assert preview.background_visible() is False

    dialog.set_color("sub_back_color", QColor(0, 0, 0, 180))
    app.processEvents()
    assert preview.background_visible() is True


def test_preview_text_stays_inside_the_surface(dialog_factory):
    app, dialog = dialog_factory()
    preview = child(dialog, "subtitlePreviewSurface")

    preview.set_sample_text("Bu çok uzun bir altyazı satırıdır " * 6)
    dialog.scale_combo.select_value(2.0)   # ust hazir deger
    app.processEvents()

    rect = preview.text_rect()
    assert preview.rect().contains(rect), (
        f"onizleme metni tasti: text={rect.getRect()} "
        f"surface={preview.rect().getRect()}")


def test_preview_is_labelled_as_a_preview(dialog_factory):
    app, dialog = dialog_factory()

    label = child(dialog, "subtitlePreviewCaption")
    assert "önizleme" in label.text().lower()


# --- 9-12. Davranis sozlesmesi ---

def test_reset_only_changes_the_dialog_state(dialog_factory):
    spy = SpyApply()
    app, dialog = dialog_factory(apply_callback=spy, values={
        "sub_scale": 2.5, "sub_color": QColor(1, 2, 3, 4)})

    child(dialog, "subtitleResetButton").click()
    app.processEvents()

    assert spy.calls == [], "reset kalici yazma yapti"
    values = dialog.current_values()
    assert values["sub_scale"] == float(SUBTITLE_DEFAULTS["sub_scale"])
    assert qcolor_to_mpv_argb(values["sub_color"]) == \
        SUBTITLE_DEFAULTS["sub_color"]


@pytest.mark.parametrize("action", ["cancel", "escape", "close"])
def test_cancel_escape_and_close_leave_no_mutation(dialog_factory, action):
    spy = SpyApply()
    app, dialog = dialog_factory(apply_callback=spy)
    dialog.scale_combo.select_value(2.0)

    if action == "cancel":
        child(dialog, "subtitleCancelButton").click()
    elif action == "escape":
        dialog.reject()
    else:
        dialog.close()
    app.processEvents()

    assert spy.calls == []
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_apply_uses_the_injected_atomic_callback_once(dialog_factory):
    spy = SpyApply()
    app, dialog = dialog_factory(apply_callback=spy)
    dialog.scale_combo.select_value(1.5)

    child(dialog, "subtitleApplyButton").click()
    app.processEvents()

    assert len(spy.calls) == 1
    assert spy.calls[0]["sub_scale"] == 1.5
    assert set(spy.calls[0]) == {"sub_delay", "sub_scale", "sub_pos",
                                 "sub_border_size", "sub_color",
                                 "sub_back_color", "sub_border_color"}


def test_a_successful_apply_closes_the_dialog(dialog_factory):
    app, dialog = dialog_factory(apply_callback=SpyApply(ok=True))

    child(dialog, "subtitleApplyButton").click()
    app.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted


def test_a_failed_apply_keeps_the_dialog_open_and_reports_safely(
        dialog_factory):
    reports = []
    spy = SpyApply(ok=False, error=RuntimeError(r"C:\Users\gizli\ayar.ini"))
    app, dialog = dialog_factory(
        apply_callback=spy,
        error_reporter=lambda title, message, exc=None: reports.append(
            (title, message)))

    child(dialog, "subtitleApplyButton").click()
    app.processEvents()

    assert dialog.isVisible(), "basarisiz uygulamada pencere kapandi"
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert len(reports) == 1
    assert "gizli" not in reports[0][1] and ":\\" not in reports[0][1]


# --- 13-14. Bitmap/PGS bilgisi ---

def test_bitmap_track_shows_the_safe_notice(dialog_factory):
    app, dialog = dialog_factory(track_list=BITMAP_TRACKS)

    notice = child(dialog, "subtitleBitmapNotice")
    assert notice.isVisible()
    assert notice.text() == BITMAP_STYLE_NOTICE


@pytest.mark.parametrize("tracks", [TEXT_TRACKS, None, [],
                                    [{"type": "sub", "id": 1}]])
def test_no_false_bitmap_warning(dialog_factory, tracks):
    app, dialog = dialog_factory(track_list=tracks)

    assert not child(dialog, "subtitleBitmapNotice").isVisible()


# --- 18. Erisilebilirlik ---

def test_controls_carry_accessible_names_and_a_sane_tab_order(dialog_factory):
    app, dialog = dialog_factory()

    for name in ("subtitleDelayCombo", "subtitleScaleCombo",
                 "subtitleBorderCombo", "subtitlePositionSlider",
                 "subtitleColorSwatch_sub_color",
                 "subtitleColorSwatch_sub_back_color",
                 "subtitleColorSwatch_sub_border_color",
                 "subtitleResetButton", "subtitleCancelButton",
                 "subtitleApplyButton"):
        widget = child(dialog, name)
        assert widget.accessibleName(), f"{name} accessibleName bos"

    order = dialog.tab_order_names()
    assert order.index("subtitleDelayCombo") < \
        order.index("subtitleScaleCombo")
    assert order.index("subtitleScaleCombo") < \
        order.index("subtitleBorderCombo")
    assert order.index("subtitleBorderCombo") < \
        order.index("subtitlePositionSlider")
    assert order.index("subtitlePositionSlider") < \
        order.index("subtitleColorSwatch_sub_color")
    assert order.index("subtitleColorSwatch_sub_border_color") < \
        order.index("subtitleApplyButton")


def test_buttons_use_the_pointing_hand_cursor(dialog_factory):
    app, dialog = dialog_factory()

    for name in ("subtitleResetButton", "subtitleCancelButton",
                 "subtitleApplyButton", "subtitleColorSwatch_sub_color"):
        assert child(dialog, name).cursor().shape() == \
            Qt.CursorShape.PointingHandCursor


def test_action_buttons_are_turkish_and_positioned_by_role(dialog_factory):
    app, dialog = dialog_factory()

    assert child(dialog, "subtitleResetButton").text() == "Varsayılana Dön"
    assert child(dialog, "subtitleCancelButton").text() == "İptal"
    assert child(dialog, "subtitleApplyButton").text() == "Uygula"
    assert not dialog.findChildren(QDialogButtonBox), (
        "Ingilizce OK/Cancel/Apply veren QDialogButtonBox kullanilmis")
    reset_x = child(dialog, "subtitleResetButton").mapTo(
        dialog, QPoint(0, 0)).x()
    apply_x = child(dialog, "subtitleApplyButton").mapTo(
        dialog, QPoint(0, 0)).x()
    assert reset_x < apply_x


# --- 16. Minimum boyut ---

def test_nothing_is_clipped_at_the_minimum_size(dialog_factory):
    app, dialog = dialog_factory()
    dialog.resize(dialog.minimumSizeHint())
    app.processEvents()

    for name in ("subtitleDelayCombo", "subtitleScaleCombo",
                 "subtitleBorderCombo", "subtitlePositionSlider",
                 "subtitleResetButton", "subtitleCancelButton",
                 "subtitleApplyButton", "subtitlePreviewSurface"):
        widget = child(dialog, name)
        hint = widget.minimumSizeHint()
        assert widget.width() >= hint.width(), f"{name} yatayda kirpildi"
        assert widget.height() >= hint.height(), f"{name} dikeyde kirpildi"
    assert child(dialog, "subtitlePreviewSurface").width() >= 300


# --- 19. Entegrasyon noktasi ince kaldi ---

def test_menu_action_only_wires_the_dialog_to_atomic_apply():
    import inspect

    from app import menu_actions

    source = inspect.getsource(menu_actions.show_subtitle_settings)
    assert "SubtitleAppearanceDialog" in source
    # `atomic_apply` artık ince bir sarmalayıcıdan çağrılır: ASS'te
    # güvenli bant EFEKTİF `sub_pos` gerektirdiği için başarılı yazımdan
    # sonra bant yeniden senkronlanır. Kalıcılık mantığı yine YALNIZ
    # `subtitle_style.atomic_apply()` içindedir.
    wrapper = inspect.getsource(menu_actions._apply_subtitle_style)
    assert "atomic_apply" in wrapper
    assert "sync_subtitle_safe_band" in wrapper
    assert "_apply_subtitle_style" in source
    # Kalicilik mantigi dialog modulunde TEKRAR YAZILMAMALI. Docstring'de
    # gecen kelime degil, GERCEK kullanim olculur.
    import ast

    from app import subtitle_appearance_dialog as dialog_module

    tree = ast.parse(inspect.getsource(dialog_module))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute)}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}

    # NOT: `setValue` burada QSlider/QDoubleSpinBox uzerinde mesru kullanilir;
    # olculen sey KALICI yazma yolunun modulde olmamasidir.
    assert "QSettings" not in names | imported, "dialog QSettings kullaniyor"
    assert "sub_ass_override" not in names | attributes
    assert "atomic_apply" not in imported, (
        "dialog kalicilik cagrisini kendisi kurmamali; callback enjekte edilir")
    assert not hasattr(dialog_module, "QSettings")


def test_enter_in_a_value_control_does_not_open_the_colour_picker(
        dialog_factory):
    """Enter, renk seçiciyi AÇMAMALIDIR.

    ESKI AD: `test_enter_in_a_spin_box_does_not_open_the_colour_picker`.
    Spinbox kaldirildi; kural (hicbir dugme varsayilan/autoDefault
    degildir) aynen surur ve hazir deger listeleri icin de gecerlidir.

    Gerçek MPV kabul koşumunda ölçülen kırmızı kanıt: kullanıcı boyut
    alanına değer yazıp Enter'a bastığında `QColorDialog` açılıyordu.
    Kök neden: renk swatch'ları `QPushButton` ve `autoDefault` KAPALI
    değil; QDialog Enter'ı ilk `autoDefault` düğmeye yönlendiriyor.
    Arayüz donmuyordu, ama yazı rengi seçici izinsiz açılıyordu.
    """
    from app.subtitle_appearance_dialog import ColorSwatch

    app, dialog = dialog_factory()
    swatches = dialog.findChildren(ColorSwatch)
    assert swatches, "renk swatch'lari bulunamadi"
    for swatch in swatches:
        assert not swatch.autoDefault(), (
            f"{swatch.objectName()} autoDefault ACIK: Enter renk secicisini "
            "acar")
        assert not swatch.isDefault()
    # Penceredeki HICBIR dugme varsayilan olmamali; aksi halde Enter
    # beklenmedik bir eylem tetikler.
    assert [button.objectName() for button in dialog.findChildren(QPushButton)
            if button.isDefault() or button.autoDefault()] == []


# --- Saydam arka plandan görünür renk secme -------------------------------

class StubColorPicker:
    """`pick_colour()` yerine gecen olculebilir sahte secici.

    ESKI SEAM: modulun `QColorDialog` sinifi degistiriliyordu. Palete
    "Renk yok (Seffaf)" eylemi eklenebilmesi icin urun artik
    `SubtitleColourDialog` ORNEGI kuruyor ve tek sizdirma noktasi
    `pick_colour(parent, initial, title, allow_transparent)`. Tohum
    olcumu sozlesmesi AYNEN korunur: kullanici picker icinde YALNIZ RGB
    degistirdiginde donen rengin alfasi BASLANGIC renginin alfasidir.
    """

    def __init__(self, rgb=None, alpha=None, cancel=False):
        self.recorded = []
        self.transparent_offered = []
        self._rgb = rgb
        self._alpha = alpha
        self._cancel = cancel

    def __call__(self, parent, initial, title="", allow_transparent=False):
        from PyQt6.QtGui import QColor as _QColor
        self.recorded.append(_QColor(initial))
        self.transparent_offered.append(bool(allow_transparent))
        if self._cancel:
            return _QColor()  # gecersiz = Iptal
        red, green, blue = self._rgb if self._rgb else (0, 32, 160)
        alpha = self._alpha if self._alpha is not None else initial.alpha()
        return _QColor(red, green, blue, alpha)


def click_swatch(app, dialog, key, picker, monkeypatch):
    from PyQt6.QtTest import QTest
    from app import subtitle_appearance_dialog as dialog_module

    monkeypatch.setattr(dialog_module, "pick_colour", picker)
    QTest.mouseClick(dialog._swatches[key], Qt.MouseButton.LeftButton)
    app.processEvents()


def test_transparent_background_seeds_the_picker_with_an_opaque_colour(
        dialog_factory, monkeypatch):
    """Saydam arka planda secici OPAK baslamali; dialog durumu degismemeli.

    Kirmizi kanit: `_choose()` mevcut `#00000000` rengi oldugu gibi
    `QColorDialog.getColor()` baslangicina veriyordu. Kullanici yalniz RGB
    sectiginde alfa 0 kaliyor ve "arka plan uygulanmiyor" goruluyordu.
    """
    app, dialog = dialog_factory(values={"sub_back_color": QColor(0, 0, 0, 0)})
    picker = StubColorPicker(cancel=True)
    click_swatch(app, dialog, "sub_back_color", picker, monkeypatch)

    assert picker.recorded, "renk secici hic acilmadi"
    assert picker.recorded[0].alpha() == 255, (
        "saydam arka planda seciciye alpha=0 tohumu verilirse kullanici "
        "yalniz RGB sectiginde arka plan yine gorunmez kalir")
    # Gecici tohum dialog durumuna SIZMAMALI.
    assert dialog.current_values()["sub_back_color"].alpha() == 0
    assert dialog._colors["sub_back_color"].alpha() == 0


def test_picking_a_colour_from_a_transparent_background_becomes_visible(
        dialog_factory, monkeypatch):
    app, dialog = dialog_factory(values={"sub_back_color": QColor(0, 0, 0, 0)})
    picker = StubColorPicker(rgb=(0, 32, 160))
    click_swatch(app, dialog, "sub_back_color", picker, monkeypatch)

    chosen = dialog.current_values()["sub_back_color"]
    assert chosen.alpha() > 0
    assert (chosen.red(), chosen.green(), chosen.blue()) == (0, 32, 160)
    assert dialog.preview.background_visible() is True


def test_chosen_background_reaches_apply_and_style_properties(
        dialog_factory, monkeypatch):
    from app.subtitle_style import BACKGROUND_BOX, style_properties

    seen = []
    app, dialog = dialog_factory(
        values={"sub_back_color": QColor(0, 0, 0, 0)},
        apply_callback=lambda values: (seen.append(dict(values)), (True, None))[1])
    picker = StubColorPicker(rgb=(0, 32, 160))
    click_swatch(app, dialog, "sub_back_color", picker, monkeypatch)
    dialog.apply_button.click()
    app.processEvents()

    assert len(seen) == 1
    props = style_properties(seen[0])
    assert props["sub_back_color"] == "#FF0020A0"
    assert props["sub_border_style"] == BACKGROUND_BOX


def test_cancelled_picker_keeps_the_transparent_background(dialog_factory,
                                                           monkeypatch):
    app, dialog = dialog_factory(values={"sub_back_color": QColor(0, 0, 0, 0)})
    picker = StubColorPicker(cancel=True)
    click_swatch(app, dialog, "sub_back_color", picker, monkeypatch)

    assert qcolor_to_mpv_argb(
        dialog.current_values()["sub_back_color"]) == "#00000000"
    assert dialog.preview.background_visible() is False


@pytest.mark.parametrize("alpha", [255, 128, 1])
def test_existing_background_alpha_is_preserved_when_opening_the_picker(
        dialog_factory, monkeypatch, alpha):
    """Alfa > 0 ise tohum DEGISTIRILMEZ; kullanici secimi ezilmez."""
    app, dialog = dialog_factory(
        values={"sub_back_color": QColor(10, 20, 30, alpha)})
    picker = StubColorPicker(cancel=True)
    click_swatch(app, dialog, "sub_back_color", picker, monkeypatch)

    seed = picker.recorded[0]
    assert seed.alpha() == alpha
    assert (seed.red(), seed.green(), seed.blue()) == (10, 20, 30)


def test_user_may_deliberately_choose_a_fully_transparent_background(
        dialog_factory, monkeypatch):
    """Tohum opaklastirilir ama SECIM zorla opaklastirilmaz."""
    app, dialog = dialog_factory(values={"sub_back_color": QColor(0, 0, 0, 0)})
    picker = StubColorPicker(rgb=(0, 32, 160), alpha=0)
    click_swatch(app, dialog, "sub_back_color", picker, monkeypatch)

    assert dialog.current_values()["sub_back_color"].alpha() == 0
    assert dialog.preview.background_visible() is False


@pytest.mark.parametrize("key,start", [("sub_color", QColor(255, 255, 255, 0)),
                                       ("sub_border_color", QColor(0, 0, 0, 0))])
def test_text_and_border_swatches_are_not_reseeded(dialog_factory, monkeypatch,
                                                   key, start):
    """Duzeltme YALNIZ `sub_back_color` icindir."""
    app, dialog = dialog_factory(values={key: start})
    picker = StubColorPicker(cancel=True)
    click_swatch(app, dialog, key, picker, monkeypatch)

    assert picker.recorded[0].alpha() == 0
    assert dialog.current_values()[key].alpha() == 0


@pytest.mark.parametrize("minimum", [False, True])
def test_action_buttons_stay_inside_the_window_and_are_hit_testable(
        dialog_factory, minimum):
    """Alt eylem düğmeleri pencere sınırı içinde ve tıklanabilir olmalı.

    `minimumSizeHint` karşılaştırması bunu yakalamaz: düğme tam boyutunda
    olup pencerenin dışına taşabilir. Gerçek Windows penceresinde de
    ölçüldü (`tests/subtitle_appearance_layout_child.py::actions`).
    """
    app, dialog = dialog_factory()
    if minimum:
        dialog.resize(dialog.minimumSizeHint())
        app.processEvents()
    for button in (dialog.reset_button, dialog.cancel_button,
                   dialog.apply_button):
        top_left = button.mapTo(dialog, button.rect().topLeft())
        assert dialog.rect().contains(top_left.x(), top_left.y())
        assert dialog.rect().contains(top_left.x() + button.width() - 1,
                                      top_left.y() + button.height() - 1)
        assert dialog.childAt(
            button.mapTo(dialog, button.rect().center())) is button
