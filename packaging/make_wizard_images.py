"""Inno Setup sihirbaz görsellerini ürünün kendi ikonundan üretir.

NEDEN: kurulum sihirbazı boş gri bir yüzeyle açılıyordu. Referans olarak
bakılan VLC kurulumunda sol tarafta markalı bir şerit var; aynı işlevi
kendi görsel kimliğimizle veriyoruz.

Renkler `assets/mlc-player-icon.png` içinden ÖLÇÜLDÜ (baskın iki renk):
koyu zemin #101020 (%40) ve marka turuncusu #F05020 (%26).

Inno Setup 24-bit BMP ister; PNG kabul etmez. Çoklu boyut verilir ki
yüksek DPI ekranlarda bulanıklaşmasın.

Kullanım: python packaging/make_wizard_images.py
"""

import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(ROOT, "assets", "mlc-player-icon.png")
OUTPUT_DIR = os.path.join(ROOT, "packaging", "wizard")

BACKGROUND = (16, 16, 32)          # ikonun koyu zemini
ACCENT = (240, 80, 32)             # marka turuncusu

#: Inno'nun sol şerit görseli için desteklenen ölçekler.
LARGE_SIZES = ((164, 314), (192, 386), (256, 496))
#: Üst köşedeki küçük görsel.
SMALL_SIZES = ((55, 55), (110, 110), (138, 140))


def _logo(size):
    icon = Image.open(ICON).convert("RGBA")
    return icon.resize((size, size), Image.LANCZOS)


def large_image(width, height):
    """Koyu zemin + altta ince turuncu şerit + ortada logo."""
    canvas = Image.new("RGB", (width, height), BACKGROUND)
    stripe_height = max(3, height // 60)
    canvas.paste(ACCENT, (0, height - stripe_height, width, height))

    logo_size = int(width * 0.62)
    logo = _logo(logo_size)
    position = ((width - logo_size) // 2, int(height * 0.30))
    canvas.paste(logo, position, logo)
    return canvas


def small_image(width, height):
    """Küçük görsel: zemin + logo, kenar boşluğu dar."""
    canvas = Image.new("RGB", (width, height), BACKGROUND)
    logo_size = int(min(width, height) * 0.86)
    logo = _logo(logo_size)
    canvas.paste(logo, ((width - logo_size) // 2, (height - logo_size) // 2),
                 logo)
    return canvas


def build():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    written = []
    for index, (width, height) in enumerate(LARGE_SIZES):
        suffix = "" if index == 0 else f"-{index}"
        path = os.path.join(OUTPUT_DIR, f"wizard-large{suffix}.bmp")
        large_image(width, height).save(path, "BMP")
        written.append(path)
    for index, (width, height) in enumerate(SMALL_SIZES):
        suffix = "" if index == 0 else f"-{index}"
        path = os.path.join(OUTPUT_DIR, f"wizard-small{suffix}.bmp")
        small_image(width, height).save(path, "BMP")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in build():
        print("yazildi:", os.path.relpath(path, ROOT))
