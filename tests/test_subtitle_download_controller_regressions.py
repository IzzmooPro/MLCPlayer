"""Altyazı indirme/kaydetme/uygulama turu regresyonları.

GERÇEK AĞA ÇIKILMAZ: fake client + tmp_path + fake MPV kullanılır.
Kullanıcının gerçek medya dizinine hiçbir yazma yapılmaz.
"""
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import opensubtitles as osub
from app import subtitle_service as service
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_download_controller import SubtitleDownloadController

VIDEO_NAME = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv"
TARGET_NAME = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.srt"
GOOD_URL = "https://dl.opensubtitles.com/download/abc.srt"
BAD_URL = "https://evil.example.com/a.srt"
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba dunya\n"
SRT_TR_CP1254 = "1\n00:00:01,000 --> 00:00:04,000\nÇöğüşİı selam\n".encode("cp1254")
RESULT = {"file_id": 7135238, "name": "Uzak.Altyazi.Adi.turkish",
          "file_name": "BAMBASKA.turkish.HI.srt", "language": "Türkçe",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}


class FakeClient:
    def __init__(self, link=GOOD_URL, payload=SRT, link_error=None,
                 fetch_error=None, delay=0.0):
        self.link = link
        self.payload = payload
        self.link_error = link_error
        self.fetch_error = fetch_error
        self.delay = delay
        self.download_calls = []
        self.fetch_calls = []
        self.threads = []

    def download_link(self, file_id):
        self.download_calls.append(file_id)
        self.threads.append(threading.get_ident())
        if self.delay:
            time.sleep(self.delay)
        if self.link_error:
            raise self.link_error
        return self.link

    def fetch(self, url):
        self.fetch_calls.append(url)
        if not osub.is_trusted_download_url(url):
            raise osub.UntrustedUrlError("untrusted")
        if self.fetch_error:
            raise self.fetch_error
        return self.payload


class FakeMpv:
    def __init__(self):
        self.track_list = [{"type": "sub", "id": 1, "selected": False}]
        self.removed = []
        self.sid = "no"
        self.sub_visibility = False
        self._next = 2

    def sub_add(self, path, *args):
        self.track_list.append({"type": "sub", "id": self._next,
                                "external-filename": path, "selected": False})
        self._next += 1

    def sub_remove(self, sid):
        self.removed.append(sid)
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(client=None, mpv=None, exists=None, select=True):
        video = tmp_path / VIDEO_NAME
        video.write_bytes(b"video")
        if exists is not None:
            (tmp_path / TARGET_NAME).write_bytes(exists)
        media = {
            "file_name": str(video), "title": "Resident Alien",
            "season": 1, "episode": 1, "is_series": True,
            "target_name": TARGET_NAME,
            "movie_hash": "abc", "file_size": 5,
        }
        window = QMainWindow()
        window.show()
        dialog = SubtitleCenterDialog(window, media=media)
        dialog.show()
        mpv_obj = mpv if mpv is not None else FakeMpv()
        player = SimpleNamespace(mpv_player=mpv_obj, video_frame=None)
        controller = SubtitleDownloadController(
            dialog, client=client or FakeClient(), player=player,
            owner=window)
        dialog.show_results([RESULT])
        if select:
            dialog.select_result(dialog.result_cards()[0])
        app.processEvents()
        created.append((window, dialog, controller))
        return app, dialog, controller, mpv_obj, tmp_path

    yield factory

    for window, dialog, controller in created:
        controller.shutdown(wait_ms=4000)
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


# --- 1. Seçim yoksa işlem yok ---

def test_no_operation_without_selection(bench):
    client = FakeClient()
    app, dialog, controller, mpv, tmp = bench(client=client, select=False)

    assert controller.download_and_apply() is False
    assert controller.download_and_apply() is False
    app.processEvents()

    assert client.download_calls == []


# --- 2/3/4. Zincir ve URL güveni ---

def test_correct_file_id_reaches_download_link(bench):
    client = FakeClient()
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert client.download_calls == [7135238]


