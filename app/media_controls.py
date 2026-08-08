import os
import time
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QInputDialog, QLineEdit, QStyle
from PyQt6.QtCore import QDateTime, QStandardPaths
from PyQt6.QtGui import QColor

import mpv
from app.config import MEDIA_EXTENSIONS, SUBTITLE_EXTENSIONS, DEFAULT_VOLUME, MAX_VOLUME
from app.utils import format_time, time_to_seconds
from app.errors import show_user_error

def toggle_mute(player):
    try:
        current_volume = player.mpv_player.volume
    except Exception as e:
        print(f"Ses seviyesi okunamadı: {e}")
        current_volume = 0

    if current_volume > 0:
        # Sessize al
        player.last_volume = current_volume
        player.mpv_player.volume = 0
        player.volume_slider.setValue(0)
        player.volume_label.setText("%0")
        player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
        player.is_muted = True
        if getattr(player, '_ui_ready', False):
            player.video_frame.show_osd("Sessiz")
    else:
        # Sessizden çık - last_volume 0 ise varsayılan ses seviyesine dön
        restore = player.last_volume if player.last_volume > 0 else DEFAULT_VOLUME
        restore = min(MAX_VOLUME, max(0, float(restore)))
        player.mpv_player.volume = restore
        player.volume_slider.setValue(int(restore))
        player.volume_label.setText(f"%{int(restore)}")
        player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        player.is_muted = False
        if getattr(player, '_ui_ready', False):
            player.video_frame.show_osd(f"Ses: %{int(restore)}")

def open_file(player):
    file_path, _ = QFileDialog.getOpenFileName(
        player, "Dosya Aç", player.last_dir, f"Medya Dosyaları ({MEDIA_EXTENSIONS})"
    )
    if file_path:
        open_path(player, file_path)

def open_path(player, path):
    """Belirli bir dosya yolunu doğrudan açar (dosya iletişim kutusu, sürükle-bırak veya komut satırı)."""
    if not path:
        return
    try:
        # Yeni medya yüklenirken eski dosyanın süre/konum bilgisi kullanılmasın.
        player.duration = 0
        player.position = 0
        player._core_idle = False
        player._audio_menu_file = ""
        player._chapter_menu_file = ""
        player._pending_subs = []
        # Doğrudan açılan dosya mevcut playlist akışından bağımsızdır.
        player.playlist = []
        player.current_playlist_index = -1
        player.current_file = path
        if os.path.isfile(path):
            player.last_dir = os.path.dirname(path)
        player._load_started_at = time.time()
        player.mpv_player.play(path)
        player.play_button.setIcon(player.pause_icon)
        player.is_paused = False
        player.video_frame.placeholder_label.hide()
        player.set_title()
        player.add_recent_file(path)
        print(f"Playing file: {path}")
    except Exception as e:
        print(f"Open file error: {e}")
        player.current_file = ""
        player.duration = 0
        player.position = 0
        player._load_started_at = 0
        player._pending_subs = []
        player.video_frame.placeholder_label.show()
        player.set_title()
        show_user_error(player, "Dosya Açılamadı",
                        "Dosya açılamadı. Dosya silinmiş, taşınmış veya "
                        "desteklenmeyen bir format olabilir.",
                        exc=e)

def open_url(player):
    url, ok = QInputDialog.getText(player, "URL'den Oynat", "Video URL'si giriniz:",
                               QLineEdit.EchoMode.Normal, "https://")
    if ok and url:
        try:
            player.duration = 0
            player.position = 0
            player._core_idle = False
            player._audio_menu_file = ""
            player._chapter_menu_file = ""
            player._pending_subs = []
            player.playlist = []
            player.current_playlist_index = -1
            player.current_file = url
            player._load_started_at = time.time()
            player.mpv_player.play(url)
            player.play_button.setIcon(player.pause_icon)
            player.is_paused = False
            player.video_frame.placeholder_label.hide()
            player.set_title()
            player.add_recent_file(url)
            print(f"URL'den oynatılıyor: {url}")
        except Exception as e:
            print(f"URL'den oynatma hatası: {e}")
            show_user_error(player, "URL Oynatılamadı",
                            "Bu adresten video oynatılamadı. Adresi kontrol edip "
                            "tekrar deneyin veya başka bir bağlantı kullanın.",
                            exc=e)

