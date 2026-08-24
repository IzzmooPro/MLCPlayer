# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Executable, fail-closed identity gates for video-format fixtures."""

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "VIDEO_FORMAT_MEDIA_MANIFEST.json"
sys.path.insert(0, str(ROOT / "scripts"))
import verify_video_format_media as guard  # noqa: E402


PROBE = {
    "streams": [{
        "index": 0,
        "codec_name": "h264",
        "profile": "High",
        "codec_tag_string": "avc1",
        "width": 640,
        "height": 360,
        "pix_fmt": "yuv420p",
        "color_range": "tv",
        "color_space": "bt709",
        "color_transfer": "bt709",
        "color_primaries": "bt709",
        "r_frame_rate": "30/1",
        "avg_frame_rate": "30/1",
        "time_base": "1/15360",
    }],
    "frames": [{"media_type": "video", "stream_index": 0}],
    "format": {
        "filename": "C:\\private\\fixture.mp4",
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "3.000000",
        "size": "7",
    },
}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def record(media, ffprobe, generator, probe):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    candidate = next(item for item in manifest["candidates"]
                     if item["id"] == "SYN-SDR709-01")
    source = next(item for item in manifest["sources"]
                  if item["id"] == candidate["source_id"])
    probe_hash = guard.canonical_json_sha256(
        guard.normalize_ffprobe(probe))
    generation = {
        "generator_binary_sha256": guard.sha256_file(generator),
        "generator_version": "ffmpeg version test",
        "generator_argv": copy.deepcopy(
            candidate["validation_contract"]["generator_argv"]),
        "input_and_sidecar_sha256": [],
    }
    generation["canonical_recipe_sha256"] = (
        guard.recipe_sha256(generation))
    return {
        "candidate_id": "SYN-SDR709-01",
        "source_id": "mlc_project_generated_fixture",
        "state": "fingerprinted",
        "exact_object_locator": "private-local:SYN-SDR709-01",
        "license_or_use_basis": source["license_or_use_basis"],
        "file_size": media.stat().st_size,
        "sha256": guard.sha256_file(media),
        "ffprobe_binary_sha256": guard.sha256_file(ffprobe),
        "ffprobe_version": "ffprobe version test",
        "ffprobe_argv": list(guard.FFPROBE_ARGV),
        "normalized_ffprobe_json_sha256": probe_hash,
        "normalized_ffprobe_json_artifact": "private:SYN-SDR709-01.ffprobe.json",
        "selected_video_stream": 0,
        "verified_claims": copy.deepcopy(
            candidate["validation_contract"]["expected_claims"]),
        "generation_identity": generation,
    }


def enabled_manifest(ffprobe, generator, payload):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["fingerprinted_state_enabled"] = True
    manifest["fingerprint_validator"]["live_tool_validation_completed"] = True
    manifest["fingerprint_validator"]["approved_tools"] = {
        "ffprobe": {
            "sha256": guard.sha256_file(ffprobe),
            "version": "ffprobe version test",
        },
        "generator": {
            "sha256": guard.sha256_file(generator),
            "version": "ffmpeg version test",
        },
    }
    candidate = next(item for item in manifest["candidates"]
                     if item["id"] == "SYN-SDR709-01")
    candidate["state"] = "fingerprinted"
    candidate["local_identity"] = {
        key: copy.deepcopy(payload.get(key))
        for key in guard.LOCAL_IDENTITY_FIELDS
    }
    candidate["generation_identity"] = copy.deepcopy(
        payload["generation_identity"])
    return manifest


@pytest.fixture
def fixture_files(tmp_path):
    media = tmp_path / "fixture.mp4"
    ffprobe = tmp_path / "ffprobe.exe"
    generator = tmp_path / "ffmpeg.exe"
    probe_artifact = tmp_path / "probe.json"
    media.write_bytes(b"fixture")
    ffprobe.write_bytes(b"probe-tool")
    generator.write_bytes(b"generator-tool")
    probe_artifact.write_text(json.dumps(PROBE), encoding="utf-8")
    return media, ffprobe, generator, probe_artifact


