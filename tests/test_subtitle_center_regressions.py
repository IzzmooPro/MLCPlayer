# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Merkezi — ürün kodundan ÖNCE yazılan başarısız regresyonlar.

18 kabul maddesinin tamamı burada ölçülür. Hiçbir test gerçek internete
çıkmaz; ağ katmanı enjekte edilebilir sahte transport ile sürülür.

Gerçek OpenSubtitles koşumu ayrı ve opt-in'dir
(`tests/opensubtitles_live_child.py`, `MLC_OPENSUBTITLES_LIVE_TEST=1`).
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import opensubtitles as osub
from app import subtitle_service as service


# --- 1. Video yolundan birebir .srt hedefi ---

@pytest.mark.parametrize("video, expected", (
    ("Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv",
     "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.srt"),
    ("Supergirl (2026) 2160p 4K HDR10.mkv", "Supergirl (2026) 2160p 4K HDR10.srt"),
    ("film.with.many.dots.v2.mp4", "film.with.many.dots.v2.srt"),
    ("BOSLUKLU AD.avi", "BOSLUKLU AD.srt"),
))
def test_target_path_is_video_stem_plus_srt(tmp_path, video, expected):
    video_path = tmp_path / video
    video_path.write_bytes(b"x")

    target = service.subtitle_target_path(str(video_path))

    assert os.path.dirname(target) == str(tmp_path), "hedef video klasoru olmali"
    assert os.path.basename(target) == expected


def test_target_path_ignores_the_opensubtitles_file_name(tmp_path):
    video_path = tmp_path / "Resident.Alien.S01E01.1080p-NTb.mkv"
    video_path.write_bytes(b"x")

    target = service.subtitle_target_path(
        str(video_path), remote_name="bambaska.turkish.HI.srt")

    assert os.path.basename(target) == "Resident.Alien.S01E01.1080p-NTb.srt"


@pytest.mark.parametrize("forbidden", (".tr.srt", ".1.srt", ".2.srt", "(1).srt"))
def test_target_path_never_contains_language_or_counter_suffix(tmp_path, forbidden):
    video_path = tmp_path / "Film.2024.1080p.mkv"
    video_path.write_bytes(b"x")

    target = service.subtitle_target_path(str(video_path))

    assert not target.endswith(forbidden)
    assert target.endswith("Film.2024.1080p.srt")


def test_no_language_suffix_option_exists():
    """Dosya adina dil kodu ekleme secenegi BULUNMAMALI."""
    import inspect

    signature = inspect.signature(service.subtitle_target_path)
    for name in signature.parameters:
        assert "lang" not in name.lower(), f"dil kodu parametresi var: {name}"


# --- 2/3. Release adinin korunmasi ve ikinci indirmede sayac olusmamasi ---

def test_second_download_reuses_the_same_target(tmp_path):
    video_path = tmp_path / "Resident.Alien.S01E01.Pilot.1080p-NTb.mkv"
    video_path.write_bytes(b"x")
    store = service.SubtitleStore()

    first = service.subtitle_target_path(str(video_path))
    store.save(first, b"1\n00:00:01,000 --> 00:00:02,000\nbir\n")
    second = service.subtitle_target_path(str(video_path))
    store.save(second, b"1\n00:00:01,000 --> 00:00:02,000\niki\n")

    assert first == second
    srt_files = sorted(p.name for p in tmp_path.glob("*.srt"))
    assert srt_files == ["Resident.Alien.S01E01.Pilot.1080p-NTb.srt"]


# --- 4. Basarili tekrar indirmede icerik degisir ---

