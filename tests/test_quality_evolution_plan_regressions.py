# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The architecture and real-Windows quality plan stays durable and honest."""

import hashlib
import json
import re

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"
CONTINUITY = ROOT / "docs" / "CONTINUITY.md"
QUALITY_PLAN = ROOT / "docs" / "QUALITY_EVOLUTION_PLAN.md"
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE_INVENTORY.md"
ARCHITECTURE_DATA = ROOT / "docs" / "ARCHITECTURE_INVENTORY.json"
WINDOWS_ACCEPTANCE = ROOT / "docs" / "WINDOWS_ACCEPTANCE_MATRIX.md"


def read(path):
    return path.read_text(encoding="utf-8")


def test_quality_documents_are_wired_into_the_current_handoff():
    assert QUALITY_PLAN.is_file()
    assert ARCHITECTURE.is_file()
    assert ARCHITECTURE_DATA.is_file()
    assert WINDOWS_ACCEPTANCE.is_file()

    agents = read(AGENTS)
    continuity = read(CONTINUITY)
    plan = read(QUALITY_PLAN)
    for path in (
            "docs/QUALITY_EVOLUTION_PLAN.md",
            "docs/ARCHITECTURE_INVENTORY.md",
            "docs/ARCHITECTURE_INVENTORY.json",
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
    assert "SORUMLULUK ANALİZİ TAMAMLANDI" in inventory
    for marker in (
            "64", "61", "53", "41", "58", "19",
            "İlk güvenli ayrıştırma adayı", "app/media_targets.py",
            "normalize_external_target", "SubtitleTrackWatcher"):
        assert marker in inventory
    assert "ürün kodu değiştirilmedi" in inventory.casefold()


def test_machine_inventory_matches_the_exact_six_sources():
    payload = json.loads(read(ARCHITECTURE_DATA))
    assert payload["schema_version"] == 1
    assert payload["status"] == "analyzed"
    modules = payload["modules"]
    assert len(modules) == 6
    assert len({row["path"] for row in modules}) == 6

    for row in modules:
        source = ROOT / row["path"]
        raw = source.read_bytes()
        text = raw.decode("utf-8")
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        assert hashlib.sha256(normalized.encode("utf-8")).hexdigest() == row["sha256"]
        assert len(text.splitlines()) == row["lines"]
        assert len(re.findall(r"(?m)^class\s+([A-Za-z_]\w*)", text)) == row["classes"]
        assert len(re.findall(r"(?m)^def\s+([A-Za-z_]\w*)", text)) == row["top_functions"]
        assert len(re.findall(r"(?m)^    def\s+([A-Za-z_]\w*)", text)) == row["indented_functions"]
        state = set(re.findall(r"self\.([A-Za-z_]\w*)\s*=", text))
        assert len(state) == row["self_state"]


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


def test_every_p0_row_has_an_honest_execution_mapping_and_exact_status():
    matrix = read(WINDOWS_ACCEPTANCE)
    for scenario_id in (
            "WIN-P0-01", "WIN-P0-02", "WIN-P0-03", "WIN-P0-04",
            "WIN-P0-05", "WIN-P0-06", "WIN-P0-07", "WIN-P0-08"):
        assert f"### {scenario_id}" in matrix

    for marker in (
            "Deterministik sınır", "Native ölçüm", "Exact girdiler",
            "Açık boşluk", "Eşleme PASS değildir",
            "tests/native_shutdown_acceptance.py",
            "tests/run_native_overlay_matrix.py",
            "tests/run_physical_acceptance.py",
            "tests/test_single_instance_regressions.py"):
        assert marker in matrix

    p0_section = matrix.split("## P0", 1)[1].split("## P1", 1)[0]
    p0_table = p0_section.split("Bu eşleme", 1)[0]
    rows = {}
    for line in p0_table.splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and cells[0].startswith("WIN-P0-"):
            rows[cells[0]] = cells[-1]
    assert rows["WIN-P0-01"] == "PASSED"
    assert rows["WIN-P0-02"] == "PASSED"
    assert p0_table.count("NOT_RUN") == 6
    assert "EV-20260823-019" in p0_section
    assert "EV-20260823-020" in p0_section
    assert "EV-20260823-022" in p0_section
    assert "EV-20260823-024" in p0_section
    assert "EV-20260824-002" in p0_section
    assert "0xC0000005" in p0_section
    assert "os._exit" in p0_section


def test_every_completed_phase_has_one_update_transaction():
    plan = read(QUALITY_PLAN)
    for required in (
            "VERIFICATION_LEDGER.json",
            "CONTINUITY.md",
            "etki alanına uygun dar test",
            "tek güncelleme işlemi",
            "başarısız sonuç"):
        assert required.casefold() in plan.casefold()
