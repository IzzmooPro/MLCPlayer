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
from app.translate import (TRANSLATION_CONTEXT, tr, tr_mark,  # noqa: F401
                           translate_marked)

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

# Çeviri çekirdeği SAF katmandan da kullanılabilsin diye `app/translate.py`
# içindedir (Qt'yi import anında yüklemez). Burada yeniden dışa verilir;
# ürün kodu alışkanlıkla `from app.i18n import tr` yazmaya devam eder.


#: Modül düzeyi sabittir: import anında çevirmen henüz yoktur, bu yüzden
#: yalnız İŞARETLENİR; çeviri kullanım yerinde `translate_marked()` ile
#: yapılır (bkz. `menu_actions._change_language`).
RESTART_REQUIRED_MESSAGE = tr_mark(
    "Dil değişikliği MLC Player yeniden başlatıldığında geçerli olur.")


def _settings():
    """Testlerin değiştirebilmesi için ayrı; gerçek depo tek kaynaktan gelir."""
    return user_settings()


def language_name(code):
    return LANGUAGE_NAMES.get(code, code)


#: `available_languages()` sonucu; her menü açılışında disk taranmaz.
_AVAILABLE_CACHE = None


def forget_available_languages():
    """Önbelleği düşürür. Yalnız testler ve `.qm` yeniden üretimi için."""
    global _AVAILABLE_CACHE
    _AVAILABLE_CACHE = None


def _translation_has_content(code):
    """`.qm` dosyası VAR MI ve GERÇEKTEN çeviri taşıyor mu?

    Dosyanın varlığı YETMEZ: tamamı `unfinished` olan bir `.ts` derlendiğinde
    geçerli ama BOŞ bir `.qm` çıkar. Öyle bir dili menüde sunmak, kullanıcıyı
    uyarısızca İngilizceye düşürmek demektir.
    """
    path = translation_file(code)
    if not path or not os.path.isfile(path):
        return False
    translator = QTranslator()
    if not translator.load(path):
        return False
    return not translator.isEmpty()


def available_languages():
    """Arayüzün GERÇEKTEN sunabildiği diller, sabit listeden değil diskten.

    KULLANICI KARARI (17 Ağustos 2026): şimdilik Türkçe + İngilizce.
    Menü sabit `SUPPORTED_LANGUAGES` listesini gösterirken kullanıcı
    `Deutsch` seçip uyarısız İngilizce görüyordu; altı dilin `.ts` dosyası
    0/401 çeviri taşıyor (ölçüldü).

    `SUPPORTED_LANGUAGES` KÜÇÜLTÜLMEZ: kurulum sihirbazı sekiz dildedir ve
    `.ts` dosyaları o küme için üretilir. Bir dil tamamlandığında burası
    KENDİLİĞİNDEN büyür; kod değişmez.
    """
    global _AVAILABLE_CACHE
    if _AVAILABLE_CACHE is None:
        codes = [SOURCE_LANGUAGE]
        codes.extend(code for code in SUPPORTED_LANGUAGES
                     if code != SOURCE_LANGUAGE
                     and _translation_has_content(code))
        _AVAILABLE_CACHE = tuple(codes)
    return _AVAILABLE_CACHE


def detect_language(locale=None):
    """Windows'un dilinden SUNULABİLEN bir dil seçer.

    Önce tam eşleşme (`pt_BR`), sonra yalnız dil kodu (`de_AT` → `de`).
    Hiçbiri tutmazsa yedek dile düşer — Portekiz Portekizcesi gibi yakın ama
    DESTEKLENMEYEN diller de buraya düşer; yanlış lehçe göstermektense
    İngilizce göstermek dürüsttür.

    Ölçüt `SUPPORTED_LANGUAGES` DEĞİL `available_languages()`tir: çevirisi
    olmayan bir dili "seçildi" diye raporlamak, kullanıcı İngilizce görürken
    menünün Almanca'yı işaretli göstermesi demekti.
    """
    locale = locale if locale is not None else QLocale.system()
    available = available_languages()
    name = locale.name()                      # örn. "de_DE"
    if name in available:
        return name
    base = name.split("_", 1)[0]
    if base in available:
        return base
    return FALLBACK_LANGUAGE


def stored_language():
    """Kullanıcının açık tercihi; yoksa boş (Windows'u izle)."""
    try:
        value = _settings().value(SETTINGS_KEY, "")
    except Exception:
        return ""
    value = str(value or "").strip()
    # Karşılanamayan tercih (çevirisi henüz yok) "sistem dilini izle" gibi
    # davranır. KAYIT SİLİNMEZ: o dil tamamlandığında tercih kendiliğinden
    # geri gelir.
    return value if value in available_languages() else ""


def store_language(code):
    """Tercihi kaydeder. Boş değer "sistem dilini izle" demektir."""
    value = code if code in available_languages() else ""
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


def _load_translator(application, code):
    """Tek dilin çevirmenini kurar. Dosya yoksa sessizce `None` döner."""
    path = translation_file(code)
    if not path or not os.path.isfile(path):
        return None
    translator = QTranslator(application)
    if not translator.load(path):
        return None
    if not application.installTranslator(translator):
        return None
    return translator


def remove_translators(application):
    """Kurulan zinciri kaldırır. Testler dışında kullanılmaz."""
    if application is None:
        return
    for translator in getattr(application, "_mlc_translators", []):
        application.removeTranslator(translator)
    application._mlc_translators = []


def install_translator(application, code):
    """Çeviri ZİNCİRİNİ yükler. Dosya yoksa program çökmez, kaynağa düşer.

    YEDEK DİL DİZGE DÜZEYİNDE UYGULANIR (VLC incelemesinden, 17 Ağustos
    2026). Önce İngilizce, SONRA hedef dil kurulur; `QCoreApplication`
    çevirmenleri son kurulandan geriye tarar, bu yüzden hedef dil kazanır
    ve o dilde EKSİK olan dizge Türkçeye değil İngilizceye düşer. Yarım
    çevrilmiş bir dil Alman kullanıcıya Almanca + Türkçe karışımı değil,
    Almanca + İngilizce karışımı gösterir.

    Dönüş: zincirden en az bir çeviri yüklendiyse `True`.
    """
    if application is None:
        return False
    # İkinci çağrı eski zinciri BIRAKMAZ; yoksa önceki dil altta kalır ve
    # hangi dilin kazandığı kurulum sırasına bağlı hâle gelir.
    remove_translators(application)
    if code == SOURCE_LANGUAGE:
        return False
    chain = [] if code == FALLBACK_LANGUAGE else [FALLBACK_LANGUAGE]
    chain.append(code)

    # Referans tutulmazsa çevirmen çöp toplanır ve çeviri sessizce kaybolur.
    installed = []
    for language in chain:
        translator = _load_translator(application, language)
        if translator is not None:
            installed.append(translator)
    application._mlc_translators = installed
    return bool(installed)


def apply_language(application, locale=None):
    """Açılışta çağrılır: dili belirler ve varsa çeviriyi yükler.

    Dönüş: `(dil_kodu, çeviri_yüklendi_mi)`
    """
    code = effective_language(locale)
    return code, install_translator(application, code)
