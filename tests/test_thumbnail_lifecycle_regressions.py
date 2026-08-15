"""Thumbnail worker ve servis yaşam döngüsü regresyonları.

Kanıtlanan sorun (gerçek dosya, gerçek libmpv):

- `audio="no"` seçeneğiyle açılan bazı dosyalarda mpv HİÇBİR stream seçmiyor
  (`end-file reason=error file_error='no audio or video data played'`,
  `track_list` boş, `duration=None`) ve worker `exit=2` ile çıkıyordu.
  Aynı dosya ses anahtarı verilmeden 6 track / 2 video / duration=7518.26 ile
  sorunsuz yükleniyor.
- Başarısız worker sonrası playlist satırı sonsuza kadar `loading` kalıyordu.

Testler DAVRANIŞSALDIR: sahte bir `mpv` modülü ile worker'ın gerçek karar
akışı ölçülür; kaynak metni kontrolü tek kanıt değildir.
"""
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


# =====================================================================
# Sahte libmpv
# =====================================================================

class FakeMPV:
    """Gerçek libmpv'nin worker için önemli davranışlarını taklit eder."""

    instances = []

    def __init__(self, **options):
        self.options = options
        self.commands = []
        self.terminated = 0
        self.pause = True
        # Gercek dosyada gorulen davranis: otomatik secim video VERMEZ;
        # `vid` acikca ayarlanana kadar cozulmus kare yoktur.
        self._auto_selects_video = options.pop("_auto_video", True)
        self.vid = options.get("vid", "auto")
        self._duration = options.pop("_duration", 12.0)
        self._tracks = options.pop("_tracks", None)
        self._time_pos = options.pop("_time_pos", 0.0)
        self._screenshot_writes = options.pop("_writes", True)
        FakeMPV.instances.append(self)

    # --- mpv özellikleri ---
    @property
    def duration(self):
        return self._duration

    @property
    def time_pos(self):
        return self._time_pos

    @property
    def track_list(self):
        if self._tracks is not None:
            return self._tracks
        return [{"type": "video", "id": 1}, {"type": "audio", "id": 1}]

    @property
    def _video_selected(self):
        if isinstance(self.vid, int):
            return True
        return self._auto_selects_video

    @property
    def width(self):
        if not self._video_selected:
            return None
        return 1920 if any(t.get("type") == "video"
                           for t in (self.track_list or [])) else None

    @property
    def dwidth(self):
        return self.width

    def play(self, path):
        self.commands.append(("play", path))

    def command(self, *args):
        self.commands.append(args)
        if args and args[0] == "seek":
            self._time_pos = 10.0
        if args and args[0] == "screenshot-to-file" and not self._video_selected:
            # Gercek libmpv: cozulmus kare yoksa komut HATA verir.
            raise SystemError("Error running mpv command")
        if args and args[0] == "screenshot-to-file" and self._screenshot_writes:
            with open(args[1], "wb") as handle:
                handle.write(b"\xff\xd8\xff" + b"0" * 64)

    def terminate(self):
        self.terminated += 1

    def wait_until_playing(self, timeout=None):
        return True


@pytest.fixture
def fake_mpv(monkeypatch):
    """`import mpv` çağrısını sahte modüle yönlendirir."""
    FakeMPV.instances = []
    module = SimpleNamespace(MPV=FakeMPV)

    def factory(**defaults):
        def build(**options):
            merged = dict(defaults)
            merged.update(options)
            return FakeMPV(**merged)

        module.MPV = build
        monkeypatch.setitem(sys.modules, "mpv", module)
        return FakeMPV

    monkeypatch.setitem(sys.modules, "mpv", module)
    return factory


def last_instance():
    assert FakeMPV.instances, "hic MPV olusturulmadi"
    return FakeMPV.instances[-1]


def seek_commands(player):
    return [c for c in player.commands if c and c[0] == "seek"]


def screenshot_commands(player):
    return [c for c in player.commands if c and c[0] == "screenshot-to-file"]


# =====================================================================
# 1. Worker karar akışı
# =====================================================================