def test_trusted_link_is_fetched(bench):
    client = FakeClient()
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert client.fetch_calls == [GOOD_URL]


def test_untrusted_link_is_never_fetched(bench):
    client = FakeClient(link=BAD_URL)
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert client.fetch_calls == [], "guvenilmeyen adrese istek gonderildi"
    assert not (tmp / TARGET_NAME).exists()
    assert dialog.status_text().strip() != ""


# --- 5/6/7. Hedef adı ve başarılı indirme ---

def test_target_name_matches_the_video_exactly(bench):
    app, dialog, controller, mpv, tmp = bench()

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    files = sorted(p.name for p in tmp.glob("*.srt"))
    assert files == [TARGET_NAME]


def test_remote_subtitle_name_is_not_used(bench):
    app, dialog, controller, mpv, tmp = bench()

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    names = [p.name for p in tmp.iterdir()]
    assert "BAMBASKA.turkish.HI.srt" not in names
    assert not any(n.endswith((".tr.srt", ".1.srt", "(1).srt")) for n in names)


def test_successful_download_when_target_missing(bench):
    app, dialog, controller, mpv, tmp = bench()

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert (tmp / TARGET_NAME).read_bytes() == SRT
    assert "indirildi" in dialog.status_text().lower()
    assert str(tmp) not in dialog.status_text(), "tam yerel yol gosteriliyor"


# --- 8/9/10. Üzerine yazma (ONAY SORULMAZ) ---
#
# KALDIRILAN ESKİ TESTLER: `test_denied_overwrite_makes_zero_network_calls`,
# `test_missing_confirm_callback_is_fail_closed`. İkisi de kullanıcıya
# sorulan bir onayı ve onun fail-closed davranışını ölçüyordu; hedef
# videodan tek anlamlı türediği için bu soru ürün sözleşmesinden çıktı.
# Korunan garanti aşağıda ve `test_invalid_srt_does_not_overwrite_existing_file`
# içinde ölçülür: mevcut dosya YALNIZ doğrulanmış içerikle değişir.

def test_existing_file_is_replaced_without_being_asked(bench):
    app, dialog, controller, mpv, tmp = bench(exists=b"ESKI DOSYA")

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert (tmp / TARGET_NAME).read_bytes() == SRT
    assert sorted(p.name for p in tmp.glob("*.srt")) == [TARGET_NAME]


# --- 11/12. Dosya güvenliği ---

