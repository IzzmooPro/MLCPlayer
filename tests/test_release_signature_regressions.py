# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Güncelleme yalnız YAYINCININ imzaladığı dosyayı kurar.

NEDEN: SHA-256 doğrulaması bozuk indirmeyi ve yanlış asset'i engelliyordu,
ama özet de release metadata'sından geliyordu — depo ele geçirilirse hem
dosya hem özet değiştirilebilirdi. İmza katmanı bunu kapatır: geçerli bir
güncelleme üretmek için ÖZEL ANAHTAR gerekir ve o anahtar depoda değildir.

Testler ağa çıkmaz; anahtar çifti test içinde üretilir.
"""

import base64
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import release_signature as signing

PAYLOAD = b"kurulum-dosyasi-icerigi"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def keypair():
    private = Ed25519PrivateKey.generate()
    public = base64.b64encode(private.public_key().public_bytes_raw()).decode()
    return private, public


def _sign(private, digest_hex):
    return base64.b64encode(private.sign(digest_hex.encode("ascii"))).decode()


def test_a_signature_from_the_publisher_is_accepted(keypair):
    private, public = keypair
    assert signing.verify(DIGEST, _sign(private, DIGEST), public) is True


def test_a_signature_from_another_key_is_rejected(keypair):
    """Depo ele geçirilse bile saldırganın anahtarı GEÇMEZ."""
    _, public = keypair
    attacker = Ed25519PrivateKey.generate()
    with pytest.raises(signing.SignatureError):
        signing.verify(DIGEST, _sign(attacker, DIGEST), public)


def test_a_signature_for_another_file_is_rejected(keypair):
    """İmza dosyaya BAĞLIDIR; başka sürümün imzası kullanılamaz."""
    private, public = keypair
    other = hashlib.sha256(b"baska-dosya").hexdigest()
    with pytest.raises(signing.SignatureError):
        signing.verify(DIGEST, _sign(private, other), public)


@pytest.mark.parametrize("signature", ["", "   ", "bozuk-base64!!", None])
def test_missing_or_broken_signature_is_rejected(keypair, signature):
    _, public = keypair
    with pytest.raises(signing.SignatureError):
        signing.verify(DIGEST, signature, public)


@pytest.mark.parametrize("digest", ["", "kisa", "z" * 64])
def test_a_malformed_digest_is_rejected(keypair, digest):
    private, public = keypair
    with pytest.raises(signing.SignatureError):
        signing.verify(digest, _sign(private, DIGEST), public)


def test_verification_never_returns_false_silently(keypair):
    """Sessiz `False` yutulabilirdi; başarısızlık İSTİSNA olmalıdır."""
    _, public = keypair
    attacker = Ed25519PrivateKey.generate()
    try:
        signing.verify(DIGEST, _sign(attacker, DIGEST), public)
    except signing.SignatureError:
        return
    pytest.fail("geçersiz imza istisna fırlatmadı")


def test_the_product_ships_a_public_key():
    """Anahtar gömülü değilse imza katmanı hiç çalışmaz."""
    assert signing.signing_enabled(), "RELEASE_PUBLIC_KEY boş"
    assert len(base64.b64decode(signing.RELEASE_PUBLIC_KEY)) == 32


def test_signature_asset_name_follows_the_installer():
    assert signing.signature_asset_name("MLCPlayer_Setup_v0.32.exe") == \
        "MLCPlayer_Setup_v0.32.exe.sig"


def test_private_key_is_not_in_the_repository():
    """Özel anahtar depoya girerse bütün koruma anlamsızlaşır."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for path in root.rglob("*.key"):
        if ".git" in path.parts:
            continue
        pytest.fail(f"depoda anahtar dosyası var: {path}")


# ── Kuralın kendisi korunur (devralan kişi/asistan için) ─────────────────

def _root():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent


def test_the_build_chain_signs_the_installer():
    """İmzalama insan hafızasına bırakılmaz; zincirin adımıdır.

    İmzasız yayımlanan bir sürümü güncelleyici REDDEDER ve kullanıcı sebebini
    göremez. Bu yüzden `build_release.bat` imzayı kendisi üretir.
    """
    chain = (_root() / "packaging" / "build_release.bat").read_text(
        encoding="utf-8", errors="ignore")
    assert "sign_release.py" in chain, "zincir kurulumu imzalamıyor"
    index = chain.index("sign_release.py")
    assert "goto :fail" in chain[index:index + 400], (
        "imzalama başarısız olursa zincir DURMALI")


def test_the_signing_rules_are_written_where_they_are_read():
    """Devralan kişi/asistan kuralı görmeli: CLAUDE.md her oturumda okunur."""
    rules = (_root() / "CLAUDE.md").read_text(encoding="utf-8")
    for expected in ("sign_release.py", ".sig", "RELEASE_PUBLIC_KEY",
                     "MLC_SIGNING_KEY"):
        assert expected in rules, f"kural eksik: {expected}"


def test_verification_cannot_be_disabled_by_emptying_the_key():
    """`RELEASE_PUBLIC_KEY` boşaltılırsa doğrulama SESSİZCE geçmez."""
    original = signing.RELEASE_PUBLIC_KEY
    signing.RELEASE_PUBLIC_KEY = ""
    try:
        assert signing.signing_enabled() is False
        with pytest.raises(signing.SignatureError):
            signing.verify(DIGEST, "imza")
    finally:
        signing.RELEASE_PUBLIC_KEY = original
