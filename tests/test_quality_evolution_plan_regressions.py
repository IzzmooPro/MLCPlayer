# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The architecture and real-Windows quality plan stays durable and honest."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"
CONTINUITY = ROOT / "docs" / "CONTINUITY.md"
QUALITY_PLAN = ROOT / "docs" / "QUALITY_EVOLUTION_PLAN.md"
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE_INVENTORY.md"
WINDOWS_ACCEPTANCE = ROOT / "docs" / "WINDOWS_ACCEPTANCE_MATRIX.md"


def read(path):
    return path.read_text(encoding="utf-8")


def test_quality_documents_are_wired_into_the_current_handoff():
    assert QUALITY_PLAN.is_file()
    assert ARCHITECTURE.is_file()
    assert WINDOWS_ACCEPTANCE.is_file()

    agents = read(AGENTS)
    continuity = read(CONTINUITY)
    plan = read(QUALITY_PLAN)
    for path in (
            "docs/QUALITY_EVOLUTION_PLAN.md",
            "docs/ARCHITECTURE_INVENTORY.md",
            "docs/WINDOWS_ACCEPTANCE_MATRIX.md"):
        assert path in agents
        assert path in continuity
    assert "ARCHITECTURE_INVENTORY.md" in plan
    assert "WINDOWS_ACCEPTANCE_MATRIX.md" in plan


def test_architecture_work_is_measurement_first_and_not_a_line_count_refactor():
    plan = read(QUALITY_PLAN)
    inventory = read(ARCHITECTURE)
    combined = plan + inventory
    assert "Büyük patlama" in combined
    assert "satır sayısı tek başına" in combined.casefold()
    assert "davranış değişikliği" in combined
    assert "video_frame.py" in inventory
    assert "2623" in inventory
    assert "ÇALIŞTIRILMADI" in inventory


def test_windows_acceptance_never_promotes_missing_or_inherited_evidence():
    plan = read(QUALITY_PLAN)
    matrix = read(WINDOWS_ACCEPTANCE)
    combined = plan + matrix
    for marker in (
            "PASSED", "FAILED", "BLOCKED", "NOT_RUN",
            "artifact SHA-256", "exact commit", "süreç sızıntısı"):
        assert marker in combined
    assert "Bir sürümdeki PASS başka sürüme taşınmaz" in matrix
    assert "BLOCKED, PASS değildir" in matrix
    assert "HDR" in matrix
    assert "çoklu monitör" in matrix.casefold()


def test_every_completed_phase_has_one_update_transaction():
    plan = read(QUALITY_PLAN)
    for required in (
            "VERIFICATION_LEDGER.json",
            "CONTINUITY.md",
            "etki alanına uygun dar test",
            "tek güncelleme işlemi",
            "başarısız sonuç"):
        assert required.casefold() in plan.casefold()
