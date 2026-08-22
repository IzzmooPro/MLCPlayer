# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The protected-master PR contract remains explicit and evidence-safe."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "docs" / "CHANGE_WORKFLOW.md"


def workflow_text():
    assert WORKFLOW.is_file(), "change workflow document is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def test_change_workflow_has_an_explicit_live_activation_gate():
    text = workflow_text()
    normalized = " ".join(text.split())
    assert "pull request gerektiriyor" in text
    assert "GitHub Actions uygulamasından gelen tam **`test`**" in text
    assert "docs/CONTINUITY.md" in text
    assert "canlı GitHub ayarı çelişirse değişiklik yapılmaz" in normalized


def test_change_workflow_preserves_commit_evidence():
    text = workflow_text()
    assert "`codex/<kısa-konu>`" in text
    assert "**Merge commit** kullan" in text
    assert "squash/rebase kullanma" in text
    assert "fast-forward" in text


def test_change_workflow_keeps_failure_and_approval_boundaries():
    text = workflow_text()
    assert "otomatik tekrar yok" in text
    assert "koruma bypass edilmez" in text
    for action in (
        "commit",
        "görev dalı push'u",
        "PR oluşturma",
        "PR birleştirme",
        "tag",
        "release",
    ):
        assert action in text


def test_change_workflow_defines_the_planned_solo_maintainer_gate():
    text = workflow_text()
    assert "approving reviews `0`" in text
    assert "required check: **`test`**, kaynak GitHub Actions" in text
    assert "branch must be up to date before merging" in text
    assert "bypass actor yok" in text


def test_agent_entrypoint_links_to_the_change_workflow():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/CHANGE_WORKFLOW.md" in agents
    assert "PR oluşturma, PR birleştirme" in agents
    assert "Force-push ve GitHub protection bypass yapılmaz" in agents


def test_release_process_uses_the_pr_merge_commit_as_build_identity():
    release = (ROOT / "docs" / "RELEASE_PROCESS.md").read_text(
        encoding="utf-8")
    assert "docs/CHANGE_WORKFLOW.md" in release
    assert "**merge commit**" in release
    assert "git rev-parse origin/master" in release
    assert "master'a ikinci kez push yapılmaz" in release


def test_public_readmes_link_to_the_change_workflow():
    for name in ("README.md", "README.tr.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "docs/CHANGE_WORKFLOW.md" in text