def open_subtitle(player):
    if not player.current_file:
        QMessageBox.warning(player, "Uyarı", "Önce bir video dosyası açın.")
        return

    subtitle_path, _ = QFileDialog.getOpenFileName(
        player, "Altyazı Ekle", "", f"Altyazı Dosyaları ({SUBTITLE_EXTENSIONS})"
    )
    if not subtitle_path:
        return

    # Dosya mevcut değilse mpv -12 (command) hatası verir
    if not os.path.isfile(subtitle_path):
        show_user_error(player, "Altyazı Bulunamadı",
                        "Altyazı dosyası bulunamadı. Dosyanın yerini kontrol edin.",
                        details=f"Altyazı yolu: {subtitle_path}")
        return

    # Video henüz yüklenmediyse (duration=0) mpv sub_add'i reddeder (-12).
    # Altyazıyı bekleme listesine al; video yüklenince otomatik eklenecek.
    if player.duration <= 0:
        player._pending_subs.append(subtitle_path)
        print(f"Altyazı yükleme sırasına alındı: {subtitle_path}")
        player.video_frame.show_osd("Altyazı yükleniyor...")
        return

    try:
        player.mpv_player.sub_add(subtitle_path)
        print(f"Subtitle added: {subtitle_path}")
        player.video_frame.show_osd("Altyazı eklendi")
    except Exception as e:
        print(f"Open subtitle error: {e}")
        show_user_error(player, "Altyazı Eklenemedi",
                        "Altyazı eklenemedi. Dosyanın hasarlı veya "
                        "desteklenmeyen bir format olması mümkün.",
                        exc=e)

def select_subtitle_language(player, sid):
    try:
        player.mpv_player.sid = sid
        print(f"Selected subtitle ID: {sid}")
    except Exception as e:
        print(f"Altyazı seçimi hatası: {e}")
        show_user_error(player, "Altyazı Seçilemedi",
                        "Altyazı seçilemedi. Lütfen başka bir altyazı parçasını deneyin.",
                        exc=e)

def toggle_subtitles(player):
    try:
        current_visibility = player.mpv_player.sub_visibility
        player.mpv_player.sub_visibility = not current_visibility
        print(f"Subtitles visibility set to: {not current_visibility}")
    except Exception as e:
        print(f"Altyazıları gösterme/gizleme hatası: {e}")
        show_user_error(player, "Altyazı Değiştirilemedi",
                        "Altyazılar açılıp kapatılamadı. Lütfen tekrar deneyin.",
                        exc=e)

def seek_position(player, position):
    # Konum slider'ının programatik güncellemesinden gelen sinyalleri yoksay
    if getattr(player, '_updating_position_slider', False):
        return
    if player.duration > 0:
        try:
            seek_time = (position * player.duration) / 1000.0
            player.mpv_player.time_pos = float(seek_time)
        except Exception as e:
            print(f"Seeking error: {e}")

def seek_relative(player, seconds):
    try:
        if player.is_paused and not player.current_file:
            return
        player.mpv_player.check_core_alive()
        if player.mpv_player.time_pos is not None:
            player.mpv_player.seek(float(seconds), reference="relative")
            direction = "İleri" if seconds > 0 else "Geri"
            target = max(0, min(player.duration, (player.position or 0) + seconds))
            player.video_frame.show_osd(
                f"{direction}: {abs(seconds):g} saniye\n{format_time(target)}")
    except mpv.ShutdownError:
        print("MPV çekirdeği kapatılmış. Göreceli arama yapılamıyor.")
    except Exception as e:
        print(f"Relative seek error: {e}")


def seek_chapter(player, delta):
    """Bir sonraki/önceki medya bölümüne geçer."""
    try:
        chapters = player.mpv_player.chapter_list or []
        current = int(player.mpv_player.chapter)
        if not chapters or current < 0:
            player.video_frame.show_osd("Bölüm bilgisi yok")
            return
        target = max(0, min(len(chapters) - 1, current + delta))
        player.mpv_player.chapter = target
        title = chapters[target].get("title") or f"Bölüm {target + 1}"
        player.video_frame.show_osd(title)
    except Exception as e:
        print(f"Bölüm değiştirme hatası: {e}")

