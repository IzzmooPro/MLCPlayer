# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Ayarları — dikey, kompakt ayarlar + altta canlı önizleme.

Tasarım:

    ┌─────────────────────────────────────────────────────────────┐
    │ Senkron ▾      Yazı boyutu ▾      Kenarlık kalınlığı ▾      │
    │ Dikey konum  [————○————] %100                               │
    │ Yazı [■]  Arka plan [▨]  Kenarlık [■]                       │
    ├─────────────────────────────────────────────────────────────┤
    │            koyu 16:9 temsili sahne önizlemesi               │
    │            iki satırlık örnek altyazı                       │
    │ (bitmap bilgisi)        Temsili video önizlemesi —…         │
    ├─────────────────────────────────────────────────────────────┤
    │ Varsayılana Dön                       İptal        Uygula   │
    └─────────────────────────────────────────────────────────────┘

Şeffaflık ARKA PLAN PALETİNİN İÇİNDEDİR ("Renk yok (Şeffaf)"); ana
pencerede ayrı bir düğme YOKTUR ve üç renk kutusu eşit genişlikte yan
yana durur.

Neden hazır listeler: eski tasarımda üç `QDoubleSpinBox` yan yanaydı;
gerçek Windows ölçümünde yazı alanı ile ok alanı kesişiyordu ve küçük
yukarı/aşağı okları anlaşılmıyordu. Aralıklar da ürün için anlamsız
genişlikteydi (±120 sn, 3× yazı, 10 px kenarlık). Artık yalnız hazır
değerler seçilebilir; gerçek sayı `currentData()` içinde float olarak
tutulur ve ETİKET METNİ HİÇ PARSE EDİLMEZ.

Katman kuralı: bu modül YALNIZCA arayüzdür. Renk biçimi, sayısal
doğrulama, migrasyon ve kalıcılık `app/subtitle_style.py` içindedir;
buradan MPV'ye veya ayarlara doğrudan yazma YAPILMAZ. Uygulama,
dışarıdan enjekte edilen `apply_callback(values) -> (ok, error)`
üzerinden gider.
"""
from PyQt6.QtCore import (QLibraryInfo, QPoint, QPointF, QRect, QRectF,
                          QSize, Qt, QTranslator)
from PyQt6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPalette, QPen, QPixmap,
                         QRadialGradient)
from PyQt6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QStyle,
    QStyleOptionComboBox, QStylePainter, QVBoxLayout, QWidget)

from app.config import SUBTITLE_DEFAULTS, UI_ACCENT
from app.i18n import tr, tr_mark, translate_marked
from app.subtitle_style import (BORDER_PRESETS, COLOR_KEYS, DELAY_PRESETS,
                                SCALE_PRESETS, mpv_argb_to_qcolor,
                                normalise_subtitle_numeric,
                                qcolor_to_mpv_argb, style_notice)

ACCENT = UI_ACCENT
SURFACE = "rgba(19, 20, 22, 255)"
TEXT = "#E9EDF1"
MUTED = "#8E969F"

# DİKEY yerleşimin ölçüleri: ayarlar üstte tek blok, önizleme altta tam
# genişlikte. Eski yan yana tasarım 852×476 istiyordu ve kullanıcı için
# gereksiz büyüktü.
#
# Önizlemeye SABİT genişlik verilmez; kalan alanı kullanır. Sabit minimum
# genişlik, pencerenin gerçekten küçülmesini engelliyordu.
DEFAULT_SIZE = (600, 480)
MINIMUM_SIZE = (540, 430)
# Üç renk kutusu arasındaki görsel boşluk (8-12 px hedefi).
COLOR_GAP = 10
PREVIEW_MIN_HEIGHT = 190
PANEL_MARGIN = 16
# Dikey bütçe ÖLÇÜLDÜ: gerçek Windows platformunda 12 px aralık ve
# 14/12 px üst/alt marj ile pencere 444 px'in altına inemiyordu; ilan
# edilen minimum 430'dur. Değerler bu bütçeye göre kısıldı.
PANEL_SPACING = 10
SWATCH_SIZE = (86, 30)

# Modül düzeyi metinler: import anında çevirmen yoktur; `tr_mark()` yalnız
# işaretler, çeviri kullanım anında `translate_marked()` ile yapılır.
PREVIEW_LINES = (tr_mark("Bu bir altyazı önizlemesidir."),
                 tr_mark("Renk, arka plan ve kenarlık burada görünür."))

COLOR_LABELS = {"sub_color": tr_mark("Yazı"),
                "sub_back_color": tr_mark("Arka plan"),
                "sub_border_color": tr_mark("Kenarlık")}

# --- Hazır değer etiketleri ---------------------------------------------
#
# Etiketler YALNIZCA gösterim içindir. Gerçek sayı her zaman
# `Qt.ItemDataRole.UserRole` altındadır; hiçbir yerde metin parse edilmez.
# Türkçe ondalık ayracı virgüldür ve negatif işaret olarak tipografik
# eksi (U+2212) kullanılır.
MINUS_SIGN = "−"
SCALE_LABELS = {0.75: tr_mark("Çok küçük"), 0.85: tr_mark("Küçük"),
                1.0: tr_mark("Normal"), 1.15: tr_mark("Biraz büyük"),
                1.25: tr_mark("Büyük"), 1.5: tr_mark("Çok büyük"),
                2.0: tr_mark("En büyük")}
BORDER_LABELS = {0.0: tr_mark("Yok"), 3.0: tr_mark("Varsayılan"),
                 5.0: tr_mark("En kalın")}


def _turkish_number(value, decimals):
    return f"{value:.{decimals}f}".replace(".", ",")


def delay_label(value):
    """`0 sn — Senkron`, `+0,25 sn`, `−1,25 sn`."""
    if abs(value) < 1e-9:
        return f"0 {tr('sn')} — {tr('Senkron')}"
    sign = "+" if value > 0 else MINUS_SIGN
    return f"{sign}{_turkish_number(abs(value), 2)} {tr('sn')}"


def scale_label(value):
    return (f"{_turkish_number(value, 2)}× — "
            f"{translate_marked(SCALE_LABELS[value])}")


def border_label(value):
    if abs(value) < 1e-9:
        return f"0 px — {translate_marked(BORDER_LABELS[0.0])}"
    text = f"{_turkish_number(value, 1)} px"
    note = BORDER_LABELS.get(value)
    return f"{text} — {translate_marked(note)}" if note else text


# KAPALI kutuda gösterilen kısa biçim. Açılır listede TAM açıklamalı
# etiket görünür; kapalı kutuda ise yalnız değer durur. Ölçüldü: tam
# etiket "0 sn — Senkron" 168 px, üç listenin yan yana durduğu satırda
# 560 px'lik minimum pencerede kutu başına ~144 px düşüyor ve metin
# kırpılıyordu. Kısa biçim hem sığar hem de kullanıcıya seçili DEĞERİ
# net gösterir.
def delay_short(value):
    if abs(value) < 1e-9:
        return f"0 {tr('sn')}"
    sign = "+" if value > 0 else MINUS_SIGN
    return f"{sign}{_turkish_number(abs(value), 2)} {tr('sn')}"


def scale_short(value):
    return f"{_turkish_number(value, 2)}×"


def border_short(value):
    return f"{_turkish_number(value, 1)} px"

STYLE = f"""
QDialog#subtitleAppearance {{ background: {SURFACE}; }}
QLabel {{ color: {TEXT}; background: transparent; font-size: 13px; }}
QLabel#subtitleFieldLabel {{ color: {MUTED}; font-size: 12px; }}
QLabel#subtitlePreviewCaption {{ color: {MUTED}; font-size: 11px; }}
QLabel#subtitleBitmapNotice {{ color: {ACCENT}; font-size: 11px; }}
QLabel#subtitlePositionValue {{ color: {TEXT}; font-size: 12px; }}