def test_worker_does_not_disable_audio_track_selection(fake_mpv, tmp_path):
    """`audio="no"` bazi dosyalarda HIC stream sectirmiyor; kullanilmamali."""
    from app.thumbnail_worker import generate_thumbnail

    fake_mpv()
    generate_thumbnail("C:/video.mkv", str(tmp_path / "out.jpg"))

    options = last_instance().options
    assert options.get("audio") != "no", options
    # Ses yine de duyulmamali: cikis kapatilir.
    assert options.get("ao") in ("null", "no") or options.get("mute") in (
        "yes", True), options


def test_worker_uses_percent_seek_when_duration_is_known(fake_mpv, tmp_path):
    from app.thumbnail_worker import generate_thumbnail

    fake_mpv(_duration=600.0)
    generate_thumbnail("C:/video.mkv", str(tmp_path / "out.jpg"))

    seeks = seek_commands(last_instance())
    assert seeks, "hic seek yapilmadi"
    assert any("absolute-percent" in " ".join(map(str, seek))
               for seek in seeks), seeks


def test_worker_falls_back_to_absolute_seek_without_duration(fake_mpv,
                                                             tmp_path):
    """Duration yoksa yuzde seek ANLAMSIZ; sabit guvenli saniye kullanilir."""
    from app.thumbnail_worker import generate_thumbnail

    fake_mpv(_duration=None)
    code = generate_thumbnail("C:/video.mkv", str(tmp_path / "out.jpg"))

    seeks = seek_commands(last_instance())
    assert seeks, "duration yokken hic seek denenmedi"
    assert not any("absolute-percent" in " ".join(map(str, seek))
                   for seek in seeks), seeks
    assert any("absolute" in " ".join(map(str, seek)) for seek in seeks), seeks
    assert code == 0


def test_worker_produces_thumbnail_without_duration(fake_mpv, tmp_path):
    """Video track varsa duration olmasa da kare uretilebilmeli."""
    from app.thumbnail_worker import generate_thumbnail

    output = tmp_path / "out.jpg"
    fake_mpv(_duration=None)

    code = generate_thumbnail("C:/video.mkv", str(output))

    assert code == 0
    assert output.is_file() and output.stat().st_size > 0


def test_worker_reports_failure_when_no_video_track(fake_mpv, tmp_path):
    """Gercek video akisi yoksa basarisizlik RAPORLANIR (sessiz gecmez)."""
    from app.thumbnail_worker import generate_thumbnail

    output = tmp_path / "out.jpg"
    fake_mpv(_duration=None, _tracks=[{"type": "audio", "id": 1}])

    code = generate_thumbnail("C:/video.mkv", str(output), timeout_s=1.0)

    assert code != 0
    assert not output.exists()


def test_worker_moves_temporary_file_atomically(fake_mpv, tmp_path):
    from app.thumbnail_worker import generate_thumbnail

    output = tmp_path / "cache" / "out.jpg"
    fake_mpv()

    code = generate_thumbnail("C:/video.mkv", str(output))

    assert code == 0
    assert output.is_file()
    leftovers = [p for p in output.parent.iterdir() if p.suffix == ".tmp"
                 or ".tmp." in p.name]
    assert leftovers == []


def test_worker_leaves_no_temporary_file_on_failure(fake_mpv, tmp_path):
    from app.thumbnail_worker import generate_thumbnail

    output = tmp_path / "cache" / "out.jpg"
    fake_mpv(_writes=False)

    code = generate_thumbnail("C:/video.mkv", str(output), timeout_s=1.0)

    assert code != 0
    assert not output.exists()
    if output.parent.exists():
        assert [p.name for p in output.parent.iterdir()] == []


def test_worker_always_terminates_mpv(fake_mpv, tmp_path):
    from app.thumbnail_worker import generate_thumbnail

    fake_mpv(_writes=False)
    generate_thumbnail("C:/video.mkv", str(tmp_path / "out.jpg"),
                       timeout_s=1.0)

    assert last_instance().terminated == 1


# =====================================================================
# 2. ThumbnailService başarısızlık sözleşmesi
# =====================================================================

@pytest.fixture
def service(tmp_path):
    from PyQt6.QtWidgets import QApplication
    from app.thumbnail_service import ThumbnailService

    app = QApplication.instance() or QApplication([])
    created = ThumbnailService(cache_dir=str(tmp_path / "cache"))
    yield SimpleNamespace(service=created, app=app, tmp=tmp_path)
    created.close()
    app.processEvents()


def media_file(tmp_path, name="film.mkv"):
    path = tmp_path / name
    path.write_bytes(b"\x00" * 2048)
    return str(path)


