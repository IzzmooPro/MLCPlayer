"""Altyazı parçası değişince güvenli bant OTOMATİK uygulanır.

Ölçülen açık: efektif ASS `sub_pos` hesabı doğruydu ama ürün yaşam
döngüsüne bağlı DEĞİLDİ.

- `media_controls.select_subtitle_language()` yalnız `mpv_player.sid`
  yazıp CC göstergesini yeniliyordu.
- `open_subtitle()`, `player` içindeki bekleyen altyazı yolları ve
  `subtitle_service` `sub_add` çağrıları da senkronlamıyordu.
- `sid`/`track-list` için MERKEZİ bir gözlemci yoktu.
- Mevcut ASS↔SRT birim testleri `track_list`i değiştirip
  `sync_subtitle_safe_band()`i ELLE çağırıyordu; gerçek kullanıcı yolunu
  kanıtlamıyordu.

Çözüm dağınık yamalar DEĞİL: tek bir `SubtitleTrackWatcher` MPV'nin
`sid` ve `track-list` özelliklerini gözler. MPV callback'i YABANCI
thread'den geldiği için Qt sinyaliyle ana thread'e taşınır; QWidget'a
oradan dokunulmaz.
"""
import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from app.video_frame import SUBTITLE_BAND_GAP, SubtitleTrackWatcher
from tests.test_subtitle_safe_band_regressions import CountingMpv, Frame


class ObservingMpv(CountingMpv):
    """`observe_property` çağrılarını kaydeden sahte MPV."""

    def __init__(self, **kwargs):
        object.__setattr__(self, "observed", [])
        object.__setattr__(self, "unobserved", [])
        super().__init__(**kwargs)

    def observe_property(self, name, callback):
        object.__getattribute__(self, "observed").append((name, callback))

    def unobserve_property(self, name, callback):
        object.__getattribute__(self, "unobserved").append((name, callback))
        observed = object.__getattribute__(self, "observed")
        try:
            observed.remove((name, callback))
        except ValueError:
            pass

    def notify(self, name="sid"):
        """MPV olayını taklit eder (GERÇEKTE yabancı thread'den gelir)."""
        for observed_name, callback in list(
                object.__getattribute__(self, "observed")):
            if observed_name == name:
                callback(name, getattr(self, "sid", None))


@pytest.fixture
def bench():
    app = QApplication.instance() or QApplication([])

    def factory(codec="subrip", stored_pos=100.0, osd=None):
        osd = osd or {"w": 1400, "h": 772, "mt": 8, "mb": 8}
        mpv = ObservingMpv(osd=osd, codec=codec)
        frame = Frame(772, mpv=mpv)
        frame.main_window.settings.stored["subtitle/sub_pos"] = stored_pos
        watcher = SubtitleTrackWatcher(frame.sync_subtitle_safe_band)
        watcher.attach(mpv)
        return app, frame, mpv, watcher

    return factory


def set_track(mpv, codec, sid=1):
    mpv.sid = sid
    mpv.track_list = ([{"type": "sub", "id": sid, "codec": codec}]
                      if codec else [])


# --- Gözlemci sözleşmesi ----------------------------------------------

def test_the_watcher_observes_track_and_render_area_changes(bench):
    """`sid`, `track-list` ve `osd-dimensions` birlikte gözlenir.

    `osd-dimensions` ölçek referansıdır: tam ekran/playlist geçişinde
    mpv yeni render alanını Qt resize olayından SONRA yerleştiriyor ve
    yalnız geometriye bağlı senkron eski alanla hesaplıyordu.
    """
    app, frame, mpv, watcher = bench()

    names = [name for name, _ in mpv.observed]

    assert sorted(names) == ["osd-dimensions", "sid", "track-list"]


def test_a_render_area_change_recomputes_the_band(bench):
    app, frame, mpv, watcher = bench(codec="ass")
    mpv.notify("sid")
    app.processEvents()
    mpv.writes.clear()

    # Tam ekran: render alanı 756 -> 1384.
    mpv.osd_dimensions = {"w": 2560, "h": 1440, "mt": 28, "mb": 28}
    mpv.notify("osd-dimensions")
    app.processEvents()

    assert sorted(name for name, _ in mpv.writes) == ["sub_margin_y",
                                                      "sub_pos"]
    assert mpv.written["sub_pos"] == round(
        100.0 - (110 + SUBTITLE_BAND_GAP) * 100 / 1440, 2)


