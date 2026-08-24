# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""A pull request may append ledger evidence but never rewrite its history."""

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import verify_ledger_append_only as guard  # noqa: E402


def write(path, entries, schema_version=1):
    path.write_text(json.dumps({
        "schema_version": schema_version,
        "entries": entries,
    }), encoding="utf-8")


def test_appending_new_entries_preserves_the_exact_prefix(tmp_path):
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    first = {"id": "EV-1", "value": "original"}
    write(base, [first])
    write(current, [first, {"id": "EV-2", "value": "new"}])
    guard.verify_files(base, current)


@pytest.mark.parametrize("current_entries", (
    [],
    [{"id": "EV-1", "value": "rewritten"}],
    [{"id": "EV-0", "value": "inserted"},
     {"id": "EV-1", "value": "original"}],
))
def test_deletion_rewrite_or_insertion_is_rejected(tmp_path, current_entries):
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    write(base, [{"id": "EV-1", "value": "original"}])
    write(current, current_entries)
    with pytest.raises(guard.LedgerHistoryError):
        guard.verify_files(base, current)


def test_schema_version_cannot_be_silently_rewritten(tmp_path):
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    write(base, [], schema_version=1)
    write(current, [], schema_version=2)
    with pytest.raises(guard.LedgerHistoryError):
        guard.verify_files(base, current)
