# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yayın imzası: güncellemenin BAĞIMSIZ güven kökü.

NEDEN VAR: güncelleyici indirilen kurulumu SHA-256 ile doğruluyordu, ama
o özet de GitHub release metadata'sından geliyordu. Bu, bozuk/eksik
indirmeyi ve yanlış asset'i engeller; GitHub hesabı ya da release
metadata'sı ele geçirilirse YETMEZ — saldırgan hem dosyayı hem özeti
değiştirebilir.

Burada eklenen katman: kurulum dosyasının SHA-256 özeti, yayıncının ÖZEL
anahtarıyla imzalanır (Ed25519) ve imza ayrı bir release asset'i olarak
(`<kurulum>.sig`) yayımlanır. Uygulama AÇIK anahtarı kendi içinde taşır.
Artık geçerli bir güncelleme üretmek için depo erişimi YETMEZ; özel anahtar
gerekir ve o anahtar depoda DEĞİLDİR.

SINIR: bu, kod imzalamanın (Authenticode) yerine geçmez. Windows'un
"bilinmeyen yayımcı" uyarısını kaldırmaz; yalnız güncelleme zincirini
korur. Anahtar kaybedilirse yeni anahtar gömülü olarak yayımlanmalı ve
kullanıcılar o sürümü elle kurmalıdır.
"""

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

#: Yayıncının açık anahtarı (base64, ham 32 bayt Ed25519).
#: BOŞ bırakılırsa imza denetimi devre dışıdır ve güncelleyici yalnız
#: SHA-256 ile korunur — bu, anahtar üretilmeden önceki geçiş durumudur.
#: `packaging/sign_release.py --init` üretir ve buraya yazılacak değeri verir.
RELEASE_PUBLIC_KEY = "FRrsxjp+JMAhbH19TGeN6ZwEfy1EE5MtfPR+nHIvd4Q="

#: İmza dosyasının adı: `<kurulum adı>.sig`
SIGNATURE_SUFFIX = ".sig"


class SignatureError(Exception):
    """İmza doğrulanamadı — kullanıcıya ayrıntı verilmez."""


def signing_enabled():
    """Uygulama bir açık anahtar taşıyor mu?"""
    return bool(RELEASE_PUBLIC_KEY.strip())


def signature_asset_name(installer_name):
    return f"{installer_name}{SIGNATURE_SUFFIX}"


def _public_key():
    try:
        raw = base64.b64decode(RELEASE_PUBLIC_KEY.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError(f"açık anahtar okunamadı: {exc}")
    if len(raw) != 32:
        raise SignatureError(f"açık anahtar 32 bayt değil: {len(raw)}")
    return Ed25519PublicKey.from_public_bytes(raw)


def verify(sha256_hex, signature_b64, public_key_b64=None):
    """`sha256_hex` üzerindeki imzayı doğrular.

    İmzalanan veri dosyanın KENDİSİ değil, ONALTILIK SHA-256 metnidir;
    böylece imzalama 300 MB'lık dosyayı ikinci kez okumaz ve doğrulama
    zaten hesaplanmış özet üzerinden yapılır.

    Başarısızlıkta `SignatureError` fırlatır — sessizce `False` DÖNMEZ,
    çünkü çağıran tarafın bunu yutması fail-open olurdu.
    """
    global RELEASE_PUBLIC_KEY
    if public_key_b64 is not None:
        original, RELEASE_PUBLIC_KEY = RELEASE_PUBLIC_KEY, public_key_b64
        try:
            return verify(sha256_hex, signature_b64)
        finally:
            RELEASE_PUBLIC_KEY = original

    if not signing_enabled():
        raise SignatureError("açık anahtar tanımlı değil")
    if not signature_b64:
        raise SignatureError("imza dosyası boş")

    digest = (sha256_hex or "").strip().lower()
    if len(digest) != 64:
        raise SignatureError("imzalanacak özet 64 onaltılık karakter değil")

    try:
        signature = base64.b64decode(signature_b64.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError(f"imza çözülemedi: {exc}")

    try:
        _public_key().verify(signature, digest.encode("ascii"))
    except InvalidSignature:
        raise SignatureError("imza bu yayıncıya ait değil")
    return True
