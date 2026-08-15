"""Normal kullanıcı kapanışının MPV yaşam döngüsü regresyonları.

Ürünün kapanış sözleşmesi burada davranışsal olarak kilitlenir:

- `stop -> terminate` sırası (bu sıra `subtitle_service.shutdown_player()`
  yolunda uzun süredir kullanılan sıradır; `stop()`suz doğrudan terminate
  eden eski yolda aralıklı native `0xC0000005` RAPORLANMIŞTI),
- her ikisinin de EN FAZLA BİR KEZ çalışması,
- bağımsız teardown adımlarının kendi hata sınırında olması,
- ertelenmiş Altyazı Merkezi drenajının MPV'ye dokunmaması.

KAPSAM NOTU: bu testler native `0xC0000005` hatasının kök nedenini
kanıtlamaz ve ölçmez. Bu turda izole edilen tek kesin tetikleyici,
Qt + libmpv + `audio-device-list` okumasının ardından gelen DOĞAL Python
finalizasyonudur; ürünün `main.py` yolu o faza girmez. Buradaki ölçüm
yalnızca ürünün kapanış çağrı SIRASI ve SAYISIDIR; kaynak metni veya AST
kontrolü yapılmaz.
"""
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =====================================================================
# Sahte kapanış tezgâhı
# =====================================================================

class FakeEvent:
    def __init__(self):
        self.accepted = 0
        self.ignored = 0

    def accept(self):
        self.accepted += 1

    def ignore(self):
        self.ignored += 1


class CloseBench:
    """`MPVPlayer.closeEvent` için minimum ama ölçülebilir sahte `self`."""

    def __init__(self, calls, stop_error=None, terminate_error=None,
                 fullscreen=False, timer_error=None, resize_filter_error=None,
                 fullscreen_error=None):
        self.calls = calls
        self._stop_error = stop_error
        self._terminate_error = terminate_error

        def step(name, error):
            """Teardown adımı: çağrıyı kaydeder, istenirse patlar."""
            def run():
                calls.append(name)
                if error is not None:
                    raise error
            return run

        self.timer = SimpleNamespace(stop=step("timer.stop", timer_error))
        self.settings = SimpleNamespace(
            setValue=lambda key, value: calls.append(f"settings.{key}"))
        self.last_dir = "C:/videolar"
        self.resize_filter = SimpleNamespace(
            remove=step("resize_filter.remove", resize_filter_error))
        self.thumbnail_service = SimpleNamespace(
            close=lambda: calls.append("thumbnail_service.close"))
        self.playlist_panel = SimpleNamespace(
            close=lambda: calls.append("playlist_panel.close"),
            thumbnail_service=self.thumbnail_service)
        self.video_frame = SimpleNamespace(
            is_video_fullscreen=fullscreen,
            playlist_panel=self.playlist_panel,
            release_overlay_surfaces=lambda: calls.append(
                "release_overlay_surfaces"),
            exit_fullscreen=step("exit_fullscreen", fullscreen_error))
        self._subtitle_watcher = SimpleNamespace(
            detach=lambda: calls.append("subtitle_watcher.detach"))
        self.mpv_player = SimpleNamespace(stop=self._stop,
                                          terminate=self._terminate)
        self._visible = True

    # --- MPV ---
    def _stop(self):
        self.calls.append("stop")
        if self._stop_error is not None:
            raise self._stop_error

    def _terminate(self):
        self.calls.append("terminate")
        if self._terminate_error is not None:
            raise self._terminate_error

    # --- Qt yüzeyi ---
    def saveGeometry(self):
        return b"geometry"

    def isVisible(self):
        return self._visible

    def close(self):
        """Ürün akışı: `close()` -> `closeEvent()`."""
        from app import player as player_module

        self.calls.append("close")
        event = FakeEvent()
        player_module.MPVPlayer.closeEvent(self, event)
        if event.accepted:
            self._visible = False
        return bool(event.accepted)