def test_the_callback_never_touches_qt_from_the_mpv_thread(bench):
    """MPV callback'i YABANCI thread'den gelir; iş ana thread'e taşınır."""
    app, frame, mpv, watcher = bench()
    threads = []
    original = frame.sync_subtitle_safe_band

    def record():
        threads.append(threading.get_ident())
        return original()

    watcher._on_changed = record
    worker = threading.Thread(target=lambda: mpv.notify("sid"))
    worker.start()
    worker.join(5)
    app.processEvents()

    assert threads, "senkron hiç çalışmadı"
    assert threads[0] == threading.get_ident(), "senkron ana thread'de değil"


# --- GERÇEK ürün geçişleri (elle sync ÇAĞRILMAZ) ----------------------

def test_switching_to_ass_applies_the_effective_position(bench):
    """Kullanıcı menüden SRT → ASS seçer; ek geometri olayı YOK."""
    app, frame, mpv, watcher = bench(codec="subrip")
    mpv.notify("sid")
    app.processEvents()
    assert mpv.written["sub_pos"] == 100.0

    set_track(mpv, "ass")
    mpv.writes.clear()
    mpv.notify("sid")
    app.processEvents()

    assert mpv.written["sub_pos"] < 100.0
    assert [name for name, _ in mpv.writes] == ["sub_pos"]


def test_switching_back_to_srt_restores_the_raw_user_value(bench):
    app, frame, mpv, watcher = bench(codec="ass", stored_pos=90.0)
    mpv.notify("sid")
    app.processEvents()
    assert mpv.written["sub_pos"] < 90.0

    set_track(mpv, "subrip")
    mpv.writes.clear()
    mpv.notify("sid")
    app.processEvents()

    assert mpv.written["sub_pos"] == 90.0


def test_an_external_ass_file_is_handled_by_the_track_list_event(bench):
    """`sub_add` sonrası `track-list` olayı bandı uygular."""
    app, frame, mpv, watcher = bench(codec="subrip")
    mpv.notify("track-list")
    app.processEvents()
    mpv.writes.clear()

    set_track(mpv, "ass", sid=7)
    mpv.notify("track-list")
    app.processEvents()

    assert mpv.written["sub_pos"] < 100.0


def test_a_late_codec_is_picked_up_by_the_second_event(bench):
    """`sid` önce, codec sonra gelirse İKİNCİ olayda ASS algılanır."""
    app, frame, mpv, watcher = bench(codec="subrip")
    mpv.sid = 9
    mpv.track_list = [{"type": "sub", "id": 9}]
    mpv.notify("sid")
    app.processEvents()

    assert mpv.written["sub_pos"] == 100.0, "codec yokken HAM konum"

    mpv.track_list = [{"type": "sub", "id": 9, "codec": "ass"}]
    mpv.writes.clear()
    mpv.notify("track-list")
    app.processEvents()

    assert mpv.written["sub_pos"] < 100.0
    assert [name for name, _ in mpv.writes] == ["sub_pos"]


def test_a_string_sid_is_matched_safely(bench):
    """MPV `sid`i dize verirse de codec doğru eşleşir."""
    app, frame, mpv, watcher = bench(codec="ass")
    mpv.sid = "1"
    mpv.notify("sid")
    app.processEvents()

    assert mpv.written["sub_pos"] < 100.0


def test_repeated_identical_events_write_nothing(bench):
    """Aynı bildirimin tekrarı gereksiz MPV yazımı ÜRETMEZ."""
    app, frame, mpv, watcher = bench(codec="ass")
    mpv.notify("sid")
    app.processEvents()
    written = len(mpv.writes)

    for _ in range(50):
        for name in ("sid", "track-list", "osd-dimensions"):
            mpv.notify(name)
    app.processEvents()

    assert len(mpv.writes) == written, mpv.writes


def test_a_failing_sync_never_escapes_the_callback(bench):
    app, frame, mpv, watcher = bench()

    def boom():
        raise RuntimeError("sentetik")

    watcher._on_changed = boom
    mpv.notify("sid")
    app.processEvents()      # istisna TAŞMAZ


