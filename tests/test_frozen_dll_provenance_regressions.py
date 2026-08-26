# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Frozen build must not accept PATH-discovered root ICU collisions."""

import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
POLICY_PATH = PACKAGING / "pyinstaller_binary_policy.py"
RUNNER_PATH = PACKAGING / "run_pyinstaller.py"
SPEC_PATH = ROOT / "MLCPlayer.spec"

sys.path.insert(0, str(PACKAGING))
import verify_build  # noqa: E402


def load_policy():
    assert POLICY_PATH.is_file(), "PyInstaller binary provenance policy is missing"
    module_spec = importlib.util.spec_from_file_location(
        "mlc_pyinstaller_binary_policy", POLICY_PATH)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def load_runner():
    assert RUNNER_PATH.is_file(), "clean PyInstaller runner is missing"
    module_spec = importlib.util.spec_from_file_location(
        "mlc_run_pyinstaller", RUNNER_PATH)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_foreign_root_icu_pair_is_removed(tmp_path):
    policy = load_policy()
    foreign = tmp_path / "foreign-path"
    foreign.mkdir()
    for name in ("icuuc.dll", "icudt78.dll", "ucrtbase.dll",
                 "api-ms-win-crt-heap-l1-1-0.dll"):
        (foreign / name).write_bytes(b"foreign")
    entries = [
        ("ICUUC.DLL", str(foreign / "icuuc.dll"), "BINARY"),
        ("icudt78.dll", str(foreign / "icudt78.dll"), "BINARY"),
        ("ucrtbase.dll", str(foreign / "ucrtbase.dll"), "BINARY"),
        ("api-ms-win-crt-heap-l1-1-0.dll",
         str(foreign / "api-ms-win-crt-heap-l1-1-0.dll"), "BINARY"),
    ]

    kept, removed = policy.sanitize_binaries(
        entries, project_root=ROOT, python_root=Path(sys.base_prefix))

    assert kept == []
    assert [entry[0] for entry in removed] == [
        "ICUUC.DLL", "icudt78.dll", "ucrtbase.dll",
        "api-ms-win-crt-heap-l1-1-0.dll"]


def test_nested_qt_icu_and_unrelated_binaries_are_preserved(tmp_path):
    policy = load_policy()
    foreign = tmp_path / "foreign-path"
    foreign.mkdir()
    for name in ("icuuc.dll", "VCRUNTIME140.dll", "libssl-3-x64.dll",
                 "other.dll"):
        (foreign / name).write_bytes(b"preserved")
    entries = [
        ("PyQt6\\Qt6\\bin\\icuuc.dll", str(foreign / "icuuc.dll"),
         "BINARY"),
        ("bin/mpv-2.dll", str(ROOT / "bin" / "mpv-2.dll"), "BINARY"),
        ("other.dll", str(foreign / "other.dll"), "BINARY"),
        ("PyQt6/Qt6/bin/VCRUNTIME140.dll",
         str(foreign / "VCRUNTIME140.dll"), "BINARY"),
        ("libssl-3-x64.dll", str(foreign / "libssl-3-x64.dll"), "BINARY"),
    ]

    kept, removed = policy.sanitize_binaries(
        entries, project_root=ROOT, python_root=Path(sys.base_prefix))

    assert kept == entries
    assert removed == []


@pytest.mark.parametrize("destination", [
    ".\\ICUUC.DLL",
    "folder\\..\\icuuc.dll",
    "icuuc.dll.",
    "icuuc.dll ",
])
def test_root_equivalent_destination_forms_are_not_a_bypass(
        tmp_path, destination):
    policy = load_policy()
    foreign = tmp_path / "foreign-path"
    foreign.mkdir()
    source = foreign / "icuuc.dll"
    source.write_bytes(b"foreign")

    kept, removed = policy.sanitize_binaries(
        [(destination, str(source), "BINARY")],
        project_root=ROOT, python_root=Path(sys.base_prefix))

    assert kept == []
    assert [entry[0] for entry in removed] == [destination]