def test_successful_redownload_replaces_content(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()
    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nESKI\n")

    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nYENI\n")

    assert "YENI" in target.read_text(encoding="utf-8")
    assert "ESKI" not in target.read_text(encoding="utf-8")


def test_file_is_written_as_utf8(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()

    store.save(str(target), "1\n00:00:01,000 --> 00:00:02,000\nşğüöçİ\n".encode("utf-8"))

    assert target.read_text(encoding="utf-8").strip().endswith("şğüöçİ")


# --- 5/7. Hata halinde eski dosya korunur, yarim dosya kalmaz ---

def test_failed_write_keeps_the_previous_file(tmp_path, monkeypatch):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()
    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nCALISAN\n")

    def boom(*args, **kwargs):
        raise OSError("disk dolu")

    monkeypatch.setattr(service.os, "replace", boom)
    with pytest.raises(service.SubtitleWriteError):
        store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nYENI\n")

    assert "CALISAN" in target.read_text(encoding="utf-8")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "Film.srt"]
    assert leftovers == [], f"yarim/gecici dosya kaldi: {leftovers}"


def test_write_uses_temporary_file_then_atomic_replace(tmp_path, monkeypatch):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()
    calls = {"replace": 0, "target_seen": None}
    original = service.os.replace

    def spy(src, dst):
        calls["replace"] += 1
        calls["target_seen"] = dst
        assert src != dst, "atomic replace gecici dosyadan yapilmali"
        return original(src, dst)

    monkeypatch.setattr(service.os, "replace", spy)
    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nX\n")

    assert calls["replace"] == 1
    assert calls["target_seen"] == str(target)


# --- 6. Kullanici reddederse uzerine yazilmaz ---

def test_existing_foreign_srt_requires_confirmation(tmp_path):
    target = tmp_path / "Film.srt"
    target.write_text("BASKA UYGULAMANIN DOSYASI", encoding="utf-8")
    store = service.SubtitleStore()
    asked = {"n": 0}

    def deny(path):
        asked["n"] += 1
        return False

    written = store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nY\n",
                         confirm=deny)

    assert written is False
    assert asked["n"] == 1
    assert target.read_text(encoding="utf-8") == "BASKA UYGULAMANIN DOSYASI"


def test_confirmation_is_asked_only_once_per_session(tmp_path):
    target = tmp_path / "Film.srt"
    target.write_text("YABANCI", encoding="utf-8")
    store = service.SubtitleStore()
    asked = {"n": 0}

    def allow(path):
        asked["n"] += 1
        return True

    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nA\n", confirm=allow)
    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nB\n", confirm=allow)

    assert asked["n"] == 1, "ayni oturumda tekrar onay istendi"
    assert "B" in target.read_text(encoding="utf-8")


