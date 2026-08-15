"""OpenSubtitles REST SÖZLEŞME regresyonları — sahte transport, AĞ YOK.

Canlı harness kotayı tüketir ve internete bağımlıdır; bu yüzden sözleşmenin
asıl güvenlik kuralları burada, gerçek servise yük bindirmeden kilitlenir.

Ölçülen kurallar
----------------
- İstek yüzeyi: HTTPS endpoint, `Api-Key`/`User-Agent` başlıkları, URL
  encode, sınırlı timeout, anahtarın URL'e SIZMAMASI.
- Hata eşlemesi: 401/403, 406/429, 5xx, timeout, bağlantı, bozuk şema.
- İndirme güvenliği: yalnız HTTPS + güvenilir OpenSubtitles host; redirect
  zincirinde her hedef yeniden doğrulanır; aşırı büyük içerik reddedilir.
- Gizli veri hiçbir kullanıcı mesajına, `repr()`'a veya URL'e çıkmaz.
"""
import json
import os
import urllib.request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import opensubtitles as osub
from app import subtitle_service as service

API_KEY = "APIKEYSUPERSECRET123"
PASSWORD = "P4rolaGizli!"
TOKEN = "TOKEN-GIZLI-9999"
TRUSTED = "https://dl.opensubtitles.com/download/abc.srt"
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba\n"


class RecordingTransport:
    """İstekleri kaydeder; istenen durum/gövdeyi döndürür."""

    def __init__(self, status=200, payload=None, raw=None, error=None):
        self.status = status
        self.payload = payload
        self.raw = raw
        self.error = error
        self.calls = []

    def request(self, method, url, *, headers=None, body=None, timeout=None):
        self.calls.append({"method": method, "url": url,
                           "headers": dict(headers or {}), "body": body,
                           "timeout": timeout})
        if self.error is not None:
            raise self.error
        if self.raw is not None:
            return self.status, {}, self.raw
        payload = self.payload if self.payload is not None else {"data": []}
        return self.status, {}, json.dumps(payload).encode("utf-8")


def make_client(transport, **kwargs):
    kwargs.setdefault("api_key", API_KEY)
    return osub.OpenSubtitlesClient(transport=transport, **kwargs)


def search_payload(count=1, language="tr", file_id=7135238):
    items = []
    for index in range(count):
        items.append({
            "id": f"sub-{index}",
            "type": "subtitle",
            "attributes": {
                "language": language,
                "download_count": 100,
                "ratings": 8.5,
                "release": "The.Matrix.1999.1080p",
                "files": [{"file_id": file_id + index,
                           "file_name": "The.Matrix.1999.srt"}],
            },
        })
    return {"data": items}


# =====================================================================
# 1. İstek yüzeyi
# =====================================================================

def test_search_uses_the_official_https_endpoint():
    transport = RecordingTransport(payload=search_payload())
    make_client(transport).search(query="The Matrix", languages="tr")

    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"].startswith(
        "https://api.opensubtitles.com/api/v1/subtitles")


def test_search_sends_api_key_and_user_agent_headers():
    transport = RecordingTransport(payload=search_payload())
    make_client(transport).search(query="The Matrix", languages="tr")

    headers = transport.calls[0]["headers"]
    assert headers.get("Api-Key") == API_KEY
    agent = headers.get("User-Agent") or ""
    assert "MLC" in agent and any(ch.isdigit() for ch in agent), agent


def test_api_key_never_appears_in_the_url():
    transport = RecordingTransport(payload=search_payload())
    make_client(transport).search(query="The Matrix", languages="tr")

    assert API_KEY not in transport.calls[0]["url"]


def test_query_is_url_encoded_and_language_is_sent():
    transport = RecordingTransport(payload=search_payload())
    make_client(transport).search(query="The Matrix", languages="tr")

    url = transport.calls[0]["url"]
    assert "languages=tr" in url
    assert "The%20Matrix" in url or "The+Matrix" in url, url
    assert " " not in url


def test_request_timeout_is_bounded():
    transport = RecordingTransport(payload=search_payload())
    make_client(transport).search(query="x", languages="tr")

    timeout = transport.calls[0]["timeout"]
    assert timeout is not None and 0 < timeout <= 30


def test_no_network_call_without_an_api_key():
    transport = RecordingTransport(payload=search_payload())
    client = osub.OpenSubtitlesClient(api_key="", transport=transport)

    with pytest.raises(osub.MissingCredentialsError):
        client.search(query="x", languages="tr")

    assert transport.calls == []


