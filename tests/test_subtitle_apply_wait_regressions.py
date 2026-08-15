"""MPV `apply()` bekleme davranışı regresyonları — GECİKMELİ track.

Neden ayrı dosya
----------------
Mevcut indirme testlerindeki `FakeMpv.sub_add()` track'i ANINDA ekliyordu;
`FakeClient` ise 300 ms uyuyordu. Bu yüzden ölçülen tek şey ağ beklemesiydi
ve gerçek `apply()` polling süresi HİÇ sınanmıyordu.

Burada tersi kurulur:

- `FakeClient` gecikmesizdir (delay=0): ölçülen süre yalnız apply beklemesidir.
- `DelayedTrackMPV.sub_add()` track'i hemen EKLEMEZ; `QTimer.singleShot` ile
  ~60-200 ms sonra ekler — gerçek MPV'nin gecikmeli `track_list` güncellemesi.
- Listede önceden YANLIŞ bir dahili sub track (id=1) bulunur; doğrulanmamış
  "son track" seçilirse test bunu yakalar.

GERÇEK AĞA ÇIKILMAZ. Kullanıcının medya dizinine yazılmaz (tmp_path).
"""
import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import subtitle_service as service
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_download_controller import (
    STATUS_APPLIED, STATUS_PARTIAL, SubtitleDownloadController)

VIDEO_NAME = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.mkv"
TARGET_NAME = "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.srt"
GOOD_URL = "https://dl.opensubtitles.com/download/abc.srt"
SRT = b"1\n00:00:01,000 --> 00:00:04,000\nMerhaba dunya\n"
RESULT = {"file_id": 7135238, "name": "Uzak.Ad", "language": "Türkçe",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}

# Gerçek polling bütçesi: 40 x 10 ms ≈ 0.4 s.
EXPECTED_BUDGET_S = (service.TRACK_WAIT_ATTEMPTS
                     * service.TRACK_WAIT_INTERVAL_S)


class InstantClient:
    """Gecikmesiz istemci: ölçülen süre yalnız apply beklemesinden gelir."""

    def __init__(self, payload=SRT):
        self.payload = payload
        self.download_calls = []
        self.fetch_calls = []

    def download_link(self, file_id):
        self.download_calls.append(file_id)
        return GOOD_URL

    def fetch(self, url):
        self.fetch_calls.append(url)
        return self.payload


class DelayedTrackMPV:
    """`sub_add()` track'i ANINDA eklemez; gerçek MPV gibi gecikmeli ekler."""

    def __init__(self, delay_ms=80, never=False):
        # Yanlış dahili track önceden listede: doğrulanmamış seçim yakalanır.
        self.track_list = [{"type": "sub", "id": 1, "selected": False}]
        self.removed = []
        self.added = []
        self.sid = "no"
        self.sub_visibility = False
        self.delay_ms = delay_ms
        self.never = never
        self._next = 2

    def sub_add(self, path, *args):
        self.added.append(path)
        if self.never:
            return  # track HİÇ gelmez: tam polling bütçesi harcanmalı.
        track = {"type": "sub", "id": self._next,
                 "external-filename": path, "selected": False}
        self._next += 1
        QTimer.singleShot(self.delay_ms, Qt.TimerType.PreciseTimer,
                          lambda: self.track_list.append(track))

    def sub_remove(self, sid):
        self.removed.append(sid)
        self.track_list = [t for t in self.track_list if t.get("id") != sid]

    def external_tracks(self):
        return [t for t in self.track_list if t.get("external-filename")]


@pytest.fixture
def bench(tmp_path):
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(client=None, mpv=None):
        video = tmp_path / VIDEO_NAME
        video.write_bytes(b"video")
        media = {"file_name": str(video), "title": "Resident Alien",
                 "season": 1, "episode": 1, "is_series": True,
                 "target_name": TARGET_NAME, "movie_hash": "abc",
                 "file_size": 5}
        window = QMainWindow()
        window.show()
        dialog = SubtitleCenterDialog(window, media=media)
        # Görünür dialog: `close()` gerçek kapanış yolunu (finished) tetikler.
        dialog.show()
        mpv_obj = mpv if mpv is not None else DelayedTrackMPV()
        player = SimpleNamespace(mpv_player=mpv_obj, video_frame=None)
        controller = SubtitleDownloadController(
            dialog, client=client or InstantClient(), player=player,
            owner=window)
        dialog.show_results([RESULT])
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
                widget.deleteLater()
            except RuntimeError:
                pass
    app.processEvents()


def pump_until(app, predicate, timeout_ms=8000):
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.002)
    app.processEvents()
    return predicate()


def settled(controller):
    return controller.is_idle() and not controller.is_applying()


# --- 1. Gecikmeli track GERÇEKTEN yakalanmalı ---

def test_delayed_external_track_is_found_and_selected(bench):
    """Mevcut `processEvents(...,10)` yolunda 40 deneme birkaç ms'de tükenir
    ve gecikmeli track kaçırılır."""
    mpv = DelayedTrackMPV(delay_ms=80)
    app, dialog, controller, mpv, tmp = bench(mpv=mpv)

    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))

    external = mpv.external_tracks()
    assert len(external) == 1, f"tek external track bekleniyordu: {mpv.track_list}"
    assert mpv.sid == external[0]["id"], "gecikmeli dogru track secilmedi"
    assert mpv.sid != 1, "yanlis dahili track secildi"
    assert mpv.sub_visibility is True
    assert dialog.status_text() == STATUS_APPLIED


def test_slower_delayed_track_is_still_inside_the_budget(bench):
    mpv = DelayedTrackMPV(delay_ms=200)
    app, dialog, controller, mpv, tmp = bench(mpv=mpv)

    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))

    assert mpv.sid == mpv.external_tracks()[0]["id"]
    assert dialog.status_text() == STATUS_APPLIED


