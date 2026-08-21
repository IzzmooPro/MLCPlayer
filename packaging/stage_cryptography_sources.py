# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Stage the exact OpenSSL and Rust sources declared by cryptography's wheel.

The locked Windows wheel carries two CycloneDX SBOMs.  They are the authority
for the OpenSSL archive and crates actually distributed in ``_rust.pyd``.
The cryptography sdist's Cargo.lock is used as an independent cross-check.

This helper never builds, installs, tags or releases anything.  ``--download``
only fetches missing immutable ``.crate`` source archives into source_mirror.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import tarfile
import tempfile
import tomllib
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_MIRROR = ROOT / "source_mirror"
CONTRACT_PATH = ROOT / "packaging" / "corresponding_sources.json"
EXPECTED_CRYPTOGRAPHY_VERSION = "50.0.0"
EXPECTED_OPENSSL_VERSION = "4.0.1"
CRATE_PURL = re.compile(r"^pkg:cargo/([^@?]+)@([^?]+)$")
TRUSTED_DOWNLOAD_HOSTS = frozenset({"crates.io", "static.crates.io"})


@dataclass(frozen=True)
class CrateSource:
    crate: str
    version: str
    sha256: str

    @property
    def filename(self) -> str:
        return f"rust-crate-{self.crate}-{self.version}.crate"

    @property
    def url(self) -> str:
        crate = urllib.parse.quote(self.crate, safe="-_")
        version = urllib.parse.quote(self.version, safe="-+._")
        return f"https://crates.io/api/v1/crates/{crate}/{version}/download"


def _distribution():
    distribution = importlib.metadata.distribution("cryptography")
    if distribution.version != EXPECTED_CRYPTOGRAPHY_VERSION:
        raise ValueError(
            "locked cryptography version drifted: "
            f"{distribution.version} != {EXPECTED_CRYPTOGRAPHY_VERSION}")
    return distribution


def _sbom(distribution, filename: str):
    relative = (f"cryptography-{EXPECTED_CRYPTOGRAPHY_VERSION}.dist-info/"
                f"sboms/{filename}")
    path = Path(distribution.locate_file(relative))
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("bomFormat") != "CycloneDX":
        raise ValueError(f"unexpected SBOM format: {filename}")
    return payload


def crate_inventory(distribution=None) -> list[CrateSource]:
    distribution = _distribution() if distribution is None else distribution
    payload = _sbom(distribution, "cryptography-rust.cyclonedx.json")
    crates = []
    for component in payload.get("components", []):
        purl = str(component.get("purl", ""))
        if "download_url=file://" in purl:
            continue
        match = CRATE_PURL.match(purl)
        hashes = component.get("hashes", [])
        sha256 = next((str(row.get("content", "")).lower()
                       for row in hashes if row.get("alg") == "SHA-256"), "")
        if not match or len(sha256) != 64:
            raise ValueError(f"invalid Rust SBOM component: {purl!r}")
        int(sha256, 16)
        crates.append(CrateSource(match.group(1), match.group(2), sha256))
    if len(crates) != 32 or len(set(crates)) != len(crates):
        raise ValueError(f"unexpected external Rust crate inventory: {len(crates)}")
    return sorted(crates, key=lambda row: (row.crate, row.version))


def openssl_inventory(distribution=None) -> tuple[str, str, str]:
    distribution = _distribution() if distribution is None else distribution
    payload = _sbom(distribution, "sbom.json")
    components = payload.get("components", [])
    if len(components) != 1:
        raise ValueError("unexpected OpenSSL SBOM inventory")
    component = components[0]
    version = str(component.get("version", ""))
    purl = str(component.get("purl", ""))
    sha256 = next((str(row.get("content", "")).lower()
                   for row in component.get("hashes", [])
                   if row.get("alg") == "SHA-256"), "")
    if version != EXPECTED_OPENSSL_VERSION or len(sha256) != 64:
        raise ValueError("unexpected OpenSSL SBOM component")
    return version, purl, sha256