# =====================================================================
# 2. Hata matrisi
# =====================================================================

@pytest.mark.parametrize("status", [401, 403])
def test_auth_statuses_map_to_auth_error(status):
    client = make_client(RecordingTransport(status=status))

    with pytest.raises(osub.AuthError):
        client.search(query="x", languages="tr")


@pytest.mark.parametrize("status", [406, 429])
def test_quota_statuses_map_to_rate_limit_error(status):
    client = make_client(RecordingTransport(status=status))

    with pytest.raises(osub.RateLimitError):
        client.search(query="x", languages="tr")


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_statuses_map_to_server_error(status):
    client = make_client(RecordingTransport(status=status))

    with pytest.raises(osub.ServerError):
        client.search(query="x", languages="tr")


def test_timeout_maps_to_network_timeout_error():
    client = make_client(RecordingTransport(error=TimeoutError("timeout")))

    with pytest.raises(osub.NetworkTimeoutError):
        client.search(query="x", languages="tr")


def test_connection_failure_maps_to_network_error():
    client = make_client(RecordingTransport(error=ConnectionError("dns")))

    with pytest.raises(osub.NetworkError):
        client.search(query="x", languages="tr")


def test_broken_json_maps_to_invalid_response_error():
    client = make_client(RecordingTransport(raw=b"<html>bozuk"))

    with pytest.raises(osub.InvalidResponseError):
        client.search(query="x", languages="tr")


def test_missing_data_key_maps_to_invalid_response_error():
    client = make_client(RecordingTransport(payload={"ok": True}))

    with pytest.raises(osub.InvalidResponseError):
        client.search(query="x", languages="tr")


def test_non_list_data_maps_to_invalid_response_error():
    client = make_client(RecordingTransport(payload={"data": {"id": 1}}))

    with pytest.raises(osub.InvalidResponseError):
        client.search(query="x", languages="tr")


def test_empty_result_list_is_not_an_error():
    client = make_client(RecordingTransport(payload={"data": []}))

    assert client.search(query="x", languages="tr") == []


# =====================================================================
# 3. İndirme bağlantısı
# =====================================================================

def test_missing_download_link_maps_to_invalid_response_error():
    client = make_client(RecordingTransport(payload={"requests": 1}))

    with pytest.raises(osub.InvalidResponseError):
        client.download_link(7135238)


def test_http_download_link_is_rejected():
    client = make_client(RecordingTransport(
        payload={"link": "http://dl.opensubtitles.com/a.srt"}))

    with pytest.raises(osub.UntrustedUrlError):
        client.download_link(7135238)


def test_foreign_https_download_link_is_rejected():
    client = make_client(RecordingTransport(
        payload={"link": "https://evil.example.com/a.srt"}))

    with pytest.raises(osub.UntrustedUrlError):
        client.download_link(7135238)


def test_lookalike_host_is_rejected():
    client = make_client(RecordingTransport(
        payload={"link": "https://opensubtitles.com.evil.net/a.srt"}))

    with pytest.raises(osub.UntrustedUrlError):
        client.download_link(7135238)


def test_trusted_download_link_is_returned():
    client = make_client(RecordingTransport(payload={"link": TRUSTED}))

    assert client.download_link(7135238) == TRUSTED


def test_download_post_is_never_retried():
    transport = RecordingTransport(status=503)
    client = make_client(transport)

    with pytest.raises(osub.ServerError):
        client.download_link(7135238)

    assert len(transport.calls) == 1


# =====================================================================
# 4. İçerik güvenliği
# =====================================================================

def test_fetch_rejects_untrusted_url():
    transport = RecordingTransport(raw=SRT)
    client = make_client(transport)

    with pytest.raises(osub.UntrustedUrlError):
        client.fetch("https://evil.example.com/a.srt")

    assert transport.calls == []


def test_oversized_response_is_rejected_safely():
    huge = b"x" * (osub.MAX_DOWNLOAD_BYTES + 1)
    client = make_client(RecordingTransport(raw=huge))

    with pytest.raises(osub.SubtitleServiceError):
        client.fetch(TRUSTED)


def test_reasonable_response_is_accepted():
    client = make_client(RecordingTransport(raw=SRT))

    assert client.fetch(TRUSTED) == SRT