def verify(fixture_files, payload=None, live_probe=None):
    media, ffprobe, generator, probe_artifact = fixture_files
    payload = record(media, ffprobe, generator, PROBE) if payload is None else payload
    return guard.verify_record(
        payload,
        manifest=enabled_manifest(ffprobe, generator, payload),
        media_path=media,
        ffprobe_path=ffprobe,
        generator_path=generator,
        probe_artifact_path=probe_artifact,
        probe_runner=lambda _tool, _media, _argv: (
            PROBE if live_probe is None else live_probe),
        regenerator=lambda _tool, _argv: {
            "file_size": media.stat().st_size,
            "sha256": guard.sha256_file(media),
        },
        version_reader=lambda tool: (
            "ffprobe version test" if tool == ffprobe
            else "ffmpeg version test"),
    )


def test_exact_bytes_probe_recipe_and_sdr_claims_pass(fixture_files):
    result = verify(fixture_files)
    assert result["candidate_id"] == "SYN-SDR709-01"
    assert result["normalized_ffprobe_json_sha256"] == (
        record(*fixture_files[:3], PROBE)[
            "normalized_ffprobe_json_sha256"])


def test_sdr_recipe_sets_frame_colour_metadata_before_encoding():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    candidate = next(item for item in manifest["candidates"]
                     if item["id"] == "SYN-SDR709-01")
    argv = candidate["validation_contract"]["generator_argv"]
    filter_chain = argv[argv.index("-vf") + 1]
    assert filter_chain.startswith(
        "setparams=range=tv:color_primaries=bt709:"
        "color_trc=bt709:colorspace=bt709,")


def test_disabled_canonical_manifest_rejects_fingerprint(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["fingerprinted_state_enabled"] = False
    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            record(media, ffprobe, generator, PROBE),
            manifest=manifest,
            media_path=media, ffprobe_path=ffprobe,
            generator_path=generator, probe_artifact_path=probe_artifact,
            probe_runner=lambda *_: PROBE,
            regenerator=lambda *_: {
                "file_size": media.stat().st_size,
                "sha256": guard.sha256_file(media),
            },
            version_reader=lambda tool: (
                "ffprobe version test" if tool == ffprobe
                else "ffmpeg version test"),
        )


def test_cli_rejects_noncanonical_manifest_without_ok_marker(
        fixture_files, tmp_path, capsys):
    media, ffprobe, generator, probe_artifact = fixture_files
    untrusted_manifest = tmp_path / "manifest.json"
    untrusted_manifest.write_text(
        json.dumps(enabled_manifest(
            ffprobe, generator,
            record(media, ffprobe, generator, PROBE))),
        encoding="utf-8",
    )
    result = guard.main([
        "--manifest", str(untrusted_manifest),
        "--record", str(probe_artifact),
        "--media", str(media),
        "--ffprobe", str(ffprobe),
        "--generator", str(generator),
        "--probe-artifact", str(probe_artifact),
    ])
    captured = capsys.readouterr()
    assert result == 1
    assert "MEDIA_FINGERPRINT_FAILED" in captured.err
    assert "MEDIA_FINGERPRINT_OK" not in captured.out + captured.err


def test_disabled_manifest_stops_before_any_tool_callback(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    called = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["fingerprinted_state_enabled"] = False
    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            record(media, ffprobe, generator, PROBE),
            manifest,
            media, ffprobe, generator, probe_artifact,
            probe_runner=lambda *_: called.append("probe"),
            regenerator=lambda *_: called.append("generator"),
            version_reader=lambda *_: called.append("version"),
        )
    assert called == []


def test_subprocess_output_limit_is_enforced_while_running(monkeypatch):
    monkeypatch.setattr(guard, "MAX_TOOL_OUTPUT", 64)
    with pytest.raises(guard.MediaFingerprintError, match="output exceeded"):
        guard.run_bounded(
            [sys.executable, "-c", "import os; os.write(1, b'x' * 4096)"],
            timeout=5, label="test tool")


def test_subprocess_invalid_utf8_and_timeout_fail_closed():
    with pytest.raises(guard.MediaFingerprintError, match="strict UTF-8"):
        guard.run_bounded(
            [sys.executable, "-c", "import os; os.write(1, b'\\xff')"],
            timeout=5, label="test tool")
    with pytest.raises(guard.MediaFingerprintError, match="timed out"):
        guard.run_bounded(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.1, label="test tool")


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing contract")
@pytest.mark.parametrize("file_index", range(4))
def test_windows_lock_denies_write_delete_and_rename(
        fixture_files, file_index):
    target = fixture_files[file_index]
    original = target.read_bytes()
    moved = target.with_name(target.name + ".moved")
    with guard.LockedFile(target, "test input"):
        with pytest.raises(PermissionError):
            target.write_bytes(b"replacement")
        with pytest.raises(PermissionError):
            target.unlink()
        with pytest.raises(PermissionError):
            target.rename(moved)
    assert target.read_bytes() == original
    assert not moved.exists()