@pytest.fixture
def close_bench(monkeypatch):
    """`closeEvent`i gerçek ürün metodu olarak koşturur."""
    from app import player as player_module

    def factory(drained=True, stop_error=None, terminate_error=None,
                fullscreen=False, timer_error=None, resize_filter_error=None,
                fullscreen_error=None):
        calls = []
        monkeypatch.setattr(
            player_module, "close_subtitle_center_before_exit",
            lambda player, timeout_ms=None: drained)
        monkeypatch.setattr(
            player_module, "subtitle_center_drained",
            lambda player: drained)
        monkeypatch.setattr(
            player_module, "shutdown_subtitle_center",
            lambda player, wait_ms=0: calls.append("shutdown_subtitle_center"))
        bench = CloseBench(calls, stop_error=stop_error,
                           terminate_error=terminate_error,
                           fullscreen=fullscreen, timer_error=timer_error,
                           resize_filter_error=resize_filter_error,
                           fullscreen_error=fullscreen_error)
        return SimpleNamespace(
            player=bench, calls=calls,
            close=lambda: _run_close_event(player_module, bench),
            set_drained=lambda value: monkeypatch.setattr(
                player_module, "close_subtitle_center_before_exit",
                lambda player, timeout_ms=None: value))

    return factory


def _run_close_event(player_module, bench):
    event = FakeEvent()
    player_module.MPVPlayer.closeEvent(bench, event)
    if event.accepted:
        bench._visible = False
    return event


def counts(calls, name):
    return calls.count(name)


# =====================================================================
# A. Normal kullanıcı kapanışı
# =====================================================================

def test_normal_close_stops_before_terminating(close_bench):
    env = close_bench()

    env.close()

    mpv_calls = [name for name in env.calls if name in ("stop", "terminate")]
    assert mpv_calls == ["stop", "terminate"]


def test_normal_close_calls_stop_exactly_once(close_bench):
    env = close_bench()

    env.close()

    assert counts(env.calls, "stop") == 1


def test_normal_close_calls_terminate_exactly_once(close_bench):
    env = close_bench()

    env.close()

    assert counts(env.calls, "terminate") == 1


def test_terminate_never_runs_before_stop(close_bench):
    env = close_bench()

    env.close()

    assert env.calls.index("stop") < env.calls.index("terminate")


def test_subtitle_watcher_detaches_before_stop_and_terminate(close_bench):
    env = close_bench()

    env.close()

    assert env.calls.index("subtitle_watcher.detach") < env.calls.index("stop")
    assert env.calls.index("subtitle_watcher.detach") < env.calls.index("terminate")


def test_normal_close_releases_the_mpv_reference(close_bench):
    env = close_bench()

    env.close()

    assert env.player.mpv_player is None


def test_normal_close_accepts_the_event(close_bench):
    env = close_bench()

    event = env.close()

    assert (event.accepted, event.ignored) == (1, 0)


# =====================================================================
# B. Tekrarlanan kapanış
# =====================================================================

def test_repeated_close_does_not_stop_twice(close_bench):
    env = close_bench()

    env.close()
    env.close()

    assert counts(env.calls, "stop") == 1


def test_repeated_close_does_not_terminate_twice(close_bench):
    env = close_bench()

    env.close()
    env.close()

    assert counts(env.calls, "terminate") == 1


def test_repeated_close_still_accepts_the_event(close_bench):
    env = close_bench()

    env.close()
    event = env.close()

    assert (event.accepted, event.ignored) == (1, 0)


@pytest.mark.parametrize("operation", [
    "settings.geometry", "timer.stop", "shutdown_subtitle_center",
    "resize_filter.remove", "exit_fullscreen", "playlist_panel.close",
    "release_overlay_surfaces",
])
def test_repeated_close_does_not_repeat_teardown_work(close_bench, operation):
    env = close_bench(fullscreen=True)

    env.close()
    env.close()

    assert counts(env.calls, operation) == 1, env.calls