def test_redirect_to_an_untrusted_host_is_rejected():
    """Redirect zincirindeki HER hedef yeniden doğrulanmalı."""
    handler = osub.TrustedRedirectHandler()

    class FakeRequest:
        full_url = TRUSTED

        def get_full_url(self):
            return self.full_url

    with pytest.raises(osub.UntrustedUrlError):
        handler.redirect_request(FakeRequest(), None, 302, "Found", {},
                                 "https://evil.example.com/a.srt")


def test_redirect_to_http_is_rejected():
    handler = osub.TrustedRedirectHandler()

    class FakeRequest:
        full_url = TRUSTED

        def get_full_url(self):
            return self.full_url

    with pytest.raises(osub.UntrustedUrlError):
        handler.redirect_request(FakeRequest(), None, 302, "Found", {},
                                 "http://dl.opensubtitles.com/a.srt")


@pytest.mark.parametrize("payload", [
    b"PK\x03\x04zip-icerigi",
    b"\x1f\x8bgzip-icerigi",
    b"<html><body>Error 404</body></html>",
    b'{"error": "not found"}',
])
def test_non_srt_content_is_never_saved_as_srt(payload, tmp_path):
    store = service.SubtitleStore()
    target = str(tmp_path / "x.srt")

    with pytest.raises(service.NotSrtError):
        store.save(target, payload)

    assert not os.path.exists(target)


# =====================================================================
# 4b. Politika hataları ISTEMCI YÜZEYİNE aynı türde ulaşmalı
# =====================================================================
#
# `TrustedRedirectHandler` güvenilmeyen yönlendirmeyi doğru reddediyordu,
# ancak `_call()`/`fetch()` içindeki geniş `except Exception` blokları bu
# GÜVENLİK hatasını sıradan bir `NetworkError`'a çeviriyordu: kullanıcı
# "ağ bağlantısı kurulamadı" görüyor, üstelik GET yolunda istek tekrar
# deneniyordu. Politika hatası ne dönüştürülmeli ne de retry edilmelidir.


class PolicyErrorTransport:
    """Transport'un kendisi politika hatası üretir (gerçek redirect gibi)."""

    def __init__(self, error=None):
        self.error = error or osub.UntrustedUrlError("redirect")
        self.calls = 0

    def request(self, method, url, *, headers=None, body=None, timeout=None):
        self.calls += 1
        raise self.error


class RedirectTransport:
    """Sunucu bizi `location`'a yönlendirir; kararı GERÇEK politika verir."""

    def __init__(self, location):
        self.location = location
        self.calls = 0

    def request(self, method, url, *, headers=None, body=None, timeout=None):
        self.calls += 1
        handler = osub.TrustedRedirectHandler()
        request = urllib.request.Request(url, method=method)
        handler.redirect_request(request, None, 302, "Found", {},
                                 self.location)
        return 200, {}, b'{"data": []}'


def test_search_preserves_untrusted_url_error():
    client = make_client(PolicyErrorTransport())

    with pytest.raises(osub.UntrustedUrlError):
        client.search(query="x", languages="tr")


def test_fetch_preserves_untrusted_url_error():
    client = make_client(PolicyErrorTransport())

    with pytest.raises(osub.UntrustedUrlError):
        client.fetch(TRUSTED)


def test_untrusted_redirect_is_never_retried_on_get():
    transport = PolicyErrorTransport()
    client = make_client(transport)

    with pytest.raises(osub.UntrustedUrlError):
        client.search(query="x", languages="tr")

    assert transport.calls == 1, (
        f"guvenlik hatasi {transport.calls} kez tekrar denendi")


def test_untrusted_redirect_is_never_retried_on_download_post():
    transport = PolicyErrorTransport()
    client = make_client(transport)

    with pytest.raises(osub.UntrustedUrlError):
        client.download_link(7135238)

    assert transport.calls == 1


@pytest.mark.parametrize("location", [
    "http://dl.opensubtitles.com/a.srt",          # HTTP'ye düşüş
    "https://evil.example.com/a.srt",             # yabancı HTTPS host
    "https://opensubtitles.com.evil.net/a.srt",   # benzer görünen host
])
def test_end_to_end_redirect_policy_reaches_the_client_surface(location):
    """Handler'ı tek başına test etmek YETMEZ: tür istemciye kadar gelmeli."""
    search_transport = RedirectTransport(location)
    fetch_transport = RedirectTransport(location)

    with pytest.raises(osub.UntrustedUrlError):
        make_client(search_transport).search(query="x", languages="tr")
    with pytest.raises(osub.UntrustedUrlError):
        make_client(fetch_transport).fetch(TRUSTED)

    assert search_transport.calls == 1
    assert fetch_transport.calls == 1


