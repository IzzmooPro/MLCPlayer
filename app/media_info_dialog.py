"""Tek sayfa Medya Bilgisi penceresi: INCE cizim katmani.

Bu pencere YALNIZ hazir bir `MediaInfoSnapshot` alir ve cizer. Oynatici veya
libmpv nesnesi okumaz, ham anahtar veya metadata YORUMLAMAZ; butun
normalize etme isi `app/media_info.py` icindedir. Menu, QAction, tekillik
sahipligi ve kapanis bagi bu dosyanin sorumlulugu DEGILDIR.

Guvenlik sozlesmesi
-------------------
- Snapshot'tan gelen her metin `Qt.TextFormat.PlainText` ile cizilir:
  `<b>Baslik</b>` gibi metadata bicimlendirme olarak YORUMLANMAZ.
- Deger etiketleri secilebilir ama link ACMAZ.
- `copy_value` hicbir QLabel, tooltip, accessibleName, objectName, statusTip
  veya whatsThis metnine yazilmaz. Yalniz Python alaninda tutulur ve ANCAK
  kullanici kopyalama dugmesine bastiginda disari verilir.
- Timer, thread, ag, child process ve `exec()` YOKTUR.

KULLANICI KARARI: sekmeli gorunum KALDIRILDI. Tek kaydirilabilir sayfada
yukaridan asagiya `Genel -> Video -> Ses -> Altyazi` bolumleri; her ses ve
altyazi parcasi kendi karti. Pencere icerikle sinirsiz buyumez: buyuyen tek
sey kaydirmadir ve dugmeler kaydirma alaninin DISINDA, altta sabittir.
"""
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget)

WINDOW_TITLE_PREFIX = "Medya Bilgisi"
CLOSE_BUTTON_TEXT = "Kapat"

DEFAULT_SIZE = (680, 520)
MINIMUM_SIZE = (560, 380)

STYLE = """
QDialog#mediaInfo { background-color: #151A1F; }
QLabel { color: #E6EAF0; background: transparent; }
QLabel#mediaInfoRowLabel { color: #9AA6B2; }
QLabel#mediaInfoGroupTitle { color: #E6EAF0; font-weight: 600; }
QLabel#mediaInfoEmpty { color: #9AA6B2; }
QFrame#mediaInfoGroup { background-color: #1A2027; border-radius: 6px; }
QLabel#mediaInfoSectionTitle { color: #E6EAF0; font-size: 15px;
                              font-weight: 700; padding-top: 4px; }
QFrame#mediaInfoSectionRule { background-color: rgba(255, 255, 255, 28);
                              max-height: 1px; min-height: 1px; }
QWidget#mediaInfoBody { background-color: #11151A; }
QScrollArea { border: none; background: transparent; }
QPushButton { background-color: #232B33; color: #E6EAF0; border: none;
              border-radius: 4px; padding: 6px 14px; }
QPushButton:hover { background-color: #2C353F; }
"""


class _BoundedScrollArea(QScrollArea):
    """`sizeHint()` icerikle BUYUMEZ.

    Varsayilan QScrollArea, `setWidgetResizable(True)` ile govdesinin
    tercihini disari yansitir; 40 track'li bir medyada pencere kendini
    buyutuyordu. Sabit tercih, kaydirmayi tek buyume yolu birakir.
    """

    HINT = QSize(520, 320)

    def sizeHint(self):
        return QSize(self.HINT)


def _plain_label(text, object_name):
    """Snapshot metni ICIN tek uretici: her zaman DUZ METIN."""
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setOpenExternalLinks(False)
    # Secilebilir ama link acmaz: link bayraklari BILINCLI olarak yok.
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    return label


