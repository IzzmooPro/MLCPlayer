"""Altyazı çekirdeği — denetimde bulunan açıkların regresyonları.

Mevcut testlerin YAKALAMADIĞI 12 davranış burada ölçülür. Hiçbir test gerçek
internete çıkmaz. Windows Credential Manager roundtrip'i opt-in'dir.
"""
import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import opensubtitles as osub
from app import subtitle_service as service

SRT_ASCII = b"1\n00:00:01,000 --> 00:00:02,000\nmerhaba\n"
TURKISH = "1\n00:00:01,000 --> 00:00:02,000\nÇöğüşİı ağır şölen\n"


# --- 1. confirm=None iken yabancı dosya ASLA ezilmemeli (fail-closed) ---

def test_foreign_target_is_never_overwritten_without_confirm(tmp_path):
    target = tmp_path / "Film.srt"
    target.write_text("YABANCI ICERIK", encoding="utf-8")
    store = service.SubtitleStore()

    with pytest.raises(service.ConfirmationRequiredError):
        store.save(str(target), SRT_ASCII)

    assert target.read_text(encoding="utf-8") == "YABANCI ICERIK"


def test_foreign_target_untouched_when_confirm_callback_missing(tmp_path):
    """confirm verilmediginde sessizce ezme yerine acik hata beklenir."""
    target = tmp_path / "Film.srt"
    target.write_bytes("ESKI".encode("utf-8"))
    store = service.SubtitleStore()

    with pytest.raises(service.ConfirmationRequiredError):
        store.save(str(target), SRT_ASCII, confirm=None)

    assert target.read_bytes() == "ESKI".encode("utf-8")
    assert [p.name for p in tmp_path.iterdir()] == ["Film.srt"]


# --- 2. Kodlama normalizasyonu: hedef daima gercek UTF-8 ---

