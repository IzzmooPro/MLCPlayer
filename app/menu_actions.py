from PyQt6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QFormLayout, QDoubleSpinBox, QDialogButtonBox, QColorDialog
)
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtCore import Qt
import os
import sys
from app.errors import show_user_error
from app.config import SUBTITLE_DEFAULTS
from app.utils import format_time

def setup_menu(player):
    menu_bar = player.menuBar()

    # Ortam menüsü
    file_menu = menu_bar.addMenu("Ortam")

    open_action = QAction("Dosya Aç", player)
    open_action.setShortcut("Ctrl+O")
    open_action.triggered.connect(player.open_file)
    file_menu.addAction(open_action)

    url_action = QAction("URL'den Oynat", player)
    url_action.setShortcut("Ctrl+U")
    url_action.triggered.connect(player.open_url)
    file_menu.addAction(url_action)

    subtitle_action = QAction("Altyazı Ekle", player)
    subtitle_action.triggered.connect(player.open_subtitle)
    file_menu.addAction(subtitle_action)

    file_menu.addSeparator()

    # Son açılanlar alt menüsü
    recent_menu = file_menu.addMenu("Son Açılanlar")
    player.recent_menu = recent_menu

    exit_action = QAction("Çıkış", player)
    exit_action.setShortcut("Ctrl+Q")
    exit_action.triggered.connect(player.close)
    file_menu.addAction(exit_action)

    # Görünüm menüsü
    view_menu = menu_bar.addMenu("Görünüm")
    add_to_playlist_action = QAction("Oynatma Listesine Ekle", player)
    add_to_playlist_action.triggered.connect(player.add_to_playlist)
    view_menu.addAction(add_to_playlist_action)

    save_playlist_action = QAction("Oynatma Listesini Kaydet", player)
    save_playlist_action.triggered.connect(player.save_playlist)
    view_menu.addAction(save_playlist_action)

    load_playlist_action = QAction("Oynatma Listesi Aç", player)
    load_playlist_action.triggered.connect(player.load_playlist)
    view_menu.addAction(load_playlist_action)

    show_playlist_action = QAction("Oynatma Listesini Göster", player)
    show_playlist_action.setShortcut("Ctrl+P")
    show_playlist_action.triggered.connect(player.show_playlist)
    view_menu.addAction(show_playlist_action)

    # Görüntü menüsü
    video_menu = menu_bar.addMenu("Görüntü")
    screenshot_action = QAction("Ekran Görüntüsü Al", player)
    screenshot_action.setShortcut("Ctrl+S")
    screenshot_action.triggered.connect(player.take_screenshot)
    video_menu.addAction(screenshot_action)

    fullscreen_action = QAction("Tam Ekran", player)
    fullscreen_action.setShortcut("F")
    fullscreen_action.triggered.connect(player.toggle_fullscreen)
    video_menu.addAction(fullscreen_action)

    video_settings_action = QAction("Video Ayarları", player)
    video_settings_action.triggered.connect(player.setup_video_adjustments)
    video_menu.addAction(video_settings_action)

    # Oynatma menüsü
    play_menu = menu_bar.addMenu("Oynatma")

    play_pause_action = QAction("Oynat/Duraklat", player)
    play_pause_action.setShortcut("Space")
    play_pause_action.triggered.connect(player.play_pause)
    play_menu.addAction(play_pause_action)

    stop_action = QAction("Durdur", player)
    stop_action.triggered.connect(player.stop)
    play_menu.addAction(stop_action)

    play_menu.addSeparator()

    next_track_action = QAction("Sonraki Parça", player)
    next_track_action.setShortcut("Ctrl+Right")
    next_track_action.triggered.connect(player.play_next)
    play_menu.addAction(next_track_action)

    prev_track_action = QAction("Önceki Parça", player)
    prev_track_action.setShortcut("Ctrl+Left")
    prev_track_action.triggered.connect(player.play_previous)
    play_menu.addAction(prev_track_action)

    chapter_menu = play_menu.addMenu("Bölüm")
    previous_chapter_action = QAction("Önceki Bölüm", player)
    previous_chapter_action.triggered.connect(lambda: player.seek_chapter(-1))
    chapter_menu.addAction(previous_chapter_action)
    next_chapter_action = QAction("Sonraki Bölüm", player)
    next_chapter_action.triggered.connect(lambda: player.seek_chapter(1))
    chapter_menu.addAction(next_chapter_action)
    chapter_refresh_action = QAction("Bölümleri Yenile", player)
    chapter_refresh_action.triggered.connect(player.refresh_chapters)
    chapter_menu.addAction(chapter_refresh_action)
    player.chapter_menu = chapter_menu

    play_menu.addSeparator()

    # Oynatma modları
    loop_file_action = QAction("Tek Dosyayı Tekrarla", player)
    loop_file_action.setCheckable(True)
    loop_file_action.setChecked(player.loop_file)
    loop_file_action.toggled.connect(player.set_loop_file)
    play_menu.addAction(loop_file_action)

    loop_playlist_action = QAction("Listeyi Tekrarla", player)
    loop_playlist_action.setCheckable(True)
    loop_playlist_action.setChecked(player.loop_playlist)
    loop_playlist_action.toggled.connect(player.set_loop_playlist)
    play_menu.addAction(loop_playlist_action)

    shuffle_action = QAction("Karışık Oynat", player)
    shuffle_action.setCheckable(True)
    shuffle_action.setChecked(player.shuffle)
    shuffle_action.toggled.connect(player.toggle_shuffle)
    play_menu.addAction(shuffle_action)

    play_menu.addSeparator()

    # Hız ayarı alt menüsü
    speed_menu = play_menu.addMenu("Oynatma Hızı")

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
    audio_menu = menu_bar.addMenu("Ses")
    volume_up_action = QAction("Sesi Aç", player)
    volume_up_action.setShortcut("Up")
    volume_up_action.triggered.connect(lambda: player.change_volume(5))
    audio_menu.addAction(volume_up_action)

    volume_down_action = QAction("Sesi Kıs", player)
    volume_down_action.setShortcut("Down")
    volume_down_action.triggered.connect(lambda: player.change_volume(-5))
    audio_menu.addAction(volume_down_action)

    mute_action = QAction("Sesi Kapat/Aç", player)
    mute_action.setShortcut("M")
    mute_action.triggered.connect(player.toggle_mute)
    audio_menu.addAction(mute_action)
    audio_menu.addSeparator()

    audio_track_menu = audio_menu.addMenu("Ses Kanalları")
    audio_track_action = QAction("Ses Kanallarını Yenile", player)
    audio_track_action.triggered.connect(player.refresh_audio_tracks)
    audio_track_menu.addAction(audio_track_action)
    player.audio_track_menu = audio_track_menu

    audio_device_menu = audio_menu.addMenu("Ses Aygıtı")
    audio_device_action = QAction("Aygıtları Yenile", player)
    audio_device_action.triggered.connect(player.refresh_audio_devices)
    audio_device_menu.addAction(audio_device_action)
    player.audio_device_menu = audio_device_menu

    # Alt Yazı menüsü
    subtitle_menu = menu_bar.addMenu("Alt Yazı")
    subtitle_add_menu_action = QAction("Altyazı Ekle", player)
    subtitle_add_menu_action.setShortcut("Alt+E")
    subtitle_add_menu_action.triggered.connect(player.open_subtitle)
    subtitle_menu.addAction(subtitle_add_menu_action)

    subtitle_toggle_action = QAction("Altyazıları Göster/Gizle", player)
    subtitle_toggle_action.setShortcut("S")
    subtitle_toggle_action.triggered.connect(player.toggle_subtitles)
    subtitle_menu.addAction(subtitle_toggle_action)

    subtitle_track_menu = subtitle_menu.addMenu("Altyazı Parçası")
    subtitle_track_action = QAction("Altyazıları Yenile", player)
    subtitle_track_action.triggered.connect(player.refresh_subtitle_tracks)
    subtitle_track_menu.addAction(subtitle_track_action)
    player.subtitle_track_menu = subtitle_track_menu

    subtitle_settings_menu_action = QAction("Altyazı Ayarları", player)
    subtitle_settings_menu_action.triggered.connect(player.show_subtitle_settings)
    subtitle_menu.addAction(subtitle_settings_menu_action)

    # Gezinim menüsü
    nav_menu = menu_bar.addMenu("Gezinim")

    forward_5s_action = QAction("5 Saniye İleri", player)
    forward_5s_action.setShortcut("Right")
    forward_5s_action.triggered.connect(lambda: player.seek_relative(5))
    nav_menu.addAction(forward_5s_action)

    backward_5s_action = QAction("5 Saniye Geri", player)
    backward_5s_action.setShortcut("Left")
    backward_5s_action.triggered.connect(lambda: player.seek_relative(-5))
    nav_menu.addAction(backward_5s_action)

    forward_30s_action = QAction("30 Saniye İleri", player)
    forward_30s_action.setShortcut("Shift+Right")
    forward_30s_action.triggered.connect(lambda: player.seek_relative(30))
    nav_menu.addAction(forward_30s_action)

    backward_30s_action = QAction("30 Saniye Geri", player)
    backward_30s_action.setShortcut("Shift+Left")
    backward_30s_action.triggered.connect(lambda: player.seek_relative(-30))
    nav_menu.addAction(backward_30s_action)

    nav_menu.addSeparator()

    goto_time_action = QAction("Zamana Git...", player)
    goto_time_action.setShortcut("Ctrl+G")
    goto_time_action.triggered.connect(player.goto_time)
    nav_menu.addAction(goto_time_action)

    # Araçlar menüsü
    tools_menu = menu_bar.addMenu("Araçlar")

    video_adj_action = QAction("Video Ayarları", player)
    video_adj_action.triggered.connect(player.setup_video_adjustments)
    tools_menu.addAction(video_adj_action)

    # Yardım menüsü
    help_menu = menu_bar.addMenu("Yardım")

    shortcuts_action = QAction("Klavye Kısayolları", player)
    shortcuts_action.triggered.connect(player.show_shortcuts)
    help_menu.addAction(shortcuts_action)

    about_action = QAction("Hakkında", player)
    about_action.triggered.connect(player.show_about)
    help_menu.addAction(about_action)

    # VLC benzeri, sabit ve anlaşılır sekme sırası.
    menu_order = ["Ortam", "Oynatma", "Ses", "Görüntü", "Alt Yazı",
                  "Araçlar", "Gezinim", "Görünüm", "Yardım"]
    top_menus = {action.text(): action for action in menu_bar.actions()}
    for name in menu_order:
        action = top_menus.get(name)
        if action:
            menu_bar.removeAction(action)
            menu_bar.addAction(action)