/* Uc hazir deger listesi tek satirda yan yana durur. Spinbox ok
   dugmeleri KALDIRILDI: gercek Windows olcumunde yazi alani ile ok alani
   kesisiyordu ve kullanicilar oklari anlamiyordu. */
QComboBox {{
    color: {TEXT}; background: rgba(255,255,255,12);
    border: 1px solid rgba(255,255,255,22); border-radius: 5px;
    padding: 5px 8px; font-size: 12px;
    /* ZORUNLU: stylesheet uygulanan bir QComboBox'ta Qt native olmayan
       acilir listeye gecer ve `setMaxVisibleItems()` YOK SAYILIR. 41
       ogeli senkron listesi bu yuzden 800 px yuksekliginde aciliyordu
       (olculdu). `combobox-popup: 0` maxVisibleItems'i tekrar gecerli
       kilar ve liste kaydirilabilir kalir. */
    combobox-popup: 0;
}}
QComboBox:focus {{ border-color: rgba(242,106,61,150); }}
QComboBox::drop-down {{ border: none; width: 18px; }}
/* NOT: `::down-arrow` OZELLESTIRILMEZ; QSS ile cizilen ok dolu beyaz
   kare olarak ciziliyordu. Stil verilmedeginde Qt kendi gorselini cizer. */
QComboBox QAbstractItemView {{
    color: {TEXT}; background: #1B1D20; outline: none;
    border: 1px solid rgba(255,255,255,26);
    selection-background-color: {ACCENT}; selection-color: #FFFFFF;
}}

QSlider::groove:horizontal {{
    height: 3px; background: rgba(255,255,255,30); border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 12px; height: 12px; margin: -5px 0; border-radius: 6px;
    background: {ACCENT};
}}

QPushButton {{
    color: {TEXT}; background: rgba(255,255,255,14); border: none;
    border-radius: 5px; padding: 7px 13px; font-size: 12px;
}}
QPushButton:hover {{ background: rgba(255,255,255,26); }}
QPushButton#subtitleApplyButton {{
    color: #FFFFFF; background: {ACCENT}; font-weight: 600;
}}
QPushButton#subtitleApplyButton:hover {{ background: #FF7A48; }}

QWidget#subtitleAppearanceSettings {{ background: transparent; }}
QWidget#subtitleAppearancePreview {{ background: transparent; }}
"""


def default_values():
    """Ürün varsayılanları; QColor'a çevrilmiş hâlde."""
    values = {name: float(SUBTITLE_DEFAULTS[name])
              for name in ("sub_delay", "sub_scale", "sub_pos",
                           "sub_border_size")}
    for key in COLOR_KEYS:
        values[key] = mpv_argb_to_qcolor(SUBTITLE_DEFAULTS[key])
    return values


# Renk penceresindeki AÇIK şeffaflık eylemi. Eskiden ana pencerede ayrı
# bir "Şeffaf" düğmesi vardı; kullanıcının aradığı yer renk penceresidir
# ve ayrı düğme renk satırının hizasını da bozuyordu. Alfa sürgüsüne
# güvenen gizli yöntem KABUL EDİLMEZ: seçenek metniyle görünür olmalıdır.
NO_COLOUR_TEXT = tr_mark("Renk yok (Şeffaf)")
NO_COLOUR_ACCESSIBLE = tr_mark("Arka planı şeffaf yap (renk yok)")


