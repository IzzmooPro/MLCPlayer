# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The hosted CI contract stays deterministic and avoids physical tests."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def workflow_text():
    assert WORKFLOW.is_file(), "GitHub Actions CI workflow is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_runs_for_pushes_and_pull_requests_on_windows():
    text = workflow_text()
    assert "push:" in text
    assert "pull_request:" in text
    assert "runs-on: windows-latest" in text
    assert "timeout-minutes:" in text
    assert "contents: read" in text


def test_ci_installs_and_verifies_the_locked_environment():
    text = workflow_text()
    assert "actions/checkout@v6" in text
    assert "actions/setup-python@v6" in text
    assert "python-version: '3.13.15'" in text
    assert "pip install -r requirements-lock.txt" in text
    assert "verify_dependencies.py requirements-lock.txt" in text


def test_ci_runs_static_translation_and_default_pytest_gates():
    text = workflow_text()
    assert "python -m compileall -q main.py app tests packaging" in text
    assert "python packaging/extract_translations.py --check" in text
    assert "git diff --check" in text
    assert "python -m pytest -q tests" in text


def test_ci_does_not_opt_into_native_physical_or_release_actions():
    text = workflow_text()
    assert "MLC_CI: '1'" in text
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
