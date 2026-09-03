# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Merkezi — MLC Player sinematik dilinde KOMPAKT yardımcı pencere.

Bu modül YALNIZCA arayüzdür: ağ çağrısı, indirme, dosya yazma, MPV track
işlemi veya ayar kalıcılığı YOKTUR. Sonuçlar çağıran tarafından verilir
(`show_results`); tasarım doğrulaması için `sample_results()` sahte veri
sağlar.

Tasarım kararı: büyük yönetim ekranı değil, hızlı kullanılan yardımcı pencere.

    [ Altyazı Merkezi                                            ⚙ ]
    [ ad  | Sezon | Bölüm | Dil |                            (Ara) ]
    [ ------------- kaydırılabilir sonuç listesi ------------------ ]
    [ 4 sonuç                      İndir ve Uygula | Kapat         ]

Teknik medya özeti, arama türü radio düğmeleri ve uzun hedef dosya
açıklaması bilinçli olarak YOKTUR. Hedef dosya adı indirme düğmesinin
tooltip'inde taşınır.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLayout,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from app.config import UI_ACCENT
from app.ui_icons import make_media_icon
from app.i18n import tr, tr_mark, translate_marked

ACCENT = UI_ACCENT
SURFACE = "rgba(19, 20, 22, 255)"
TEXT = "#E9EDF1"
MUTED = "#8E969F"

# Dil seçimi: KOD ile ETİKET ayrıdır. Kod `QComboBox` öğesinin `data()`
# alanında taşınır; etiket serbestçe çevrilir. Görünen metni kimlik olarak
# kullanmak, arayüz çevrildiğinde arama dilini sessizce Türkçeye
# düşürüyordu (`tests/test_subtitle_language_translation_regressions.py`).
LANGUAGE_CHOICES = (
    ("tr", tr_mark("Türkçe")),
    ("en", tr_mark("İngilizce")),
    ("de", tr_mark("Almanca")),
    ("fr", tr_mark("Fransızca")),
    ("es", tr_mark("İspanyolca")),
)

#: Geriye dönük ad; yalnız GÖRÜNEN etiketler.
LANGUAGES = tuple(label for _code, label in LANGUAGE_CHOICES)

#: Kutunun açılışta seçili geleceği dil.
DEFAULT_LANGUAGE_CODE = "tr"


def populate_language_box(box):
    """Dil kutusunu KOD + çevrilmiş etiketle doldurur."""
    box.clear()
    for code, label in LANGUAGE_CHOICES:
        box.addItem(translate_marked(label), code)
    return box


def _code_for_label(label):
    """KAYNAK dildeki etiket → dil kodu. Bilinmiyorsa `None`."""
    for code, source in LANGUAGE_CHOICES:
        if source == label:
            return code
    return None


def select_language_label(box, label):
    """Kutuyu KAYNAK dildeki etikete göre seçer.

    Ayar deposu kaynak dildeki adı tutar (`Almanca`); kutunun GÖRÜNEN metni
    çevrilmiş olabilir. `setCurrentText()` bu yüzden kullanılamaz — eşleşme
    bulamayınca kutu sessizce ilk öğede kalır ve kullanıcının tercihi
    kaybolur. Dönüş: seçim yapıldıysa `True`.
    """
    code = _code_for_label(label)
    if code is None:
        return False
    index = box.findData(code)
    if index < 0:
        return False
    box.setCurrentIndex(index)
    return True


def current_language_label(box):
    """Seçili dilin KAYNAK dildeki adı; depoya bu yazılır.

    Böylece kayıt biçimi arayüz diline göre DEĞİŞMEZ ve eski kurulumlarla
    uyumlu kalır.
    """
    code = box.currentData()
    for source_code, label in LANGUAGE_CHOICES:
        if source_code == code:
            return label
    return box.currentText()
CARD_HEIGHT = 56
# Kompakt yardımcı pencere: içerik kadar yüksek, sonuç sayısıyla büyümez.
DEFAULT_SIZE = (660, 440)
MINIMUM_SIZE = (620, 420)
# Ad alanı gerçekten yazılabilir olmalı; birkaç karakterlik kutu kabul değil.
TITLE_MIN_WIDTH = 240