def test_service_emits_failure_signal(service):
    """Worker sifir olmayan exit dondurdugunde SESSIZ kalinmaz."""
    failures = []
    service.service.thumbnail_failed.connect(
        lambda path: failures.append(path))
    path = media_file(service.tmp)

    service.service.request(path)
    service.service._finished(2, None)

    assert failures == [path]


def test_service_moves_to_the_next_queued_file_after_failure(service):
    first = media_file(service.tmp, "a.mkv")
    second = media_file(service.tmp, "b.mkv")
    started = []
    service.service._process = SimpleNamespace(
        state=lambda: 0, start=lambda program, args: started.append(args[-2]),
        kill=lambda: None, waitForFinished=lambda ms: True)

    service.service.request(first)
    service.service.request(second)
    service.service._finished(2, None)

    assert started[-1] == second


def test_failed_file_is_not_requeued_in_the_same_session(service):
    path = media_file(service.tmp)
    starts = []
    service.service._process = SimpleNamespace(
        state=lambda: 0, start=lambda program, args: starts.append(args[-2]),
        kill=lambda: None, waitForFinished=lambda ms: True)

    service.service.request(path)
    service.service._finished(2, None)
    service.service.request(path)
    service.service.request(path)

    assert starts.count(path) == 1


def test_successful_cache_is_reused_without_a_new_worker(service):
    from app.thumbnail_service import thumbnail_cache_path

    path = media_file(service.tmp)
    cached = thumbnail_cache_path(path, service.service.cache_dir)
    os.makedirs(os.path.dirname(cached), exist_ok=True)
    with open(cached, "wb") as handle:
        handle.write(b"\xff\xd8\xff" + b"0" * 32)
    starts = []
    service.service._process = SimpleNamespace(
        state=lambda: 0, start=lambda program, args: starts.append(args),
        kill=lambda: None, waitForFinished=lambda ms: True)

    result = service.service.request(path)

    assert result == cached
    assert starts == []


def test_close_stops_only_its_own_process_and_clears_the_queue(service):
    killed = []
    service.service._process = SimpleNamespace(
        state=lambda: 2, start=lambda program, args: None,
        kill=lambda: killed.append("kill"),
        waitForFinished=lambda ms: True)
    service.service._queue.append(("a", "b", "c"))

    service.service.close()

    assert killed == ["kill"]
    assert service.service._queue == []
    assert service.service.pending_paths == ()


# =====================================================================
# 3. PlaylistPanel: başarısız satır `loading` KALMAZ
# =====================================================================

@pytest.fixture
def panel_env(tmp_path):
    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])

    def factory(files):
        from app.playlist_panel import PlaylistPanel

        host = QWidget()
        host.resize(900, 600)
        player = SimpleNamespace(
            playlist=list(files), current_playlist_index=0,
            playlist_dock_host=host,
            play_from_playlist=lambda index: None,
            remove_from_playlist=lambda index: None,
            clear_playlist=lambda: None, add_to_playlist=lambda: None)
        video_frame = SimpleNamespace(main_window=player, host=host,
                                      width=lambda: 900,
                                      playlist_dock_target_width=lambda: 360)
        panel = PlaylistPanel(player, video_frame)
        panel.refresh()
        app.processEvents()
        return SimpleNamespace(panel=panel, player=player, app=app, host=host)

    yield factory
    app.processEvents()


def test_failed_row_leaves_the_loading_state(panel_env, tmp_path):
    """Basarisiz worker satiri SONSUZA KADAR `loading` birakmamali."""
    files = [media_file(tmp_path, "a.mkv"), media_file(tmp_path, "b.mkv")]
    env = panel_env(files)
    widget = env.panel.row_widget(0)
    widget.thumbnail_label.setProperty("thumbnailState", "loading")

    env.panel._thumbnail_failed(files[0])
    env.app.processEvents()

    state = env.panel.row_widget(0).thumbnail_label.property("thumbnailState")
    assert state in ("failed", "empty"), state
    assert state != "loading"


def test_failed_signal_does_not_touch_other_rows(panel_env, tmp_path):
    files = [media_file(tmp_path, "a.mkv"), media_file(tmp_path, "b.mkv")]
    env = panel_env(files)
    other = env.panel.row_widget(1)
    other.thumbnail_label.setProperty("thumbnailState", "ready")

    env.panel._thumbnail_failed(files[0])
    env.app.processEvents()

    assert env.panel.row_widget(1).thumbnail_label.property(
        "thumbnailState") == "ready"