class SubtitleColourDialog(QColorDialog):
    """Renk penceresi + isteğe bağlı "Renk yok (Şeffaf)" eylemi.

    Sistem (native) renk penceresi kendi düğme kutusunu gizlediği için
    seçenek oraya EKLENEMEZ; bu yüzden pencere bilinçli olarak
    `DontUseNativeDialog` ile açılır. Alfa sürgüsü yine görünür kalır
    (`ShowAlphaChannel`), fakat şeffaflık artık sürgüyü keşfetmeyi
    gerektirmez.
    """

    def __init__(self, initial, parent=None, title="",
                 allow_transparent=False):
        super().__init__(QColor(initial), parent)
        if title:
            self.setWindowTitle(title)
        self.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        self.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog,
                       True)
        self._transparent_chosen = False
        self.no_colour_button = None
        if allow_transparent:
            button = QPushButton(translate_marked(NO_COLOUR_TEXT), self)
            button.setObjectName("subtitleNoColourButton")
            button.setAccessibleName(translate_marked(NO_COLOUR_ACCESSIBLE))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            # Enter'ın yanlışlıkla şeffaflık uygulamasını engeller.
            button.setAutoDefault(False)
            button.setDefault(False)
            button.clicked.connect(self._choose_transparent)
            box = self.findChild(QDialogButtonBox)
            if box is not None:
                box.addButton(button, QDialogButtonBox.ButtonRole.ResetRole)
            else:                       # savunma: düğme kutusu bulunamazsa
                layout = self.layout()
                if layout is not None:
                    layout.addWidget(button)
            self.no_colour_button = button

    def _choose_transparent(self):
        self._transparent_chosen = True
        self.accept()

    def selected_colour(self):
        """Kullanıcının seçtiği renk; "renk yok" ise tam saydam."""
        if self._transparent_chosen:
            return QColor(0, 0, 0, 0)
        return QColor(self.selectedColor())


def _turkish_translator():
    """Qt'nin KENDİ dizelerinin Türkçe çevirisi (varsa) — YENİ nesne.

    Sistem renk penceresini Windows yerelleştiriyordu; non-native
    pencerede Qt'nin gömülü İngilizce metinleri ("Basic colors", "OK",
    "Cancel") çıkıyor ve ürünün tamamen Türkçe arayüzünde karma dil
    oluşuyordu. Çeviri dosyası bulunamazsa sessizce vazgeçilir.

    Nesne ÖNBELLEĞE ALINMAZ: modül düzeyinde tutulan bir `QTranslator`'ın
    C++ tarafı Qt tarafından yok edilebiliyor ve sonraki çağrı
    `RuntimeError` veriyordu (ölçüldü). `.qm` yüklemesi ucuzdur.
    """
    try:
        translator = QTranslator()
        path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        return translator if translator.load("qtbase_tr", path) else None
    except Exception:
        return None


def pick_colour(parent, initial, title="", allow_transparent=False):
    """Renk penceresini açar. İptalde GEÇERSİZ `QColor` döner.

    Tek sızdırma noktasıdır: testler ve kabul harness'i bu fonksiyonu
    değiştirir, `QColorDialog`'un kendisini değil.
    """
    application = QApplication.instance()
    translator = _turkish_translator()
    # Çeviri YALNIZ bu pencere yaşarken kuruludur; uygulamanın geri
    # kalanının Qt dizeleri etkilenmez.
    installed = bool(translator is not None and application is not None
                     and application.installTranslator(translator))
    dialog = SubtitleColourDialog(initial, parent, title, allow_transparent)
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return QColor()             # iptal: önceki renk KORUNUR
        return dialog.selected_colour()
    finally:
        dialog.deleteLater()
        if installed:
            application.removeTranslator(translator)


class PresetCombo(QComboBox):
    """Hazır değer listesi. Gerçek sayı `currentData()` içindedir.

    `wheelEvent` bilinçli olarak ezilir: combo ODAKTA DEĞİLKEN fare
    tekerleği listeyi kaydırıp kullanıcının farkında olmadığı bir değer
    uygulanmasına yol açıyordu (pencere kaydırılırken kolayca oluşur).
    Odaktayken tekerlek normal çalışır.
    """

    def __init__(self, name, accessible, presets, labeller, short_labeller,
                 preset_key, parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        # Merkezî doğrulamanın hangi ayarı normalleştireceği.
        self._preset_key = preset_key
        self.setAccessibleName(accessible)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Uzun listede açılır kutu makul yükseklikte ve KAYDIRILABİLİR
        # kalır (senkron listesi 41 öğedir).
        self.setMaxVisibleItems(12)
        self._short = short_labeller
        for value in presets:
            self.addItem(labeller(value), float(value))
        metrics = self.fontMetrics()
        # Kapalı kutu: en uzun KISA biçim + açılır ok alanı.
        widest_short = max(metrics.horizontalAdvance(short_labeller(value))
                           for value in presets)
        self.setMinimumWidth(widest_short + 34)
        # Açılır liste: en uzun TAM etiket kırpılmadan görünür.
        widest_full = max(metrics.horizontalAdvance(labeller(value))
                          for value in presets)
        self.view().setMinimumWidth(widest_full + 24)

    def short_text(self):
        data = self.currentData(Qt.ItemDataRole.UserRole)
        return self._short(float(data)) if data is not None else ""

    def minimumSizeHint(self):
        """Qt varsayılanı EN UZUN ÖĞE metnine göre ölçer (206 px).

        Kapalı kutuda kısa biçim çizildiği için bu hint yanıltıcıydı ve
        560 px'lik pencerede "yatayda kırpıldı" ölçümü veriyordu. Gerçek
        ihtiyaç kısa biçimdir; açılır listenin genişliği ayrı ayarlanır.
        """
        hint = super().minimumSizeHint()
        return QSize(self.minimumWidth(), hint.height())

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(self.minimumWidth(), hint.height())

    def paintEvent(self, event):
        """Kapalı kutuda KISA biçim çizilir; liste öğeleri değişmez."""
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = self.short_text()
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)

    def select_value(self, value):
        """Verilen sayıya EN YAKIN hazır öğeyi seçer.

        ÖLÇÜLEN KUSUR: listede bulunmayan bir değer için `findData()`
        `-1` döndürüyor ve kod indeks 0'a düşüyordu; `select_value(1.8)`
        yazı boyutunu 0,75×'e (listenin EN KÜÇÜĞÜ) çekiyordu. Artık
        merkezî `normalise_subtitle_numeric()` ile en yakın hazır değere
        yuvarlanır — pencerenin açılışıyla aynı sözleşme.
        """
        index = self.findData(float(value), Qt.ItemDataRole.UserRole)
        if index < 0:
            index = self.findData(
                normalise_subtitle_numeric(self._preset_key, value),
                Qt.ItemDataRole.UserRole)
        if index < 0:
            index = 0
        self.setCurrentIndex(index)
        return index

    def value(self):
        data = self.currentData(Qt.ItemDataRole.UserRole)
        return float(data) if data is not None else 0.0

    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


