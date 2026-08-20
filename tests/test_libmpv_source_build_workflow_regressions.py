# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""The manual libmpv build captures the binary's corresponding sources."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "libmpv-source-build.yml"


def workflow_text():
    assert WORKFLOW.is_file(), "manual libmpv source build workflow is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_build_is_manual_read_only_and_bounded():
    text = workflow_text()
    trigger = text.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert "pull_request:" not in trigger
    assert "contents: read" in text
    assert "timeout-minutes: 360" in text
    assert "cancel-in-progress: false" in text


def test_the_reviewed_recipe_and_container_are_immutable():
    text = workflow_text()
    assert "cd1edc11dc6887a50f705717619d879f5a93a488" in text
    assert (
        "ghcr.io/shinchiro/archlinux@sha256:"
        "9bef1a43edf26ad4048d851e8fef712285200f82ba09e9575a6862c7ff3e293a"
    ) in text
    assert 'test "$(git -C recipe rev-parse HEAD)" = "$RECIPE_COMMIT"' in text


def test_every_source_is_downloaded_without_a_fail_open_or_cache():
    text = workflow_text()
    assert "ninja -C build_x86_64 download" in text
    assert "ninja -C build_x86_64 download || true" not in text
    assert "ninja -C build_x86_64 update" in text
    assert "actions/cache" not in text
    assert "ENABLE_CCACHE=OFF" in text


def test_the_exact_sources_and_build_recipe_are_recorded():
    text = workflow_text()
    assert "SOURCE_LOCK.tsv" in text
    assert "SOURCE_FILES.sha256" in text
    assert "git archive HEAD" in text
    assert "recipe/src_packages" in text
    assert "registry/src" in text
    assert "git/checkouts" in text
    assert "libmpv-corresponding-source.tar.zst" in text
    assert "SHA256SUMS" in text


def test_the_windows_libmpv_archive_is_required_and_validated():
    text = workflow_text()
    build_step = text.split(
        "- name: Build the Clang toolchain and package Windows libmpv", 1
    )[1].split("- name: Validate and collect Windows archives", 1)[0]
    targets = (
        "ninja -C build_x86_64 llvm",
        "ninja -C build_x86_64 rustup",
        "ninja -C build_x86_64 llvm-clang",
        "ninja -C build_x86_64 mpv",
        "ninja -C build_x86_64 mpv-packaging",
    )
    positions = [build_step.index(target) for target in targets]
    assert positions == sorted(positions)
    assert "ninja -C build_x86_64 mpv" in text
    assert "ninja -C build_x86_64 mpv-packaging" in text
    assert "mpv-dev-x86_64*.7z" in text
    assert "libmpv-2.dll" in text
    assert "libmpv-windows-x86_64" in text


def test_artifacts_are_uploaded_by_immutable_action_without_a_release():
    text = workflow_text()
    upload = (
        "actions/upload-artifact@"
        "ea165f8d65b6e75b540449e92b4886f43607fa02"
    )
    assert text.count(upload) == 3
    assert "compression-level: 0" in text
    forbidden = (
        "actions/cache",
        "gh release",
        "create release",
        "git tag",
        "softprops/action-gh-release",
        "pacman ",
        "apt-get ",
    )
    for value in forbidden:
        assert value not in text
