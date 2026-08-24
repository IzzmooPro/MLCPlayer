# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Manual workflows fail closed unless dispatched for an approved master SHA."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CHANGE_WORKFLOW = ROOT / "docs" / "CHANGE_WORKFLOW.md"
RELEASE_PROCESS = ROOT / "docs" / "RELEASE_PROCESS.md"
MANUAL = (
    "ci.yml",
    "build-unsigned-main.yml",
    "libmpv-source-build.yml",
    "mirror-libmpv-buildenv.yml",
    "publish-libmpv-runtime.yml",
)


@pytest.mark.parametrize("name", MANUAL)
def test_manual_workflow_requires_exact_master_sha(name):
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    assert "expected_sha:" in text
    assert "required: true" in text
    assert "refs/heads/master" in text
    assert "github.sha" in text
    assert "inputs.expected_sha" in text
    assert "Verify exact master dispatch" in text
    steps = text.split("    steps:", 1)[1]
    assert steps.lstrip().startswith("- name: Verify exact master dispatch")


def test_exact_dispatch_contract_is_documented_at_both_decision_points():
    for path in (CHANGE_WORKFLOW, RELEASE_PROCESS):
        text = path.read_text(encoding="utf-8")
        assert "expected_sha" in text
        assert "refs/heads/master" in text
        assert "github.sha" in text
        assert "fail-closed" in text
