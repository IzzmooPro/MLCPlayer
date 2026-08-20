# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
from PyQt6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QMenu
)
from PyQt6.QtGui import QAction, QActionGroup, QColor
from PyQt6.QtCore import Qt
import os
import sys
from app import track_labels
from app.errors import show_user_error, safe_console
from app import i18n
from app.i18n import tr
from app.config import APP_VERSION, COPYRIGHT_YEAR, SUBTITLE_DEFAULTS
from app.updater import check_for_updates
from app.media_info import build_media_info, media_info_refresh_key
from app.media_controls import is_remote_media_url, safe_media_host
from app.subtitle_appearance_dialog import SubtitleAppearanceDialog
from app.subtitle_style import (atomic_apply, mpv_argb_to_qcolor,
                                qcolor_to_mpv_argb)
from app.utils import format_time

def setup_menu(player):
    menu_bar = player.menuBar()

    # Ortam menüsü
    file_menu = menu_bar.addMenu(tr("Ortam"))

    open_action = QAction(tr("Dosya Aç"), player)
    open_action.setShortcut("Ctrl+O")
    open_action.triggered.connect(player.open_file)
    file_menu.addAction(open_action)

    folder_action = QAction(tr("Klasör Aç"), player)
    folder_action.triggered.connect(player.open_folder)
    file_menu.addAction(folder_action)

    url_action = QAction(tr("URL'den Oynat"), player)
    url_action.setShortcut("Ctrl+U")
    url_action.triggered.connect(player.open_url)
    file_menu.addAction(url_action)

    subtitle_action = QAction(tr("Altyazı Ekle"), player)
    subtitle_action.triggered.connect(player.open_subtitle)
    file_menu.addAction(subtitle_action)

    file_menu.addSeparator()

    # Son açılanlar alt menüsü
    recent_menu = file_menu.addMenu(tr("Son Açılanlar"))
    player.recent_menu = recent_menu

    file_menu.addSeparator()

    # Medya Bilgisi: TEK eylem. Üç nokta menüsü `build_overflow_menu()` ile
    # menü çubuğunu miras aldığı için oraya AYRICA eklenmez.
    media_info_action = QAction(tr("Medya Bilgisi"), player)
    media_info_action.setEnabled(bool(getattr(player, "current_file", "")))
    media_info_action.triggered.connect(
        lambda _checked=False: player.show_media_info())
    file_menu.addAction(media_info_action)
    player.media_info_action = media_info_action

    exit_action = QAction(tr("Çıkış"), player)
    exit_action.setShortcut("Ctrl+Q")
    exit_action.triggered.connect(player.close)
    file_menu.addAction(exit_action)

    # Görünüm menüsü
    view_menu = menu_bar.addMenu(tr("Görünüm"))
    add_to_playlist_action = QAction(tr("Oynatma Listesine Ekle"), player)
    add_to_playlist_action.triggered.connect(player.add_to_playlist)
    view_menu.addAction(add_to_playlist_action)

    save_playlist_action = QAction(tr("Oynatma Listesini Kaydet"), player)
    save_playlist_action.triggered.connect(player.save_playlist)
    view_menu.addAction(save_playlist_action)

    load_playlist_action = QAction(tr("Oynatma Listesi Aç"), player)
    load_playlist_action.triggered.connect(player.load_playlist)
    view_menu.addAction(load_playlist_action)

    show_playlist_action = QAction(tr("Oynatma Listesini Göster"), player)
    show_playlist_action.setShortcut("Ctrl+P")
    show_playlist_action.triggered.connect(player.show_playlist)
    view_menu.addAction(show_playlist_action)

    # Görüntü menüsü
    video_menu = menu_bar.addMenu(tr("Görüntü"))
    screenshot_action = QAction(tr("Ekran Görüntüsü Al"), player)
    screenshot_action.setShortcut("Ctrl+S")
    screenshot_action.triggered.connect(player.take_screenshot)
    video_menu.addAction(screenshot_action)

    fullscreen_action = QAction(tr("Tam Ekran"), player)
    fullscreen_action.setShortcut("F")
    fullscreen_action.triggered.connect(player.toggle_fullscreen)
    video_menu.addAction(fullscreen_action)

    video_settings_action = QAction(tr("Video Ayarları"), player)
    video_settings_action.triggered.connect(player.setup_video_adjustments)
    video_menu.addAction(video_settings_action)

    # Oynatma menüsü
    play_menu = menu_bar.addMenu(tr("Oynatma"))

    play_pause_action = QAction(tr("Oynat/Duraklat"), player)
    play_pause_action.setShortcut("Space")
    play_pause_action.triggered.connect(player.play_pause)
    play_menu.addAction(play_pause_action)

    stop_action = QAction(tr("Durdur"), player)
    stop_action.triggered.connect(player.stop)
    play_menu.addAction(stop_action)

    play_menu.addSeparator()

    next_track_action = QAction(tr("Sonraki Parça"), player)
    next_track_action.setShortcut("Ctrl+Right")
    next_track_action.triggered.connect(player.play_next)
    play_menu.addAction(next_track_action)

    prev_track_action = QAction(tr("Önceki Parça"), player)
    prev_track_action.setShortcut("Ctrl+Left")
    prev_track_action.triggered.connect(player.play_previous)
    play_menu.addAction(prev_track_action)

    chapter_menu = play_menu.addMenu(tr("Bölüm"))
    previous_chapter_action = QAction(tr("Önceki Bölüm"), player)
    previous_chapter_action.triggered.connect(lambda: player.seek_chapter(-1))
    chapter_menu.addAction(previous_chapter_action)
    next_chapter_action = QAction(tr("Sonraki Bölüm"), player)
    next_chapter_action.triggered.connect(lambda: player.seek_chapter(1))
    chapter_menu.addAction(next_chapter_action)
    chapter_refresh_action = QAction(tr("Bölümleri Yenile"), player)
    chapter_refresh_action.triggered.connect(player.refresh_chapters)
    chapter_menu.addAction(chapter_refresh_action)
    player.chapter_menu = chapter_menu

    play_menu.addSeparator()

    # Oynatma modları
    loop_file_action = QAction(tr("Tek Dosyayı Tekrarla"), player)
    loop_file_action.setCheckable(True)
    loop_file_action.setChecked(player.loop_file)
    loop_file_action.toggled.connect(player.set_loop_file)
    play_menu.addAction(loop_file_action)

    loop_playlist_action = QAction(tr("Listeyi Tekrarla"), player)
    loop_playlist_action.setCheckable(True)
    loop_playlist_action.setChecked(player.loop_playlist)
    loop_playlist_action.toggled.connect(player.set_loop_playlist)
    play_menu.addAction(loop_playlist_action)

    shuffle_action = QAction(tr("Karışık Oynat"), player)
    shuffle_action.setCheckable(True)
    shuffle_action.setChecked(player.shuffle)
    shuffle_action.toggled.connect(player.toggle_shuffle)
    play_menu.addAction(shuffle_action)

    play_menu.addSeparator()

    # Hız ayarı alt menüsü
    speed_menu = play_menu.addMenu(tr("Oynatma Hızı"))

    speed_actions = {}
    for speed in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        speed_action = QAction(f"{speed}x", player)
        speed_action.setCheckable(True)
        if speed == 1.0:
            speed_action.setChecked(True)
        speed_action.triggered.connect(lambda checked, s=speed: player.set_playback_speed(s))
        speed_menu.addAction(speed_action)
        speed_actions[speed] = speed_action

    player.speed_actions = speed_actions  # Oynatıcıda saklıyoruz

    # Ses menüsü
    audio_menu = menu_bar.addMenu(tr("Ses"))
    volume_up_action = QAction(tr("Sesi Aç"), player)
    volume_up_action.setShortcut("Up")
    volume_up_action.triggered.connect(lambda: player.change_volume(5))
    audio_menu.addAction(volume_up_action)

    volume_down_action = QAction(tr("Sesi Kıs"), player)
    volume_down_action.setShortcut("Down")
    volume_down_action.triggered.connect(lambda: player.change_volume(-5))
    audio_menu.addAction(volume_down_action)

    mute_action = QAction(tr("Sesi Kapat/Aç"), player)
    mute_action.setShortcut("M")
    mute_action.triggered.connect(player.toggle_mute)
    audio_menu.addAction(mute_action)
    audio_menu.addSeparator()

    # "Ses Parçası" = videonun içindeki ses akışları (İngilizce/Türkçe/yorum).
    # "Ses Çıkışı"  = hoparlör/kulaklık/HDMI gibi aygıtlar. İkisi ayrı kavram.
    # Elle yenileme satırları kaldırıldı: parçalar yeni medyada, çıkışlar
    # açılışta otomatik doldurulur.
    audio_track_menu = audio_menu.addMenu(tr("Ses Parçası"))
    player.audio_track_menu = audio_track_menu

    audio_device_menu = audio_menu.addMenu(tr("Ses Çıkışı"))
    player.audio_device_menu = audio_device_menu
    # NOT: Ses çıkışları BURADA algılanmaz — menü kurulumu MPV hazır olmadan
    # önce çalışır. Algılama `MPVPlayer.init_mpv_player()` sonrasında bir kez
    # yapılır; menü açılışında yeniden tarama YOKTUR.

    # Alt Yazı menüsü
    subtitle_menu = menu_bar.addMenu(tr("Alt Yazı"))
    subtitle_add_menu_action = QAction(tr("Altyazı Ekle"), player)
    subtitle_add_menu_action.setShortcut("Alt+E")
    subtitle_add_menu_action.triggered.connect(player.open_subtitle)
    subtitle_menu.addAction(subtitle_add_menu_action)

    # Altyazı Merkezi: yerel dosya eklemenin hemen ardından, indirme yolu.
    # Kısayol verilmez; mevcut kısayollarla çakışma üretmez.
    from app.config import SUBTITLE_SEARCH_UI_ENABLED
    subtitle_find_action = QAction(tr("Altyazı Bul…"), player)
    subtitle_find_action.triggered.connect(player.open_subtitle_center)
    subtitle_find_action.setVisible(SUBTITLE_SEARCH_UI_ENABLED)
    subtitle_menu.addAction(subtitle_find_action)
    player.subtitle_find_action = subtitle_find_action

    subtitle_toggle_action = QAction(tr("Altyazıları Göster/Gizle"), player)
    subtitle_toggle_action.setShortcut("S")
    subtitle_toggle_action.triggered.connect(player.toggle_subtitles)
    subtitle_menu.addAction(subtitle_toggle_action)

    subtitle_track_menu = subtitle_menu.addMenu(tr("Altyazı Parçası"))
    player.subtitle_track_menu = subtitle_track_menu

    subtitle_settings_menu_action = QAction(tr("Altyazı Ayarları"), player)
    subtitle_settings_menu_action.triggered.connect(player.show_subtitle_settings)
    subtitle_menu.addAction(subtitle_settings_menu_action)

    # Gezinim menüsü
    nav_menu = menu_bar.addMenu(tr("Gezinim"))

    forward_5s_action = QAction(tr("5 Saniye İleri"), player)
    forward_5s_action.setShortcut("Right")
    forward_5s_action.triggered.connect(lambda: player.seek_relative(5))
    nav_menu.addAction(forward_5s_action)

    backward_5s_action = QAction(tr("5 Saniye Geri"), player)
    backward_5s_action.setShortcut("Left")
    backward_5s_action.triggered.connect(lambda: player.seek_relative(-5))
    nav_menu.addAction(backward_5s_action)

    forward_30s_action = QAction(tr("30 Saniye İleri"), player)
    forward_30s_action.setShortcut("Shift+Right")
    forward_30s_action.triggered.connect(lambda: player.seek_relative(30))
    nav_menu.addAction(forward_30s_action)

    backward_30s_action = QAction(tr("30 Saniye Geri"), player)
    backward_30s_action.setShortcut("Shift+Left")
    backward_30s_action.triggered.connect(lambda: player.seek_relative(-30))
    nav_menu.addAction(backward_30s_action)

    nav_menu.addSeparator()

    goto_time_action = QAction(tr("Zamana Git..."), player)
    goto_time_action.setShortcut("Ctrl+G")
    goto_time_action.triggered.connect(player.goto_time)
    nav_menu.addAction(goto_time_action)

    # Araçlar menüsü
    tools_menu = menu_bar.addMenu(tr("Araçlar"))

    video_adj_action = QAction(tr("Video Ayarları"), player)
    video_adj_action.triggered.connect(player.setup_video_adjustments)
    tools_menu.addAction(video_adj_action)

    # Dil: varsayılan Windows'un dilidir; kullanıcı buradan sabitleyebilir.
    # Değişiklik yeniden başlatmada geçerli olur (bkz. app/i18n.py).
    tools_menu.addMenu(build_language_menu(player))

    # Yardım menüsü
    help_menu = menu_bar.addMenu(tr("Yardım"))

    shortcuts_action = QAction(tr("Klavye Kısayolları"), player)
    shortcuts_action.triggered.connect(player.show_shortcuts)
    help_menu.addAction(shortcuts_action)

    log_action = QAction(tr("Günlük Yönetimi"), player)
    log_action.triggered.connect(player.show_log_management)
    help_menu.addAction(log_action)

    update_action = QAction(tr("Güncellemeleri Denetle"), player)
    update_action.triggered.connect(lambda: check_for_updates(player))
    help_menu.addAction(update_action)

    about_action = QAction(tr("Hakkında"), player)
    about_action.triggered.connect(player.show_about)
    help_menu.addAction(about_action)

    # VLC benzeri, sabit ve anlaşılır sekme sırası.
    #
    # Sıra menü NESNELERİNDEN kurulur, GÖRÜNEN metinden değil: başlıklar
    # `tr()` ile çevrildiği için İngilizce arayüzde metinle geri arama
    # hiçbir menüyü bulamıyor ve sıralama sessizce uygulanmıyordu
    # (`tests/test_menu_order_translation_regressions.py`).
    menu_order = [file_menu, play_menu, audio_menu, video_menu,
                  subtitle_menu, tools_menu, nav_menu, view_menu, help_menu]
    for menu in menu_order:
        action = menu.menuAction()
        menu_bar.removeAction(action)
        menu_bar.addAction(action)