# --- Temsili sahne -------------------------------------------------------
#
# Neden gerekli: düz siyah bir yüzeyde kullanıcı beyaz yazının aydınlık
# gökyüzünde, koyu yazının karanlık siluette nasıl görüneceğini göremiyor;
# yarı saydam arka planın ne işe yaradığı da anlaşılmıyordu.
#
# Sahne TAMAMEN yereldir: ağ, kullanıcı videosu, harici veya telifli asset
# KULLANILMAZ. Her şey `QPainter` ile ve rastgelelik olmadan çizilir; aynı
# boyut her zaman aynı görüntüyü verir.
SCENE_ASPECT = 16 / 9
SCENE_HORIZON = 0.72

# Gökyüzü: gece mavisinden ufuktaki sıcak turuncuya.
SCENE_SKY = ((0.00, (12, 16, 40)), (0.35, (34, 30, 68)),
             (0.58, (96, 58, 84)), (0.68, (198, 110, 74)),
             (SCENE_HORIZON, (250, 176, 104)))
# Bulutlar: (cx, cy, rx, ry, alfa, renk) — hepsi genişlik/yükseklik oranı.
SCENE_CLOUDS = (
    (0.22, 0.20, 0.20, 0.030, 120, (176, 168, 200)),
    (0.34, 0.235, 0.14, 0.022, 90, (200, 190, 214)),
    (0.72, 0.16, 0.17, 0.026, 100, (150, 146, 186)),
    (0.60, 0.30, 0.22, 0.028, 130, (226, 178, 168)),
    (0.86, 0.36, 0.15, 0.022, 150, (244, 196, 150)),
    (0.15, 0.42, 0.18, 0.024, 110, (214, 146, 132)),
    (0.44, 0.50, 0.26, 0.026, 120, (244, 182, 136)),
)
# Silüet binalar: (x, genişlik, üst kenar).
SCENE_BUILDINGS = (
    (0.02, 0.07, 0.52), (0.09, 0.05, 0.60), (0.15, 0.09, 0.44),
    (0.25, 0.06, 0.57), (0.31, 0.04, 0.63), (0.36, 0.08, 0.49),
    (0.45, 0.05, 0.58), (0.51, 0.07, 0.40), (0.59, 0.05, 0.55),
    (0.65, 0.09, 0.62), (0.75, 0.06, 0.47), (0.82, 0.05, 0.58),
    (0.88, 0.10, 0.53),
)
SCENE_BUILDING_COLOR = (9, 10, 16)
SCENE_WINDOW_COLOR = (255, 206, 138)
SCENE_SILHOUETTE_COLOR = (5, 6, 9)


def _scene_colour(rgb, alpha=255):
    return QColor(rgb[0], rgb[1], rgb[2], alpha)


