# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Official yt-dlp executable source inventory and safe staging contracts."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "packaging" / "stage_ytdlp_sources.py"


def module():
    spec = importlib.util.spec_from_file_location("mlc_stage_ytdlp", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def test_locked_executable_and_official_build_identity_are_explicit():
    stage = module()

    assert stage.EXPECTED_RELEASE == "2026.08.19"
    assert stage.EXPECTED_BUILD_COMMIT == (
        "594bd50c2c78ac432f81600d309fdc4e0a92d82c")
    assert stage.EXPECTED_PYTHON == "3.10.11"
    assert stage.EXPECTED_OPENSSL == "1.1.1t"
    assert stage.EXPECTED_EXE_SHA256 == (
        "66674953fe251b89f4d08c5f0e35e0728679bd67ab3d7d05c0562af101dd3e7a")


def test_official_build_metadata_matches_every_locked_runtime_package():
    stage = module()
    build_archive = ROOT / "source_mirror" / (
        "yt-dlp-build-594bd50c2c78ac432f81600d309fdc4e0a92d82c.tar.gz")
    release_archive = (
        ROOT / "source_mirror" / "yt-dlp-2026.08.19.tar.gz")

    stage.validate_build_metadata(build_archive, release_archive)

    assert len(stage.EXPECTED_RUNTIME_PACKAGES) == 14
    assert stage.EXPECTED_RUNTIME_PACKAGES["curl-cffi"] == "0.16.0"
    assert stage.EXPECTED_RUNTIME_PACKAGES["websockets"] == "16.1.1"


def test_curl_cffi_native_source_archive_carries_every_exact_pin():
    stage = module()
    archive = ROOT / "source_mirror" / (
        "curl_cffi-native-curl-impersonate-v2.0.0.tar.gz")

    stage.validate_native_metadata(archive)


def test_curl_cffi_sdist_selects_the_verified_native_source_release():
    stage = module()

    stage.validate_curl_cffi_metadata(
        ROOT / "source_mirror" / "curl_cffi-0.16.0.tar.gz")


def test_cpython_source_carries_the_six_windows_dependency_pins():
    stage = module()

    stage.validate_cpython_metadata(
        ROOT / "source_mirror" / "Python-3.10.11.tar.xz")


def test_contract_contains_the_complete_ytdlp_inventory():
    stage = module()
    contract = json.loads((
        ROOT / "packaging" / "corresponding_sources.json"
    ).read_text(encoding="utf-8"))
    rows = {row["name"]: row for row in contract["sources"]}

    assert len(stage.SOURCES) == 33
    for source in stage.SOURCES:
        row = rows[source.name]
        assert row["url"] == source.url
        assert row["size"] > 0
        assert row["sha256"] == source.sha256
    assert "yt-dlp" not in " ".join(contract["blockers"]).lower()


def test_source_hosts_are_narrow_and_explicit():
    stage = module()
    from urllib.parse import urlsplit

    for row in stage.SOURCES:
        assert urlsplit(row.url).hostname in stage.TRUSTED_DOWNLOAD_HOSTS


def test_existing_verified_source_needs_no_download(tmp_path):
    stage = module()
    payload = b"source"
    row = stage.Source(
        "source.tar.gz", "https://github.com/example/source.tar.gz",
        hashlib.sha256(payload).hexdigest())
    target = tmp_path / row.name
    target.write_bytes(payload)

    path, size = stage.stage_source(row, folder=tmp_path)

    assert path == target
    assert size == len(payload)


def test_bad_download_does_not_replace_existing_file(tmp_path):
    stage = module()
    expected = b"expected"
    row = stage.Source(
        "source.tar.gz", "https://github.com/example/source.tar.gz",
        hashlib.sha256(expected).hexdigest())
    target = tmp_path / row.name
    target.write_bytes(b"recoverable old file")

    def bad_download(_row, temporary):
        payload = b"wrong"
        temporary.write(payload)
        return len(payload), hashlib.sha256(payload).hexdigest()

    try:
        stage.stage_source(
            row, folder=tmp_path, allow_download=True,
            downloader=bad_download)
    except ValueError:
        pass
    else:
        raise AssertionError("bad source download was accepted")

    assert target.read_bytes() == b"recoverable old file"
