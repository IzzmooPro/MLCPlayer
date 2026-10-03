# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Onaylı yuvarlak ikon bütün Windows yüzeylerinde aynı kimliği kullanır.

KULLANICI BİLDİRİMİ: kurulum başlığı yuvarlak ikona geçtiği hâlde sol büyük
panelde altıgen işaret kalmıştı. İki kurulum yüzeyi de yuvarlak olmalıdır.

Üretim `packaging/make_app_icon.py` ile yapılır: kaynak sanattaki plaka
rengi (ölçülen `(20, 25, 32)`) şeffaflaştırılır, kenar pikselleri kapsama
alfası alır (basit eşik kenarlarda koyu hale bırakıyordu).

Kurulum sihirbazının büyük görselleri aynı yuvarlak kaynak sanattan üretilir.
"""

import importlib.util
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "mlc-player-icon.png"
STANDARD = ROOT / "assets" / "mlc-player-icon.ico"
TRANSPARENT = ROOT / "assets" / "mlc-player-icon-transparent.ico"
TRANSPARENT_PNG = ROOT / "assets" / "mlc-player-icon-transparent.png"
PLATE = (20, 25, 32)
REQUIRED_ICO_SIZES = {
    (16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
    (48, 48), (64, 64), (128, 128), (256, 256),
}


def _generator():
    path = ROOT / "packaging" / "make_app_icon.py"
    spec = importlib.util.spec_from_file_location("mlc_app_icon", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_transparent_icon_exists():
    assert TRANSPARENT.is_file(), "şeffaf ikon üretilmemiş"
    assert TRANSPARENT_PNG.is_file()


def test_no_dark_plate_pixels_remain():
    """Plaka rengine yakın OPAK piksel kalmamalı."""
    image = Image.open(TRANSPARENT_PNG).convert("RGBA")
    width, height = image.size
    pixels = image.load()
    offenders = 0
    for y in range(0, height, 7):
        for x in range(0, width, 7):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 200:
                continue
            if sum((a - b) ** 2 for a, b in zip((red, green, blue), PLATE)) < 900:
                offenders += 1
    assert offenders == 0, f"{offenders} koyu plaka pikseli duruyor"


@pytest.mark.parametrize("point", [(5, 5), (120, 120), (627, 60)])
def test_the_background_is_empty(point):
    """Köşeler ve plaka bölgesi tamamen şeffaf olmalı."""
    image = Image.open(TRANSPARENT_PNG).convert("RGBA")
    assert image.getpixel(point)[3] == 0, f"{point} şeffaf değil"


def test_the_mark_itself_survived():
    """Plakayı silerken işaret de silinmiş olmasın."""
    image = Image.open(TRANSPARENT_PNG).convert("RGBA")
    # `getdata()` Pillow 14'te kaldırılıyor; alfa kanalı histogramı aynı
    # ölçümü verir ve sürüm değişiminde kırılmaz.
    alpha_histogram = image.getchannel("A").histogram()
    opaque = sum(alpha_histogram[201:])
    ratio = opaque / (image.size[0] * image.size[1])
    assert 0.15 < ratio < 0.60, f"işaret oranı beklenmedik: {ratio:.2f}"


@pytest.mark.parametrize("path", [SOURCE, TRANSPARENT_PNG])
def test_the_approved_round_mark_is_the_canonical_icon(path):
    image = Image.open(path).convert("RGBA")
    width, height = image.size

    # Yuvarlak işaret orta-sol ve üst-orta noktalarda turuncudur; altıgen
    # varyant orta-sol noktada boş kalıyordu.
    assert image.getpixel((width // 10, height // 2)) == (255, 90, 31, 255)
    assert image.getpixel((width // 2, height // 10)) == (255, 90, 31, 255)
    assert image.getpixel((width // 2, height // 2))[:3] == (255, 255, 255)


@pytest.mark.parametrize("path", [STANDARD, TRANSPARENT])
def test_every_ico_frame_uses_the_approved_round_mark(path):
    icon = Image.open(path)
    sizes = icon.info.get("sizes", set())
    assert sizes == REQUIRED_ICO_SIZES

    for size in sizes:
        icon.size = size
        frame = icon.convert("RGBA")
        width, height = frame.size
        for point in ((width // 10, height // 2), (width // 2, height // 10)):
            red, green, blue, alpha = frame.getpixel(point)
            assert red > 240 and 50 <= green <= 150 and blue < 100 and alpha > 190, (
                path.name, size, point, (red, green, blue, alpha)
            )
        red, green, blue, alpha = frame.getpixel((width // 2, height // 2))
        assert min(red, green, blue) > 230 and alpha > 240, (path.name, size)


def test_the_icon_carries_small_sizes():
    """Windows kısayolu 16-32 piksel boyutlarını kullanır."""
    image = Image.open(TRANSPARENT)
    available = {size for size in image.info.get("sizes", set())}
    assert (16, 16) in available and (32, 32) in available, available


def test_the_application_loads_the_transparent_icon():
    from app import app_icon
    assert app_icon.ICON_FILE_NAME == "mlc-player-icon-transparent.ico"


def test_the_packaged_exe_uses_the_transparent_icon():
    spec = (ROOT / "packaging/MLCPlayer.spec").read_text(encoding="utf-8")
    assert "icon=_from_root('assets/mlc-player-icon-transparent.ico')" in spec
    assert "('assets/mlc-player-icon-transparent.ico', 'assets')" in spec, (
        "şeffaf ikon pakete kopyalanmıyor; kurulu sürümde ikon kaybolur")


def test_both_installers_use_the_round_icon_on_their_title_bars():
    iss = (ROOT / "packaging" / "MLCPlayer.iss").read_text(encoding="utf-8-sig")
    assert "SetupIconFile=..\\assets\\mlc-player-icon.ico" in iss

    addon_iss = (ROOT / "packaging" / "MLCPlayer_InternetVideo.iss").read_text(
        encoding="utf-8-sig"
    )
    assert "SetupIconFile=..\\assets\\mlc-player-icon.ico" in addon_iss


def test_the_left_wizard_panels_are_generated_from_the_round_icon():
    path = ROOT / "packaging" / "make_wizard_images.py"
    spec = importlib.util.spec_from_file_location("mlc_wizard_images", path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    for index, (width, height) in enumerate(generator.LARGE_SIZES):
        suffix = "" if index == 0 else f"-{index}"
        actual = Image.open(
            ROOT / "packaging" / "wizard" / f"wizard-large{suffix}.bmp"
        ).convert("RGB")
        expected = generator.large_image(width, height)
        assert actual.tobytes() == expected.tobytes(), suffix

        logo_size = int(width * 0.62)
        logo_x = (width - logo_size) // 2
        logo_y = int(height * 0.30)
        assert actual.getpixel(
            (logo_x + logo_size // 10, logo_y + logo_size // 2)
        ) == (255, 90, 31), suffix
        assert actual.getpixel(
            (logo_x + logo_size // 2, logo_y + logo_size // 10)
        ) == (255, 90, 31), suffix


def test_the_generator_is_reproducible():
    """Kaynak sanattan aynı sonucu üretebilmeli."""
    generator = _generator()
    produced = generator.remove_plate(Image.open(generator.SOURCE).resize(
        (64, 64), Image.LANCZOS))
    assert produced.getpixel((2, 2))[3] == 0