def _mpv_color_to_qcolor(value, fallback):
    """mpv'nin #RRGGBBAA rengini QColor'a çevirir."""
    text = str(value or "")
    if len(text) == 9 and text.startswith("#"):
        try:
            return QColor(int(text[1:3], 16), int(text[3:5], 16),
                          int(text[5:7], 16), int(text[7:9], 16))
        except ValueError:
            pass
    color = QColor(text)
    return color if color.isValid() else QColor(fallback)


def _qcolor_to_mpv(color):
    return (f"#{color.red():02X}{color.green():02X}{color.blue():02X}"
            f"{color.alpha():02X}")


def show_subtitle_settings(player):
    dialog = QDialog(player)
    dialog.setWindowTitle("Altyazı Ayarları")
    dialog.setMinimumWidth(440)
    layout = QVBoxLayout(dialog)
    form = QFormLayout()
    form.setSpacing(10)

    def read_number(name, default):
        try:
            return float(getattr(player.mpv_player, name))
        except Exception:
            return float(default)

    delay = QDoubleSpinBox()
    delay.setRange(-120.0, 120.0)
    delay.setSingleStep(0.1)
    delay.setDecimals(1)
    delay.setSuffix(" sn")
    delay.setValue(read_number("sub_delay", 0.0))
    delay.setToolTip("Pozitif değer altyazıyı geciktirir, negatif değer öne alır.")

    scale = QDoubleSpinBox()
    scale.setRange(0.5, 3.0)
    scale.setSingleStep(0.1)
    scale.setDecimals(1)
    scale.setSuffix("x")
    scale.setValue(read_number("sub_scale", 1.0))

    position_row = QHBoxLayout()
    position = QSlider(Qt.Orientation.Horizontal)
    position.setRange(0, 100)
    position.setValue(int(read_number("sub_pos", 100.0)))
    position_label = QLabel(f"%{position.value()}")
    position_label.setMinimumWidth(42)
    position.valueChanged.connect(lambda value: position_label.setText(f"%{value}"))
    position_row.addWidget(position)
    position_row.addWidget(position_label)

    colors = {
        "sub_color": _mpv_color_to_qcolor(
            getattr(player.mpv_player, "sub_color", ""), "#FFFFFFFF"),
        "sub_back_color": _mpv_color_to_qcolor(
            getattr(player.mpv_player, "sub_back_color", ""), "#00000000"),
        "sub_border_color": _mpv_color_to_qcolor(
            getattr(player.mpv_player, "sub_border_color", ""), "#000000FF"),
    }
    color_buttons = {}

    def refresh_color_button(key):
        color = colors[key]
        button = color_buttons[key]
        button.setText("Renk seç")
        button.setStyleSheet(
            f"background-color: {color.name()}; color: "
            f"{'black' if color.lightness() > 150 else 'white'};"
        )

    def add_color_row(label, key):
        button = QPushButton()
        color_buttons[key] = button

        def choose_color():
            selected = QColorDialog.getColor(
                colors[key], dialog, label,
                QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if selected.isValid():
                colors[key] = selected
                refresh_color_button(key)

        button.clicked.connect(choose_color)
        refresh_color_button(key)
        form.addRow(label, button)

    border_size = QDoubleSpinBox()
    border_size.setRange(0.0, 10.0)
    border_size.setSingleStep(0.5)
    border_size.setDecimals(1)
    border_size.setSuffix(" px")
    border_size.setValue(read_number("sub_border_size", 3.0))

    form.addRow("Senkron gecikmesi:", delay)
    form.addRow("Yazı boyutu:", scale)
    form.addRow("Dikey konum:", position_row)
    add_color_row("Yazı rengi:", "sub_color")
    add_color_row("Arka plan rengi:", "sub_back_color")
    add_color_row("Kenarlık rengi:", "sub_border_color")
    form.addRow("Kenarlık kalınlığı:", border_size)
    layout.addLayout(form)

    def reset_values():
        delay.setValue(float(SUBTITLE_DEFAULTS["sub_delay"]))
        scale.setValue(float(SUBTITLE_DEFAULTS["sub_scale"]))
        position.setValue(int(SUBTITLE_DEFAULTS["sub_pos"]))
        border_size.setValue(float(SUBTITLE_DEFAULTS["sub_border_size"]))
        for key in colors:
            colors[key] = _mpv_color_to_qcolor(SUBTITLE_DEFAULTS[key], "#00000000")
            refresh_color_button(key)

    reset_button = QPushButton("Varsayılana Dön")
    reset_button.clicked.connect(reset_values)
    layout.addWidget(reset_button)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok |
        QDialogButtonBox.StandardButton.Cancel |
        QDialogButtonBox.StandardButton.Apply
    )
    layout.addWidget(buttons)

    def apply_settings():
        values = {
            "sub_delay": delay.value(),
            "sub_scale": scale.value(),
            "sub_pos": float(position.value()),
            "sub_border_size": border_size.value(),
            "sub_color": _qcolor_to_mpv(colors["sub_color"]),
            "sub_back_color": _qcolor_to_mpv(colors["sub_back_color"]),
            "sub_border_color": _qcolor_to_mpv(colors["sub_border_color"]),
        }
        try:
            for name, value in values.items():
                setattr(player.mpv_player, name, value)
                player.settings.setValue(f"subtitle/{name}", value)
            player.settings.setValue("subtitle/sub_ass_override", True)
            player.mpv_player.sub_ass_override = True
        except Exception as e:
            show_user_error(player, "Altyazı Ayarları Uygulanamadı",
                            "Altyazı ayarları uygulanamadı. Lütfen tekrar deneyin.",
                            exc=e)

    buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(apply_settings)
    buttons.accepted.connect(lambda: (apply_settings(), dialog.accept()))
    buttons.rejected.connect(dialog.reject)
    dialog.exec()