def test_cp1254_input_is_stored_as_real_utf8(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()

    store.save(str(target), TURKISH.encode("cp1254"))

    raw = target.read_bytes()
    assert raw.decode("utf-8") == TURKISH, "hedef gercek UTF-8 degil"
    assert "Çöğüşİı" in raw.decode("utf-8")


def test_utf8_bom_is_normalized_away(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()

    store.save(str(target), b"\xef\xbb\xbf" + TURKISH.encode("utf-8"))

    raw = target.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM temizlenmedi"
    assert raw.decode("utf-8") == TURKISH


def test_utf8_input_round_trips_unchanged(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()

    store.save(str(target), TURKISH.encode("utf-8"))

    assert target.read_bytes().decode("utf-8") == TURKISH


def test_undecodable_payload_is_rejected(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()
    # Gecerli SRT iskeleti + hicbir kodlamada cozulemeyen bayt dizisi
    payload = b"1\n00:00:01,000 --> 00:00:02,000\n\xff\xfe\x00\x00\xd8\x00\n"

    with pytest.raises((service.NotSrtError, service.SubtitleEncodingError)):
        store.save(str(target), payload)

    assert not target.exists()


# --- 3/5. Track kaldirma track_list uzerinden, bellege guvenmeden ---

class FakeMpv:
    def __init__(self, delay=0):
        self.track_list = []
        self.removed = []
        self.sid = "no"
        self.sub_visibility = False
        self._next = 1
        self._delay = delay
        self._pending = []

    def sub_add(self, path, *args):
        entry = {"type": "sub", "id": self._next,
                 "external-filename": path, "selected": False}
        self._next += 1
        if self._delay > 0:
            self._pending.append((self._delay, entry))
        else:
            self.track_list.append(entry)

    def sub_remove(self, sid):
        self.removed.append(sid)
        self.track_list = [t for t in self.track_list if t.get("id") != sid]

    def tick(self):
        """track_list gecikmesini simule eder."""
        still = []
        for countdown, entry in self._pending:
            if countdown <= 1:
                self.track_list.append(entry)
            else:
                still.append((countdown - 1, entry))
        self._pending = still


def make_player(mpv):
    return SimpleNamespace(mpv_player=mpv, video_frame=None)


def test_new_session_removes_previous_track_found_in_track_list(tmp_path):
    target = str(tmp_path / "Film.srt")
    mpv = FakeMpv()
    player = make_player(mpv)

    service.SubtitleSession().apply(player, target)
    first_id = mpv.sid
    # Yeni oturum: bellekte self._sid YOK, track_list'ten bulunmali.
    service.SubtitleSession().apply(player, target)

    assert first_id in mpv.removed, (
        f"onceki MLC track track_list uzerinden kaldirilmadi: {mpv.removed}")
    external = [t for t in mpv.track_list if t.get("external-filename")]
    assert len(external) == 1


def test_five_separate_sessions_leave_one_external_track(tmp_path):
    target = str(tmp_path / "Film.srt")
    mpv = FakeMpv()
    player = make_player(mpv)

    for _ in range(5):
        service.SubtitleSession().apply(player, target)

    external = [t for t in mpv.track_list if t.get("external-filename")]
    assert len(external) == 1, f"yinelenen track: {mpv.track_list}"


# --- 4. Gecikmeli track_list: yanlis track secilmemeli ---

def test_delayed_track_list_does_not_select_the_wrong_track(tmp_path):
    target = str(tmp_path / "Film.srt")
    mpv = FakeMpv(delay=3)
    # Dahili (gomulu) altyazi zaten var; yanlislikla bu secilmemeli.
    mpv.track_list.append({"type": "sub", "id": 99, "selected": False})
    player = make_player(mpv)

    service.SubtitleSession().apply(player, target, wait=mpv.tick)

    assert mpv.sid != 99, "gecikme sirasinda mevcut dahili track secildi"
    chosen = [t for t in mpv.track_list if t.get("id") == mpv.sid]
    assert chosen and chosen[0].get("external-filename") == target


def test_track_never_selected_without_verified_id(tmp_path):
    """track_list hic guncellenmezse rastgele son track secilmemeli."""
    target = str(tmp_path / "Film.srt")
    mpv = FakeMpv(delay=99)
    mpv.track_list.append({"type": "sub", "id": 42, "selected": False})
    player = make_player(mpv)

    service.SubtitleSession().apply(player, target, wait=lambda: None)

    assert mpv.sid != 42, "dogrulanmamis track secildi"


# --- 6. Credential Manager: typed struct, sabit ofset yok ---

def test_credential_store_uses_typed_structure_not_fixed_offsets():
    import inspect

    source = inspect.getsource(osub)
    assert "pointer.value + 24" not in source
    assert "pointer.value + 32" not in source
    assert "CREDENTIALW" in source or "CREDENTIAL" in source


@pytest.mark.skipif(os.environ.get("MLC_CREDENTIAL_ROUNDTRIP") != "1",
                    reason="opt-in: MLC_CREDENTIAL_ROUNDTRIP=1")
def test_windows_credential_roundtrip():
    import uuid

    namespace = f"MLCPlayerTest/{uuid.uuid4().hex}"
    store = osub.CredentialStore(namespace=namespace)
    user, secret = "test-user", "P4rola-Ğüş!"
    try:
        assert store.set_password(user, secret) == "credential_manager"
        assert store.get_password(user) == secret
        assert store.delete_password(user) is True
        assert store.get_password(user) is None
    finally:
        try:
            store.delete_password(user)
        except Exception:
            pass


# --- 7. Login gercekten uygulanmali ---

class FakeTransport:
    def __init__(self):
        self.calls = []
        self.handler = None

    def request(self, method, url, *, headers=None, body=None, timeout=None):
        self.calls.append({"method": method, "url": url,
                           "headers": dict(headers or {}), "body": body})
        if self.handler:
            return self.handler(method, url, headers, body)
        return 200, {}, b"{}"


def test_login_posts_and_keeps_token_in_memory_only(tmp_path):
    transport = FakeTransport()

    def handler(method, url, headers, body):
        if url.endswith("/login"):
            return 200, {}, json.dumps(
                {"token": "TKN123", "base_url": "vip-api.opensubtitles.com"}
            ).encode()
        return 200, {}, b'{"data": []}'

    transport.handler = handler
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport,
                                      username="user", password="pass")

    client.login()

    login_calls = [c for c in transport.calls if c["url"].endswith("/login")]
    assert login_calls and login_calls[0]["method"] == "POST"
    assert client.has_token() is True
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "TKN123" not in path.read_text(encoding="utf-8", errors="ignore")


def test_login_base_url_is_validated_and_used():
    transport = FakeTransport()

    def handler(method, url, headers, body):
        if url.endswith("/login"):
            return 200, {}, json.dumps(
                {"token": "T", "base_url": "vip-api.opensubtitles.com"}).encode()
        return 200, {}, b'{"data": []}'

    transport.handler = handler
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport,
                                      username="u", password="p")
    client.login()
    client.search(query="film")

    search_calls = [c for c in transport.calls if "/subtitles" in c["url"]]
    assert search_calls
    assert search_calls[-1]["url"].startswith("https://vip-api.opensubtitles.com")


def test_untrusted_base_url_from_login_is_rejected():
    transport = FakeTransport()

    def handler(method, url, headers, body):
        # NOT: arama yanıtı GERÇEK şemayı taşımalı; login gövdesini her
        # isteğe döndürmek artık (haklı olarak) şema ihlali sayılıyor.
        if url.endswith("/login"):
            return 200, {}, json.dumps(
                {"token": "T", "base_url": "evil.example.com"}).encode()
        return 200, {}, b'{"data": []}'

    transport.handler = handler
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport,
                                      username="u", password="p")

    client.login()
    client.search(query="film")

    search_calls = [c for c in transport.calls if "/subtitles" in c["url"]]
    assert search_calls
    assert "evil.example.com" not in search_calls[-1]["url"]


def test_login_401_is_not_retried():
    transport = FakeTransport()
    transport.handler = lambda *a: (401, {}, b'{"message":"bad"}')
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport,
                                      username="u", password="p")

    with pytest.raises(osub.AuthError):
        client.login()
    with pytest.raises(osub.AuthError):
        client.login()

    login_calls = [c for c in transport.calls if c["url"].endswith("/login")]
    assert len(login_calls) == 1, (
        f"401 sonrasi tekrar giris denendi: {len(login_calls)}")