def test_the_stored_preference_is_never_written_by_track_changes(bench):
    app, frame, mpv, watcher = bench(codec="ass", stored_pos=90.0)

    mpv.notify("sid")
    mpv.notify("track-list")
    app.processEvents()

    assert frame.main_window.settings.writes == []
    assert frame.main_window.settings.value("subtitle/sub_pos") == 90.0


# --- Ürün gerçekten bağlı mı? -----------------------------------------

def test_the_player_attaches_the_watcher_to_real_mpv():
    """`MPVPlayer` gözlemciyi GERÇEK mpv nesnesine bağlar."""
    from types import SimpleNamespace

    from app.player import MPVPlayer

    mpv = ObservingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    calls = []
    player = SimpleNamespace(
        mpv_player=mpv,
        video_frame=SimpleNamespace(
            sync_subtitle_safe_band=lambda: calls.append(1)))

    watcher = MPVPlayer.attach_subtitle_track_watcher(player)

    assert sorted(name for name, _ in mpv.observed) == [
        "osd-dimensions", "sid", "track-list"]
    assert player._subtitle_watcher is watcher

    app = QApplication.instance() or QApplication([])
    mpv.notify("sid")
    app.processEvents()

    assert calls == [1]


def test_mpv_initialisation_wires_the_watcher():
    """Gözlemci mpv kurulumunda, ayarlar geri yüklenmeden ÖNCE bağlanır."""
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.init_mpv_player)

    assert "attach_subtitle_track_watcher" in source
    assert (source.index("attach_subtitle_track_watcher")
            < source.index("restore_subtitle_settings"))


# --- Yaşam döngüsü ve olay fırtınası ---------------------------------

def test_detach_unobserves_each_property_with_the_exact_callback(bench):
    app, frame, mpv, watcher = bench()
    registered = list(mpv.observed)

    watcher.detach()

    assert mpv.unobserved == registered
    assert mpv.observed == []


def test_detach_is_idempotent(bench):
    app, frame, mpv, watcher = bench()

    watcher.detach()
    watcher.detach()

    assert len(mpv.unobserved) == len(SubtitleTrackWatcher.OBSERVED)


def test_callback_after_detach_is_a_noop(bench):
    app, frame, mpv, watcher = bench()
    calls = []
    watcher._on_changed = lambda: calls.append("sync")
    registered = list(mpv.observed)
    watcher.detach()

    for name, callback in registered:
        callback(name, {"h": 1440})
    app.processEvents()

    assert calls == []


def test_already_queued_callback_is_a_noop_after_detach(bench):
    app, frame, mpv, watcher = bench()
    calls = []
    watcher._on_changed = lambda: calls.append("sync")

    worker = threading.Thread(target=lambda: mpv.notify("sid"))
    worker.start()
    worker.join(5)
    watcher.detach()
    app.processEvents()

    assert calls == []


def test_an_osd_event_storm_coalesces_to_one_main_thread_sync(bench):
    app, frame, mpv, watcher = bench(codec="ass")
    calls = []
    original = frame.sync_subtitle_safe_band

    def record():
        calls.append(dict(mpv.osd_dimensions))
        return original()

    watcher._on_changed = record
    for height in range(800, 950):
        mpv.osd_dimensions = {"w": 1400, "h": height, "mt": 8, "mb": 8}
        mpv.notify("osd-dimensions")
    app.processEvents()

    assert calls == [{"w": 1400, "h": 949, "mt": 8, "mb": 8}]


def test_normal_fullscreen_normal_uses_each_final_geometry(bench):
    app, frame, mpv, watcher = bench(codec="ass")

    mpv.notify("sid")
    app.processEvents()
    normal_pos = mpv.written["sub_pos"]

    mpv.osd_dimensions = {"w": 2560, "h": 1440, "mt": 28, "mb": 28}
    mpv.notify("osd-dimensions")
    app.processEvents()
    fullscreen_pos = mpv.written["sub_pos"]

    mpv.osd_dimensions = {"w": 1400, "h": 772, "mt": 8, "mb": 8}
    mpv.notify("osd-dimensions")
    app.processEvents()

    assert fullscreen_pos > normal_pos
    assert mpv.written["sub_pos"] == normal_pos
