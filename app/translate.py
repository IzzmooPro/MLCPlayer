# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Çeviri çekirdeği — Qt'yi IMPORT ANINDA yüklemez.

NEDEN AYRI MODÜL. `app/media_info.py` ve `app/track_labels.py` bilinçli
olarak SAF katmandır: import zincirleri Qt'yi sürece SOKMAMALIDIR
(`tests/test_media_info_builder_regressions.py::
test_the_builder_never_pulls_qt_into_the_process` bunu ayrı bir süreçte
ölçer). Ama bu katmanın ürettiği metinlerin çoğu doğrudan kullanıcıya
gider — dil adları, bölüm başlıkları, satır etiketleri — ve çevrilmek
zorundadır: Alman kullanıcıya İngilizce ses parçası için `İngilizce`
yazmak kabul edilemez.

Çözüm: `QCoreApplication` modül düzeyinde DEĞİL, çağrı anında içe
aktarılır. Çeviri gerçekten gerektiğinde uygulama zaten ayaktadır ve Qt
yüklüdür; import zinciri ise temiz kalır.

`app/i18n.py` buradaki üç fonksiyonu yeniden dışa verir; ürün kodu
alışkanlıkla `from app.i18n import tr` yazmaya devam edebilir.
"""

#: Bütün ürün metinlerinin ortak çeviri bağlamı. Tek bağlam, çevirmenin
#: aynı metni iki kez çevirmesini önler.
TRANSLATION_CONTEXT = "MLCPlayer"


def _translate(text):
    from PyQt6.QtCore import QCoreApplication
    return QCoreApplication.translate(TRANSLATION_CONTEXT, text)


def tr(text):
    """Kullanıcıya görünen metin. Çeviri yoksa KAYNAK metni döndürür.

    Çalışma zamanı standart Qt'dir (`QTranslator` + `QCoreApplication`).
    Metin çıkarma ise `packaging/extract_translations.py` ile AST üzerinden
    yapılır: `pylupdate6` yalnız `QCoreApplication.translate(...)` biçimini
    tanıyor, bu sarmalayıcıyı GÖREMİYOR (ölçüldü).
    """
    return _translate(text)


def tr_mark(text):
    """Metni yalnız ÇIKARMA için işaretler; çeviri YAPMAZ.

    Modül düzeyi sabitler ve tablolar import anında hesaplanır; o an ne
    QApplication ne de çevirmen vardır. Sabiti `tr()` ile sarmalamak metni
    sonsuza dek kaynak dile dondururdu. İşaret burada konur, çeviri
    kullanım anında `translate_marked()` ile yapılır.

    Aynı ayrım VLC'de de vardır (17 Ağustos 2026, depoda görüldü):
    `N_()` işaretler, `vlc_gettext()` kullanım anında çevirir.
    """
    return text


def translate_marked(text):
    """`tr_mark()` ile işaretlenmiş bir sabiti KULLANIM anında çevirir.

    `tr()`den ayrı tutulur: `tr()` çağrıları sabit metin taşımak ZORUNDADIR
    (çıkarıcı bunu denetler), burada ise metin zaten başka bir yerde
    işaretlenmiştir ve değişken gelmesi normaldir.
    """
    return _translate(text)
