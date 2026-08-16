"""Uygulama ikonunun ŞEFFAF sürümünü üretir.

KULLANICI İSTEĞİ: masaüstündeki kısayolda ikonun arkasındaki koyu plaka
görünüyordu; VLC'nin konisi gibi yalnız işaretin durması, arkasının boş
olması isteniyor.

YÖNTEM: kaynak sanat düz renklerden oluşur — plaka `(20, 25, 32)`, işaret
turuncu `(252, 88, 33)` ve beyaz üçgen (ÖLÇÜLDÜ). Basit bir "koyu pikselleri
sil" eşiği kenarlarda koyu hale bırakırdı, çünkü kenar pikselleri plaka ile
işaretin KARIŞIMIDIR. Bunun yerine her piksel için kapsama (alfa) hesaplanır:
piksel plakadan ne kadar uzaksa o kadar opak olur ve rengi en yakın düz
işaret rengine sabitlenir. Böylece kenarlar temiz kalır.

Kurulum sihirbazının görselleri BİLEREK dokunulmaz; onlar koyu panel
üzerinde duruyor ve orada plaka sorun değil.

Kullanım: python packaging/make_app_icon.py
"""

import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "assets", "mlc-player-icon.png")
TRANSPARENT_PNG = os.path.join(ROOT, "assets", "mlc-player-icon-transparent.png")
TRANSPARENT_ICO = os.path.join(ROOT, "assets", "mlc-player-icon-transparent.ico")

#: Kaldırılacak plaka rengi ve korunacak işaret renkleri (ölçülen değerler).
PLATE = (20, 25, 32)
FOREGROUNDS = ((252, 88, 33), (240, 245, 250))

#: Windows kısayolu 16 pikselden 256'ya kadar her boyutu kullanır.
ICO_SIZES = [(size, size) for size in (16, 24, 32, 48, 64, 128, 256)]


def _distance(first, second):
    return sum((a - b) ** 2 for a, b in zip(first, second)) ** 0.5


def remove_plate(image):
    """Plakayı şeffaflaştırır; kenar pikselleri kapsama alfası alır."""
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
