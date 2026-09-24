# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
from app import user_cleanup_helper as helper
import hashlib


class _RegistryKey:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeWinreg:
    KEY_READ = 1
    KEY_WRITE = 2
    HKEY_CURRENT_USER = object()

    def __init__(self, paths, delete_is_noop=False):
        self.paths = set(paths)
        self.delete_is_noop = delete_is_noop

    def OpenKey(self, _root, path, *_):
        if path not in self.paths:
            raise FileNotFoundError(path)
        return _RegistryKey(path)

    def EnumKey(self, key, index):
        prefix = key.path + "\\"
        children = sorted({
            path[len(prefix):].split("\\", 1)[0]
            for path in self.paths if path.startswith(prefix)
        })
        if index >= len(children):
            raise OSError("no more keys")
        return children[index]

    def DeleteKey(self, _root, path):
        if any(item.startswith(path + "\\") for item in self.paths):
            raise OSError("key has children")
        if not self.delete_is_noop:
            self.paths.remove(path)


def test_task_names_are_sid_bound_and_reject_untrusted_text():
    assert helper.task_name_for_sid("S-1-5-21-42") == "\\MLCPlayer_UninstallCleanup_S-1-5-21-42"
    assert helper.task_name_for_sid("S-1-5-21-42;cmd") is None
    assert helper.task_name_for_sid("") is None


def test_request_match_never_accepts_a_missing_or_different_sid(monkeypatch):
    monkeypatch.setattr(helper, "current_user_sid", lambda: "S-1-5-21-1")
    assert helper.request_matches_current_user("S-1-5-21-1")
    assert not helper.request_matches_current_user("S-1-5-21-2")
    assert not helper.request_matches_current_user("")


def test_helper_uses_the_schedulable_per_user_programs_path(tmp_path):
    assert helper.helper_location(tmp_path) == (
        tmp_path / "Programs" / "MLC Player" / "UninstallCleanup" /
        "v1" / "MLCUserCleanup.exe"
    )


def test_task_is_hidden_triggerless_sid_bound_and_on_demand(tmp_path):
    exe = helper.helper_location(tmp_path)
    xml = helper.task_xml("S-1-5-21-42", exe)
    assert "<Triggers>" not in xml
    assert "<LogonType>InteractiveToken</LogonType>" in xml
    assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
    assert "<Hidden>true</Hidden>" in xml
    assert "<AllowStartOnDemand>true</AllowStartOnDemand>" in xml
    assert "--process-request" in xml
    create = helper.create_task_command("S-1-5-21-42", exe, tmp_path / "task.xml")
    assert create[:4] == ["schtasks.exe", "/Create", "/TN", "\\MLCPlayer_UninstallCleanup_S-1-5-21-42"]
    assert "/XML" in create
    assert helper.run_task_command("S-1-5-21-42") == ["schtasks.exe", "/Run", "/TN", "\\MLCPlayer_UninstallCleanup_S-1-5-21-42"]
    assert helper.create_task_command("S-1-5-21-42;bad", exe) is None
    assert helper.create_task_command("S-1-5-21-42", tmp_path / "other.exe") is None


def test_result_is_atomically_bound_to_a_hex_nonce(tmp_path):
    nonce = "a" * 32
    path = helper.result_file(tmp_path, nonce)
    assert path is not None
    assert helper.write_result_atomically(path, nonce, True)
    assert path.read_text(encoding="utf-8") == '{"failure_count":0,"nonce":"' + nonce + '","succeeded":true}'
    assert helper.request_file(tmp_path, "bad-nonce") is None
    assert helper.request_file(tmp_path, "a" * 31) is None


def test_owned_path_rejects_traversal_and_parent_symlinks(tmp_path):
    assert helper.safe_owned_path(tmp_path, "MLCPlayer", "logs") == tmp_path / "MLCPlayer" / "logs"
    assert helper.safe_owned_path(tmp_path, "..", "outside") is None
    linked = tmp_path / "MLCPlayer"
    linked.symlink_to(tmp_path, target_is_directory=True)
    assert helper.safe_owned_path(tmp_path, "MLCPlayer", "logs") is None


def test_safe_directory_creation_rejects_a_reparse_ancestor(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    programs = tmp_path / "Programs"
    programs.symlink_to(outside, target_is_directory=True)

    assert helper._ensure_safe_directories(
        tmp_path, helper._HELPER_PARTS[:-1]) is None
    assert not (outside / "MLC Player").exists()


def test_profile_local_appdata_rejects_an_appdata_reparse(tmp_path):
    profile = tmp_path / "profile"
    outside = tmp_path / "outside"
    profile.mkdir()
    outside.mkdir()
    (profile / "AppData").symlink_to(outside, target_is_directory=True)
    (outside / "Local").mkdir()

    assert helper.profile_local_appdata({"USERPROFILE": str(profile)}) is None
    assert helper._safe_profile_owned_path(
        profile / "AppData" / "Local", *helper._HELPER_PARTS) is None


def test_current_registration_requires_new_path_and_current_binary_hash(tmp_path):
    sid = "S-1-5-21-42"
    expected = helper.helper_location(tmp_path)
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"current helper")
    digest = hashlib.sha256(expected.read_bytes()).hexdigest()
    registration = {
        "install_id": "a" * 32,
        "sid": sid,
        "task_name": helper.task_name_for_sid(sid),
        "helper_path": expected,
        "helper_hash": digest,
    }

    assert helper._registration_is_current(
        registration, "a" * 32, sid, expected, digest)
    legacy = dict(registration, helper_path=helper.legacy_helper_location(tmp_path))
    assert not helper._registration_is_current(
        legacy, "a" * 32, sid, expected, digest)
    assert not helper._registration_is_current(
        registration, "a" * 32, sid, expected, "b" * 64)


