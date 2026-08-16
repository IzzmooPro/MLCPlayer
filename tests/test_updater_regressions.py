"""Güncelleme denetimi: güven zinciri ve kooperatif kapanış.

Bu testler AĞA ÇIKMAZ. HTTP katmanı sahte `urlopen` ile değiştirilir; asset
seçimi ve URL doğrulaması zaten saf fonksiyonlardır.
"""

import hashlib
import io
import re
from pathlib import Path

import pytest

from app import updater
from app.config import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent
TAG = "v9.9"
NAME = f"MLCPlayer_Setup_{TAG}.exe"
URL = f"https://github.com/{updater.GITHUB_REPO}/releases/download/{TAG}/{NAME}"
PAYLOAD = b"kurulum-icerigi" * 10
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def release(**overrides):
    asset = {"name": NAME, "browser_download_url": URL,
             "digest": f"sha256:{DIGEST}", "size": len(PAYLOAD)}
    asset.update(overrides.pop("asset", {}))
    data = {"tag_name": TAG, "assets": [asset]}
    data.update(overrides)
    return data


# ── Sürüm karşılaştırma ──────────────────────────────────────────────────

@pytest.mark.parametrize("latest,current,expected", [
    ("v0.2", "v0.1", True),
    ("v0.1", "v0.1", False),
    ("v0.1", "v0.2", False),
    ("v1.0", "v0.9", True),
    ("v0.10", "v0.9", True),          # sayısal karşılaştırma, metin değil
    ("", "v0.1", False),
])
def test_version_comparison(latest, current, expected):
    assert updater.is_newer_version(latest, current) is expected


# ── Asset seçimi: fail-closed ────────────────────────────────────────────

def test_valid_release_is_accepted():
    asset, reason = updater.select_update_asset(release())
    assert reason == ""
    assert asset.name == NAME and asset.sha256 == DIGEST
    assert asset.size == len(PAYLOAD)


@pytest.mark.parametrize("data,hint", [
    (release(tag_name=""), "tag_name"),
    (release(assets=[]), "beklenen asset yok"),
    (release(asset={"name": "baska.exe"}), "beklenen asset yok"),
    (release(asset={"digest": "sha1:abc"}), "digest"),
    (release(asset={"digest": None}), "digest"),
    (release(asset={"size": 0}), "size"),
    (release(asset={"size": True}), "size"),          # bool boyut sayılmaz
    (release(asset={"browser_download_url":
                    "http://github.com/x/y/releases/download/v9.9/" + NAME}),
     "URL"),
    (release(asset={"browser_download_url":
                    f"https://github.com.evil.tld/{updater.GITHUB_REPO}"
                    f"/releases/download/{TAG}/{NAME}"}), "URL"),
])
def test_broken_release_is_rejected(data, hint):
    asset, reason = updater.select_update_asset(data)
    assert asset is None
    assert hint.lower() in reason.lower(), reason


def test_two_assets_with_the_same_name_are_rejected():
    data = release()
    data["assets"] = data["assets"] * 2
    asset, reason = updater.select_update_asset(data)
    assert asset is None and "2 asset" in reason


# ── Host denetimi (redirect sonrası) ─────────────────────────────────────

@pytest.mark.parametrize("url,allowed", [
    (URL, True),
    ("https://objects.githubusercontent.com/x", True),
    ("https://release-assets.githubusercontent.com/x", True),
    ("http://github.com/x", False),                       # HTTPS zorunlu
    ("https://evil-github.com/x", False),                 # prefix hilesi
    ("https://github.com.evil.tld/x", False),             # suffix hilesi
    ("https://github.com:8443/x", False),                 # port
    (None, False),
])
def test_download_host_allowlist(url, allowed):
    assert updater.is_allowed_download_host(url) is allowed


# ── İndirme doğrulaması ──────────────────────────────────────────────────

class FakeResponse(io.BytesIO):
    def __init__(self, payload, final_url=URL, content_length=None):
        super().__init__(payload)
        self._final_url = final_url
        self.headers = {} if content_length is None else {
            "Content-Length": str(content_length)}

    def geturl(self):
        return self._final_url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def run_downloader(monkeypatch, tmp_path, response, *, sha=DIGEST,
                   size=len(PAYLOAD)):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: response)
    destination = tmp_path / "setup.exe"
    downloader = updater.UpdateDownloader(URL, str(destination), sha, size)
    results = {"ok": None, "error": None}
    downloader.download_finished.connect(
        lambda path: results.__setitem__("ok", path))
    downloader.failed.connect(lambda msg: results.__setitem__("error", msg))
    downloader.run()          # thread başlatmadan, doğrudan gövde
    return results, destination


