# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Builds the Inno Setup wizard images from the product's own icon.

WHY: the installer wizard opened on an empty grey surface. The VLC
installer, looked at as a reference, carries a branded strip down the left
side; this gives the same function in our own visual identity.

The colours were MEASURED from `assets/mlc-player-icon.png` (the two
dominant ones): dark ground #101020 (40%) and brand orange #F05020 (26%).

Inno Setup 7.1 also accepts PNG; this project deliberately emits deterministic
24-bit RGB BMP files for a simple, decoder-independent installer input. Several
sizes are provided so the images do not blur on high-DPI screens.

Usage: python packaging/make_wizard_images.py
"""

import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(ROOT, "assets", "mlc-player-icon.png")
OUTPUT_DIR = os.path.join(ROOT, "packaging", "wizard")

BACKGROUND = (16, 16, 32)          # ikonun koyu zemini
ACCENT = (240, 80, 32)             # marka turuncusu

#: The scales Inno supports for the left-hand strip image.
LARGE_SIZES = ((164, 314), (192, 386), (256, 496))
#: The small image in the top corner.
SMALL_SIZES = ((55, 55), (110, 110), (138, 140))
#: Inno 7.1 full wizard background sizes for 100%, 125% and 200% DPI.
BACK_SIZES = ((596, 432), (796, 576), (1272, 922))
BRAND_RAIL_PERCENT = 24
CONTENT_BACKGROUND = (255, 255, 255)
FOOTER_PERCENT = 14


def _logo(size):
    icon = Image.open(ICON).convert("RGBA")
    return icon.resize((size, size), Image.LANCZOS)


def large_image(width, height):
    """Dark ground + a thin orange strip along the bottom + centred logo."""
    canvas = Image.new("RGB", (width, height), BACKGROUND)
    stripe_height = max(3, height // 60)
    canvas.paste(ACCENT, (0, height - stripe_height, width, height))

    logo_size = int(width * 0.62)
    logo = _logo(logo_size)
    position = ((width - logo_size) // 2, int(height * 0.30))
    canvas.paste(logo, position, logo)
    return canvas


#: The ground of Inno's modern wizard header is white.
HEADER_BACKGROUND = (255, 255, 255)


def small_image(width, height):
    """Top-right corner of the inner pages: NO IMAGE WANTED.

    USER DECISION: the full-height left panel on the first page already
    carries the identity; a second logo on the inner pages is redundant.
    Inno has NO key that turns the small image off - without
    `WizardSmallImageFile` it inserts ITS OWN default. So a flat image in
    the same colour as the header ground is supplied and the corner reads
    as empty.
    """
    return Image.new("RGB", (width, height), HEADER_BACKGROUND)


def back_image(width, height):
    """C v2 shell: dark brand rail, white content/footer and real logo.

    The footer remains white because Inno owns the native navigation buttons.
    Only the page surface receives brand colour; the bitmap contains no fake
    controls, text, progress value or clickable affordance.
    """
    canvas = Image.new("RGB", (width, height), CONTENT_BACKGROUND)
    rail_width = width * BRAND_RAIL_PERCENT // 100
    footer_top = height * (100 - FOOTER_PERCENT) // 100
    canvas.paste(BACKGROUND, (0, 0, rail_width, footer_top))

    accent_width = max(2, width // 240)
    canvas.paste(ACCENT, (
        rail_width - accent_width,
        0,
        rail_width,
        footer_top,
    ))

    logo_size = int(rail_width * 0.48)
    logo = _logo(logo_size)
    position = ((rail_width - logo_size) // 2, int(height * 0.19))
    canvas.paste(logo, position, logo)
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
    for index, (width, height) in enumerate(BACK_SIZES):
        suffix = "" if index == 0 else f"-{index}"
        path = os.path.join(OUTPUT_DIR, f"c-back{suffix}.bmp")
        back_image(width, height).save(path, "BMP")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in build():
        print("yazildi:", os.path.relpath(path, ROOT))