def play_pause(player):
    # Eğer video yüklenmemişse, dosya gezgini aç
    if not player.current_file:
        open_file(player)
        return

    if not player.is_paused:
        player.mpv_player.pause = True
        player.play_button.setIcon(player.play_icon)
        player.is_paused = True
    else:
        player.mpv_player.pause = False
        player.play_button.setIcon(player.pause_icon)
        player.is_paused = False

def stop(player):
    try:
        player.mpv_player.stop()
    except Exception as e:
        print(f"MPV durdurma hatası: {e}")
    player.play_button.setIcon(player.play_icon)
    player.is_paused = True
    player.duration = 0
    player.position = 0
    player._load_started_at = 0
    player._core_idle = False
    player._audio_menu_file = ""
    player._chapter_menu_file = ""
    player._pending_subs = []
    player.current_file = ""
    player.set_title()
    # duration'ı önce sıfırla ki slider sıfırlanması gereksiz seek tetiklemesin
    player._updating_position_slider = True
    player.position_slider.setValue(0)
    player._updating_position_slider = False
    if hasattr(player, 'current_time_label'):
        player.current_time_label.setText("00:00")
    if hasattr(player, 'total_time_label'):
        player.total_time_label.setText("00:00")
    player.video_frame.placeholder_label.show()

def set_volume(player, volume):
    try:
        # Üst/alt sınır: mpv volume 1000'e kadar izin verir; burada MAX_VOLUME ile sınırla
        volume = min(MAX_VOLUME, max(0, float(volume)))

        # 100 üstü amplifikasyon için mpv'nin üst sınırını yükselt (varsayılan 130)
        if volume > 100:
            player.mpv_player.volume_max = MAX_VOLUME

        player.mpv_player.volume = volume
        player.volume_label.setText(f"%{int(volume)}")
        if volume == 0:
            player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
            player.is_muted = True
            osd_text = "Sessiz"
        else:
            player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
            player.is_muted = False
            player.last_volume = volume
            osd_text = f"Ses: %{int(volume)}"
        if getattr(player, '_ui_ready', False):
            player.video_frame.show_osd(osd_text)
    except Exception as e:
        print(f"Set volume error: {e}")


def change_volume(player, delta):
    """Ses seviyesini mevcut değere göre değiştirir."""
    try:
        current = min(MAX_VOLUME, max(0, float(player.mpv_player.volume)))
        player.volume_slider.setValue(int(current + delta))
    except Exception as e:
        print(f"Ses değiştirme hatası: {e}")

def add_to_playlist(player):
    files, _ = QFileDialog.getOpenFileNames(
        player, "Oynatma Listesine Dosya Ekle", "", f"Medya Dosyaları ({MEDIA_EXTENSIONS})"
    )
    if files:
        for file in files:
            player.playlist.append(file)
            print(f"Oynatma listesine eklendi: {file}")

        # Eğer şu an bir dosya oynatılmıyorsa, ilk dosyayı oynat
        if not player.current_file and player.playlist:
            player.current_playlist_index = 0
            play_from_playlist(player, player.current_playlist_index)

def show_playlist(player):
    if not player.playlist:
        QMessageBox.information(player, "Oynatma Listesi", "Oynatma listesi boş.")
        return

    playlist_dialog = QDialog(player)
    playlist_dialog.setWindowTitle("Oynatma Listesi")
    playlist_dialog.setMinimumSize(400, 300)

    layout = QVBoxLayout(playlist_dialog)

    list_widget = QListWidget()
    sync_playlist_view(player, list_widget)

    layout.addWidget(list_widget)

    button_layout = QHBoxLayout()

    play_button = QPushButton("Oynat")
    play_button.clicked.connect(lambda: play_from_playlist(player, list_widget.currentRow()))

    remove_button = QPushButton("Kaldır")
    def remove_selected():
        remove_from_playlist(player, list_widget.currentRow())
        sync_playlist_view(player, list_widget)

    remove_button.clicked.connect(remove_selected)

    clear_button = QPushButton("Listeyi Temizle")
    def clear_list():
        clear_playlist(player)
        sync_playlist_view(player, list_widget)

    clear_button.clicked.connect(clear_list)

    button_layout.addWidget(play_button)
    button_layout.addWidget(remove_button)
    button_layout.addWidget(clear_button)

    layout.addLayout(button_layout)
    playlist_dialog.exec()


