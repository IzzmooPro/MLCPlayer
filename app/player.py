import os
import sys
import time
import mpv
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QMessageBox, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, QSettings, QObject, QEventLoop

from app.config import cinematic_ui_enabled, APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT, APP_STYLE, DEFAULT_VOLUME, MAX_VOLUME, MPV_CONFIG, MEDIA_EXTENSIONS, SUBTITLE_EXTENSIONS, SUBTITLE_DEFAULTS
from app.settings_store import user_settings
from app.video_frame import SubtitleTrackWatcher, VideoFrame
from app.title_bar import (RESIZE_MARGIN, FramelessResizeFilter,
                           TitleBar)
from app.ui_components import setup_controls
from app.menu_actions import setup_menu, setup_video_adjustments, show_subtitle_settings, show_log_management, refresh_audio_tracks, refresh_audio_devices, refresh_subtitle_tracks, refresh_chapters, select_chapter, select_audio_track, select_audio_device, show_shortcuts, show_about, update_recent_menu, show_media_info, refresh_media_info, close_media_info
from app.errors import show_user_error, log, safe_console
from app.subtitle_style import (BACKGROUND_BOX, BACKGROUND_BOX_SHADOW_OFFSET,
                                border_style_for, normalise_subtitle_numeric,
                                migrate_settings as migrate_subtitle_style_settings)
from app.local_subtitle import activate_local_subtitle, suppress_local_subtitle
from app.app_icon import apply_window_icon
from app.runtime_binaries import internet_video_ready, ytdl_script_opt
from main import get_bin_dir
from app.subtitle_service import (SubtitleSession, TRACK_WAIT_ATTEMPTS,
                                  TRACK_WAIT_INTERVAL_S)
from app.subtitle_center_composition import (
    close_subtitle_center_before_exit, open_subtitle_center,
    shutdown_subtitle_center, subtitle_center_drained)
from app.media_controls import (clear_url_loading, is_remote_media_url,
    safe_media_host, update_url_loading,
    toggle_mute, open_file, open_folder, open_url, open_path, open_recent, open_subtitle, select_subtitle_language, toggle_subtitles,
    seek_position, seek_relative, seek_chapter, play_pause, stop, set_volume, change_volume, add_to_playlist, show_playlist,
    play_from_playlist, remove_from_playlist, clear_playlist, take_screenshot, play_next,
    play_previous, goto_time, set_playback_speed, save_playlist, load_playlist,
    append_media_paths, media_suffixes
)

ESCAPE_WINDOW_WIDTH = 960
ESCAPE_WINDOW_HEIGHT = 600

# Sinematik içerik pencere kenarlarına sıfır boşlukla oturur. Görünür marj
# YOKTUR; kenar resize toleransı RESIZE_MARGIN ile ayrıca sağlanır.
CINEMATIC_CONTENT_MARGINS = (0, 0, 0, 0)


# Son acilanlar kayit siniri; bellek ve kalici liste AYNI siniri kullanir.
RECENT_FILE_LIMIT = 10


def build_ytdl_config(bin_dir):
    """MPV'ye verilecek ytdl karari. SISTEM FALLBACK YOKTUR.

    Site cikarimi YALNIZ paketli `yt-dlp.exe` VE `deno.exe` birlikte
    varsa acilir; bu durumda mpv'ye paketteki TAM yol verilir. Herhangi
    biri eksikse `ytdl=False` yazilir, boylece mpv varsayilan adlarla
    sistem PATH'inde arama YAPAMAZ.

    NOT: `ytdl=False` MPV'nin KENDI ag oynatmasini kapatmaz; dogrudan
    HTTP/HLS baglantilari calismaya devam eder.
    """
    if not internet_video_ready(bin_dir):
        return {'ytdl': False}
    option = ytdl_script_opt(bin_dir)
    if not option:
        # FAIL-CLOSED: exact yol uretilemediyse `ytdl` ACILMAZ. Aksi halde
        # mpv varsayilan adlarla sistem PATH aramasina dusebilirdi.
        return {'ytdl': False}
    return {'ytdl': True, 'script_opts': option}


class MPVPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, WINDOW_WIDTH, WINDOW_HEIGHT)
        # Ana pencere ORTAK uygulama ikonunu kullanir; standart Qt/DVD
        # ikonu HICBIR kosulda atanmaz.
        apply_window_icon(self)

        # Pencere davranışı ayarlarını ekle
        self.setMinimumSize(400, 300)  # Minimum pencere boyutu
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Yeniden boyutlandırmaya izin ver

        # Sinematik arayüz ürünün TEK arayüzüdür; klasik kabuk hiçbir env,
        # bayrak veya test yoluyla görünür pencere olarak açılmaz.
        # NOT: Frameless bayrağı, herhangi bir native pencere oluşturulmadan
        # ÖNCE ayarlanmalıdır. Aksi halde Qt show() sırasında top-level
        # pencereyi yeniden yaratır, mpv'nin wid child penceresi geçersizleşir
        # ve video başlık çubuğunun üstünü kaplar.
        self.cinematic_ui_enabled = cinematic_ui_enabled()
        # Geriye dönük iç takma ad (kod tabanında yaygın olarak kullanılıyor).
        self.preview_mode = self.cinematic_ui_enabled
        window_flags = self.windowFlags() | Qt.WindowType.Window
        if self.cinematic_ui_enabled:
            window_flags |= Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(window_flags)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Değişkenleri başlat
        self.duration = 0
        self.position = 0
        self.is_paused = True
        self.current_file = ""
        self.last_volume = DEFAULT_VOLUME
        self.is_muted = False
        self.playlist = []
        self.current_playlist_index = -1
        self.speed_actions = {}
        # Konum slider'ı programatik olarak güncellenirken seek'leri bastırmak için bayrak
        self._updating_position_slider = False
        # core-idle: dosya sonuna ulaşma takibi (END_FILE bu mpv build'inde wid ile gelmiyor)
        self._core_idle = False
        # Dosya yükleme takibi: duration uzun süre 0 kalırsa açma hatası göster
        self._load_started_at = 0
        # Ses kanalı menüsünün hangi dosya için doldurulduğunu takip eder
        self._audio_menu_file = ""
        self._chapter_menu_file = ""
        # Medya ile birlikte bırakılan ama henüz yüklenmemiş dosyaya eklenemeyen altyazılar
        self._pending_subs = []
        # Sürükle-bırak altyazısı Altyazı Merkezi ile AYNI yaşam döngüsünü
        # kullanır; ikinci bir altyazı akışı yoktur. Oturum ilk bırakmada
        # oluşturulur (bkz. `_activate_dropped_subtitle`).
        self._drop_subtitle_session = None
        # Yerel SRT otomatik etkinleştirmesi medya başına TEK ATIMDIR;
        # durum ve seçilen hedef önbelleklenir (bkz. `app/local_subtitle.py`).
        self._auto_local_subtitle_file = None
        self._auto_local_subtitle_state = None
        self._auto_local_subtitle_target = None
        # Medya Bilgisi TEK ve modeless penceredir; sahiplik burada durur
        # (bkz. `app/menu_actions.py::show_media_info`). Yeni timer yoktur.
        # URL yükleme durumu YEREL `_load_started_at` akışından AYRIDIR.
        self._url_loading_active = False
        self._url_loading_started_at = 0.0
        self._media_info_dialog = None
        self._media_info_refresh_key = None
        # Oynatma başlayınca başlık çubuğunu bir kez öne alma bayrağı
        self._title_bar_raise_pending = False
        # Döngü ve karışık mod bayrakları
        self.loop_file = False
        self.loop_playlist = False
        self.shuffle = False
        # Ayarlar kalıcılığı (pencere, ses, son dosyalar)
        self.settings = user_settings()
        self.restore_recent_files()
        stored_dir = self.settings.value("last_dir", "") or ""
        self.last_dir = stored_dir if isinstance(stored_dir, str) and os.path.isdir(stored_dir) else ""

        # Menü çubuğu
        setup_menu(self)

        # Modern özel başlık çubuğu klasik QMenuBar'ın yerini alır. Klasik
        # menü aksiyonları uyumluluk katmanı olarak yaşamaya devam eder ve
        # üç nokta menüsünden erişilir; ayrı bir klasik kabuk açılmaz.
        self.title_bar = None
        self.resize_filter = None
        if self.cinematic_ui_enabled:
            self.menuBar().hide()
            self.title_bar = TitleBar(self)
            self.main_layout.addWidget(self.title_bar)
            # NOT: mpv native yüzeyi normal child widget'ların üstünü
            # kapatabiliyor (projedeki OSD/overlay ile aynı sorun). Başlık
            # çubuğuna kendi native penceresini verip z-order'da öne alıyoruz.
            self.title_bar.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
            self.title_bar.winId()
            # NOT: Burada eskiden RESIZE_MARGIN görünür iç boşluk olarak
            # uygulanıyordu; sağda, solda ve altta ince koyu bir çerçeve
            # oluşuyordu. RESIZE_MARGIN bir HIT-TEST toleransıdır ve yalnızca
            # app/title_bar.py::resize_edges_at + FramelessResizeFilter
            # yolunda kullanılır. Kenar resize'ı ana pencere dikdörtgeni
            # üzerinden hesaplandığı için görünür boşluğa ihtiyaç yoktur.
            self.main_layout.setContentsMargins(*CINEMATIC_CONTENT_MARGINS)
            self.setMouseTracking(True)

        # Video ve sinematik playlist aynı içerik satırında yaşar. Playlist
        # top-level native panel olarak çizilir; sağdaki host alanı videonun
        # altında kalmasını önlemek için gerçek yer ayırır.
        self.media_container = QWidget(self.central_widget)
        self.media_container.setObjectName("mediaContainer")
        self.media_layout = QHBoxLayout(self.media_container)
        self.media_layout.setContentsMargins(0, 0, 0, 0)
        self.media_layout.setSpacing(0)
        self.playlist_dock_host = QWidget(self.media_container)
        self.playlist_dock_host.setObjectName("playlistDockHost")
        self.playlist_dock_host.setFixedWidth(0)
        self.playlist_dock_host.hide()

        # Video çerçevesi
        self.video_frame = VideoFrame(self)
        # NOT: Bu minimum, ana pencerenin 400x300 minimumundan küçük olmalıdır;
        # aksi halde menü çubuğu ve klasik kontrol paneli eklendiğinde video
        # alanı pencerenin dışına taşar.
        self.video_frame.setMinimumSize(200, 120)
        self.video_frame.setStyleSheet("background-color: #000000;")
        self.media_layout.addWidget(self.video_frame, 1)
        self.media_layout.addWidget(self.playlist_dock_host, 0)
        self.main_layout.addWidget(self.media_container, 1)

        # MPV yapılandırmasını optimize et
        try:
            self.init_mpv_player()
            # NOT: Ses çıkışı taraması `init_mpv_player()` SONUNDA bir kez
            # yapılır; burada TEKRAR çağrılmaz (çift tarama olurdu).
            safe_console("MPV oynatıcı başarıyla yapılandırıldı.")
        except Exception as e:
            safe_console(f"MPV yapılandırma hatası: {e}")
            show_user_error(self, "Oynatıcı Başlatılamadı",
                            "Oynatıcı başlatılamadı. Programın bin klasörünü "
                            "kontrol edip tekrar deneyin.",
                            exc=e)
            sys.exit(1)

        # Kontrol paneli
        setup_controls(self)

        # Kaydedilmiş pencere boyutu/konumu ve ses seviyesini geri yükle
        saved_geometry = self.settings.value("geometry")
        if saved_geometry:
            self.restoreGeometry(saved_geometry)
        saved_volume = self.settings.value("volume")
        try:
            volume = int(float(saved_volume)) if saved_volume is not None else DEFAULT_VOLUME
        except (TypeError, ValueError):
            volume = DEFAULT_VOLUME
        self.volume_slider.setValue(max(0, min(MAX_VOLUME, volume)))

        # Son açılanlar menüsünü doldur
        update_recent_menu(self)

        # Sürükle-bırak desteği
        self.setAcceptDrops(True)

        # Zamanlayıcı
        self.timer = QTimer(self)
        self.timer.setInterval(100)  # More responsive updates (100ms)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

        # Stil
        self.setStyleSheet(APP_STYLE)

        # mpv native yüzeyi kurulduktan SONRA başlık çubuğunu z-order'da
        # tekrar öne al.
        self.ensure_title_bar_on_top()

        # Resize filtresi ancak pencere tamamen kurulduktan sonra takılır.
        if self.cinematic_ui_enabled and self.title_bar is not None:
            self.resize_filter = FramelessResizeFilter(self, self.title_bar)
            self.resize_filter.install()

        self._ui_ready = True

    def clear_title_bar_raise_pending(self):
        """Yeni bir medya yükleme girişimi başladığında eski işareti siler.

        Önceki medyanın pending'i (duration henüz pozitif olmadığı için)
        tüketilmemiş olabilir; yeni deneme başarısız olursa bu bayrak açık
        kalmamalıdır.
        """
        self._title_bar_raise_pending = False

    def mark_title_bar_raise_pending(self):
        """Oynatma başlangıcı için tek seferlik z-order yenilemesi işaretler.

        Gerçek mpv_player.play() çağrısı BAŞARILI olduktan hemen sonra
        çağrılır (open_path, open_url, play_from_playlist). Oynatma hata
        verirse bayrak açılmaz, dolayısıyla stale pending oluşmaz.
        """
        if not getattr(self, "cinematic_ui_enabled", False):
            return
        if getattr(self, "title_bar", None) is None:
            return
        self._title_bar_raise_pending = True

    def ensure_title_bar_on_top(self):
        """Başlık çubuğunu güvenli biçimde göster ve z-order'da öne al.

        mpv native yüzeyi normal child widget'ların üstünü kapatabildiği için
        yaşam döngüsünün belirli noktalarında çağrılır: kurulum sonrası,
        pencere durum/aktivasyon olaylarında, fullscreen çıkışında ve oynatma
        başladığında. Sürekli polling yapılmaz; update_ui() içinden yalnızca
        _title_bar_raise_pending bayrağı açıkken, dosya başına bir kez
        çağrılır ve bayrak hemen temizlenir.
        """
        if not getattr(self, "cinematic_ui_enabled", False):
            return
        title_bar = getattr(self, "title_bar", None)
        if title_bar is None:
            return
        if self.video_frame.is_video_fullscreen:
            return
        if not title_bar.isVisible():
            title_bar.show()
        title_bar.raise_()

    def init_mpv_player(self):
        config = MPV_CONFIG.copy()
        config['wid'] = str(int(self.video_frame.winId()))
        config['log_handler'] = self.log_handler
        # Klavye komutlarını Qt yönetsin. mpv'nin varsayılan Up/Down bağları
        # açık kalırsa tuşlar ses yerine seek işlemi yapar.
        config['input_default_bindings'] = False
        config['input_vo_keyboard'] = False
        bin_dir = get_bin_dir()
        ytdl_config = build_ytdl_config(bin_dir)
        config.update(ytdl_config)
        # Guvenli bayrak: URL hata yolunda hangi mesajin gosterilecegini
        # belirler. Yol veya istisna TASIMAZ.
        self.internet_video_ready = bool(ytdl_config.get('ytdl'))
        self.mpv_player = mpv.MPV(**config)
        self.mpv_player.deinterlace = 'no'
        self.mpv_player.untimed = False

        self.mpv_player.observe_property('time-pos', self.handle_time_pos_change)
        self.mpv_player.observe_property('duration', self.handle_duration_change)
        self.mpv_player.observe_property('core-idle', self.handle_core_idle_change)
        # Altyazı parçası HANGİ yoldan değişirse değişsin (menü, dış
        # dosya, bekleyen altyazı, Altyazı Merkezi indirmesi) güvenli
        # bant otomatik uygulanır. Tek merkez; `sub_add` çağrılarının
        # yanına dağınık yama YOKTUR.
        self.attach_subtitle_track_watcher()
        self.restore_subtitle_settings()
        # Ses çıkışları açılışta TAM BİR KEZ taranır (MPV hazır olduktan
        # sonra). Menü her açıldığında yeniden taranmaz; sonradan takılan
        # aygıt için yeniden başlatma gerekir.
        self.refresh_audio_devices()

    def attach_subtitle_track_watcher(self):
        """Altyazı parçası değişimini güvenli bant senkronuna bağlar."""
        previous = self.__dict__.get("_subtitle_watcher")
        if previous is not None:
            previous.detach()
        # Normal üründe watcher pencerenin QObject çocuğudur. Bazı saf
        # birim testleri `MPVPlayer.__new__()` ile SIP nesnesini kurup Qt
        # üst sınıfını başlatmaz; `isinstance(QObject)` yine True olsa da
        # parent olarak vermek RuntimeError üretir. `thread()` güvenli bir
        # başlatılmışlık yoklamasıdır.
        watcher_parent = None
        if isinstance(self, QObject):
            try:
                self.thread()
                watcher_parent = self
            except RuntimeError:
                pass
        watcher = SubtitleTrackWatcher(
            self.video_frame.sync_subtitle_safe_band,
            parent=watcher_parent)
        watcher.attach(self.mpv_player)
        # Referans TUTULUR: sahipsiz kalırsa Python tarafında toplanır ve
        # gözlem sessizce ölür.
        self._subtitle_watcher = watcher
        return watcher

    def restore_subtitle_settings(self):
        """Kaydedilmiş altyazı görünüm ayarlarını yeni mpv oturumuna uygular."""
        # Eski `#RRGGBBAA` kayıtları TAM BİR KEZ canonical `#AARRGGBB`
        # biçimine çevrilir (bkz. app/subtitle_style.py).
        try:
            migrate_subtitle_style_settings(self.settings)
        except Exception as e:
            log(f"Altyazı stil migrasyonu yapılamadı: {e}", 'WARNING')
        for name, default in SUBTITLE_DEFAULTS.items():
            key = f"subtitle/{name}"
            # Senkron gecikmesi içeriğe özeldir; önceki videodan yeni oturuma
            # taşınması bütün altyazıları kalıcı olarak erken/geç gösterir.
            if name == "sub_delay":
                value = 0.0
                self.settings.setValue(key, value)
            else:
                value = self.settings.value(key, default)
            try:
                if isinstance(default, float):
                    # Eski sürümden kalan aşırı kayıt (`sub_scale=3.0`,
                    # `sub_border_size=10.0`) doğrudan MPV'ye UYGULANMAZ;
                    # pencereyle aynı merkezi sınırdan geçer.
                    value = normalise_subtitle_numeric(name, value)
                elif isinstance(default, bool):
                    value = str(value).lower() in ("1", "true", "yes")
                setattr(self.mpv_player, name, value)
            except Exception as e:
                log(f"Altyazı ayarı yüklenemedi ({name}): {e}", 'WARNING')
        # Arka plan kutusu, kaydedilmiş arka plan renginin alfasından
        # TÜRETİLİR; `sub_back_color` tek başına gölge rengidir.
        back = self.settings.value("subtitle/sub_back_color",
                                   SUBTITLE_DEFAULTS["sub_back_color"])
        style = border_style_for(back)
        for name, value in (("sub_border_style", style),
                            ("sub_shadow_offset",
                             BACKGROUND_BOX_SHADOW_OFFSET
                             if style == BACKGROUND_BOX else 0.0)):
            try:
                setattr(self.mpv_player, name, value)
            except Exception as e:
                log(f"Altyazı ayarı yüklenemedi ({name}): {e}", 'WARNING')
        # Kontrol katmanının kapladığı bant için ALT MARJ. `sub_pos`
        # kullanıcının tercihidir ve değiştirilmez; %100 bu marj sayesinde
        # "panele en yakın GÜVENLİ konum" olur.
        try:
            applied = self.video_frame.sync_subtitle_safe_band()
            log(f"Altyazı güvenli bandı: sub_margin_y={applied}", 'INFO')
        except Exception as e:
            log(f"Altyazı güvenli bandı uygulanamadı: {e}", 'WARNING')

    def log_handler(self, loglevel, component, message):
        # NOT: mpv her bilgi mesajını (AO/VO/cplayer vb.) buraya gönderir.
        # Hepsini stdout'a basmak hem konsolu doldurur hem de çıktı bir
        # pipe'a yönlendirildiğinde süreci bloke edebilir. Sadece uyarı ve
        # hata seviyelerini göster.
        if loglevel in ('warn', 'error', 'fatal'):
            # libmpv tanısı URL token'ı, `Authorization` değeri veya tam
            # medya yolu taşıyabilir. Burada ÖNCEDEN maskeleme yapılmaz:
            # konsol (`safe_console`) ve dosya logu (`log`) kendi son
            # sınırlarında maskeler. Böylece çağıranın maskelemesine
            # güvenilmez; her iki çıkış birer kez yazar.
            formatted = f"[{loglevel}] [{component}] {message}"
            safe_console(formatted)
            log(formatted, 'ERROR' if loglevel in ('error', 'fatal') else 'WARNING')

    def handle_core_idle_change(self, name, value):
        # NOT: mpv event thread'inde çalışır. Sadece state güncelle;
        # otomatik sıradaki dosya geçişi update_ui (GUI thread) içinde yapılır.
        self._core_idle = bool(value)

    def handle_time_pos_change(self, name, value):
        # NOT: Bu callback python-mpv'nin event thread'inde çalışır.
        # Qt widget'larına buradan DOKUNMAYIN - bu thread-unsafe'dir ve
        # mpv event loop'unu bloke ederek oynatmayı yavaşlatır.
        # UI güncellemeleri update_ui (QTimer, GUI thread) üzerinden yapılır.
        if value is not None:
            self.position = value

    def handle_duration_change(self, name, value):
        if value is not None:
            self.duration = value

    def update_time_label(self):
        # Bu method ui_components.py'de setup_controls içinde override edilecek
        pass

    def update_ui(self):
        # Kullanıcı arayüzü güncellemeleri - GUI thread'de çalışır (QTimer)
        try:
            # Konum slider'ı ve zaman etiketini güncelle
            if hasattr(self, 'position_slider'):
                if not self.position_slider.isSliderDown():
                    if self.duration > 0:
                        relative_pos = int(((self.position or 0) * 1000) / self.duration)
                        # Programatik güncellemeyi işaretle ki slider'ın valueChanged
                        # sinyali seek_position'a gidip seek döngüsü yaratmasın
                        self._updating_position_slider = True
                        self.position_slider.setValue(relative_pos)
                        self._updating_position_slider = False
                self.update_time_label()
                if self.video_frame.control_overlay is not None:
                    self.video_frame.update_overlay_state()

            # Oynatma gerçekten başladığında başlık çubuğunu bir kez öne al.
            # Bayrak hemen temizlendiği için her 100 ms'de raise_ çağrılmaz.
            if self._title_bar_raise_pending and self.duration > 0:
                self._title_bar_raise_pending = False
                self.ensure_title_bar_on_top()

            # Dosya sonuna ulaşıldıysa oynatma listesinde otomatik sıradaki dosyaya geç
            # NOT: Bu mpv build'i vo=gpu+wid ile END_FILE event'i göndermiyor;
            # core-idle >= dosya sonu kontrolü daha güvenilir.
            if (self._core_idle and not self.loop_file and self.duration > 0
                    and self.position >= self.duration - 0.2
                    and self.playlist):
                if self.current_playlist_index < len(self.playlist) - 1:
                    self.current_playlist_index += 1
                    play_from_playlist(self, self.current_playlist_index)
                elif self.loop_playlist:
                    play_from_playlist(self, 0)

            # Dosya açma hatası kontrolü: yükleme denendi ama 3 saniye içinde
            # süre bilgisi gelmediyse ve çekirdek boşta kaldıysa dosya açılamamıştır.
            # (core-idle koşulu, duration=0 olan canlı yayınların yanlış
            # tetiklenmesini önler — çalan yayın boşta olmaz.)
            # URL yüklemesi AYRI yaşam döngüsünden geçer; yerel 3 saniyelik
            # yol onu hiç değerlendirmez.
            update_url_loading(self)
            if (self.current_file and self.duration <= 0
                    and self._core_idle and self._load_started_at
                    and not self.__dict__.get("_url_loading_active")
                    and time.time() - self._load_started_at > 3.0):
                # NOT: Kullanıcı penceresine geliştirici talimatı
                # (`pip install ...`) YAZILMAZ.
                msg = f"Dosya açılamadı:\n{self.current_file}"
                show_user_error(self, "Dosya Açılamadı",
                                "Dosya açılamadı. Dosyanın mevcut ve desteklenen "
                                "bir medya dosyası olduğunu kontrol edin.",
                                details=msg)
                stop(self)

            # Yeni bir dosya yüklendiğinde ses kanalı menüsünü otomatik doldur
            # (kullanıcının "Ses Kanallarını Yenile"ye tıklaması gerekmez)
            if (self.current_file and self.current_file != self._audio_menu_file
                    and self.duration > 0):
                self._audio_menu_file = self.current_file
                try:
                    refresh_audio_tracks(self)
                except Exception as e:
                    safe_console(f"Ses kanalı menüsü yenilenemedi: {e}")

            if (self.current_file and self.current_file != self._chapter_menu_file
                    and self.duration > 0):
                self._chapter_menu_file = self.current_file
                refresh_chapters(self)

            # Medya ile birlikte bırakılan altyazılar yükleme tamamlanınca
            # eklensin; canlı bırakmayla AYNI etkinleştirme yolu kullanılır.
            self._apply_pending_subtitles()

            # Yerel SRT sessiz otomatik etkinleştirme (medya başına tek atım).
            # Yeni timer kurulmaz; mevcut UI döngüsünün içinde çalışır.
            if self.duration > 0 and self.mpv_player.track_list:
                activate_local_subtitle(self)

            # Mevcut dosya oynatılıyorsa butonları etkinleştir
            has_file = bool(self.current_file)
            if hasattr(self, 'stop_button'):
                self.stop_button.setEnabled(has_file)
            if hasattr(self, 'fullscreen_button'):
                self.fullscreen_button.setEnabled(has_file)
            if hasattr(self, 'screenshot_button'):
                self.screenshot_button.setEnabled(has_file)
            if hasattr(self, 'subtitle_button'):
                self.subtitle_button.setEnabled(has_file)
            # Medya Bilgisi eylemi ve açık pencere AYNI turdan beslenir;
            # ayrı timer veya observe_property kurulmaz. Pencere kapalıysa
            # `refresh_media_info()` hiçbir mpv property'si okumaz.
            media_info_action = self.__dict__.get("media_info_action")
            if media_info_action is not None:
                media_info_action.setEnabled(has_file)
            refresh_media_info(self)

            # Önceki/sonraki butonlar için oynatma listesi kontrolü
            has_playlist = len(self.playlist) > 0
            has_next = has_playlist and self.current_playlist_index < len(self.playlist) - 1
            has_prev = has_playlist and self.current_playlist_index > 0

            if hasattr(self, 'prev_button'):
                self.prev_button.setEnabled(has_prev)
            if hasattr(self, 'next_button'):
                self.next_button.setEnabled(has_next)

        except Exception as e:
            safe_console(f"UI güncelleme hatası: {e}")
            log(f"UI güncelleme hatası: {e}", 'ERROR')

    # --- Sürükle-bırak altyazısı ---
    def _subtitle_track_wait(self):
        """`track_list` beklemesinde ana thread'i UYUTMADAN süre geçirir.

        Kalıcı timer veya polling EKLENMEZ: kısa ömürlü yerel loop yalnız
        aktif bekleme boyunca yaşar (Altyazı Merkezi'ndeki `_qt_wait` ile
        aynı gerekçe: `processEvents` tek başına gerçek süre harcamıyor).
        """
        if QApplication.instance() is None:
            return
        loop = QEventLoop()
        QTimer.singleShot(max(1, int(round(TRACK_WAIT_INTERVAL_S * 1000))),
                          Qt.TimerType.PreciseTimer, loop.quit)
        loop.exec()

    def _activate_dropped_subtitle(self, path):
        """Bırakılan altyazıyı ekler, DOĞRULAR, seçer ve görünür yapar.

        İkinci bir altyazı yaşam döngüsü yazılmaz: Altyazı Merkezi'nin
        `SubtitleSession.apply()` sözleşmesi yeniden kullanılır. Böylece aynı
        yol iki kez eklenmez, track `external-filename` ile doğrulanır ve
        doğrulanamazsa hiçbir track seçilmez; mevcut `sid`, görünürlük ve
        oynatma bozulmaz.
        """
        if not os.path.isfile(path):
            show_user_error(self, "Altyazı Bulunamadı",
                            "Altyazı dosyası bulunamadı. Dosyanın yerini kontrol edin.",
                            details=f"Altyazı yolu: {path}")
            return False
        if self._drop_subtitle_session is None:
            self._drop_subtitle_session = SubtitleSession()
        try:
            applied = bool(self._drop_subtitle_session.apply(
                self, path, wait=self._subtitle_track_wait,
                attempts=TRACK_WAIT_ATTEMPTS))
        except Exception as e:
            safe_console(f"Altyazı ekleme hatası: {type(e).__name__}")
            show_user_error(self, "Altyazı Eklenemedi",
                            "Altyazı eklenemedi. Dosyanın desteklenen ve "
                            "okunabilir bir altyazı dosyası olduğundan emin olun.",
                            exc=e)
            return False
        if applied:
            safe_console(f"Altyazı eklendi: {path}")
            self.video_frame.show_osd("Altyazı eklendi")
            # Açık kullanıcı seçimi bu medya için otomatik yerel SRT
            # seçimini tüketir; otomasyon kullanıcının tercihini EZMEZ.
            suppress_local_subtitle(self)
            return True
        show_user_error(self, "Altyazı Eklenemedi",
                        "Altyazı eklenemedi. Dosyanın desteklenen ve "
                        "okunabilir bir altyazı dosyası olduğundan emin olun.",
                        details=f"Altyazı yolu: {path}")
        return False

    def _apply_pending_subtitles(self):
        """Medya ile birlikte bırakılan altyazıları yükleme bitince ekler.

        mpv, yükleme sırasında önceden `sub_add` edilmiş dış altyazıları
        siler; bu yüzden kuyruk yalnız gerçek `track_list` hazır olduğunda
        boşaltılır ve canlı bırakmayla AYNI etkinleştirme yolundan geçer.
        """
        if not (self._pending_subs and self.duration > 0
                and self.mpv_player.track_list):
            return
        pending = self._pending_subs
        self._pending_subs = []
        for path in pending:
            self._activate_dropped_subtitle(path)

    # --- Sürükle-bırak ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        paths = [u.toLocalFile() for u in urls]
        event.acceptProposedAction()
        if not paths:
            return

        # Altyazı uzantılarını tespit et (".srt" -> "srt")
        sub_exts = tuple(e.strip('*').lower() for e in SUBTITLE_EXTENSIONS.split())
        subtitle_paths = [p for p in paths if os.path.splitext(p)[1].lower() in sub_exts]
        allowed_media = media_suffixes()
        media_paths = [
            p for p in paths
            if (os.path.isfile(p) and p not in subtitle_paths
                and os.path.splitext(p)[1].lower() in allowed_media)
        ]

        def add_sub(s):
            # mpv, video yüklü değilken sub_add'i -12 (command) ile reddeder.
            # Yüklü değilse altyazıyı bekleme listesine al; video yüklenince eklenecek.
            if not self.current_file:
                show_user_error(self, "Altyazı Eklenemedi",
                                "Önce bir video açın, sonra altyazıyı ekleyin.",
                                details=f"Altyazı yolu: {s}")
                return
            if self.duration <= 0:
                self._pending_subs.append(s)
                safe_console(f"Altyazı yükleme sırasına alındı: {s}")
                self.video_frame.show_osd("Altyazı yükleniyor...")
                return
            self._activate_dropped_subtitle(s)

        if len(media_paths) == 1:
            if (subtitle_paths and media_paths[0] == self.current_file
                    and self.duration > 0 and not self._core_idle):
                # Aynı dosya zaten oynuyor: altyazıyı canlı ekle, yeniden yükleme yapma
                for s in subtitle_paths:
                    add_sub(s)
            elif (getattr(self.video_frame, "playlist_panel", None) is not None
                  and self.video_frame.playlist_panel.is_open):
                # Playlist açıkken video yüzeyine bırakılan tek dosya da kuyruğa
                # eklenir; listeyi tek öğeye sıfırlamaz.
                append_media_paths(self, media_paths)
                self._pending_subs = list(subtitle_paths)
            else:
                # Yeni medya açılacak: mpv yükleme sırasında önceden eklenen dış
                # altyazıları sildiği için altyazıları yükleme tamamlanınca ekle
                open_path(self, media_paths[0])
                self._pending_subs = list(subtitle_paths)
        elif len(media_paths) > 1:
            # Çoklu bırakma mevcut listeyi silmez. Oynatma yoksa ilk yeni öğe
            # başlatılır; oynatma sürüyorsa yalnızca kuyruğa eklenir.
            append_media_paths(self, media_paths)
            self._pending_subs = list(subtitle_paths)
        else:
            # Sürükle-bırak ile altyazı: video oynarken anında ekle (canlı)
            for s in subtitle_paths:
                add_sub(s)

    # --- Pencere başlığı ve son açılanlar ---
    def set_title(self):
        """Pencere basligi. UZAK adres BASLIGA TAM yazilmaz.

        OLCULEN ACIK: yerel dosya degilse tam `current_file` kullaniliyordu;
        `userinfo`, `query`, `token` ve `fragment` basliga cikabiliyordu.
        Uzak adreste yalniz guvenli `host[:port]` gosterilir.
        """
        base = ""
        if self.current_file:
            if is_remote_media_url(self.current_file):
                base = safe_media_host(self.current_file)
            elif os.path.isfile(self.current_file):
                base = os.path.basename(self.current_file)
            else:
                base = self.current_file
        if base:
            self.setWindowTitle(f"{base} - {APP_NAME}")
        else:
            self.setWindowTitle(APP_NAME)

    def restore_recent_files(self):
        """Kalici listeyi okur ve UZAK adresleri GERI YUKLEMEZ.

        URUN KARARI: uzak URL'ler kalici ayara hic yazilmaz; eski surumden
        kalan girdiler de geri getirilmez ve ayar bir kez normalize edilir.
        Yerel yollar (var olmayan ya da UNC dahil) KORUNUR.
        """
        stored = self.settings.value("recent_files", []) or []
        if isinstance(stored, str):
            stored = [stored]
        entries = [path for path in stored if isinstance(path, str)]
        safe = [path for path in entries if not is_remote_media_url(path)]
        self.recent_files = safe
        if len(safe) != len(entries):
            self.settings.setValue("recent_files", safe)

    def _persistable_recent_files(self):
        """Diske YALNIZ yerel girdiler yazilir."""
        return [path for path in self.recent_files
                if not is_remote_media_url(path)][:RECENT_FILE_LIMIT]

    def add_recent_file(self, path):
        if not path:
            return
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        del self.recent_files[RECENT_FILE_LIMIT:]
        # Uzak adres OTURUM icinde listede kalir ama diske YAZILMAZ.
        self.settings.setValue("recent_files", self._persistable_recent_files())
        update_recent_menu(self)

    def remove_recent_file(self, path):
        """Artık açılamayan girdiyi modelden VE kalıcı ayardan siler."""
        if path not in self.recent_files:
            return
        self.recent_files.remove(path)
        self.settings.setValue("recent_files", self._persistable_recent_files())
        update_recent_menu(self)

    # --- Döngü ve karışık modlar ---
    def set_loop_file(self, enabled):
        self.loop_file = enabled
        try:
            self.mpv_player.loop_file = "inf" if enabled else "no"
        except Exception as e:
            safe_console(f"Döngü ayarı hatası: {e}")

    def set_loop_playlist(self, enabled):
        self.loop_playlist = enabled

    def toggle_shuffle(self, enabled):
        self.shuffle = bool(enabled)
        if self.shuffle and len(self.playlist) > 1:
            import random
            current = self.playlist[self.current_playlist_index] if (
                0 <= self.current_playlist_index < len(self.playlist)) else None
            current_index = self.current_playlist_index
            remaining = [path for index, path in enumerate(self.playlist)
                         if index != current_index]
            random.shuffle(remaining)
            self.playlist = ([current] if current else []) + remaining
            self.current_playlist_index = 0 if current else -1
        return self.shuffle

    def toggle_fullscreen(self):
        if not self.video_frame.is_video_fullscreen:
            self.video_frame.enter_fullscreen()
        else:
            self.video_frame.exit_fullscreen()

    def restore_default_window_size(self):
        """Pencere modunda Esc ile dengeli varsayılan boyuta dön ve ortala."""
        if self.isMaximized() or self.isMinimized():
            self.showNormal()
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(ESCAPE_WINDOW_WIDTH, ESCAPE_WINDOW_HEIGHT)
            return
        available = screen.availableGeometry()
        width = min(ESCAPE_WINDOW_WIDTH, max(self.minimumWidth(),
                                             available.width() - 40))
        height = min(ESCAPE_WINDOW_HEIGHT, max(self.minimumHeight(),
                                               available.height() - 40))
        self.resize(width, height)
        self.move(available.x() + (available.width() - width) // 2,
                  available.y() + (available.height() - height) // 2)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # Modifier kombinasyonları önce kontrol edilmelidir.
        # Aksi halde aşağıdaki yalın ok tuşu kontrolleri bu kombinasyonları
        # "yutar" ve Shift/Ctrl+ok kısayolları asla çalışmaz.
        if key == Qt.Key.Key_Space:
            play_pause(self)
        elif key == Qt.Key.Key_Escape:
            if self.video_frame.is_video_fullscreen:
                self.video_frame.exit_fullscreen()
            else:
                self.restore_default_window_size()
            event.accept()
        elif key == Qt.Key.Key_O and modifiers & Qt.KeyboardModifier.ControlModifier:
            open_file(self)
        elif key == Qt.Key.Key_P and modifiers & Qt.KeyboardModifier.ControlModifier:
            show_playlist(self)
        elif key == Qt.Key.Key_U and modifiers & Qt.KeyboardModifier.ControlModifier:
            open_url(self)
        elif key == Qt.Key.Key_S and modifiers & Qt.KeyboardModifier.ControlModifier:
            take_screenshot(self)
        elif key == Qt.Key.Key_G and modifiers & Qt.KeyboardModifier.ControlModifier:
            goto_time(self)
        elif key == Qt.Key.Key_Q and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.close()
        elif key == Qt.Key.Key_Right and modifiers & Qt.KeyboardModifier.ControlModifier:
            # Ctrl + Sağ ok - Sonraki parça
            play_next(self)
        elif key == Qt.Key.Key_Left and modifiers & Qt.KeyboardModifier.ControlModifier:
            # Ctrl + Sol ok - Önceki parça
            play_previous(self)
        elif key == Qt.Key.Key_Right and modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Shift + Sağ ok - 30 saniye ileri
            seek_relative(self, 30)
        elif key == Qt.Key.Key_Left and modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Shift + Sol ok - 30 saniye geri
            seek_relative(self, -30)
        elif key == Qt.Key.Key_Right:
            # Sağ ok - 5 saniye ileri
            seek_relative(self, 5)
        elif key == Qt.Key.Key_Left:
            # Sol ok - 5 saniye geri
            seek_relative(self, -5)
        elif key == Qt.Key.Key_Up:
            # Ses arttır
            try:
                current_volume = min(MAX_VOLUME, max(0, float(self.mpv_player.volume)))
                new_volume = min(MAX_VOLUME, current_volume + 5)
                self.mpv_player.volume = new_volume
                self.volume_slider.setValue(int(new_volume))
            except Exception as e:
                safe_console(f"Volume up error: {e}")
        elif key == Qt.Key.Key_Down:
            # Ses azalt - negatif değerleri önle
            try:
                current_volume = min(MAX_VOLUME, max(0, float(self.mpv_player.volume)))
                new_volume = max(0, current_volume - 5)  # 0'dan küçük olamaz
                self.mpv_player.volume = new_volume
                self.volume_slider.setValue(int(new_volume))
            except Exception as e:
                safe_console(f"Volume down error: {e}")
        elif key == Qt.Key.Key_M:
            # Sessiz modunu aç/kapat
            toggle_mute(self)
        elif key == Qt.Key.Key_F:
            # F ile tam ekran
            self.toggle_fullscreen()
        elif key == Qt.Key.Key_S:
            # Alt menüyü getir (altyazılar için)
            toggle_subtitles(self)
        elif key == Qt.Key.Key_H and modifiers & Qt.KeyboardModifier.AltModifier:
            toggle_subtitles(self)
        elif key == Qt.Key.Key_E and modifiers & Qt.KeyboardModifier.AltModifier:
            open_subtitle(self)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Altyazı Merkezi'nde çalışan arama/indirme/apply varsa kapanış
        # ERTELENİR: UI donmaz, çalışan QThread geride bırakılmaz ve zorla
        # sonlandırılmaz. İşler bitince pencere kapatma isteği kendiliğinden
        # ve YALNIZ BİR KEZ yeniden tetiklenir.
        try:
            ready = close_subtitle_center_before_exit(self)
        except Exception:
            # FAIL-CLOSED: koordinasyon beklenmedik biçimde başarısızsa
            # "hazır" VARSAYILMAZ. Yalnızca gerçekten boşta olduğu ayrıca
            # doğrulanabiliyorsa kapanışa devam edilir; böylece çalışan bir
            # QThread'in üzerine yıkım yapılmaz. Hata metni kullanıcıya
            # gösterilmez (yol/anahtar sızdırabilir).
            safe_console("Altyazı Merkezi kapatma koordinasyonu başarısız; "
                  "kapanış ertelendi.")
            ready = subtitle_center_drained(self)
        if not ready:
            event.ignore()
            return

        # Kapanış temizliği YALNIZ BİR KEZ çalışır. Kapanış isteği tekrar
        # gelirse (ör. `shutdown_player()` + pencere kapatma) ayarlar
        # yeniden yazılmaz, timer/overlay/filtre temizliği tekrarlanmaz.
        # NOT: bayraklar `__dict__` üzerinden okunur/yazılır; testlerdeki
        # sip stub'larında normal öznitelik erişimi RuntimeError üretebiliyor.
        if self.__dict__.get("_mlc_close_done", False):
            event.accept()
            return
        self.__dict__["_mlc_close_done"] = True

        # Ayarları kaydet (pencere boyutu, ses seviyesi, son klasör)
        try:
            self.settings.setValue("geometry", self.saveGeometry())
            if hasattr(self, 'volume_slider'):
                self.settings.setValue("volume", self.volume_slider.value())
            if self.last_dir:
                self.settings.setValue("last_dir", self.last_dir)
        except Exception as e:
            safe_console(f"Ayar kaydetme hatası: {type(e).__name__}")

        # Her bağımsız teardown adımı KENDİ hata sınırındadır: birinin
        # hatası MPV `stop`/`terminate` adımına ulaşmayı engellememelidir.
        # Hata metni yazdırılmaz (yol/anahtar sızdırabilir); yalnız tür adı.
        try:
            self.timer.stop()
        except Exception as e:
            safe_console(f"Zamanlayıcı durdurulamadı: {type(e).__name__}")
        # Medya Bilgisi penceresi MPV'ye dokunulmadan ÖNCE kapatılır.
        # Worker/thread barındırmadığı için Altyazı Merkezi drenajına
        # bağlanmaz; çağrı idempotenttir ve hata kapanışı engellemez.
        try:
            close_media_info(self)
        except Exception as e:
            safe_console(f"Medya Bilgisi kapatılamadı: {type(e).__name__}")
        try:
            clear_url_loading(self)
        except Exception as e:
            safe_console(f"Bağlantı durumu temizlenemedi: {type(e).__name__}")
        # MPV olay thread'i stop/terminate sırasında Qt nesnelerine geç
        # bildirim taşımasın. Ayırma idempotenttir ve kendi hata sınırında
        # çalışır; başarısızlık kapanışı engellemez.
        subtitle_watcher = self.__dict__.get("_subtitle_watcher")
        if subtitle_watcher is not None:
            try:
                subtitle_watcher.detach()
            except Exception as e:
                safe_console("Altyazı gözlemcisi kapatılamadı: "
                             f"{type(e).__name__}")
            finally:
                self._subtitle_watcher = None
        # Drenaj bitti; kalan pencere/referanslar MPV terminate edilmeden
        # ÖNCE bırakılır. Bu çağrı idempotenttir.
        try:
            shutdown_subtitle_center(self, wait_ms=0)
        except Exception as e:
            safe_console(f"Altyazı Merkezi kapatma hatası: {type(e).__name__}")
        # Yüzen overlay/OSD pencereleri MPV'ye dokunulmadan ÖNCE, düzenli
        # ve sahipli biçimde bırakılır (timer'lar durur, geç olayların
        # tutunacağı referanslar temizlenir).
        release_surfaces = getattr(self.video_frame,
                                   "release_overlay_surfaces", None)
        if callable(release_surfaces):
            try:
                release_surfaces()
            except Exception as e:
                safe_console(f"Overlay yüzeyleri bırakılamadı: {type(e).__name__}")
        # Playlist panelinin thumbnail worker SÜRECİ kapanışta sahipsiz
        # kalmamalı. Qt, ana pencere kapanırken çocuk widget'lara
        # `closeEvent` GÖNDERMEZ; bu yüzden panelin kendi kapanış
        # sözleşmesi burada açıkça çağrılır. MPV terminate'ten ÖNCE olur.
        panel = getattr(self.video_frame, "playlist_panel", None)
        if panel is not None:
            try:
                panel.close()
            except Exception as e:
                safe_console(f"Playlist paneli kapatılamadı: {type(e).__name__}")
        # NOT: __dict__ üzerinden okunur; testlerdeki sip stub'larında
        # normal öznitelik erişimi RuntimeError üretebiliyor.
        resize_filter = self.__dict__.get("resize_filter")
        if resize_filter is not None:
            try:
                resize_filter.remove()
            except Exception as e:
                safe_console(f"Resize filtresi kaldırılamadı: {type(e).__name__}")
            self.resize_filter = None
        try:
            if self.video_frame.is_video_fullscreen:
                self.video_frame.exit_fullscreen()
        except Exception as e:
            safe_console(f"Tam ekrandan çıkılamadı: {type(e).__name__}")
        # MPV KAPANIŞI: önce `stop()`, sonra `terminate()`.
        # Bu sıra, `subtitle_service.shutdown_player()` yolunda uzun süredir
        # sorunsuz kullanılan sıradır; `stop()` çağrılmadan doğrudan
        # terminate eden eski yolda aralıklı native erişim ihlali
        # (`0xC0000005`) RAPORLANMIŞTI. Bu turda ölçülen kesin nokta
        # şudur: sıra ve idempotanslık testlerle kilitlidir.
        # `_mlc_stop_done` bayrağı `subtitle_service.shutdown_player()` ile
        # ORTAKTIR: o yol stop'u zaten çağırdıysa burada TEKRAR çağrılmaz.
        mpv_player = self.mpv_player
        if mpv_player is not None:
            if not self.__dict__.get("_mlc_stop_done", False):
                self.__dict__["_mlc_stop_done"] = True
                try:
                    mpv_player.stop()
                except Exception as e:
                    # Durdurma başarısız olsa bile kapanış SÜRER; aksi halde
                    # uygulama kapanamaz durumda kalırdı. Hata metni
                    # kullanıcıya/log'a sızdırılmaz (yol/anahtar taşıyabilir).
                    safe_console(f"MPV durdurulamadı: {type(e).__name__}")
            # Referans terminate DENEMESİNDEN sonra her hâlükârda bırakılır;
            # böylece aynı MPV nesnesi ikinci kez terminate edilmez.
            try:
                mpv_player.terminate()
            except Exception as e:
                safe_console(f"MPV sonlandırılamadı: {type(e).__name__}")
            finally:
                self.mpv_player = None
        event.accept()

    # Media kontrollerini ve menü işlemlerini ayrı modüllerden çağırmak için fonksiyon yönlendirmeleri
    def toggle_mute(self): toggle_mute(self)
    def open_file(self): open_file(self)
    def open_folder(self): open_folder(self)
    def open_url(self): open_url(self)
    def open_path(self, path): open_path(self, path)
    def open_recent(self, path): open_recent(self, path)
    def open_subtitle(self): open_subtitle(self)
    def select_subtitle_language(self, sid): select_subtitle_language(self, sid)
    def toggle_subtitles(self): toggle_subtitles(self)
    def seek_position(self, position): seek_position(self, position)
    def seek_relative(self, seconds): seek_relative(self, seconds)
    def seek_chapter(self, delta): seek_chapter(self, delta)
    def play_pause(self): play_pause(self)
    def stop(self): stop(self)
    def set_volume(self, volume): set_volume(self, volume)
    def change_volume(self, delta): change_volume(self, delta)
    def add_to_playlist(self): add_to_playlist(self)
    def show_playlist(self): show_playlist(self)
    def save_playlist(self): save_playlist(self)
    def load_playlist(self): load_playlist(self)
    def play_from_playlist(self, index): play_from_playlist(self, index)
    def remove_from_playlist(self, index): remove_from_playlist(self, index)
    def clear_playlist(self): clear_playlist(self)
    def take_screenshot(self): take_screenshot(self)
    def play_next(self): play_next(self)
    def play_previous(self): play_previous(self)
    def goto_time(self): goto_time(self)
    def set_playback_speed(self, speed): set_playback_speed(self, speed)
    def setup_video_adjustments(self): setup_video_adjustments(self)
    def show_subtitle_settings(self): show_subtitle_settings(self)
    def open_subtitle_center(self): return open_subtitle_center(self)
    def refresh_audio_tracks(self): refresh_audio_tracks(self)
    def select_audio_track(self, aid): select_audio_track(self, aid)
    def refresh_audio_devices(self): refresh_audio_devices(self)
    def select_audio_device(self, name): select_audio_device(self, name)
    def refresh_subtitle_tracks(self): refresh_subtitle_tracks(self)
    def refresh_chapters(self): refresh_chapters(self)
    def select_chapter(self, index): select_chapter(self, index)
    def show_log_management(self): show_log_management(self)
    def show_media_info(self): return show_media_info(self)
    def show_shortcuts(self): show_shortcuts(self)
    def show_about(self): show_about(self)