def test_invalid_srt_does_not_overwrite_existing_file(bench):
    client = FakeClient(payload=b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nx\n")
    app, dialog, controller, mpv, tmp = bench(
        client=client, exists=b"CALISAN SRT")

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert (tmp / TARGET_NAME).read_bytes() == b"CALISAN SRT"
    leftovers = [p.name for p in tmp.iterdir()
                 if p.name not in (VIDEO_NAME, TARGET_NAME)]
    assert leftovers == [], f"gecici dosya kaldi: {leftovers}"


def test_cp1254_payload_is_saved_as_utf8(bench):
    client = FakeClient(payload=SRT_TR_CP1254)
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    text = (tmp / TARGET_NAME).read_bytes().decode("utf-8")
    assert "Çöğüşİı" in text


# --- 13/14/15. MPV davranışı ---

# KALDIRILAN ESKİ TEST: `test_download_only_never_touches_mpv`.
# "Yalnızca İndir" akışı yoktur; başarılı her indirme MPV'ye uygulanır.
# Uygulamanın TAM OLARAK BİR kez ve doğru parçayla yapıldığı
# `test_download_and_apply_selects_one_correct_external_track` ile ölçülür.


def test_download_and_apply_selects_one_correct_external_track(bench):
    app, dialog, controller, mpv, tmp = bench()

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    external = [t for t in mpv.track_list if t.get("external-filename")]
    assert len(external) == 1
    assert mpv.sid == external[0]["id"]
    assert mpv.sid != 1, "yanlis dahili track secildi"
    assert mpv.sub_visibility is True
    assert "uygulandı" in dialog.status_text().lower()


def test_repeated_apply_keeps_a_single_external_track(bench):
    app, dialog, controller, mpv, tmp = bench()

    for _ in range(3):
        controller.download_and_apply()
        pump_until(app, lambda: controller.is_idle())

    external = [t for t in mpv.track_list if t.get("external-filename")]
    assert len(external) == 1


# --- 16/17. Kısmi başarı ve sıra ---

def test_partial_success_when_apply_fails(bench):
    class NoAddMpv(FakeMpv):
        def sub_add(self, path, *args):
            pass  # track hic olusmaz -> apply dogrulanamaz

    app, dialog, controller, mpv, tmp = bench(mpv=NoAddMpv())

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert (tmp / TARGET_NAME).exists(), "kismi basarida dosya silinmemeli"
    message = dialog.status_text().lower()
    assert "indirildi" in message and "uygulanamadı" in message
    assert "uygulandı" not in message


def test_apply_is_skipped_when_saving_fails(bench):
    client = FakeClient(payload=b"bozuk-icerik")
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert mpv.removed == []
    assert all("external-filename" not in t for t in mpv.track_list)
    assert not (tmp / TARGET_NAME).exists()


# --- 18/19. Ağ ve eşzamanlılık disiplini ---

def test_download_post_is_not_retried(bench):
    client = FakeClient(link_error=osub.ServerError("503"))
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert len(client.download_calls) == 1
    assert dialog.status_text() == osub.safe_message(osub.ServerError())


def test_second_download_is_ignored_while_running(bench):
    client = FakeClient(delay=0.3)
    app, dialog, controller, mpv, tmp = bench(client=client)

    assert controller.download_and_apply() is True
    app.processEvents()
    assert controller.download_and_apply() is False
    pump_until(app, lambda: controller.is_idle())

    assert len(client.download_calls) == 1


def test_buttons_disabled_during_the_operation(bench):
    client = FakeClient(delay=0.3)
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    app.processEvents()
    assert dialog.apply_button.isEnabled() is False
    assert "indiriliyor" in dialog.status_text().lower()

    pump_until(app, lambda: controller.is_idle())
    assert dialog.apply_button.isEnabled() is True


# --- 20/21/22. Yaşam döngüsü ve UI akıcılığı ---

def test_close_during_download_finishes_naturally(bench):
    client = FakeClient(delay=0.4)
    app, dialog, controller, mpv, tmp = bench(client=client)
    controller.download_and_apply()
    app.processEvents()

    dialog.close()
    app.processEvents()

    assert pump_until(app, lambda: controller.is_idle(), 6000)
    assert controller.thread_is_running() is False


def test_delete_later_during_download_finishes_naturally(bench):
    from PyQt6.QtCore import QEvent

    client = FakeClient(delay=0.4)
    app, dialog, controller, mpv, tmp = bench(client=client)
    controller.download_and_apply()
    app.processEvents()

    dialog.deleteLater()
    deadline = time.time() + 3
    while time.time() < deadline and controller.dialog is not None:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        time.sleep(0.01)

    assert controller.dialog is None
    assert pump_until(app, lambda: controller.is_idle(), 6000)


def test_download_runs_off_the_main_thread(bench):
    client = FakeClient(delay=0.2)
    app, dialog, controller, mpv, tmp = bench(client=client)
    main_thread = threading.get_ident()

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert client.threads and all(t != main_thread for t in client.threads)


def test_ui_event_loop_progresses_during_the_download_thread(bench):
    """A kanıtı: indirme QThread'i sürerken UI ilerliyor.

    Bu test SADECE ağ/indirme beklemesini ölçer (`FakeMpv` track'i anında
    ekler, yani apply beklemesi yoktur). Apply polling'i sırasındaki UI
    akıcılığı ayrı bir kanıttır; bkz.
    `tests/test_subtitle_apply_wait_regressions.py`
    (`test_ui_event_loop_progresses_during_apply_polling`).
    """
    client = FakeClient(delay=0.3)
    app, dialog, controller, mpv, tmp = bench(client=client)
    ticks = {"n": 0}
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    timer.start()
    try:
        controller.download_and_apply()
        pump_until(app, lambda: controller.is_idle())
    finally:
        timer.stop()

    assert ticks["n"] > 3, f"UI dondu (tick={ticks['n']})"


def test_apply_is_given_a_wait_callback_so_it_never_sleeps(bench, monkeypatch):
    """NOT: `service.time.sleep` yamalamak GLOBAL time modulunu yamalar ve
    testin kendi bekleme dongusunu de sayar. Bu yuzden gercek sozlesme
    olculur: apply'a bir `wait` geri cagrisi verilir; `SubtitleSession.apply`
    zaten `wait` verildiginde time.sleep KULLANMAZ (ayri testle kilitli).
    """
    captured = {}
    original = service.SubtitleSession.apply

    def spy(self, player, target, wait=None, attempts=None, **kwargs):
        captured["wait"] = wait
        captured["attempts"] = attempts
        return original(self, player, target, wait=wait,
                        attempts=attempts or service.TRACK_WAIT_ATTEMPTS)

    monkeypatch.setattr(service.SubtitleSession, "apply", spy)
    app, dialog, controller, mpv, tmp = bench()

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    assert callable(captured.get("wait")), "apply'a wait geri cagrisi verilmedi"
    assert (captured.get("attempts") or 0) <= service.TRACK_WAIT_ATTEMPTS


def test_qt_wait_callback_does_not_sleep(monkeypatch):
    """Qt bekleme geri cagrisi ana thread'i UYUTMAZ; olay isler.

    NOT: docstring'de "sleep" kelimesi gecebilir (neden kullanilmadigini
    anlatir); olculen sey KOD govdesidir. Gercek bekleme suresi ayrica
    `tests/test_subtitle_apply_wait_regressions.py` icinde olculur.
    """
    import ast
    import inspect
    import textwrap

    from app.subtitle_download_controller import SubtitleDownloadController

    source = inspect.getsource(SubtitleDownloadController._qt_wait)
    tree = ast.parse(textwrap.dedent(source))
    function = tree.body[0]
    if (function.body and isinstance(function.body[0], ast.Expr)
            and isinstance(function.body[0].value, ast.Constant)):
        del function.body[0]  # docstring govdeye dahil degildir
    body = ast.unparse(function)

    assert "sleep" not in body, "ana thread uyutuluyor"
    # Ana thread'i uyutmadan olay isleyen Qt yollarindan biri kullanilmali.
    assert "QEventLoop" in body or "processEvents" in body


def test_apply_wait_budget_is_bounded():
    budget = service.TRACK_WAIT_ATTEMPTS * service.TRACK_WAIT_INTERVAL_S
    assert budget <= 0.4


# --- 23/24/25. Artık ve sızıntı ---

def test_no_temporary_files_left_behind(bench):
    app, dialog, controller, mpv, tmp = bench()

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    names = sorted(p.name for p in tmp.iterdir())
    assert names == sorted([VIDEO_NAME, TARGET_NAME])


def test_stale_signal_does_not_disturb_the_ui(bench):
    app, dialog, controller, mpv, tmp = bench()
    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())
    before = dialog.status_text()

    controller._on_failed(controller.generation() - 1, "ESKI HATA")
    app.processEvents()

    assert dialog.status_text() == before


def test_secrets_and_raw_body_never_reach_the_ui(bench):
    class LeakyError(osub.SubtitleServiceError):
        user_message = "Servis hatası."

    client = FakeClient(fetch_error=LeakyError("APIKEY=SECRET token=TKN body=<html>"))
    app, dialog, controller, mpv, tmp = bench(client=client)

    controller.download_and_apply()
    pump_until(app, lambda: controller.is_idle())

    message = dialog.status_text()
    for secret in ("SECRET", "TKN", "<html>", "Traceback"):
        assert secret not in message


def test_no_forced_thread_termination_in_source():
    import inspect

    from app import subtitle_download_controller

    source = inspect.getsource(subtitle_download_controller)
    assert "terminate()" not in source