def test_failed_row_shows_no_broken_pixmap(panel_env, tmp_path):
    files = [media_file(tmp_path, "a.mkv")]
    env = panel_env(files)

    env.panel._thumbnail_failed(files[0])
    env.app.processEvents()

    pixmap = env.panel.row_widget(0).thumbnail_label.pixmap()
    assert pixmap is None or pixmap.isNull()


def test_panel_connects_the_failure_signal(panel_env, tmp_path):
    """Panel servis basarisizligini DINLEMELI."""
    files = [media_file(tmp_path, "a.mkv")]
    env = panel_env(files)

    received = []
    env.panel._thumbnail_failed = lambda path: received.append(path)
    env.panel.thumbnail_service.thumbnail_failed.emit(files[0])
    env.app.processEvents()

    assert received == [files[0]]


def test_worker_selects_a_video_track_explicitly(fake_mpv, tmp_path):
    """Otomatik secim video vermeyen dosyalarda `vid` ACIKCA ayarlanmali.

    Gercek olcum: `vid=auto` iken `vid=False` kaliyor ve
    `screenshot-to-file` "Taking screenshot failed" ile dusuyordu;
    `vid=<ilk video track id>` ile ayni dosyadan 130 KB'lik kare uretildi.
    """
    from app.thumbnail_worker import generate_thumbnail

    output = tmp_path / "out.jpg"
    fake_mpv(_auto_video=False,
             _tracks=[{"type": "video", "id": 1, "codec": "hevc"},
                      {"type": "video", "id": 2, "codec": "mjpeg"},
                      {"type": "audio", "id": 1}])

    code = generate_thumbnail("C:/video.mkv", str(output))

    assert last_instance().vid == 1, last_instance().vid
    assert code == 0
    assert output.is_file() and output.stat().st_size > 0


def test_worker_waits_for_a_decoded_frame_before_screenshot(fake_mpv,
                                                            tmp_path):
    """Kare hazir degilken screenshot denenmemeli (hata uretir)."""
    from app.thumbnail_worker import generate_thumbnail

    output = tmp_path / "out.jpg"
    fake_mpv(_auto_video=False,
             _tracks=[{"type": "audio", "id": 1}])

    code = generate_thumbnail("C:/video.mkv", str(output), timeout_s=1.0)

    assert code != 0
    assert screenshot_commands(last_instance()) == []
    assert not output.exists()


# =====================================================================
# 4. Refresh sonrası durum sözleşmesi (BULUNAN GERÇEK AÇIK)
# =====================================================================

def test_failed_row_stays_failed_after_refresh(panel_env, tmp_path):
    """Ölçülen açık: `refresh()` sonrası satır tekrar `loading` oluyordu."""
    files = [media_file(tmp_path, "a.mkv"), media_file(tmp_path, "b.mkv")]
    env = panel_env(files)
    env.panel.thumbnail_service._finished_for_test = None
    env.panel.thumbnail_service.request(files[0])
    env.panel.thumbnail_service._finished(2, None)
    env.app.processEvents()
    assert env.panel.row_widget(0).thumbnail_label.property(
        "thumbnailState") in ("failed", "empty")

    env.panel.refresh()
    env.app.processEvents()

    state = env.panel.row_widget(0).thumbnail_label.property("thumbnailState")
    assert state == "failed", state


def test_failed_row_stays_failed_after_repeated_refresh(panel_env, tmp_path):
    files = [media_file(tmp_path, "a.mkv")]
    env = panel_env(files)
    env.panel.thumbnail_service.request(files[0])
    env.panel.thumbnail_service._finished(2, None)

    for _ in range(3):
        env.panel.refresh()
        env.app.processEvents()

    assert env.panel.row_widget(0).thumbnail_label.property(
        "thumbnailState") == "failed"


def test_refresh_does_not_restart_a_worker_for_failed_file(panel_env,
                                                           tmp_path):
    files = [media_file(tmp_path, "a.mkv")]
    env = panel_env(files)
    service = env.panel.thumbnail_service
    service.request(files[0])
    service._finished(2, None)
    starts = []
    service._process = SimpleNamespace(
        state=lambda: 0, start=lambda program, args: starts.append(args),
        kill=lambda: None, waitForFinished=lambda ms: True)

    env.panel.refresh()
    env.app.processEvents()

    assert starts == []