def _mpv_color_to_qcolor(value, fallback):
    """mpv'nin canonical #AARRGGBB rengini QColor'a çevirir."""
    return mpv_argb_to_qcolor(value, fallback)


def _qcolor_to_mpv(color):
    """QColor → mpv'nin beklediği #AARRGGBB."""
    return qcolor_to_mpv_argb(color)


def _apply_subtitle_style(player, chosen):
    """`atomic_apply()` + güvenli bandın YENİDEN uygulanması.

    `atomic_apply()` kullanıcının HAM `sub_pos` değerini MPV'ye yazar;
    ASS altyazıda güvenli bant efektif bir `sub_pos` gerektirdiği için
    başarılı yazımdan sonra bant önbelleği geçersiz kılınıp yeniden
    senkronlanır. Kullanıcının KAYITLI tercihi değişmez.
    """
    ok, error = atomic_apply(player.mpv_player, player.settings, chosen)
    if ok:
        try:
            player.video_frame.invalidate_subtitle_band()
            player.video_frame.sync_subtitle_safe_band()
        except Exception as exc:
            safe_console(f"Could not refresh the subtitle safe band: {exc}")
    return ok, error


def show_subtitle_settings(player):
    """Kompakt Altyazı Ayarları penceresini açar (ince entegrasyon noktası).

    Görsel yerleşim `app/subtitle_appearance_dialog.py`, kalıcılık
    sözleşmesi `app/subtitle_style.py` içindedir. Burada yalnız ikisi
    birbirine bağlanır.
    """
    def read_number(name, default):
        try:
            return float(getattr(player.mpv_player, name))
        except Exception:
            return float(default)

    values = {name: read_number(name, SUBTITLE_DEFAULTS[name])
              for name in ("sub_delay", "sub_scale", "sub_pos",
                           "sub_border_size")}
    for key in ("sub_color", "sub_back_color", "sub_border_color"):
        values[key] = _mpv_color_to_qcolor(
            getattr(player.mpv_player, key, ""), SUBTITLE_DEFAULTS[key])
    try:
        tracks = list(player.mpv_player.track_list or [])
    except Exception:
        tracks = []

    dialog = SubtitleAppearanceDialog(
        player, values=values, track_list=tracks,
        apply_callback=lambda chosen: _apply_subtitle_style(player, chosen),
        error_reporter=lambda title, message, exc=None: show_user_error(
            player, title, message, exc=exc))
    dialog.exec()