def test_mlc_created_file_never_asks_for_confirmation(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()
    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nA\n")

    def fail(path):
        raise AssertionError("MLC'nin kendi dosyasi icin onay istenmemeli")

    store.save(str(target), b"1\n00:00:01,000 --> 00:00:02,000\nB\n", confirm=fail)

    assert "B" in target.read_text(encoding="utf-8")


# --- 12 (kismi). Yalnizca gercek SRT kabul edilir ---

@pytest.mark.parametrize("payload", (
    b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nmerhaba\n",
    b"[Script Info]\nScriptType: v4.00+\n[Events]\nDialogue: 0,...",
    b"\x00\x01binary",
))
def test_non_srt_payload_is_rejected(tmp_path, payload):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()

    with pytest.raises(service.NotSrtError):
        store.save(str(target), payload)

    assert not target.exists()


def test_real_srt_payload_is_accepted(tmp_path):
    target = tmp_path / "Film.srt"
    store = service.SubtitleStore()

    assert store.save(
        str(target), b"1\n00:00:01,000 --> 00:00:02,000\nmerhaba\n") is True


# --- 14. S01E01 ayristirma ---

def test_series_season_and_episode_are_parsed():
    info = service.parse_release(
        "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv")

    assert info["is_series"] is True
    assert info["season"] == 1
    assert info["episode"] == 1
    assert info["title"] == "Resident Alien"


@pytest.mark.parametrize("name, season, episode", (
    ("Show.Name.S02E10.720p.mkv", 2, 10),
    ("Show Name 3x07 HDTV.mkv", 3, 7),
    ("Show.Name.S12E24.mkv", 12, 24),
))
def test_more_series_patterns(name, season, episode):
    info = service.parse_release(name)
    assert (info["season"], info["episode"]) == (season, episode)


def test_movie_is_not_detected_as_series():
    info = service.parse_release("Supergirl.2026.2160p.WEB-DL.H265.mkv")

    assert info["is_series"] is False
    assert info["season"] is None and info["episode"] is None
    assert info["title"] == "Supergirl"
    assert info["year"] == 2026


# --- 8/9. MPV track yasam dongusu ---

class FakeMpv:
    def __init__(self):
        self.sub_files = []
        self.removed = []
        self.sid = "no"
        self.sub_visibility = False
        self.track_list = []
        self._next_id = 1

    def sub_add(self, path, *args):
        self.sub_files.append(path)
        self.track_list.append({"type": "sub", "id": self._next_id,
                                "external-filename": path, "selected": False})
        self._next_id += 1

    def sub_remove(self, sid):
        self.removed.append(sid)
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


def test_apply_removes_previous_mlc_track_and_selects_new(tmp_path):
    target = str(tmp_path / "Film.srt")
    mpv = FakeMpv()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    session = service.SubtitleSession()

    session.apply(player, target)
    first_sid = mpv.sid
    session.apply(player, target)

    assert mpv.removed == [first_sid], (
        f"onceki MLC track kaldirilmadi: removed={mpv.removed}")
    assert mpv.sub_visibility is True
    assert len([t for t in mpv.track_list if t["type"] == "sub"]) == 1, (
        "yinelenen subtitle track olustu")
    assert mpv.sid == mpv.track_list[0]["id"]


def test_apply_does_not_duplicate_tracks_across_many_downloads(tmp_path):
    target = str(tmp_path / "Film.srt")
    mpv = FakeMpv()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    session = service.SubtitleSession()

    for _ in range(5):
        session.apply(player, target)

    assert len([t for t in mpv.track_list if t["type"] == "sub"]) == 1


def test_download_only_does_not_touch_the_active_track(tmp_path):
    target = str(tmp_path / "Film.srt")
    mpv = FakeMpv()
    mpv.sid, mpv.sub_visibility = 7, True
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    session = service.SubtitleSession()

    session.download_only(player, target,
                          b"1\n00:00:01,000 --> 00:00:02,000\nX\n")

    assert mpv.sid == 7 and mpv.sub_visibility is True
    assert mpv.sub_files == [] and mpv.removed == []
    assert os.path.exists(target)


# --- 10/11/16. Kimlik bilgisi ve guvenli hatalar ---

class FakeTransport:
    """Enjekte edilen sahte ag katmani. Gercek internete cikilmaz."""

    def __init__(self, responses=None, error=None):
        self.responses = responses or {}
        self.error = error
        self.calls = []

    def request(self, method, url, *, headers=None, body=None, timeout=None):
        self.calls.append({"method": method, "url": url,
                           "headers": headers or {}, "body": body})
        if self.error:
            raise self.error
        return self.responses.get(url, (200, {}, b"{}"))


def test_no_network_call_without_api_key():
    transport = FakeTransport()
    client = osub.OpenSubtitlesClient(api_key="", transport=transport)

    with pytest.raises(osub.MissingCredentialsError):
        client.search(query="film")

    assert transport.calls == [], "API anahtari yokken ag istegi gonderildi"


def test_missing_key_message_tells_the_user_to_configure():
    message = osub.safe_message(osub.MissingCredentialsError())
    assert "ayar" in message.lower() or "anahtar" in message.lower()


@pytest.mark.parametrize("status, expected_type", (
    (401, osub.AuthError),
    (403, osub.AuthError),
    (429, osub.RateLimitError),
    (500, osub.ServerError),
    (503, osub.ServerError),
))
def test_http_errors_map_to_safe_turkish_errors(status, expected_type):
    transport = FakeTransport()
    transport.responses = {}
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)
    transport.request = lambda *a, **k: (status, {}, b'{"message":"x"}')

    with pytest.raises(expected_type) as info:
        client.search(query="film")

    message = osub.safe_message(info.value)
    assert message and message == message.strip()
    assert "Traceback" not in message


