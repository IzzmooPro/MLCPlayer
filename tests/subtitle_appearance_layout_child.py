"""Altyazı Ayarları penceresinin DPI ölçeklerindeki yerleşimini ölçer.

`QT_SCALE_FACTOR` süreç başlamadan okunduğu için ölçüm AYRI child'da
yapılır. Sonuç tek satır JSON. Ekran görüntüsü isteğe bağlıdır
(`--shot <yol>`); Git'e eklenmez.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Çıktı UTF-8'e SABİTLENİR. Yönlendirilmiş stdout Windows'ta cp1254 olur
# ve rapordaki tipografik eksi (U+2212, hazır senkron etiketleri)
# `UnicodeEncodeError` fırlatıp child'ı exit=1 ile düşürüyordu.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
# `MLC_DIALOG_REAL_PLATFORM=1` verildiğinde gerçek Windows platformu
# kullanılır (Türkçe glifler offscreen'de kare çiziliyor).
if os.environ.get("MLC_DIALOG_REAL_PLATFORM") != "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtGui import QColor  # noqa: E402
from PyQt6.QtWidgets import QApplication, QComboBox, QWidget  # noqa: E402

# 1366x768 en dar hedef ekran; pencere bu alana sigmali.
TARGET_SCREEN = (1366, 768)

MEASURED = ("subtitleDelayCombo", "subtitleScaleCombo", "subtitleBorderCombo",
            "subtitlePositionSlider", "subtitlePositionValue",
            "subtitleColorSwatch_sub_color",
            "subtitleColorSwatch_sub_back_color",
            "subtitleColorSwatch_sub_border_color", "subtitleResetButton",
            "subtitleCancelButton", "subtitleApplyButton",
            "subtitlePreviewSurface", "subtitlePreviewCaption")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", required=True)
    parser.add_argument("--shot", default="")
    parser.add_argument("--minimum", action="store_true")
    parser.add_argument("--scenario", default="default")
    args = parser.parse_args()

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      args.settings)
    app = QApplication(sys.argv)

    from app.subtitle_appearance_dialog import SubtitleAppearanceDialog

    values, tracks = {}, [{"type": "sub", "id": 1, "codec": "subrip",
                           "selected": True}]
    if args.scenario == "orange_box":
        values = {"sub_color": QColor(242, 106, 61, 255),
                  "sub_back_color": QColor(0, 0, 0, 140),
                  "sub_border_color": QColor(0, 0, 0, 255)}
    elif args.scenario == "clear_background":
        values = {"sub_back_color": QColor(0, 0, 0, 0)}
    elif args.scenario == "orange_blue_box":
        # Temsili sahne kabulü: turuncu yazi + yari saydam mavi kutu +
        # belirgin kenarlik.
        values = {"sub_color": QColor(242, 106, 61, 255),
                  "sub_back_color": QColor(0, 32, 160, 150),
                  "sub_border_color": QColor(0, 0, 0, 255),
                  "sub_border_size": 5.0}
    elif args.scenario == "large_high":
        # Buyuk yazi + altyazi yuzeyin UST bolgesinde (`sub_pos` kucuk).
        # NOT: 1.8 artik hazir deger degil; en yakin hazir deger 1.5'tir.
        values = {"sub_scale": 1.5, "sub_pos": 25.0,
                  "sub_back_color": QColor(0, 0, 0, 0)}
    elif args.scenario == "large_text":
        # En buyuk hazir yazi + en kalin kenarlik.
        values = {"sub_scale": 2.0, "sub_border_size": 5.0}
    elif args.scenario in ("palette_open", "palette_no_colour"):
        values = {"sub_back_color": QColor(0, 32, 160, 200)}
    elif args.scenario == "bitmap":
        tracks = [{"type": "sub", "id": 1, "codec": "hdmv_pgs_subtitle",
                   "selected": True}]

    failed = args.scenario == "apply_failure"
    dialog = SubtitleAppearanceDialog(
        values=values, track_list=tracks,
        apply_callback=(lambda chosen: (False, OSError("backend")))
        if failed else (lambda chosen: (True, None)),
        error_reporter=lambda *a, **k: None)
    dialog.show()
    app.processEvents()
    if args.minimum:
        # GERÇEK minimum: `resize(1, 1)` Qt'yi ilan edilen minimuma çeker.
        dialog.resize(1, 1)
        app.processEvents()
    if args.scenario in ("long_text", "large_text"):
        dialog.findChild(QWidget, "subtitlePreviewSurface").set_sample_text(
            "Bu çok uzun bir altyazı satırıdır ve önizleme alanından "
            "taşmamalıdır " * 4)
        app.processEvents()
    palette = {}
    if args.scenario in ("palette_open", "palette_no_colour"):
        # GERÇEK kullanıcı akışı: arka plan kutusuna tıklanınca açılan
        # PALETTE "Renk yok (Şeffaf)" seçeneği bulunur.
        from app.subtitle_appearance_dialog import (NO_COLOUR_TEXT,
                                                    SubtitleColourDialog,
                                                    _turkish_translator)
        from PyQt6.QtWidgets import QDialogButtonBox, QPushButton

        # Ürünün `pick_colour()` akışıyla AYNI: Qt'nin kendi dizeleri
        # pencere yaşarken Türkçeleştirilir.
        translator = _turkish_translator()
        translated = bool(translator is not None
                          and app.installTranslator(translator))
        picker = SubtitleColourDialog(
            dialog._picker_seed("sub_back_color"), dialog, "Arka plan",
            allow_transparent=True)
        picker.show()
        app.processEvents()
        button = picker.findChild(QPushButton, "subtitleNoColourButton")
        screen = app.primaryScreen().availableGeometry()
        palette = {
            "visible": bool(picker.isVisible()),
            "rect": list(picker.geometry().getRect()),
            "inside_screen": bool(screen.contains(picker.geometry())),
            "no_colour_text": button.text() if button else "",
            "no_colour_visible": bool(button and button.isVisible()),
            "no_colour_accessible": button.accessibleName() if button else "",
            "expected_text": NO_COLOUR_TEXT,
            "translated": translated,
            "standard_buttons": [b.text().replace("&", "") for b in
                                 (picker.findChild(QDialogButtonBox).buttons()
                                  if picker.findChild(QDialogButtonBox)
                                  else [])],
        }
        if args.shot:
            os.makedirs(os.path.dirname(args.shot), exist_ok=True)
            picker.grab().save(args.shot.replace(".png", "-palette.png"))
        if args.scenario == "palette_no_colour":
            button.click()
            app.processEvents()
            palette["chosen_alpha"] = picker.selected_colour().alpha()
            palette["closed"] = not picker.isVisible()
            dialog.set_color("sub_back_color", picker.selected_colour())
            app.processEvents()
        else:
            picker.reject()
            app.processEvents()
        picker.deleteLater()
        if translated:
            app.removeTranslator(translator)
        app.processEvents()

    # Açılır liste senaryoları: popup GERÇEKTEN açılır ve ölçülür.
    popup = {}
    popup_target = {"popup_scale": "subtitleScaleCombo",
                    "popup_delay": "subtitleDelayCombo",
                    "popup_border": "subtitleBorderCombo"}.get(args.scenario)
    if popup_target:
        combo = dialog.findChild(QComboBox, popup_target)
        combo.showPopup()
        app.processEvents()
        view = combo.view().window()
        combo_top_left = combo.mapToGlobal(combo.rect().bottomLeft())
        screen = app.primaryScreen().availableGeometry()
        popup = {
            "combo": popup_target,
            "visible": bool(view.isVisible()),
            "rect": list(view.geometry().getRect()),
            "below_combo": view.geometry().y() >= combo_top_left.y() - 2,
            "inside_screen": bool(screen.contains(view.geometry())),
            "item_count": combo.count(),
        }
        # Seçim sonrası popup KAPANMALI.
        combo.setCurrentIndex(min(2, combo.count() - 1))
        combo.hidePopup()
        app.processEvents()
        popup["closed_after_selection"] = not combo.view().isVisible()
        popup["selected_value"] = combo.currentData()
    if failed:
        dialog.findChild(QWidget, "subtitleApplyButton").click()
        app.processEvents()

    top = dialog.findChild(QWidget, "subtitleAppearanceSettings")
    bottom = dialog.findChild(QWidget, "subtitleAppearancePreview")
    preview = dialog.findChild(QWidget, "subtitlePreviewSurface")
    # SPINBOX YOK: hazır değer listeleri ölçülür. Eski `overlap` alanı
    # (yazı alanı ile ok alanının kesişmesi) artık ANLAMSIZDIR; yerine
    # kapalı kutudaki kısa metnin sığıp sığmadığı ölçülür.
    combos = {}
    for name in ("subtitleDelayCombo", "subtitleScaleCombo",
                 "subtitleBorderCombo"):
        combo = dialog.findChild(QComboBox, name)
        metrics = combo.fontMetrics()
        widest_short = max(
            metrics.horizontalAdvance(combo._short(combo.itemData(index)))
            for index in range(combo.count()))
        widest_full = max(metrics.horizontalAdvance(combo.itemText(index))
                          for index in range(combo.count()))
        combos[name] = {
            "widget": list(combo.geometry().getRect()),
            "item_count": combo.count(),
            "current_text": combo.short_text(),
            "current_value": combo.currentData(),
            "widest_short_px": widest_short,
            "widest_full_px": widest_full,
            "popup_min_width": combo.view().minimumWidth(),
            "short_fits": widest_short <= combo.width() - 26,
            "popup_fits_full_label": combo.view().minimumWidth() >= widest_full,
        }
    # Üç renk kutusu EŞİT ve YAN YANA mı?
    swatches = {}
    for key in ("sub_color", "sub_back_color", "sub_border_color"):
        widget = dialog._swatches[key]
        top_left = widget.mapTo(dialog, widget.rect().topLeft())
        swatches[key] = [top_left.x(), top_left.y(), widget.width(),
                         widget.height()]

    report = {
        "scenario": args.scenario,
        "scale": os.environ.get("QT_SCALE_FACTOR", "1"),
        "dialog": [dialog.width(), dialog.height()],
        "settings_rect": list(top.geometry().getRect()),
        "preview_panel_rect": list(bottom.geometry().getRect()),
        "settings_above_preview": bottom.geometry().y() >= top.geometry().bottom(),
        "panels_overlap": top.geometry().intersects(bottom.geometry()),
        "preview_width": bottom.width(),
        "preview_height": bottom.height(),
        "fits_target_screen": (dialog.width() <= TARGET_SCREEN[0]
                               and dialog.height() <= TARGET_SCREEN[1]),
        "visible": dialog.isVisible(),
        "clipped": [],
        "preview_text_inside": preview.rect().contains(preview.text_rect()),
        "preview_text_rect": list(preview.text_rect().getRect()),
        "preview_rect": list(preview.rect().getRect()),
        "background_visible": preview.background_visible(),
        "bitmap_notice": dialog.findChild(
            QWidget, "subtitleBitmapNotice").isVisible(),
        "combos": combos,
        "popup": popup,
        "palette": palette,
        "swatches": swatches,
        "left_margin": top.geometry().x(),
        "panel_gap": bottom.geometry().y() - top.geometry().bottom() - 1,
        "right_margin": dialog.width() - (top.geometry().x() + top.width()),
        "platform": os.environ.get("QT_QPA_PLATFORM", "windows"),
    }
    # Alt eylem düğmeleri GERÇEKTEN pencere içinde ve tıklanabilir mi?
    # `minimumSizeHint` karşılaştırması kırpılmayı yakalamaz: düğme tam
    # boyutunda olup pencere sınırının dışına taşabilir.
    actions = {}
    for name in ("subtitleResetButton", "subtitleCancelButton",
                 "subtitleApplyButton"):
        button = dialog.findChild(QWidget, name)
        if button is None:
            actions[name] = {"missing": True}
            continue
        rect = button.geometry()
        top_left = button.mapTo(dialog, button.rect().topLeft())
        inside = dialog.rect().contains(
            top_left.x(), top_left.y()) and dialog.rect().contains(
            top_left.x() + button.width() - 1,
            top_left.y() + button.height() - 1)
        centre = button.mapTo(dialog, button.rect().center())
        hit = dialog.childAt(centre)
        actions[name] = {
            "rect_in_dialog": [top_left.x(), top_left.y(), button.width(),
                               button.height()],
            "local_rect": list(rect.getRect()),
            "inside_dialog": bool(inside),
            "bottom_gap": dialog.height() - (top_left.y() + button.height()),
            "hit_widget": hit.objectName() if hit is not None else None,
            "clickable": hit is button,
            "visible": bool(button.isVisible()),
            "visible_region_empty": bool(button.visibleRegion().isEmpty()),
        }
    report["actions"] = actions

    for name in MEASURED:
        widget = dialog.findChild(QWidget, name)
        if widget is None:
            report["clipped"].append(f"{name}:missing")
            continue
        hint = widget.minimumSizeHint()
        if widget.width() < hint.width() or widget.height() < hint.height():
            report["clipped"].append(
                f"{name}:{widget.width()}x{widget.height()}<"
                f"{hint.width()}x{hint.height()}")
    if args.shot:
        os.makedirs(os.path.dirname(args.shot), exist_ok=True)
        dialog.grab().save(args.shot)
        report["shot"] = args.shot
    print("LAYOUT_JSON " + json.dumps(report, ensure_ascii=False), flush=True)
    dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