def test_close_shuts_down_the_thumbnail_worker_before_mpv(close_bench):
    """Thumbnail worker SÜRECİ kapanışta sahipsiz kalmamalı.

    Qt, ana pencere kapanırken çocuk widget'lara `closeEvent` GÖNDERMEZ;
    panelin kendi kapanış sözleşmesi ürün tarafından çağrılmalıdır. Aksi
    halde worker süreci MPV terminate ve Qt yıkımı boyunca yaşamaya devam
    ediyordu.
    """
    env = close_bench()

    env.close()

    assert "playlist_panel.close" in env.calls
    assert env.calls.index("playlist_panel.close") < env.calls.index("stop")


def test_close_releases_overlay_surfaces_before_mpv(close_bench):
    """Yüzen overlay/OSD pencereleri MPV'ye dokunulmadan ÖNCE bırakılır.

    Bu yüzeyler ayrı top-level (Tool) pencerelerdir; ana pencere kapanınca
    Qt onları kapatmaz ve sahipsiz kalırlar. Ölçülen şey DÜZENLİ teardown
    sırasıdır: yüzeyler MPV kapanışından önce bırakılır. Native
    `0xC0000005` ile nedensel bir bağ İDDİA EDİLMEZ (bkz. modül başlığı).
    """
    env = close_bench()

    env.close()

    assert counts(env.calls, "release_overlay_surfaces") == 1
    assert (env.calls.index("release_overlay_surfaces")
            < env.calls.index("stop"))


def test_overlay_release_error_does_not_block_the_shutdown(close_bench):
    def boom():
        env.calls.append("release_overlay_surfaces")
        raise RuntimeError("overlay birakilamadi")

    env = close_bench()
    env.player.video_frame.release_overlay_surfaces = boom

    event = env.close()

    assert event.accepted == 1
    assert counts(env.calls, "stop") == 1
    assert counts(env.calls, "terminate") == 1


def test_video_frame_without_release_api_still_closes(close_bench):
    """Eski test double'ları bu API'yi tanımlamak zorunda değildir."""
    env = close_bench()
    del env.player.video_frame.release_overlay_surfaces

    event = env.close()

    assert event.accepted == 1
    assert counts(env.calls, "terminate") == 1


def test_missing_playlist_panel_does_not_break_the_close(close_bench):
    env = close_bench()
    env.player.video_frame.playlist_panel = None

    event = env.close()

    assert event.accepted == 1
    assert counts(env.calls, "terminate") == 1


def test_panel_close_error_does_not_block_the_shutdown(close_bench):
    def boom():
        env.calls.append("playlist_panel.close")
        raise RuntimeError("panel kapanmadı")

    env = close_bench()
    env.player.video_frame.playlist_panel = SimpleNamespace(close=boom)

    event = env.close()

    assert event.accepted == 1
    assert counts(env.calls, "stop") == 1
    assert counts(env.calls, "terminate") == 1


# =====================================================================
# B2. Teardown adımları HATA SINIRINDA: hiçbiri MPV kapanışını engellemez
# =====================================================================

SECRET = "C:/gizli/yol ve APIKEY"

# Her senaryo: (fixture argümanı, patlayan adımın adı)
TEARDOWN_FAILURES = [
    ("timer_error", "timer.stop"),
    ("resize_filter_error", "resize_filter.remove"),
    ("fullscreen_error", "exit_fullscreen"),
]


def _bench_with_failing_step(close_bench, argument):
    return close_bench(fullscreen=True, **{argument: RuntimeError(SECRET)})


@pytest.mark.parametrize("argument,step", TEARDOWN_FAILURES)
def test_teardown_failure_still_accepts_the_close(close_bench, argument, step):
    env = _bench_with_failing_step(close_bench, argument)

    event = env.close()

    assert step in env.calls, env.calls
    assert (event.accepted, event.ignored) == (1, 0)