# Ürün politikası: en fazla 10 son açılan girdi gösterilir
# (`MPVPlayer.add_recent_file` de listeyi 10 ile sınırlar).
RECENT_MENU_LIMIT = 10


def recent_entry_label(path):
    """Son açılan kaydın kullanıcıya gösterilecek adı.

    UZAK adreste YALNIZ güvenli `host[:port]` gösterilir: `userinfo`,
    `query`, `fragment`, yol ve video kimliği menüye HİÇ çıkmaz. Yerel
    dosyada mevcut basename davranışı korunur.
    """
    if is_remote_media_url(path):
        return safe_media_host(path) or tr("Bağlantı")
    name = os.path.basename(str(path).split("?", 1)[0].rstrip("/\\"))
    return name or str(path)


def recent_entry_hint(path):
    """Tooltip/statusTip metni. Uzak adreste tam hedef GÖRÜNMEZ."""
    if is_remote_media_url(path):
        return safe_media_host(path) or tr("Bağlantı")
    return str(path)


def populate_recent_menu(player, menu, owner=None):
    """`Son Açılanlar` menüsünü doldurur (ana menü + sağ-tık ORTAK).

    Aynı `player.recent_files` modeli okunur ama her menü KENDİ
    QAction'larını üretir; aynı nesne iki menü arasında taşınmaz. Tam yol
    yalnızca `data()`/tooltip'te taşınır ve girdi `p=path` ile bağlanır
    (lambda late-binding YOK).
    """
    clear_dynamic_menu(menu)
    recent_files = list(getattr(player, "recent_files", None) or [])
    if not recent_files:
        empty_action = QAction(tr("Son açılan dosya yok"), owner or player)
        empty_action.setEnabled(False)
        menu.addAction(empty_action)
        return
    # Eksik yerel dosyayı temizleyen ürün yolu; test double'ları yalnız
    # `open_path` tanımlayabilir.
    open_entry = getattr(player, "open_recent", None) or player.open_path
    for path in recent_files[:RECENT_MENU_LIMIT]:
        action = QAction(recent_entry_label(path), owner or player)
        hint = recent_entry_hint(path)
        action.setToolTip(hint)
        action.setStatusTip(hint)
        # `data()` YALNIZ bellekte yasar; aynı oturumda yeniden açmak için
        # gerçek hedefi taşır ve hiçbir görünür alana yazılmaz.
        action.setData(path)
        action.triggered.connect(lambda checked, p=path: open_entry(p))
        menu.addAction(action)