def update_recent_menu(player):
    recent_menu = player.recent_menu
    recent_menu.clear()
    for path in player.recent_files:
        action = QAction(os.path.basename(path), player)
        action.setToolTip(path)
        action.triggered.connect(lambda checked, p=path: player.open_path(p))
        recent_menu.addAction(action)
    if not player.recent_files:
        empty_action = QAction("Son açılan dosya yok", player)
        empty_action.setEnabled(False)
        recent_menu.addAction(empty_action)

def setup_video_adjustments(player):
    video_adj_dialog = QDialog(player)
    video_adj_dialog.setWindowTitle("Video Ayarları")
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
            print(f"{name} ayarı uygulanamadı: {e}")

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
    brightness_label = QLabel("Parlaklık:")
    brightness_slider = QSlider(Qt.Orientation.Horizontal)
    brightness_slider.setRange(-100, 100)
    brightness_slider.setValue(read_setting("brightness"))
    brightness_slider.valueChanged.connect(lambda v: set_setting("brightness", v))
    brightness_layout.addWidget(brightness_label)
    brightness_layout.addWidget(brightness_slider)

    # Kontrast
    contrast_layout = QHBoxLayout()
    contrast_label = QLabel("Kontrast:")
    contrast_slider = QSlider(Qt.Orientation.Horizontal)
    contrast_slider.setRange(-100, 100)
    contrast_slider.setValue(read_setting("contrast"))
    contrast_slider.valueChanged.connect(lambda v: set_setting("contrast", v))
    contrast_layout.addWidget(contrast_label)
    contrast_layout.addWidget(contrast_slider)

    # Doygunluk
    saturation_layout = QHBoxLayout()
    saturation_label = QLabel("Doygunluk:")
    saturation_slider = QSlider(Qt.Orientation.Horizontal)
    saturation_slider.setRange(-100, 100)
    saturation_slider.setValue(read_setting("saturation"))
    saturation_slider.valueChanged.connect(lambda v: set_setting("saturation", v))
    saturation_layout.addWidget(saturation_label)
    saturation_layout.addWidget(saturation_slider)

    # Gamma
    gamma_layout = QHBoxLayout()
    gamma_label = QLabel("Gamma:")
    gamma_slider = QSlider(Qt.Orientation.Horizontal)
    gamma_slider.setRange(-100, 100)
    gamma_slider.setValue(read_setting("gamma"))
    gamma_slider.valueChanged.connect(lambda v: set_setting("gamma", v))
    gamma_layout.addWidget(gamma_label)
    gamma_layout.addWidget(gamma_slider)

    # Butonlar
    button_layout = QHBoxLayout()
    button_layout.setSpacing(8)
    reset_button = QPushButton("Sıfırla")
    reset_button.clicked.connect(reset_settings)
    close_button = QPushButton("Kapat")
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

