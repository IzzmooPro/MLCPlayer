# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The verified libmpv source bundle is reusable without another build."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "packaging" / "stage_libmpv_source.py"


def module():
    spec = importlib.util.spec_from_file_location("mlc_stage_libmpv", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def item(payload=b"captured source", name="libmpv-source.tar.zst"):
    return SimpleNamespace(
        name=name,
        url=f"https://github.com/example/releases/download/v1/{name}",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_checked_in_contract_binds_the_exact_future_release_asset():
    stage = module()
    row = stage.source_item()
    assert row.name == (
        "libmpv-corresponding-source-20260821-g49418246f.tar.zst")
    assert row.url == (
        "https://github.com/IzzmooPro/MLCPlayer/releases/download/v0.38/"
        "libmpv-corresponding-source-20260821-g49418246f.tar.zst")
    assert row.size == 557940716
    assert row.sha256 == (
        "5ce4be96436566d9eca18727a1779a6534d6d5e9985178baf87ff3521753efc0")


def test_valid_source_is_staged_under_the_contract_name(tmp_path):
    stage = module()
    payload = b"captured source"
    source = tmp_path / "part-00"
    source.write_bytes(payload)
    output = tmp_path / "mirror"

    target = stage.stage(source, target_dir=output, item=item(payload))

    assert target == output / "libmpv-source.tar.zst"
    assert target.read_bytes() == payload


def test_wrong_source_never_overwrites_an_existing_target(tmp_path):
    stage = module()
    expected = b"expected source"
    existing = b"keep this recoverable copy"
    contract = item(expected)
    output = tmp_path / "mirror"
    output.mkdir()
    target = output / contract.name
    target.write_bytes(existing)
    wrong = tmp_path / "part-00"
    wrong.write_bytes(b"wrong")

    try:
        stage.stage(wrong, target_dir=output, item=contract)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong source was accepted")

    assert target.read_bytes() == existing


def test_an_existing_verified_stage_needs_no_source_or_rebuild(tmp_path):
    stage = module()
    payload = b"already staged"
    contract = item(payload)
    output = tmp_path / "mirror"
    output.mkdir()
    target = output / contract.name
    target.write_bytes(payload)

    assert stage.stage(None, target_dir=output, item=contract) == target
