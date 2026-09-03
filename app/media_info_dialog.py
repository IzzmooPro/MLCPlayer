# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Sekmeli Medya Bilgisi penceresi: INCE cizim katmani.

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

KULLANICI KARARI: `Genel -> Video -> Ses -> Altyazi` dort gercek sekmedir.
Her sekmenin kendi kaydirma alani vardir; her ses ve altyazi parcasi kendi
karti olarak kalir. Pencere icerikle sinirsiz buyumez ve dugmeler sekmelerin
DISINDA, altta sabittir.
"""
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QSizePolicy, QTabWidget, QVBoxLayout, QWidget)

from app.config import UI_ACCENT, UI_FONT_FAMILY

WINDOW_TITLE_PREFIX = "Medya Bilgisi"
CLOSE_BUTTON_TEXT = "Kapat"

DEFAULT_SIZE = (520, 420)
MINIMUM_SIZE = (460, 320)

STYLE = """
QDialog#mediaInfo { background-color: #151A1F;
                    font-family: __UI_FONT_FAMILY__; }
QLabel { color: #E6EAF0; background: transparent; }
QLabel#mediaInfoRowLabel { color: #9AA6B2; }
QLabel#mediaInfoGroupTitle { color: #E6EAF0; font-weight: 600; }
QLabel#mediaInfoEmpty { color: #9AA6B2; }
QFrame#mediaInfoGroup { background-color: #1A2027; border-radius: 6px; }
QWidget#mediaInfoBody { background-color: #11151A; }
QScrollArea { border: none; background: transparent; }
QTabWidget#mediaInfoTabs::pane { border: 1px solid #2A323A;
                                 border-radius: 6px;
                                 background-color: #11151A; }
QTabBar::tab { color: #AEB7C0; background-color: #1A2027;
               border: none; border-bottom: 2px solid transparent;
               min-width: 72px; padding: 7px 10px; }
QTabBar::tab:selected { color: #FFFFFF; background-color: #202832;
                        border-bottom-color: __UI_ACCENT__; }
QTabBar::tab:hover:!selected { color: #E6EAF0; background-color: #20262E; }
QTabBar::tab:focus { color: #FFFFFF; background-color: #29323A; }
QPushButton { background-color: #232B33; color: #E6EAF0; border: none;
              border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background-color: #2C353F; }
QPushButton:focus { border: 1px solid #707A84; }
QPushButton#mediaInfoCopyButton { background: transparent;
                                  border: 1px solid #414950; }
QPushButton#mediaInfoCopyButton:hover { background: #252D35;
                                        border-color: #59636C; }
QPushButton#mediaInfoCloseButton { background: #303840;
                                   border: 1px solid #46515B;
                                   font-weight: 600; }
QPushButton#mediaInfoCloseButton:hover { background: #39434C; }
""".replace("__UI_ACCENT__", UI_ACCENT).replace(
    "__UI_FONT_FAMILY__", UI_FONT_FAMILY)


class _BoundedScrollArea(QScrollArea):
    """`sizeHint()` icerikle BUYUMEZ.

    Varsayilan QScrollArea, `setWidgetResizable(True)` ile govdesinin
    tercihini disari yansitir; 40 track'li bir medyada pencere kendini
    buyutuyordu. Sabit tercih, kaydirmayi tek buyume yolu birakir.
    """

    HINT = QSize(400, 260)

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
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Sekme kabugu ve her sekmenin kaydirma alani yenilemede korunur;
        # yalniz hazir snapshot'tan cizilen govdeler degisir.
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("mediaInfoTabs")
        self.tabs.setDocumentMode(True)
        self._section_areas = {}
        root.addWidget(self.tabs, 1)

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
        if snapshot is None:
            self._replace_sections(())
            self.setWindowTitle(WINDOW_TITLE_PREFIX)
            self._copy_value = ""
            self.copy_button.setText("")
            self.copy_button.setEnabled(False)
            return
        self._replace_sections(snapshot.sections)
        self.setWindowTitle(f"{WINDOW_TITLE_PREFIX} — {snapshot.title}")
        self._copy_value = snapshot.copy_value or ""
        self.copy_button.setText(snapshot.copy_label or "")
        self.copy_button.setEnabled(bool(self._copy_value))

    def _replace_sections(self, sections):
        """Sekme kabugunu koruyup her sekmenin govdesini atomik yeniler."""
        current = self.tabs.currentWidget()
        current_key = (current.property("mediaInfoSectionKey")
                       if current is not None else None)
        wanted = {section.key for section in sections}
        self.tabs.clear()
        for key in tuple(self._section_areas):
            if key not in wanted:
                self._section_areas.pop(key).deleteLater()
        restore_index = 0
        for index, section in enumerate(sections):
            area = self._section_areas.get(section.key)
            if area is None:
                area = _BoundedScrollArea(self.tabs)
                area.setObjectName(f"mediaInfoScroll_{section.key}")
                area.setWidgetResizable(True)
                area.setFrameShape(QFrame.Shape.NoFrame)
                area.setProperty("mediaInfoSectionKey", section.key)
                self._section_areas[section.key] = area
            area.setWidget(self._build_section_body(section))
            area.verticalScrollBar().setValue(0)
            self.tabs.addTab(area, section.title)
            if section.key == current_key:
                restore_index = index
        if self.tabs.count():
            self.tabs.setCurrentIndex(restore_index)

    def _build_section_body(self, section):
        body = QWidget()
        body.setObjectName("mediaInfoBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        if section.is_empty:
            layout.addWidget(_plain_label(section.empty_message,
                                          "mediaInfoEmpty"))
        else:
            for group in section.groups:
                layout.addWidget(self._build_group(group))
        layout.addStretch(1)
        return body

    def _build_group(self, group):
        frame = QFrame()
        frame.setObjectName("mediaInfoGroup")
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setHorizontalSpacing(12)
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