def refresh_audio_tracks(player):
    if not player.current_file:
        QMessageBox.warning(player, "Uyarı", "Önce bir video dosyası açın.")
        return

    # Mevcut menü öğelerini temizle (ilk öğe hariç)
    for action in player.audio_track_menu.actions()[1:]:
        player.audio_track_menu.removeAction(action)

    try:
        # Ses kanallarını al
        player.mpv_player.command('rescan-external-files')
        track_list = player.mpv_player.track_list
        audio_tracks = [track for track in track_list if track['type'] == 'audio']
        current_aid = player.mpv_player.aid

        if not audio_tracks:
            no_audio_action = QAction("Ses kanalı bulunamadı", player)
            no_audio_action.setEnabled(False)
            player.audio_track_menu.addAction(no_audio_action)
        else:
            # Kanalları menüye ekle
            for track in audio_tracks:
                track_name = track.get('title', f"Ses Kanalı {track['id']}")
                track_action = QAction(f"{track_name} (ID: {track['id']})", player)
                track_action.setCheckable(True)
                if track['id'] == current_aid:
                    track_action.setChecked(True)
                track_action.triggered.connect(lambda checked, aid=track['id']: player.select_audio_track(aid))
                player.audio_track_menu.addAction(track_action)
    except Exception as e:
        print(f"Ses kanallarını listeleme hatası: {e}")
        error_action = QAction("Ses kanalları yüklenemedi", player)
        error_action.setEnabled(False)
        player.audio_track_menu.addAction(error_action)