def test_timeout_is_reported_safely():
    transport = FakeTransport(error=TimeoutError("timed out"))
    client = osub.OpenSubtitlesClient(api_key="k" * 20, transport=transport)

    with pytest.raises(osub.NetworkTimeoutError) as info:
        client.search(query="film")

    assert "zaman" in osub.safe_message(info.value).lower()


def test_secrets_never_appear_in_messages_or_repr():
    secret_key = "SUPERSECRETAPIKEY12345"
    secret_password = "P4rolaGizli!"
    client = osub.OpenSubtitlesClient(
        api_key=secret_key, transport=FakeTransport(),
        username="kullanici", password=secret_password)

    blob = " ".join([repr(client), str(client),
                     osub.safe_message(osub.AuthError("401")),
                     osub.safe_message(osub.RateLimitError("429"))])

    assert secret_key not in blob
    assert secret_password not in blob


def test_password_is_not_persisted_in_settings(tmp_path):
    # NOT: Bu test kullanicinin GERCEK Credential Manager'ini kirletmemeli;
    # yalnizca "parola ayar dosyasina yazilmaz" kurali olculur.
    store = osub.CredentialStore(namespace="MLCPlayerTest",
                                 settings_dir=str(tmp_path),
                                 use_credential_manager=False)
    store.set_password("kullanici", "P4rolaGizli!")

    written = ""
    for path in tmp_path.rglob("*"):
        if path.is_file():
            written += path.read_text(encoding="utf-8", errors="ignore")

    assert "P4rolaGizli!" not in written, "parola duz ayar dosyasina yazildi"


# --- 12/13. Filtreleme ve siralama ---

def make_result(**kwargs):
    base = {"file_id": 1, "name": "Release", "language": "tr", "format": "srt",
            "moviehash_match": False, "downloads": 10, "ratings": 5.0,
            "fps": 23.976, "hearing_impaired": False}
    base.update(kwargs)
    return base


def test_only_selected_language_and_real_srt_are_listed():
    raw = [
        make_result(file_id=1, language="tr", format="srt"),
        make_result(file_id=2, language="en", format="srt"),
        make_result(file_id=3, language="tr", format="ass"),
        make_result(file_id=4, language="tr", format="vtt"),
    ]

    listed = osub.filter_results(raw, language="tr")

    assert [item["file_id"] for item in listed] == [1]


def test_hash_matches_are_ranked_first():
    raw = [
        make_result(file_id=1, moviehash_match=False, downloads=9999),
        make_result(file_id=2, moviehash_match=True, downloads=5),
        make_result(file_id=3, moviehash_match=True, downloads=50),
    ]

    ranked = osub.rank_results(osub.filter_results(raw, language="tr"))

    assert [item["file_id"] for item in ranked[:2]] == [3, 2]
    assert ranked[0].get("best_match") is True


def test_search_order_prefers_hash_then_name():
    calls = []

    class RecordingClient:
        def search(self, **kwargs):
            calls.append(kwargs)
            if "moviehash" in kwargs and not getattr(self, "hash_hit", False):
                return []
            return [make_result()]

    plan = osub.build_search_plan(
        video_path="X.mkv", movie_hash="abc", file_size=123,
        parsed={"title": "X", "is_series": False, "season": None,
                "episode": None, "year": None}, language="tr")

    assert plan[0]["moviehash"] == "abc"
    assert "query" in plan[1]
    assert calls == []


# --- 15. Worker/dialog guvenli kapanis sozlesmesi ---

def test_worker_supports_cancel_and_never_uses_terminate():
    import inspect

    source = inspect.getsource(osub)
    assert "terminate()" not in source, "QThread.terminate() kullanilamaz"
    assert hasattr(osub.SubtitleSearchWorker, "cancel")


def test_worker_marks_itself_cancelled_before_finishing():
    worker = osub.SubtitleSearchWorker(client=None, plan=[])
    worker.cancel()
    assert worker.is_cancelled() is True
