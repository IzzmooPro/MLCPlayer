# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Video format programinin insan/JSON/Windows devir sozlesmesi."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "VIDEO_FORMAT_ACCEPTANCE_PLAN.md"
MATRIX = ROOT / "docs" / "VIDEO_FORMAT_ACCEPTANCE_MATRIX.json"
INVENTORY = ROOT / "docs" / "VIDEO_FORMAT_CAPABILITY_INVENTORY.md"
WINDOWS = ROOT / "docs" / "WINDOWS_ACCEPTANCE_MATRIX.md"
LEDGER = ROOT / "docs" / "VERIFICATION_LEDGER.json"

REQUIRED_CASES = {
    "VF-CORE-01", "VF-CORE-02", "VF-CORE-03", "VF-CORE-04",
    "VF-CORE-05", "VF-CODEC-01", "VF-CODEC-02", "VF-HDR-01",
    "VF-HDR-02", "VF-HDR-03", "VF-HDR-04", "VF-HDR-05",
    "VF-PERF-01", "VF-RANGE-01", "VF-DISPLAY-01", "VF-META-01",
}
REQUIRED_BENCHMARKS = {"mpv", "vlc", "kodi", "mpc_video_renderer"}
ALLOWED_STATUS = {"NOT_RUN", "BLOCKED", "FAILED", "PASSED"}


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def payload():
    return json.loads(read(MATRIX))


def test_format_plan_and_machine_matrix_exist():
    assert PLAN.is_file()
    assert MATRIX.is_file()
    assert INVENTORY.is_file()


def test_matrix_is_exact_bounded_and_has_no_unearned_pass():
    data = payload()
    ledger_ids = {
        entry["id"] for entry in json.loads(read(LEDGER))["entries"]
    }
    assert data["schema_version"] == 1
    assert data["baseline_commit"] == (
        "5cfced39c24608d2a574f82009b294088dae9eb7")
    assert data["runtime"]["mpv_commit"] == "49418246f"
    assert data["plan_evidence_id"] == "EV-20260824-022"
    assert data["merge_evidence_id"] == "EV-20260824-023"
    assert data["capability_inventory"]["evidence_id"] == "EV-20260824-026"
    assert {
        data["plan_evidence_id"], data["merge_evidence_id"],
        data["capability_inventory"]["evidence_id"],
    } <= ledger_ids
    assert 0 < data["execution_policy"]["max_child_seconds"] <= 60
    assert data["execution_policy"]["automatic_retry"] is False
    assert data["execution_policy"]["native_requires_separate_approval"] is True

    cases = data["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert REQUIRED_CASES <= set(ids)
    for case in cases:
        assert case["status"] in ALLOWED_STATUS
        assert case["status"] != "PASSED"
        assert case["input_class"]
        assert case["display_state"]
        assert case["expected_path"]
        assert case["required_evidence"]
        assert case["blocker"]


def test_competitor_lessons_use_primary_sources_and_keep_claim_boundaries():
    data = payload()
    benchmarks = {item["id"]: item for item in data["benchmarks"]}
    assert REQUIRED_BENCHMARKS <= set(benchmarks)
    for benchmark in benchmarks.values():
        assert benchmark["source_urls"]
        assert all(url.startswith("https://")
                   for url in benchmark["source_urls"])
        assert benchmark["concrete_behavior"]
        assert benchmark["adoptable_lesson"]
        assert benchmark["claim_boundary"]


def test_capability_inventory_keeps_compiled_and_active_proof_separate():
    data = payload()["capability_inventory"]
    assert data["measured_commit"] == (
        "419d6c7cede0b6fad37425b28c375fc89e61b141")
    assert data["active_edid_sha256"] == (
        "f325d9f7e693b0ee79049ba342bf01066419110658a56452d0e0a20e44f4456f")
    assert data["active_dxgi_color_space"] == (
        "DXGI_COLOR_SPACE_RGB_FULL_G22_NONE_P709")
    assert data["active_hdr10_output_proven"] is False
    assert data["compiled_codec_drivers_are_hardware_proof"] is False
    assert data["media_opened"] is False
    assert data["all_cases_remain_blocked"] is True
    assert {"gpu", "gpu-next"} <= set(data["compiled_video_outputs"])
    assert "d3d11" in data["compiled_gpu_apis"]
    assert set(data["target_colorspace_hint_modes"]) == {
        "target", "source", "source-dynamic"}

    text = read(INVENTORY)
    for token in (
            "RTX 4070 Ti", "G274QPF E2", "EDID", "P709", "G2084",
            "gpu-next", "source-dynamic", "hwdec-current", "BLOCKED"):
        assert token.lower() in text.lower()


def test_plan_carries_concrete_user_visible_paths_and_evidence_rules():
    text = read(PLAN)
    for token in (
            "MPC Video Renderer", "Kodi", "VLC", "mpv",
            "HDR10+", "Dolby Vision", "HLG", "BT.709",
            "Girdi", "Isleme", "Cikis", "Donanim decode",
            "ekran goruntusu", "otomatik tekrar", "60 saniye"):
        assert token.lower() in text.lower()
    assert "VIDEO_FORMAT_ACCEPTANCE_MATRIX.json" in text
    assert "VERIFICATION_LEDGER.json" in text
    assert "CONTINUITY.md" in text


def test_windows_matrix_routes_p2_hdr_to_format_contract_without_pass():
    text = read(WINDOWS)
    section = text[text.index("## P2"):]
    assert "VIDEO_FORMAT_ACCEPTANCE_PLAN.md" in section
    assert "VIDEO_FORMAT_ACCEPTANCE_MATRIX.json" in section
    assert "WIN-P2-01" in section
    assert "BLOCKED" in section
