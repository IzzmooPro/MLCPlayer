"""Altyazı Merkezi ayarları — AYRI, küçük, temaya uygun pencere.

Neden ayrı pencere
------------------
Ayarlar eskiden ana pencerenin SAĞINDAN açılan bir çekmeceydi ve yeri ana
içerikten çalıyordu: 660 px'lik dialogda film adı alanı 148 px'ten 35 px'e
(birkaç karakter) düşüyordu. Ölçüm kullanıcının bildirdiği hatayla birebir
aynıydı. Ayarlar artık ana pencerenin geometrisine HİÇ dokunmaz.

Bu modül YALNIZCA arayüzdür. Kalıcılık, doğrulama ve transaction mantığı
`SubtitleSettingsController` + `SubtitleSettingsStore` katmanındadır; ikinci
bir ayar saklama mantığı YOKTUR.

Controller'ın beklediği alan adları (`api_key_field`, `username_field`,
`password_field`, `settings_language_box`,
`settings_save_button`, `settings_cancel_button`, `language_box`,
`set_operation_status`) burada aynen sağlanır; `language_box` ve arama
durumu ana pencereye vekâleten iletilir.
"""
import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout)

from app.subtitle_center import STYLE, populate_language_box
from app.i18n import tr, tr_mark, translate_marked

# OpenSubtitles'in RESMÎ başlangıç rehberi. Yalnızca kullanıcı tıklayınca
# açılır; program başlangıcında veya pencere açılışında ASLA açılmaz.
API_KEY_HELP_URL = "https://opensubtitles.tawk.help/article/getting-started"

DIALOG_WIDTH = 440
# Modül düzeyi metinler: import anında çevirmen yoktur; `tr_mark()` yalnız
# işaretler, çeviri kullanım anında `translate_marked()` ile yapılır.
CREDENTIAL_HINT = tr_mark(
    "Arama için API anahtarı gerekir. Kullanıcı adı ve parola daha yüksek "
    "hesap kotasıyla oturum açmak için isteğe bağlıdır. Yeni "
    "OpenSubtitles.com hesabı kullanılır (eski opensubtitles.org değil)."
)
STORAGE_HINT = tr_mark(
    "Anahtar ve parola Windows Kimlik Bilgileri'nde saklanır.")


