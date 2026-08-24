# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Public READMEs must describe the product users actually install.

These checks deliberately target user-visible contracts rather than exact
paragraph formatting.  The English and Turkish documents must not drift on
the separate Internet Video package, update verification, source runtimes,
playlist window model, or data retained during uninstall.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EN = (ROOT / "README.md").read_text(encoding="utf-8")
TR = (ROOT / "README.tr.md").read_text(encoding="utf-8")


def test_both_readmes_explain_the_two_installer_contract():
    for text in (EN, TR):
        assert "MLCPlayer_Setup_v*.exe" in text
        assert "MLCPlayer_InternetVideo_v*.exe" in text
        assert text.index("MLCPlayer_Setup_v*.exe") < text.index(
            "MLCPlayer_InternetVideo_v*.exe")
        assert ".sig" in text

    assert "install the main player first" in EN.lower()
    assert "internet video" in EN.lower()
    assert "built-in updater updates only the main player" in EN.lower()
    assert "Önce ana oynatıcıyı" in TR
    assert "İnternet Videosu" in TR
    assert "Yerleşik güncelleyici yalnız ana oynatıcıyı günceller" in TR


def test_both_readmes_describe_all_update_verification_gates():
    for text in (EN, TR):
        lowered = text.lower()
        assert "sha-256" in lowered
        assert "ed25519" in lowered
        assert "smartscreen" in lowered

    assert "published size" in EN.lower()
    assert "yayımlanan boyut" in TR.lower()


def test_source_runtime_requirements_distinguish_local_and_internet_media():
    for text in (EN, TR):
        assert "mpv-2.dll" in text
        assert "yt-dlp.exe" in text
        assert "deno.exe" in text
        assert "Start.bat" in text

    assert "local media" in EN.lower()
    assert "internet video" in EN.lower()
    assert "yerel medya" in TR.lower()
    assert "İnternet videosu" in TR


def test_playlist_description_matches_the_owned_adjacent_window_model():
    assert "owned window beside the main window" in EN.lower()
    assert "does not overlap the video" in EN.lower()
    assert "docked inside the main window" not in EN.lower()
    assert "playlist stays embedded in the main window" not in EN.lower()

    assert "ana pencerenin yanında" in TR.lower()
    assert "bağımsız pencere" in TR.lower()
    assert "videoyla kesişmez" in TR.lower()
    assert "ana pencereye gömülü" not in TR.lower()


def test_both_readmes_have_a_user_quick_start_and_data_retention_note():
    assert "## Quick start" in EN
    assert "## Hızlı başlangıç" in TR

    assert "keyboard shortcuts" in EN.lower()
    assert "klavye kısayolları" in TR.lower()
    assert "log management" in EN.lower()
    assert "günlük yönetimi" in TR.lower()

    assert "keeps your settings and logs" in EN.lower()
    assert "ayarlarınızı ve günlüklerinizi korur" in TR.lower()
    assert "%APPDATA%\\MLCPlayer\\logs" in EN
    assert "%APPDATA%\\MLCPlayer\\logs" in TR


def test_ready_installer_requirements_name_windows_x64_and_admin_rights():
    assert "Windows 10 or 11" in EN
    assert "64-bit" in EN
    assert "administrator" in EN.lower()

    assert "Windows 10 veya 11" in TR
    assert "64-bit" in TR
    assert "yönetici" in TR.lower()