def test_verified_download_is_accepted(monkeypatch, tmp_path):
    results, destination = run_downloader(
        monkeypatch, tmp_path,
        FakeResponse(PAYLOAD, content_length=len(PAYLOAD)))
    assert results["error"] is None
    assert results["ok"] == str(destination)
    assert destination.read_bytes() == PAYLOAD


def test_wrong_digest_deletes_the_file_and_fails(monkeypatch, tmp_path):
    results, destination = run_downloader(
        monkeypatch, tmp_path, FakeResponse(PAYLOAD), sha="0" * 64)
    assert results["ok"] is None
    assert results["error"] == updater.VERIFY_FAILED_MESSAGE
    assert not destination.exists(), "doğrulanmamış dosya silinmeli"


def test_short_download_is_rejected(monkeypatch, tmp_path):
    results, destination = run_downloader(
        monkeypatch, tmp_path, FakeResponse(PAYLOAD[:5]))
    assert results["error"] == updater.VERIFY_FAILED_MESSAGE
    assert not destination.exists()


def test_content_length_mismatch_is_rejected(monkeypatch, tmp_path):
    results, destination = run_downloader(
        monkeypatch, tmp_path, FakeResponse(PAYLOAD, content_length=7))
    assert results["error"] == updater.VERIFY_FAILED_MESSAGE
    assert not destination.exists()


def test_redirect_to_a_foreign_host_is_rejected(monkeypatch, tmp_path):
    results, destination = run_downloader(
        monkeypatch, tmp_path,
        FakeResponse(PAYLOAD, final_url="https://evil.example/setup.exe"))
    assert results["error"] == updater.VERIFY_FAILED_MESSAGE
    assert not destination.exists()


# ── Kooperatif kapanış (ürün değişmezi) ──────────────────────────────────

class FakePlayer:
    """`close()` ürünün kapanış sözleşmesini taklit eder."""

    def __init__(self, closes=True):
        self._closes = closes
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        return self._closes


def test_installer_starts_only_after_the_product_closed(tmp_path):
    started, quit_calls = [], []
    player = FakePlayer(closes=True)
    outcome, message = updater.apply_update(
        str(tmp_path / "setup.exe"), player, frozen=True,
        start_installer=started.append,
        quit_application=lambda: quit_calls.append(1))

    assert outcome == "started" and message == ""
    assert player.close_calls == 1, "ürünün kendi kapanışı çalışmalı"
    assert started, "kurulum başlatılmalı"
    assert quit_calls, "uygulama kapanmalı"


def test_busy_product_blocks_the_installer(tmp_path):
    """Altyazı Merkezi'nde iş varken kapanış ertelenir; kurulum BAŞLAMAZ."""
    started, quit_calls = [], []
    player = FakePlayer(closes=False)
    outcome, message = updater.apply_update(
        str(tmp_path / "setup.exe"), player, frozen=True,
        start_installer=started.append,
        quit_application=lambda: quit_calls.append(1))

    assert outcome == "busy"
    assert message == updater.BUSY_MESSAGE
    assert not started, "program kapanmadan kurulum başlatılmamalı"
    assert not quit_calls


def test_source_checkout_never_runs_an_installer(tmp_path):
    started = []
    player = FakePlayer(closes=True)
    outcome, _ = updater.apply_update(
        str(tmp_path / "setup.exe"), player, frozen=False,
        start_installer=started.append, quit_application=lambda: None)

    assert outcome == "source"
    assert not started
    assert player.close_calls == 0


def test_updater_never_force_terminates_a_thread():
    """Ürün değişmezi: kooperatif kapanış, `terminate()`/`os._exit` YOK.

    Ölçüm metin araması DEĞİL AST üzerindedir; modülün kendi belgelendirme
    metni bu yasakları anlattığı için düz arama yanlış alarm verirdi.
    """
    import ast
    tree = ast.parse((ROOT / "app" / "updater.py").read_text(encoding="utf-8"))

    called, used_names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
        elif isinstance(node, ast.Attribute):
            used_names.add(node.attr)
        elif isinstance(node, ast.Name):
            used_names.add(node.id)

    assert "terminate" not in called, "worker zorla sonlandırılmamalı"
    assert "_exit" not in called, "süreç zorla öldürülmemeli"
    assert "QTimer" not in used_names, "yeni timer eklenmemeli"


# ── Sürüm/asset adı bağı ─────────────────────────────────────────────────

def test_asset_name_matches_the_installer_output_name():
    """`ASSET_NAME_TEMPLATE` ile `.iss` çıktısı ayrışamaz."""
    iss = (ROOT / "packaging" / "MLCPlayer.iss").read_text(encoding="utf-8-sig")
    base = re.search(r"^OutputBaseFilename=(.+)$", iss, re.MULTILINE).group(1)
    define = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', iss).group(1)
    expected = base.strip().replace("{#MyAppVersion}", define) + ".exe"
    assert updater.expected_asset_name(define) == expected
    assert define == APP_VERSION
