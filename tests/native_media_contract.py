# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Native kabul icin ORTAK medya sozlesmesi: TEK kaynak.

Bu modul BILEREK kucuktur ve `mpv`, `PyQt6` ya da `app.*` IMPORT ETMEZ;
boylece hem ebeveyn degerlendirici hem de native child ayni yardimcilari
kullanabilir ve uzanti listesi/kodlama iki yerde KOPYALANMAZ.

OLCULEN KUSUR (18 Agustos 2026, bagimsiz denetim): marker satirlari
bosluga gore ayristigi icin GECERLI bir dosya adi kabulu DUSURUYORDU:

    MARK_PLAYER_CREATED t=0.51 kayıt 01.mkv

`kayıt` ve `01.mkv` iki ayri alan sayiliyordu. Cozum, adi bosluk
icermeyen ve KAYIPSIZ bir alanda tasimaktir: UTF-8 -> URL-safe Base64.
Boylece bosluk, Turkce harf, emoji ve `=` gibi karakterler protokolu
bozmaz.
"""

import base64
import binascii
import os

#: Gercek video sayilan TEK uzanti kumesi (buyuk/kucuk harf duyarsiz).
MEDIA_EXTENSIONS = (".mkv", ".mp4")

#: Marker icindeki kodlanmis medya adi alaninin oneki.
MEDIA_FIELD_PREFIX = "media_b64="


def encode_media_basename(name):
    """Dosya adini bosluk icermeyen, kayipsiz bir token'a cevirir.

    URL-safe Base64 kullanilir: ciktida bosluk, `+` veya `/` YOKTUR;
    yalnizca `A-Z a-z 0-9 - _ =` gecer ve hicbiri alan ayirici degildir.
    """
    return base64.urlsafe_b64encode(name.encode("utf-8")).decode("ascii")


def decode_media_basename(token):
    """Token'i coz. Gecersiz Base64 veya gecersiz UTF-8 -> `None`.

    FAIL-CLOSED: cozulemeyen bir token SESSIZCE kabul edilmez ve
    `errors="replace"` ile "kurtarilmaz"; kurtarma, farkli bir dosyayi
    dogru dosya gibi gosterebilirdi.
    """
    if not isinstance(token, str) or not token:
        return None
    try:
        # `validate=True` SART: varsayilan cozucu alfabe disi karakterleri
        # SESSIZCE ATAR ve `"!!!"` gibi tamamen bozuk bir token bos dizeye
        # cozulup gecerli sayilirdi.
        raw = base64.b64decode(token.encode("ascii"), altchars=b"-_",
                               validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError):
        return None
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def is_supported_media(path):
    """Yalniz gercek `.mkv`/`.mp4` DOSYASI. Dizin ve digerleri REDDEDILIR.

    Ebeveyn kapisi ve child AYNI bu fonksiyonu kullanir; child dogrudan
    calistirildiginda da gecersiz bir dosya oynatilmaya CALISILMAZ.
    """
    if not path:
        return False
    if os.path.splitext(path)[1].lower() not in MEDIA_EXTENSIONS:
        return False
    try:
        return os.path.isfile(path)
    except OSError:
        return False