def _paint_scene(painter, width, height):
    """16:9 taban yüzeye temsili alacakaranlık sahnesini çizer."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    horizon = SCENE_HORIZON * height

    sky = QLinearGradient(0.0, 0.0, 0.0, horizon)
    for stop, rgb in SCENE_SKY:
        sky.setColorAt(min(1.0, stop / SCENE_HORIZON), _scene_colour(rgb))
    painter.fillRect(QRectF(0, 0, width, horizon), QBrush(sky))

    # Ufuk ışığı: sahnenin EN PARLAK bölgesi.
    glow = QRadialGradient(QPointF(0.615 * width, 0.715 * height),
                           0.30 * width)
    glow.setColorAt(0.0, _scene_colour((255, 240, 206), 255))
    glow.setColorAt(0.35, _scene_colour((255, 196, 120), 170))
    glow.setColorAt(1.0, _scene_colour((255, 170, 90), 0))
    painter.fillRect(QRectF(0, 0, width, horizon), QBrush(glow))

    painter.setPen(Qt.PenStyle.NoPen)
    for cx, cy, rx, ry, alpha, rgb in SCENE_CLOUDS:
        painter.setBrush(QBrush(_scene_colour(rgb, alpha)))
        painter.drawEllipse(QPointF(cx * width, cy * height),
                            rx * width, ry * height)

    ground = QLinearGradient(0.0, horizon, 0.0, float(height))
    ground.setColorAt(0.0, _scene_colour((30, 26, 38)))
    ground.setColorAt(1.0, _scene_colour((9, 9, 14)))
    painter.fillRect(QRectF(0, horizon, width, height - horizon),
                     QBrush(ground))

    # Suda yansıma: ufuk ışığının altında birkaç ince şerit.
    for index, (offset, span, alpha) in enumerate(
            ((0.02, 0.26, 70), (0.05, 0.18, 55), (0.09, 0.30, 45),
             (0.14, 0.14, 38), (0.19, 0.22, 30))):
        top = horizon + offset * height
        painter.setBrush(QBrush(_scene_colour((255, 186, 116), alpha)))
        painter.drawRoundedRect(
            QRectF((0.615 - span / 2) * width, top, span * width,
                   0.012 * height), 3.0, 3.0)

    painter.setBrush(QBrush(_scene_colour(SCENE_BUILDING_COLOR)))
    for x, span, top in SCENE_BUILDINGS:
        painter.drawRect(QRectF(x * width, top * height, span * width,
                                (SCENE_HORIZON - top) * height + 1.0))

    # Pencere ışıkları: deterministik desen (rastgelelik yok).
    window_w, window_h = 0.006 * width, 0.016 * height
    for index, (x, span, top) in enumerate(SCENE_BUILDINGS):
        columns = max(1, int(span / 0.018))
        rows = max(1, int((SCENE_HORIZON - top) / 0.055))
        for column in range(columns):
            for row in range(rows):
                if (index * 7 + column * 3 + row * 5) % 4:
                    continue
                alpha = 210 if (index + column + row) % 3 else 140
                painter.setBrush(QBrush(
                    _scene_colour(SCENE_WINDOW_COLOR, alpha)))
                painter.drawRect(QRectF(
                    (x + 0.006 + column * 0.018) * width,
                    (top + 0.020 + row * 0.055) * height,
                    window_w, window_h))

    # Ön plan: insan silueti + sokak lambası (koyu referans alanlar).
    # Silüet AYDINLIK gökyüzüne karşı durur; koyu zeminde kaybolmasın
    # diye başı ufuk çizgisinin belirgin biçimde üstündedir.
    painter.setBrush(QBrush(_scene_colour(SCENE_SILHOUETTE_COLOR)))
    head = QPointF(0.300 * width, 0.585 * height)
    painter.drawEllipse(head, 0.023 * width, 0.042 * height)
    body = QPainterPath()
    body.moveTo(0.245 * width, height)
    body.lineTo(0.256 * width, 0.700 * height)
    body.quadTo(0.300 * width, 0.618 * height, 0.344 * width, 0.700 * height)
    body.lineTo(0.355 * width, height)
    body.closeSubpath()
    painter.drawPath(body)

    painter.drawRect(QRectF(0.658 * width, 0.470 * height, 0.005 * width,
                            0.530 * height))
    painter.setBrush(QBrush(_scene_colour((255, 226, 170), 235)))
    painter.drawEllipse(QPointF(0.6605 * width, 0.470 * height),
                        0.013 * width, 0.023 * height)

    # Köşe karartması: gerçek bir kare hissi verir, metni etkilemez.
    vignette = QRadialGradient(QPointF(width / 2.0, height / 2.0),
                               max(width, height) * 0.72)
    vignette.setColorAt(0.55, QColor(0, 0, 0, 0))
    vignette.setColorAt(1.0, QColor(0, 0, 0, 110))
    painter.fillRect(QRectF(0, 0, width, height), QBrush(vignette))


def build_preview_scene(width, height):
    """Verilen yüzeyi TAM kaplayan temsili sahne.

    Sahne her zaman 16:9 çizilir; hedef yüzeye `cover` mantığıyla
    ortadan KIRPILARAK yerleştirilir. Böylece en-boy oranı bozulmaz ve
    yüzeyde boşluk kalmaz.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    scale = max(width / 16.0, height / 9.0)
    base_width = max(width, int(round(16 * scale)))
    base_height = max(height, int(round(9 * scale)))

    scene = QPixmap(base_width, base_height)
    # `QPixmap` BAŞLATILMAMIŞ bellekle gelir. Gökyüzü ve zemin
    # dikdörtgenleri ondalık ufuk çizgisinde yarım piksellik bir dikiş
    # bırakabildiği için yüzey önce tamamen doldurulur; aksi halde aynı
    # boyutta iki çizim farklı çıkıyordu (determinizm testi kırmızıydı).
    scene.fill(_scene_colour((9, 9, 14)))
    painter = QPainter(scene)
    try:
        _paint_scene(painter, base_width, base_height)
    finally:
        painter.end()
    if (base_width, base_height) == (width, height):
        return scene
    return scene.copy((base_width - width) // 2, (base_height - height) // 2,
                      width, height)