def locked_crates(sdist: Path) -> list[CrateSource]:
    with tarfile.open(sdist, "r:gz") as archive:
        members = [member for member in archive.getmembers()
                   if member.name.endswith("/Cargo.lock")]
        if len(members) != 1:
            raise ValueError("cryptography sdist must contain one Cargo.lock")
        extracted = archive.extractfile(members[0])
        if extracted is None:
            raise ValueError("Cargo.lock cannot be read")
        payload = tomllib.loads(extracted.read().decode("utf-8"))
    crates = []
    for package in payload.get("package", []):
        if not str(package.get("source", "")).startswith("registry+"):
            continue
        sha256 = str(package.get("checksum", "")).lower()
        crates.append(CrateSource(
            str(package["name"]), str(package["version"]), sha256))
    return sorted(crates, key=lambda row: (row.crate, row.version))


def fingerprint(path: Path) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _download(crate: CrateSource, temporary) -> tuple[int, str]:
    request = urllib.request.Request(
        crate.url,
        headers={"User-Agent": "MLCPlayer-source-audit/0.38"},
    )
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=60) as response:
        final_host = urllib.parse.urlsplit(response.geturl()).hostname or ""
        if final_host not in TRUSTED_DOWNLOAD_HOSTS:
            raise ValueError(f"untrusted crates.io redirect: {final_host}")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            temporary.write(chunk)
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def stage_crate(crate: CrateSource, *, folder=SOURCE_MIRROR,
                allow_download=False, downloader=_download) -> tuple[Path, int]:
    folder = Path(folder)
    target = folder / crate.filename
    try:
        size, digest = fingerprint(target)
    except OSError:
        size, digest = 0, ""
    if digest.lower() == crate.sha256:
        return target, size
    if not allow_download:
        raise ValueError(f"missing or invalid staged crate: {target}")

    folder.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=folder, prefix=f".{crate.filename}.",
                suffix=".tmp", delete=False) as temporary:
            temporary_name = temporary.name
            size, digest = downloader(crate, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        if digest.lower() != crate.sha256:
            raise ValueError(
                f"crate checksum mismatch: {crate.crate} {crate.version}")
        os.replace(temporary_name, target)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                os.remove(temporary_name)
            except OSError:
                pass
    return target, size


def contract_rows(staged: list[tuple[CrateSource, Path, int]]):
    return [{
        "name": crate.filename,
        "url": crate.url,
        "size": size,
        "sha256": crate.sha256,
    } for crate, _path, size in staged]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--print-contract-rows", action="store_true")
    args = parser.parse_args(argv)
    try:
        crates = crate_inventory()
        sdist = SOURCE_MIRROR / (
            f"cryptography-{EXPECTED_CRYPTOGRAPHY_VERSION}.tar.gz")
        if crates != locked_crates(sdist):
            raise ValueError("wheel Rust SBOM and sdist Cargo.lock differ")
        openssl_version, _purl, openssl_sha256 = openssl_inventory()
        openssl = SOURCE_MIRROR / f"openssl-{openssl_version}.tar.gz"
        openssl_size, actual_openssl = fingerprint(openssl)
        if actual_openssl.lower() != openssl_sha256:
            raise ValueError("OpenSSL source does not match the wheel SBOM")

        staged = []
        for crate in crates:
            path, size = stage_crate(crate, allow_download=args.download)
            staged.append((crate, path, size))
    except (OSError, ValueError, tarfile.TarError, tomllib.TOMLDecodeError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"[OK] cryptography {EXPECTED_CRYPTOGRAPHY_VERSION}")
    print(f"[OK] OpenSSL {openssl_version}: {openssl_size} bytes "
          f"sha256:{openssl_sha256}")
    print(f"[OK] {len(staged)} Rust crate sources match wheel SBOM and Cargo.lock")
    if args.print_contract_rows:
        print(json.dumps(contract_rows(staged), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
