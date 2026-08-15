"""Kapanış GÜVENLİĞİ regresyonları: zaman aşımı ve hata kolları.

Bu tur yalnızca kapanış/zaman aşımı disiplinidir. Görsel tasarım, arama ve
indirme davranışı DEĞİŞMEZ.

Kesin kural
-----------
`player.close()` YALNIZCA `coordinator.is_fully_drained()` gerçekten True
olduğunda sürdürülebilir. Zaman aşımı "zorla güvenli oldu" anlamına GELMEZ:
çalışan QThread varken ne player ne coordinator yok edilir ve `terminate()`
asla çağrılmaz.
"""
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QSettings, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import subtitle_service as service
from app.subtitle_center_composition import SubtitleCenterCoordinator
from app.subtitle_settings import SubtitleSettingsStore

SERIES = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.mkv"
RESULT = {"file_id": 7135238, "name": "Uzak.Ad", "language": "tr",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}
API_KEY = "APIKEY"


class SlowClient:
    def __init__(self, gate):
        self.release = gate.release
        self.entered = gate.entered

    def search(self, **kwargs):
        self.entered.set()
        self.release.wait(30)
        return [RESULT]

    def download_link(self, file_id):
        return "https://dl.opensubtitles.com/download/a.srt"

    def fetch(self, url):
        return b"1\n00:00:01,000 --> 00:00:04,000\nx\n"


class FakeCredentialStore:
    def __init__(self):
        self.secrets = {"api": API_KEY}

    def set_api_key(self, value):
        self.secrets["api"] = value
        return "credential_manager"

    def get_api_key(self):
        return self.secrets.get("api")

    def delete_api_key(self):
        self.secrets.pop("api", None)
        return True

    def set_password(self, username, value):
        self.secrets["pw"] = value
        return "credential_manager"

    def get_password(self, username):
        return self.secrets.get("pw")

    def delete_password(self, username):
        self.secrets.pop("pw", None)
        return True


class StubVideoFrame:
    def __init__(self):
        self.osd_messages = []

    def show_osd(self, text, duration=1200):
        self.osd_messages.append(text)

    def _update_overlay_subtitle_state(self):
        pass


class StubPlayer(QMainWindow):
    def __init__(self, current_file=""):
        super().__init__()
        self.current_file = current_file
        self.video_frame = StubVideoFrame()
        self.mpv_player = SimpleNamespace(
            track_list=[], sid="no", sub_visibility=False,
            sub_add=lambda p, *a: None, sub_remove=lambda s: None)


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory():
        path = tmp_path / SERIES
        path.write_bytes(b"\0" * (140 * 1024))
        player = StubPlayer(str(path))
        gate = SimpleNamespace(release=threading.Event(),
                               entered=threading.Event())
        store = SubtitleSettingsStore(
            settings=QSettings(str(tmp_path / "settings.ini"),
                               QSettings.Format.IniFormat),
            credentials=FakeCredentialStore())
        coordinator = SubtitleCenterCoordinator(
            player, client_factory=lambda **kwargs: SlowClient(gate),
            settings_store=store)
        player._subtitle_center = coordinator
        created.append((player, coordinator, gate))
        return SimpleNamespace(app=app, player=player, gate=gate,
                               coordinator=coordinator, tmp=tmp_path)

    yield factory

    for player, coordinator, gate in created:
        gate.release.set()
        coordinator.shutdown(wait_ms=8000)
        try:
            player.close()
            player.deleteLater()
        except RuntimeError:
            pass
    app.processEvents()


def pump(app, milliseconds):
    end = time.time() + milliseconds / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.005)


def pump_until(app, predicate, timeout_ms=15000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


def start_running_search(env):
    env.coordinator.open()
    env.coordinator.dialog.search_button.click()
    assert env.gate.entered.wait(8), "arama worker'i baslamadi"


# =====================================================================
# 1. `shutdown()` bitmemiş işi UNUTMAZ
# =====================================================================

def test_shutdown_reports_failure_when_work_outlives_the_budget(bench):
    env = bench()
    start_running_search(env)

    finished = env.coordinator.shutdown(wait_ms=200)

    assert finished is False, "bitmeyen is 'tamamlandi' diye raporlandi"


def test_unfinished_controller_stays_owned_after_a_failed_shutdown(bench):
    env = bench()
    start_running_search(env)

    env.coordinator.shutdown(wait_ms=200)

    assert env.coordinator.draining_count() == 1, (
        "calisan controller sahiplik listesinden silindi")
    assert env.coordinator.is_idle() is False
    assert env.coordinator.is_fully_drained() is False


def test_failed_shutdown_prunes_only_after_the_worker_finishes(bench):
    env = bench()
    start_running_search(env)
    env.coordinator.shutdown(wait_ms=200)

    env.gate.release.set()

    assert pump_until(env.app, lambda: env.coordinator.is_idle(), 12000)
    assert env.coordinator.draining_count() == 0


def test_second_shutdown_is_idempotent_and_safe(bench):
    env = bench()
    start_running_search(env)

    first = env.coordinator.shutdown(wait_ms=200)
    second = env.coordinator.shutdown(wait_ms=200)

    assert first is False and second is False
    assert env.coordinator.draining_count() == 1

    env.gate.release.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle(), 12000)
    assert env.coordinator.shutdown(wait_ms=1000) is True


