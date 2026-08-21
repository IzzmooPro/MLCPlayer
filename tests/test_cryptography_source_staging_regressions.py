# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Cryptography wheel source inventory and safe crate staging contracts."""

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "packaging" / "stage_cryptography_sources.py"


def module():
    spec = importlib.util.spec_from_file_location(
        "mlc_stage_cryptography", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def crate(stage, payload=b"crate source"):
    return stage.CrateSource(
        "example", "1.2.3", hashlib.sha256(payload).hexdigest())


def test_locked_wheel_carries_the_expected_rust_and_openssl_sboms():
    stage = module()
    crates = stage.crate_inventory()
    version, purl, digest = stage.openssl_inventory()

    assert len(crates) == 32
    assert len({(row.crate, row.version) for row in crates}) == 32
    assert version == "4.0.1"
    assert "openssl-4.0.1.tar.gz" in purl
    assert digest == (
        "2db3f3a0d6ea4b59e1f094ace2c8cd536dffb87cdc39084c5afa1e6f7f37dd09")


def test_every_crate_uses_the_official_versioned_registry_endpoint():
    stage = module()
    for row in stage.crate_inventory():
        assert row.filename == (
            f"rust-crate-{row.crate}-{row.version}.crate")
        assert row.url == (
            f"https://crates.io/api/v1/crates/{row.crate}/"
            f"{row.version}/download")
    assert stage.TRUSTED_DOWNLOAD_HOSTS == {"crates.io", "static.crates.io"}


def test_contract_matches_every_crate_in_the_locked_wheel_sbom():
    stage = module()
    contract = json.loads((
        ROOT / "packaging" / "corresponding_sources.json"
    ).read_text(encoding="utf-8"))
    rows = {row["name"]: row for row in contract["sources"]
            if row["name"].startswith("rust-crate-")}
    crates = stage.crate_inventory()

    assert len(rows) == len(crates) == 32
    for crate_row in crates:
        row = rows[crate_row.filename]
        assert row["url"] == crate_row.url
        assert row["size"] > 0
        assert row["sha256"] == crate_row.sha256


def test_contract_openssl_source_matches_the_locked_wheel_sbom():
    stage = module()
    version, _purl, digest = stage.openssl_inventory()
    contract = json.loads((
        ROOT / "packaging" / "corresponding_sources.json"
    ).read_text(encoding="utf-8"))
    row = next(row for row in contract["sources"]
               if row["name"] == f"openssl-{version}.tar.gz")

    assert row["size"] == 55079428
    assert row["sha256"] == digest


def test_existing_verified_crate_needs_no_download(tmp_path):
    stage = module()
    payload = b"crate source"
    row = crate(stage, payload)
    target = tmp_path / row.filename
    target.write_bytes(payload)

    path, size = stage.stage_crate(row, folder=tmp_path)

    assert path == target
    assert size == len(payload)


def test_wrong_download_never_overwrites_an_existing_target(tmp_path):
    stage = module()
    row = crate(stage)
    target = tmp_path / row.filename
    target.write_bytes(b"recoverable old file")

    def wrong_download(_crate, temporary):
        payload = b"wrong"
        temporary.write(payload)
        return len(payload), hashlib.sha256(payload).hexdigest()

    try:
        stage.stage_crate(
            row, folder=tmp_path, allow_download=True,
            downloader=wrong_download)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong crate source was accepted")

    assert target.read_bytes() == b"recoverable old file"


def test_cargo_lock_parser_selects_only_registry_sources(tmp_path):
    stage = module()
    lock = b'''version = 4

[[package]]
name = "registry-crate"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

[[package]]
name = "local-crate"
version = "1.0.0"
'''
    archive = tmp_path / "cryptography.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("cryptography/Cargo.lock")
        info.size = len(lock)
        handle.addfile(info, io.BytesIO(lock))

    assert stage.locked_crates(archive) == [stage.CrateSource(
        "registry-crate", "1.0.0", "a" * 64)]
