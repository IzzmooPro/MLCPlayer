# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fail closed when a pull request rewrites verification-ledger history."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = ROOT / "docs" / "VERIFICATION_LEDGER.json"


class LedgerHistoryError(RuntimeError):
    """The current ledger is not an exact append-only extension."""


def load_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_payloads(base, current):
    if base.get("schema_version") != current.get("schema_version"):
        raise LedgerHistoryError("schema_version changed")
    base_entries = base.get("entries")
    current_entries = current.get("entries")
    if not isinstance(base_entries, list) or not isinstance(current_entries, list):
        raise LedgerHistoryError("entries must be lists")
    if len(current_entries) < len(base_entries):
        raise LedgerHistoryError("historical entries were deleted")
    if current_entries[:len(base_entries)] != base_entries:
        raise LedgerHistoryError("historical entries were rewritten or reordered")


def verify_files(base_path, current_path=DEFAULT_LEDGER):
    verify_payloads(load_file(base_path), load_file(current_path))


def load_from_git(base_ref, relative_path="docs/VERIFICATION_LEDGER.json"):
    completed = subprocess.run(
        ["git", "show", f"{base_ref}:{relative_path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "no stderr"
        raise LedgerHistoryError(
            f"cannot read base ledger from {base_ref}: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise LedgerHistoryError("base ledger is invalid JSON") from error


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--current", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args(argv)
    try:
        verify_payloads(load_from_git(args.base_ref), load_file(args.current))
    except (LedgerHistoryError, OSError, json.JSONDecodeError) as error:
        print(f"LEDGER_APPEND_ONLY_FAILED: {error}", file=sys.stderr)
        return 1
    print("LEDGER_APPEND_ONLY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
