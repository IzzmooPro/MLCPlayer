# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Run PyInstaller without inheriting third-party native PATH entries."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
_REMOVED_ENV = {
    "PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH",
    "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE",
}


def _windows_directories():
    """Return OS-reported Windows and system directories."""
    if os.name != "nt":
        raise RuntimeError("Windows directories are unavailable on this OS")

    def read_directory(api_name):
        buffer = ctypes.create_unicode_buffer(32768)
        api = getattr(ctypes.windll.kernel32, api_name)
        length = api(buffer, len(buffer))
        if not length or length >= len(buffer):
            raise RuntimeError(f"{api_name} failed")
        return Path(buffer.value).resolve()

    return read_directory("GetWindowsDirectoryW"), read_directory(
        "GetSystemDirectoryW")


def make_child_environment(environ=None, executable=None, base_prefix=None,
                           trusted_system_root=None):
    """Return a child env whose PATH has no caller-supplied native dirs."""
    source = dict(os.environ if environ is None else environ)
    executable = Path(executable or sys.executable).resolve()
    base_prefix = Path(base_prefix or sys.base_prefix).resolve()
    if trusted_system_root is None:
        system_root, system_directory = _windows_directories()
    else:
        system_root = Path(trusted_system_root).resolve()
        system_directory = (system_root / "System32").resolve()
    candidates = (
        executable.parent,
        base_prefix,
        system_directory,
        system_root,
    )
    clean = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.normcase(str(candidate.resolve()))
        if normalized not in seen and candidate.is_dir():
            clean.append(str(candidate.resolve()))
            seen.add(normalized)
    if not clean:
        raise RuntimeError("no trusted PyInstaller PATH directories exist")

    child = {key: value for key, value in source.items()
             if key.casefold() not in {"path", *
                                      (name.casefold() for name in _REMOVED_ENV)}}
    child["PATH"] = os.pathsep.join(clean)
    child["SystemRoot"] = str(system_root)
    child["WINDIR"] = str(system_root)
    if system_root.drive:
        child["SystemDrive"] = system_root.drive
    return child


def run_pyinstaller(args, environ=None, executable=None, base_prefix=None,
                    trusted_system_root=None, runner=subprocess.run):
    executable = str(Path(executable or sys.executable).resolve())
    child = make_child_environment(
        environ=environ, executable=executable, base_prefix=base_prefix,
        trusted_system_root=trusted_system_root)
    command = [executable, "-m", "PyInstaller", *args]
    completed = runner(command, cwd=str(ROOT), env=child, check=False)
    return completed.returncode


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: run_pyinstaller.py <spec> [PyInstaller arguments...] ")
        return 2
    return run_pyinstaller(args)


if __name__ == "__main__":
    sys.exit(main())
