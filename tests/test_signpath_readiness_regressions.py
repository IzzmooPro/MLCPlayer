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

    assert "submitted on 23 August 2026" in readme
    assert "23 Ağustos 2026 tarihinde gönderildi" in readme_tr


def test_code_signing_policy_is_truthful_about_current_status_and_roles():
    policy = _read("CODE_SIGNING_POLICY.md")
    policy_flat = " ".join(policy.split())

    assert "Free code signing provided by SignPath.io" in policy
    assert "certificate by SignPath Foundation" in policy
    assert "IzzmooPro" in policy
    assert "manual approval" in policy.lower()
    assert "not Authenticode-signed" in policy
    assert "application was submitted on 23 August 2026" in policy
    assert "awaiting SignPath Foundation's decision" in policy_flat
    assert "has not yet applied" not in policy
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

    assert "Submission status: SUBMITTED - AWAITING DECISION" in readiness
    assert "NOT SUBMITTED" not in readiness
    assert "not application-ready" not in readiness
    assert "It has not been run" not in readiness
    assert "Why the hosted build is not accepted yet" not in readiness
    assert "GitHub-hosted" in readiness
    assert "SignPath acceptance" in readiness
    assert "Ed25519" in readiness
    assert "SignPath is not currently part" in release_process
    assert "Authenticode must happen before" in release_process
    assert "Ed25519" in release_process


def test_signpath_foundation_application_is_submitted_but_not_accepted():
    application = _read("docs/SIGNPATH_FOUNDATION_APPLICATION.md")
    application_flat = " ".join(application.split())
    workflow = _read(".github/workflows/build-unsigned-main.yml")

    assert "Submission status: SUBMITTED - AWAITING DECISION" in application
    assert "https://github.com/IzzmooPro/MLCPlayer" in application
    assert "https://github.com/IzzmooPro/MLCPlayer/releases/latest" in application
    assert "https://signpath.org/terms.html" in application
    assert "https://docs.signpath.io/trusted-build-systems/github" in application
    assert "CODE_SIGNING_POLICY.md" in application
    assert "PRIVACY.md" in application
    assert "RELEASE_PROCESS.md" in application
    assert "32634062651" in application
    assert "1f01633bd7b008dba6faec8362ddff66e0d6d009" in application
    assert "MLCPlayer_Setup_v0.39.exe" in application
    assert "57,255,931 bytes" in application
    assert "cab8c89ba614dcf3589410d345248b831439beacaecad3db6994af9a0f436066" in application
    assert "mlcplayer-unsigned-main-1f01633bd7b008dba6faec8362ddff66e0d6d009" in application
    assert "mlcplayer-unsigned-main-provenance-1f01633bd7b008dba6faec8362ddff66e0d6d009" in application
    assert "user attestation" in application
    assert "optional Internet Video add-on is outside" in application
    assert "provided privately in the submitted form" in application
    assert "[TO BE PROVIDED AT SUBMISSION]" not in application
    assert "gmail.com" not in application.lower()
    assert "Murat" not in application
    assert "Only SignPath Foundation can decide eligibility" in application_flat

    assert "signpath/" not in workflow.lower()
    assert "signpath_api_token" not in workflow.lower()
