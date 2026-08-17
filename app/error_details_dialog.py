"""Ayrı ve güvenli "Hata Ayrıntıları" penceresi (2. aşama).

Ana hata kutusu SADE kalır; kullanıcı isterse `Hata Ayrıntılarını
Görüntüle` düğmesiyle bu pencereyi açar. Burada gösterilen her şey
`app/errors.py` içindeki merkezi `redact()` süzgecinden GEÇER —
`ErrorEvent` zaten maskelenmiş olsa bile gösterim ve kopyalama
sınırlarında savunma amaçlı TEKRAR uygulanır.

Bu pencere:

- Yeni `ErrorEvent` üretmez, yeni log kaydı yazmaz, kayıt numarasını
  değiştirmez.
- Ham istisna nesnesinden traceback YENİDEN OLUŞTURMAZ; yalnız
  `ErrorEvent.developer_detail` gösterilir.
- Log dosyasını OKUMAZ; yalnız ilgili kayıt gösterilir.
- Panoya kendiliğinden yazmaz; yalnız kullanıcı `Bilgileri Kopyala`
  düğmesine basarsa yazar.

Log temizleme ve hata gönderme SONRAKİ aşamalardır; burada yoktur.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QSizePolicy,
                             QVBoxLayout, QWidget)

from app.errors import redact, safe_console
from app.translate import tr, tr_mark, translate_marked

# Modul duzeyi metinler: import aninda cevirmen yoktur; `tr_mark()` yalniz
# isaretler, ceviri kullanim aninda `translate_marked()` ile yapilir.
DIALOG_TITLE = tr_mark("Hata Ayrıntıları")
INTRO_TEXT = tr_mark("Bu bilgiler destek ve tanı amacıyla hazırlanmıştır.\n"
                     "Hassas bilgiler otomatik olarak gizlenmiştir.")
EMPTY_DETAIL = tr_mark("Ek teknik ayrıntı bulunmuyor.")
COPY_BUTTON_TEXT = tr_mark("Bilgileri Kopyala")
CLOSE_BUTTON_TEXT = tr_mark("Kapat")
COPY_DONE_TEXT = tr_mark("Kopyalandı")
COPY_FAILED_TEXT = tr_mark("Kopyalanamadı")

DEFAULT_SIZE = (680, 460)
MINIMUM_SIZE = (520, 360)

# (ErrorEvent alani, KAYNAK dildeki etiket) — SIRA ONEMLIDIR.
# Etiketler yalniz isaretlidir; gosterimde `safe_fields()` cevirir.
FIELDS = (
    ("record_id", tr_mark("Kayıt numarası")),
    ("timestamp", tr_mark("Tarih")),
    ("category", tr_mark("Kategori")),
    ("title", tr_mark("Hata başlığı")),
    ("user_message", tr_mark("Kullanıcı mesajı")),
    ("exception_type", tr_mark("Hata türü")),
    ("technical_summary", tr_mark("Teknik özet")),
)

STYLE = """
QDialog#errorDetails { background: rgba(19, 20, 22, 255); }
QLabel { color: #E9EDF1; background: transparent; font-size: 12px; }
QLabel#errorDetailsIntro { color: #8E969F; font-size: 12px; }
QLabel#errorDetailsFieldLabel { color: #8E969F; font-size: 12px; }
QLabel#errorDetailsStatus { color: #8E969F; font-size: 11px; }
QPlainTextEdit#errorDetailsText {
    color: #E9EDF1; background: rgba(255,255,255,10);
    border: 1px solid rgba(255,255,255,22); border-radius: 5px;
    font-family: Consolas, monospace; font-size: 11px;
}
QPushButton {
    color: #E9EDF1; background: rgba(255,255,255,14); border: none;
    border-radius: 5px; padding: 7px 13px; font-size: 12px;
}
QPushButton:hover { background: rgba(255,255,255,26); }
"""


def safe_fields(event):
    """(etiket, güvenli değer) çiftleri. Her değer yeniden maskelenir."""
    rows = []
    for name, label in FIELDS:
        rows.append((translate_marked(label),
                     redact(getattr(event, name, ""))))
    return rows


def safe_detail(event):
    """Maskelenmiş teknik ayrıntı; boşsa güvenli açıklama."""
    detail = redact(getattr(event, "developer_detail", "") or "")
    return detail if detail.strip() else translate_marked(EMPTY_DETAIL)


def clipboard_text(event):
    """Panoya yazılacak metin: penceredeki AYNI güvenli alanlardan.

    Log dosyası okunmaz; metnin tamamı kopyalamadan hemen önce bir kez
    daha `redact()` işleminden geçer.
    """
    lines = [translate_marked(DIALOG_TITLE), ""]
    for label, value in safe_fields(event):
        lines.append(f"{label}: {value}")
    lines.append("")
    lines.append(f"{tr('Teknik ayrıntı (maskelenmiş)')}:")
    lines.append(safe_detail(event))
    return redact("\n".join(lines))


class ErrorDetailsDialog(QDialog):
    """Tek bir `ErrorEvent`in güvenli görünümü."""

    def __init__(self, event, parent=None):
        super().__init__(parent)
        self.event = event
        self.setObjectName("errorDetails")
        self.setWindowTitle(translate_marked(DIALOG_TITLE))
        self.setStyleSheet(STYLE)
        self.setMinimumSize(*MINIMUM_SIZE)
        self.resize(*DEFAULT_SIZE)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        self.intro_label = QLabel(translate_marked(INTRO_TEXT))
        self.intro_label.setObjectName("errorDetailsIntro")
        self.intro_label.setWordWrap(True)
        root.addWidget(self.intro_label)

        self._field_labels = {}
        fields = QWidget()
        fields.setObjectName("errorDetailsFields")
        grid = QVBoxLayout(fields)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        for (_attr, source_label), (label, value) in zip(FIELDS,
                                                        safe_fields(event)):
            row = QHBoxLayout()
            row.setSpacing(8)
            name = QLabel(f"{label}:")
            name.setObjectName("errorDetailsFieldLabel")
            name.setMinimumWidth(120)
            name.setSizePolicy(QSizePolicy.Policy.Fixed,
                               QSizePolicy.Policy.Preferred)
            # Uzun kayıt numarası ve teknik özet KIRPILMAZ: değer sarar.
            content = QLabel(value)
            # Nesne adi KIMLIKTIR; ceviriyle degismez.
            content.setObjectName(f"errorDetailsValue_{source_label}")
            content.setWordWrap(True)
            content.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            self._field_labels[label] = content
            row.addWidget(name, 0)
            row.addWidget(content, 1)
            grid.addLayout(row)
        root.addWidget(fields, 0)

        detail_caption = QLabel(tr("Teknik ayrıntı (maskelenmiş)"))
        detail_caption.setObjectName("errorDetailsFieldLabel")
        root.addWidget(detail_caption, 0)

        self.detail_view = QPlainTextEdit(safe_detail(event))
        self.detail_view.setObjectName("errorDetailsText")
        self.detail_view.setReadOnly(True)
        self.detail_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.detail_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.detail_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.detail_view.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Expanding)
        # Teknik metin KALAN alanı büyüyerek kullanır.
        root.addWidget(self.detail_view, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.status_label = QLabel("")
        self.status_label.setObjectName("errorDetailsStatus")
        self.copy_button = QPushButton(translate_marked(COPY_BUTTON_TEXT))
        self.copy_button.setObjectName("errorDetailsCopyButton")
        self.copy_button.setAutoDefault(False)
        self.copy_button.setDefault(False)
        self.copy_button.clicked.connect(self.copy_details)
        self.close_button = QPushButton(translate_marked(CLOSE_BUTTON_TEXT))
        self.close_button.setObjectName("errorDetailsCloseButton")
        self.close_button.setAutoDefault(False)
        self.close_button.setDefault(False)
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.status_label, 1)
        actions.addWidget(self.copy_button, 0)
        actions.addWidget(self.close_button, 0)
        root.addLayout(actions)

    # --- durum ---

    def intro_text(self):
        return self.intro_label.text()

    def fields(self):
        return [(label, self._field_labels[label].text())
                for label, _value in safe_fields(self.event)]

    def detail_text(self):
        return self.detail_view.toPlainText()

    # --- pano ---

    def _write_clipboard(self, text):
        """Gerçek pano yazımı; testler bunu değiştirebilir."""
        QApplication.clipboard().setText(text)

    def copy_details(self):
        """YALNIZ kullanıcı tıklayınca çalışır; tek yazma yapar."""
        try:
            self._write_clipboard(clipboard_text(self.event))
        except Exception as exc:
            # Ham veri veya ham istisna metni KONSOLA yazılmaz.
            safe_console("Hata ayrıntıları panoya kopyalanamadı: "
                         f"{type(exc).__name__}")
            self.status_label.setText(translate_marked(COPY_FAILED_TEXT))
            return
        # Küçük, dikkat dağıtmayan geri bildirim: yeni pencere AÇILMAZ.
        self.status_label.setText(translate_marked(COPY_DONE_TEXT))