# --- 2. Track hiç gelmezse GERÇEK süre harcanmalı ---

def test_apply_spends_real_time_when_the_track_never_arrives(bench):
    mpv = DelayedTrackMPV(never=True)
    app, dialog, controller, mpv, tmp = bench(mpv=mpv)

    started = time.monotonic()
    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))
    elapsed = time.monotonic() - started

    assert elapsed >= 0.25, (
        f"apply beklemesi gercek zaman harcamadi: {elapsed:.3f}s "
        f"(beklenen butce ~{EXPECTED_BUDGET_S:.2f}s)")
    # Windows zamanlayici cozunurlugu icin genis tolerans.
    assert elapsed <= 0.8, f"apply beklemesi butceyi asti: {elapsed:.3f}s"
    assert dialog.status_text() == STATUS_PARTIAL
    assert (tmp / TARGET_NAME).exists(), "kismi basarida dosya silinmemeli"


def test_ui_event_loop_progresses_during_apply_polling(bench):
    """B kanıtı: ağ gecikmesi YOK; ölçülen tick'ler apply beklemesindendir."""
    mpv = DelayedTrackMPV(never=True)
    app, dialog, controller, mpv, tmp = bench(mpv=mpv)

    ticks = {"n": 0}
    timer = QTimer()
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    timer.start()
    try:
        controller.download_and_apply()
        assert pump_until(app, lambda: settled(controller))
    finally:
        timer.stop()

    assert ticks["n"] > 3, f"apply sirasinda UI dondu (tick={ticks['n']})"


# --- 3. Apply sırasında kapatma / yok etme ---

def test_close_during_apply_reports_no_success(bench):
    mpv = DelayedTrackMPV(delay_ms=200)
    app, dialog, controller, mpv, tmp = bench(mpv=mpv)

    QTimer.singleShot(30, Qt.TimerType.PreciseTimer, dialog.close)
    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))

    assert controller.is_cancelled() is True
    assert mpv.sid == "no", "iptalden sonra track zorla secildi"
    assert mpv.sub_visibility is False
    assert STATUS_APPLIED not in dialog.status_text()
    # Kayit basariyla tamamlandi: indirilen dosya KORUNUR.
    assert (tmp / TARGET_NAME).read_bytes() == SRT
    assert controller.thread_is_running() is False


def test_delete_later_during_apply_is_safe(bench):
    mpv = DelayedTrackMPV(delay_ms=200)
    app, dialog, controller, mpv, tmp = bench(mpv=mpv)

    def destroy():
        dialog.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    QTimer.singleShot(30, Qt.TimerType.PreciseTimer, destroy)
    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))

    assert controller.dialog is None, "yok edilen dialog referansi birakilmadi"
    assert mpv.sid == "no"
    assert (tmp / TARGET_NAME).read_bytes() == SRT
    assert controller.thread_is_running() is False


# --- 4. Nested event loop disiplini ---

def test_second_download_cannot_start_during_apply(bench):
    client = InstantClient()
    mpv = DelayedTrackMPV(delay_ms=200)
    app, dialog, controller, mpv, tmp = bench(client=client, mpv=mpv)
    attempts = {"result": None}

    def reenter():
        if controller.is_applying():
            attempts["result"] = controller.download_and_apply()

    QTimer.singleShot(40, Qt.TimerType.PreciseTimer, reenter)
    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))

    assert attempts["result"] is False, "apply sirasinda ikinci indirme basladi"
    assert len(client.download_calls) == 1


def test_no_timer_or_loop_residue_after_apply(bench):
    mpv = DelayedTrackMPV(never=True)
    app, dialog, controller, mpv, tmp = bench(mpv=mpv)

    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))
    app.processEvents()

    assert controller.is_applying() is False
    assert controller.findChildren(QTimer) == [], "bekleme timer'i kaldi"


def test_buttons_recover_after_apply(bench):
    app, dialog, controller, mpv, tmp = bench()

    controller.download_and_apply()
    assert pump_until(app, lambda: settled(controller))

    assert dialog.apply_button.isEnabled() is True


# --- 5. Çekirdek sözleşme: opsiyonel iptal geri çağrısı ---

class InstantMPV(DelayedTrackMPV):
    def sub_add(self, path, *args):
        self.added.append(path)
        self.track_list.append({"type": "sub", "id": self._next,
                                "external-filename": path, "selected": False})
        self._next += 1


def test_apply_without_cancel_callback_behaves_as_before():
    mpv = InstantMPV()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    session = service.SubtitleSession()

    assert session.apply(player, "C:/tmp/x.srt") is True
    assert mpv.sid == 2
    assert mpv.sub_visibility is True


def test_apply_returns_false_when_cancelled_before_selection():
    mpv = InstantMPV()
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    session = service.SubtitleSession()

    applied = session.apply(player, "C:/tmp/x.srt",
                            is_cancelled=lambda: True)

    assert applied is False
    assert mpv.sid == "no", "iptalde track secildi"
    assert mpv.sub_visibility is False


def test_apply_cancellation_stops_the_polling_loop():
    mpv = DelayedTrackMPV(never=True)
    player = SimpleNamespace(mpv_player=mpv, video_frame=None)
    session = service.SubtitleSession()
    waits = {"n": 0}

    def wait():
        waits["n"] += 1

    applied = session.apply(player, "C:/tmp/x.srt", wait=wait,
                            attempts=service.TRACK_WAIT_ATTEMPTS,
                            is_cancelled=lambda: waits["n"] >= 3)

    assert applied is False
    assert waits["n"] < service.TRACK_WAIT_ATTEMPTS, (
        "iptal edildigi halde butun butce harcandi")