def test_legacy_helper_migration_removes_only_the_exact_owned_layout(tmp_path):
    sid = "S-1-5-21-42"
    local = tmp_path / "profile" / "AppData" / "Local"
    local.mkdir(parents=True)
    legacy = helper.legacy_helper_location(local)
    ipc = legacy.parent / "ipc"
    ipc.mkdir(parents=True)
    legacy.write_bytes(b"current helper")
    request = ipc / (("c" * 32) + ".request.json")
    request.write_text("{}", encoding="utf-8")
    digest = hashlib.sha256(legacy.read_bytes()).hexdigest()
    registration = {
        "install_id": "a" * 32,
        "sid": sid,
        "task_name": helper.task_name_for_sid(sid),
        "helper_path": legacy,
        "helper_hash": digest,
    }

    assert helper._remove_legacy_helper(
        local, registration, "a" * 32, sid)
    assert not legacy.exists()
    assert not request.exists()
    assert not (local / "MLCPlayer").exists()


def test_legacy_helper_migration_rejects_hash_mismatch(tmp_path):
    sid = "S-1-5-21-42"
    local = tmp_path / "profile" / "AppData" / "Local"
    local.mkdir(parents=True)
    legacy = helper.legacy_helper_location(local)
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"old helper")
    registration = {
        "install_id": "a" * 32,
        "sid": sid,
        "task_name": helper.task_name_for_sid(sid),
        "helper_path": legacy,
        "helper_hash": hashlib.sha256(b"different registered helper").hexdigest(),
    }

    assert not helper._remove_legacy_helper(
        local, registration, "a" * 32, sid)
    assert legacy.exists()


def test_legacy_upgrade_accepts_a_different_but_registered_old_binary(tmp_path):
    sid = "S-1-5-21-42"
    local = tmp_path / "profile" / "AppData" / "Local"
    local.mkdir(parents=True)
    legacy = helper.legacy_helper_location(local)
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"old-version")
    old_digest = hashlib.sha256(legacy.read_bytes()).hexdigest()
    registration = {
        "install_id": "a" * 32,
        "sid": sid,
        "task_name": helper.task_name_for_sid(sid),
        "helper_path": legacy,
        "helper_hash": old_digest,
    }

    assert helper._remove_legacy_helper(
        local, registration, "a" * 32, sid)
    assert not legacy.exists()


def test_cleanup_removes_only_exact_owned_files(tmp_path, monkeypatch):
    roaming = tmp_path / "roaming"
    local = tmp_path / "local"
    logs = roaming / "MLCPlayer" / "logs"
    thumbs = local / "MLCPlayer" / "cache" / "thumbnails"
    update = local / "MLCPlayerUpdate_123"
    logs.mkdir(parents=True)
    thumbs.mkdir(parents=True)
    update.mkdir()
    (logs / "uygulama.log").write_text("x")
    (logs / "foreign.txt").write_text("keep")
    (thumbs / (("a" * 64) + ".jpg")).write_text("x")
    (thumbs / "foreign.jpg").write_text("keep")
    (update / "MLCPlayer_Setup_v0.41.exe").write_text("x")
    (update / "foreign.bin").write_text("keep")
    monkeypatch.setattr(helper, "_delete_settings_registry", lambda failures: None)
    monkeypatch.setattr(helper, "_delete_credentials", lambda failures: None)

    result = helper.cleanup_current_user(True, True, {
        "APPDATA": str(roaming), "LOCALAPPDATA": str(local)})

    assert not result["succeeded"]
    assert not (logs / "uygulama.log").exists()
    assert (logs / "foreign.txt").exists()
    assert not (thumbs / (("a" * 64) + ".jpg")).exists()
    assert (thumbs / "foreign.jpg").exists()
    assert not (update / "MLCPlayer_Setup_v0.41.exe").exists()
    assert (update / "foreign.bin").exists()


def test_settings_registry_tree_is_recursive_and_verified_absent():
    root = r"Software\MLCPlayer"
    fake = _FakeWinreg({root, root + r"\MLCPlayer",
                        root + r"\MLCPlayer\subtitle"})

    assert helper._delete_registry_tree(
        fake, fake.HKEY_CURRENT_USER, root) is True
    assert fake.paths == set()


def test_settings_registry_delete_rejects_a_false_success():
    root = r"Software\MLCPlayer"
    fake = _FakeWinreg({root}, delete_is_noop=True)

    assert helper._delete_registry_tree(
        fake, fake.HKEY_CURRENT_USER, root) is False
    assert fake.paths == {root}


def test_request_requires_exact_sid_and_separate_result_file(tmp_path, monkeypatch):
    nonce = "b" * 32
    path = helper.request_file(tmp_path, nonce)
    path.parent.mkdir(parents=True)
    path.write_text('{"nonce":"' + nonce + '","sid":"S-1-5-21-9",'
                    '"delete_settings":true,"delete_cache":false}')
    monkeypatch.setattr(helper, "current_user_sid", lambda: "S-1-5-21-9")
    assert helper.read_owned_request(path)["delete_settings"] is True
    assert helper.result_file(tmp_path, nonce) != path
