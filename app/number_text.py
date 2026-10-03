# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dile göre sayı metinleri (ondalık ayırıcı, yüzde, bayt).

Qt İÇERMEZ: `media_info` gibi Qt'siz modüller de kullanır. Biçim
`tr()` ile çevrilir; testler makinenin sistem dilinden bağımsızdır.
"""

from app.translate import tr


def localize_decimal(text):
    """`23.976` gibi noktalı sayıyı dilin ondalık ayırıcısıyla yazar."""
    whole, dot, fraction = str(text).partition(".")
    if not dot:
        return whole
    return tr("{whole},{fraction}").format(whole=whole, fraction=fraction)


def byte_count_text(count):
    """1024'ten küçük boyut: Türkçe `512 bayt`, İngilizce `512 bytes`."""
    return tr("{count} bayt").format(count=int(count))


def percent_text(value):
    """Yüzde değerini dilin yazımıyla verir (Türkçe `%70`, İngilizce `70%`)."""
    return tr("%{value}").format(value=int(round(float(value))))
