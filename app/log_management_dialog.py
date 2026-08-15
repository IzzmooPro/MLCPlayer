"""Ayrı "Günlük Yönetimi" penceresi (3. aşama).

Bu pencere YALNIZ saklama politikasını ve toplam boyutu gösterir,
klasörü açar ve onay aldıktan sonra izinli günlük dosyalarını siler.

Bilerek YAPMADIKLARI:

- Log İÇERİĞİNİ göstermez (hassas tanı metni ekrana basılmaz).
- Mutlak kullanıcı yolunu ekrana yazmaz.
- Açılışta hiçbir dosyayı değiştirmez, panoya yazmaz, ağa çıkmaz.
- Hata bildirme/gönderme akışı İÇERMEZ (sonraki aşama).
- Klasörü açmak için shell/subprocess kullanmaz; `QDesktopServices`.
"""
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox,
                             QSizePolicy, QVBoxLayout)

from app.errors import (LOG_BACKUP_COUNT, MAX_LOG_FILE_BYTES, clear_logs,
                        format_bytes, get_log_directory, get_log_usage,
                        safe_console)

DIALOG_TITLE = "Günlük Yönetimi"
INTRO_TEXT = ("Günlükler yalnız destek ve hata tanısı için bu bilgisayarda "
              "tutulur. Hassas bilgiler kaydedilirken otomatik olarak "
              "gizlenir.")
POLICY_TEXT = ("Saklama politikası: en fazla 2 MiB aktif dosya + 1 yedek "
               "dosya. Sınır aşılınca en eski yedek silinir.")
USAGE_PREFIX = "Mevcut günlük boyutu:"
OPEN_BUTTON_TEXT = "Günlük Klasörünü Aç"
CLEAR_BUTTON_TEXT = "Günlükleri Temizle"
CLOSE_BUTTON_TEXT = "Kapat"

CONFIRM_TITLE = "Günlükleri Temizle"
CONFIRM_TEXT = ("Tanı günlükleri kalıcı olarak silinecek. Bu işlem geri "
                "alınamaz.")
OPEN_FAILED_TEXT = "Günlük klasörü açılamadı."

DEFAULT_SIZE = (560, 320)
MINIMUM_SIZE = (460, 280)

STYLE = """
QDialog#logManagement { background: rgba(19, 20, 22, 255); }
QLabel { color: #E9EDF1; background: transparent; font-size: 12px; }
QLabel#logManagementMuted { color: #8E969F; font-size: 12px; }
QLabel#logManagementUsage { color: #E9EDF1; font-size: 13px; font-weight: 600; }
QLabel#logManagementStatus { color: #8E969F; font-size: 11px; }
QPushButton {
    color: #E9EDF1; background: rgba(255,255,255,14); border: none;
    border-radius: 5px; padding: 7px 13px; font-size: 12px;
}
QPushButton:hover { background: rgba(255,255,255,26); }
"""


def usage_text():
    """Kullanıcı dostu toplam boyut metni. Yol İÇERMEZ."""
    return f"{USAGE_PREFIX} {format_bytes(get_log_usage()['total_bytes'])}"


class LogManagementDialog(QDialog):
    """Sade günlük yönetimi penceresi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logManagement")
        self.setWindowTitle(DIALOG_TITLE)
        self.setStyleSheet(STYLE)
        self.setMinimumSize(*MINIMUM_SIZE)
        self.resize(*DEFAULT_SIZE)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        self.intro_label = QLabel(INTRO_TEXT)
        self.intro_label.setObjectName("logManagementMuted")
        self.intro_label.setWordWrap(True)
        root.addWidget(self.intro_label)

        self.policy_label = QLabel(POLICY_TEXT)
        self.policy_label.setObjectName("logManagementMuted")
        self.policy_label.setWordWrap(True)
        root.addWidget(self.policy_label)

        self.usage_label = QLabel(usage_text())
        self.usage_label.setObjectName("logManagementUsage")
        self.usage_label.setWordWrap(True)
        self.usage_label.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Preferred)
        root.addWidget(self.usage_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("logManagementStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        root.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = self._button("logManagementOpenButton",
                                        OPEN_BUTTON_TEXT)
        self.open_button.clicked.connect(self.open_log_folder)
        self.clear_button = self._button("logManagementClearButton",
                                         CLEAR_BUTTON_TEXT)
        self.clear_button.clicked.connect(self.confirm_clear)
        self.close_button = self._button("logManagementCloseButton",
                                         CLOSE_BUTTON_TEXT)
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.open_button, 0)
        actions.addStretch(1)
        actions.addWidget(self.clear_button, 0)
        actions.addWidget(self.close_button, 0)
        root.addLayout(actions)

    def _button(self, name, text):
        from PyQt6.QtWidgets import QPushButton

        button = QPushButton(text)
        button.setObjectName(name)
        button.setAutoDefault(False)
        button.setDefault(False)
        return button

    # --- durum ---

    def visible_text(self):
        """Ekranda GERÇEKTEN görünen metinlerin tamamı (test için)."""
        return "\n".join([self.windowTitle(), self.intro_label.text(),
                          self.policy_label.text(), self.usage_label.text(),
                          self.status_label.text()])

    def refresh_usage(self):
        self.usage_label.setText(usage_text())

    # --- eylemler ---

    def open_log_folder(self):
        """Klasörü YALNIZ kullanıcı tıklarsa açar; shell kullanmaz."""
        try:
            opened = QDesktopServices.openUrl(
                QUrl.fromLocalFile(get_log_directory()))
        except Exception as exc:
            safe_console("Günlük klasörü açılamadı: "
                         f"{type(exc).__name__}")
            opened = False
        if not opened:
            self.status_label.setText(OPEN_FAILED_TEXT)

    def confirm_clear(self):
        """Önce ONAY sorar; `İptal` varsayılan ve Escape düğmesidir."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(CONFIRM_TITLE)
        box.setText(CONFIRM_TEXT)
        box.setStandardButtons(QMessageBox.StandardButton.Yes
                               | QMessageBox.StandardButton.Cancel)
        cancel = box.button(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is not box.button(
                QMessageBox.StandardButton.Yes):
            return          # İptal: dosya sistemi DEĞİŞMEZ.
        self._clear_logs()

    def _clear_logs(self):
        try:
            result = clear_logs()
        except Exception as exc:
            # Ham istisna metni kullanıcıya ULAŞMAZ.
            safe_console(f"Günlükler temizlenemedi: {type(exc).__name__}")
            self.status_label.setText(
                "Günlükler temizlenemedi. Lütfen tekrar deneyin.")
            self.refresh_usage()
            return
        self.status_label.setText(getattr(result, "message", ""))
        self.refresh_usage()