class SubtitleCenterSettingsDialog(QDialog):
    """Küçük ayar penceresi. Global topmost DEĞİLDİR."""

    connection_test_requested = pyqtSignal()

    def __init__(self, center_dialog):
        super().__init__(center_dialog)
        self._center = center_dialog

        self.setObjectName("subtitleCenter")
        self.setWindowTitle(tr("Altyazı Merkezi Ayarları"))
        self.setStyleSheet(STYLE)
        self.setModal(True)
        # Window-modal: ana pencereyi bekletir ama BAŞKA uygulamaların
        # üstünde asılı kalmaz.
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFixedWidth(DIALOG_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        heading = QLabel("Ayarlar", self)
        heading.setObjectName("subtitleHeading")
        layout.addWidget(heading)

        hint = QLabel(translate_marked(CREDENTIAL_HINT), self)
        hint.setObjectName("subtitleMeta")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.credential_hint = hint

        # --- API anahtarı: ZORUNLU ---
        layout.addWidget(self._field_label(tr("API anahtarı (zorunlu)")))
        self.api_key_field = QLineEdit(self)
        self.api_key_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_field.setAccessibleName(
            tr("OpenSubtitles API anahtarı"))
        self.api_key_field.setPlaceholderText(tr("OpenSubtitles.com API anahtarı"))
        layout.addWidget(self.api_key_field)

        self.help_button = QPushButton(tr("Anahtar nasıl alınır?"), self)
        self.help_button.setObjectName("subtitleLinkButton")
        self.help_button.setAccessibleName(
            tr("API anahtarı alma rehberini aç"))
        self.help_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_button.clicked.connect(self.open_api_key_help)
        layout.addWidget(self.help_button, 0, Qt.AlignmentFlag.AlignLeft)

        # --- Hesap: İSTEĞE BAĞLI ---
        layout.addWidget(
            self._field_label(
                tr("OpenSubtitles.com kullanıcı adı (isteğe bağlı)")))
        self.username_field = QLineEdit(self)
        self.username_field.setAccessibleName(
            tr("OpenSubtitles kullanıcı adı"))
        layout.addWidget(self.username_field)

        layout.addWidget(self._field_label(tr("Parola (isteğe bağlı)")))
        self.password_field = QLineEdit(self)
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.setAccessibleName(tr("OpenSubtitles parolası"))
        layout.addWidget(self.password_field)

        self.show_password_box = QCheckBox(tr("Parolayı göster"), self)
        self.show_password_box.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_password_box.toggled.connect(self.toggle_password_visibility)
        layout.addWidget(self.show_password_box)

        storage = QLabel(translate_marked(STORAGE_HINT), self)
        storage.setObjectName("subtitleMeta")
        storage.setWordWrap(True)
        layout.addWidget(storage)

        # --- Tercihler ---
        layout.addWidget(self._field_label(tr("Varsayılan dil")))
        self.settings_language_box = QComboBox(self)
        populate_language_box(self.settings_language_box)
        self.settings_language_box.setAccessibleName(
            tr("Varsayılan altyazı dili"))
        self.settings_language_box.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.settings_language_box)

        # "İndirme sonrası" seçimi KALDIRILDI: davranışa hiç bağlı
        # değildi ve tek akış artık her zaman "İndir ve Uygula"dır.

        # --- Durum satırı ---
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("subtitleStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # --- Düğmeler ---
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.test_button = QPushButton(tr("Bağlantıyı Test Et"), self)
        self.test_button.setAccessibleName(
            tr("OpenSubtitles bağlantısını test et"))
        self.test_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_button.clicked.connect(self.connection_test_requested)
        buttons.addWidget(self.test_button)
        buttons.addStretch(1)

        self.settings_cancel_button = QPushButton(tr("Vazgeç"), self)
        self.settings_cancel_button.setAccessibleName(
            tr("Ayarlardan vazgeç"))
        self.settings_cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_cancel_button.clicked.connect(self.reject)
        self.settings_save_button = QPushButton(tr("Kaydet"), self)
        self.settings_save_button.setObjectName("subtitlePrimaryAction")
        self.settings_save_button.setAccessibleName(tr("Ayarları kaydet"))
        self.settings_save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.addWidget(self.settings_cancel_button)
        buttons.addWidget(self.settings_save_button)
        layout.addLayout(buttons)

        self.adjustSize()

    # --- Yardımcılar ---

    def _field_label(self, text):
        label = QLabel(text, self)
        label.setObjectName("subtitleFieldLabel")
        return label

    def toggle_password_visibility(self, visible):
        self.password_field.setEchoMode(
            QLineEdit.EchoMode.Normal if visible
            else QLineEdit.EchoMode.Password)

    def open_api_key_help(self):
        """Resmî rehberi SİSTEM tarayıcısında açar (yalnız kullanıcı isteğiyle)."""
        try:
            webbrowser.open(API_KEY_HELP_URL)
            return True
        except Exception:
            self.set_operation_status(
                tr("Tarayıcı açılamadı. Rehber adresini elle girebilirsiniz."))
            return False

    # --- Controller sözleşmesi ---

    @property
    def language_box(self):
        """Arama satırındaki dil kutusu ANA pencereye aittir."""
        return self._center.language_box

    def set_operation_status(self, text):
        """Ayar durumu BU pencerede gösterilir; arama durumu ezilmez."""
        self.status_label.setText(text or "")

    def status_text(self):
        return self.status_label.text()

    def credential_hint_text(self):
        return self.credential_hint.text()