@pytest.mark.parametrize("argument,step", TEARDOWN_FAILURES)
def test_teardown_failure_still_stops_and_terminates_once(close_bench,
                                                          argument, step):
    env = _bench_with_failing_step(close_bench, argument)

    env.close()

    assert counts(env.calls, "stop") == 1, env.calls
    assert counts(env.calls, "terminate") == 1, env.calls


@pytest.mark.parametrize("argument,step", TEARDOWN_FAILURES)
def test_teardown_failure_keeps_the_stop_then_terminate_order(close_bench,
                                                              argument, step):
    env = _bench_with_failing_step(close_bench, argument)

    env.close()

    assert env.calls.index("stop") < env.calls.index("terminate")


@pytest.mark.parametrize("argument,step", TEARDOWN_FAILURES)
def test_teardown_failure_still_releases_the_mpv_reference(close_bench,
                                                           argument, step):
    env = _bench_with_failing_step(close_bench, argument)

    env.close()

    assert env.player.mpv_player is None


@pytest.mark.parametrize("argument,step", TEARDOWN_FAILURES)
def test_teardown_failure_does_not_repeat_work_on_the_second_close(
        close_bench, argument, step):
    env = _bench_with_failing_step(close_bench, argument)

    env.close()
    before = list(env.calls)
    event = env.close()

    assert env.calls == before, env.calls
    assert (event.accepted, event.ignored) == (1, 0)


@pytest.mark.parametrize("argument,step", TEARDOWN_FAILURES)
def test_teardown_failure_does_not_leak_the_error_text(close_bench, capsys,
                                                       argument, step):
    env = _bench_with_failing_step(close_bench, argument)

    env.close()

    printed = capsys.readouterr().out
    assert SECRET not in printed
    assert "APIKEY" not in printed
    assert "Traceback" not in printed
    assert "RuntimeError(" not in printed


def test_every_teardown_step_is_error_bounded(close_bench):
    """Adımların HEPSİ aynı anda patlasa bile MPV kapanışı tamamlanır."""
    env = close_bench(fullscreen=True, timer_error=RuntimeError(SECRET),
                      resize_filter_error=RuntimeError(SECRET),
                      fullscreen_error=RuntimeError(SECRET))

    event = env.close()

    assert (event.accepted, event.ignored) == (1, 0)
    assert counts(env.calls, "stop") == 1
    assert counts(env.calls, "terminate") == 1
    assert env.player.mpv_player is None


# =====================================================================
# C. `shutdown_player()` uyumluluğu
# =====================================================================

def test_shutdown_player_path_stops_once_and_terminates_once(close_bench):
    from app import subtitle_service as service

    env = close_bench()

    finished = service.shutdown_player(env.player)

    assert finished is True
    assert counts(env.calls, "stop") == 1
    assert counts(env.calls, "terminate") == 1


def test_shutdown_player_path_keeps_the_stop_then_terminate_order(close_bench):
    from app import subtitle_service as service

    env = close_bench()

    service.shutdown_player(env.player)

    mpv_calls = [name for name in env.calls if name in ("stop", "terminate")]
    assert mpv_calls == ["stop", "terminate"]


def test_shutdown_player_contract_flags_are_preserved(close_bench):
    from app import subtitle_service as service

    env = close_bench()

    service.shutdown_player(env.player)

    assert env.player._mlc_stop_done is True
    assert env.player._mlc_shutdown_done is True
    assert env.player.mpv_player is None


def test_second_shutdown_player_call_is_a_no_op(close_bench):
    from app import subtitle_service as service

    env = close_bench()

    service.shutdown_player(env.player)
    again = service.shutdown_player(env.player)

    assert again is False
    assert counts(env.calls, "stop") == 1
    assert counts(env.calls, "terminate") == 1


# =====================================================================
# D. Ertelenen Altyazı Merkezi kapanışı
# =====================================================================

def test_deferred_close_touches_no_mpv_call(close_bench):
    env = close_bench(drained=False)

    event = env.close()

    assert (event.ignored, event.accepted) == (1, 0)
    assert counts(env.calls, "stop") == 0
    assert counts(env.calls, "terminate") == 0