def test_unfinished_hash_job_is_not_dropped(bench, monkeypatch):
    gate = threading.Event()
    started = threading.Event()

    def slow_hash(path):
        started.set()
        gate.wait(30)
        return "HASH"

    monkeypatch.setattr(service, "opensubtitles_hash", slow_hash)
    env = bench()
    env.coordinator.open()
    assert started.wait(8), "hash worker'i baslamadi"

    finished = env.coordinator.shutdown(wait_ms=200)

    assert finished is False
    assert env.coordinator.is_idle() is False, (
        "calisan hash isi sahiplik disinda birakildi")

    gate.set()
    assert pump_until(env.app, lambda: env.coordinator.is_idle(), 12000)


# =====================================================================
# 2. Zaman aşımı KAPANIŞ İZNİ DEĞİLDİR
# =====================================================================

def test_timeout_does_not_invoke_the_close_callback(bench):
    env = bench()
    start_running_search(env)
    calls = {"n": 0}

    ready = env.coordinator.begin_close(
        lambda: calls.__setitem__("n", calls["n"] + 1), timeout_ms=150)
    assert ready is False
    pump(env.app, 800)  # deadline COKTAN doldu

    assert calls["n"] == 0, "zaman asiminda kapanis zorlandi"
    # NOT: dialog hâlâ AÇIK olduğu için controller "aktif" slotta durur;
    # ölçülmesi gereken şey işin hâlâ SAHİPLENİLDİĞİDİR.
    assert env.coordinator.is_fully_drained() is False
    assert env.coordinator.is_idle() is False, "calisan is takipten cikti"


def test_callback_runs_exactly_once_after_the_worker_finishes(bench):
    env = bench()
    start_running_search(env)
    calls = {"n": 0}
    env.coordinator.begin_close(
        lambda: calls.__setitem__("n", calls["n"] + 1), timeout_ms=150)
    pump(env.app, 500)

    env.gate.release.set()
    assert pump_until(env.app, lambda: calls["n"] == 1, 12000)
    pump(env.app, 400)

    assert calls["n"] == 1, f"callback {calls['n']} kez calisti"
    assert env.coordinator.is_fully_drained() is True


def test_second_close_request_does_not_double_the_callback(bench):
    env = bench()
    start_running_search(env)
    calls = {"n": 0}

    def callback():
        calls["n"] += 1

    env.coordinator.begin_close(callback, timeout_ms=150)
    pump(env.app, 400)
    env.coordinator.begin_close(callback, timeout_ms=150)  # kullanici tekrar

    env.gate.release.set()
    assert pump_until(env.app, lambda: calls["n"] >= 1, 12000)
    pump(env.app, 400)

    assert calls["n"] == 1


def test_ui_stays_responsive_after_the_close_deadline(bench):
    env = bench()
    start_running_search(env)
    ticks = {"n": 0}
    timer = QTimer()
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    timer.start()
    try:
        env.coordinator.begin_close(lambda: None, timeout_ms=150)
        pump(env.app, 700)
    finally:
        timer.stop()

    assert ticks["n"] > 3, f"deadline sonrasi UI dondu (tick={ticks['n']})"


def test_timeout_shows_a_safe_notice_only_once(bench):
    env = bench()
    start_running_search(env)

    env.coordinator.begin_close(lambda: None, timeout_ms=150)
    pump(env.app, 900)

    messages = env.player.video_frame.osd_messages
    assert len(messages) <= 1, f"uyari tekrarlandi: {messages}"
    for message in messages:
        assert str(env.tmp) not in message
        assert "Traceback" not in message
        assert API_KEY not in message


def test_no_forced_thread_termination_anywhere():
    import inspect

    from app import subtitle_center_composition as composition

    source = inspect.getsource(composition)
    assert ".terminate()" not in source


# =====================================================================
# 3. `closeEvent` FAIL-CLOSED olmalı
# =====================================================================

class FakeEvent:
    def __init__(self):
        self.accepted = 0
        self.ignored = 0

    def accept(self):
        self.accepted += 1

    def ignore(self):
        self.ignored += 1


class TrackingTimer:
    def __init__(self):
        self.stops = 0

    def stop(self):
        self.stops += 1


