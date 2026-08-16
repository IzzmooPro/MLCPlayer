"""Program dili: Windows'tan algılanır, kullanıcı ayarlardan değiştirir.

TASARIM KARARI — KAYNAK DİL TÜRKÇE KALIR. Ürün metinleri Türkçe yazılmıştır
ve 105 test dosyasındaki 453 assert doğrudan bu metinlere bakar. Qt'nin
`tr()` çağrısı, yüklü çeviri yokken kaynak metni döndürür; bu yüzden
metinleri `tr()` ile sarmalamak mevcut davranışı DEĞİŞTİRMEZ ve testleri
kırmaz. Diğer diller üstüne eklenir.

YEDEK DİL İNGİLİZCEDİR, Türkçe değil: dili desteklenmeyen bir kullanıcıya
Türkçe arayüz vermek çıkmaz sokaktır.

DİL DEĞİŞİMİ YENİDEN BAŞLATMADA GEÇERLİ OLUR. Qt widget arayüzünde canlı
dil değişimi her pencerenin yeniden kurulmasını gerektirir; sinematik
arayüzün overlay/timeline durumları buna hazır değildir ve bu risk bilerek
alınmaz. Kullanıcıya açıkça söylenir.

Bu modül saftır: pencere oluşturmaz, ağa çıkmaz. Yalnız dil kararı,
kalıcılık ve çevirmen kurulumu yapar.
"""

import os
import sys

from PyQt6.QtCore import QCoreApplication, QLocale, QTranslator

from app.settings_store import user_settings

#: Ürün metinlerinin YAZILDIĞI dil. Değişirse bütün kaynak metinler ve
#: onlara bakan testler değişmek zorunda kalır.
SOURCE_LANGUAGE = "tr"

#: Dili desteklenmeyen kullanıcının göreceği dil.
FALLBACK_LANGUAGE = "en"

#: Kurulum betikleriyle AYNI küme (packaging/MLCPlayer.iss).
#: `tests/test_installer_language_regressions.py` ve
#: `tests/test_language_settings_regressions.py` ikisini birbirine bağlar.
SUPPORTED_LANGUAGES = ("en", "tr", "de", "es", "fr", "it", "ru", "pt_BR")

#: Ayar menüsünde her dil KENDİ dilinde yazılır; kullanıcı kendi dilini
#: tanıyamazsa listeden seçemez.
LANGUAGE_NAMES = {
    "en": "English",
    "tr": "Türkçe",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "ru": "Русский",
    "pt_BR": "Português (Brasil)",
}

#: Boş değer "Windows'un dilini izle" demektir.
SETTINGS_KEY = "language"

#: Çeviri dosyası adı: `mlcplayer_<kod>.qm`
TRANSLATION_PREFIX = "mlcplayer_"
TRANSLATIONS_DIR_NAME = "translations"

RESTART_REQUIRED_MESSAGE = (
    "Dil değişikliği MLC Player yeniden başlatıldığında geçerli olur.")


#: Bütün ürün metinlerinin ortak çeviri bağlamı. Tek bağlam, çevirmenin
#: aynı metni iki kez çevirmesini önler.
TRANSLATION_CONTEXT = "MLCPlayer"


def tr(text):
    """Kullanıcıya görünen metin. Çeviri yoksa KAYNAK metni döndürür.

    Çalışma zamanı standart Qt'dir (`QTranslator` + `QCoreApplication`).
    Metin çıkarma ise `packaging/extract_translations.py` ile yapılır:
    `pylupdate6` yalnız `QCoreApplication.translate(...)` biçimini tanıyor,
    bu sarmalayıcıyı GÖREMİYOR (ölçüldü). Çağrı yerlerine o uzun ifadeyi
    yazmak menü kodunu okunmaz hâle getirirdi.
    """
    return QCoreApplication.translate(TRANSLATION_CONTEXT, text)


def _settings():
    """Testlerin değiştirebilmesi için ayrı; gerçek depo tek kaynaktan gelir."""
    return user_settings()


def language_name(code):
    return LANGUAGE_NAMES.get(code, code)


def detect_language(locale=None):
    """Windows'un dilinden desteklenen bir dil seçer.

    Önce tam eşleşme (`pt_BR`), sonra yalnız dil kodu (`de_AT` → `de`).
    Hiçbiri tutmazsa yedek dile düşer — Portekiz Portekizcesi gibi yakın ama
    DESTEKLENMEYEN diller de buraya düşer; yanlış lehçe göstermektense
    İngilizce göstermek dürüsttür.
    """
    locale = locale if locale is not None else QLocale.system()
    name = locale.name()                      # örn. "de_DE"
    if name in SUPPORTED_LANGUAGES:
        return name
    base = name.split("_", 1)[0]
    if base in SUPPORTED_LANGUAGES:
        return base
    return FALLBACK_LANGUAGE


def stored_language():
    """Kullanıcının açık tercihi; yoksa boş (Windows'u izle)."""
    try:
        value = _settings().value(SETTINGS_KEY, "")
    except Exception:
        return ""
    value = str(value or "").strip()
    return value if value in SUPPORTED_LANGUAGES else ""


def store_language(code):
    """Tercihi kaydeder. Boş değer "sistem dilini izle" demektir."""
    value = code if code in SUPPORTED_LANGUAGES else ""
    _settings().setValue(SETTINGS_KEY, value)


def effective_language(locale=None):
    """Yürürlükteki dil: kullanıcı tercihi varsa o, yoksa Windows'unki."""
    return stored_language() or detect_language(locale)


def translations_directory():
    """`.qm` dosyalarının bulunduğu dizin (paketli ve geliştirme)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.join(meipass, TRANSLATIONS_DIR_NAME)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))), TRANSLATIONS_DIR_NAME)


def translation_file(code):
    """Dilin çeviri dosyası; kaynak dil için BOŞ (çeviri gerekmez)."""
    if code == SOURCE_LANGUAGE:
        return ""
    return os.path.join(translations_directory(),
                        f"{TRANSLATION_PREFIX}{code}.qm")


def install_translator(application, code):
    """Çeviriyi yükler. Dosya yoksa program Türkçe devam eder, ÇÖKMEZ.

    Dönüş: çeviri gerçekten yüklendiyse `True`.
    """
    path = translation_file(code)
    if not path or not os.path.isfile(path):
        return False
    translator = QTranslator(application)
    if not translator.load(path):
        return False
    if application is None:
        return False
    installed = application.installTranslator(translator)
    if installed:
        # Referans tutulmazsa çevirmen çöp toplanır ve çeviri sessizce kaybolur.
        application._mlc_translator = translator
    return bool(installed)


def apply_language(application, locale=None):
    """Açılışta çağrılır: dili belirler ve varsa çeviriyi yükler.

    Dönüş: `(dil_kodu, çeviri_yüklendi_mi)`
    """
    code = effective_language(locale)
    return code, install_translator(application, code)
