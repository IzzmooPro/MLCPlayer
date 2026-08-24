# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Recalculate exact fixture, tool, recipe and ffprobe evidence fail closed."""

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("file_attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("volume_serial", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        ]


ROOT = Path(__file__).resolve().parent.parent
CANONICAL_MANIFEST = (ROOT / "docs" / "VIDEO_FORMAT_MEDIA_MANIFEST.json").resolve()
FFPROBE_ARGV = (
    "-v", "error", "-show_format", "-show_streams", "-show_frames",
    "-select_streams", "v:0", "-of", "json", "$MEDIA",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_LOCAL_RE = re.compile(r"^private-local:[A-Z0-9][A-Za-z0-9._-]{0,127}$")
PRIVATE_ARTIFACT_RE = re.compile(r"^private:[A-Z0-9][A-Za-z0-9._-]{0,127}$")
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
MAX_TOOL_OUTPUT = 8 * 1024 * 1024
STREAM_FIELDS = (
    "index", "codec_name", "profile", "codec_tag_string", "width", "height",
    "pix_fmt", "bits_per_raw_sample", "color_range", "color_space",
    "color_transfer", "color_primaries", "r_frame_rate", "avg_frame_rate",
)
FORMAT_FIELDS = ("format_name", "duration", "size")
FRAME_FIELDS = ("media_type", "stream_index")
SDR_CLAIMS = {
    "codec_name", "profile", "codec_tag_string", "bit_depth", "pix_fmt",
    "color_range", "color_space", "color_transfer", "color_primaries",
    "width", "height", "r_frame_rate", "avg_frame_rate", "duration",
    "format_name",
}
LOCAL_IDENTITY_FIELDS = (
    "exact_object_locator", "file_size", "sha256", "ffprobe_binary_sha256",
    "ffprobe_version", "ffprobe_argv", "normalized_ffprobe_json_sha256",
    "normalized_ffprobe_json_artifact", "selected_video_stream",
    "verified_claims",
)


class MediaFingerprintError(RuntimeError):
    """The supplied bytes do not satisfy their recorded identity contract."""


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path):
    path = Path(path)
    return {"file_size": path.stat().st_size, "sha256": sha256_file(path)}


class LockedFile:
    """Keep the verified file open; on Windows deny write/delete replacement."""

    def __init__(self, path, label):
        self.path = ensure_regular_file(path, label)
        self.label = label
        self.handle = None
        self.file_key = None

    def __enter__(self):
        try:
            if os.name == "nt":
                create_file = ctypes.windll.kernel32.CreateFileW
                create_file.argtypes = (
                    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                    wintypes.HANDLE,
                )
                create_file.restype = wintypes.HANDLE
                raw_handle = create_file(
                    str(self.path), 0x80000000, 0x00000001, None, 3,
                    0x00200000, None,
                )
                if raw_handle == wintypes.HANDLE(-1).value:
                    raise OSError(ctypes.get_last_error())
                information = ByHandleFileInformation()
                if ctypes.windll.kernel32.GetFileType(raw_handle) != 1:
                    ctypes.windll.kernel32.CloseHandle(raw_handle)
                    raise OSError("not a disk file")
                if not ctypes.windll.kernel32.GetFileInformationByHandle(
                        raw_handle, ctypes.byref(information)):
                    ctypes.windll.kernel32.CloseHandle(raw_handle)
                    raise OSError(ctypes.get_last_error())
                if information.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                    ctypes.windll.kernel32.CloseHandle(raw_handle)
                    raise OSError("handle identifies a reparse point")
                self.file_key = (
                    information.volume_serial,
                    information.file_index_high,
                    information.file_index_low,
                )
                descriptor = msvcrt.open_osfhandle(
                    raw_handle, os.O_RDONLY | os.O_BINARY)
                self.handle = os.fdopen(descriptor, "rb", closefd=True)
            else:
                self.handle = self.path.open("rb")
        except OSError as error:
            raise MediaFingerprintError(f"{self.label} cannot be locked") from error
        return self

    def identity(self):
        try:
            self.handle.seek(0)
            digest = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: self.handle.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
            return {"file_size": size, "sha256": digest.hexdigest()}
        except OSError as error:
            raise MediaFingerprintError(
                f"{self.label} identity cannot be read") from error

    def __exit__(self, *_exc):
        if self.handle is not None:
            self.handle.close()


def canonical_json_bytes(payload):
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_sha256(payload):
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def normalize_ffprobe(payload):
    """Allowlist technical fields so local paths and arbitrary tags cannot escape."""
    if not isinstance(payload, dict):
        raise MediaFingerprintError("ffprobe payload must be an object")
    streams = payload.get("streams")
    frames = payload.get("frames")
    format_data = payload.get("format")
    if not isinstance(streams, list) or not isinstance(frames, list):
        raise MediaFingerprintError("ffprobe stream or frame list is missing")
    if not isinstance(format_data, dict):
        raise MediaFingerprintError("ffprobe format is missing")
    if not all(isinstance(item, dict) for item in streams + frames):
        raise MediaFingerprintError("ffprobe stream or frame entry is invalid")
    return {
        "streams": [
            {key: item[key] for key in STREAM_FIELDS if key in item}
            for item in streams
        ],
        "frames": [
            {key: item[key] for key in FRAME_FIELDS if key in item}
            for item in frames
        ],
        "format": {
            key: format_data[key] for key in FORMAT_FIELDS if key in format_data
        },
    }


def _reject_reparse(path, label):
    try:
        stat = path.lstat()
    except OSError as error:
        raise MediaFingerprintError(f"{label} is unreadable") from error
    if path.is_symlink() or getattr(stat, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
        raise MediaFingerprintError(f"{label} must not traverse a reparse point")


def ensure_regular_file(path, label):
    original = Path(path).absolute()
    current = original.parent
    while current != current.parent:
        _reject_reparse(current, f"{label} parent")
        current = current.parent
    _reject_reparse(original, label)
    if not original.is_file():
        raise MediaFingerprintError(f"{label} must be a regular file")
    try:
        return original.resolve(strict=True)
    except OSError as error:
        raise MediaFingerprintError(f"{label} cannot be resolved") from error


def require_sha256(value, label):
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise MediaFingerprintError(f"{label} must be lowercase SHA-256")


def read_json(path, label):
    path = ensure_regular_file(path, label)
    try:
        return json.loads(path.read_bytes().decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MediaFingerprintError(f"{label} is invalid JSON") from error


def _terminate_process_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        windows_directory = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetWindowsDirectoryW(
            windows_directory, len(windows_directory))
        if 0 < length < len(windows_directory):
            taskkill = Path(windows_directory.value) / "System32" / "taskkill.exe"
            try:
                subprocess.run(
                    [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, check=False, timeout=5,
                )
            except (OSError, subprocess.SubprocessError):
                process.kill()
        else:
            process.kill()
    else:
        process.kill()


def run_bounded(command, timeout, label):
    process = subprocess.Popen(
        [str(item) for item in command], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    exceeded = threading.Event()

    def drain(name, pipe):
        try:
            while True:
                chunk = pipe.read(64 * 1024)
                if not chunk:
                    break
                if len(captured[name]) + len(chunk) > MAX_TOOL_OUTPUT:
                    exceeded.set()
                    _terminate_process_tree(process)
                    break
                captured[name].extend(chunk)
        finally:
            pipe.close()

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        _terminate_process_tree(process)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        for reader in readers:
            reader.join(timeout=5)
        raise MediaFingerprintError(f"{label} timed out") from error
    for reader in readers:
        reader.join(timeout=5)
    if any(reader.is_alive() for reader in readers):
        _terminate_process_tree(process)
        raise MediaFingerprintError(f"{label} output reader did not stop")
    if exceeded.is_set():
        raise MediaFingerprintError(f"{label} output exceeded the limit")
    stdout = bytes(captured["stdout"])
    stderr = bytes(captured["stderr"])
    if returncode != 0:
        raise MediaFingerprintError(f"{label} failed with {returncode}")
    try:
        return stdout.decode("utf-8", errors="strict"), stderr.decode(
            "utf-8", errors="strict")
    except UnicodeError as error:
        raise MediaFingerprintError(f"{label} output is not strict UTF-8") from error


def read_tool_version(path):
    stdout, _ = run_bounded([path, "-version"], timeout=15, label="tool version")
    first = next((line.strip() for line in stdout.splitlines() if line.strip()), "")
    if not first:
        raise MediaFingerprintError("tool version output is empty")
    return first


def run_ffprobe(path, media_path, argv):
    if tuple(argv) != FFPROBE_ARGV:
        raise MediaFingerprintError("ffprobe argv does not match the contract")
    command = [path] + [media_path if item == "$MEDIA" else item for item in argv]
    stdout, _ = run_bounded(command, timeout=30, label="ffprobe")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as error:
        raise MediaFingerprintError("ffprobe output is invalid JSON") from error


def regenerate_fixture(generator_path, argv):
    with tempfile.TemporaryDirectory(prefix="mlc-sdr-regenerate-") as directory:
        output = Path(directory).resolve() / "SYN-SDR709-01.mp4"
        command = [generator_path] + [output if item == "$OUTPUT" else item for item in argv]
        run_bounded(command, timeout=90, label="fixture regeneration")
        output = ensure_regular_file(output, "regenerated media")
        return file_identity(output)


def recipe_sha256(generation_identity):
    if not isinstance(generation_identity, dict):
        raise MediaFingerprintError("generation_identity must be an object")
    payload = {
        key: value for key, value in generation_identity.items()
        if key != "canonical_recipe_sha256"
    }
    return canonical_json_sha256(payload)


def bit_depth(stream):
    raw = str(stream.get("bits_per_raw_sample") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    pix_fmt = str(stream.get("pix_fmt") or "")
    match = re.search(r"p(\d+)(?:le|be)?$", pix_fmt)
    if match:
        return int(match.group(1))
    if pix_fmt in {"yuv420p", "yuv422p", "yuv444p", "gray", "rgb24"}:
        return 8
    raise MediaFingerprintError("video bit depth cannot be established")


def select_video_stream(probe, index):
    streams = probe.get("streams")
    matches = [item for item in streams if item.get("index") == index]
    if len(matches) != 1:
        raise MediaFingerprintError("selected video stream is not unique")
    if not any(
            item.get("media_type") == "video" and item.get("stream_index") == index
            for item in probe.get("frames", [])):
        raise MediaFingerprintError("selected stream has no probed video frame")
    return matches[0]


def verify_sdr_claims(record, probe, media_size, expected_claims):
    claims = record.get("verified_claims")
    if not isinstance(claims, dict) or set(claims) != SDR_CLAIMS:
        raise MediaFingerprintError("SYN-SDR709-01 claims are incomplete")
    if claims != expected_claims:
        raise MediaFingerprintError("claims differ from the manifest contract")
    index = record.get("selected_video_stream")
    if not isinstance(index, int) or index < 0:
        raise MediaFingerprintError("selected_video_stream must be nonnegative")
    stream = select_video_stream(probe, index)
    format_data = probe["format"]
    actual = {
        "codec_name": stream.get("codec_name"),
        "profile": stream.get("profile"),
        "codec_tag_string": stream.get("codec_tag_string"),
        "bit_depth": bit_depth(stream),
        "pix_fmt": stream.get("pix_fmt"),
        "color_range": stream.get("color_range"),
        "color_space": stream.get("color_space"),
        "color_transfer": stream.get("color_transfer"),
        "color_primaries": stream.get("color_primaries"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "duration": format_data.get("duration"),
        "format_name": format_data.get("format_name"),
    }
    if claims != actual:
        raise MediaFingerprintError("recorded SDR claims differ from ffprobe")
    if str(format_data.get("size")) != str(media_size):
        raise MediaFingerprintError("ffprobe format size differs from file size")


def _unique_by_id(items, identifier, label):
    if not isinstance(items, list):
        raise MediaFingerprintError(f"manifest {label} list is missing")
    matches = [item for item in items if isinstance(item, dict) and item.get("id") == identifier]
    if len(matches) != 1:
        raise MediaFingerprintError(f"manifest {label} identity is not unique")
    return matches[0]


def validate_manifest(record, manifest):
    if not isinstance(manifest, dict) or manifest.get("fingerprinted_state_enabled") is not True:
        raise MediaFingerprintError("manifest fingerprinted state is disabled")
    validator = manifest.get("fingerprint_validator")
    if not isinstance(validator, dict) or validator.get("live_tool_validation_completed") is not True:
        raise MediaFingerprintError("manifest live tool validation is incomplete")
    candidate_id = record.get("candidate_id")
    supported = validator.get("supported_candidate_ids")
    if not isinstance(supported, list) or candidate_id not in supported:
        raise MediaFingerprintError("candidate is not supported by the validator")
    candidate = _unique_by_id(manifest.get("candidates"), candidate_id, "candidate")
    if candidate.get("state") != "fingerprinted":
        raise MediaFingerprintError("manifest candidate state is not fingerprinted")
    source = _unique_by_id(manifest.get("sources"), candidate.get("source_id"), "source")
    if record.get("source_id") != source.get("id"):
        raise MediaFingerprintError("record source differs from the manifest")
    if record.get("license_or_use_basis") != source.get("license_or_use_basis"):
        raise MediaFingerprintError("record use basis differs from the manifest")
    contract = candidate.get("validation_contract")
    if not isinstance(contract, dict):
        raise MediaFingerprintError("candidate validation contract is missing")
    expected_local_identity = {
        key: record.get(key) for key in LOCAL_IDENTITY_FIELDS
    }
    if candidate.get("local_identity") != expected_local_identity:
        raise MediaFingerprintError("record differs from manifest local identity")
    if candidate.get("generation_identity") != record.get("generation_identity"):
        raise MediaFingerprintError("record differs from manifest generation identity")
    approved = validator.get("approved_tools")
    if not isinstance(approved, dict):
        raise MediaFingerprintError("manifest approved tool identities are missing")
    return contract, approved


def verify_tool(path, record_hash, record_version, approved, label, version_reader):
    path = ensure_regular_file(path, label)
    approved_hash = approved.get("sha256") if isinstance(approved, dict) else None
    approved_version = approved.get("version") if isinstance(approved, dict) else None
    require_sha256(record_hash, f"{label} SHA-256")
    require_sha256(approved_hash, f"approved {label} SHA-256")
    if record_hash != approved_hash or sha256_file(path) != approved_hash:
        raise MediaFingerprintError(f"{label} binary SHA-256 differs")
    if record_version != approved_version or version_reader(path) != approved_version:
        raise MediaFingerprintError(f"{label} version differs")
    return path


def verify_generation(record, contract, approved_tools, generator_path, version_reader):
    generation = record.get("generation_identity")
    if not isinstance(generation, dict):
        raise MediaFingerprintError("generation_identity is missing")
    generator_path = verify_tool(
        generator_path, generation.get("generator_binary_sha256"),
        generation.get("generator_version"), approved_tools.get("generator"),
        "generator", version_reader,
    )
    argv = generation.get("generator_argv")
    if argv != contract.get("generator_argv"):
        raise MediaFingerprintError("generator argv differs from the manifest contract")
    if not isinstance(argv, list) or argv.count("$OUTPUT") != 1 or not all(
            isinstance(item, str) for item in argv):
        raise MediaFingerprintError("generator argv is invalid")
    inputs = generation.get("input_and_sidecar_sha256")
    if inputs != []:
        raise MediaFingerprintError("self-contained SDR fixture must have no inputs")
    expected_recipe = generation.get("canonical_recipe_sha256")
    require_sha256(expected_recipe, "canonical_recipe_sha256")
    if recipe_sha256(generation) != expected_recipe:
        raise MediaFingerprintError("canonical recipe SHA-256 differs")
    return generator_path, argv


def verify_record(
        record, manifest, media_path, ffprobe_path, generator_path,
        probe_artifact_path, probe_runner=run_ffprobe,
        regenerator=regenerate_fixture, version_reader=read_tool_version):
    if not isinstance(record, dict):
        raise MediaFingerprintError("record must be an object")
    if record.get("candidate_id") != "SYN-SDR709-01":
        raise MediaFingerprintError("only SYN-SDR709-01 is allowed")
    if record.get("state") != "fingerprinted":
        raise MediaFingerprintError("record state must be fingerprinted")
    if not PRIVATE_LOCAL_RE.fullmatch(str(record.get("exact_object_locator") or "")):
        raise MediaFingerprintError("exact locator must be an opaque private label")
    if not PRIVATE_ARTIFACT_RE.fullmatch(
            str(record.get("normalized_ffprobe_json_artifact") or "")):
        raise MediaFingerprintError("probe artifact must be an opaque private label")

    contract, approved_tools = validate_manifest(record, manifest)
    with contextlib.ExitStack() as stack:
        media_lock = stack.enter_context(LockedFile(media_path, "media"))
        ffprobe_lock = stack.enter_context(LockedFile(ffprobe_path, "ffprobe"))
        generator_lock = stack.enter_context(LockedFile(generator_path, "generator"))
        probe_lock = stack.enter_context(
            LockedFile(probe_artifact_path, "probe artifact"))
        media_path = media_lock.path
        ffprobe_path = ffprobe_lock.path
        generator_path = generator_lock.path
        initial_media = media_lock.identity()
        if record.get("file_size") != initial_media["file_size"]:
            raise MediaFingerprintError("media file size differs")
        require_sha256(record.get("sha256"), "media sha256")
        if record.get("sha256") != initial_media["sha256"]:
            raise MediaFingerprintError("media SHA-256 differs")

        ffprobe_path = verify_tool(
            ffprobe_path, record.get("ffprobe_binary_sha256"),
            record.get("ffprobe_version"), approved_tools.get("ffprobe"),
            "ffprobe", version_reader,
        )
        argv = record.get("ffprobe_argv")
        if not isinstance(argv, list) or tuple(argv) != FFPROBE_ARGV:
            raise MediaFingerprintError("ffprobe argv differs")
        generator_path, generator_argv = verify_generation(
            record, contract, approved_tools, generator_path, version_reader)

        try:
            stored_probe = normalize_ffprobe(json.loads(
                probe_lock.handle.read().decode("utf-8", errors="strict")))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise MediaFingerprintError(
                "probe artifact is invalid strict UTF-8 JSON") from error
        try:
            live_probe = normalize_ffprobe(
                probe_runner(ffprobe_path, media_path, argv))
        except OSError as error:
            raise MediaFingerprintError("ffprobe input changed or became unavailable") from error
        if canonical_json_bytes(stored_probe) != canonical_json_bytes(live_probe):
            raise MediaFingerprintError("live ffprobe output differs from artifact")
        require_sha256(record.get("normalized_ffprobe_json_sha256"),
                       "normalized_ffprobe_json_sha256")
        actual_probe_hash = canonical_json_sha256(stored_probe)
        if actual_probe_hash != record.get("normalized_ffprobe_json_sha256"):
            raise MediaFingerprintError("normalized ffprobe SHA-256 differs")
        verify_sdr_claims(
            record, stored_probe, initial_media["file_size"],
            contract.get("expected_claims"),
        )

        regenerated = regenerator(generator_path, generator_argv)
        if regenerated != initial_media:
            raise MediaFingerprintError(
                "recipe regeneration differs from exact media bytes")
        if media_lock.identity() != initial_media:
            raise MediaFingerprintError("media changed during verification")
        if ffprobe_lock.identity()["sha256"] != record["ffprobe_binary_sha256"]:
            raise MediaFingerprintError("ffprobe changed during verification")
        if generator_lock.identity()["sha256"] != record[
                "generation_identity"]["generator_binary_sha256"]:
            raise MediaFingerprintError("generator changed during verification")
    return {
        "candidate_id": record["candidate_id"],
        "file_size": initial_media["file_size"],
        "sha256": initial_media["sha256"],
        "normalized_ffprobe_json_sha256": actual_probe_hash,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    parser.add_argument("--generator", type=Path, required=True)
    parser.add_argument("--probe-artifact", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest_path = ensure_regular_file(args.manifest, "manifest")
        if manifest_path != CANONICAL_MANIFEST:
            raise MediaFingerprintError("only the canonical repository manifest is trusted")
        manifest = read_json(manifest_path, "manifest")
        record = read_json(args.record, "record")
        result = verify_record(
            record, manifest, args.media, args.ffprobe, args.generator,
            args.probe_artifact,
        )
    except (MediaFingerprintError, OSError, subprocess.SubprocessError) as error:
        print(f"MEDIA_FINGERPRINT_FAILED: {error}", file=sys.stderr)
        return 1
    print("MEDIA_FINGERPRINT_OK " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
