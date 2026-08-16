"""Yayın imzalama aracı (Ed25519).

    python packaging/sign_release.py --init
        Yayıncı anahtar çiftini ÜRETİR. Özel anahtar depo DIŞINDA saklanır;
        açık anahtar ekrana yazılır ve `app/release_signature.py` içine
        elle gömülür.

    python packaging/sign_release.py installer_output/MLCPlayer_Setup_vX.exe
        Dosyanın SHA-256 özetini imzalar ve `<dosya>.sig` üretir. Bu dosya
        release'e ASSET olarak yüklenmelidir; güncelleyici onu indirip
        gömülü açık anahtarla doğrular.

ÖZEL ANAHTAR ASLA DEPOYA GİRMEZ. Varsayılan konum:
    %USERPROFILE%\\.mlcplayer\\release_ed25519.key
`MLC_SIGNING_KEY` ortam değişkeniyle başka bir yol verilebilir.
"""

import base64
import hashlib
import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)

DEFAULT_KEY_PATH = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")),
    ".mlcplayer", "release_ed25519.key")


def key_path():
    return os.environ.get("MLC_SIGNING_KEY") or DEFAULT_KEY_PATH


def create_key():
    path = key_path()
    if os.path.exists(path):
        print(f"[HATA] Anahtar zaten var: {path}")
        print("       Yenisini üretmek eski imzaları GEÇERSİZ kılar; dosyayı")
        print("       elle taşıyın ve gömülü açık anahtarı da güncelleyin.")
        return 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes_raw()
    with open(path, "wb") as handle:
        handle.write(base64.b64encode(raw))
    public = base64.b64encode(private.public_key().public_bytes_raw()).decode()
    print(f"[OK] Özel anahtar yazıldı: {path}")
    print("     BU DOSYAYI YEDEKLEYİN ve depoya EKLEMEYİN.")
    print()
    print("app/release_signature.py içine gömülecek açık anahtar:")
    print(f'RELEASE_PUBLIC_KEY = "{public}"')
    return 0


def load_private():
    path = key_path()
    if not os.path.exists(path):
        raise SystemExit(f"[HATA] Özel anahtar yok: {path}\n"
                         f"       Önce: python packaging/sign_release.py --init")
    with open(path, "rb") as handle:
        raw = base64.b64decode(handle.read().strip())
    return Ed25519PrivateKey.from_private_bytes(raw)


def sha256_hex(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sign(path):
    if not os.path.isfile(path):
        print(f"[HATA] Dosya yok: {path}")
        return 1
    digest = sha256_hex(path)
    signature = load_private().sign(digest.encode("ascii"))
    target = path + ".sig"
    with open(target, "w", encoding="ascii") as handle:
        handle.write(base64.b64encode(signature).decode())
    print(f"[OK] SHA-256 : {digest}")
    print(f"[OK] İmza    : {target}")
    print("     Bu dosyayı release'e ASSET olarak yükleyin.")
    return 0


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    if argv[1] == "--init":
        return create_key()
    return sign(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
