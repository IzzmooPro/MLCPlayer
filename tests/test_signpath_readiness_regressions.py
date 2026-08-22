# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_home_pages_link_the_code_signing_and_privacy_policies():
    readme = _read("README.md")
    readme_tr = _read("README.tr.md")

    for text in (readme, readme_tr):
        assert "CODE_SIGNING_POLICY.md" in text
        assert "PRIVACY.md" in text


def test_code_signing_policy_is_truthful_about_current_status_and_roles():
    policy = _read("CODE_SIGNING_POLICY.md")

    assert "Free code signing provided by SignPath.io" in policy
    assert "certificate by SignPath Foundation" in policy
    assert "IzzmooPro" in policy
    assert "manual approval" in policy.lower()
    assert "not Authenticode-signed" in policy
    assert "has not yet applied" in policy
    assert "been accepted" in policy
    assert "PRIVACY.md" in policy


def test_privacy_policy_discloses_every_current_network_category():
    policy = _read("PRIVACY.md")

    assert "api.github.com/repos/IzzmooPro/MLCPlayer/releases/latest" in policy
    assert "No telemetry or analytics" in policy
    assert "URL playback" in policy
    assert "OpenSubtitles" in policy
    assert "disabled" in policy.lower()
    assert "%APPDATA%\\MLCPlayer" in policy


def test_readiness_record_keeps_signpath_out_of_the_active_release_chain():
    readiness = _read("docs/SIGNPATH_READINESS.md")
    release_process = _read("docs/RELEASE_PROCESS.md")

    assert "not application-ready" in readiness
    assert "GitHub-hosted" in readiness
    assert "SignPath acceptance" in readiness
    assert "Ed25519" in readiness
    assert "SignPath is not currently part" in release_process
    assert "Authenticode must happen before" in release_process
    assert "Ed25519" in release_process