def _windows_process_is_running(pid):
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(
                handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == 259
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


@pytest.mark.skipif(os.name != "nt", reason="Windows process-tree contract")
def test_timeout_leaves_no_spawned_child_process(tmp_path):
    pid_file = tmp_path / "child.pid"
    parent_code = (
        "import pathlib,subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
        "time.sleep(30)"
    )
    with pytest.raises(guard.MediaFingerprintError, match="timed out"):
        guard.run_bounded(
            [sys.executable, "-c", parent_code, str(pid_file)],
            timeout=0.5, label="tree tool")
    assert pid_file.exists()
    child_pid = int(pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and _windows_process_is_running(child_pid):
        time.sleep(0.05)
    assert not _windows_process_is_running(child_pid)


def test_manifest_tool_identity_is_an_independent_anchor(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    manifest = enabled_manifest(ffprobe, generator, payload)
    manifest["fingerprint_validator"]["approved_tools"]["ffprobe"][
        "sha256"] = "0" * 64
    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            payload, manifest,
            media, ffprobe, generator, probe_artifact,
            probe_runner=lambda *_: PROBE,
            regenerator=lambda *_: {
                "file_size": media.stat().st_size,
                "sha256": guard.sha256_file(media),
            },
            version_reader=lambda tool: (
                "ffprobe version test" if tool == ffprobe
                else "ffmpeg version test"),
        )


def test_candidate_only_state_rejects_fingerprint(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    manifest = enabled_manifest(ffprobe, generator, payload)
    candidate = next(item for item in manifest["candidates"]
                     if item["id"] == "SYN-SDR709-01")
    candidate["state"] = "candidate_only"
    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            payload, manifest, media, ffprobe, generator, probe_artifact,
            probe_runner=lambda *_: PROBE,
            regenerator=lambda *_: {
                "file_size": media.stat().st_size,
                "sha256": guard.sha256_file(media),
            },
            version_reader=lambda tool: (
                "ffprobe version test" if tool == ffprobe
                else "ffmpeg version test"),
        )


def test_manifest_local_identity_drift_is_rejected(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    manifest = enabled_manifest(ffprobe, generator, payload)
    candidate = next(item for item in manifest["candidates"]
                     if item["id"] == "SYN-SDR709-01")
    candidate["local_identity"]["sha256"] = "0" * 64
    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            payload, manifest, media, ffprobe, generator, probe_artifact,
            probe_runner=lambda *_: PROBE,
            regenerator=lambda *_: {
                "file_size": media.stat().st_size,
                "sha256": guard.sha256_file(media),
            },
            version_reader=lambda tool: (
                "ffprobe version test" if tool == ffprobe
                else "ffmpeg version test"),
        )


def test_tool_execution_receives_resolved_absolute_paths(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    seen = []

    def version(tool):
        seen.append(tool)
        return ("ffprobe version test" if tool.name == "ffprobe.exe"
                else "ffmpeg version test")

    guard.verify_record(
        payload, enabled_manifest(ffprobe, generator, payload),
        media, ffprobe, generator,
        probe_artifact, probe_runner=lambda *_: PROBE,
        regenerator=lambda *_: {
            "file_size": media.stat().st_size,
            "sha256": guard.sha256_file(media),
        }, version_reader=version,
    )
    assert seen and all(path.is_absolute() and path == path.resolve()
                        for path in seen)


def test_manifest_source_and_use_basis_are_bound(fixture_files):
    media, ffprobe, generator, _ = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    payload["license_or_use_basis"] = "self asserted"
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, payload)


@pytest.mark.parametrize("field,value", (
    ("file_size", 8),
    ("sha256", "0" * 64),
    ("ffprobe_binary_sha256", "1" * 64),
    ("ffprobe_version", "wrong"),
    ("normalized_ffprobe_json_sha256", "2" * 64),
    ("selected_video_stream", 1),
))
def test_identity_or_tool_mismatch_fails_closed(fixture_files, field, value):
    media, ffprobe, generator, _ = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    payload[field] = value
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, payload)


def test_live_probe_drift_and_private_filename_are_handled(fixture_files):
    normalized = guard.normalize_ffprobe(PROBE)
    assert "filename" not in normalized["format"]
    tagged = copy.deepcopy(PROBE)
    tagged["format"]["tags"] = {"comment": "C:\\secret\\fixture.mp4"}
    assert "tags" not in guard.normalize_ffprobe(tagged)["format"]
    drifted = copy.deepcopy(PROBE)
    drifted["streams"][0]["color_transfer"] = "smpte2084"
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, live_probe=drifted)


