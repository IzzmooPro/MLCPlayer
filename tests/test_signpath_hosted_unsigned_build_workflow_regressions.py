# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-unsigned-main.yml"
CHAIN = ROOT / "packaging" / "build_unsigned_main.bat"
HASH_LOCK = ROOT / "requirements-build-windows.txt"
RUNTIME_LOCK = ROOT / "packaging" / "libmpv_runtime_lock.json"
GIT_ATTRIBUTES = ROOT / ".gitattributes"


def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_hosted_unsigned_build_is_manual_narrow_and_github_hosted():
    text = workflow_text()

    assert "workflow_dispatch:" in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "schedule:" not in text
    assert "runs-on: windows-2025" in text
    assert "contents: read" in text
    assert "packages: read" in text
    permissions = text.split("permissions:", 1)[1].split("concurrency:", 1)[0]
    assert "write" not in permissions
    assert "cancel-in-progress: false" in text


def test_hosted_unsigned_build_pins_actions_python_inno_and_wheels():
    text = workflow_text()

    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in text
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in text
    assert "oras-project/setup-oras@1d808f7d7f6995cc68b7bf507bfe5c5446e1dc9d" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in text
    assert "python-version: '3.13.15'" in text
    assert "6.7.1" in text
    assert "requirements-build-windows.txt" in text
    assert "--require-hashes" in text
    assert "--only-binary=:all:" in text
    assert "verify_dependencies.py requirements-lock.txt" in text


def test_hosted_unsigned_build_reads_inno_engine_version_from_the_compiler():
    text = workflow_text()

    assert "FileVersionInfo" not in text
    assert "ProductVersion" not in text
    assert "Compiler engine version:" in text
    assert "mlc-inno-version-probe.iss" in text
    assert "& $iscc /O- $probePath" in text
    assert "if ($innoExit -ne 0)" in text
    assert "if (-not $innoMatch.Success)" in text
    assert "if ($inno -ne '6.7.1')" in text
    assert "Remove-Item -LiteralPath $probePath" in text


def test_runtime_manifest_is_lf_stable_for_exact_oci_byte_comparison():
    attributes = GIT_ATTRIBUTES.read_text(encoding="utf-8").splitlines()

    assert "bin/RUNTIME_MANIFEST.txt text eol=lf" in attributes


def test_hosted_unsigned_build_pulls_only_the_locked_runtime_digest():
    text = workflow_text().lower()
    lock = json.loads(RUNTIME_LOCK.read_text(encoding="utf-8"))

    assert "libmpv_runtime_lock.json" in text
    assert "oras pull" in text
    assert "repository" in text and "digest" in text
    assert "runtime_sha256" in text and "runtime_size" in text
    assert "runtime_manifest.txt" in text
    assert "source_artifact.json" in text
    assert "mpv-2.dll" in text
    assert lock["digest"].split(":", 1)[1] not in text
    assert "20260821-g49418246f" not in text


def test_hosted_unsigned_build_uploads_exact_unsigned_installer_and_provenance():
    text = workflow_text().lower()

    assert "packaging\\build_unsigned_main.bat" in text
    assert "get-authenticodesignature" in text
    assert "notsigned" in text
    assert "build-provenance.json" in text
    assert "mlcplayer-unsigned-main-" in text
    assert "if-no-files-found: error" in text
    assert "retention-days: 90" in text
    assert "installer_sha256" in text
    assert "runtime_manifest_digest" in text

    for forbidden in (
        "signpath/",
        "sign_release.py",
        "mlc_signing_key",
        "gh release",
        "git tag",
        "mlcplayer_internetvideo",
        "yt-dlp.exe",
        "deno.exe",
    ):
        assert forbidden not in text


def test_unsigned_main_chain_is_isolated_from_release_signing_and_addon():
    text = CHAIN.read_text(encoding="utf-8").lower()

    assert "mlc_hosted_unsigned_build" in text
    assert "--pre-main" in text
    assert "--post" in text
    assert "--final" in text
    assert "mlcplayer.iss" in text
    assert "mlcplayer_setup_" in text
    assert "pyinstaller" in text
    assert "compile_translations.py" in text
    assert "verify_dependencies.py" in text
    assert "if exist \"!main_setup!.sig\"" in text

    for forbidden in (
        "sign_release.py",
        "mlc_signing_key",
        "mlcplayer_internetvideo.iss",
        "addon_setup",
        "check_publishable.py",
    ):
        assert forbidden not in text


def test_windows_build_hash_lock_matches_every_exact_dependency_pin():
    source_pins = {}
    for raw in (ROOT / "requirements-lock.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            name, version = line.split("==", 1)
            source_pins[re.sub(r"[-_.]+", "-", name).lower()] = version

    locked = {}
    current = None
    for raw in HASH_LOCK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("--hash=sha256:"):
            assert current is not None
            digest = line.removeprefix("--hash=sha256:")
            assert re.fullmatch(r"[0-9a-f]{64}", digest)
            locked[current][1].append(digest)
            continue
        assert line.endswith("\\")
        name, version = line[:-1].strip().split("==", 1)
        current = re.sub(r"[-_.]+", "-", name).lower()
        assert current not in locked
        locked[current] = [version, []]

    assert {name: value[0] for name, value in locked.items()} == source_pins
    assert all(len(value[1]) == 1 for value in locked.values())