def sync_playlist_view(player, list_widget):
    """Playlist görünümünü tek kaynak olan player.playlist ile eşitler."""
    list_widget.clear()
    for index, file_path in enumerate(player.playlist):
        item = QListWidgetItem(os.path.basename(file_path))
        item.setToolTip(file_path)
        if index == player.current_playlist_index:
            item.setBackground(QColor(46, 155, 216, 60))
        list_widget.addItem(item)

def play_from_playlist(player, index):
    if 0 <= index < len(player.playlist):
        try:
            player.current_playlist_index = index
            file_path = player.playlist[index]
            player.duration = 0
            player.position = 0
            player._core_idle = False
            player._audio_menu_file = ""
            player._chapter_menu_file = ""
            player._pending_subs = []
            player.current_file = file_path
            player._load_started_at = time.time()
            player.mpv_player.play(file_path)
            player.play_button.setIcon(player.pause_icon)
            player.is_paused = False
            player.video_frame.placeholder_label.hide()
            player.set_title()
            player.add_recent_file(file_path)
            print(f"Oynatılıyor: {file_path}")
        except Exception as e:
            print(f"Oynatma listesinden oynatma hatası: {e}")
            show_user_error(player, "Dosya Açılamadı",
                            "Oynatma listesindeki dosya açılamadı. Dosya taşınmış "
                            "veya silinmiş olabilir.",
                            exc=e)

def remove_from_playlist(player, index):
    if 0 <= index < len(player.playlist):
        player.playlist.pop(index)
        if index == player.current_playlist_index:
            # Eğer oynatılan dosya kaldırıldıysa
            if player.playlist:
                # Listede başka dosyalar varsa, sıradakini oynat
                new_index = min(index, len(player.playlist) - 1)
                play_from_playlist(player, new_index)
            else:
                # Liste boşaldıysa oynatmayı durdur
                stop(player)
                player.current_playlist_index = -1
        elif index < player.current_playlist_index:
            # Eğer oynatılan dosyadan önceki bir dosya kaldırıldıysa, indeksi güncelle
            player.current_playlist_index -= 1

def clear_playlist(player):
    if player.current_file:
        stop(player)
    player.playlist = []
    player.current_playlist_index = -1

def save_playlist(player):
    if not player.playlist:
        QMessageBox.information(player, "Oynatma Listesi", "Kaydedilecek oynatma listesi yok.")
        return
    file_path, _ = QFileDialog.getSaveFileName(
        player, "Oynatma Listesini Kaydet", "", "Oynatma Listesi (*.m3u)"
    )
    if not file_path:
        return
    if not file_path.lower().endswith(".m3u"):
        file_path += ".m3u"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in player.playlist:
                f.write(f"#EXTINF:0,{os.path.basename(item)}\n")
                f.write(f"{item}\n")
        print(f"Oynatma listesi kaydedildi: {file_path}")
    except Exception as e:
        print(f"Oynatma listesi kaydetme hatası: {e}")
        show_user_error(player, "Kaydedilemedi",
                        "Oynatma listesi kaydedilemedi. Dosyanın yazılabileceği "
                        "bir konum seçmeyi deneyin.",
                        exc=e)

def load_playlist(player):
    file_path, _ = QFileDialog.getOpenFileName(
        player, "Oynatma Listesi Aç", "", "Oynatma Listesi (*.m3u)"
    )
    if not file_path:
        return
    try:
        entries = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # M3U listeleri mutlak veya liste dosyasına göreli yol içerebilir.
                    entry = line if os.path.isabs(line) else os.path.join(
                        os.path.dirname(file_path), line)
                    if os.path.isfile(entry):
                        entries.append(os.path.normpath(entry))
        if not entries:
            QMessageBox.warning(player, "Uyarı", "Oynatma listesinde geçerli dosya bulunamadı.")
            return
        if player.current_file:
            stop(player)
        player.playlist = entries
        player.current_playlist_index = -1
        play_from_playlist(player, 0)
        print(f"Oynatma listesi yüklendi ({len(entries)} dosya): {file_path}")
    except Exception as e:
        print(f"Oynatma listesi açma hatası: {e}")
        show_user_error(player, "Açılamadı",
                        "Oynatma listesi açılamadı. Dosya bozuk veya "
                        "okunamıyor olabilir.",
                        exc=e)

