# Program yapılandırma sabitleri
APP_NAME = "MLC Player"
VERSION = "1.1"
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 450
DEFAULT_VOLUME = 70
# 100 üstü mpv amplifikasyonu; ses çubuğu 0-175 arası değer alır
MAX_VOLUME = 175

# Altyazı görünüm ve senkron varsayılanları. Renk biçimi mpv için RGBA'dır.
SUBTITLE_DEFAULTS = {
    "sub_delay": 0.0,
    "sub_scale": 1.0,
    "sub_pos": 100.0,
    "sub_color": "#FFFFFFFF",
    "sub_back_color": "#00000000",
    "sub_border_color": "#000000FF",
    "sub_border_size": 3.0,
    "sub_ass_override": True,
}

# MPV yapılandırma sabitleri
# Hafif profil: gpu-hq'nin ağır shader'ları (correct-downscaling,
# linear-downscaling, sigmoid-upscaling, dither-depth) kaldırıldı;
# spline36 + deband kalitesi korunur. İlk kare 4K'da daha hızlı gelir.
# Cache anahtarları kaldırıldı: mpv varsayılanı yerel dosyada ön-bellek
# yapmaz, ağ akışında otomatik açar.
MPV_CONFIG = {
    "hwdec": "auto-safe",
    "vo": "gpu",
    "keep_open": "yes",
    "video_sync": "audio",
    "sub_auto": "fuzzy",
    "scale": "spline36",
    "cscale": "spline36",
    "deband": "yes",
    "video_latency_hacks": "yes",
    # Kaldığın yerden devam kapalı: 20GB+ dosyalarda açılışta kayıtlı
    # konuma seek gecikmeye yol açıyor. Gerekirse "yes" yapılabilir.
    "save_position_on_quit": "no",
    "resume_playback": "no",
}

# Medya dosya uzantıları
MEDIA_EXTENSIONS = "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.mpeg *.mpg *.m4v *.mp3 *.wav *.flac *.ogg *.m4a"
SUBTITLE_EXTENSIONS = "*.srt *.vtt *.ass *.ssa *.sub"

# Uygulama stili - modern koyu tema
APP_STYLE = """
    QMainWindow {
        background-color: #151A1F;
    }

    QMenuBar {
        background-color: #1A2027;
        color: #E0E5EB;
        padding: 4px 6px;
        border-bottom: 1px solid #2A323A;
        font-size: 13px;
    }
    QMenuBar::item {
        background: transparent;
        padding: 5px 10px;
        border-radius: 5px;
    }
    QMenuBar::item:selected {
        background: #2C3640;
    }
    QMenuBar::item:pressed {
        background: #333F4A;
    }

    QMenu {
        background-color: #1E252C;
        color: #E0E5EB;
        border: 1px solid #2E3842;
        border-radius: 8px;
        padding: 5px;
        font-size: 13px;
    }
    QMenu::item {
        padding: 6px 28px 6px 20px;
        border-radius: 5px;
    }
    QMenu::item:selected {
        background-color: #2E7DB8;
        color: #FFFFFF;
    }
    QMenu::item:disabled {
        color: #6B7785;
    }
    QMenu::separator {
        height: 1px;
        background: #2E3842;
        margin: 5px 8px;
    }
    QMenu::icon {
        padding-left: 6px;
    }

    QStatusBar {
        background-color: #1A2027;
        color: #9AA7B3;
        border-top: 1px solid #2A323A;
    }

    QSlider {
        background: transparent;
    }
    QSlider::groove:horizontal {
        height: 4px;
        background: #3A4450;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #E8EDF2;
        width: 10px;
        height: 10px;
        margin: -3px 0;
        border-radius: 5px;
    }
    QSlider::handle:horizontal:hover {
        background: #FFFFFF;
    }
    QSlider::sub-page:horizontal {
        background: #2E9BD8;
        border-radius: 2px;
    }

    QSlider#positionSlider::groove:horizontal {
        height: 4px;
        background: #3A4450;
        border-radius: 2px;
    }
    QSlider#positionSlider::handle:horizontal {
        background: #E8EDF2;
        width: 10px;
        height: 10px;
        margin: -3px 0;
        border-radius: 5px;
    }
    QSlider#positionSlider::handle:horizontal:hover {
        background: #FFFFFF;
    }
    QSlider#positionSlider::sub-page:horizontal {
        background: #2E9BD8;
        border-radius: 2px;
    }
    QSlider#volumeSlider::groove:horizontal {
        height: 3px;
        background: #3A4450;
        border-radius: 1px;
    }
    QSlider#volumeSlider::handle:horizontal {
        background: #E8EDF2;
        width: 8px;
        height: 8px;
        margin: -2px 0;
        border-radius: 4px;
    }
    QSlider#volumeSlider::handle:horizontal:hover {
        background: #FFFFFF;
    }
    QSlider#volumeSlider::sub-page:horizontal {
        background: #2E9BD8;
        border-radius: 1px;
    }

    QPushButton {
        background-color: #232B33;
        color: #E0E5EB;
        border: 1px solid #333F4A;
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 13px;
    }
    QPushButton:hover {
        background-color: #2C3640;
        border-color: #3E4B58;
    }
    QPushButton:pressed {
        background-color: #333F4A;
    }
    QPushButton:disabled {
        color: #6B7785;
        background-color: #1E252C;
    }

    QToolButton {
        background-color: transparent;
        border: none;
        border-radius: 5px;
        padding: 3px;
    }
    QToolButton:hover {
        background-color: #2C3640;
    }
    QToolButton:pressed {
        background-color: #333F4A;
    }

    QLabel {
        color: #E0E5EB;
        font-size: 13px;
    }

    QDialog {
        background-color: #1A2027;
    }

    QListWidget {
        background-color: #1E252C;
        color: #E0E5EB;
        border: 1px solid #2E3842;
        border-radius: 6px;
        padding: 4px;
        outline: none;
    }
    QListWidget::item {
        padding: 6px 8px;
        border-radius: 4px;
    }
    QListWidget::item:selected {
        background-color: #2E7DB8;
        color: #FFFFFF;
    }
    QListWidget::item:hover {
        background-color: #2C3640;
    }

    QLineEdit {
        background-color: #1E252C;
        color: #E0E5EB;
        border: 1px solid #333F4A;
        border-radius: 6px;
        padding: 6px 8px;
        selection-background-color: #2E7DB8;
    }
    QLineEdit:focus {
        border-color: #2E9BD8;
    }

    QComboBox {
        background-color: #1E252C;
        color: #E0E5EB;
        border: 1px solid #333F4A;
        border-radius: 6px;
        padding: 5px 8px;
    }
    QComboBox:hover {
        border-color: #3E4B58;
    }
    QComboBox::drop-down {
        border: none;
        width: 22px;
    }
    QComboBox QAbstractItemView {
        background-color: #1E252C;
        color: #E0E5EB;
        border: 1px solid #2E3842;
        selection-background-color: #2E7DB8;
        selection-color: #FFFFFF;
    }

    QToolTip {
        background-color: #232B33;
        color: #E0E5EB;
        border: 1px solid #333F4A;
        padding: 5px 8px;
        border-radius: 4px;
    }

    QMessageBox {
        background-color: #1A2027;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 2px;
    }
    QScrollBar::handle:vertical {
        background: #3A4450;
        border-radius: 4px;
        min-height: 24px;
    }
    QScrollBar::handle:vertical:hover {
        background: #4A5561;
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        height: 0px;
    }
    QScrollBar::add-page, QScrollBar::sub-page {
        background: transparent;
    }
"""
