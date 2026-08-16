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


#: Inno'nun modern sihirbaz başlığının zemini beyazdır.
HEADER_BACKGROUND = (255, 255, 255)


def small_image(width, height):
    """İç sayfaların sağ üst köşesi: GÖRSEL İSTENMİYOR.

    KULLANICI KARARI: ilk sayfadaki boydan boya sol panel kimliği zaten
    veriyor; iç sayfalarda ikinci bir logo fazlalık. Inno'da küçük görseli
    kapatan bir anahtar YOKTUR — `WizardSmallImageFile` verilmezse Inno
    KENDİ varsayılan görselini koyar. Bu yüzden başlık zeminiyle aynı
    renkte düz bir görsel verilir ve köşe boş görünür.
    """
    return Image.new("RGB", (width, height), HEADER_BACKGROUND)


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
