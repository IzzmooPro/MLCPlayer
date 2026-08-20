# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Catches an unpublishable version BEFORE it is released.

MEASURED TRAP: `app/updater.is_newer_version()` compares versions
NUMERICALLY (`v0.31` -> `(0, 31, 0)`). That works for the numbering in use
(`v0.3 -> v0.31 -> v0.32`), BUT if `v0.4` were ever released after `v0.31`,
then `31 > 4` and installed copies would NEVER SEE the update; they would
quietly report "you are up to date".

Rather than changing the comparison semantics, the rule is enforced HERE:
the version about to be published must be strictly newer than the already
published one BY THE CLIENT'S OWN measure. A tag that falls into the trap
is stopped before it can become a release.

Exit codes:
    0  publishable (or no network without a matching local release tag)
    1  NOT PUBLISHABLE (clients cannot see this version, or the tag exists)
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import APP_VERSION                      # noqa: E402
from app.updater import GITHUB_REPO, is_newer_version   # noqa: E402

TIMEOUT = 8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def local_tag_exists(version):
    """`True` when this checkout already contains the exact release tag.

    The probe is deliberately read-only and shell-free. `None` means Git or
    the repository state could not be inspected; the remote check still gets
    a chance to decide.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet",
             f"refs/tags/{version}^{{}}"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5, check=False, shell=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def published_tags():
    """Published tags, newest first. `None` when there is no network."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    request = urllib.request.Request(
        url, headers={"User-Agent": f"MLCPlayer/{APP_VERSION}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return [str(item.get("tag_name", "")).strip() for item in data
            if item.get("tag_name")]


def evaluate(version, tags, local_tagged=False):
    """`(publishable, message)`. `tags` is None when there is no network."""
    if local_tagged is True:
        if os.environ.get("MLC_ALLOW_REPUBLISH") == "1":
            return True, (f"[UYARI] {version} YEREL etiketi ZATEN var; "
                          "MLC_ALLOW_REPUBLISH=1 verildigi icin devam "
                          "ediliyor.")
        return False, (f"[HATA] {version} YEREL etiketi ZATEN var. Kabul "
                       "edilmis ayni surum ciktilarini ezmemek icin surumu "
                       "yukseltin; bilincli yeniden uretim icin "
                       "MLC_ALLOW_REPUBLISH=1 gerekir.")
    if tags is None:
        return True, ("[UYARI] GitHub'a ulasilamadi; surum karsilastirmasi "
                      "YAPILAMADI. Yayindan once elle dogrulayin.")
    if version in tags:
        # A deliberate rebuild (for example when only the installer
        # wrapper changed) must not be blocked, but must not pass in
        # silence either.
        if os.environ.get("MLC_ALLOW_REPUBLISH") == "1":
            return True, (f"[UYARI] {version} zaten yayimlanmis; "
                          f"MLC_ALLOW_REPUBLISH=1 verildigi icin devam ediliyor.")
        return False, (f"[HATA] {version} etiketi ZATEN yayimlanmis. Surumu "
                       f"yukseltin veya bilerek yeniden uretiyorsaniz "
                       f"MLC_ALLOW_REPUBLISH=1 ile calistirin.")
    if not tags:
        return True, f"[OK] Ilk yayin: {version}"
    latest = tags[0]
    if not is_newer_version(version, latest):
        return False, (
            f"[HATA] {version}, yayindaki {latest} surumunden YENI DEGIL "
            f"(istemci olcutune gore). Kurulu kopyalar bu guncellemeyi "
            f"GOREMEZ. Ornek: v0.31 varken v0.4 yayimlanamaz; v0.40 kullanin.")
    return True, f"[OK] {version} > {latest} (yayindaki en son surum)"


def main():
    local_tagged = local_tag_exists(APP_VERSION)
    tags = None if local_tagged is True else published_tags()
    publishable, message = evaluate(APP_VERSION, tags, local_tagged)
    print(message)
    return 0 if publishable else 1


if __name__ == "__main__":
    sys.exit(main())
