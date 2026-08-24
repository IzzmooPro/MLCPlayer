# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The durable handoff points to current, typed, machine-readable evidence."""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / "CLAUDE.md"
CONTINUITY = ROOT / "docs" / "CONTINUITY.md"
LEDGER = ROOT / "docs" / "VERIFICATION_LEDGER.json"
PROJECT_HISTORY = ROOT / "docs" / "PROJECT_STATUS.md"
ROADMAP_HISTORY = ROOT / "docs" / "ROADMAP.md"
ENGINEERING_HISTORY = ROOT / "docs" / "ENGINEERING_AUDIT.md"
SESSION_HOOK = ROOT / ".claude" / "hooks" / "session_start.py"

PROOF_LAYERS = {
    "deterministic",
    "hosted_ci",
    "source_build",
    "registry_artifact",
    "native_smoke",
    "installed_artifact",
    "external_submission",
}
RESULTS = {"passed", "failed", "blocked"}
SHA = re.compile(r"^[0-9a-f]{40}$")
ENTRY_ID = re.compile(r"^EV-[0-9]{8}-[0-9]{3}$")


def read(path):
    return path.read_text(encoding="utf-8")


def ledger():
    return json.loads(read(LEDGER))


def current_next_step():
    text = read(CONTINUITY)
    section = text.split("## Sıradaki tek adım", 1)[1]
    return section.split("\n## ", 1)[0].strip()


def test_every_agent_has_one_current_starting_point():
    assert AGENTS.is_file()
    assert CONTINUITY.is_file()
    agents = read(AGENTS)
    assert "docs/CONTINUITY.md" in agents
    assert "docs/VERIFICATION_LEDGER.json" in agents
    assert "docs/RELEASE_PROCESS.md" in agents
    assert "ayrı ayrı açık" in agents


def test_historical_status_cannot_claim_to_be_the_current_start():
    for path in (PROJECT_HISTORY, ROADMAP_HISTORY, ENGINEERING_HISTORY):
        opening = "\n".join(read(path).splitlines()[:12])
        assert "TARİHSEL" in opening.upper(), path
        assert "GÜNCEL" in opening.upper(), path
        assert "docs/CONTINUITY.md" in opening, path
    assert "## Sıradaki tek adım" not in read(PROJECT_HISTORY)


def test_legacy_agent_guide_points_to_current_dynamic_contracts():
    text = read(CLAUDE)
    assert "docs/CONTINUITY.md" in text
    assert "docs/VERIFICATION_LEDGER.json" in text
    assert "docs/RELEASE_PROCESS.md" in text
    assert "Release varlık sayısı sabit değildir" in text
    assert "Her release'e SEKİZ dosya" not in text
    assert "fetch_sources.py::FETCHABLE" not in text


def test_the_ledger_is_typed_complete_and_chronological():
    payload = ledger()
    assert payload["schema_version"] == 1
    entries = payload["entries"]
    assert entries
    assert len({entry["id"] for entry in entries}) == len(entries)

    timestamps = []
    for entry in entries:
        assert ENTRY_ID.fullmatch(entry["id"])
        assert entry["proof_layer"] in PROOF_LAYERS
        assert entry["result"] in RESULTS
        assert SHA.fullmatch(entry["commit"])
        assert entry["subject"].strip()
        assert entry["evidence"] and all(item.strip() for item in entry["evidence"])
        assert entry["summary"].strip()
        assert isinstance(entry["limitations"], list) and entry["limitations"]
        assert entry["next_action"].strip()
        timestamps.append(datetime.fromisoformat(
            entry["recorded_at_utc"].replace("Z", "+00:00")))
    assert timestamps == sorted(timestamps)


def test_ledger_commit_corrections_are_structured_later_and_unambiguous():
    entries = ledger()["entries"]
    positions = {entry["id"]: index for index, entry in enumerate(entries)}
    corrections = {}
    for index, entry in enumerate(entries):
        for correction in entry.get("corrects", []):
            target_id = correction["entry_id"]
            key = (target_id, correction["field"])
            assert target_id in positions
            assert positions[target_id] < index
            assert correction["field"] == "commit"
            assert correction["incorrect"] == entries[positions[target_id]]["commit"]
            assert SHA.fullmatch(correction["corrected"])
            assert key not in corrections
            corrections[key] = correction

    wrong = "770101fa5bf2ae58e7641befbb0e0c029c36ab17"
    right = "770101fbda976e7202871fe7499a83d6042fcd89"
    for target_id in (
            "EV-20260822-017", "EV-20260822-018",
            "EV-20260822-019", "EV-20260822-020"):
        correction = corrections[(target_id, "commit")]
        assert correction["incorrect"] == wrong
        assert correction["corrected"] == right


def test_every_ledger_commit_resolves_or_has_a_later_correction():
    entries = ledger()["entries"]
    corrections = {
        (item["entry_id"], item["field"]): item["corrected"]
        for entry in entries for item in entry.get("corrects", [])
    }
    hashes = {entry["commit"] for entry in entries} | set(corrections.values())
    completed = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        cwd=ROOT,
        input="\n".join(sorted(hashes)) + "\n",
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    available = {
        line.split()[0]
        for line in completed.stdout.splitlines()
        if line.endswith(" commit")
    }
    for entry in entries:
        commit = entry["commit"]
        if commit not in available:
            corrected = corrections[(entry["id"], "commit")]
            assert corrected in available


def test_current_state_points_to_the_latest_evidence_and_a_known_commit():
    text = read(CONTINUITY)
    payload = ledger()
    latest = payload["entries"][-1]
    assert f"`{latest['id']}`" in text

    match = re.search(
        r"Kayıt hazırlanırken doğrulanan HEAD: `([0-9a-f]{40})`", text)
    assert match, "CONTINUITY must carry one measured baseline SHA"
    assert any(entry["commit"] == match.group(1) for entry in payload["entries"])
    assert "Son push edilmiş taban:" not in text
    assert "git rev-list --left-right --count" in text
    assert "bu belge kendi commit hash'ini" in text
    assert "## Sıradaki tek adım" in text
    next_step = current_next_step()
    assert next_step
    assert "EV-20260821-045" not in next_step
    assert "commit etmek için kullanıcıdan" not in next_step


def test_proof_layers_are_kept_separate_in_agent_rules_and_current_state():
    combined = read(AGENTS) + read(CONTINUITY)
    for layer in PROOF_LAYERS:
        assert layer in combined
    assert "Bir katmandaki PASS başka katmana aktarılmaz" in combined
    assert "Kurulu v0.37" in combined


def test_session_start_injects_the_current_next_step_not_stale_history():
    completed = subprocess.run(
        [sys.executable, str(SESSION_HOOK)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    payload = json.loads(completed.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "git rev-parse --show-toplevel" in context
    assert "docs/CONTINUITY.md -> ## Sıradaki tek adım" in context
    assert "git log -1 --oneline --decorate" in context
    assert "git rev-list --left-right --count HEAD...origin/master" in context
    assert "Son kanıt" in context
    assert current_next_step() in context
    assert "docs/PROJECT_STATUS.md ->" not in context
    assert "SIRADAKİ PLAN (17 Ağustos 2026" not in context
