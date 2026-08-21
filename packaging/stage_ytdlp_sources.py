# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Stage the exact sources represented by the locked official yt-dlp EXE.

The official Windows executable is a PyInstaller bundle.  Its runtime report,
the yt-dlp build commit's hashed requirements, CPython's Windows dependency
pins and curl-impersonate's CMake source pins form one fail-closed inventory.

This helper never builds or installs anything.  ``--download`` only fetches
missing immutable source archives into ``source_mirror`` and verifies SHA-256
before replacing a target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_MIRROR = ROOT / "source_mirror"
EXE = ROOT / "bin" / "yt-dlp.exe"
NOTICE = ROOT / "licenses" / "yt-dlp-THIRD_PARTY_LICENSES.txt"
EXPECTED_EXE_SHA256 = (
    "66674953fe251b89f4d08c5f0e35e0728679bd67ab3d7d05c0562af101dd3e7a")
EXPECTED_RELEASE = "2026.08.19"
EXPECTED_BUILD_COMMIT = "594bd50c2c78ac432f81600d309fdc4e0a92d82c"
EXPECTED_PYTHON = "3.10.11"
EXPECTED_OPENSSL = "1.1.1t"
TRUSTED_DOWNLOAD_HOSTS = frozenset({
    "codeload.github.com",
    "files.pythonhosted.org",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "www.python.org",
})

EXPECTED_RUNTIME_PACKAGES = {
    "brotli": "1.2.0",
    "certifi": "2026.7.22",
    "cffi": "2.1.1",
    "charset-normalizer": "3.5.0",
    "curl-cffi": "0.16.0",
    "idna": "3.18",
    "mutagen": "1.48.1",
    "pycparser": "3.0",
    "pycryptodomex": "3.23.0",
    "requests": "2.34.2",
    "typing-extensions": "4.16.0",
    "urllib3": "2.7.0",
    "websockets": "16.1.1",
    "yt-dlp-ejs": "0.8.0",
}


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    sha256: str


def source(name: str, url: str, sha256: str) -> Source:
    return Source(name, url, sha256)


