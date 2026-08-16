# Program yapılandırma sabitleri
APP_NAME = "MLC Player"
# Sürümün TEK kaynağı. Hakkında penceresi, installer betiği ve yayın
# etiketi buradan türer; `tests/test_version_consistency.py` bağı korur.
APP_VERSION = "v0.3"
# Windows sürüm alanları dört sayılı olmak zorundadır; elle yazılmaz.
WINDOWS_VERSION = ".".join((APP_VERSION.lstrip("v").split(".") + ["0", "0", "0"])[:4])
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
    # MPV renk biçimi #AARRGGBB'dir (bkz. app/subtitle_style.py).
    "sub_color": "#FFFFFFFF",
    "sub_back_color": "#00000000",
    "sub_border_color": "#FF000000",
    "sub_border_size": 3.0,
    # ASS altyazıda normal stil seçeneklerinin uygulanması için "force"
    # gerekir; bool True bütün seçenekleri zorlamaz.
    "sub_ass_override": "force",
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
    # Geniş `fuzzy` yerine mpv'nin resmî `exact` davranışı: yalnız tam video
    # gövdesi ve dil/etiket sonekleri yüklenir (bkz. `app/local_subtitle.py`).
    "sub_auto": "exact",
    # Gömülü ve aynı adlı harici altyazıları bul; kullanıcı açana kadar gösterme.
    "sub_visibility": "no",
    # Ses dosyalarında albüm kapağı video alanında gösterilir; aksi hâlde
    # siyah kare kalıyordu. ÖLÇÜLDÜ: bu libmpv sürümünde varsayılan KAPALI
    # (`audio-display=False`) ve kabul edilen değerler yalnız
    # `embedded-first` / `external-first`; `attachment` ve `yes` reddediliyor.
    # Gömülü kapak önceliklidir, yoksa dosyanın yanındaki resim kullanılır
    # (`cover-art-auto=exact`).
    "audio_display": "embedded-first",
    "scale": "spline36",
    "cscale": "spline36",
    "deband": "yes",
    "video_latency_hacks": "yes",
    # Kaldığın yerden devam kapalı: 20GB+ dosyalarda açılışta kayıtlı
    # konuma seek gecikmeye yol açıyor. Gerekirse "yes" yapılabilir.
    "save_position_on_quit": "no",
    "resume_playback": "no",
}

# Medya dosya uzantıları. Dosya seçici, klasör taraması, playlist paneli ve
# ana pencere sürükle-bırak yolu bu TEK kaynağı kullanır. Uzantının listede
# olması dosyayı medya adayı yapar; gerçek container/codec desteğini libmpv
# belirler ve açılamayan dosya mevcut güvenli hata yoluna düşer.
MEDIA_EXTENSIONS = (
    "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.mpeg *.mpg *.m4v "
    "*.webm *.ts *.m2ts *.mts *.vob *.ogv *.3gp *.3g2 *.asf *.mxf "
    "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.opus *.wma *.ape *.alac "
    "*.aiff *.aif *.ac3 *.dts *.mka"
)
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


# --- Arayüz modu ---
# Sinematik arayüz ürünün TEK arayüzüdür. Eski klasik kabuk artık hiçbir
# ürün, test veya native doğrulama koşumunda GÖRÜNÜR pencere olarak açılmaz.
#
# `MLCPLAYER_CLASSIC_UI` geçmişte klasik kabuğu açan bir teşhis kapısıydı ve
# gerçek Windows koşumlarında eski pencerenin görünmesine yol açıyordu. Ad,
# eski betikler ve kısayollar kırılmasın diye korunur ama ARTIK ETKİSİZDİR.
CLASSIC_UI_ENV = "MLCPLAYER_CLASSIC_UI"


def cinematic_ui_enabled():
    """Sinematik arayüz açık mı? Üründe DAİMA True.

    Değer artık ortam değişkenine bakmaz; legacy anahtar hangi değerle
    verilirse verilsin ürün sinematik açılır.

    NOT: Klasik QMenuBar aksiyonları, `control_container`, `position_slider`
    ve `volume_slider` gibi gizli nesneler uyumluluk katmanı olarak yaşamaya
    devam eder; yalnızca kullanıcıya görünmezler.
    """
    return True