def select_audio_track(player, aid):
    try:
        player.mpv_player.aid = aid
        print(f"Seçilen ses kanalı ID: {aid}")
    except Exception as e:
        print(f"Ses kanalı seçimi hatası: {e}")
        show_user_error(player, "Ses Kanalı Seçilemedi",
                        "Ses kanalı değiştirilemedi. Lütfen başka bir kanal deneyin.",
                        exc=e)


def refresh_audio_devices(player):
    for action in player.audio_device_menu.actions()[1:]:
        player.audio_device_menu.removeAction(action)
    try:
        current = player.mpv_player.audio_device
        devices = player.mpv_player.audio_device_list or []
        if sys.platform == "win32":
            # OpenAL/SDL mpv backend'leridir; Windows'taki gerçek çıkış aygıtı
            # değildir. Gerçek donanım çıkışlarını WASAPI listesinde göster.
            devices = [device for device in devices if (
                device.get("name") == "auto" or
                str(device.get("name", "")).startswith("wasapi/")
            )]
        for device in devices:
            name = device.get("name", "auto")
            description = ("Otomatik Seç" if name == "auto"
                           else device.get("description") or name)
            action = QAction(description, player)
            action.setCheckable(True)
            action.setChecked(name == current)
            action.triggered.connect(
                lambda checked, value=name: select_audio_device(player, value))
            player.audio_device_menu.addAction(action)
    except Exception as e:
        print(f"Ses aygıtları listeleme hatası: {e}")
        error_action = QAction("Ses aygıtları yüklenemedi", player)
        error_action.setEnabled(False)
        player.audio_device_menu.addAction(error_action)