SOURCES = (
    source("yt-dlp-2026.08.19.tar.gz",
           "https://github.com/yt-dlp/yt-dlp/releases/download/2026.08.19/yt-dlp.tar.gz",
           "072aad4f2a7604e92155f61a275a4752dc64046c8f6d90df3710525d94cd37c1"),
    source("yt-dlp-build-594bd50c2c78ac432f81600d309fdc4e0a92d82c.tar.gz",
           "https://codeload.github.com/yt-dlp/yt-dlp/tar.gz/594bd50c2c78ac432f81600d309fdc4e0a92d82c",
           "9434bc31521a5ce0badaaa7315cd4e687c837a722d4e6f60b6f78725f8b83163"),
    source("brotli-1.2.0.tar.gz",
           "https://files.pythonhosted.org/packages/f7/16/c92ca344d646e71a43b8bb353f0a6490d7f6e06210f8554c8f874e454285/brotli-1.2.0.tar.gz",
           "e310f77e41941c13340a95976fe66a8a95b01e783d430eeaf7a2f87e0a57dd0a"),
    source("certifi-2026.7.22.tar.gz",
           "https://files.pythonhosted.org/packages/a3/c2/24167ea9858356b47a87a50d39908bfdb72ceeefe0041586e704e5376b3a/certifi-2026.7.22.tar.gz",
           "741e2c3b351ddf169a738da9f2c048608ff7f2c5cc02f1ebc6b118bb090d5d55"),
    source("cffi-2.1.1.tar.gz",
           "https://files.pythonhosted.org/packages/9e/ef/008a1939e372c06329a3fce4279c02f328488f3526744906eeec3da7ad5f/cffi-2.1.1.tar.gz",
           "dd31f52ea1086513bb9df30f8fcee9b8918323ae067a3d5b78bc826a000712be"),
    source("charset_normalizer-3.5.0.tar.gz",
           "https://files.pythonhosted.org/packages/cb/31/4971872b3ed8715346231fb6eb4da8fcba65a4143c189db151ee28a2812b/charset_normalizer-3.5.0.tar.gz",
           "49bd5feb59b0bf3cbf6ebcf4352e371c95b9da9bacd4449f8b64d0ad2c10a26e"),
    source("curl_cffi-0.16.0.tar.gz",
           "https://files.pythonhosted.org/packages/b4/23/d32e113b16dbfb458bea408871ed98dd12f306a366a04215e84537e0af7e/curl_cffi-0.16.0.tar.gz",
           "b00b423da8028eb6221e3b63bcd63d681150c07cee8b16000d1f7ea292731895"),
    source("idna-3.18.tar.gz",
           "https://files.pythonhosted.org/packages/cd/63/9496c57188a2ee585e0f1db071d75089a11e98aa86eb99d9d7618fc1edce/idna-3.18.tar.gz",
           "ffb385a7e039654cef1ab9ef32c6fafe283c0c0467bba1d9029738ce4a14a848"),
    source("mutagen-1.48.1.tar.gz",
           "https://files.pythonhosted.org/packages/df/70/1675da133ea92227da41bf5b24e1c66be597ff736a1533ade41da986852f/mutagen-1.48.1.tar.gz",
           "8f95637ab9f6f305cec6bd1294e197debe207998e3e068596563c74f86b0a173"),
    source("pycparser-3.0.tar.gz",
           "https://files.pythonhosted.org/packages/1b/7d/92392ff7815c21062bea51aa7b87d45576f649f16458d78b7cf94b9ab2e6/pycparser-3.0.tar.gz",
           "600f49d217304a5902ac3c37e1281c9fe94e4d0489de643a9504c5cdfdfc6b29"),
    source("pycryptodomex-3.23.0.tar.gz",
           "https://files.pythonhosted.org/packages/c9/85/e24bf90972a30b0fcd16c73009add1d7d7cd9140c2498a68252028899e41/pycryptodomex-3.23.0.tar.gz",
           "71909758f010c82bc99b0abf4ea12012c98962fbf0583c2164f8b84533c2e4da"),
    source("requests-2.34.2.tar.gz",
           "https://files.pythonhosted.org/packages/ac/c3/e2a2b89f2d3e2179abd6d00ebd70bff6273f37fb3e0cc209f48b39d00cbf/requests-2.34.2.tar.gz",
           "f288924cae4e29463698d6d60bc6a4da69c89185ad1e0bcc4104f584e960b9ed"),
    source("typing_extensions-4.16.0.tar.gz",
           "https://files.pythonhosted.org/packages/f6/cc/6253133b5bb138fc3306cebfbda2c520f545d36b5be2c7255cc528bb45d6/typing_extensions-4.16.0.tar.gz",
           "dc983d19a509c94dba722ee6abd33940f7c05a89e243c47e907eb4db6f1a43e5"),
    source("urllib3-2.7.0.tar.gz",
           "https://files.pythonhosted.org/packages/53/0c/06f8b233b8fd13b9e5ee11424ef85419ba0d8ba0b3138bf360be2ff56953/urllib3-2.7.0.tar.gz",
           "231e0ec3b63ceb14667c67be60f2f2c40a518cb38b03af60abc813da26505f4c"),
    source("websockets-16.1.1.tar.gz",
           "https://files.pythonhosted.org/packages/21/f7/bc3a25c5ec26ce62ce487690becc2f3710bbc7b33338f005ad390db0b986/websockets-16.1.1.tar.gz",
           "db234eda965dcce15df96bb9709f587cd87d4d52aaf0e80e2f34ec04c7670c57"),
    source("yt_dlp_ejs-0.8.0.tar.gz",
           "https://files.pythonhosted.org/packages/d3/e6/cceb9530e8f4e5940f6f7822d90e9d94f1b85343329a16baaf47bbbb3de1/yt_dlp_ejs-0.8.0.tar.gz",
           "d5fa1639f63b5c4af8d932495f60689d5370f1a095782c944f7f62a303eb104e"),
    source("Python-3.10.11.tar.xz",
           "https://www.python.org/ftp/python/3.10.11/Python-3.10.11.tar.xz",
           "3c3bc3048303721c904a03eb8326b631e921f11cc3be2988456a42f115daf04c"),
    source("cpython-bzip2-05301997b2f9590f49c672cf3dfd3d3dfa7ad521.tar.gz",
           "https://codeload.github.com/python/cpython-source-deps/tar.gz/05301997b2f9590f49c672cf3dfd3d3dfa7ad521",
           "ab14accac86cdd92021d50465deeb221b476d6675bd1383d3c7fb83751c2e0a3"),
    source("cpython-libffi-35a5081d073058159e8db96c43029f88c1da501a.tar.gz",
           "https://codeload.github.com/python/cpython-source-deps/tar.gz/35a5081d073058159e8db96c43029f88c1da501a",
           "34e0130e4065b0efc71a6c5af75e9b451c96a9a8f8418e911c59b7dc6f2452e4"),
    source("cpython-openssl-82bfdc9e019e4892c5bd8f90b71c42fbf79f29d0.tar.gz",
           "https://codeload.github.com/python/cpython-source-deps/tar.gz/82bfdc9e019e4892c5bd8f90b71c42fbf79f29d0",
           "e5aa38e691368396daed27e4f336f5f0f5ca0ff8c6f7f673394500224079e654"),
    source("cpython-sqlite-db4ca556b25787c263ee72a4b764c4be474c322f.tar.gz",
           "https://codeload.github.com/python/cpython-source-deps/tar.gz/db4ca556b25787c263ee72a4b764c4be474c322f",
           "61a33a1f61b30617564ae869296339b19dfd30b9b32a0e1b3493d8b93b23b54c"),
    source("cpython-xz-c6bc0c612605622aaef101a33a751f9de2ecc193.tar.gz",
           "https://codeload.github.com/python/cpython-source-deps/tar.gz/c6bc0c612605622aaef101a33a751f9de2ecc193",
           "115433c946ee069e857fd04cf41b38a4a74ed45d868a3b2e08ccd4a1f04f39d0"),
    source("cpython-zlib-9071e5ae1bd90c30518404b95ec0be0d4cf6cf84.tar.gz",
           "https://codeload.github.com/python/cpython-source-deps/tar.gz/9071e5ae1bd90c30518404b95ec0be0d4cf6cf84",
           "0200469024cfc47334c7f6a28855a54d33740a7207d1b9e860fbbaf0bebfca63"),
    source("pyinstaller-6.22.0.tar.gz",
           "https://github.com/yt-dlp/Pyinstaller-Builds/releases/download/2026.08.19.215425/pyinstaller-6.22.0.tar.gz",
           "2fadbed5d951d53f003ed899312823a07dbba59990a223cbe538933e1c42a168"),
    source("curl_cffi-native-curl-impersonate-v2.0.0.tar.gz",
           "https://codeload.github.com/lexiforest/curl-impersonate/tar.gz/refs/tags/v2.0.0",
           "a9827cfce8246e78b86e26f012ae9fcb9bc05822009cd7ce4c9e130af6bdfb6f"),
    source("curl-8.21.0.tar.gz",
           "https://github.com/curl/curl/archive/curl-8_21_0.tar.gz",
           "ec753aa6f408a3ca9f0d6d5f7a77417aecd1544db13c03ae5d443612bf367364"),
    source("google-brotli-1.2.0.tar.gz",
           "https://github.com/google/brotli/archive/refs/tags/v1.2.0.tar.gz",
           "816c96e8e8f193b40151dad7e8ff37b1221d019dbcb9c35cd3fadbfe6477dfec"),
    source("boringssl-156c7b75ae9b8c3b3f847acf264f17594c3859fb.zip",
           "https://github.com/google/boringssl/archive/156c7b75ae9b8c3b3f847acf264f17594c3859fb.zip",
           "450e169b284697c6eafe523cb7679f4221fbe1a0993f773a566c33b188762844"),
    source("nghttp2-1.63.0.tar.bz2",
           "https://github.com/nghttp2/nghttp2/releases/download/v1.63.0/nghttp2-1.63.0.tar.bz2",
           "607b174554d22a828bc532d1d734fe0f729b5d5ed207f2f12e96a62e83f29c55"),
    source("ngtcp2-1.20.0.tar.bz2",
           "https://github.com/ngtcp2/ngtcp2/releases/download/v1.20.0/ngtcp2-1.20.0.tar.bz2",
           "871ec97ad86803cf312901b0c393b0ee70163e25a87c9b2894d1234341ce4e97"),
    source("nghttp3-1.15.0.tar.bz2",
           "https://github.com/ngtcp2/nghttp3/releases/download/v1.15.0/nghttp3-1.15.0.tar.bz2",
           "c6c491a52804814098e446630e6efc459afc0d3da7952ffe6cbdc0b3f99b2b62"),
    source("zlib-1.3.1.tar.gz",
           "https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz",
           "9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23"),
    source("zstd-1.5.7.tar.gz",
           "https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz",
           "eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3"),
)