def test_credentials_never_leak_through_login_errors():
    transport = FakeTransport()
    transport.handler = lambda *a: (401, {}, b'{"message":"bad"}')
    client = osub.OpenSubtitlesClient(api_key="APIKEYSECRET", transport=transport,
                                      username="kullanici", password="PAROLA!")

    try:
        client.login()
    except osub.AuthError as error:
        blob = " ".join([str(error), repr(error), osub.safe_message(error),
                         repr(client)])
        assert "PAROLA!" not in blob and "APIKEYSECRET" not in blob


# --- 8. Kota tuketen POST tekrar gonderilmemeli ---

def test_download_post_is_not_retried_on_timeout():
    transport = FakeTransport()

    def handler(method, url, headers, body):
        raise TimeoutError("timeout")

    transport.handler = handler
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.NetworkTimeoutError):
        client.download_link(123)

    posts = [c for c in transport.calls if c["method"] == "POST"]
    assert len(posts) == 1, f"kota tuketen POST tekrarlandi: {len(posts)}"


def test_download_post_is_not_retried_on_server_error():
    transport = FakeTransport()
    transport.handler = lambda *a: (503, {}, b"{}")
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.ServerError):
        client.download_link(123)

    posts = [c for c in transport.calls if c["method"] == "POST"]
    assert len(posts) == 1


def test_search_get_may_retry_on_server_error():
    transport = FakeTransport()
    state = {"n": 0}

    def handler(method, url, headers, body):
        state["n"] += 1
        if state["n"] == 1:
            return 500, {}, b"{}"
        return 200, {}, b'{"data": []}'

    transport.handler = handler
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    client.search(query="film")

    assert state["n"] >= 2, "GET arama icin sinirli retry beklenir"