def select_audio_device(player, name):
    try:
        player.mpv_player.audio_device = name
        player.video_frame.show_osd("Ses aygıtı değiştirildi")
    except Exception as e:
        show_user_error(player, "Ses Aygıtı Değiştirilemedi",
                        "Ses aygıtı değiştirilemedi. Lütfen başka bir aygıt deneyin.",
                        exc=e)


def refresh_subtitle_tracks(player):
    if not player.current_file:
        QMessageBox.warning(player, "Uyarı", "Önce bir video dosyası açın.")
        return
    for action in player.subtitle_track_menu.actions()[1:]:
        player.subtitle_track_menu.removeAction(action)
    try:
        player.mpv_player.command("rescan-external-files")
        tracks = [track for track in (player.mpv_player.track_list or [])
                  if track.get("type") == "sub"]
        current_sid = player.mpv_player.sid
        if not tracks:
            empty_action = QAction("Altyazı parçası bulunamadı", player)
            empty_action.setEnabled(False)
            player.subtitle_track_menu.addAction(empty_action)
            return
        for track in tracks:
            title = track.get("title") or track.get("lang") or f"Altyazı {track['id']}"
            action = QAction(f"{title} (ID: {track['id']})", player)
            action.setCheckable(True)
            action.setChecked(track["id"] == current_sid)
            action.triggered.connect(
                lambda checked, sid=track["id"]: player.select_subtitle_language(sid))
            player.subtitle_track_menu.addAction(action)
    except Exception as e:
        print(f"Altyazı parçaları listeleme hatası: {e}")
        error_action = QAction("Altyazı parçaları yüklenemedi", player)
        error_action.setEnabled(False)
        player.subtitle_track_menu.addAction(error_action)


def refresh_chapters(player):
    for action in player.chapter_menu.actions()[2:]:
        player.chapter_menu.removeAction(action)
    try:
        chapters = player.mpv_player.chapter_list or []
        if not chapters:
            empty_action = QAction("Bölüm bulunamadı", player)
            empty_action.setEnabled(False)
            player.chapter_menu.addAction(empty_action)
        else:
            for index, chapter in enumerate(chapters):
                title = chapter.get("title") or f"Bölüm {index + 1:02d}"
                start = chapter.get("time")
                label = f"{title} ({format_time(start)})" if start is not None else title
                action = QAction(label, player)
                action.triggered.connect(
                    lambda checked, chapter_index=index: select_chapter(player, chapter_index))
                player.chapter_menu.addAction(action)
        refresh_action = QAction("Bölümleri Yenile", player)
        refresh_action.triggered.connect(player.refresh_chapters)
        player.chapter_menu.addAction(refresh_action)
    except Exception as e:
        print(f"Bölümler listelenemedi: {e}")