class SubtitlePreview(QWidget):
    """Temsili sinematik sahne üzerinde canlı altyazı önizlemesi.

    Yerel çizim: harici görsel veya asset KULLANILMAZ. Bu yüzey gerçek
    MPV çıktısı değildir; yalnız seçimlerin yönünü gösterir. Sahne
    yalnız ARKA PLANDIR: kullanıcının `sub_back_color` seçimi yine
    yalnız metnin arkasındaki kutuyu boyar, sahnenin tamamına filtre
    uygulanmaz.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("subtitlePreviewSurface")
        # Dikey yerleşimde genişlik KALAN alandan gelir; yalnız okunabilir
        # bir yükseklik garanti edilir.
        self.setMinimumHeight(PREVIEW_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.style_values = default_values()
        self._lines = [translate_marked(line) for line in PREVIEW_LINES]
        self._text_rect = QRect()
        # Sahne YALNIZ boyut değiştiğinde üretilir; `paintEvent` her
        # karede pahalı çizim yapmaz.
        self._scene = None
        self._scene_key = None
        self._scene_builds = 0

    def scene_builds(self):
        """Sahnenin kaç kez ÜRETİLDİĞİ (cache ölçümü içindir)."""
        return self._scene_builds

    def _scene_pixmap(self):
        key = (max(1, self.width()), max(1, self.height()))
        if self._scene is None or self._scene_key != key:
            self._scene = build_preview_scene(*key)
            self._scene_key = key
            self._scene_builds += 1
        return self._scene

    def set_style(self, values):
        self.style_values = dict(values)
        self.update()

    def set_sample_text(self, text):
        self._lines = [line for line in str(text).splitlines() if line] or \
            [str(text)]
        self.update()

    def background_visible(self):
        """Arka plan kutusu gerçekten çiziliyor mu?"""
        color = self.style_values.get("sub_back_color")
        return isinstance(color, QColor) and color.alpha() > 0

    def text_rect(self):
        """En son çizilen metin bloğunun yüzey içindeki dikdörtgeni."""
        if self._text_rect.isNull():
            self._layout_text(self.rect())
        return QRect(self._text_rect)

    def _font(self):
        font = QFont(self.font())
        scale = float(self.style_values.get("sub_scale", 1.0) or 1.0)
        font.setPointSizeF(max(6.0, 13.0 * scale))
        return font

    def _layout_text(self, surface):
        """Metin bloğunu yüzeye SIĞACAK biçimde yerleştirir."""
        margin = 12
        available = max(40, surface.width() - 2 * margin)
        metrics = self.fontMetrics()
        font = self._font()
        from PyQt6.QtGui import QFontMetrics
        metrics = QFontMetrics(font)
        wrapped = []
        for line in self._lines:
            wrapped.extend(_wrap(line, metrics, available))
        height = metrics.height() * max(1, len(wrapped))
        width = min(available, max((metrics.horizontalAdvance(l)
                                    for l in wrapped), default=0))
        position = float(self.style_values.get("sub_pos", 100.0) or 0.0)
        # `sub_pos` 100 = en alt, 0 = en üst (MPV ile aynı yön).
        span = max(0, surface.height() - height - 2 * margin)
        top = surface.top() + margin + int(span * min(1.0, position / 100.0))
        left = surface.left() + (surface.width() - width) // 2
        rect = QRect(left, top, width, height)
        # Hiçbir koşulda yüzeyin dışına taşmaz.
        rect = rect.intersected(surface)
        self._text_rect = rect
        return wrapped, rect, metrics, font

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = self.rect()
        # Sahne yalnız arka plandır; altyazı katmanı üstüne çizilir.
        painter.drawPixmap(surface.topLeft(), self._scene_pixmap())
        wrapped, rect, metrics, font = self._layout_text(surface)
        painter.setFont(font)

        back = self.style_values.get("sub_back_color")
        if isinstance(back, QColor) and back.alpha() > 0:
            box = rect.adjusted(-8, -4, 8, 4).intersected(surface)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(back))
            painter.drawRect(box)

        text_color = self.style_values.get("sub_color") or QColor(255, 255,
                                                                  255)
        border_color = self.style_values.get("sub_border_color") or \
            QColor(0, 0, 0)
        border = float(self.style_values.get("sub_border_size", 0.0) or 0.0)
        line_height = metrics.height()
        for index, line in enumerate(wrapped):
            baseline = rect.top() + line_height * index + metrics.ascent()
            width = metrics.horizontalAdvance(line)
            x = rect.left() + (rect.width() - width) // 2
            if border > 0 and border_color.alpha() > 0:
                painter.setPen(QPen(border_color, max(1.0, border)))
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    painter.drawText(QPoint(int(x + dx), int(baseline + dy)),
                                     line)
            painter.setPen(QPen(text_color))
            painter.drawText(QPoint(int(x), int(baseline)), line)
        painter.end()


def _wrap(line, metrics, available):
    """Basit sözcük sarma: uzun metin yüzeyden taşmaz."""
    if metrics.horizontalAdvance(line) <= available:
        return [line]
    out, current = [], ""
    for word in str(line).split():
        candidate = f"{current} {word}".strip()
        if current and metrics.horizontalAdvance(candidate) > available:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    return out or [line]


class ColorSwatch(QPushButton):
    """Gerçek rengi ve saydamlığını gösteren kompakt renk düğmesi."""

    def __init__(self, key, color, parent=None):
        super().__init__(parent)
        self.setObjectName(f"subtitleColorSwatch_{key}")
        self.key = key
        self.color = QColor(color)
        self.setFixedSize(*SWATCH_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        # QDialog içindeki QPushButton'lar varsayılan olarak `autoDefault`
        # olur ve Enter tuşu ilk böyle düğmeye gider. Kapatılmazsa
        # kullanıcı boyut/senkron alanına değer yazıp Enter'a bastığında
        # renk seçici penceresi açılıyordu (gerçek MPV kabulünde ölçüldü).
        self.setAutoDefault(False)
        self.setDefault(False)
        self.set_color(color)

    def set_color(self, color):
        self.color = QColor(color)
        canonical = qcolor_to_mpv_argb(self.color)
        alpha = self.color.alpha()
        self.setProperty("hasAlpha", alpha < 255)
        if alpha == 0:
            state = tr("tamamen saydam")
        elif alpha < 255:
            state = (f"{tr('kısmen saydam')} "
                     f"(%{round(alpha / 255 * 100)} {tr('opak')})")
        else:
            state = tr("opak")
        marked = COLOR_LABELS.get(self.key, "")
        label = translate_marked(marked) if marked else ""
        self.setToolTip(f"{label} — {canonical} ({state})")
        self.setAccessibleName(f"{label or self.key} {tr('rengi')}")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        # Dama deseni: alfa durumu rengin ardından okunabilir olur.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(70, 72, 76)))
        painter.drawRoundedRect(rect, 5, 5)
        size = 6
        painter.save()
        painter.setClipRect(rect)
        for y in range(rect.top(), rect.bottom(), size):
            for x in range(rect.left(), rect.right(), size):
                if ((x - rect.left()) // size + (y - rect.top()) // size) % 2:
                    painter.fillRect(QRect(x, y, size, size),
                                     QColor(104, 106, 110))
        painter.restore()
        painter.setBrush(QBrush(self.color))
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawRoundedRect(rect, 5, 5)
        painter.end()


class SubtitleAppearanceDialog(QDialog):
    """Kompakt altyazı görünüm penceresi.

    `apply_callback(values) -> (ok, error)` DIŞARIDAN verilir; bu sınıf
    MPV veya QSettings referansı TUTMAZ.
    """

    def __init__(self, parent=None, values=None, track_list=None,
                 apply_callback=None, error_reporter=None):
        super().__init__(parent)
        self.setObjectName("subtitleAppearance")
        self.setWindowTitle(tr("Altyazı Ayarları"))
        self.setStyleSheet(STYLE)
        self._apply_callback = apply_callback
        self._error_reporter = error_reporter
        self._colors = default_values()
        self._colors.update({k: QColor(v) for k, v in (values or {}).items()
                             if k in COLOR_KEYS})
        self._swatches = {}
        self._tab_order = []

        root = QVBoxLayout(self)
        root.setContentsMargins(PANEL_MARGIN, 12, PANEL_MARGIN, 10)
        root.setSpacing(PANEL_SPACING)
        # DİKEY sıra: ayarlar → önizleme → eylemler.
        self.settings_panel = self._build_settings(values or {})
        root.addWidget(self.settings_panel, 0)
        root.addWidget(self._build_preview(track_list), 1)
        root.addLayout(self._build_actions())

        self.setMinimumSize(*MINIMUM_SIZE)
        self.resize(*DEFAULT_SIZE)
        self._apply_tab_order()
        self._refresh_preview()

    # --- kurulum ---

    def _label(self, text):
        label = QLabel(text)
        label.setObjectName("subtitleFieldLabel")
        return label

    def _build_settings(self, values):
        panel = QWidget()
        panel.setObjectName("subtitleAppearanceSettings")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Maximum)
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        defaults = default_values()

        def initial(name):
            """Eski/aşırı kayıt merkezi sınırdan geçirilir."""
            return normalise_subtitle_numeric(
                name, values.get(name, defaults[name]))

        quick = QWidget()
        quick.setObjectName("subtitleQuickRow")
        quick_row = QHBoxLayout(quick)
        quick_row.setContentsMargins(0, 0, 0, 0)
        quick_row.setSpacing(10)
        self.delay_combo = PresetCombo(
            "subtitleDelayCombo", tr("Altyazı senkronu"), DELAY_PRESETS,
            delay_label, delay_short, "sub_delay", panel)
        self.delay_combo.setToolTip(tr(
            "Altyazı senkronu. Pozitif değer altyazıyı geciktirir, "
            "negatif değer öne alır."))
        self.scale_combo = PresetCombo(
            "subtitleScaleCombo", tr("Yazı boyutu"), SCALE_PRESETS,
            scale_label,
            scale_short, "sub_scale", panel)
        self.border_combo = PresetCombo(
            "subtitleBorderCombo", tr("Kenarlık kalınlığı"), BORDER_PRESETS,
            border_label, border_short, "sub_border_size", panel)
        self.delay_combo.select_value(initial("sub_delay"))
        self.scale_combo.select_value(initial("sub_scale"))
        self.border_combo.select_value(initial("sub_border_size"))
        for combo in (self.delay_combo, self.scale_combo, self.border_combo):
            combo.currentIndexChanged.connect(self._refresh_preview)
        for label, widget in ((tr("Senkron"), self.delay_combo),
                              (tr("Yazı boyutu"), self.scale_combo),
                              (tr("Kenarlık kalınlığı"), self.border_combo)):
            cell = QVBoxLayout()
            cell.setSpacing(3)
            cell.addWidget(self._label(label))
            cell.addWidget(widget)
            quick_row.addLayout(cell, 1)
        column.addWidget(quick)

        position_block = QVBoxLayout()
        position_block.setSpacing(3)
        position_block.addWidget(self._label("Dikey konum"))
        position_row = QHBoxLayout()
        position_row.setSpacing(8)
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setObjectName("subtitlePositionSlider")
        self.position_slider.setAccessibleName(tr("Dikey konum"))
        self.position_slider.setRange(0, 100)
        # ÖLÇÜLEN ÇÖKME: `int(values.get("sub_pos", ...))` doğrudan
        # kullanılıyordu ve `None`, `"bozuk"`, `NaN`, `±inf` değerlerinde
        # pencere AÇILIRKEN düşüyordu (TypeError/ValueError/OverflowError).
        # `sub_pos` da diğer sayılar gibi merkezî sınırdan geçer.
        self.position_slider.setValue(int(round(initial("sub_pos"))))
        self.position_value = QLabel(f"%{self.position_slider.value()}")
        self.position_value.setObjectName("subtitlePositionValue")
        self.position_value.setMinimumWidth(40)
        self.position_slider.valueChanged.connect(
            lambda value: (self.position_value.setText(f"%{value}"),
                           self._refresh_preview()))
        position_row.addWidget(self.position_slider, 1)
        position_row.addWidget(self.position_value, 0)
        position_block.addLayout(position_row)
        column.addLayout(position_block)

        # ÜÇ RENK EŞİT ve YAN YANA. Eskiden arka plan hücresine çift
        # genişlik payı ve içine bir `addStretch(1)` verilmişti; bu,
        # "Kenarlık" kutusunu sağ kenara tek başına itiyordu. Şeffaflık
        # artık ayrı bir düğme değil, arka plan PALETİNİN İÇİNDE bir
        # seçenektir; hücrelerin eşit olmasını engelleyen sebep kalmadı.
        colors_row = QHBoxLayout()
        colors_row.setSpacing(COLOR_GAP)
        colour_labels = []
        for key in COLOR_KEYS:
            cell = QVBoxLayout()
            cell.setSpacing(3)
            label = self._label(translate_marked(COLOR_LABELS[key]))
            colour_labels.append(label)
            cell.addWidget(label)
            swatch = ColorSwatch(key, self._colors[key], panel)
            swatch.clicked.connect(lambda _=False, k=key: self._choose(k))
            self._swatches[key] = swatch
            if key == "sub_back_color":
                swatch.setToolTip(
                    swatch.toolTip()
                    + f"\nPalette: {translate_marked(NO_COLOUR_TEXT)}")
            cell.addWidget(swatch)
            colors_row.addLayout(cell, 0)
        # Hücre genişliği en geniş ÇOCUĞA göre belirlenir; "Arka plan"
        # etiketi (ölçüldü: 108 px) kutudan geniş olduğu için kutular
        # eşitsiz görünüyor ve aralarındaki boşluk 10/32 px'e çıkıyordu.
        # Üç kutuya ortak genişlik verilir; boşluk her yerde `COLOR_GAP`.
        cell_width = max([SWATCH_SIZE[0]]
                         + [label.sizeHint().width() for label in colour_labels])
        for swatch in self._swatches.values():
            swatch.setFixedWidth(cell_width)
        colors_row.addStretch(1)
        column.addLayout(colors_row)
        return panel

    def _build_preview(self, track_list):
        panel = QWidget()
        panel.setObjectName("subtitleAppearancePreview")
        # Önizleme KALAN alanı kullanır: sabit genişlik minimumu pencerenin
        # gerçekten küçülmesini engelliyordu. Dikey yerleşimde yalnız
        # OKUNABİLİR bir yükseklik garanti edilir.
        panel.setMinimumHeight(PREVIEW_MIN_HEIGHT)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.preview = SubtitlePreview(panel)
        layout.addWidget(self.preview, 1)

        # Bilgi satırı KENDİ satırında durur: aynı satırı paylaştığında
        # "Önizleme" etiketi dar pencerede kırpılıyordu.
        self.bitmap_notice = QLabel(style_notice(track_list))
        self.bitmap_notice.setObjectName("subtitleBitmapNotice")
        self.bitmap_notice.setWordWrap(True)
        self.bitmap_notice.setVisible(bool(self.bitmap_notice.text()))
        layout.addWidget(self.bitmap_notice, 0)
        # NOT: bilgi satırı GİZLİ iken de yer bütçesine girmesin diye
        # kendi aralığı küçük tutulur.

        caption = QLabel(tr("Temsili video önizlemesi — gerçek video "
                            "çıktısı değildir"))
        caption.setObjectName("subtitlePreviewCaption")
        # Dar pencerede tek satıra sığmayıp kırpılıyordu; sarılarak kalır.
        caption.setWordWrap(True)
        caption.setAlignment(Qt.AlignmentFlag.AlignRight
                             | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(caption, 0)
        return panel

    def _button(self, name, text, accessible):
        button = QPushButton(text)
        button.setObjectName(name)
        button.setAccessibleName(accessible)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoDefault(False)
        return button

    def _build_actions(self):
        row = QHBoxLayout()
        row.setSpacing(8)
        self.reset_button = self._button("subtitleResetButton",
                                         tr("Varsayılana Dön"),
                                         tr("Varsayılan ayarlara dön"))
        self.cancel_button = self._button("subtitleCancelButton",
                                          tr("İptal"),
                                          tr("Değişiklikleri iptal et"))
        self.apply_button = self._button("subtitleApplyButton",
                                         tr("Uygula"),
                                         tr("Ayarları uygula"))
        self.reset_button.clicked.connect(self.reset_to_defaults)
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self._apply)
        row.addWidget(self.reset_button, 0)
        row.addStretch(1)
        row.addWidget(self.cancel_button, 0)
        row.addWidget(self.apply_button, 0)
        return row

    def _apply_tab_order(self):
        chain = [self.delay_combo, self.scale_combo, self.border_combo,
                 self.position_slider]
        chain += [self._swatches[key] for key in COLOR_KEYS]
        chain += [self.reset_button, self.cancel_button, self.apply_button]
        for first, second in zip(chain, chain[1:]):
            QDialog.setTabOrder(first, second)
        self._tab_order = [widget.objectName() for widget in chain]

    # --- durum ---

    def tab_order_names(self):
        return list(self._tab_order)

    def current_values(self):
        """`atomic_apply()` için hazır sözlük; kalıcı yazma YAPILMAZ.

        Sayılar `currentData()` içindeki float'lardır; görünen etiket
        metni HİÇ parse edilmez.
        """
        return {
            "sub_delay": self.delay_combo.value(),
            "sub_scale": self.scale_combo.value(),
            "sub_pos": float(self.position_slider.value()),
            "sub_border_size": self.border_combo.value(),
            "sub_color": QColor(self._colors["sub_color"]),
            "sub_back_color": QColor(self._colors["sub_back_color"]),
            "sub_border_color": QColor(self._colors["sub_border_color"]),
        }

    def set_color(self, key, color):
        self._colors[key] = QColor(color)
        self._swatches[key].set_color(self._colors[key])
        self._refresh_preview()

    def _picker_seed(self, key):
        """Renk seçiciye verilecek GEÇİCİ başlangıç rengi.

        Arka plan tamamen saydamken seçici alfa 0 ile açılırsa, yalnız
        RGB değiştiren kullanıcı yine görünmez bir arka plan uygular
        (`#000020A0`) ve "arka plan uygulanmıyor" görür. Bu yüzden
        SADECE `sub_back_color` ve alfa == 0 iken tohum opaklaştırılır;
        RGB değerleri korunur.

        Bu geçici renk dialog durumuna ve ayarlara YAZILMAZ; alfası > 0
        olan arka plan ile Yazı/Kenarlık renkleri hiç dokunulmadan
        geçirilir. Kullanıcı seçicide bilerek alfa 0 seçerse bu seçim
        zorla değiştirilmez.
        """
        colour = QColor(self._colors[key])
        if key == "sub_back_color" and colour.alpha() == 0:
            colour.setAlpha(255)
        return colour

    def _choose(self, key):
        # "Renk yok (Şeffaf)" YALNIZ arka plan için anlamlıdır; yazı ve
        # kenarlık paletine gereksiz seçenek eklenmez.
        selected = pick_colour(
            self, self._picker_seed(key),
            translate_marked(COLOR_LABELS[key]) if key in COLOR_LABELS
            else tr("Renk"),
            allow_transparent=(key == "sub_back_color"))
        # İptal edilen seçicide önceki renk KORUNUR.
        if selected.isValid():
            self.set_color(key, selected)

    def _refresh_preview(self):
        self.preview.set_style(self.current_values())

    def reset_to_defaults(self):
        """YALNIZ dialog durumunu değiştirir; kalıcı yazma yapmaz."""
        defaults = default_values()
        self.delay_combo.select_value(defaults["sub_delay"])
        self.scale_combo.select_value(defaults["sub_scale"])
        self.border_combo.select_value(defaults["sub_border_size"])
        self.position_slider.setValue(int(defaults["sub_pos"]))
        for key in COLOR_KEYS:
            self.set_color(key, defaults[key])

    def _apply(self):
        if self._apply_callback is None:
            self.accept()
            return
        ok, error = self._apply_callback(self.current_values())
        if ok:
            self.accept()
            return
        # Başarısız uygulamada pencere AÇIK kalır; sahte başarı yok.
        if self._error_reporter is not None:
            from app.subtitle_style import APPLY_ERROR_MESSAGE
            self._error_reporter(tr("Altyazı Ayarları Uygulanamadı"),
                                 translate_marked(APPLY_ERROR_MESSAGE),
                                 exc=error)
