# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Merkezi — QThread arama entegrasyonu regresyonları.

Bu tur GERÇEK AĞA ÇIKMAZ: bütün davranış enjekte edilen sahte client ile
doğrulanır. İndirme, dosya yazma, MPV ve menü entegrasyonu YOKTUR.
"""
import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import opensubtitles as osub
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_search_controller import (
    LANGUAGE_CODES, SubtitleSearchController)

SERIES = {
    "file_name": "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv",
    "title": "Resident Alien", "season": 1, "episode": 1, "is_series": True,
    "target_name": "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.srt",
    "movie_hash": "abc123def456", "file_size": 987654321,
}
MOVIE = {
    "file_name": "Supergirl.2026.2160p.WEB-DL.H265.mkv",
    "title": "Supergirl", "season": None, "episode": None, "is_series": False,
    "target_name": "Supergirl.2026.2160p.WEB-DL.H265.srt",
    "movie_hash": "", "file_size": 0,
}

OFFICIAL = [{
    "id": "7061050",
    "attributes": {
        "language": "tr", "download_count": 4321, "format": "srt",
        "fps": 23.976, "ratings": 9.1, "moviehash_match": True,
        "hearing_impaired": False,
        "release": "Resident.Alien.S01E01.1080p.AMZN.WEB-DL-NTb",
        "files": [{"file_id": 7135238, "file_name": "tr.srt"}],
    },
}]
SECOND = [{
    "attributes": {
        "language": "tr", "download_count": 7, "format": "srt",
        "moviehash_match": False,
        "files": [{"file_id": 555, "file_name": "ikinci.srt"}],
    },
}]


class FakeClient:
    """Enjekte edilen sahte istemci; GERÇEK AĞA ÇIKMAZ."""

    def __init__(self, responses=None, error=None, delay=0.0):
        self.responses = responses if responses is not None else [OFFICIAL]
        self.error = error
        self.delay = delay
        self.calls = []
        self.threads = []
        self.downloads = []

    def search(self, **params):
        self.calls.append(dict(params))
        self.threads.append(threading.get_ident())
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]

    def download_link(self, file_id):
        self.downloads.append(file_id)
        return "https://dl.opensubtitles.com/download/x.srt"


@pytest.fixture
def bench():
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(media=None, client=None, **kwargs):
        window = QMainWindow()
        window.show()
        dialog = SubtitleCenterDialog(window, media=media or SERIES)
        dialog.show()
        controller = SubtitleSearchController(
            dialog, client=client or FakeClient(), **kwargs)
        app.processEvents()
        created.append((window, dialog, controller))
        return app, dialog, controller

    yield factory

    for window, dialog, controller in created:
        controller.shutdown(wait_ms=4000)
        # Test dialogu bilerek yok etmis olabilir; teardown buna dayanikli.
        for widget in (dialog, window):
            try:
                widget.close()
            except RuntimeError:
                pass
    app.processEvents()


def pump_until(app, predicate, timeout_ms=6000):
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


# --- 1/2. Thread ayrımı ---

def test_search_runs_off_the_main_thread(bench):
    client = FakeClient(delay=0.15)
    app, dialog, controller = bench(client=client)
    main_thread = threading.get_ident()

    controller.start_search()
    assert pump_until(app, lambda: controller.is_idle())

    assert client.threads, "arama hic calismadi"
    assert all(ident != main_thread for ident in client.threads), (
        "arama ANA Qt thread'inde calisti")


def test_main_event_loop_keeps_running_during_search(bench):
    client = FakeClient(delay=0.3)
    app, dialog, controller = bench(client=client)
    ticks = {"n": 0}
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    timer.start()
    try:
        controller.start_search()
        pump_until(app, lambda: controller.is_idle())
    finally:
        timer.stop()

    assert ticks["n"] > 3, f"arama sirasinda UI dondu (tick={ticks['n']})"


# --- 3/4. Plan sırası ---

def test_hash_hit_skips_the_name_search(bench):
    client = FakeClient(responses=[OFFICIAL])
    app, dialog, controller = bench(client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert len(client.calls) == 1, f"ad aramasi da yapildi: {client.calls}"
    assert client.calls[0].get("moviehash") == "abc123def456"


def test_empty_hash_result_falls_back_to_name_search(bench):
    client = FakeClient(responses=[[], OFFICIAL])
    app, dialog, controller = bench(client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert len(client.calls) == 2
    assert "moviehash" in client.calls[0]
    assert client.calls[1].get("query") == "Resident Alien"


# --- 5/6/7/8. Parametre aktarımı ---

def test_nested_file_id_reaches_the_card(bench):
    app, dialog, controller = bench()

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    cards = dialog.result_cards()
    assert cards, "sonuc karti olusmadi"
    assert cards[0].result["file_id"] == 7135238


def test_language_label_is_converted_to_a_code(bench):
    client = FakeClient()
    app, dialog, controller = bench(client=client)
    dialog.language_box.setCurrentText("Türkçe")

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert client.calls[0].get("languages") == "tr"
    assert LANGUAGE_CODES["Türkçe"] == "tr"


def test_series_fields_are_forwarded_from_the_dialog(bench):
    client = FakeClient(responses=[[], OFFICIAL])
    app, dialog, controller = bench(client=client)
    dialog.season_field.setText("3")
    dialog.episode_field.setText("7")

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    name_call = client.calls[1]
    assert name_call.get("season_number") == 3
    assert name_call.get("episode_number") == 7


def test_movie_mode_sends_no_season_or_episode(bench):
    client = FakeClient(responses=[OFFICIAL])
    app, dialog, controller = bench(media=MOVIE, client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    for call in client.calls:
        assert "season_number" not in call
        assert "episode_number" not in call


# --- 9/10/11/12. Durumlar ---

def test_loading_state_and_disabled_search_button(bench):
    client = FakeClient(delay=0.3)
    app, dialog, controller = bench(client=client)

    controller.start_search()
    app.processEvents()

    assert dialog.search_button.isEnabled() is False
    assert "aran" in dialog.status_text().lower()
    pump_until(app, lambda: controller.is_idle())
    assert dialog.search_button.isEnabled() is True


def test_previous_results_are_cleared_when_a_search_starts(bench):
    client = FakeClient(responses=[OFFICIAL, SECOND], delay=0.2)
    app, dialog, controller = bench(client=client)
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    assert dialog.result_cards()

    controller.start_search()
    app.processEvents()
    assert dialog.result_cards() == [], "eski sonuclar temizlenmedi"
    pump_until(app, lambda: controller.is_idle())


def test_successful_search_shows_cards_without_auto_selection(bench):
    app, dialog, controller = bench()

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert len(dialog.result_cards()) == 1
    assert dialog.selected_result() is None, "ilk sonuc otomatik secildi"
    assert dialog.apply_button.isEnabled() is False


def test_no_result_state(bench):
    client = FakeClient(responses=[[], []])
    app, dialog, controller = bench(client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert dialog.result_cards() == []
    assert "bulunamadı" in dialog.status_text().lower()


def test_safe_error_state(bench):
    client = FakeClient(error=osub.RateLimitError("429"))
    app, dialog, controller = bench(client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    message = dialog.status_text()
    assert message == osub.safe_message(osub.RateLimitError())
    assert "429" not in message
    assert "Traceback" not in message
    assert dialog.search_button.isEnabled() is True


def test_missing_credentials_becomes_a_user_message(bench):
    client = FakeClient(error=osub.MissingCredentialsError())
    app, dialog, controller = bench(client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert "anahtar" in dialog.status_text().lower()


def test_secrets_never_reach_the_ui(bench):
    class LeakyError(osub.SubtitleServiceError):
        user_message = "Servis hatası."

    client = FakeClient(error=LeakyError("APIKEY=SECRET123 token=TKN"))
    app, dialog, controller = bench(client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert "SECRET123" not in dialog.status_text()
    assert "TKN" not in dialog.status_text()


# --- 13/14. Tekrarlanan aramalar ---

def test_search_can_be_retried_after_an_error(bench):
    client = FakeClient(error=osub.ServerError("500"))
    app, dialog, controller = bench(client=client)
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    client.error = None
    client.responses = [OFFICIAL]
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert dialog.result_cards()


def test_second_search_replaces_the_first_results(bench):
    client = FakeClient(responses=[OFFICIAL, SECOND])
    app, dialog, controller = bench(client=client)
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    assert dialog.result_cards()[0].result["file_id"] == 7135238

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    cards = dialog.result_cards()
    assert len(cards) == 1
    assert cards[0].result["file_id"] == 555


def test_second_search_is_ignored_while_the_first_runs(bench):
    client = FakeClient(responses=[OFFICIAL], delay=0.3)
    app, dialog, controller = bench(client=client)

    controller.start_search()
    app.processEvents()
    started_again = controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert started_again is False, "ilk arama surerken ikincisi baslatildi"
    assert len(client.calls) == 1


# --- 15. Stale sonuç koruması ---

def test_stale_worker_results_are_rejected(bench):
    app, dialog, controller = bench()
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    current = controller.generation()

    # Gecikmis eski worker'dan gelen sinyal simule edilir.
    controller._on_results(current - 1, [
        {"file_id": 999, "name": "ESKI", "language": "tr", "format": "srt",
         "moviehash_match": False, "downloads": 0, "ratings": 0,
         "hearing_impaired": False}])
    app.processEvents()

    ids = [card.result["file_id"] for card in dialog.result_cards()]
    assert 999 not in ids, "stale sonuc UI'a sizdi"


def test_stale_error_is_rejected(bench):
    app, dialog, controller = bench()
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    before = dialog.status_text()

    controller._on_failed(controller.generation() - 1, "ESKI HATA")
    app.processEvents()

    assert dialog.status_text() == before


# --- 16/17/18/19. Yaşam döngüsü ---

def test_closing_during_search_cancels_and_finishes_cleanly(bench):
    client = FakeClient(delay=0.4)
    app, dialog, controller = bench(client=client)
    controller.start_search()
    app.processEvents()

    dialog.close()
    app.processEvents()
    assert controller.is_cancelled() is True

    assert pump_until(app, lambda: controller.is_idle(), 6000), (
        "thread dogal olarak bitmedi")
    assert controller.thread_is_running() is False


def test_references_are_held_until_finished(bench):
    client = FakeClient(delay=0.25)
    app, dialog, controller = bench(client=client)

    controller.start_search()
    app.processEvents()
    assert controller._thread is not None
    assert controller._worker is not None
    assert controller.thread_is_running() is True

    pump_until(app, lambda: controller.is_idle())
    assert controller._thread is None
    assert controller._worker is None


def test_no_forced_thread_termination_in_source():
    import inspect

    from app import subtitle_search_controller

    source = inspect.getsource(subtitle_search_controller)
    assert "terminate()" not in source
    assert ".quit()" in source or "requestInterruption" in source


def test_shutdown_waits_for_the_thread(bench):
    client = FakeClient(delay=0.3)
    app, dialog, controller = bench(client=client)
    controller.start_search()
    app.processEvents()

    controller.shutdown(wait_ms=5000)

    assert controller.thread_is_running() is False
    assert controller.is_cancelled() is True


# --- 20/21/22. Seçim, indirme ve ağ ---

def test_selected_card_file_id_is_kept_in_state(bench):
    app, dialog, controller = bench()
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    dialog.select_result(dialog.result_cards()[0])
    app.processEvents()

    assert dialog.selected_result()["file_id"] == 7135238
    assert controller.selected_file_id() == 7135238


def test_the_download_action_does_nothing_this_round(bench):
    """ESKİ AD: `test_download_buttons_do_nothing_this_round`."""
    client = FakeClient()
    app, dialog, controller = bench(client=client)
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    dialog.select_result(dialog.result_cards()[0])

    dialog.apply_button.click()
    app.processEvents()

    assert client.downloads == [], "bu turda indirme yapilmamali"


def test_controller_makes_no_real_network_calls(bench):
    client = FakeClient()
    app, dialog, controller = bench(client=client)

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    # Yalnizca enjekte edilen sahte istemci kullanildi.
    assert client.calls
    assert not hasattr(client, "_transport")


# --- Denetim 1: Qt katmani CORE worker'a delege etmeli ---

class FakeCoreWorker:
    """app.opensubtitles.SubtitleSearchWorker yerine gecen sahte cekirdek."""

    instances = []

    def __init__(self, client, plan, on_results=None, on_error=None):
        self.client = client
        self.plan = list(plan or [])
        self.on_results = on_results
        self.on_error = on_error
        self.run_calls = []
        self.cancelled = False
        FakeCoreWorker.instances.append(self)

    def cancel(self):
        self.cancelled = True

    def is_cancelled(self):
        return self.cancelled

    def run(self, language="tr"):
        self.run_calls.append(language)
        if self.on_results:
            self.on_results([{"file_id": 4242, "name": "CORE",
                              "language": "tr", "format": "srt",
                              "moviehash_match": False, "downloads": 1,
                              "ratings": 1.0, "hearing_impaired": False}])
        return []


def test_qt_adapter_delegates_to_the_core_worker(bench, monkeypatch):
    FakeCoreWorker.instances = []
    monkeypatch.setattr(osub, "SubtitleSearchWorker", FakeCoreWorker)
    app, dialog, controller = bench()

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert FakeCoreWorker.instances, "core SubtitleSearchWorker kullanilmadi"
    core = FakeCoreWorker.instances[0]
    assert core.run_calls == ["tr"], f"core run() cagrilmadi: {core.run_calls}"
    ids = [card.result["file_id"] for card in dialog.result_cards()]
    assert ids == [4242], "core sonucu Qt signal'ine cevrilmedi"


def test_core_worker_error_callback_becomes_a_failed_signal(bench, monkeypatch):
    class ErroringCore(FakeCoreWorker):
        def run(self, language="tr"):
            self.run_calls.append(language)
            if self.on_error:
                self.on_error(osub.safe_message(osub.RateLimitError()))
            return []

    FakeCoreWorker.instances = []
    monkeypatch.setattr(osub, "SubtitleSearchWorker", ErroringCore)
    app, dialog, controller = bench()

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert dialog.status_text() == osub.safe_message(osub.RateLimitError())
    assert dialog.search_button.isEnabled() is True


def test_cancel_reaches_the_core_worker(bench, monkeypatch):
    class SlowCore(FakeCoreWorker):
        def run(self, language="tr"):
            self.run_calls.append(language)
            end = time.time() + 0.4
            while time.time() < end and not self.cancelled:
                time.sleep(0.02)
            return []

    FakeCoreWorker.instances = []
    monkeypatch.setattr(osub, "SubtitleSearchWorker", SlowCore)
    app, dialog, controller = bench()

    controller.start_search()
    app.processEvents()
    controller.cancel()
    pump_until(app, lambda: controller.is_idle())

    assert FakeCoreWorker.instances[0].cancelled is True, (
        "iptal istegi core worker'a ulasmadi")


def test_controller_does_not_reimplement_the_search_chain():
    import inspect

    from app import subtitle_search_controller

    source = inspect.getsource(subtitle_search_controller)
    for name in ("normalize_results", "filter_results", "rank_results"):
        assert f"{name}(" not in source, (
            f"arama zinciri controller'da kopyalanmis: {name}")


# --- Denetim 2: stale selected_file_id ---

def test_file_id_is_none_without_a_selection(bench):
    app, dialog, controller = bench()
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert controller.selected_file_id() is None


def test_file_id_forgotten_when_selection_is_cleared(bench):
    app, dialog, controller = bench()
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    dialog.select_result(dialog.result_cards()[0])
    assert controller.selected_file_id() == 7135238

    dialog.select_result(None)
    app.processEvents()

    assert controller.selected_file_id() is None, "eski file_id donuyor"


def test_file_id_forgotten_after_a_new_search(bench):
    client = FakeClient(responses=[OFFICIAL, SECOND])
    app, dialog, controller = bench(client=client)
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    dialog.select_result(dialog.result_cards()[0])
    assert controller.selected_file_id() == 7135238

    controller.start_search()
    pump_until(app, lambda: controller.is_idle())

    assert controller.selected_file_id() is None, (
        "yeni aramada eski file_id korundu")


@pytest.mark.parametrize("state", ("loading", "empty", "error"))
def test_file_id_is_none_in_transient_states(bench, state):
    app, dialog, controller = bench()
    controller.start_search()
    pump_until(app, lambda: controller.is_idle())
    dialog.select_result(dialog.result_cards()[0])
    assert controller.selected_file_id() == 7135238

    if state == "loading":
        dialog.show_loading()
    elif state == "empty":
        dialog.show_results([])
    else:
        dialog.show_error("Servis hatası.")
    app.processEvents()

    assert controller.selected_file_id() is None


# --- Denetim 4: GUI kapanisi bloklamamali ---

def test_close_path_does_not_wait_on_the_thread(bench):
    started = threading.Event()
    release = threading.Event()

    class BlockingClient(FakeClient):
        def search(self, **params):
            self.calls.append(dict(params))
            self.threads.append(threading.get_ident())
            started.set()
            release.wait(timeout=3.0)
            return self.responses[0]

    client = BlockingClient()
    app, dialog, controller = bench(client=client)
    controller.start_search()
    assert pump_until(app, started.is_set), "worker gerçekten başlamadı"

    started = time.perf_counter()
    dialog.close()
    app.processEvents()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.15, f"kapatma GUI'yi {elapsed:.3f}s blokladi"
    assert controller.is_cancelled() is True
    assert controller.thread_is_running() is True, (
        "kapatma thread'i senkron bekledi")
    release.set()
    pump_until(app, lambda: controller.is_idle())


def test_close_signal_handler_never_calls_wait():
    import inspect

    from app import subtitle_search_controller

    source = inspect.getsource(subtitle_search_controller.SubtitleSearchController)
    cancel_source = inspect.getsource(
        subtitle_search_controller.SubtitleSearchController.cancel)
    assert "wait(" not in cancel_source, "cancel() thread'i bekliyor"


def test_controller_survives_dialog_destruction(bench):
    client = FakeClient(delay=0.35)
    app, dialog, controller = bench(client=client)
    controller.start_search()
    app.processEvents()
    assert controller.thread_is_running() is True

    dialog.deleteLater()
    # deleteLater yalnizca processEvents ile bosalmaz; ertelenmis silme
    # kuyrugu acikca akitilir.
    from PyQt6.QtCore import QEvent

    deadline = time.time() + 3.0
    while time.time() < deadline and controller.dialog is not None:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)

    assert controller.dialog is None, "dialog referansi temizlenmedi"
    assert pump_until(app, lambda: controller.is_idle(), 6000), (
        "dialog yok edildikten sonra thread dogal bitmedi")


def test_worker_uses_a_qthread(bench):
    client = FakeClient(delay=0.2)
    app, dialog, controller = bench(client=client)

    controller.start_search()
    app.processEvents()
    assert isinstance(controller._thread, QThread)
    pump_until(app, lambda: controller.is_idle())
