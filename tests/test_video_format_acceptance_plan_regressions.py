# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Video format programinin insan/JSON/Windows devir sozlesmesi."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "VIDEO_FORMAT_ACCEPTANCE_PLAN.md"
MATRIX = ROOT / "docs" / "VIDEO_FORMAT_ACCEPTANCE_MATRIX.json"
MEDIA = ROOT / "docs" / "VIDEO_FORMAT_MEDIA_MANIFEST.json"
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
    assert MEDIA.is_file()


def media_payload():
    return json.loads(read(MEDIA))


def test_media_candidates_are_fail_closed_and_cover_every_case():
    matrix = payload()
    media = media_payload()
    assert media["schema_version"] == 1
    assert media["status"] == "partially_fingerprinted"
    assert media["fingerprinted_state_enabled"] is True
    assert media["acquisition_or_generation_performed"] is True
    assert media["native_media_opened"] is False
    assert matrix["media_policy"]["manifest_document"] == (
        "docs/VIDEO_FORMAT_MEDIA_MANIFEST.json")
    assert matrix["media_policy"]["manifest_status"] == (
        "partially_fingerprinted")
    assert matrix["media_policy"]["manifest_evidence_id"] == (
        "EV-20260824-041")
    ledger_ids = {
        entry["id"] for entry in json.loads(read(LEDGER))["entries"]}
    assert matrix["media_policy"]["manifest_evidence_id"] in ledger_ids
    assert matrix["media_policy"]["acquisition_or_generation_performed"] is True

    source_ids = {item["id"] for item in media["sources"]}
    candidates = {item["id"]: item for item in media["candidates"]}
    assert len(candidates) == len(media["candidates"])
    assert set(media["case_bindings"]) == REQUIRED_CASES
    for case_id, candidate_ids in media["case_bindings"].items():
        assert candidate_ids, case_id
        assert set(candidate_ids) <= set(candidates)
        assert all(case_id in candidates[item_id]["intended_cases"]
                   for item_id in candidate_ids)

    for candidate_id, candidate in candidates.items():
        assert candidate["source_id"] in source_ids
        assert candidate["intended_cases"]
        if candidate_id == "SYN-SDR709-01":
            assert candidate["state"] == "fingerprinted"
            assert candidate["exact_object_locator"] == (
                "private-local:SYN-SDR709-01")
            assert candidate["local_identity"]
            assert candidate["generation_identity"]
            assert candidate["blocker"] is None
        else:
            assert candidate["state"] == "candidate_only"
            assert candidate["exact_object_locator"] is None
            assert candidate["local_identity"] is None
            assert candidate["blocker"]
            if candidate["kind"].startswith("synthetic") or (
                    candidate["kind"] == "derived_synthetic"):
                assert candidate["generation_identity"] is None
    reverse = {candidate_id: set() for candidate_id in candidates}
    for case_id, candidate_ids in media["case_bindings"].items():
        for candidate_id in candidate_ids:
            reverse[candidate_id].add(case_id)
    for candidate_id, candidate in candidates.items():
        assert reverse[candidate_id] == set(candidate["intended_cases"])
        for reference_id in candidate.get("recipe_reference_ids", []):
            assert reference_id in source_ids
        parent_id = candidate.get("derived_from_candidate_id")
        if parent_id:
            assert parent_id in candidates
            assert parent_id != candidate_id