STYLE = f"""
QDialog#subtitleCenter {{ background: {SURFACE}; }}
QLabel {{ color: {TEXT}; background: transparent; font-size: 13px; }}
QLabel#subtitleHeading {{ font-size: 15px; }}
QLabel#subtitleStatus {{ color: {MUTED}; font-size: 12px; }}
QLabel#subtitleMeta {{ color: {MUTED}; font-size: 11px; }}
QLabel#subtitleMatch {{ color: {ACCENT}; font-size: 11px; font-weight: 600; }}
QLabel#subtitleFieldLabel {{ color: {MUTED}; font-size: 12px; }}

QLineEdit, QComboBox {{
    color: {TEXT}; background: rgba(255,255,255,12);
    border: 1px solid rgba(255,255,255,22); border-radius: 5px;
    padding: 5px 8px; font-size: 13px;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: rgba(242,106,61,150); }}

QCheckBox {{ color: {TEXT}; font-size: 12px; spacing: 7px; }}
/* Qt varsayilan gostergesi eski form gorunumu verir. */
QCheckBox::indicator {{
    width: 14px; height: 14px; border-radius: 3px;
    border: 1px solid rgba(255,255,255,60); background: rgba(255,255,255,10);
}}
QCheckBox::indicator:hover {{ border-color: rgba(242,106,61,150); }}
QCheckBox::indicator:checked {{ border: 1px solid {ACCENT}; background: {ACCENT}; }}

QPushButton {{
    color: {TEXT}; background: rgba(255,255,255,14); border: none;
    border-radius: 5px; padding: 7px 13px; font-size: 12px;
}}
QPushButton:hover {{ background: rgba(255,255,255,26); }}
QPushButton:disabled {{ color: rgba(233,237,241,70);
                        background: rgba(255,255,255,6); }}
QPushButton#subtitlePrimaryAction {{
    color: #FFFFFF; background: {ACCENT}; font-weight: 600;
}}
QPushButton#subtitlePrimaryAction:hover {{ background: #FF7A48; }}
QPushButton#subtitlePrimaryAction:disabled {{
    background: rgba(242,106,61,80); color: rgba(255,255,255,110);
}}
QPushButton#subtitleGear {{ background: transparent; padding: 4px; }}
QPushButton#subtitleGear:hover {{ background: rgba(255,255,255,22); }}

/* Kartlar kalin cerceveli kutu degil; ince ayirici cizgiyle ayrilir. */
QFrame#subtitleCard {{
    background: transparent; border: none;
    border-bottom: 1px solid rgba(255,255,255,14);
    border-left: 2px solid transparent;
}}
QFrame#subtitleCard:hover {{ background: rgba(255,255,255,10); }}
QFrame#subtitleCard[selected="true"] {{
    background: rgba(242,106,61,26); border-left: 2px solid {ACCENT};
}}

QWidget#subtitleDrawer {{
    background: rgba(255,255,255,8);
    border-left: 1px solid rgba(255,255,255,20);
}}
QScrollArea {{ background: transparent; border: 1px solid rgba(255,255,255,14);
               border-radius: 6px; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
"""


def sample_results():
    """Tasarım doğrulaması için sahte sonuç kümesi (ağ YOK)."""
    return [
        {
            "file_id": 7135238,
            "name": "Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb",
            "language": "Türkçe", "format": "srt",
            "moviehash_match": True, "downloads": 4321, "ratings": 9.1,
            "hearing_impaired": False,
        },
        {
            "file_id": 7135240,
            "name": "Resident Alien 1x01 - Pilot (TR)",
            "language": "Türkçe", "format": "srt",
            "moviehash_match": False, "downloads": 1180, "ratings": 8.2,
            "hearing_impaired": False,
        },
        {
            "file_id": 7135241,
            "name": "Resident.Alien.S01E01.Pilot.HI.Turkish",
            "language": "Türkçe", "format": "srt",
            "moviehash_match": False, "downloads": 640, "ratings": 7.4,
            "hearing_impaired": True,
        },
        {
            "file_id": 7135242,
            "name": ("Resident.Alien.S01E01.Pilot.REPACK.PROPER.EXTENDED."
                     "1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.TURKISH.FORCED.v3"),
            "language": "Türkçe", "format": "srt",
            "moviehash_match": False, "downloads": 92, "ratings": 6.0,
            "hearing_impaired": False,
        },
    ]