@pytest.mark.parametrize("destination", [
    "../icuuc.dll",
    "folder/../../icuuc.dll",
    "/icuuc.dll",
    "C:/Windows/System32/icuuc.dll",
    "//server/share/icuuc.dll",
])
def test_unsafe_destination_forms_fail_closed(tmp_path, destination):
    policy = load_policy()
    source = tmp_path / "icuuc.dll"
    source.write_bytes(b"foreign")

    with pytest.raises(policy.BinaryPolicyError):
        policy.sanitize_binaries(
            [(destination, str(source), "BINARY")],
            project_root=ROOT, python_root=Path(sys.base_prefix))


@pytest.mark.parametrize("source", ["icuuc.dll", "relative/icuuc.dll"])
def test_unknown_root_icu_provenance_fails_closed(source):
    policy = load_policy()

    with pytest.raises(policy.BinaryPolicyError):
        policy.sanitize_binaries(
            [("icuuc.dll", source, "BINARY")],
            project_root=ROOT, python_root=Path(sys.base_prefix))


def test_project_or_python_root_icu_requires_explicit_review():
    policy = load_policy()
    source = ROOT / "README.md"

    with pytest.raises(policy.BinaryPolicyError):
        policy.sanitize_binaries(
            [("icuuc.dll", str(source), "BINARY")],
            project_root=ROOT, python_root=Path(sys.base_prefix))


@pytest.mark.parametrize("name", [
    "icuuc.dll", "ICUUC.DLL", "icudt78.dll", "ucrtbase.dll",
    "api-ms-win-core-file-l1-1-0.dll",
])
def test_post_build_gate_rejects_root_icu(tmp_path, monkeypatch, name):
    dist = tmp_path / "MLC Player"
    internal = dist / "_internal"
    internal.mkdir(parents=True)
    (internal / name).write_bytes(b"foreign ICU")
    monkeypatch.setattr(verify_build, "DIST", str(dist))
    monkeypatch.setattr(verify_build, "REQUIRED_IN_DIST", ())
    monkeypatch.setattr(verify_build, "FORBIDDEN_IN_DIST", ())

    assert verify_build.check_post() is False


def test_post_build_gate_allows_nested_qt_icu(tmp_path, monkeypatch):
    dist = tmp_path / "MLC Player"
    nested = dist / "_internal" / "PyQt6" / "Qt6" / "bin"
    nested.mkdir(parents=True)
    (nested / "icuuc.dll").write_bytes(b"nested Qt ICU")
    monkeypatch.setattr(verify_build, "DIST", str(dist))
    monkeypatch.setattr(verify_build, "REQUIRED_IN_DIST", ())
    monkeypatch.setattr(verify_build, "FORBIDDEN_IN_DIST", ())

    assert verify_build.check_post() is True


def test_spec_routes_analysis_binaries_through_the_policy():
    source = SPEC_PATH.read_text(encoding="utf-8")

    assert "sanitize_binaries" in source
    assert source.index("Analysis(") < source.index("sanitize_binaries")
    assert source.index("sanitize_binaries") < source.index("PYZ(")


def test_clean_runner_drops_caller_native_path_and_overrides(tmp_path):
    runner = load_runner()
    python_dir = tmp_path / "python"
    python_dir.mkdir()
    executable = python_dir / "python.exe"
    executable.write_bytes(b"")
    base_prefix = tmp_path / "python-base"
    base_prefix.mkdir()
    system_root = tmp_path / "Windows"
    (system_root / "System32").mkdir(parents=True)
    foreign = tmp_path / "codex-runtimes" / "poppler"
    foreign.mkdir(parents=True)
    environ = {
        "Path": str(foreign),
        "SystemRoot": str(system_root),
        "PYTHONPATH": str(foreign),
        "QT_PLUGIN_PATH": str(foreign),
        "KEEP_ME": "yes",
    }

    child = runner.make_child_environment(
        environ=environ, executable=executable, base_prefix=base_prefix,
        trusted_system_root=system_root)
    clean_parts = child["PATH"].split(os.pathsep)

    assert str(foreign) not in clean_parts
    assert str(python_dir.resolve()) in clean_parts
    assert str(base_prefix.resolve()) in clean_parts
    assert str((system_root / "System32").resolve()) in clean_parts
    assert child["KEEP_ME"] == "yes"
    assert not {key.casefold() for key in child} & {
        "pythonpath", "pythonhome", "qt_plugin_path", "qml2_import_path"}