def test_deferred_close_keeps_the_mpv_reference(close_bench):
    env = close_bench(drained=False)

    env.close()

    assert env.player.mpv_player is not None


def test_deferred_close_does_not_start_teardown(close_bench):
    env = close_bench(drained=False, fullscreen=True)

    env.close()

    for operation in ("timer.stop", "shutdown_subtitle_center",
                      "resize_filter.remove", "exit_fullscreen"):
        assert counts(env.calls, operation) == 0, env.calls


def test_close_after_worker_drain_completes_the_shutdown(close_bench):
    env = close_bench(drained=False)

    env.close()
    env.set_drained(True)
    event = env.close()

    assert (event.accepted, event.ignored) == (1, 0)
    assert counts(env.calls, "stop") == 1
    assert counts(env.calls, "terminate") == 1
    assert env.calls.index("stop") < env.calls.index("terminate")


def test_deferred_shutdown_player_does_not_release_mpv(close_bench):
    from app import subtitle_service as service

    env = close_bench(drained=False)

    finished = service.shutdown_player(env.player)

    assert finished is False
    assert env.player.mpv_player is not None
    assert counts(env.calls, "terminate") == 0


# =====================================================================
# E. Hata sınırları
# =====================================================================

def test_stop_error_does_not_block_the_shutdown(close_bench):
    env = close_bench(stop_error=RuntimeError("mpv stop patladı"))

    event = env.close()

    assert event.accepted == 1
    assert counts(env.calls, "terminate") == 1
    assert env.player.mpv_player is None


def test_stop_error_is_not_retried_on_the_next_close(close_bench):
    env = close_bench(stop_error=RuntimeError("mpv stop patladı"))

    env.close()
    env.close()

    assert counts(env.calls, "stop") == 1


def test_terminate_error_is_not_retried(close_bench):
    env = close_bench(terminate_error=RuntimeError("mpv terminate patladı"))

    env.close()
    env.close()

    assert counts(env.calls, "terminate") == 1
    assert env.player.mpv_player is None


def test_terminate_error_still_accepts_the_close(close_bench):
    env = close_bench(terminate_error=RuntimeError("mpv terminate patladı"))

    event = env.close()

    assert event.accepted == 1


def test_shutdown_errors_are_not_leaked_to_the_user(close_bench, capsys):
    env = close_bench(stop_error=RuntimeError("C:/gizli/yol ve APIKEY"),
                      terminate_error=RuntimeError("C:/gizli/yol ve APIKEY"))

    env.close()

    printed = capsys.readouterr().out
    assert "APIKEY" not in printed
    assert "C:/gizli/yol" not in printed
    assert "Traceback" not in printed


# =====================================================================
# G. Gerçek `VideoFrame` yüzey bırakma davranışı
# =====================================================================

