# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""User-session half of MLC Player's optional uninstall cleanup."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape


ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NOT_FOUND = 1168
CRED_TYPE_GENERIC = 1
TOKEN_QUERY = 0x0008
_SID_RE = re.compile(r"S-\d+(?:-\d+)+\Z")
_NONCE_RE = re.compile(r"[0-9a-f]{32}\Z")
_THUMBNAIL_RE = re.compile(r"[0-9a-fA-F]{64}\.jpg\Z")
_UPDATE_RE = re.compile(r"MLCPlayer_Setup_v[^\\/]+\.(?:exe|exe\.sig)\Z", re.I)
_IPC_RE = re.compile(r"[0-9a-f]{32}\.(?:request|result)\.json\Z", re.I)
_HELPER_PARTS = ("Programs", "MLC Player", "UninstallCleanup", "v1",
                 "MLCUserCleanup.exe")
_LEGACY_HELPER_PARTS = ("MLCPlayer", "UninstallCleanup", "v1",
                        "MLCUserCleanup.exe")


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _windows_libraries():
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                           ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p,
                                                ctypes.POINTER(wintypes.LPWSTR)]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.CredEnumerateW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.POINTER(ctypes.POINTER(CREDENTIALW)))]
    advapi32.CredEnumerateW.restype = wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                     wintypes.DWORD]
    advapi32.CredDeleteW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    return advapi32, kernel32


def current_user_sid():
    """Return the exact SID from this process token; never infer from paths."""
    if os.name != "nt":
        return None
    advapi32, kernel32 = _windows_libraries()
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY,
                                     ctypes.byref(token)):
        return None
    try:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or not size.value:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, 1, buffer, size.value,
                                             ctypes.byref(size)):
            return None
        sid_pointer = ctypes.c_void_p.from_buffer(buffer).value
        text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid_pointer, ctypes.byref(text)):
            return None
        try:
            value = text.value
            return value if value and _SID_RE.fullmatch(value) else None
        finally:
            kernel32.LocalFree(text)
    finally:
        kernel32.CloseHandle(token)


def task_name_for_sid(sid):
    if not isinstance(sid, str) or not _SID_RE.fullmatch(sid):
        return None
    return "\\MLCPlayer_UninstallCleanup_" + sid


def request_matches_current_user(request_sid):
    sid = current_user_sid()
    return bool(sid and request_sid and sid == request_sid)


def helper_location(local_appdata):
    # This host's Task Scheduler deterministically returns 0x80070002 for
    # executables directly below %LOCALAPPDATA%, while the per-user Programs
    # tree launches the exact same helper. Keep the helper durable and scoped
    # to this product without relying on the purgeable Temp directory.
    return Path(os.path.abspath(str(local_appdata))).joinpath(*_HELPER_PARTS)


def legacy_helper_location(local_appdata):
    return Path(os.path.abspath(str(local_appdata))).joinpath(
        *_LEGACY_HELPER_PARTS)


def profile_local_appdata(environ=None):
    env = os.environ if environ is None else environ
    profile = env.get("USERPROFILE")
    if not profile:
        return None
    profile = Path(os.path.abspath(profile))
    local = safe_owned_path(profile, "AppData", "Local")
    return local if local is not None and local.is_dir() else None


def ipc_root(local_appdata):
    return helper_location(local_appdata).parent / "ipc"


def request_file(local_appdata, nonce):
    if not isinstance(nonce, str) or not _NONCE_RE.fullmatch(nonce):
        return None
    return ipc_root(local_appdata) / (nonce + ".request.json")


def result_file(local_appdata, nonce):
    if not isinstance(nonce, str) or not _NONCE_RE.fullmatch(nonce):
        return None
    return ipc_root(local_appdata) / (nonce + ".result.json")


def _is_reparse(path):
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) &
        getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def safe_owned_path(root, *parts):
    """Reject traversal and every existing reparse component, including leaf."""
    current = Path(root)
    try:
        if _is_reparse(current):
            return None
        for part in parts:
            if part in ("", ".", "..") or Path(part).name != part:
                return None
            current = current / part
            if _is_reparse(current):
                return None
        return current
    except OSError:
        return None


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
        os.path.abspath(str(right)))