def test_clean_runner_ignores_caller_controlled_system_root(tmp_path):
    runner = load_runner()
    python_dir = tmp_path / "python"
    python_dir.mkdir()
    executable = python_dir / "python.exe"
    executable.write_bytes(b"")
    trusted_root = tmp_path / "trusted-Windows"
    (trusted_root / "System32").mkdir(parents=True)
    foreign_root = tmp_path / "foreign-Windows"
    (foreign_root / "System32").mkdir(parents=True)

    child = runner.make_child_environment(
        environ={
            "sYsTeMrOoT": str(foreign_root),
            "windir": str(foreign_root),
            "SYSTEMdrive": "Z:",
        },
        executable=executable,
        base_prefix=python_dir,
        trusted_system_root=trusted_root)
    clean_parts = child["PATH"].split(os.pathsep)

    assert str((trusted_root / "System32").resolve()) in clean_parts
    assert str((foreign_root / "System32").resolve()) not in clean_parts
    assert child["SystemRoot"] == str(trusted_root.resolve())
    assert child["WINDIR"] == str(trusted_root.resolve())
    assert child["SystemDrive"] == trusted_root.resolve().drive
    assert not {"systemroot", "windir", "systemdrive"} & {
        key.casefold() for key in child
        if key not in {"SystemRoot", "WINDIR", "SystemDrive"}}
    assert str(foreign_root) not in child.values()


def test_clean_runner_default_branch_uses_os_api_directories(
        tmp_path, monkeypatch):
    runner = load_runner()
    python_dir = tmp_path / "python"
    python_dir.mkdir()
    executable = python_dir / "python.exe"
    executable.write_bytes(b"")
    trusted_root = tmp_path / "trusted-Windows"
    trusted_system = trusted_root / "System32"
    trusted_system.mkdir(parents=True)
    monkeypatch.setattr(
        runner, "_windows_directories",
        lambda: (trusted_root.resolve(), trusted_system.resolve()))

    child = runner.make_child_environment(
        environ={"SystemRoot": "C:\\foreign", "WINDIR": "C:\\foreign"},
        executable=executable,
        base_prefix=python_dir)

    assert child["SystemRoot"] == str(trusted_root.resolve())
    assert child["WINDIR"] == str(trusted_root.resolve())
    assert str(trusted_system.resolve()) in child["PATH"].split(os.pathsep)


def test_clean_runner_preserves_command_and_return_code(tmp_path):
    runner = load_runner()
    python_dir = tmp_path / "python"
    python_dir.mkdir()
    executable = python_dir / "python.exe"
    executable.write_bytes(b"")
    system_root = tmp_path / "Windows"
    (system_root / "System32").mkdir(parents=True)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=7)

    code = runner.run_pyinstaller(
        ["MLCPlayer.spec", "--clean"],
        environ={"SystemRoot": str(system_root)},
        executable=executable,
        base_prefix=python_dir,
        trusted_system_root=system_root,
        runner=fake_run)

    assert code == 7
    assert captured["command"] == [
        str(executable.resolve()), "-m", "PyInstaller",
        "MLCPlayer.spec", "--clean"]
    assert captured["cwd"] == str(ROOT)
    assert captured["check"] is False


@pytest.mark.parametrize("relative", [
    "packaging/build_unsigned_main.bat",
    "packaging/build_release.bat",
])
def test_build_chains_use_the_clean_runner(relative):
    source = (ROOT / relative).read_text(encoding="utf-8")
    build_lines = [line.strip() for line in source.splitlines()
                   if '"%SPEC%" --noconfirm --clean' in line]

    assert build_lines == [
        'python "packaging\\run_pyinstaller.py" "%SPEC%" '
        '--noconfirm --clean --log-level WARN']