@pytest.mark.parametrize("claim,value", (
    ("codec_name", "hevc"),
    ("bit_depth", 10),
    ("color_range", "pc"),
    ("color_space", "bt2020nc"),
    ("color_transfer", "smpte2084"),
    ("color_primaries", "bt2020"),
))
def test_false_sdr_claims_are_rejected(fixture_files, claim, value):
    media, ffprobe, generator, _ = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    payload["verified_claims"][claim] = value
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, payload)


def test_recipe_hash_and_placeholder_are_mandatory(fixture_files):
    media, ffprobe, generator, _ = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    payload["generation_identity"]["generator_argv"][-1] = str(media)
    payload["generation_identity"]["canonical_recipe_sha256"] = (
        guard.recipe_sha256(payload["generation_identity"]))
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, payload)


def test_changed_recipe_is_rejected_even_with_recomputed_hash(fixture_files):
    media, ffprobe, generator, _ = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    payload["generation_identity"]["generator_argv"][4] = (
        "testsrc2=size=1x1:rate=1:duration=1")
    payload["generation_identity"]["canonical_recipe_sha256"] = (
        guard.recipe_sha256(payload["generation_identity"]))
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, payload)


def test_media_mutation_during_probe_is_rejected(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    payload = record(media, ffprobe, generator, PROBE)

    def mutate(*_args):
        media.write_bytes(b"changed")
        return PROBE

    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            payload, enabled_manifest(ffprobe, generator, payload),
            media, ffprobe, generator,
            probe_artifact, probe_runner=mutate,
            regenerator=lambda *_: {
                "file_size": 7, "sha256": sha(b"fixture")},
            version_reader=lambda tool: (
                "ffprobe version test" if tool == ffprobe
                else "ffmpeg version test"),
        )


def test_regenerated_bytes_must_match_original(fixture_files):
    media, ffprobe, generator, probe_artifact = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            payload, enabled_manifest(ffprobe, generator, payload), media, ffprobe,
            generator, probe_artifact, probe_runner=lambda *_: PROBE,
            regenerator=lambda *_: {
                "file_size": 9, "sha256": sha(b"different")},
            version_reader=lambda tool: (
                "ffprobe version test" if tool == ffprobe
                else "ffmpeg version test"),
        )


@pytest.mark.parametrize("field,value", (
    ("exact_object_locator", "private-local:C:\\secret\\fixture.mp4"),
    ("normalized_ffprobe_json_artifact", "private:\\\\server\\probe"),
))
def test_private_labels_cannot_embed_paths(fixture_files, field, value):
    media, ffprobe, generator, _ = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    payload[field] = value
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, payload)


@pytest.mark.parametrize("field,value", (
    ("width", 1),
    ("height", 1),
    ("r_frame_rate", "1/1"),
    ("avg_frame_rate", "0/0"),
    ("duration", "1.000000"),
    ("format_name", "matroska,webm"),
    ("profile", "Baseline"),
))
def test_noncanonical_fixture_shape_is_rejected(fixture_files, field, value):
    media, ffprobe, generator, _ = fixture_files
    payload = record(media, ffprobe, generator, PROBE)
    payload["verified_claims"][field] = value
    with pytest.raises(guard.MediaFingerprintError):
        verify(fixture_files, payload)


def test_symlink_media_is_rejected_when_supported(fixture_files, tmp_path):
    media, ffprobe, generator, probe_artifact = fixture_files
    link = tmp_path / "linked.mp4"
    try:
        link.symlink_to(media)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    payload = record(media, ffprobe, generator, PROBE)
    with pytest.raises(guard.MediaFingerprintError):
        guard.verify_record(
            payload, enabled_manifest(ffprobe, generator, payload),
            link, ffprobe, generator,
            probe_artifact,
            probe_runner=lambda *_: PROBE,
            regenerator=lambda *_: {
                "file_size": media.stat().st_size,
                "sha256": guard.sha256_file(media),
            },
            version_reader=lambda tool: (
                "ffprobe version test" if tool == ffprobe
                else "ffmpeg version test"),
        )