def test_media_manifest_has_provenance_and_strict_identity_contract():
    media = media_payload()
    required = set(media["fingerprinted_requirements"])
    assert {
        "exact_object_locator", "license_or_use_basis", "file_size",
        "sha256", "ffprobe_binary_sha256", "ffprobe_version",
        "ffprobe_argv", "normalized_ffprobe_json_sha256",
        "normalized_ffprobe_json_artifact",
        "selected_video_stream", "verified_claims",
    } <= required
    assert {
        "generator_binary_sha256", "generator_version", "generator_argv",
        "canonical_recipe_sha256", "input_and_sidecar_sha256",
    } <= set(media["generated_requirements"])
    assert {
        "member_id", "exact_object_locator", "file_size", "sha256",
        "normalized_ffprobe_json_sha256", "selected_video_stream",
    } <= set(media["artifact_set_requirements"])
    assert {
        "member_id", "encoding", "file_size", "sha256", "cue_times",
        "style_summary_when_ass",
    } <= set(media["sidecar_requirements"])
    assert media["privacy_policy"]["publish_local_paths"] is False
    assert media["privacy_policy"]["publish_user_media_names"] is False
    assert media["privacy_policy"]["normalize_ffprobe_format_filename"] is True
    assert media["claim_policy"]["catalog_text_is_probe_evidence"] is False
    assert media["claim_policy"]["codec_name_is_dynamic_hdr_proof"] is False
    assert media["claim_policy"][
        "dynamic_hdr_requires_frame_or_stream_side_data"] is True
    assert media["claim_policy"][
        "dolby_vision_requires_profile_level_and_rpu_evidence"] is True
    for format_name in ("hdr10plus", "dolby_vision"):
        format_requirements = set(
            media["format_specific_requirements"][format_name])
        assert {
            "supplemental_probe_binary_sha256",
            "supplemental_probe_version",
            "supplemental_probe_argv",
            "supplemental_probe_output_sha256",
        } <= format_requirements
    candidates = {item["id"]: item for item in media["candidates"]}
    assert {"SYN-OVERLAY-SRT-01", "SYN-OVERLAY-ASS-01"} <= set(
        media["case_bindings"]["VF-CORE-05"])
    core_overlay = media["case_requirements"]["VF-CORE-05"]
    assert set(core_overlay["video_any_of"]) == {
        "NFLX-SOL-HDR10-01", "SYN-HDR10-01"}
    assert set(core_overlay["sidecars_all_of"]) == {
        "SYN-OVERLAY-SRT-01", "SYN-OVERLAY-ASS-01"}
    assert candidates["SYN-RANGE-PAIR-01"]["planned_member_count"] == 4
    assert len(candidates["SYN-RANGE-PAIR-01"]["planned_members"]) == 4
    assert candidates["SYN-META-ANOMALY-01"]["planned_member_count"] == 2
    assert len(candidates["SYN-META-ANOMALY-01"]["planned_members"]) == 2
    for candidate_id in (
            "SYN-RANGE-PAIR-01", "SYN-META-ANOMALY-01",
            "NFLX-SOL-DV-01"):
        assert candidates[candidate_id]["planned_member_model"].startswith(
            "artifacts[]")
    assert candidates["NFLX-SOL-HDR10-01"][
        "planned_member_model"].startswith("artifacts[]")
    for candidate_id in (
            "SYN-SDR709-01", "SYN-HDR10-01", "SYN-OVERLAY-SRT-01",
            "SYN-OVERLAY-ASS-01", "SYN-AV1-HDR10-01",
            "SYN-VP9P2-HDR-01", "SYN-HLG-01", "SYN-HDR10PLUS-01",
            "SYN-DV84-01", "SYN-RANGE-PAIR-01",
            "SYN-META-ANOMALY-01"):
        assert candidates[candidate_id]["source_id"] == (
            "mlc_project_generated_fixture")
    for source in media["sources"]:
        assert source["source_url"].startswith("https://")
        assert source["license_or_use_basis"]
        assert source["primary_source"] is True
    deferred = media["deferred_external_options"]
    assert len({item["id"] for item in deferred}) == len(deferred)
    for item in deferred:
        assert item["source_url"].startswith("https://")
        assert item["license_or_use_basis"]
        assert item["deferred_reason"]
        assert item["redistribution_allowed"] is False or (
            item["id"] == "BLENDER-SDR-OPTION")


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
    assert "VIDEO_FORMAT_MEDIA_MANIFEST.json" in text
    assert "VERIFICATION_LEDGER.json" in text
    assert "CONTINUITY.md" in text


def test_windows_matrix_routes_p2_hdr_to_format_contract_without_pass():
    text = read(WINDOWS)
    section = text[text.index("## P2"):]
    assert "VIDEO_FORMAT_ACCEPTANCE_PLAN.md" in section
    assert "VIDEO_FORMAT_ACCEPTANCE_MATRIX.json" in section
    assert "WIN-P2-01" in section
    assert "BLOCKED" in section