# --- 9. Indirme baglantisi yalniz HTTPS + guvenilir alan adi ---

@pytest.mark.parametrize("url, trusted", (
    ("https://dl.opensubtitles.com/download/abc.srt", True),
    ("https://api.opensubtitles.com/x.srt", True),
    ("https://vip-dl.opensubtitles.com/a.srt", True),
    ("http://dl.opensubtitles.com/download/abc.srt", False),
    ("https://evil.example.com/a.srt", False),
    ("https://opensubtitles.com.evil.net/a.srt", False),
    ("ftp://dl.opensubtitles.com/a.srt", False),
))
def test_download_url_trust_rules(url, trusted):
    assert osub.is_trusted_download_url(url) is trusted


def test_fetch_refuses_untrusted_url():
    transport = FakeTransport()
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.UntrustedUrlError):
        client.fetch("https://evil.example.com/a.srt")

    assert transport.calls == [], "guvenilmeyen adrese istek gonderildi"


# --- 10. Gecersiz JSON bos sonuc gibi gosterilmemeli ---

def test_invalid_json_raises_safe_error():
    transport = FakeTransport()
    transport.handler = lambda *a: (200, {}, b"<html>not json</html>")
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.InvalidResponseError):
        client.search(query="film")

    assert "geçersiz" in osub.safe_message(osub.InvalidResponseError()).lower()


# --- 11. Resmi cevap bicimi (nested files) ---

OFFICIAL_RESPONSE = {
    "total_pages": 1,
    "data": [
        {
            "id": "7061050",
            "type": "subtitle",
            "attributes": {
                "subtitle_id": "7061050",
                "language": "tr",
                "download_count": 1234,
                "hearing_impaired": False,
                "fps": 23.976,
                "ratings": 8.5,
                "moviehash_match": True,
                "format": "srt",
                "release": "Resident.Alien.S01E01.1080p.AMZN.WEB-DL-NTb",
                "files": [
                    {"file_id": 7135238,
                     "file_name": "Resident.Alien.S01E01.turkish.srt"}
                ],
            },
        },
        {
            "id": "7061051",
            "type": "subtitle",
            "attributes": {
                "language": "en", "download_count": 99, "format": "srt",
                "moviehash_match": False,
                "files": [{"file_id": 1, "file_name": "eng.srt"}],
            },
        },
    ],
}


def test_official_response_file_id_is_extracted_from_nested_files():
    normalized = osub.normalize_results(OFFICIAL_RESPONSE["data"])

    turkish = [item for item in normalized if item["language"] == "tr"]
    assert len(turkish) == 1
    assert turkish[0]["file_id"] == 7135238, "nested files icinden file_id alinmadi"
    assert turkish[0]["file_name"] == "Resident.Alien.S01E01.turkish.srt"
    assert turkish[0]["downloads"] == 1234
    assert turkish[0]["fps"] == 23.976
    assert turkish[0]["moviehash_match"] is True


def test_official_response_filters_and_ranks():
    normalized = osub.normalize_results(OFFICIAL_RESPONSE["data"])
    ranked = osub.rank_results(osub.filter_results(normalized, language="tr"))

    assert [item["file_id"] for item in ranked] == [7135238]
    assert ranked[0]["best_match"] is True


def test_entry_without_files_is_dropped():
    normalized = osub.normalize_results(
        [{"attributes": {"language": "tr", "format": "srt", "files": []}}])
    assert normalized == []


# --- 12. Anahtarsiz sifir ag cagrisi korunur ---

def test_no_network_without_api_key_for_every_entry_point():
    transport = FakeTransport()
    client = osub.OpenSubtitlesClient(api_key="", transport=transport)

    for call in (lambda: client.search(query="x"),
                 lambda: client.download_link(1),
                 lambda: client.login(),
                 lambda: client.fetch(
                     "https://dl.opensubtitles.com/download/a.srt")):
        with pytest.raises(osub.MissingCredentialsError):
            call()

    assert transport.calls == []