def take_screenshot(player):
    if not player.current_file:
        QMessageBox.warning(player, "Uyarı", "Ekran görüntüsü almak için bir video oynatılıyor olmalıdır.")
        return

    # Varsayılan kayıt klasörü: Masaüstü
    screenshots_folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    if not screenshots_folder:
        screenshots_folder = os.path.expanduser("~")

    # Milisaniye ve çakışma eki kullan: aynı saniyedeki görüntüler ezilmesin.
    timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss_zzz")
    screenshot_path = os.path.join(screenshots_folder, f"screenshot_{timestamp}.png")
    suffix = 2
    while os.path.exists(screenshot_path):
        screenshot_path = os.path.join(
            screenshots_folder, f"screenshot_{timestamp}_{suffix}.png")
        suffix += 1

    try:
        # Ekran görüntüsü al
        player.mpv_player.screenshot_to_file(screenshot_path)
        QMessageBox.information(player, "Başarılı", f"Ekran görüntüsü kaydedildi:\n{screenshot_path}")
    except Exception as e:
        print(f"Ekran görüntüsü alma hatası: {e}")
        show_user_error(player, "Ekran Görüntüsü Alınamadı",
                        "Ekran görüntüsü kaydedilemedi. Masaüstüne yazma iznini "
                        "ve boş alanı kontrol edin.",
                        exc=e)

def play_next(player):
    if player.playlist:
        if player.current_playlist_index < len(player.playlist) - 1:
            player.current_playlist_index += 1
            play_from_playlist(player, player.current_playlist_index)
        elif player.loop_playlist:
            play_from_playlist(player, 0)
        else:
            QMessageBox.information(player, "Oynatma Listesi", "Listenin sonuna ulaştınız.")
    else:
        QMessageBox.information(player, "Oynatma Listesi", "Oynatma listesi boş.")

def play_previous(player):
    if player.playlist and player.current_playlist_index > 0:
        player.current_playlist_index -= 1
        play_from_playlist(player, player.current_playlist_index)
    else:
        QMessageBox.information(player, "Oynatma Listesi", "Listenin başındasınız.")

def toggle_fullscreen(player):
    video_frame = player.video_frame
    if not video_frame.is_video_fullscreen:
        video_frame.enter_fullscreen()
    else:
        video_frame.exit_fullscreen()

def goto_time(player):
    if not player.current_file:
        QMessageBox.warning(player, "Uyarı", "Önce bir video dosyası açın.")
        return

    current_time = format_time(player.position)
    time_str, ok = QInputDialog.getText(
        player, "Zamana Git",
        "Zaman pozisyonunu girin (MM:SS veya HH:MM:SS formatında):",
        QLineEdit.EchoMode.Normal,
        current_time
    )

    if ok and time_str:
        try:
            # MM:SS / HH:MM:SS formatını saniyeye çevir
            total_seconds = time_to_seconds(time_str)

            # Geçerli süre kontrolü
            if total_seconds is not None and 0 <= total_seconds <= player.duration:
                player.mpv_player.time_pos = float(total_seconds)
            else:
                QMessageBox.warning(player, "Geçersiz Zaman",
                                    f"Zamanı MM:SS veya HH:MM:SS biçiminde ve "
                                    f"0 ile {int(player.duration)} saniye arasında girin.")
        except Exception as e:
            show_user_error(player, "Zamana Gidilemedi",
                            "Girilen zaman konumuna gidilemedi. Zamanı tekrar kontrol edin.",
                            exc=e)

def set_playback_speed(player, speed):
    try:
        if player.mpv_player:
            player.mpv_player.speed = float(speed)
            # Hız etiketini güncelle
            if hasattr(player, 'speed_label'):
                player.speed_label.setText(f"{speed}x")
            # Menü öğelerini güncelle
            for s, action in player.speed_actions.items():
                action.setChecked(s == speed)
    except Exception as e:
        print(f"Oynatma hızı değiştirme hatası: {e}")
        show_user_error(player, "Oynatma Hızı Değiştirilemedi",
                        "Oynatma hızı değiştirilemedi. Lütfen başka bir hız deneyin.",
                        exc=e)
