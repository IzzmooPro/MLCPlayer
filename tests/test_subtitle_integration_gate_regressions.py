"""Altyazı çekirdeği — entegrasyon kapısı regresyonları.

Denetimde bulunan beş açık:

1. `normalize_results()` var ama GERÇEK worker zincirinde kullanılmıyor.
2. `fetch()` 404/410 gibi >=400 cevapların gövdesini SRT veriymiş gibi
   döndürüyor.
3. Native smoke kullanıcının gerçek videosunun yanındaki `.srt` dosyasına
   yazıyor/yedekliyor.
4. Smoke `terminate()` çağırıyor, `closeEvent` de çağırıyor -> çift terminate.
5. `apply()` bekleme döngüsü ileride Qt ana thread'ini bloklayabilir.
"""
import inspect
import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import opensubtitles as osub
from app import subtitle_service as service

SMOKE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "subtitle_track_lifecycle_smoke_child.py")

# Resmî /subtitles yanıtı: file_id NESTED attributes.files[] içinde.
OFFICIAL_PAYLOAD = [
    {
        "id": "7061050",
        "type": "subtitle",
        "attributes": {
            "language": "tr", "download_count": 4321, "format": "srt",
            "fps": 23.976, "ratings": 9.1, "moviehash_match": True,
            "hearing_impaired": False,
            "release": "Resident.Alien.S01E01.1080p.AMZN.WEB-DL-NTb",
            "files": [{"file_id": 7135238,
                       "file_name": "Resident.Alien.S01E01.turkish.srt"}],
        },
    },
    {
        "id": "7061051",
        "type": "subtitle",
        "attributes": {
            "language": "tr", "download_count": 12, "format": "srt",
            "moviehash_match": False,
            "files": [{"file_id": 999, "file_name": "digeri.srt"}],
        },
    },
    {   # files BOŞ -> güvenli biçimde düşmeli
        "attributes": {"language": "tr", "format": "srt", "files": []},
    },
    {   # files EKSİK -> düşmeli
        "attributes": {"language": "tr", "format": "srt"},
    },
    {   # files HATALI tip -> düşmeli
        "attributes": {"language": "tr", "format": "srt", "files": ["bozuk"]},
    },
]


class RecordingClient:
    """Gerçek istemci sözleşmesini taklit eder; ağa çıkmaz."""

    def __init__(self, payload):
        self.payload = payload
        self.searches = []
        self.download_calls = []

    def search(self, **params):
        self.searches.append(params)
        return self.payload

    def download_link(self, file_id):
        self.download_calls.append(file_id)
        return "https://dl.opensubtitles.com/download/x.srt"


# --- 1. Worker zinciri normalize_results kullanmali ---

def test_worker_results_carry_flat_file_id_from_nested_files():
    client = RecordingClient(OFFICIAL_PAYLOAD)
    worker = osub.SubtitleSearchWorker(client=client, plan=[{"query": "x"}])

    results = worker.run(language="tr")

    assert results, "worker resmi cevaptan sonuc uretemedi"
    assert results[0]["file_id"] == 7135238, (
        f"duzlestirilmis file_id yok: {results[0]}")
    assert results[0]["best_match"] is True


def test_worker_result_file_id_reaches_download_link():
    client = RecordingClient(OFFICIAL_PAYLOAD)
    worker = osub.SubtitleSearchWorker(client=client, plan=[{"query": "x"}])

    results = worker.run(language="tr")
    chosen = results[0]
    client.download_link(chosen["file_id"])

    assert client.download_calls == [7135238], (
        f"secilen sonucun file_id'si download_link'e ulasmadi: "
        f"{client.download_calls}")


def test_worker_drops_entries_without_usable_files():
    client = RecordingClient(OFFICIAL_PAYLOAD)
    worker = osub.SubtitleSearchWorker(client=client, plan=[{"query": "x"}])

    results = worker.run(language="tr")

    assert [item["file_id"] for item in results] == [7135238, 999]


