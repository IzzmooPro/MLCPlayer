"""Masaüstü kısayolunda ikonun arkasında koyu plaka OLMAZ.

KULLANICI BİLDİRİMİ: kısayolda ikon koyu bir kare içinde duruyordu; VLC'nin
konisi gibi yalnız işaretin görünmesi, arkasının boş kalması istendi.

Üretim `packaging/make_app_icon.py` ile yapılır: kaynak sanattaki plaka
rengi (ölçülen `(20, 25, 32)`) şeffaflaştırılır, kenar pikselleri kapsama
alfası alır (basit eşik kenarlarda koyu hale bırakıyordu).

Kurulum sihirbazının görselleri BİLEREK eski sanatı kullanır; koyu panel
üzerinde plaka sorun değildir.
"""

import importlib.util
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TRANSPARENT = ROOT / "assets" / "mlc-player-icon-transparent.ico"
TRANSPARENT_PNG = ROOT / "assets" / "mlc-player-icon-transparent.png"
PLATE = (20, 25, 32)


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
    opaque = sum(1 for pixel in image.getdata() if pixel[3] > 200)
    ratio = opaque / (image.size[0] * image.size[1])
    assert 0.15 < ratio < 0.60, f"işaret oranı beklenmedik: {ratio:.2f}"


def test_the_icon_carries_small_sizes():
    """Windows kısayolu 16-32 piksel boyutlarını kullanır."""
    image = Image.open(TRANSPARENT)
    available = {size for size in image.info.get("sizes", set())}
    assert (16, 16) in available and (32, 32) in available, available


def test_the_application_loads_the_transparent_icon():
    from app import app_icon
    assert app_icon.ICON_FILE_NAME == "mlc-player-icon-transparent.ico"


def test_the_packaged_exe_uses_the_transparent_icon():
    spec = (ROOT / "MLCPlayer.spec").read_text(encoding="utf-8")
    assert "icon='assets/mlc-player-icon-transparent.ico'" in spec
    assert "('assets/mlc-player-icon-transparent.ico', 'assets')" in spec, (
        "şeffaf ikon pakete kopyalanmıyor; kurulu sürümde ikon kaybolur")


def test_the_installer_keeps_the_original_artwork():
    """KULLANICI KARARI: sihirbaz görselleri değişmez."""
    iss = (ROOT / "packaging" / "MLCPlayer.iss").read_text(encoding="utf-8-sig")
    assert "SetupIconFile=..\\assets\\mlc-player-icon.ico" in iss


def test_the_generator_is_reproducible():
    """Kaynak sanattan aynı sonucu üretebilmeli."""
    generator = _generator()
    produced = generator.remove_plate(Image.open(generator.SOURCE).resize(
        (64, 64), Image.LANCZOS))
    assert produced.getpixel((2, 2))[3] == 0
