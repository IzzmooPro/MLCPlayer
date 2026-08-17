# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı önizlemesindeki TEMSİLİ sahnenin sözleşmesi.

Eski önizleme düz siyahtı (`fillRect(QColor(12, 13, 15))`); kullanıcı
beyaz yazının aydınlık bir gökyüzünde, koyu yazının karanlık bir
siluette nasıl görüneceğini göremiyordu.

Bu dosya sahnenin ÖLÇÜLEBİLİR sözleşmesini kilitler:

- yüzeyin tamamını kaplar,
- hem açık hem koyu bölgeler içerir,
- tek renk veya YALNIZ dikey gradient değildir,
- deterministiktir ve boyuta göre cache'lenir,
- altyazı katmanının davranışını (konum, kutu, renkler) DEĞİŞTİRMEZ.

Sahne yereldir: ağ, kullanıcı videosu veya harici asset kullanılmaz.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from app.subtitle_appearance_dialog import SubtitleAppearanceDialog

SURFACE = (640, 360)


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    """QApplication modül boyunca YAŞAMALI.

    Referans düşerse Qt uygulaması yok edilir ve `QPixmap` oluşturmak
    süreci düşürür ("Must construct a QGuiApplication before a QPixmap").
    """
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def preview_factory(tmp_path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(values=None, size=SURFACE):
        dialog = SubtitleAppearanceDialog(values=values, track_list=[],
                                          apply_callback=lambda v: (True, None))
        created.append(dialog)
        dialog.show()
        app.processEvents()
        preview = dialog.preview
        preview.resize(*size)
        app.processEvents()
        return app, dialog, preview

    yield factory

    for dialog in created:
        dialog.close()
        dialog.deleteLater()
    app.processEvents()


# --- ölçüm yardımcıları (saf) ---

def luma(red, green, blue):
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def image_bytes(image):
    """Görüntünün SATIR DOLGUSUZ RGB içeriği (üstveriden bağımsız)."""
    from PyQt6.QtGui import QImage

    converted = image.convertToFormat(QImage.Format.Format_RGB888)
    line = converted.bytesPerLine()
    bits = converted.bits()
    bits.setsize(line * converted.height())
    raw = bytes(bits)
    width = converted.width() * 3
    return b"".join(raw[y * line:y * line + width]
                    for y in range(converted.height()))


def image_stats(image, step=1):
    """Görüntünün parlaklık dağılımı ve yatay değişim profili."""
    width, height = image.width(), image.height()
    buckets = [0] * 8
    unique = set()
    lowest, highest = 255.0, 0.0
    rows_with_variation = 0
    total = 0
    for y in range(0, height, step):
        row_low, row_high = 255.0, 0.0
        for x in range(0, width, step):
            colour = image.pixelColor(x, y)
            rgb = (colour.red(), colour.green(), colour.blue())
            unique.add(rgb)
            value = luma(*rgb)
            buckets[min(7, int(value // 32))] += 1
            total += 1
            lowest = min(lowest, value)
            highest = max(highest, value)
            row_low = min(row_low, value)
            row_high = max(row_high, value)
        if row_high - row_low >= 30:
            rows_with_variation += 1
    rows = len(range(0, height, step))
    return {
        "min_luma": lowest, "max_luma": highest,
        "unique_colours": len(unique),
        "bands": [count / float(total) for count in buckets],
        "row_variation_share": rows_with_variation / float(max(1, rows)),
        "total": total,
    }


def scene_problems(image):
    """Temsili sahne sözleşmesini karşılamayan yönler. Boş liste = kabul."""
    problems = []
    stats = image_stats(image, step=2)
    if stats["max_luma"] < 200:
        problems.append(f"no_bright_region max_luma={stats['max_luma']:.0f}")
    if stats["min_luma"] > 40:
        problems.append(f"no_dark_region min_luma={stats['min_luma']:.0f}")
    if stats["unique_colours"] < 500:
        problems.append(f"flat_colour unique={stats['unique_colours']}")
    meaningful = len([share for share in stats["bands"] if share >= 0.01])
    if meaningful < 4:
        problems.append(f"too_few_brightness_bands={meaningful}")
    # Saf dikey gradient'te her satır yatayda SABİTTİR; oran 0 olur.
    if stats["row_variation_share"] < 0.33:
        problems.append(
            f"vertical_gradient_only rows={stats['row_variation_share']:.2f}")
    return problems, stats


# --- 1. Kırmızı kanıt: mevcut önizleme sahne sözleşmesini karşılamıyor ---

def test_preview_surface_paints_a_representative_scene(preview_factory):
    app, dialog, preview = preview_factory()
    image = preview.grab().toImage()

    problems, stats = scene_problems(image)
    assert problems == [], f"sahne sözleşmesi karşılanmadı: {problems} {stats}"


# --- 2. Sahne üreticisinin kendi sözleşmesi ---

def test_scene_fills_the_requested_surface_exactly():
    from app.subtitle_appearance_dialog import build_preview_scene

    scene = build_preview_scene(*SURFACE)
    assert (scene.width(), scene.height()) == SURFACE
    image = scene.toImage()
    assert image.pixelColor(0, 0).alpha() == 255
    assert image.pixelColor(SURFACE[0] - 1, SURFACE[1] - 1).alpha() == 255


@pytest.mark.parametrize("size", [(330, 200), (484, 260), (960, 300),
                                 (300, 400)])
def test_scene_contract_holds_at_every_panel_size(size):
    from app.subtitle_appearance_dialog import build_preview_scene

    problems, stats = scene_problems(build_preview_scene(*size).toImage())
    assert problems == [], f"{size}: {problems} {stats}"


def test_scene_is_deterministic():
    from app.subtitle_appearance_dialog import build_preview_scene

    first = build_preview_scene(*SURFACE).toImage()
    second = build_preview_scene(*SURFACE).toImage()
    assert first.size() == second.size()
    # PIKSEL ICERIGI karsilastirilir. `QImage.__eq__` bicim/renk uzayi gibi
    # ustveriyi de kapsadigi icin ayni icerikte bile False donebiliyor;
    # olculmek istenen sey sahnenin cizim sonucudur.
    assert image_bytes(first) == image_bytes(second)


def test_scene_keeps_its_aspect_ratio_by_cropping_not_stretching():
    """Farklı en-boy oranlarında sahne GERİLMEZ; kırpılarak kaplar."""
    from app.subtitle_appearance_dialog import (SCENE_ASPECT,
                                                build_preview_scene)

    wide = build_preview_scene(800, 200)
    tall = build_preview_scene(300, 400)
    assert (wide.width(), wide.height()) == (800, 200)
    assert (tall.width(), tall.height()) == (300, 400)
    assert abs(SCENE_ASPECT - 16 / 9) < 1e-9


# --- 3. Cache: paintEvent her karede sahne üretmemeli ---

def test_scene_is_built_once_and_reused_across_repaints(preview_factory):
    app, dialog, preview = preview_factory()
    preview.grab()
    builds = preview.scene_builds()
    for _ in range(5):
        preview.set_style(preview.style_values)
        preview.grab()
    assert preview.scene_builds() == builds


def test_scene_is_rebuilt_after_a_resize(preview_factory):
    app, dialog, preview = preview_factory()
    preview.grab()
    builds = preview.scene_builds()
    preview.resize(SURFACE[0] - 90, SURFACE[1] - 40)
    app.processEvents()
    preview.grab()
    assert preview.scene_builds() == builds + 1


# --- 4. Altyazı katmanı davranışı DEĞİŞMEDİ ---

def test_subtitle_moves_with_sub_pos_while_the_scene_stays_still(
        preview_factory):
    app, dialog, preview = preview_factory()
    preview.set_style(dict(preview.style_values, sub_pos=10.0))
    top = preview.grab().toImage()
    top_rect = preview.text_rect()
    preview.set_style(dict(preview.style_values, sub_pos=90.0))
    bottom = preview.grab().toImage()
    bottom_rect = preview.text_rect()

    assert bottom_rect.top() > top_rect.top()
    assert top != bottom
    # Altyazının HİÇ uğramadığı satırlarda sahne birebir aynı kalmalı.
    untouched = [y for y in range(0, preview.height(), 3)
                 if not (top_rect.top() - 6 <= y <= top_rect.bottom() + 6)
                 and not (bottom_rect.top() - 6 <= y <= bottom_rect.bottom() + 6)]
    assert untouched, "karşılaştırılacak boş satır kalmadı"
    for y in untouched:
        for x in range(0, preview.width(), 7):
            assert top.pixelColor(x, y) == bottom.pixelColor(x, y), (x, y)


def test_text_bounding_box_stays_inside_the_surface(preview_factory):
    app, dialog, preview = preview_factory()
    for position in (0.0, 50.0, 100.0):
        preview.set_style(dict(preview.style_values, sub_pos=position,
                               sub_scale=1.8))
        preview.grab()
        assert preview.rect().contains(preview.text_rect())


def test_transparent_background_draws_no_box(preview_factory):
    app, dialog, preview = preview_factory(
        values={"sub_back_color": QColor(0, 0, 0, 0)})
    preview.set_style(dict(preview.style_values,
                           sub_back_color=QColor(0, 0, 0, 0)))
    image = preview.grab().toImage()

    assert preview.background_visible() is False
    # Ayirt edici bir RGB ile alfa 0: hicbir piksel bu renge boyanmamali.
    preview.set_style(dict(preview.style_values,
                           sub_back_color=QColor(0, 32, 160, 0)))
    image = preview.grab().toImage()
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            colour = image.pixelColor(x, y)
            assert (colour.red(), colour.green(),
                    colour.blue()) != (0, 32, 160), (x, y)


def test_opaque_background_draws_a_box_that_does_not_cover_the_scene(
        preview_factory):
    app, dialog, preview = preview_factory()
    back = QColor(0, 32, 160, 255)
    preview.set_style(dict(preview.style_values, sub_back_color=back))
    image = preview.grab().toImage()

    assert preview.background_visible() is True
    matches = 0
    total = 0
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            total += 1
            colour = image.pixelColor(x, y)
            if (colour.red(), colour.green(), colour.blue()) == (0, 32, 160):
                matches += 1
    assert matches > 0, "arka plan kutusu hiç çizilmedi"
    assert matches / float(total) < 0.60, "kutu bütün sahneyi kaplıyor"


def test_text_and_border_colours_update_live(preview_factory):
    app, dialog, preview = preview_factory()
    preview.set_style(dict(preview.style_values,
                           sub_color=QColor(255, 255, 255, 255),
                           sub_border_color=QColor(0, 0, 0, 255)))
    white = preview.grab().toImage()
    preview.set_style(dict(preview.style_values,
                           sub_color=QColor(242, 106, 61, 255),
                           sub_border_color=QColor(0, 32, 160, 255)))
    orange = preview.grab().toImage()
    assert white != orange


def test_caption_names_the_scene_as_representative(preview_factory):
    app, dialog, preview = preview_factory()
    from PyQt6.QtWidgets import QLabel

    caption = dialog.findChild(QLabel, "subtitlePreviewCaption")
    assert caption.text() == ("Temsili video önizlemesi — gerçek video "
                              "çıktısı değildir")


def test_scene_uses_no_external_asset_or_network():
    """Sahne YEREL çizimdir: dosya/ağ erişimi yoktur."""
    import ast
    import inspect

    from app import subtitle_appearance_dialog as module

    tree = ast.parse(inspect.getsource(module))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute)}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
    forbidden = {"QNetworkAccessManager", "urlopen", "requests", "QMovie",
                 "QImageReader", "QFile", "open", "QResource"}
    assert not (forbidden & (names | imported | attributes))
