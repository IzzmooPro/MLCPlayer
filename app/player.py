import os
import sys
import time
import mpv
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QMessageBox, QStyle, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QSettings

from app.config import APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT, APP_STYLE, DEFAULT_VOLUME, MAX_VOLUME, MPV_CONFIG, MEDIA_EXTENSIONS, SUBTITLE_EXTENSIONS, SUBTITLE_DEFAULTS
from app.video_frame import VideoFrame
from app.title_bar import (RESIZE_MARGIN, FramelessResizeFilter,
                           TitleBar)
from app.ui_components import setup_controls
from app.menu_actions import setup_menu, setup_video_adjustments, show_subtitle_settings, refresh_audio_tracks, refresh_audio_devices, refresh_subtitle_tracks, refresh_chapters, select_chapter, select_audio_track, select_audio_device, show_shortcuts, show_about, update_recent_menu
from app.errors import show_user_error, log
from app.media_controls import (
    toggle_mute, open_file, open_url, open_path, open_subtitle, select_subtitle_language, toggle_subtitles,
    seek_position, seek_relative, seek_chapter, play_pause, stop, set_volume, change_volume, add_to_playlist, show_playlist,
    play_from_playlist, remove_from_playlist, clear_playlist, take_screenshot, play_next,
    play_previous, goto_time, set_playback_speed, save_playlist, load_playlist
)

class MPVPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveDVDIcon))

        # Pencere davranışı ayarlarını ekle
        self.setMinimumSize(400, 300)  # Minimum pencere boyutu
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # Yeniden boyutlandırmaya izin ver

        # Preview modunda frameless bayrağı, herhangi bir native pencere
        # oluşturulmadan ÖNCE ayarlanmalıdır. Aksi halde Qt show() sırasında
        # top-level pencereyi yeniden yaratır, mpv'nin wid child penceresi
        # geçersizleşir ve video başlık çubuğunun üstünü kaplar.
        self.preview_mode = os.environ.get("MLCPLAYER_OVERLAY_PREVIEW") == "1"
        window_flags = self.windowFlags() | Qt.WindowType.Window
        if self.preview_mode:
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
        # Oynatma başlayınca başlık çubuğunu bir kez öne alma bayrağı
        self._title_bar_raise_pending = False
        # Döngü ve karışık mod bayrakları
        self.loop_file = False
        self.loop_playlist = False
        self.shuffle = False
        # Ayarlar kalıcılığı (pencere, ses, son dosyalar)
        self.settings = QSettings("MLCPlayer", "MLCPlayer")
        stored_recent = self.settings.value("recent_files", []) or []
        if isinstance(stored_recent, str):
            stored_recent = [stored_recent]
        self.recent_files = [path for path in stored_recent if isinstance(path, str)]
        stored_dir = self.settings.value("last_dir", "") or ""
        self.last_dir = stored_dir if isinstance(stored_dir, str) and os.path.isdir(stored_dir) else ""

        # Menü çubuğu
        setup_menu(self)

        # Preview modunda klasik başlık çubuğu yerine modern özel çubuk.
        # Normal (preview kapalı) davranış hiçbir şekilde değişmez.
        self.title_bar = None
        self.resize_filter = None
        if self.preview_mode:
            self.menuBar().hide()
            self.title_bar = TitleBar(self)
            self.main_layout.addWidget(self.title_bar)
            # NOT: mpv native yüzeyi normal child widget'ların üstünü
            # kapatabiliyor (projedeki OSD/overlay ile aynı sorun). Başlık
            # çubuğuna kendi native penceresini verip z-order'da öne alıyoruz.
            self.title_bar.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
            self.title_bar.winId()
            # Kenar resize bölgesi pencereye ait kalsın diye ince iç boşluk.
            self.main_layout.setContentsMargins(
                RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN)
            self.setMouseTracking(True)

        # Video çerçevesi
        self.video_frame = VideoFrame(self)
        # NOT: Bu minimum, ana pencerenin 400x300 minimumundan küçük olmalıdır;
        # aksi halde menü çubuğu ve klasik kontrol paneli eklendiğinde video
        # alanı pencerenin dışına taşar.
        self.video_frame.setMinimumSize(200, 120)
        self.video_frame.setStyleSheet("background-color: #000000;")
        self.main_layout.addWidget(self.video_frame)

        # MPV yapılandırmasını optimize et
        try:
            self.init_mpv_player()
            print("MPV oynatıcı başarıyla yapılandırıldı.")
        except Exception as e:
            print(f"MPV yapılandırma hatası: {e}")
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
        if self.preview_mode and self.title_bar is not None:
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
        if not getattr(self, "preview_mode", False):
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
        if not getattr(self, "preview_mode", False):
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
        config['ytdl'] = True
        self.mpv_player = mpv.MPV(**config)
        self.mpv_player.deinterlace = 'no'
        self.mpv_player.untimed = False

        self.mpv_player.observe_property('time-pos', self.handle_time_pos_change)
        self.mpv_player.observe_property('duration', self.handle_duration_change)
        self.mpv_player.observe_property('core-idle', self.handle_core_idle_change)
        self.restore_subtitle_settings()
        self.refresh_audio_devices()

    def restore_subtitle_settings(self):
        """Kaydedilmiş altyazı görünüm ayarlarını yeni mpv oturumuna uygular."""
        for name, default in SUBTITLE_DEFAULTS.items():
            value = self.settings.value(f"subtitle/{name}", default)
            try:
                if isinstance(default, float):
                    value = float(value)
                elif isinstance(default, bool):
                    value = str(value).lower() in ("1", "true", "yes")
                setattr(self.mpv_player, name, value)
            except Exception as e:
                log(f"Altyazı ayarı yüklenemedi ({name}): {e}", 'WARNING')

    def log_handler(self, loglevel, component, message):
        # NOT: mpv her bilgi mesajını (AO/VO/cplayer vb.) buraya gönderir.
        # Hepsini stdout'a basmak hem konsolu doldurur hem de çıktı bir
        # pipe'a yönlendirildiğinde süreci bloke edebilir. Sadece uyarı ve
        # hata seviyelerini göster.
        if loglevel in ('warn', 'error', 'fatal'):
            formatted = f"[{loglevel}] [{component}] {message}"
            print(formatted)
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
            if (self.current_file and self.duration <= 0
                    and self._core_idle and self._load_started_at
                    and time.time() - self._load_started_at > 3.0):
                msg = f"Dosya açılamadı:\n{self.current_file}"
                if str(self.current_file).startswith(('http://', 'https://')):
                    msg += ("\n\nNot: URL oynatma başarısız olabilir. YouTube gibi "
                            "siteler için yt-dlp kurulu olmalıdır:\npip install yt-dlp")
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
                    print(f"Ses kanalı menüsü yenilenemedi: {e}")

            if (self.current_file and self.current_file != self._chapter_menu_file
                    and self.duration > 0):
                self._chapter_menu_file = self.current_file
                refresh_chapters(self)

            # Medya ile birlikte bırakılan altyazılar yükleme tamamlanınca eklensin
            # (mpv, yükleme sırasında önceden sub_add edilmiş dış altyazıları siler)
            if self._pending_subs and self.duration > 0 and self.mpv_player.track_list:
                pending = self._pending_subs
                self._pending_subs = []
                for s in pending:
                    if not os.path.isfile(s):
                        show_user_error(self, "Altyazı Bulunamadı",
                                        "Altyazı dosyası bulunamadı. Dosyanın yerini kontrol edin.",
                                        details=f"Altyazı yolu: {s}")
                        continue
                    try:
                        self.mpv_player.sub_add(s)
                        self.video_frame.show_osd("Altyazı eklendi")
                    except Exception as e:
                        print(f"Altyazı ekleme hatası: {e}")
                        show_user_error(self, "Altyazı Eklenemedi",
                                        "Altyazı eklenemedi. Dosyanın okunabilir olduğunu kontrol edin.",
                                        exc=e)

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

            # Önceki/sonraki butonlar için oynatma listesi kontrolü
            has_playlist = len(self.playlist) > 0
            has_next = has_playlist and self.current_playlist_index < len(self.playlist) - 1
            has_prev = has_playlist and self.current_playlist_index > 0

            if hasattr(self, 'prev_button'):
                self.prev_button.setEnabled(has_prev)
            if hasattr(self, 'next_button'):
                self.next_button.setEnabled(has_next)

        except Exception as e:
            print(f"UI güncelleme hatası: {e}")
            log(f"UI güncelleme hatası: {e}", 'ERROR')

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
        media_paths = [p for p in paths if os.path.isfile(p) and p not in subtitle_paths]

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
                print(f"Altyazı yükleme sırasına alındı: {s}")
                self.video_frame.show_osd("Altyazı yükleniyor...")
                return
            if not os.path.isfile(s):
                show_user_error(self, "Altyazı Bulunamadı",
                                "Altyazı dosyası bulunamadı. Dosyanın yerini kontrol edin.",
                                details=f"Altyazı yolu: {s}")
                return
            try:
                self.mpv_player.sub_add(s)
                print(f"Altyazı eklendi: {s}")
                self.video_frame.show_osd("Altyazı eklendi")
            except Exception as e:
                print(f"Altyazı ekleme hatası: {e}")
                show_user_error(self, "Altyazı Eklenemedi",
                                "Altyazı eklenemedi. Dosyanın desteklenen ve "
                                "okunabilir bir altyazı dosyası olduğundan emin olun.",
                                exc=e)

        if len(media_paths) == 1:
            if (subtitle_paths and media_paths[0] == self.current_file
                    and self.duration > 0 and not self._core_idle):
                # Aynı dosya zaten oynuyor: altyazıyı canlı ekle, yeniden yükleme yapma
                for s in subtitle_paths:
                    add_sub(s)
            else:
                # Yeni medya açılacak: mpv yükleme sırasında önceden eklenen dış
                # altyazıları sildiği için altyazıları yükleme tamamlanınca ekle
                open_path(self, media_paths[0])
                self._pending_subs = list(subtitle_paths)
        elif len(media_paths) > 1:
            # Birden fazla medya dosyası bırakıldıysa playlist oluştur
            self.playlist = media_paths
            self.current_playlist_index = 0
            play_from_playlist(self, 0)
            self._pending_subs = list(subtitle_paths)
        else:
            # Sürükle-bırak ile altyazı: video oynarken anında ekle (canlı)
            for s in subtitle_paths:
                add_sub(s)

    # --- Pencere başlığı ve son açılanlar ---
    def set_title(self):
        if self.current_file and os.path.isfile(self.current_file):
            base = os.path.basename(self.current_file)
        else:
            base = self.current_file
        if base:
            self.setWindowTitle(f"{base} - {APP_NAME}")
        else:
            self.setWindowTitle(APP_NAME)

    def add_recent_file(self, path):
        if not path:
            return
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        del self.recent_files[10:]
        self.settings.setValue("recent_files", self.recent_files)
        update_recent_menu(self)

    # --- Döngü ve karışık modlar ---
    def set_loop_file(self, enabled):
        self.loop_file = enabled
        try:
            self.mpv_player.loop_file = "inf" if enabled else "no"
        except Exception as e:
            print(f"Döngü ayarı hatası: {e}")

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
                print(f"Volume up error: {e}")
        elif key == Qt.Key.Key_Down:
            # Ses azalt - negatif değerleri önle
            try:
                current_volume = min(MAX_VOLUME, max(0, float(self.mpv_player.volume)))
                new_volume = max(0, current_volume - 5)  # 0'dan küçük olamaz
                self.mpv_player.volume = new_volume
                self.volume_slider.setValue(int(new_volume))
            except Exception as e:
                print(f"Volume down error: {e}")
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
        # Ayarları kaydet (pencere boyutu, ses seviyesi, son klasör)
        try:
            self.settings.setValue("geometry", self.saveGeometry())
            if hasattr(self, 'volume_slider'):
                self.settings.setValue("volume", self.volume_slider.value())
            if self.last_dir:
                self.settings.setValue("last_dir", self.last_dir)
        except Exception as e:
            print(f"Ayar kaydetme hatası: {e}")

        self.timer.stop()
        # NOT: __dict__ üzerinden okunur; testlerdeki sip stub'larında
        # normal öznitelik erişimi RuntimeError üretebiliyor.
        resize_filter = self.__dict__.get("resize_filter")
        if resize_filter is not None:
            resize_filter.remove()
            self.resize_filter = None
        if self.video_frame.is_video_fullscreen:
            self.video_frame.exit_fullscreen()
        try:
            if self.mpv_player:
                self.mpv_player.terminate()
                self.mpv_player = None
        except Exception as e:
            print(f"Error terminating MPV: {e}")
        event.accept()

    # Media kontrollerini ve menü işlemlerini ayrı modüllerden çağırmak için fonksiyon yönlendirmeleri
    def toggle_mute(self): toggle_mute(self)
    def open_file(self): open_file(self)
    def open_url(self): open_url(self)
    def open_path(self, path): open_path(self, path)
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
    def refresh_audio_tracks(self): refresh_audio_tracks(self)
    def select_audio_track(self, aid): select_audio_track(self, aid)
    def refresh_audio_devices(self): refresh_audio_devices(self)
    def select_audio_device(self, name): select_audio_device(self, name)
    def refresh_subtitle_tracks(self): refresh_subtitle_tracks(self)
    def refresh_chapters(self): refresh_chapters(self)
    def select_chapter(self, index): select_chapter(self, index)
    def show_shortcuts(self): show_shortcuts(self)
    def show_about(self): show_about(self)