def test_worker_chain_calls_normalize_before_filter():
    source = inspect.getsource(osub.SubtitleSearchWorker.run)
    assert "normalize_results" in source, (
        "worker gercek akisinda normalize_results kullanmiyor")


def test_flat_fake_results_still_work():
    """Mevcut sade sahte sema ile calisan testler bozulmamali."""
    flat = [{"file_id": 5, "language": "tr", "format": "srt",
             "moviehash_match": True, "downloads": 3, "ratings": 1.0}]
    client = RecordingClient(flat)
    worker = osub.SubtitleSearchWorker(client=client, plan=[{"query": "x"}])

    results = worker.run(language="tr")

    assert [item["file_id"] for item in results] == [5]


# --- 2. HTTP hata matrisi ---

class FakeTransport:
    def __init__(self, status=200, body=b"{}"):
        self.status = status
        self.body = body
        self.calls = []

    def request(self, method, url, *, headers=None, body=None, timeout=None):
        self.calls.append({"method": method, "url": url,
                           "headers": dict(headers or {}), "body": body})
        return self.status, {}, self.body


SRT_LOOKING_ERROR_BODY = (b"1\n00:00:01,000 --> 00:00:02,000\n"
                          b"Not Found\n")


@pytest.mark.parametrize("status", (400, 404, 410, 418, 451))
def test_fetch_rejects_every_client_error_status(status):
    transport = FakeTransport(status=status, body=SRT_LOOKING_ERROR_BODY)
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.SubtitleServiceError) as info:
        client.fetch("https://dl.opensubtitles.com/download/a.srt")

    message = osub.safe_message(info.value)
    assert message and "Traceback" not in message


@pytest.mark.parametrize("status", (404, 410))
def test_fetch_never_returns_error_body_as_subtitle(status):
    transport = FakeTransport(status=status, body=SRT_LOOKING_ERROR_BODY)
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.SubtitleServiceError):
        data = client.fetch("https://dl.opensubtitles.com/download/a.srt")
        assert data != SRT_LOOKING_ERROR_BODY, (
            "hata gövdesi altyazı verisi gibi dondu")


def test_fetch_returns_body_only_on_success():
    payload = b"1\n00:00:01,000 --> 00:00:02,000\ngercek\n"
    transport = FakeTransport(status=200, body=payload)
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    assert client.fetch(
        "https://dl.opensubtitles.com/download/a.srt") == payload


def test_fetch_error_does_not_leak_server_body_or_secrets():
    transport = FakeTransport(status=404, body=b"secret-server-detail")
    client = osub.OpenSubtitlesClient(
        api_key="APIKEYSECRET", transport=transport,
        username="kullanici", password="PAROLA!")

    try:
        client.fetch("https://dl.opensubtitles.com/download/a.srt")
    except osub.SubtitleServiceError as error:
        blob = " ".join([str(error), repr(error), osub.safe_message(error)])
        assert "secret-server-detail" not in blob
        assert "APIKEYSECRET" not in blob
        assert "PAROLA!" not in blob


@pytest.mark.parametrize("status", (400, 404, 410))
def test_download_link_client_errors_are_not_retried(status):
    transport = FakeTransport(status=status)
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.SubtitleServiceError):
        client.download_link(1)

    assert len([c for c in transport.calls if c["method"] == "POST"]) == 1


# --- 3. Native smoke kullanici dosyasina dokunmamali ---