def make_close_self(drained):
    """`MPVPlayer.closeEvent` için minimum sahte `self`."""
    mpv = SimpleNamespace(terminate_calls=0)

    def terminate():
        mpv.terminate_calls += 1

    mpv.terminate = terminate
    coordinator = SimpleNamespace(is_fully_drained=lambda: drained)
    return SimpleNamespace(
        _subtitle_center=coordinator, mpv_player=mpv,
        timer=TrackingTimer(), settings=None,
        video_frame=SimpleNamespace(is_video_fullscreen=False))


def test_close_event_is_fail_closed_when_the_helper_raises(monkeypatch):
    from app import player as player_module

    def boom(player, timeout_ms=None):
        raise RuntimeError("beklenmeyen hata")

    monkeypatch.setattr(player_module, "close_subtitle_center_before_exit",
                        boom)
    fake = make_close_self(drained=False)
    event = FakeEvent()

    player_module.MPVPlayer.closeEvent(fake, event)

    assert event.ignored == 1, "hata halinde pencere kapandi (fail-open)"
    assert event.accepted == 0
    assert fake.mpv_player.terminate_calls == 0, "MPV terminate edildi"
    assert fake.timer.stops == 0, "kapanis temizligi baslatildi"


def test_close_event_recovers_once_the_work_is_done(monkeypatch):
    """Sonsuz kapanamama olmamalı: iş bittiğinde kapanış sürdürülebilir."""
    from app import player as player_module

    def boom(player, timeout_ms=None):
        raise RuntimeError("beklenmeyen hata")

    monkeypatch.setattr(player_module, "close_subtitle_center_before_exit",
                        boom)
    fake = make_close_self(drained=True)
    mpv = fake.mpv_player  # closeEvent referansı bırakır; önceden tutulur
    event = FakeEvent()

    player_module.MPVPlayer.closeEvent(fake, event)

    assert event.ignored == 0
    assert event.accepted == 1
    assert mpv.terminate_calls == 1
    assert fake.mpv_player is None


def test_close_event_error_is_not_leaked_to_the_user(monkeypatch, capsys):
    from app import player as player_module

    def boom(player, timeout_ms=None):
        raise RuntimeError("C:/gizli/yol ve APIKEY")

    monkeypatch.setattr(player_module, "close_subtitle_center_before_exit",
                        boom)
    fake = make_close_self(drained=False)

    player_module.MPVPlayer.closeEvent(fake, FakeEvent())

    printed = capsys.readouterr().out
    assert "APIKEY" not in printed
    assert "C:/gizli/yol" not in printed
    assert "Traceback" not in printed


# =====================================================================
# 4. `service.shutdown_player()` ertelenmiş kapanışa uyumlu
# =====================================================================

class DeferringPlayer:
    """`close()` iş bitene kadar kapanmayı ERTELER (ürün davranışı)."""

    def __init__(self):
        self.visible = True
        self.close_calls = 0
        self.stop_calls = 0
        self.terminate_calls = 0
        self.busy = True
        self.mpv_player = SimpleNamespace(stop=self._stop,
                                          terminate=self._terminate)

    def _stop(self):
        self.stop_calls += 1

    def _terminate(self):
        self.terminate_calls += 1

    def isVisible(self):
        return self.visible

    def close(self):
        self.close_calls += 1
        if self.busy:
            return  # ERTELENDI: pencere acik kalir
        if self.mpv_player is not None:
            self.mpv_player.terminate()
            self.mpv_player = None
        self.visible = False


def test_shutdown_player_does_not_claim_success_while_deferred():
    player = DeferringPlayer()

    result = service.shutdown_player(player)

    assert result is False, "ertelenen kapanis 'tamamlandi' sayildi"
    assert player.visible is True
    assert player.mpv_player is not None, "MPV referansi erken birakildi"
    assert player.terminate_calls == 0


def test_shutdown_player_completes_after_the_work_finishes():
    player = DeferringPlayer()
    service.shutdown_player(player)

    player.busy = False
    result = service.shutdown_player(player)

    assert result is True
    assert player.visible is False
    assert player.mpv_player is None
    assert player.terminate_calls == 1, (
        f"terminate {player.terminate_calls} kez")
    assert player.stop_calls == 1, f"stop {player.stop_calls} kez"


def test_shutdown_player_stays_idempotent_when_deferred():
    player = DeferringPlayer()

    for _ in range(3):
        assert service.shutdown_player(player) is False

    assert player.stop_calls == 1, f"stop {player.stop_calls} kez cagrildi"
    assert player.terminate_calls == 0


def test_shutdown_player_fast_path_is_preserved():
    """İş yokken davranış AYNI kalmalı."""
    player = DeferringPlayer()
    player.busy = False

    first = service.shutdown_player(player)
    second = service.shutdown_player(player)

    assert first is True
    assert second is False, "ikinci cagri tekrar is yapti"
    assert player.terminate_calls == 1
    assert player.stop_calls == 1
