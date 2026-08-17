# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Produces the TRANSPARENT variant of the application icon.

USER REQUEST: the dark plate behind the icon was visible on the desktop
shortcut. Like VLC's cone, only the mark should remain, with nothing
behind it.

METHOD: the source art is made of flat colours - plate `(20, 25, 32)`,
brand orange `(252, 88, 33)` and a white triangle (MEASURED). A simple
"delete dark pixels" threshold would leave a dark halo along the edges,
because edge pixels are a BLEND of the plate and the mark. Instead a
coverage (alpha) value is computed per pixel: the further a pixel is from
the plate colour, the more opaque it becomes, and its colour is snapped to
the nearest flat mark colour. That keeps the edges clean.

The installer wizard images are DELIBERATELY left alone; they sit on a
dark panel where the plate is not a problem.

Usage: python packaging/make_app_icon.py
"""

import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "assets", "mlc-player-icon.png")
TRANSPARENT_PNG = os.path.join(ROOT, "assets", "mlc-player-icon-transparent.png")
TRANSPARENT_ICO = os.path.join(ROOT, "assets", "mlc-player-icon-transparent.ico")

#: The plate colour to remove and the mark colours to keep (measured).
PLATE = (20, 25, 32)
FOREGROUNDS = ((252, 88, 33), (240, 245, 250))

#: A Windows shortcut uses every size from 16 pixels up to 256.
ICO_SIZES = [(size, size) for size in (16, 24, 32, 48, 64, 128, 256)]


def _distance(first, second):
    return sum((a - b) ** 2 for a, b in zip(first, second)) ** 0.5


def remove_plate(image):
    """Makes the plate transparent; edge pixels get a coverage alpha."""
    image = image.convert("RGBA")
    width, height = image.size
    source = image.load()
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    target = result.load()

    spans = [_distance(colour, PLATE) for colour in FOREGROUNDS]
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = source[x, y]
            if alpha == 0:
                continue
            pixel = (red, green, blue)
            distances = [_distance(pixel, colour) for colour in FOREGROUNDS]
            index = distances.index(min(distances))
            coverage = _distance(pixel, PLATE) / spans[index]
            coverage = max(0.0, min(1.0, coverage))
            if coverage <= 0.02:
                continue
            target[x, y] = FOREGROUNDS[index] + (int(alpha * coverage),)
    return result


def build():
    image = remove_plate(Image.open(SOURCE))
    image.save(TRANSPARENT_PNG, "PNG")
    image.save(TRANSPARENT_ICO, "ICO", sizes=ICO_SIZES)
    return TRANSPARENT_PNG, TRANSPARENT_ICO


if __name__ == "__main__":
    for path in build():
        print("yazildi:", os.path.relpath(path, ROOT))
