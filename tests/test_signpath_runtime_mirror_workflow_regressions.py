# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-libmpv-runtime.yml"
LOCK = ROOT / "packaging" / "libmpv_runtime_lock.json"


def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_runtime_mirror_is_manual_and_has_narrow_permissions():
    text = workflow_text()

    assert "workflow_dispatch:" in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "schedule:" not in text
    assert "contents: read" in text
    assert "actions: read" in text
    assert "packages: write" in text
    assert "cancel-in-progress: false" in text


def test_runtime_mirror_pins_the_expiring_source_artifact_and_binary_identity():
    text = workflow_text()

    for value in (
        "9452521445",
        "32488810460",
        "4b948676990dde217206b878fca388093a367b61",
        "2026-09-20T15:35:47Z",
        "29427624",
        "024f4e98884db6074e956d4f5001040836bfa395cdc90e6bd5c20634b881297e",
        "112772608",
        "de80329f5c019ba2ee48184b5dc1e1d0c2ee9eeba3f1fb7959f20b4b0f684f4e",
    ):
        assert value.lower() in text.lower()

    assert "artifact['expired']" in text
    assert "workflow_run" in text
    assert "head_sha" in text


def test_runtime_mirror_uses_immutable_actions_and_fail_closed_oci_readback():
    text = workflow_text()

    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in text
    assert "oras-project/setup-oras@1d808f7d7f6995cc68b7bf507bfe5c5446e1dc9d" in text
    assert "version: 1.3.3" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in text
    assert "ghcr.io/izzmoopro/mlcplayer-libmpv-runtime" in text
    assert "oras resolve" in text
    assert "oras push" in text
    assert "oras pull" in text
    assert "org.opencontainers.image.source" in text
    assert "already exists" in text
    assert "cmp --silent" in text
    assert "runtime-lock.json" in text


def test_runtime_mirror_neither_rebuilds_nor_signs_nor_mutates_releases():
    text = workflow_text().lower()

    for forbidden in (
        "signpath",
        "sign_release.py",
        "gh release",
        "git tag",
        "ninja -c",
        "cmake --build",
    ):
        assert forbidden not in text

    assert "libmpv-2.dll" in text
    assert "mpv-2.dll" in text
    assert "runtime_manifest.txt" in text
    assert "sha256sums.txt" in text


def test_runtime_lock_records_the_hosted_digest_and_exact_source_identity():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))

    assert lock == {
        "artifact_type": "application/vnd.mlcplayer.libmpv.runtime.v1",
        "digest": "sha256:f33b793c23505fd2f752f65f03e0545c14c85915c9f6eef5abffab1443410518",
        "repository": "ghcr.io/izzmoopro/mlcplayer-libmpv-runtime",
        "runtime_name": "mpv-2.dll",
        "runtime_sha256": "de80329f5c019ba2ee48184b5dc1e1d0c2ee9eeba3f1fb7959f20b4b0f684f4e",
        "runtime_size": 112772608,
        "schema_version": 1,
        "source_artifact_id": 9452521445,
        "source_expires_at": "2026-09-20T15:35:47Z",
        "source_head_sha": "4b948676990dde217206b878fca388093a367b61",
        "source_run_id": 32488810460,
        "tag": "ghcr.io/izzmoopro/mlcplayer-libmpv-runtime:20260821-g49418246f",
    }

    workflow = workflow_text().lower()
    for key in (
        "digest",
        "runtime_sha256",
        "runtime_size",
        "source_artifact_id",
        "source_head_sha",
        "source_run_id",
        "tag",
    ):
        assert str(lock[key]).lower() in workflow or key == "digest"