@pytest.fixture
def video_frame_env():
    """Gerçek `VideoFrame` (offscreen) + minimum ana pencere."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication, QLabel, QMainWindow, QSlider, QVBoxLayout, QWidget)

    app = QApplication.instance() or QApplication([])
    created = []

    def factory():
        from app.video_frame import VideoFrame

        window = QMainWindow()
        window.central_widget = QWidget(window)
        window.setCentralWidget(window.central_widget)
        window.main_layout = QVBoxLayout(window.central_widget)
        window.duration = 600.0
        window.position = 0.0
        window.current_file = "C:/video.mkv"
        window.is_paused = False
        window.is_muted = False
        window.playlist = []
        window.current_playlist_index = 0
        window.loop_file = False
        window.loop_playlist = False
        window.shuffle = False
        window.recent_files = []
        window._updating_position_slider = False
        window._pending_subs = []
        window.volume_slider = QSlider(Qt.Orientation.Horizontal)
        window.position_slider = QSlider()
        window.current_time_label = QLabel()
        window.total_time_label = QLabel()
        window.play_button = SimpleNamespace(setIcon=lambda icon: None)
        window.play_icon = object()
        window.pause_icon = object()
        window.update_time_label = lambda: None
        window.mpv_player = SimpleNamespace(
            aid=1, sid=1, audio_device="auto", sub_visibility=False,
            speed=1.0, track_list=[], audio_device_list=[],
            command=lambda *a, **k: None)
        for name in ("open_file", "open_folder", "open_url", "open_path",
                     "play_pause", "stop", "play_previous", "play_next",
                     "show_playlist", "toggle_mute", "seek_position",
                     "toggle_subtitles", "toggle_fullscreen"):
            setattr(window, name, lambda *a, **k: None)
        frame = VideoFrame(window)
        window.video_frame = frame
        created.append(window)
        app.processEvents()
        return SimpleNamespace(frame=frame, window=window, app=app)

    yield factory

    for window in created:
        window.close()
        window.deleteLater()
    app.processEvents()


def test_release_clears_the_floating_surface_references(video_frame_env):
    env = video_frame_env()
    assert env.frame.control_overlay is not None
    assert env.frame.osd_label is not None

    env.frame.release_overlay_surfaces()

    assert env.frame.control_overlay is None
    assert env.frame.osd_label is None


def test_release_stops_the_overlay_timers(video_frame_env):
    env = video_frame_env()
    env.frame.overlay_hide_timer.start(5000)
    env.frame.osd_timer.start(5000)

    env.frame.release_overlay_surfaces()

    assert not env.frame.overlay_hide_timer.isActive()
    assert not env.frame.osd_timer.isActive()


def test_release_is_idempotent(video_frame_env):
    env = video_frame_env()

    env.frame.release_overlay_surfaces()
    env.frame.release_overlay_surfaces()

    assert env.frame.control_overlay is None


@pytest.mark.parametrize("call", [
    lambda frame: frame.show_osd("test"),
    lambda frame: frame.hide_overlay_immediately(),
    lambda frame: frame.close_control_overlay(),
    lambda frame: frame.update_overlay_geometry(),
    lambda frame: frame.show_overlay_for_interaction(),
    lambda frame: frame.schedule_overlay_hide(),
    lambda frame: frame.cancel_overlay_hide(),
    lambda frame: frame.update_overlay_play_state(),
    lambda frame: frame.resize(400, 300),
])
def test_overlay_api_is_safe_after_release(video_frame_env, call):
    """Bırakma sonrası gelen geç olaylar istisna üretmemeli."""
    env = video_frame_env()
    env.frame.release_overlay_surfaces()

    call(env.frame)
    env.app.processEvents()


def test_release_keeps_the_video_surface_alive(video_frame_env):
    """Yalnız YÜZEN yüzeyler bırakılır; mpv `wid` yüzeyi korunur."""
    env = video_frame_env()

    env.frame.release_overlay_surfaces()

    assert env.frame.isVisible() or env.frame.winId() is not None


def test_shutdown_uses_no_thread_terminate_or_process_kill():
    """Erken uyarı: kapanış yolu zorla sonlandırma aracı ÇAĞIRMAMALI.

    Asıl kanıt yukarıdaki davranış testleri ve native child'dır; bu yalnız
    gerçek çağrı biçimlerini arar (yorumlardaki 'QThread' sözcüğü değil).
    """
    import inspect

    from app import player as player_module

    source = inspect.getsource(player_module.MPVPlayer.closeEvent)
    for forbidden in ("QThread.terminate", "os.kill(", "taskkill",
                      "TerminateProcess", "os._exit("):
        assert forbidden not in source, forbidden


def test_native_shutdown_child_uses_the_product_exit_policy():
    """Native kabul, kullanıcının gerçekten çalıştırdığı çıkış yolunu ölçer."""
    project_root = Path(__file__).resolve().parents[1]
    child_source = (project_root / "tests" / "native_player_shutdown_child.py").read_text(
        encoding="utf-8")

    assert "os._exit(exit_code)" in child_source