def _file_sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _ensure_safe_directories(root, parts):
    """Create one component at a time and recheck every ancestor."""
    root = Path(root)
    if not root.is_dir() or _is_reparse(root):
        return None
    current_parts = []
    for part in parts:
        current_parts.append(part)
        current = safe_owned_path(root, *current_parts)
        if current is None:
            return None
        try:
            current.mkdir(exist_ok=True)
        except OSError:
            return None
        current = safe_owned_path(root, *current_parts)
        if current is None or not current.is_dir():
            return None
    return current


def _safe_profile_owned_path(local_appdata, *parts):
    """Validate Profile/AppData/Local plus the requested product components."""
    local = Path(os.path.abspath(str(local_appdata)))
    appdata = local.parent
    profile = appdata.parent
    if local.name.casefold() != "local" or \
            appdata.name.casefold() != "appdata":
        return None
    return safe_owned_path(profile, appdata.name, local.name, *parts)


def read_owned_request(path):
    try:
        target = Path(path)
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if set(data) != {"nonce", "sid", "delete_settings", "delete_cache"}:
        return None
    if target.name != str(data.get("nonce")) + ".request.json":
        return None
    if not _NONCE_RE.fullmatch(str(data.get("nonce", ""))):
        return None
    if not request_matches_current_user(data.get("sid")):
        return None
    if not isinstance(data.get("delete_settings"), bool):
        return None
    if not isinstance(data.get("delete_cache"), bool):
        return None
    return data


def write_result_atomically(path, nonce, succeeded, failures=()):
    target = Path(path)
    failures = tuple(failures)
    if target.name != str(nonce) + ".result.json" or not _NONCE_RE.fullmatch(
            str(nonce)) or not isinstance(succeeded, bool):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"nonce": nonce, "succeeded": succeeded,
               "failure_count": len(failures)}
    handle = None
    try:
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=target.parent,
            suffix=".tmp")
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, target)
        return True
    except OSError:
        if handle is not None:
            try:
                handle.close()
                os.unlink(handle.name)
            except OSError:
                pass
        return False


def task_xml(sid, helper_executable):
    task = task_name_for_sid(sid)
    helper = Path(helper_executable)
    if task is None or helper.name != "MLCUserCleanup.exe" or not helper.is_absolute():
        return None
    command = escape(str(helper))
    user_sid = escape(sid)
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>MLC Player optional uninstall cleanup</Description></RegistrationInfo>
  <Principals><Principal id="Author"><UserId>{user_sid}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>false</StartWhenAvailable><RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings><AllowStartOnDemand>true</AllowStartOnDemand><Enabled>true</Enabled><Hidden>true</Hidden><RunOnlyIfIdle>false</RunOnlyIfIdle><WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT5M</ExecutionTimeLimit><Priority>7</Priority></Settings>
  <Actions Context="Author"><Exec><Command>{command}</Command><Arguments>--process-request</Arguments></Exec></Actions>