class ResultCard(QFrame):
    """Tek sonuç: iki satır, sabit yükseklik, seçilince turuncu vurgu."""

    def __init__(self, result, on_click, parent=None):
        super().__init__(parent)
        self.result = dict(result)
        self._on_click = on_click
        self.setObjectName("subtitleCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(CARD_HEIGHT)
        self.setAccessibleName(
            f"{tr('Altyazı sonucu:')} {self.result['name']}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

        # 1. satır: ad (elide, tam metin tooltip'te)
        self.name_label = QLabel(self.result["name"], self)
        self.name_label.setWordWrap(False)
        self.name_label.setFixedHeight(17)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Fixed)
        self.name_label.setToolTip(self.result["name"])
        layout.addWidget(self.name_label)

        # 2. satır: eşleşme, dil, biçim, indirme, puan
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(12)
        self._meta_labels = []
        if self.result.get("moviehash_match"):
            self._meta_labels.append(self._meta(tr("Tam eşleşme"),
                                                accent=True))
        if self.result.get("hearing_impaired"):
            self._meta_labels.append(self._meta(tr("İşitme engelli")))
        self._meta_labels.append(self._meta(self.result.get("language", "")))
        self._meta_labels.append(self._meta(self.result.get("format", "").upper()))
        self._meta_labels.append(
            self._meta(f"{self.result.get('downloads', 0)} {tr('indirme')}"))
        self._meta_labels.append(
            self._meta(f"{tr('Puan')} {self.result.get('ratings', 0)}"))
        for label in self._meta_labels:
            meta_row.addWidget(label)
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

    def _meta(self, text, accent=False):
        label = QLabel(text, self)
        label.setObjectName("subtitleMatch" if accent else "subtitleMeta")
        return label

    def line_count(self):
        return 2

    def meta_text(self):
        return " · ".join(label.text() for label in self._meta_labels
                          if label.text())

    def summary_text(self):
        return f"{self.result['name']} · {self.meta_text()}"

    def set_selected(self, selected):
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        metrics = self.name_label.fontMetrics()
        width = max(40, self.name_label.width())
        self.name_label.setText(metrics.elidedText(
            self.result["name"], Qt.TextElideMode.ElideRight, width))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._on_click:
            self._on_click(self)
            event.accept()
            return
        super().mousePressEvent(event)


class SubtitleCenterDialog(QDialog):
    """Altyazı Merkezi'nin kompakt görsel kabuğu."""

    # Dişli düğmesi ayarları BU pencerede açmaz; isteği koordinatöre iletir.
    settings_requested = pyqtSignal()

    def __init__(self, player=None, media=None):
        super().__init__(player)
        self.player = player
        self.media = dict(media or {})
        self._selected_card = None
        self._overwrite_warning = False
        self._result_count = 0
        self._state_text = ""
        # İndirme/uygulama gibi işlemlerin kısa durumu. Doluyken durum
        # satırını devralır; sonuç listesi ve seçim korunur.
        self._operation_text = ""
        # Kurulum sırasındaki boş liste varsayılan boyutu küçültmesin;
        # yükseklik uyumu ilk gerçek arama sonucundan itibaren çalışır.
        self._auto_fit_enabled = False

        self.setObjectName("subtitleCenter")
        self.setWindowTitle(tr("Altyazı Merkezi"))
        self.setStyleSheet(STYLE)
        self.setMinimumSize(*MINIMUM_SIZE)
        self.resize(*DEFAULT_SIZE)

        # Ayarlar ARTIK ayrı bir pencerede açılır (bkz.
        # `app/subtitle_center_settings_dialog.py`). Eski sağdan açılan
        # çekmece ana arama alanını eziyordu; kaldırıldı.
        main = QVBoxLayout(self)
        main.setContentsMargins(14, 12, 14, 12)
        main.setSpacing(10)
        self._build_header(main)
        self._build_search_row(main)
        self._build_results(main)
        self._build_action_row(main)

        self._apply_series_visibility()
        self.show_results([])
        self._auto_fit_enabled = True

    # --- Başlık: ad + dişli ---

    def _build_header(self, layout):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.heading_label = QLabel(tr("Altyazı Merkezi"), self)
        self.heading_label.setObjectName("subtitleHeading")
        row.addWidget(self.heading_label)
        row.addStretch(1)

        self.settings_icon_button = QPushButton(self)
        self.settings_icon_button.setObjectName("subtitleGear")
        # Mevcut QPainter ikon sistemi; harici asset yok.
        self.settings_icon_button.setIcon(make_media_icon("settings", 17, TEXT))
        # İkon küçük kalabilir ama gerçek tıklama alanı en az 32x32 olmalı.
        self.settings_icon_button.setFixedSize(32, 32)
        self.settings_icon_button.setAccessibleName(tr("Ayarlar"))
        self.settings_icon_button.setToolTip(tr("Ayarlar"))
        self.settings_icon_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_icon_button.clicked.connect(self.settings_requested)
        row.addWidget(self.settings_icon_button)
        layout.addLayout(row)

    # --- Tek yatay arama satırı ---

    def _build_search_row(self, layout):
        # İKİ SATIR: başlık kendi satırında TAM genişlik alır.
        #
        # Tek satırda başlık, sezon/bölüm/dil/Ara ile yarışıyordu ve 660 px
        # dialogda 148 px'e, ayar çekmecesi açıkken 35 px'e (birkaç karakter)
        # düşüyordu. Ölçüm kullanıcının bildirdiği hatayla birebir aynıydı.
        self.title_field = QLineEdit(self.media.get("title", ""), self)
        self.title_field.setPlaceholderText(tr("Film veya dizi adı"))
        self.title_field.setAccessibleName(tr("Aranacak ad"))
        self.title_field.setMinimumWidth(TITLE_MIN_WIDTH)
        # Uzun ad yazılabilir; görünmeyen bölüm imleçle gezilir, tamamı
        # tooltip'te okunur.
        self.title_field.setToolTip(self.title_field.text())
        self.title_field.textChanged.connect(self.title_field.setToolTip)
        layout.addWidget(self.title_field)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        # Tek harfli "S"/"B" kullanıcıya anlamsızdı; alan başlıkları açık yazılır.
        self.season_label = QLabel(tr("Sezon"), self)
        self.season_label.setObjectName("subtitleFieldLabel")
        self.season_field = QLineEdit(self)
        self.season_field.setMaximumWidth(44)
        self.season_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.season_field.setAccessibleName(tr("Sezon"))
        self.season_field.setToolTip(tr("Sezon"))
        self.episode_label = QLabel(tr("Bölüm"), self)
        self.episode_label.setObjectName("subtitleFieldLabel")
        self.episode_field = QLineEdit(self)
        self.episode_field.setMaximumWidth(44)
        self.episode_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.episode_field.setAccessibleName(tr("Bölüm"))
        self.episode_field.setToolTip(tr("Bölüm"))
        for widget in (self.season_label, self.season_field,
                       self.episode_label, self.episode_field):
            row.addWidget(widget)
        row.addStretch(1)

        self.language_box = QComboBox(self)
        populate_language_box(self.language_box)
        self.language_box.setCurrentIndex(
            self.language_box.findData(DEFAULT_LANGUAGE_CODE))
        self.language_box.setAccessibleName(tr("Altyazı dili"))
        self.language_box.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self.language_box)

        self.search_button = QPushButton(tr("Ara"), self)
        self.search_button.setObjectName("subtitlePrimaryAction")
        self.search_button.setAccessibleName(tr("Altyazı ara"))
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.setDefault(True)
        self.search_button.setAutoDefault(True)
        row.addWidget(self.search_button)

        self._search_row = [self.title_field, self.season_field,
                            self.episode_field, self.language_box,
                            self.search_button]
        layout.addLayout(row)

    def search_row_widgets(self):
        return list(self._search_row)

    def _apply_series_visibility(self):
        series = bool(self.media.get("is_series"))
        if series:
            self.season_field.setText(str(self.media.get("season") or ""))
            self.episode_field.setText(str(self.media.get("episode") or ""))
        for widget in (self.season_label, self.season_field,
                       self.episode_label, self.episode_field):
            widget.setVisible(series)

    # --- Sonuç listesi ---

    def _build_results(self, layout):
        self.results_area = QScrollArea(self)
        self.results_area.setWidgetResizable(True)
        self.results_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_host = QWidget(self.results_area)
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(0)
        # Alan yetmezse kartlar EZİLMEZ, liste kaydırılır.
        self.results_layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinimumSize)
        self.results_layout.addStretch(1)
        self.results_area.setWidget(self.results_host)
        layout.addWidget(self.results_area, 1)

        self.empty_label = QLabel("", self)
        self.empty_label.setObjectName("subtitleStatus")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                       QSizePolicy.Policy.Fixed)
        layout.addWidget(self.empty_label)

    def result_cards(self):
        return [self.results_layout.itemAt(index).widget()
                for index in range(self.results_layout.count())
                if isinstance(self.results_layout.itemAt(index).widget(),
                              ResultCard)]

    def results_content_height(self):
        return sum(card.height() for card in self.result_cards())

    def results_gap(self):
        """Sonuçların altında kalan kullanılmayan dikey alan (px)."""
        viewport = self.results_area.viewport().height()
        return max(0, viewport - self.results_content_height())

    def _fit_height_to_content(self):
        """Pencere yüksekliğini içeriğe göre ayarlar.

        Sonuç sayısı arttığında pencere BÜYÜMEZ (varsayılan yükseklik tavan),
        az sonuçta da minimumun altına inmez. Böylece dört sonuçta listenin
        altında büyük anlamsız boşluk kalmaz.
        """
        if not self._auto_fit_enabled:
            return
        self.layout().activate()
        chrome = self.height() - self.results_area.height()
        if chrome <= 0:
            return
        desired = chrome + self.results_content_height() + 4
        target = max(MINIMUM_SIZE[1], min(DEFAULT_SIZE[1], desired))
        if target != self.height():
            self.resize(self.width(), target)
            self.layout().activate()

    def _clear_results(self):
        for card in self.result_cards():
            self.results_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._selected_card = None

    def show_results(self, results):
        self._operation_text = ""
        self._clear_results()
        results = list(results or [])
        for index, result in enumerate(results):
            card = ResultCard(result, self.select_result, self.results_host)
            self.results_layout.insertWidget(index, card)
        self._result_count = len(results)
        self._state_text = "" if results else tr("Altyazı bulunamadı.")
        self._refresh_status()
        self._sync_action_state()
        self._fit_height_to_content()

    def show_loading(self):
        self._operation_text = ""
        self._clear_results()
        self._result_count = 0
        self._state_text = tr("Altyazılar aranıyor…")
        self._refresh_status()
        self._sync_action_state()

    def show_error(self, message):
        self._operation_text = ""
        self._clear_results()
        self._result_count = 0
        self._state_text = (translate_marked(message) if message
                            else tr("Beklenmeyen bir sorun oluştu."))
        self._refresh_status()
        self._sync_action_state()

    def select_result(self, card):
        for other in self.result_cards():
            other.set_selected(other is card)
        self._selected_card = card
        self._sync_action_state()

    def selected_result(self):
        return self._selected_card.result if self._selected_card else None

    # --- Alt işlem satırı ---

    def _build_action_row(self, layout):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("subtitleStatus")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                        QSizePolicy.Policy.Preferred)
        row.addWidget(self.status_label, 1)

        target = self.media.get("target_name", "")
        tooltip = f"{tr('Video klasörüne şu adla kaydedilecek:')} {target}"

        # TEK ana eylem. Eski "Yalnızca İndir" düğmesi kaldırıldı: iki
        # düğme aynı dosyayı aynı yere yazdığı için fark yalnız MPV'ye
        # uygulanıp uygulanmamasıydı ve bu ayrım kullanıcıya çelişkili
        # görünüyordu.
        self.apply_button = QPushButton(tr("İndir ve Uygula"), self)
        self.apply_button.setObjectName("subtitlePrimaryAction")
        self.apply_button.setAccessibleName(tr("Altyazıyı indir ve uygula"))
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.setToolTip(tooltip)
        row.addWidget(self.apply_button)

        self.close_button = QPushButton(tr("Kapat"), self)
        self.close_button.setAccessibleName(tr("Altyazı Merkezini kapat"))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.reject)
        row.addWidget(self.close_button)

        self._action_row = [self.apply_button, self.close_button]
        layout.addLayout(row)

    def action_row_buttons(self):
        return list(self._action_row)

    def status_text(self):
        return self.status_label.text()

    def set_operation_status(self, text):
        """Kısa işlem durumu (indiriliyor/indirildi/uygulandı/hata).

        TEK ÇEVİRİ SINIRI. Denetleyicilerin durum metinleri modül
        düzeyinde `tr_mark()` ile İŞARETLENİR; çeviri burada yapılır.
        Zaten çevrilmiş metin (ör. `safe_message()` çıktısı) katalogda
        yer almadığı için AYNEN geri döner.
        """
        self._operation_text = translate_marked(text) if text else ""
        self._refresh_status()

    def _refresh_status(self):
        if self._operation_text:
            self.status_label.setText(self._operation_text)
            self.empty_label.setText(
                self._state_text if not self._result_count else "")
            self.empty_label.setVisible(bool(self.empty_label.text()))
            return
        parts = []
        if self._state_text:
            parts.append(self._state_text)
        elif self._result_count:
            parts.append(f"{self._result_count} {tr('sonuç')}")
        if self._overwrite_warning:
            parts.append(tr("Mevcut dosyanın üzerine yazılacak"))
        text = "  •  ".join(parts)
        self.status_label.setText(text)
        # Liste boşken açıklama listenin ortasında da görünür.
        self.empty_label.setText(
            self._state_text if not self._result_count else "")
        self.empty_label.setVisible(bool(self.empty_label.text()))

    def set_overwrite_warning(self, warning):
        self._overwrite_warning = bool(warning)
        self._refresh_status()

    def _sync_action_state(self):
        enabled = self._selected_card is not None
        self.apply_button.setEnabled(enabled)