def _smoke_calls():
    """Smoke'un GERCEK cagri adlari (yorum/docstring haric, AST uzerinden)."""
    import ast

    tree = ast.parse(open(SMOKE, encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_smoke_never_uses_the_product_target_path():
    assert "subtitle_target_path" not in _smoke_calls(), (
        "native smoke urun hedef adini cagiriyor -> kullanici .srt'sine yazar")


def test_smoke_does_not_backup_or_restore_user_files():
    calls = _smoke_calls()
    for forbidden in ("copy2", "copyfile", "move"):
        assert forbidden not in calls, (
            f"smoke kullanici dosyasini kopyaliyor/tasiyor: {forbidden}")
    # Silme yalnizca kendi gecici calisma dizininde olabilir.
    assert "remove" not in calls, "smoke dosya siliyor"


def test_smoke_creates_its_subtitle_under_temp():
    assert "mkdtemp" in _smoke_calls(), "smoke benzersiz gecici dizin acmiyor"


def test_smoke_writes_only_inside_its_workspace():
    """Kaydetme cagrisinin hedefi calisma dizini degiskeni olmali."""
    import ast

    tree = ast.parse(open(SMOKE, encoding="utf-8").read())
    save_targets = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "save" and node.args):
            first = node.args[0]
            save_targets.append(
                first.id if isinstance(first, ast.Name) else type(first).__name__)
    assert save_targets, "smoke hic altyazi kaydetmiyor"
    assert all(name == "temp_srt" for name in save_targets), (
        f"kaydetme hedefi calisma dizini disinda: {save_targets}")


# --- 4. Tek sahipli teardown ---

def test_smoke_does_not_call_terminate_itself():
    assert "terminate" not in _smoke_calls(), (
        "smoke terminate() cagiriyor; closeEvent zaten cagiriyor -> "
        "cift terminate riski")


def test_smoke_uses_the_canonical_shutdown_owner():
    assert "shutdown_player" in _smoke_calls(), (
        "smoke kanonik kapanis sahibini kullanmiyor")


class CountingMpv:
    def __init__(self):
        self.terminate_calls = 0
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1

    def terminate(self):
        self.terminate_calls += 1


def test_shutdown_helper_terminates_at_most_once():
    mpv = CountingMpv()
    closed = {"n": 0}

    def close():
        closed["n"] += 1
        mpv.terminate()  # urun closeEvent'inin yaptigi is

    player = SimpleNamespace(mpv_player=mpv, close=close)

    service.shutdown_player(player)
    service.shutdown_player(player)

    assert mpv.terminate_calls <= 1, (
        f"terminate {mpv.terminate_calls} kez cagrildi")
    assert mpv.stop_calls >= 1


# --- 5. UI thread hazirligi ---

def test_track_wait_budget_is_declared_and_bounded():
    assert hasattr(service, "TRACK_WAIT_ATTEMPTS")
    assert hasattr(service, "TRACK_WAIT_INTERVAL_S")
    budget = service.TRACK_WAIT_ATTEMPTS * service.TRACK_WAIT_INTERVAL_S
    assert budget <= 0.4, f"varsayilan bloklama butcesi {budget}s"


def test_apply_never_sleeps_when_a_wait_callback_is_given(monkeypatch):
    calls = {"sleep": 0}
    monkeypatch.setattr(service.time, "sleep",
                        lambda *_: calls.__setitem__("sleep", calls["sleep"] + 1))

    class NeverAdds:
        track_list = []
        sid = "no"
        sub_visibility = False

        def sub_add(self, path, *args):
            pass

    player = SimpleNamespace(mpv_player=NeverAdds(), video_frame=None)
    ticks = {"n": 0}

    service.SubtitleSession().apply(
        player, "x.srt", wait=lambda: ticks.__setitem__("n", ticks["n"] + 1))

    assert calls["sleep"] == 0, "wait verildiginde time.sleep kullanilmamali"
    assert ticks["n"] > 0, "verilen wait geri cagrisi kullanilmadi"


def test_apply_supports_non_blocking_probe():
    """UI thread'inde tek tur deneme yapilabilmeli (hic beklemeden)."""
    class NeverAdds:
        track_list = []
        sid = "no"
        sub_visibility = False

        def sub_add(self, path, *args):
            pass

    player = SimpleNamespace(mpv_player=NeverAdds(), video_frame=None)

    import time as clock
    started = clock.perf_counter()
    result = service.SubtitleSession().apply(player, "x.srt", attempts=1,
                                             wait=None)
    elapsed = clock.perf_counter() - started

    assert result is False
    assert elapsed < 0.1, f"tek turluk deneme {elapsed:.3f}s blokladi"
