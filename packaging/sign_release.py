# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Release signing tool (Ed25519).

    python packaging/sign_release.py --init
        GENERATES the publisher key pair. The private key is kept OUTSIDE
        the repository; the public key is printed and embedded by hand into
        `app/release_signature.py`.

    python packaging/sign_release.py installer_output/MLCPlayer_Setup_vX.exe
        Signs the file's SHA-256 digest and writes `<file>.sig`. That file
        MUST be uploaded to the release as an asset; the updater downloads
        it and verifies it against the embedded public key.

THE PRIVATE KEY NEVER ENTERS THE REPOSITORY. Default location:
    %USERPROFILE%\\.mlcplayer\\release_ed25519.key
`MLC_SIGNING_KEY` can point somewhere else.
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
        print(f"[ERROR] A key already exists: {path}")
        print("        Generating a new one INVALIDATES every existing")
        print("        signature; move the file by hand and update the")
        print("        embedded public key as well.")
        return 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes_raw()
    with open(path, "wb") as handle:
        handle.write(base64.b64encode(raw))
    public = base64.b64encode(private.public_key().public_bytes_raw()).decode()
    print(f"[OK] Private key written: {path}")
    print("     BACK THIS FILE UP and do NOT add it to the repository.")
    print()
    print("Public key to embed into app/release_signature.py:")
    print(f'RELEASE_PUBLIC_KEY = "{public}"')
    return 0


def load_private():
    path = key_path()
    if not os.path.exists(path):
        raise SystemExit(f"[ERROR] No private key: {path}\n"
                         f"        Run first: python packaging/sign_release.py --init")
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
        print(f"[ERROR] No such file: {path}")
        return 1
    digest = sha256_hex(path)
    signature = load_private().sign(digest.encode("ascii"))
    target = path + ".sig"
    with open(target, "w", encoding="ascii") as handle:
        handle.write(base64.b64encode(signature).decode())
    print(f"[OK] SHA-256 : {digest}")
    print(f"[OK] Signature: {target}")
    print("     Upload this file to the release as an asset.")
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
