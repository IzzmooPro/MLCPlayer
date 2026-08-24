# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The hosted CI contract stays deterministic and avoids physical tests."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DOCS_REQUIREMENTS = ROOT / "requirements-ci-docs.txt"


def workflow_text():
    assert WORKFLOW.is_file(), "GitHub Actions CI workflow is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def workflow_step(text, name):
    marker = f"      - name: {name}\n"
    start = text.index(marker)
    end = text.find("\n      - name: ", start + len(marker))
    return text[start:] if end == -1 else text[start:end]


def test_ci_runs_once_for_pull_requests_and_keeps_manual_dispatch():
    text = workflow_text()
    trigger = text[:text.index("\npermissions:")]
    assert "pull_request:" in trigger
    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert "runs-on: windows-latest" in text
    assert "timeout-minutes:" in text
    assert "contents: read" in text


def test_ci_installs_and_verifies_the_locked_environment():
    text = workflow_text()
    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in text
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in text
    assert "python-version: '3.13.15'" in text
    assert "pip install -r requirements-lock.txt" in text
    assert "verify_dependencies.py requirements-lock.txt" in text


def test_ci_runs_static_translation_and_default_pytest_gates():
    text = workflow_text()
    assert "python -m compileall -q main.py app tests packaging" in text
    assert "python packaging/extract_translations.py --check" in text
    assert "git diff --check" in text
    assert "python -m pytest -q tests" in text


def test_ci_classifies_documentation_only_changes_before_running_jobs():
    text = workflow_text()
    assert "fetch-depth: 0" in text
    assert "id: classify" in text
    assert "github.event.pull_request.base.sha" in text
    assert "github.event.before" not in text
    assert "PUSH_BASE_SHA" not in text
    assert "steps.classify.outputs.docs_only == 'true'" in text
    assert "steps.classify.outputs.docs_only != 'true'" in text


def test_documentation_only_ci_uses_the_small_deterministic_gate():
    text = workflow_text()
    assert "python -m pip install -r requirements-ci-docs.txt" in text
    for path in (
            "tests/test_continuity_regressions.py",
            "tests/test_change_workflow_regressions.py",
            "tests/test_quality_evolution_plan_regressions.py",
            "tests/test_readme_user_guidance_regressions.py",
            "tests/test_release_documentation_regressions.py",
            "tests/test_signpath_readiness_regressions.py",
            "tests/test_video_format_acceptance_plan_regressions.py"):
        assert path in text
    assert "python -m pytest -q --noconftest" in text
    assert "python -m json.tool docs/VERIFICATION_LEDGER.json" in text
    assert "git diff --check" in text
    assert "scripts/verify_ledger_append_only.py" in text


def test_documentation_ci_is_isolated_from_the_product_test_bootstrap():
    text = workflow_text()
    assert "python -m pytest -q --noconftest" in text
    assert text.count("MLC_CI: '0'") >= 2
    assert text.count("PYTHONPATH: ''") >= 2

    requirements = DOCS_REQUIREMENTS.read_text(encoding="utf-8").lower()
    for forbidden in ("python-mpv", "pyqt", "pyside", "shiboken"):
        assert forbidden not in requirements


def test_documentation_ci_requirements_are_pinned_and_match_the_full_lock():
    assert DOCS_REQUIREMENTS.is_file()
    docs = {
        line.strip().lower()
        for line in DOCS_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    locked = {
        line.strip().lower()
        for line in (ROOT / "requirements-lock.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if "==" in line
    }
    assert docs
    assert all("==" in requirement for requirement in docs)
    assert docs <= locked
    assert "pytest==9.0.3" in docs


def test_ci_does_not_opt_into_native_physical_or_release_actions():
    text = workflow_text()
    test_step = workflow_step(text, "Run CI-safe test suite")
    install_step = workflow_step(text, "Install locked dependencies")
    assert "MLC_CI: '1'" in test_step
    assert "PYTHONPATH: ${{ github.workspace }}/scripts" in test_step
    assert "MLC_CI:" not in install_step
    assert "PYTHONPATH:" not in install_step
    job_prefix = text[:text.index("    steps:")]
    assert "MLC_CI:" not in job_prefix
    assert "PYTHONPATH:" not in job_prefix
    forbidden = (
        "MLC_NATIVE_SMOKE: '1'",
        "MLC_PHYSICAL_ACCEPTANCE: '1'",
        "run_physical_acceptance.py",
        "native_feature_batch_smoke_child.py",
        "build_release.bat",
        "MLC_SIGNING_KEY",
    )
    for value in forbidden:
        assert value not in text


def test_exact_byte_licences_are_pinned_to_lf_in_every_checkout():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "LICENSE text eol=lf" in attributes.splitlines()
    assert "licenses/*.txt text eol=lf" in attributes.splitlines()


def test_hosted_ci_explicitly_excludes_the_two_native_libmpv_acceptances():
    smoke = (ROOT / "tests" / "test_smoke.py").read_text(encoding="utf-8")
    cover = (
        ROOT / "tests" / "test_cover_art_regressions.py"
    ).read_text(encoding="utf-8")
    assert "@pytest.mark.skipif(HOSTED_CI" in smoke
    assert "@pytest.mark.skipif(HOSTED_CI" in cover


def test_hosted_ci_excludes_main_entry_checks_that_require_the_runtime_dll():
    for name in (
        "test_classic_ui_removal_regressions.py",
        "test_default_cinematic_ui_regressions.py",
    ):
        source = (ROOT / "tests" / name).read_text(encoding="utf-8")
        assert "main entry acceptance requires mpv-2.dll" in source
