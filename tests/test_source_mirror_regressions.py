# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fail-closed corresponding-source contract and archive verification."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def module():
    path = ROOT / "packaging" / "fetch_sources.py"
    spec = importlib.util.spec_from_file_location("mlc_fetch", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def write_contract(path, *, status="ready", blockers=None, sources=None):
    path.write_text(json.dumps({
        "schema": 1,
        "status": status,
        "blockers": blockers or [],
        "sources": sources or [],
    }), encoding="utf-8")


def source_row(name="mpv-source.tar.gz", payload=b"source"):
    return {
        "name": name,
        "url": f"https://github.com/example/project/{name}",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def test_the_checked_in_contract_blocks_release_without_real_sources():
    fetch = module()
    assert fetch.blockers(), "eksik kaynaklara ragmen release kapisi acik"
    assert fetch.plan(), "dogrulanmis dogrudan kaynaklar kaydedilmemis"


def test_the_checked_in_contract_records_the_staged_libmpv_source_and_remaining_blockers():
    fetch = module()
    names = {item.name for item in fetch.plan()}
    for expected in (
        "Python-3.14.3.tar.xz",
        "qtbase-everywhere-src-6.10.2.tar.xz",
        "libmpv-corresponding-source-20260821-g49418246f.tar.zst",
        "openssl-4.0.1.tar.gz",
        "rust-crate-openssl-sys-0.9.117.crate",
        "yt-dlp-2026.08.19.tar.gz",
    ):
        assert expected in names
    assert len(names) == 83
    reasons = " ".join(fetch.blockers()).lower()
    assert "libmpv" not in reasons
    assert "cryptography" not in reasons
    assert "yt-dlp" not in reasons
    assert "license" in reasons


def test_binary_and_developer_archives_are_not_called_source():
    fetch = module()
    names = {item.name for item in fetch.plan()}
    forbidden = {
        "mpv-dev-x86_64-20260814-git-7b8915bc1d.7z",
        "yt-dlp.exe",
        "deno-x86_64-pc-windows-msvc.zip",
        "yt-dlp-THIRD_PARTY_LICENSES.txt",
    }
    assert names.isdisjoint(forbidden)


def test_a_ready_contract_with_a_source_archive_has_no_blocker(tmp_path):
    fetch = module()
    contract = tmp_path / "sources.json"
    write_contract(contract, sources=[source_row()])

    assert fetch.blockers(contract) == []
    assert [item.name for item in fetch.plan(contract)] == [
        "mpv-source.tar.gz"]


def test_not_ready_empty_and_explicit_reasons_all_block(tmp_path):
    fetch = module()
    contract = tmp_path / "sources.json"
    write_contract(contract, status="blocked", blockers=["inventory missing"])

    reasons = fetch.blockers(contract)
    assert "inventory missing" in reasons
    assert any("not ready" in reason for reason in reasons)
    assert any("no corresponding-source" in reason for reason in reasons)


def test_the_plan_reads_url_size_and_digest_from_the_contract(tmp_path):
    fetch = module()
    contract = tmp_path / "sources.json"
    payload = b"exact source"
    write_contract(contract, sources=[source_row(payload=payload)])

    item = fetch.plan(contract)[0]
    assert item.url.startswith("https://")
    assert item.size == len(payload)
    assert item.sha256 == hashlib.sha256(payload).hexdigest()


def test_the_plan_rejects_duplicate_or_path_names(tmp_path):
    fetch = module()
    contract = tmp_path / "sources.json"
    row = source_row()
    write_contract(contract, sources=[row, row])
    try:
        fetch.plan(contract)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate source name accepted")

    row = source_row(name="../outside.tar.gz")
    write_contract(contract, sources=[row])
    try:
        fetch.plan(contract)
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal source name accepted")


def test_the_plan_never_leaves_the_trusted_hosts(tmp_path):
    fetch = module()
    contract = tmp_path / "sources.json"
    write_contract(contract, sources=[source_row()])
    from urllib.parse import urlsplit

    for item in fetch.plan(contract):
        host = urlsplit(item.url).hostname or ""
        assert host in fetch.TRUSTED_HOSTS


def test_the_reviewed_qt_mirror_is_explicitly_trusted():
    fetch = module()
    assert "ftp.fau.de" in fetch.TRUSTED_HOSTS


def test_the_official_crates_io_source_hosts_are_explicitly_trusted():
    fetch = module()
    assert {"crates.io", "static.crates.io"} <= fetch.TRUSTED_HOSTS


def test_a_wrong_digest_is_rejected_and_removed(tmp_path):
    fetch = module()
    target = tmp_path / "bad.bin"
    target.write_bytes(b"wrong")

    assert fetch.verify(target, 5, "0" * 64) is False
    assert not target.exists()


def test_a_correct_digest_is_accepted(tmp_path):
    fetch = module()
    payload = b"correct"
    target = tmp_path / "good.bin"
    target.write_bytes(payload)

    assert fetch.verify(
        target, len(payload), hashlib.sha256(payload).hexdigest()) is True
    assert target.exists()


def test_a_size_mismatch_is_rejected(tmp_path):
    fetch = module()
    target = tmp_path / "short.bin"
    target.write_bytes(b"short")

    assert fetch.verify(target, 999, hashlib.sha256(b"short").hexdigest()) \
        is False


def test_the_mirror_folder_is_ignored_by_git():
    fetch = module()
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert fetch.OUTPUT_DIR_NAME in ignore


def test_import_does_not_download_anything():
    source = (ROOT / "packaging" / "fetch_sources.py").read_text(
        encoding="utf-8")
    assert 'if __name__ == "__main__":' in source
    assert "urlopen" not in source.split('if __name__ == "__main__":')[0] \
        .split("def ")[0]


def test_default_cli_refuses_a_blocked_contract(capsys):
    fetch = module()
    assert fetch.main([]) == 1
    assert "CLOSED" in capsys.readouterr().out


def test_unknown_cli_argument_is_rejected(capsys):
    fetch = module()
    assert fetch.main(["--unknown"]) == 1
    assert "Unknown argument" in capsys.readouterr().out