def test_failed_row_has_no_pixmap_after_refresh(panel_env, tmp_path):
    files = [media_file(tmp_path, "a.mkv")]
    env = panel_env(files)
    service = env.panel.thumbnail_service
    service.request(files[0])
    service._finished(2, None)

    env.panel.refresh()
    env.app.processEvents()

    pixmap = env.panel.row_widget(0).thumbnail_label.pixmap()
    assert pixmap is None or pixmap.isNull()


def test_other_rows_keep_their_state_after_refresh(panel_env, tmp_path):
    from app.thumbnail_service import thumbnail_cache_path

    files = [media_file(tmp_path, "a.mkv"), media_file(tmp_path, "b.mkv")]
    env = panel_env(files)
    service = env.panel.thumbnail_service
    service.request(files[0])
    service._finished(2, None)
    ready_cache = thumbnail_cache_path(files[1], service.cache_dir)
    os.makedirs(os.path.dirname(ready_cache), exist_ok=True)
    with open(ready_cache, "wb") as handle:
        handle.write(b"\xff\xd8\xff" + b"0" * 64)

    env.panel.refresh()
    env.app.processEvents()

    assert env.panel.row_widget(0).thumbnail_label.property(
        "thumbnailState") == "failed"
    assert env.panel.row_widget(1).thumbnail_label.property(
        "thumbnailState") != "failed"


def test_ready_cache_wins_over_a_recorded_failure(panel_env, tmp_path):
    """Cache sonradan gercekten olustuysa satir `ready` olabilmeli."""
    from app.thumbnail_service import thumbnail_cache_path

    files = [media_file(tmp_path, "a.mkv")]
    env = panel_env(files)
    service = env.panel.thumbnail_service
    service.request(files[0])
    service._finished(2, None)
    cache = thumbnail_cache_path(files[0], service.cache_dir)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "wb") as handle:
        handle.write(b"\xff\xd8\xff" + b"0" * 64)

    assert service.status(files[0]) == "ready"


def test_changed_file_is_retried_after_a_failure(tmp_path):
    """Ayni yoldaki dosya DEGISTIYSE eski basarisizlik sonsuza kadar
    yeni surumu engellememeli (cache kimligi degisir)."""
    from PyQt6.QtWidgets import QApplication
    from app.thumbnail_service import ThumbnailService

    app = QApplication.instance() or QApplication([])
    service = ThumbnailService(cache_dir=str(tmp_path / "cache"))
    try:
        path = media_file(tmp_path, "a.mkv")
        service.request(path)
        service._finished(2, None)
        assert service.status(path) == "failed"

        # Dosya degisti: boyut ve mtime farkli -> yeni kimlik.
        with open(path, "wb") as handle:
            handle.write(b"\x01" * 8192)
        os.utime(path, (0, 0))

        assert service.status(path) != "failed"
    finally:
        service.close()
        app.processEvents()


def test_service_status_contract(tmp_path):
    """`status()` dort durumu KESIN ayirir."""
    from PyQt6.QtWidgets import QApplication
    from app.thumbnail_service import ThumbnailService, thumbnail_cache_path

    app = QApplication.instance() or QApplication([])
    service = ThumbnailService(cache_dir=str(tmp_path / "cache"))
    try:
        assert service.status("https://ornek.test/x.mkv") == "empty"
        assert service.status(str(tmp_path / "yok.mkv")) == "empty"
        assert service.status(str(media_file(tmp_path, "not.txt"))) == "empty"

        pending = media_file(tmp_path, "p.mkv")
        service._process = SimpleNamespace(
            state=lambda: 0, start=lambda program, args: None,
            kill=lambda: None, waitForFinished=lambda ms: True)
        service.request(pending)
        assert service.status(pending) == "loading"

        service._finished(2, None)
        assert service.status(pending) == "failed"

        cache = thumbnail_cache_path(pending, service.cache_dir)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "wb") as handle:
            handle.write(b"\xff\xd8\xff" + b"0" * 64)
        assert service.status(pending) == "ready"
    finally:
        service.close()
        app.processEvents()