def test_untrusted_redirect_message_is_the_safe_one():
    client = make_client(PolicyErrorTransport())

    try:
        client.fetch(TRUSTED)
        raise AssertionError("beklenen hata olusmadi")
    except osub.UntrustedUrlError as error:
        message = osub.safe_message(error)

    assert message == ("Güvenilmeyen bir indirme adresi reddedildi. "
                       "İndirme yapılmadı.")


def test_untrusted_url_message_carries_no_sensitive_detail():
    detailed = osub.UntrustedUrlError(
        f"https://evil.example.com/a.srt key={API_KEY} token={TOKEN} "
        r"C:\Users\gizli\video.mkv")

    message = osub.safe_message(detailed)

    for leak in (API_KEY, TOKEN, "evil.example.com", "C:\\Users", "http"):
        assert leak not in message, leak


def test_timeout_mapping_is_not_broken_by_the_policy_fix():
    transport = PolicyErrorTransport(error=TimeoutError("timeout"))
    client = make_client(transport)

    with pytest.raises(osub.NetworkTimeoutError):
        client.search(query="x", languages="tr")
    with pytest.raises(osub.NetworkTimeoutError):
        client.fetch(TRUSTED)


@pytest.mark.parametrize("error", [
    ConnectionError("dns"),
    OSError("tls handshake"),
    ValueError("beklenmeyen"),
])
def test_ordinary_network_errors_still_map_to_network_error(error):
    client = make_client(PolicyErrorTransport(error=error))

    with pytest.raises(osub.NetworkError):
        client.search(query="x", languages="tr")


def test_ordinary_network_failures_still_use_the_get_retry_budget():
    transport = PolicyErrorTransport(error=ConnectionError("dns"))
    client = make_client(transport)

    with pytest.raises(osub.NetworkError):
        client.search(query="x", languages="tr")

    assert transport.calls == osub.MAX_RETRY + 1, (
        "siradan ag hatasinin retry butcesi bozuldu")


# =====================================================================
# 5. Login sözleşmesi
# =====================================================================

def test_login_posts_json_to_the_official_root():
    transport = RecordingTransport(payload={"token": TOKEN})
    client = make_client(transport, username="kullanici", password=PASSWORD)

    assert client.login() is True

    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.opensubtitles.com/api/v1/login"
    assert call["headers"].get("Content-Type") == "application/json"
    assert json.loads(call["body"].decode("utf-8"))["username"] == "kullanici"


def test_login_token_is_memory_only_and_not_in_repr():
    transport = RecordingTransport(payload={"token": TOKEN})
    client = make_client(transport, username="kullanici", password=PASSWORD)
    client.login()

    blob = " ".join([repr(client), str(client)])
    assert TOKEN not in blob
    assert PASSWORD not in blob
    assert API_KEY not in blob
    assert client.has_token() is True


def test_untrusted_base_url_is_ignored():
    transport = RecordingTransport(
        payload={"token": TOKEN, "base_url": "evil.example.com"})
    client = make_client(transport, username="kullanici", password=PASSWORD)
    client.login()
    transport.payload = search_payload()

    client.search(query="x", languages="tr")

    assert transport.calls[-1]["url"].startswith(
        "https://api.opensubtitles.com/api/v1/")


def test_login_is_not_retried_after_a_rejection():
    transport = RecordingTransport(status=401)
    client = make_client(transport, username="kullanici", password=PASSWORD)

    with pytest.raises(osub.AuthError):
        client.login()
    with pytest.raises(osub.AuthError):
        client.login()

    assert len(transport.calls) == 1, "bozuk credential ile tekrar denendi"


def test_missing_user_credentials_do_not_reach_the_network():
    transport = RecordingTransport(payload={"token": TOKEN})
    client = make_client(transport)

    with pytest.raises(osub.MissingCredentialsError):
        client.login()

    assert transport.calls == []


# =====================================================================
# 6. Gizli veri sızıntısı
# =====================================================================

def test_user_messages_never_contain_secrets():
    errors = [osub.AuthError(f"401 {API_KEY}"),
              osub.RateLimitError(f"429 {TOKEN}"),
              osub.ServerError(f"503 {PASSWORD}"),
              osub.InvalidResponseError(f"body {API_KEY}"),
              osub.UntrustedUrlError(f"https://evil/{TOKEN}")]

    blob = " ".join(osub.safe_message(error) for error in errors)

    for secret in (API_KEY, TOKEN, PASSWORD):
        assert secret not in blob