class MediaInfoDialog(QDialog):
    """Modeless, sekmeli medya bilgisi penceresi.

    `copy_text` testlerin GERCEK sistem panosunu kirletmemesi icindir;
    verilmezse urun `QApplication.clipboard().setText` kullanir.
    """

    def __init__(self, snapshot, parent=None, copy_text=None):
        super().__init__(parent)
        self.setObjectName("mediaInfo")
        self.setStyleSheet(STYLE)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumSize(*MINIMUM_SIZE)
        self.resize(*DEFAULT_SIZE)

        # Tam yol / adres YALNIZ burada durur; hicbir widget metnine gecmez.
        self._copy_value = ""
        self._copy_text = copy_text

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # TEK kaydırma alanı; gövde her yenilemede baştan kurulur.
        self.scroll_area = _BoundedScrollArea(self)
        self.scroll_area.setObjectName("mediaInfoScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll_area, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_button = QPushButton("", self)
        self.copy_button.setObjectName("mediaInfoCopyButton")
        self.copy_button.setAutoDefault(False)
        self.copy_button.setDefault(False)
        self.copy_button.clicked.connect(self.copy_current_value)
        self.close_button = QPushButton(CLOSE_BUTTON_TEXT, self)
        self.close_button.setObjectName("mediaInfoCloseButton")
        self.close_button.setAutoDefault(False)
        self.close_button.setDefault(False)
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.copy_button, 0)
        actions.addStretch(1)
        actions.addWidget(self.close_button, 0)
        root.addLayout(actions)

        self.set_snapshot(snapshot)

    # --- Cizim ---

    def set_snapshot(self, snapshot):
        """Ayni pencereyi TAMAMEN yeniler; yeni pencere uretilmez.

        Gövde baştan kurulur: eski medya metni, eski kartlar ve eski
        kopyalama hedefi kalmaz. Kaydırma alanı ve düğmeler korunur.
        """
        body = QWidget()
        body.setObjectName("mediaInfoBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        if snapshot is not None:
            for section in snapshot.sections:
                self._add_section(layout, section)
        layout.addStretch(1)
        # `setWidget()` eski gövdeyi sahiplenip siler; artık widget kalmaz.
        self.scroll_area.setWidget(body)
        if snapshot is None:
            self.setWindowTitle(WINDOW_TITLE_PREFIX)
            self._copy_value = ""
            self.copy_button.setText("")
            self.copy_button.setEnabled(False)
            return
        self.setWindowTitle(f"{WINDOW_TITLE_PREFIX} — {snapshot.title}")
        self._copy_value = snapshot.copy_value or ""
        self.copy_button.setText(snapshot.copy_label or "")
        self.copy_button.setEnabled(bool(self._copy_value))

    def _add_section(self, layout, section):
        """Belirgin başlık + ince ayraç + kartlar (veya boş mesaj)."""
        title = _plain_label(section.title, "mediaInfoSectionTitle")
        layout.addWidget(title)
        rule = QFrame()
        rule.setObjectName("mediaInfoSectionRule")
        rule.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(rule)
        if section.is_empty:
            layout.addWidget(_plain_label(section.empty_message,
                                          "mediaInfoEmpty"))
            return
        for group in section.groups:
            layout.addWidget(self._build_group(group))

    def _build_group(self, group):
        frame = QFrame()
        frame.setObjectName("mediaInfoGroup")
        layout = QGridLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(4)
        row_index = 0
        if group.title:
            title = _plain_label(group.title, "mediaInfoGroupTitle")
            layout.addWidget(title, 0, 0, 1, 2)
            row_index = 1
        for offset, row in enumerate(group.rows):
            layout.addWidget(_plain_label(row.label, "mediaInfoRowLabel"),
                             row_index + offset, 0,
                             Qt.AlignmentFlag.AlignTop)
            layout.addWidget(_plain_label(row.value, "mediaInfoRowValue"),
                             row_index + offset, 1,
                             Qt.AlignmentFlag.AlignTop)
        layout.setColumnStretch(1, 1)
        return frame

    # --- Kopyalama ---

    def copy_current_value(self):
        """YALNIZ kullanici tiklamasiyla calisir.

        Hata durumunda pencere kapanmaz ve ham hata metni GOSTERILMEZ;
        ayrica basari popup'i veya OSD uretilmez.
        """
        value = self._copy_value
        if not value:
            return False
        try:
            if self._copy_text is not None:
                self._copy_text(value)
            else:
                QApplication.clipboard().setText(value)
        except Exception:
            return False
        return True