def select_chapter(player, index):
    try:
        player.mpv_player.chapter = index
        chapters = player.mpv_player.chapter_list or []
        title = chapters[index].get("title") if index < len(chapters) else None
        player.video_frame.show_osd(title or f"Bölüm {index + 1:02d}")
    except Exception as e:
        print(f"Bölüm seçilemedi: {e}")

def show_shortcuts(player):
    shortcut_dialog = QDialog(player)
    shortcut_dialog.setWindowTitle("Klavye Kısayolları")
    shortcut_dialog.setMinimumSize(500, 350)

    layout = QVBoxLayout(shortcut_dialog)

    shortcuts_text = """
    <h3>Klavye Kısayolları</h3>
    <table border="0" cellspacing="10">
    <tr><td><b>Space</b></td><td>Oynat/Duraklat</td></tr>
    <tr><td><b>Ctrl+O</b></td><td>Dosya Aç</td></tr>
    <tr><td><b>Ctrl+U</b></td><td>URL'den Oynat</td></tr>
    <tr><td><b>Ctrl+S</b></td><td>Ekran Görüntüsü Al</td></tr>
    <tr><td><b>Ctrl+P</b></td><td>Oynatma Listesini Göster</td></tr>
    <tr><td><b>Ctrl+Q</b></td><td>Çıkış</td></tr>
    <tr><td><b>F</b></td><td>Tam Ekran</td></tr>
    <tr><td><b>Esc</b></td><td>Tam Ekrandan Çık</td></tr>
    <tr><td><b>Sağ Ok</b></td><td>5 Saniye İleri</td></tr>
    <tr><td><b>Sol Ok</b></td><td>5 Saniye Geri</td></tr>
    <tr><td><b>Shift+Sağ Ok</b></td><td>30 Saniye İleri</td></tr>
    <tr><td><b>Shift+Sol Ok</b></td><td>30 Saniye Geri</td></tr>
    <tr><td><b>Ctrl+Sağ Ok</b></td><td>Sonraki Parça</td></tr>
    <tr><td><b>Ctrl+Sol Ok</b></td><td>Önceki Parça</td></tr>
    <tr><td><b>Yukarı Ok</b></td><td>Ses Seviyesi Artır</td></tr>
    <tr><td><b>Aşağı Ok</b></td><td>Ses Seviyesi Azalt</td></tr>
    <tr><td><b>M</b></td><td>Sessiz</td></tr>
    <tr><td><b>S</b></td><td>Altyazıları Göster/Gizle</td></tr>
    <tr><td><b>Ctrl+G</b></td><td>Zamana Git</td></tr>
    </table>
    """

    shortcuts_label = QLabel(shortcuts_text)
    shortcuts_label.setStyleSheet("color: #C6CED6; font-size: 13px;")
    layout.addWidget(shortcuts_label)

    ok_button = QPushButton("Tamam")
    ok_button.clicked.connect(shortcut_dialog.close)
    layout.addWidget(ok_button)

    shortcut_dialog.exec()

def show_about(player):
    about_text = """
    <h2>MLC Player</h2>
    <p>Sürüm 1.1</p>
    <p><i>Media Launch Codec Player</i> — MPV tabanlı minimal video oynatıcı.</p>
    <p>Özellikler:</p>
    <ul>
    <li>Birçok video formatını destekler</li>
    <li>Altyazı desteği</li>
    <li>Oynatma listesi (kaydet/aç - .m3u)</li>
    <li>Ekran görüntüsü alma</li>
    <li>Video ayarları</li>
    <li>URL'den oynatma</li>
    <li>Sürükle-bırak ile dosya açma</li>
    <li>Son açılanlar</li>
    <li>Tekrarla / karışık oynatma modları</li>
    </ul>
    <p>© 2025</p>
    """

    QMessageBox.about(player, "Hakkında", about_text)