</Task>'''


def create_task_command(sid, helper_executable, xml_path=None):
    if task_xml(sid, helper_executable) is None:
        return None
    xml_path = Path(xml_path) if xml_path else Path(helper_executable).with_suffix(".task.xml")
    return ["schtasks.exe", "/Create", "/TN", task_name_for_sid(sid),
            "/XML", str(xml_path), "/F"]


def run_task_command(sid):
    task = task_name_for_sid(sid)
    return None if task is None else ["schtasks.exe", "/Run", "/TN", task]


def _remove_file(path, failures):
    if path is None:
        failures.append("unsafe-path")
        return
    try:
        if not path.exists():
            return
        if _is_reparse(path) or not path.is_file():
            failures.append(path.name)
            return
        path.unlink()
    except OSError:
        failures.append(path.name)


def _remove_allowed_directory(path, allowed, failures):
    if path is None:
        failures.append("unsafe-directory")
        return
    try:
        if not path.exists():
            return
        if _is_reparse(path) or not path.is_dir():
            failures.append(path.name)
            return
        for entry in path.iterdir():
            if _is_reparse(entry) or not entry.is_file() or not allowed(entry.name):
                failures.append(entry.name)
                continue
            _remove_file(entry, failures)
        try:
            path.rmdir()
        except OSError:
            failures.append(path.name)
    except OSError:
        failures.append(path.name)


def _remove_empty(path, failures):
    if path is None:
        return
    try:
        if not path.exists():
            return
        if _is_reparse(path) or not path.is_dir():
            failures.append(path.name)
            return
        path.rmdir()
    except OSError:
        failures.append(path.name)


def _delete_registry_tree(winreg_module, root, subkey):
    """Delete one owned registry tree and prove that it is gone."""
    try:
        with winreg_module.OpenKey(
                root, subkey, 0,
                winreg_module.KEY_READ | winreg_module.KEY_WRITE) as key:
            children = []
            index = 0
            while True:
                try:
                    children.append(winreg_module.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
        for child in children:
            if not _delete_registry_tree(
                    winreg_module, root, subkey + "\\" + child):
                return False
        winreg_module.DeleteKey(root, subkey)
    except FileNotFoundError:
        return True
    except OSError:
        return False

    try:
        with winreg_module.OpenKey(root, subkey):
            return False
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _delete_settings_registry(failures):
    if os.name != "nt":
        return
    try:
        import winreg
        deleted = _delete_registry_tree(
            winreg, winreg.HKEY_CURRENT_USER, "Software\\MLCPlayer")
    except (ImportError, OSError, ValueError):
        deleted = False
    if not deleted:
        failures.append("settings-registry")


def _delete_credentials(failures):
    if os.name != "nt":
        return
    try:
        library, _ = _windows_libraries()
        for prefix in ("MLCPlayer/OpenSubtitles/", "MLCPlayer/OpenSubtitles.ApiKey/"):
            count = wintypes.DWORD()
            items = ctypes.POINTER(ctypes.POINTER(CREDENTIALW))()
            if not library.CredEnumerateW(prefix + "*", 0, ctypes.byref(count),
                                          ctypes.byref(items)):
                if ctypes.get_last_error() != ERROR_NOT_FOUND:
                    failures.append("credentials")
                continue
            try:
                targets = [items[index].contents.TargetName
                           for index in range(count.value)]
            finally:
                library.CredFree(items)
            for target in targets:
                if not target.startswith(prefix):
                    failures.append("credential-namespace")
                elif not library.CredDeleteW(target, CRED_TYPE_GENERIC, 0) and \
                        ctypes.get_last_error() != ERROR_NOT_FOUND:
                    failures.append("credential-delete")
    except (OSError, ValueError, ctypes.ArgumentError):
        failures.append("credentials")


def cleanup_current_user(delete_settings, delete_cache, environ=None):
    env = dict(os.environ if environ is None else environ)
    failures = []
    roaming = Path(env["APPDATA"]) if env.get("APPDATA") else None
    local = Path(env["LOCALAPPDATA"]) if env.get("LOCALAPPDATA") else None
    if delete_settings:
        _delete_settings_registry(failures)
        _delete_credentials(failures)
        if roaming is None:
            failures.append("appdata-missing")
        else:
            _remove_file(safe_owned_path(roaming, "MLCPlayer", "MLCPlayer.ini"), failures)
    if delete_cache:
        if roaming is None:
            failures.append("appdata-missing")
        else:
            logs = safe_owned_path(roaming, "MLCPlayer", "logs")
            _remove_allowed_directory(
                logs, lambda name: name in {"uygulama.log", "uygulama.log.1"}, failures)
        if local is None:
            failures.append("localappdata-missing")
        else:
            thumbs = safe_owned_path(local, "MLCPlayer", "cache", "thumbnails")
            _remove_allowed_directory(thumbs, lambda name: bool(_THUMBNAIL_RE.fullmatch(name)), failures)
            try:
                if not _is_reparse(local):
                    for entry in local.iterdir():
                        if (entry.name.startswith("MLCPlayerUpdate_") and entry.is_dir() and
                                not _is_reparse(entry)):
                            _remove_allowed_directory(entry, lambda name: bool(_UPDATE_RE.fullmatch(name)), failures)
            except OSError:
                failures.append("update-scan")
    if roaming is not None and (delete_settings or delete_cache):
        _remove_empty(safe_owned_path(roaming, "MLCPlayer"), failures)
    if local is not None and delete_cache:
        _remove_empty(safe_owned_path(local, "MLCPlayer", "cache"), failures)
    return {"succeeded": not failures, "failures": tuple(failures)}


def process_requests(local_appdata=None):
    local = (Path(local_appdata) if local_appdata is not None else
             profile_local_appdata())
    root = (None if local is None else _safe_profile_owned_path(
        local, *_HELPER_PARTS[:-1], "ipc"))
    sid = current_user_sid()
    if root is None or not sid or not root.is_dir():
        return 2
    candidates = []
    try:
        for path in root.glob("*.request.json"):
            request = read_owned_request(path)
            if request is not None:
                candidates.append((path, request))
    except OSError:
        return 2
    if not candidates:
        return 3
    # Requests live in this user's private profile. Prefer the newest valid
    # request and discard older valid nonce files left by an interrupted run.
    candidates.sort(key=lambda item: item[0].stat().st_mtime_ns, reverse=True)
    path, request = candidates[0]
    for stale_path, _ in candidates[1:]:
        try:
            stale_path.unlink()
        except OSError:
            return 3
    outcome = cleanup_current_user(request["delete_settings"], request["delete_cache"])
    target = result_file(local, request["nonce"])
    if target is None or not write_result_atomically(
            target, request["nonce"], outcome["succeeded"], outcome["failures"]):
        return 4
    try:
        path.unlink()
    except OSError:
        return 5
    return 0 if outcome["succeeded"] else 6


def _read_install_id():
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"Software\MLCPlayer\UninstallCleanup") as key:
            value, kind = winreg.QueryValueEx(key, "InstallId")
        return value if kind == winreg.REG_SZ and _NONCE_RE.fullmatch(value) else None
    except OSError:
        return None


def _write_user_registration(install_id, sid, task_name, target):
    import winreg
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            r"Software\MLCPlayer\UninstallCleanup", 0,
                            winreg.KEY_SET_VALUE) as key:
        for name, value in (("InstallId", install_id), ("UserSid", sid),
                            ("TaskName", task_name), ("HelperPath", str(target)),
                            ("HelperSha256", digest)):
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _read_user_registration():
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r"Software\MLCPlayer\UninstallCleanup") as key:
        return {
            "install_id": winreg.QueryValueEx(key, "InstallId")[0],
            "sid": winreg.QueryValueEx(key, "UserSid")[0],
            "task_name": winreg.QueryValueEx(key, "TaskName")[0],
            "helper_path": Path(winreg.QueryValueEx(key, "HelperPath")[0]),
            "helper_hash": winreg.QueryValueEx(key, "HelperSha256")[0],
        }


def _registration_is_current(registration, install_id, sid, expected_path,
                             source_hash):
    if not registration or not install_id or not sid or not source_hash:
        return False
    registered_path = registration.get("helper_path")
    registered_hash = registration.get("helper_hash")
    return bool(
        registration.get("install_id") == install_id and
        registration.get("sid") == sid and
        registration.get("task_name") == task_name_for_sid(sid) and
        registered_path is not None and
        _same_path(registered_path, expected_path) and
        registered_hash == source_hash and
        _file_sha256(registered_path) == source_hash
    )


def _remove_legacy_helper(local, registration, install_id, sid):
    """Remove only the former exact helper layout after safe reprovisioning."""
    if not registration or registration.get("install_id") != install_id or \
            registration.get("sid") != sid or \
            registration.get("task_name") != task_name_for_sid(sid):
        return True
    registered_path = registration.get("helper_path")
    registered_hash = registration.get("helper_hash")
    expected = legacy_helper_location(local)
    if registered_path is None or not _same_path(registered_path, expected):
        return True
    safe_helper = _safe_profile_owned_path(local, *_LEGACY_HELPER_PARTS)
    if safe_helper is None or not isinstance(registered_hash, str) or \
            not re.fullmatch(r"[0-9a-fA-F]{64}", registered_hash) or \
            _file_sha256(safe_helper) != registered_hash.lower():
        return False
    failures = []
    legacy_ipc = _safe_profile_owned_path(
        local, *_LEGACY_HELPER_PARTS[:-1], "ipc")
    if legacy_ipc is None:
        return False
    _remove_allowed_directory(
        legacy_ipc, lambda name: bool(_IPC_RE.fullmatch(name)), failures)
    _remove_file(safe_helper, failures)
    for parts in (
            _LEGACY_HELPER_PARTS[:-1],
            _LEGACY_HELPER_PARTS[:-2],
            _LEGACY_HELPER_PARTS[:-3]):
        _remove_empty(_safe_profile_owned_path(local, *parts), failures)
    return not failures


def provision():
    sid = current_user_sid()
    local = profile_local_appdata()
    install_id = _read_install_id()
    if not sid or local is None or not install_id or os.name != "nt":
        return 2
    source = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    source_hash = _file_sha256(source)
    if not source_hash:
        return 3
    try:
        previous_registration = _read_user_registration()
    except (OSError, ValueError):
        previous_registration = None
    profile = local.parent.parent
    parent = _ensure_safe_directories(
        profile, (local.parent.name, local.name, *_HELPER_PARTS[:-1]))
    target = _safe_profile_owned_path(local, *_HELPER_PARTS)
    if parent is None or target is None:
        return 3
    if source != target:
        temporary = target.with_name(target.name + ".new")
        try:
            if temporary.exists() or _is_reparse(temporary):
                return 3
            shutil.copy2(source, temporary)
            if _safe_profile_owned_path(local, *_HELPER_PARTS[:-1]) is None:
                return 3
            os.replace(temporary, target)
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass
    if _safe_profile_owned_path(local, *_HELPER_PARTS) is None or \
            _file_sha256(target) != source_hash:
        return 3
    ipc = _ensure_safe_directories(
        profile, (local.parent.name, local.name, *_HELPER_PARTS[:-1], "ipc"))
    if ipc is None:
        return 3
    xml_path = target.with_suffix(".task.xml")
    xml_path.write_text(task_xml(sid, target), encoding="utf-16")
    try:
        completed = subprocess.run(create_task_command(sid, target, xml_path),
                                   check=False, capture_output=True, timeout=30)
    finally:
        try:
            xml_path.unlink()
        except OSError:
            pass
    if completed.returncode != 0:
        return 4
    if not _remove_legacy_helper(
            local, previous_registration, install_id, sid):
        return 5
    try:
        _write_user_registration(install_id, sid, task_name_for_sid(sid), target)
    except OSError:
        return 6
    return 0


def ensure_user_cleanup_task():
    """Provision from an installed player without showing another window."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    executable = Path(sys.executable).resolve().with_name("MLCUserCleanup.exe")
    if not executable.is_file():
        return False
    install_id = _read_install_id()
    sid = current_user_sid()
    local = profile_local_appdata()
    source_hash = _file_sha256(executable)
    try:
        registration = _read_user_registration()
        if local is not None and _registration_is_current(
                registration, install_id, sid, helper_location(local),
                source_hash):
            return True
    except (OSError, ValueError):
        pass
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run([str(executable), "--provision"], check=False,
                                   timeout=30, creationflags=flags)
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--process-request", action="store_true")
    group.add_argument("--provision", action="store_true")
    args = parser.parse_args(argv)
    if args.process_request:
        return process_requests()
    return provision()


if __name__ == "__main__":
    raise SystemExit(main())