def fingerprint(path: Path) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _download(row: Source, temporary) -> tuple[int, str]:
    request = urllib.request.Request(
        row.url, headers={"User-Agent": "MLCPlayer-source-audit/0.38"})
    size = 0
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=90) as response:
        host = urllib.parse.urlsplit(response.geturl()).hostname or ""
        if host not in TRUSTED_DOWNLOAD_HOSTS:
            raise ValueError(f"untrusted source redirect: {host}")
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            temporary.write(chunk)
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def stage_source(row: Source, *, folder=SOURCE_MIRROR,
                 allow_download=False, downloader=_download) -> tuple[Path, int]:
    folder = Path(folder)
    target = folder / row.name
    try:
        size, digest = fingerprint(target)
    except OSError:
        size, digest = 0, ""
    if digest.lower() == row.sha256:
        return target, size
    if not allow_download:
        raise ValueError(f"missing or invalid staged yt-dlp source: {target}")

    folder.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=folder, prefix=f".{row.name}.",
                suffix=".tmp", delete=False) as temporary:
            temporary_name = temporary.name
            size, digest = downloader(row, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        if digest.lower() != row.sha256:
            raise ValueError(f"source checksum mismatch: {row.name}")
        os.replace(temporary_name, target)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                os.remove(temporary_name)
            except OSError:
                pass
    return target, size


def _archive_member(archive: Path, suffix: str) -> str:
    with tarfile.open(archive, "r:*") as handle:
        members = [member for member in handle.getmembers()
                   if member.name.endswith(suffix)]
        if len(members) != 1:
            raise ValueError(f"archive member is not unique: {suffix}")
        extracted = handle.extractfile(members[0])
        if extracted is None:
            raise ValueError(f"archive member cannot be read: {suffix}")
        return extracted.read().decode("utf-8")


def validate_build_metadata(build_archive: Path, release_archive: Path) -> None:
    # update-version.py generates the release identity after checkout.  The
    # commit archive is authoritative for locks/workflow, while the published
    # release tar is authoritative for the generated version.py.
    version = _archive_member(release_archive, "/yt_dlp/version.py")
    requirements = _archive_member(
        build_archive, "/bundle/requirements/curl-cffi.txt")
    pyinstaller = _archive_member(
        build_archive, "/bundle/requirements/win-x64-pyinstaller.txt")
    workflow = _archive_member(build_archive, "/.github/workflows/build.yml")
    if EXPECTED_RELEASE not in version or EXPECTED_BUILD_COMMIT not in version:
        raise ValueError("yt-dlp published release identity drifted")
    if ("devscripts/update-version.py" not in workflow
            or 'python_version: \'3.10\'' not in workflow):
        raise ValueError("yt-dlp Windows release workflow drifted")
    normalized = requirements.lower().replace("_", "-")
    for name, package_version in EXPECTED_RUNTIME_PACKAGES.items():
        if not re.search(
                rf"(?m)^{re.escape(name)}=={re.escape(package_version)}(?:\s|$)",
                normalized):
            raise ValueError(f"yt-dlp runtime lock drifted: {name}")
    required_pyinstaller = (
        "2026.08.19.215425/pyinstaller-6.22.0-py3-none-win_amd64.whl")
    if required_pyinstaller not in pyinstaller:
        raise ValueError("yt-dlp PyInstaller build lock drifted")


def validate_native_metadata(archive: Path) -> None:
    cmake = _archive_member(archive, "/CMakeLists.txt")
    required = (
        'set(BROTLI_VERSION "1.2.0")',
        'set(BROTLI_URL_HASH "SHA256=816c96e8e8f193b40151dad7e8ff37b1221d019dbcb9c35cd3fadbfe6477dfec")',
        'set(BORINGSSL_COMMIT "156c7b75ae9b8c3b3f847acf264f17594c3859fb")',
        'set(BORINGSSL_URL_HASH "SHA256=450e169b284697c6eafe523cb7679f4221fbe1a0993f773a566c33b188762844")',
        'set(NGHTTP2_VERSION "1.63.0")',
        'set(NGHTTP2_URL_HASH "SHA256=607b174554d22a828bc532d1d734fe0f729b5d5ed207f2f12e96a62e83f29c55")',
        'set(NGTCP2_VERSION "1.20.0")',
        'set(NGTCP2_URL_HASH "SHA256=871ec97ad86803cf312901b0c393b0ee70163e25a87c9b2894d1234341ce4e97")',
        'set(NGHTTP3_VERSION "1.15.0")',
        'set(NGHTTP3_URL_HASH "SHA256=c6c491a52804814098e446630e6efc459afc0d3da7952ffe6cbdc0b3f99b2b62")',
        'set(ZLIB_VERSION "1.3.1")',
        'set(ZLIB_URL_HASH "SHA256=9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23")',
        'set(ZSTD_VERSION "1.5.7")',
        'set(ZSTD_URL_HASH "SHA256=eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3")',
        'set(CURL_VERSION "curl-8_21_0")',
        'set(CURL_URL_HASH "SHA256=ec753aa6f408a3ca9f0d6d5f7a77417aecd1544db13c03ae5d443612bf367364")',
    )
    missing = [line for line in required if line not in cmake]
    if missing:
        raise ValueError(f"curl-impersonate native lock drifted: {missing[0]}")


def validate_curl_cffi_metadata(archive: Path) -> None:
    makefile = _archive_member(archive, "/Makefile")
    for line in ("VERSION := 2.0.0", "CURL_VERSION := curl-8_21_0"):
        if line not in makefile:
            raise ValueError(f"curl_cffi native source pin drifted: {line}")


def validate_cpython_metadata(archive: Path) -> None:
    externals = _archive_member(archive, "/PCbuild/get_externals.bat")
    expected = (
        "bzip2-1.0.8",
        "libffi-3.3.0",
        "openssl-1.1.1t",
        "sqlite-3.40.1.0",
        "xz-5.2.5",
        "zlib-1.2.13",
    )
    missing = [pin for pin in expected if pin not in externals]
    if missing:
        raise ValueError(f"CPython Windows source pin drifted: {missing[0]}")


def validate_distribution() -> None:
    _size, digest = fingerprint(EXE)
    if digest.lower() != EXPECTED_EXE_SHA256:
        raise ValueError("locked yt-dlp.exe hash drifted")
    notice = NOTICE.read_text(encoding="utf-8")
    for heading in (
            "Python | PSF-2.0", "OpenSSL 1.x | OpenSSL",
            "curl-impersonate | MIT", "BoringSSL | Apache-2.0",
            "curl_cffi | MIT", "PyCryptodome | Public Domain and BSD-2-Clause"):
        if heading not in notice:
            raise ValueError(f"yt-dlp third-party notice drifted: {heading}")


def contract_rows(staged: list[tuple[Source, Path, int]]) -> list[dict]:
    return [{
        "name": row.name,
        "url": row.url,
        "size": size,
        "sha256": row.sha256,
    } for row, _path, size in staged]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--print-contract-rows", action="store_true")
    args = parser.parse_args(argv)
    try:
        validate_distribution()
        staged = []
        for row in SOURCES:
            path, size = stage_source(row, allow_download=args.download)
            staged.append((row, path, size))
        build = SOURCE_MIRROR / (
            "yt-dlp-build-594bd50c2c78ac432f81600d309fdc4e0a92d82c.tar.gz")
        release = SOURCE_MIRROR / "yt-dlp-2026.08.19.tar.gz"
        validate_build_metadata(build, release)
        native = SOURCE_MIRROR / (
            "curl_cffi-native-curl-impersonate-v2.0.0.tar.gz")
        validate_native_metadata(native)
        validate_curl_cffi_metadata(
            SOURCE_MIRROR / "curl_cffi-0.16.0.tar.gz")
        validate_cpython_metadata(
            SOURCE_MIRROR / "Python-3.10.11.tar.xz")
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"[OK] yt-dlp {EXPECTED_RELEASE} EXE sha256:{EXPECTED_EXE_SHA256}")
    print(f"[OK] Python {EXPECTED_PYTHON} / OpenSSL {EXPECTED_OPENSSL}")
    print(f"[OK] {len(EXPECTED_RUNTIME_PACKAGES)} locked runtime packages")
    print(f"[OK] {len(staged)} corresponding-source archives")
    if args.print_contract_rows:
        print(json.dumps(contract_rows(staged), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