def update_recent_menu(player):
    populate_recent_menu(player, player.recent_menu)

def setup_video_adjustments(player):
    video_adj_dialog = QDialog(player)
    video_adj_dialog.setWindowTitle(tr("Video Ayarları"))
    video_adj_dialog.setMinimumSize(360, 260)

    layout = QVBoxLayout(video_adj_dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(20, 20, 20, 20)

    def read_setting(name):
        # Slaytı mevcut mpv değeriyle başlat (yeniden açıldığında bile doğru olsun)
        try:
            return int(getattr(player.mpv_player, name) or 0)
        except Exception:
            return 0

    def set_setting(name, value):
        try:
            setattr(player.mpv_player, name, value)
        except Exception as e:
            safe_console(f"{name} setting could not be applied: {e}")

    def reset_settings():
        # valueChanged sinyaline güvenme: slayt zaten 0 ise sinyal tetiklenmez,
        # bu yüzden mpv özelliğini her zaman doğrudan 0 yap
        for name in ("brightness", "contrast", "saturation", "gamma"):
            set_setting(name, 0)
        brightness_slider.setValue(0)
        contrast_slider.setValue(0)
        saturation_slider.setValue(0)
        gamma_slider.setValue(0)

    # Parlaklık
    brightness_layout = QHBoxLayout()
    brightness_label = QLabel(tr("Parlaklık:"))
    brightness_slider = QSlider(Qt.Orientation.Horizontal)
    brightness_slider.setRange(-100, 100)
    brightness_slider.setValue(read_setting("brightness"))
    brightness_slider.valueChanged.connect(lambda v: set_setting("brightness", v))
    brightness_layout.addWidget(brightness_label)
    brightness_layout.addWidget(brightness_slider)

    # Kontrast
    contrast_layout = QHBoxLayout()
    contrast_label = QLabel(tr("Kontrast:"))
    contrast_slider = QSlider(Qt.Orientation.Horizontal)
    contrast_slider.setRange(-100, 100)
    contrast_slider.setValue(read_setting("contrast"))
    contrast_slider.valueChanged.connect(lambda v: set_setting("contrast", v))
    contrast_layout.addWidget(contrast_label)
    contrast_layout.addWidget(contrast_slider)

    # Doygunluk
    saturation_layout = QHBoxLayout()
    saturation_label = QLabel(tr("Doygunluk:"))
    saturation_slider = QSlider(Qt.Orientation.Horizontal)
    saturation_slider.setRange(-100, 100)
    saturation_slider.setValue(read_setting("saturation"))
    saturation_slider.valueChanged.connect(lambda v: set_setting("saturation", v))
    saturation_layout.addWidget(saturation_label)
    saturation_layout.addWidget(saturation_slider)

    # Gamma
    gamma_layout = QHBoxLayout()
    gamma_label = QLabel(tr("Gamma:"))
    gamma_slider = QSlider(Qt.Orientation.Horizontal)
    gamma_slider.setRange(-100, 100)
    gamma_slider.setValue(read_setting("gamma"))
    gamma_slider.valueChanged.connect(lambda v: set_setting("gamma", v))
    gamma_layout.addWidget(gamma_label)
    gamma_layout.addWidget(gamma_slider)

    # Butonlar
    button_layout = QHBoxLayout()
    button_layout.setSpacing(8)
    reset_button = QPushButton(tr("Sıfırla"))
    reset_button.clicked.connect(reset_settings)
    close_button = QPushButton(tr("Kapat"))
    close_button.setDefault(True)
    close_button.clicked.connect(video_adj_dialog.close)
    button_layout.addWidget(reset_button)
    button_layout.addStretch(1)
    button_layout.addWidget(close_button)

    # Düzenleri yerleştir
    layout.addLayout(brightness_layout)
    layout.addLayout(contrast_layout)
    layout.addLayout(saturation_layout)
    layout.addLayout(gamma_layout)
    layout.addLayout(button_layout)

    video_adj_dialog.exec()

def clear_dynamic_menu(menu):
    """Dinamik menüyü TAMAMEN boşaltır.

    Eskiden `actions()[1:]` kullanılıyordu ("ilk satır sabit yenileme
    eylemidir" varsayımı). Yenileme satırları kaldırıldığı için bu varsayım
    artık geçersizdir ve bayat satır bırakırdı.
    """
    for action in list(menu.actions()):
        menu.removeAction(action)


def _exclusive_group(player, menu, attribute):
    """Menü boyunca YAŞAYAN exclusive seçim grubu.

    Grup player'a bağlanır; menü yenilendiğinde yenisi kurulur ve eskisi
    action'larıyla birlikte bırakılır.
    """
    group = QActionGroup(menu)
    group.setExclusive(True)
    setattr(player, attribute, group)
    return group


def refresh_audio_tracks(player):
    """Ses PARÇALARI (videonun içindeki ses akışları) menüsünü doldurur."""
    menu = player.audio_track_menu
    clear_dynamic_menu(menu)
    if not player.current_file:
        empty_action = QAction(tr("Önce bir video açın."), player)
        empty_action.setEnabled(False)
        menu.addAction(empty_action)
        return

    try:
        player.mpv_player.command('rescan-external-files')
        track_list = player.mpv_player.track_list or []
        audio_tracks = [track for track in track_list
                        if isinstance(track, dict)
                        and track.get('type') == 'audio']
        current_aid = player.mpv_player.aid
    except Exception as e:
        safe_console(f"Audio track listing error: {e}")
        error_action = QAction(tr("Ses parçaları yüklenemedi"), player)
        error_action.setEnabled(False)
        menu.addAction(error_action)
        return

    if not audio_tracks:
        no_audio_action = QAction(tr("Ses parçası bulunamadı"), player)
        no_audio_action.setEnabled(False)
        menu.addAction(no_audio_action)
        return

    group = _exclusive_group(player, menu, "_audio_track_group")
    for track, label in zip(audio_tracks,
                            track_labels.audio_track_labels(audio_tracks)):
        track_id = track.get('id')
        action = QAction(label, player)
        action.setCheckable(True)
        action.setChecked(track_id == current_aid)
        # Teknik kimlik yalnızca veri tarafında; kullanıcı metnine YAZILMAZ.
        action.setData(track_id)
        full = _text_or_empty(track.get("title"))
        if full and full not in label:
            action.setToolTip(full)
            action.setStatusTip(full)
        action.triggered.connect(
            lambda checked, aid=track_id: player.select_audio_track(aid))
        group.addAction(action)
        menu.addAction(action)


def _text_or_empty(value):
    return value.strip() if isinstance(value, str) else ""

def select_audio_track(player, aid):
    try:
        player.mpv_player.aid = aid
        safe_console(f"Selected audio track ID: {aid}")
    except Exception as e:
        safe_console(f"Audio track selection error: {e}")
        show_user_error(player, tr("Ses Kanalı Seçilemedi"),
                        tr("Ses kanalı değiştirilemedi. Lütfen başka bir "
                           "kanal deneyin."),
                        exc=e)


def detect_audio_devices(player):
    """Gerçek ses çıkışlarını BİR KEZ algılar ve player'a önbelleğe alır.

    Menüler bu önbellekten okur; menü AÇILIŞINDA yeni tarama yapılmaz.
    Dönen liste `(name, description)` çiftlerinden oluşur. Okunamazsa
    `None` döner (menü güvenli bir disabled satır gösterir).
    """
    devices = []
    try:
        raw = player.mpv_player.audio_device_list or []
    except Exception as e:
        # MPV henüz hazır olmayabilir (menü kurulumu init'ten ÖNCE çalışır).
        # Başarısızlık ÖNBELLEĞE ALINMAZ ki sonraki erişim yeniden denesin.
        safe_console(f"Audio device listing error: {e}")
        return None
    for device in raw:
        if not isinstance(device, dict):
            continue
        name = device.get("name", "")
        if not name or name == "auto":
            # `auto` gerçek bir aygıt değil, MPV pseudo-device'ıdır.
            continue
        if sys.platform == "win32" and not str(name).startswith("wasapi/"):
            # OpenAL/SDL backend'leri Windows'ta gerçek çıkış aygıtı değildir.
            continue
        devices.append((name, device.get("description") or name))
    player._audio_devices = devices
    return devices


def audio_devices(player):
    """Önbellekteki ses çıkışları; hiç algılanmadıysa bir kez algılar."""
    cached = getattr(player, "_audio_devices", "missing")
    if cached == "missing":
        return detect_audio_devices(player)
    return cached


def populate_audio_device_menu(player, menu, on_select=None, owner=None):
    """Ses Çıkışı menüsünü ÖNBELLEKTEN doldurur (ana menü + sağ-tık ortak).

    Her menü KENDİ QAction'larını üretir; aynı nesne iki menü arasında
    taşınmaz.
    """
    clear_dynamic_menu(menu)
    devices = audio_devices(player)
    if devices is None:
        error_action = QAction(tr("Ses çıkışları yüklenemedi"), owner or player)
        error_action.setEnabled(False)
        menu.addAction(error_action)
        return
    if not devices:
        empty_action = QAction(tr("Ses çıkışı bulunamadı"), owner or player)
        empty_action.setEnabled(False)
        menu.addAction(empty_action)
        return
    try:
        current = player.mpv_player.audio_device
    except Exception:
        current = None
    select = on_select or (lambda value: select_audio_device(player, value))
    group = QActionGroup(menu)
    group.setExclusive(True)
    for name, description in devices:
        action = QAction(description, owner or player)
        action.setCheckable(True)
        action.setChecked(name == current)
        action.setData(name)
        action.triggered.connect(lambda checked, value=name: select(value))
        group.addAction(action)
        menu.addAction(action)


def refresh_audio_devices(player):
    """Ses ÇIKIŞLARI menüsünü yeniden algılayıp doldurur (açılışta bir kez)."""
    detect_audio_devices(player)
    populate_audio_device_menu(player, player.audio_device_menu)


def select_audio_device(player, name):
    try:
        player.mpv_player.audio_device = name
        player.video_frame.show_osd(tr("Ses aygıtı değiştirildi"))
    except Exception as e:
        show_user_error(player, tr("Ses Aygıtı Değiştirilemedi"),
                        tr("Ses aygıtı değiştirilemedi. Lütfen başka bir "
                           "aygıt deneyin."),
                        exc=e)


def refresh_subtitle_tracks(player):
    """Altyazı PARÇALARI menüsünü ortak etiket üreticisiyle doldurur."""
    menu = player.subtitle_track_menu
    clear_dynamic_menu(menu)
    if not player.current_file:
        empty_action = QAction(tr("Önce bir video açın."), player)
        empty_action.setEnabled(False)
        menu.addAction(empty_action)
        return
    try:
        player.mpv_player.command("rescan-external-files")
        tracks = [track for track in (player.mpv_player.track_list or [])
                  if isinstance(track, dict) and track.get("type") == "sub"]
        current_sid = player.mpv_player.sid
    except Exception as e:
        safe_console(f"Subtitle track listing error: {e}")
        error_action = QAction(tr("Altyazı parçaları yüklenemedi"), player)
        error_action.setEnabled(False)
        menu.addAction(error_action)
        return

    if not tracks:
        empty_action = QAction(tr("Altyazı parçası bulunamadı"), player)
        empty_action.setEnabled(False)
        menu.addAction(empty_action)
        return

    group = _exclusive_group(player, menu, "_subtitle_track_group")
    for track, label in zip(tracks,
                            track_labels.subtitle_track_labels(tracks)):
        track_id = track.get("id")
        action = QAction(label, player)
        action.setCheckable(True)
        action.setChecked(track_id == current_sid)
        action.setData(track_id)
        full = _text_or_empty(track.get("title")) or _text_or_empty(
            track.get("external-filename"))
        if full and full not in label:
            action.setToolTip(full)
            action.setStatusTip(full)
        action.triggered.connect(
            lambda checked, sid=track_id: player.select_subtitle_language(sid))
        group.addAction(action)
        menu.addAction(action)


def refresh_chapters(player):
    for action in player.chapter_menu.actions()[2:]:
        player.chapter_menu.removeAction(action)
    try:
        chapters = player.mpv_player.chapter_list or []
        if not chapters:
            empty_action = QAction(tr("Bölüm bulunamadı"), player)
            empty_action.setEnabled(False)
            player.chapter_menu.addAction(empty_action)
        else:
            for index, chapter in enumerate(chapters):
                title = (chapter.get("title")
                         or f"{tr('Bölüm')} {index + 1:02d}")
                start = chapter.get("time")
                label = f"{title} ({format_time(start)})" if start is not None else title
                action = QAction(label, player)
                action.triggered.connect(
                    lambda checked, chapter_index=index: select_chapter(player, chapter_index))
                player.chapter_menu.addAction(action)
        refresh_action = QAction(tr("Bölümleri Yenile"), player)
        refresh_action.triggered.connect(player.refresh_chapters)
        player.chapter_menu.addAction(refresh_action)
    except Exception as e:
        safe_console(f"Could not list the chapters: {e}")


def select_chapter(player, index):
    try:
        player.mpv_player.chapter = index
        chapters = player.mpv_player.chapter_list or []
        title = chapters[index].get("title") if index < len(chapters) else None
        player.video_frame.show_osd(
            title or f"{tr('Bölüm')} {index + 1:02d}")
    except Exception as e:
        safe_console(f"Could not select the chapter: {e}")

def show_log_management(player):
    """Ayrı "Günlük Yönetimi" penceresini açar (ince entegrasyon noktası).

    Saklama politikası ve temizleme sözleşmesi `app/errors.py`,
    yerleşim `app/log_management_dialog.py` içindedir.
    """
    from app.log_management_dialog import LogManagementDialog

    dialog = LogManagementDialog(player)
    dialog.exec()


def media_info_property_reader(player):
    """python-mpv'nin GERÇEK okuma yolu.

    Kurulu `mpv.py` kaynağında `MPV.__getattr__` yalnızca
    `self._get_property(_py_to_mpv(name), ...)` çağırır; yani asıl API
    `_get_property(<mpv adı>)` metodudur ve tire içeren adı doğrudan alır.
    Tahmini `getattr` yerine önce o kullanılır; bulunmazsa öznitelik yolu
    yedek kalır. Hangi anahtarların okunacağına BUILDER karar verir.
    """
    mpv_player = getattr(player, "mpv_player", None)
    if mpv_player is None:
        return None
    getter = getattr(mpv_player, "_get_property", None)

    def read(name):
        if callable(getter):
            return getter(name)
        return getattr(mpv_player, str(name).replace("-", "_"))

    return read


def _media_info_inputs(player):
    """Snapshot/anahtar girdileri; okuma hatası boş listeye düşer."""
    try:
        tracks = list(getattr(getattr(player, "mpv_player", None),
                              "track_list", None) or [])
    except Exception:
        tracks = []
    return (getattr(player, "current_file", ""),
            getattr(player, "duration", 0), tracks)


def _live_media_info_dialog(player):
    """Silinmiş C++ sarmalayıcısını HAM hata üretmeden ayırt eder."""
    dialog = player.__dict__.get("_media_info_dialog")
    if dialog is None:
        return None
    try:
        dialog.isVisible()
    except RuntimeError:
        _forget_media_info(player, dialog)
        return None
    return dialog


def _forget_media_info(player, dialog):
    """YALNIZ hâlâ aynı pencereyse temizler.

    Eski pencerenin geç gelen `finished`/`destroyed` sinyali, yerine açılmış
    YENİ pencerenin referansını silmemelidir.
    """
    if player.__dict__.get("_media_info_dialog") is not dialog:
        return
    player._media_info_dialog = None
    player._media_info_refresh_key = None


def show_media_info(player):
    """Medya Bilgisi'nin TEK açma noktası (menü, sağ-tık ve facade).

    Modeless ve tekildir: açık pencere varken ikinci çağrı yeni pencere
    üretmez, gerekirse içeriği tazeler ve pencereyi öne alır. Medya yoksa
    pencere OLUŞTURULMAZ.
    """
    from app.media_info_dialog import MediaInfoDialog

    reader = media_info_property_reader(player)
    current_file, duration, tracks = _media_info_inputs(player)
    try:
        snapshot = build_media_info(current_file, duration, tracks, reader)
    except Exception:
        snapshot = None
    if snapshot is None:
        close_media_info(player)
        return None
    dialog = _live_media_info_dialog(player)
    if dialog is None:
        dialog = MediaInfoDialog(snapshot, parent=player)
        player._media_info_dialog = dialog
        # `finished` kapanışta ANINDA gelir; `destroyed` yıkımda gelir.
        # İkisi de kimlik korumalı olduğu için tekrar çalışması zararsızdır.
        dialog.finished.connect(
            lambda _code=0, target=dialog: _forget_media_info(player, target))
        dialog.destroyed.connect(
            lambda _obj=None, target=dialog: _forget_media_info(player, target))
    else:
        dialog.set_snapshot(snapshot)
    try:
        player._media_info_refresh_key = media_info_refresh_key(
            current_file, duration, tracks, reader)
    except Exception:
        player._media_info_refresh_key = None
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def refresh_media_info(player):
    """Açık pencereyi YALNIZ gerçekten değiştiyse tazeler.

    Pencere kapalıysa hiçbir mpv property'si OKUNMAZ: genel oynatma
    döngüsüne maliyet eklenmez. Yeni timer veya observer kurulmaz; çağrı
    mevcut `update_ui` turundan gelir.
    """
    dialog = _live_media_info_dialog(player)
    if dialog is None:
        return False
    reader = media_info_property_reader(player)
    current_file, duration, tracks = _media_info_inputs(player)
    try:
        key = media_info_refresh_key(current_file, duration, tracks, reader)
    except Exception:
        return False
    if key == player.__dict__.get("_media_info_refresh_key"):
        return False
    try:
        snapshot = build_media_info(current_file, duration, tracks, reader)
    except Exception:
        snapshot = None
    if snapshot is None:
        # Eski medyayı göstermeye DEVAM ETMEZ.
        close_media_info(player)
        return False
    dialog.set_snapshot(snapshot)
    player._media_info_refresh_key = key
    return True


def close_media_info(player):
    """Kapanış yolu: idempotent ve sessiz. Worker/thread yoktur."""
    dialog = player.__dict__.get("_media_info_dialog")
    player._media_info_dialog = None
    player._media_info_refresh_key = None
    if dialog is None:
        return False
    try:
        dialog.close()
    except Exception:
        pass
    return True


def show_shortcuts(player):
    shortcut_dialog = QDialog(player)
    shortcut_dialog.setWindowTitle(tr("Klavye Kısayolları"))
    shortcut_dialog.setMinimumSize(500, 350)

    layout = QVBoxLayout(shortcut_dialog)

    # HTML tablosu METİNDEN değil VERİDEN kurulur. Tek bir dev HTML bloğu
    # çevirmene etiketleri de teslim ederdi; bozuk bir `<td>` bütün
    # pencereyi bozar. Tuş adları (`Ctrl+O`) çevrilmez, YÖN adları
    # (`Sağ Ok`) çevrilir.
    shortcut_rows = [
        ("Space", tr("Oynat/Duraklat")),
        ("Ctrl+O", tr("Dosya Aç")),
        ("Ctrl+U", tr("URL'den Oynat")),
        ("Ctrl+S", tr("Ekran Görüntüsü Al")),
        ("Ctrl+P", tr("Oynatma Listesini Göster")),
        ("Ctrl+Q", tr("Çıkış")),
        ("F", tr("Tam Ekran")),
        ("Esc", tr("Tam Ekrandan Çık")),
        (tr("Sağ Ok"), tr("5 Saniye İleri")),
        (tr("Sol Ok"), tr("5 Saniye Geri")),
        (f"Shift+{tr('Sağ Ok')}", tr("30 Saniye İleri")),
        (f"Shift+{tr('Sol Ok')}", tr("30 Saniye Geri")),
        (f"Ctrl+{tr('Sağ Ok')}", tr("Sonraki Parça")),
        (f"Ctrl+{tr('Sol Ok')}", tr("Önceki Parça")),
        (tr("Yukarı Ok"), tr("Ses Seviyesi Artır")),
        (tr("Aşağı Ok"), tr("Ses Seviyesi Azalt")),
        ("M", tr("Sessiz")),
        ("S", tr("Altyazıları Göster/Gizle")),
        ("Ctrl+G", tr("Zamana Git")),
    ]
    rows = "\n".join(f"    <tr><td><b>{key}</b></td><td>{label}</td></tr>"
                     for key, label in shortcut_rows)
    shortcuts_text = (f"\n    <h3>{tr('Klavye Kısayolları')}</h3>\n"
                      '    <table border="0" cellspacing="10">\n'
                      f"{rows}\n    </table>\n    ")

    shortcuts_label = QLabel(shortcuts_text)
    shortcuts_label.setStyleSheet("color: #C6CED6; font-size: 13px;")
    layout.addWidget(shortcuts_label)

    ok_button = QPushButton(tr("Tamam"))
    ok_button.clicked.connect(shortcut_dialog.close)
    layout.addWidget(ok_button)

    shortcut_dialog.exec()

def build_language_menu(player):
    """`Araçlar → Dil` alt menüsü.

    "Sistem dili" seçeneği tercihi SİLER; program yeniden Windows'u izler.
    Her dil KENDİ dilinde yazılır, yoksa kullanıcı kendi dilini seçemez.
    """
    menu = QMenu(tr("Dil"), player)
    group = QActionGroup(menu)
    group.setExclusive(True)
    current = i18n.stored_language()

    system_action = QAction(
        f"{tr('Sistem dili')} "
        f"({i18n.language_name(i18n.detect_language())})", player)
    system_action.setCheckable(True)
    system_action.setChecked(current == "")
    system_action.triggered.connect(lambda: choose_language(player, ""))
    group.addAction(system_action)
    menu.addAction(system_action)
    menu.addSeparator()

    # Sabit liste DEĞİL: yalnız çevirisi gerçekten var olan diller.
    for code in i18n.available_languages():
        action = QAction(i18n.language_name(code), player)
        action.setCheckable(True)
        action.setChecked(current == code)
        action.setData(code)
        action.triggered.connect(lambda _checked=False, value=code:
                                 choose_language(player, value))
        group.addAction(action)
        menu.addAction(action)
    return menu


def choose_language(player, code):
    """Dili kaydeder ve yeniden başlatma gerektiğini SÖYLER.

    Sessizce kaydedip hiçbir şey değişmemesi, kullanıcıya "çalışmadı" gibi
    görünürdü.
    """
    if code == i18n.stored_language():
        return
    i18n.store_language(code)
    QMessageBox.information(
        player, tr("Dil"),
        i18n.translate_marked(i18n.RESTART_REQUIRED_MESSAGE))


def show_about(player):
    # Kısayol tablosunda olduğu gibi: HTML üründe kalır, çevirmene yalnız
    # cümleler gider. `MLC Player` ve `Media Launch Codec Player` ürün
    # ADIDIR, çevrilmez.
    features = [
        tr("Birçok video formatını destekler"),
        tr("Altyazı desteği"),
        tr("Oynatma listesi (kaydet/aç - .m3u)"),
        tr("Ekran görüntüsü alma"),
        tr("Video ayarları"),
        tr("URL'den oynatma"),
        tr("Sürükle-bırak ile dosya açma"),
        tr("Son açılanlar"),
        tr("Tekrarla / karışık oynatma modları"),
    ]
    items = "\n".join(f"    <li>{feature}</li>" for feature in features)
    # LİSANS BLOĞU. GPLv3, etkileşimli bir programın uygun telif uyarısını
    # ve GARANTİ REDDİNİ göstermesini bekler; ayrıca §6 karşılık gelen
    # KAYNAĞA erişim ister. Bunları yalnız `LICENSE` dosyasına bırakmak
    # kullanıcının o dosyayı açmasını gerektiriyordu.
    # Telif yılı README ile AYNI olmalıdır (tests/test_about_licence_*).
    from app.updater import GITHUB_URL
    licence = (
        f"    <p>© {COPYRIGHT_YEAR} {tr('MLC Player katkıcıları')}</p>\n"
        f"    <p>{tr('Bu program ÖZGÜR YAZILIMDIR ve GNU GPL sürüm 3 '
                     'koşullarıyla dağıtılır.')}<br>\n"
        f"    {tr('HİÇBİR GARANTİ VERİLMEZ; satılabilirlik veya belirli bir '
                  'amaca uygunluk zımni garantisi dahil değildir.')}</p>\n"
        f"    <p>{tr('Kaynak kodu:')} "
        f'<a href="{GITHUB_URL}">{GITHUB_URL}</a></p>\n'
        f"    <p>{tr('Bu paket mpv/FFmpeg bileşenini içerir; künyesi ve '
                     'kaynak adresi için kurulum dizinindeki '
                     '<code>licenses</code> klasörüne bakın.')}</p>\n")
    about_text = (
        "\n    <h2>MLC Player</h2>\n"
        f"    <p>{tr('Sürüm')} {APP_VERSION}</p>\n"
        f"    <p><i>Media Launch Codec Player</i> — "
        f"{tr('MPV tabanlı minimal video oynatıcı.')}</p>\n"
        f"    <p>{tr('Özellikler:')}</p>\n"
        f"    <ul>\n{items}\n    </ul>\n"
        "    <hr>\n"
        f"{licence}    ")

    QMessageBox.about(player, tr("Hakkında"), about_text)
