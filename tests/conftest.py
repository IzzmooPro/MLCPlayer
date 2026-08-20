# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
import atexit
import gc
import os
import shutil
import sys
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ["PATH"]

# Hosted CI deliberately has no large/native runtime binaries. Product tests
# patch MPV with their own doubles; this gate only lets those modules import.
from scripts.ci_mpv_stub import install_ci_mpv_stub  # noqa: E402

install_ci_mpv_stub()

# ── Kullanıcı alanı izolasyonu (import anında, HER ŞEYDEN ÖNCE) ──────────
#
# ÖLÇÜLEN KUSUR: paket, kullanıcının GERÇEK `%APPDATA%\MLCPlayer\logs\
# uygulama.log` dosyasına yazıyordu; kullanıcının günlüğünde test
# koşumundan gelen satırlar bulundu. Günlük yolu ve Qt'nin standart
# dizinleri ortam değişkenlerinden türer, bu yüzden yönlendirme burada —
# `app.errors` veya QApplication yüklenmeden ÖNCE — yapılır.
#
# Kayıt defteri tarafı `app/settings_store.user_settings()` ile çözüldü:
# varsayılan biçim Ini olduğunda ürün de izole dosyaya yazar (bkz.
# tests/test_settings_isolation_regressions.py).
_isolated_appdata = tempfile.mkdtemp(prefix="mlc_test_appdata_")
os.environ["MLC_REAL_APPDATA"] = os.environ.get("APPDATA", "")
os.environ["APPDATA"] = _isolated_appdata
os.environ["LOCALAPPDATA"] = _isolated_appdata

from PyQt6.QtCore import QSettings, QStandardPaths  # noqa: E402

QStandardPaths.setTestModeEnabled(True)
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                  _isolated_appdata)

# Geçici dizin koşum sonunda silinir: eski harness `%TEMP%` altında 439 boş
# klasör bırakmıştı.
atexit.register(shutil.rmtree, _isolated_appdata, True)


@pytest.fixture(autouse=True)
def qt_test_cleanup():
    """Her testten SONRA, QApplication hâlâ yaşarken Qt yaşam döngüsünü kapatır.

    Neden oturum-sonu temizlik yetmiyordu
    -------------------------------------
    `qt_session_shutdown` yalnızca bütün paket bittikten sonra çalışır. Oysa
    çökme paketin ORTASINDA, `test_split_handle_stays_visible_and_hit_testable_
    after_owner_restore` testi çalışırken oluyordu.

    Ölçülen kanıt (testten hemen önce, tam pakette):
      topLevelWidgets_total=93  (31 QMainWindow + 31 QWidget + 31 QLabel)
      running_animations=38     (hepsi <dangling>: C++ tarafı yok, sarmalayıcı canlı)
      visible_top_level=0

    Yani her VideoFrame'li test geride bir QMainWindow ile onun top-level
    `control_overlay` (QWidget) ve `osd_label` (QLabel) Tool yüzeylerini
    bırakıyordu. Söz konusu test `QApplication.widgetAt()` çağırıyor; bu çağrı
    top-level pencereleri native olarak dolaşır ve birikmiş/yarı yıkılmış
    yüzeyler üzerinde abort (0xC0000409) üretiyordu.

    Burada her testten sonra: aktif pencere temizlenir, canlı animasyonlar
    sahipleri yok edilmeden durdurulur, top-level widget'lar kapatılıp
    silinir ve ertelenmiş silmeler boşaltılır. QApplication KAPATILMAZ;
    sonraki testler aynı event dispatcher ile devam eder.

    Paketteki modül kapsamlı fixture'ların tamamı subprocess'ten JSON döndürür
    (bkz. test_default_cinematic_ui / test_overlay_shell / test_title_bar_shell);
    hiçbiri testler arasında Qt widget'ı yaşatmaz, bu yüzden bu temizlik
    kasıtlı kalıcı durumları bozmaz.
    """
    yield

    from PyQt6.QtCore import QAbstractAnimation, QEvent
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return

    QApplication.setActiveWindow(None)

    top_level = []
    for widget in list(app.topLevelWidgets()):
        try:
            widget.objectName()
        except RuntimeError:
            # C++ tarafı zaten yok; sarmalayıcıya dokunulmaz.
            continue
        top_level.append(widget)

    # Animasyonlar sahipleri yok edilmeden durdurulur.
    for widget in top_level:
        try:
            animations = widget.findChildren(QAbstractAnimation)
        except RuntimeError:
            continue
        for animation in animations:
            try:
                if animation.state() != QAbstractAnimation.State.Stopped:
                    animation.stop()
            except RuntimeError:
                pass

    for widget in top_level:
        try:
            widget.close()
            widget.deleteLater()
        except RuntimeError:
            pass

    app.processEvents()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture(scope="session", autouse=True)
def qt_session_shutdown():
    """Oturum sonunda Qt'yi DETERMİNİSTİK biçimde kapatır.

    Testlerin tamamı geçtiği hâlde pytest süreci 0xC0000409 (abort) ile
    kapanıyordu. Sebep tek bir test değildi: oturum boyunca biriken top-level
    Qt widget'ları, yorumlayıcı kapanışında QApplication yok edildikten SONRA
    yıkılıyordu. Tek bir dosyayı çıkarmak toplamı eşiğin altına indirdiği için
    hata "rastgele" bir dosyaya bağlıymış gibi görünüyordu.

    Burada widget'lar QApplication hâlâ yaşarken kapatılır ve silinir; böylece
    yıkım sırası garanti altına alınır. Tek noktadan, davranış değiştirmeyen
    bir düzeltmedir.
    """
    yield

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in list(app.topLevelWidgets()):
        try:
            widget.close()
            widget.deleteLater()
        except RuntimeError:
            # C++ tarafında zaten yok edilmiş widget'lar sorun değildir.
            pass
    app.processEvents()
    app.quit()
    app.processEvents()
    gc.collect()


# --- Playlist penceresi icin GERCEKCI ekran ---------------------------
#
# OLCULDU (17 Agustos 2026): offscreen platformun sanal ekrani 800x800'dur,
# ama testlerin cogu 1280x720 pencere kurar -- yani PENCERE EKRANDAN
# GENIStir. Gercek bir kullanicida bu olmaz.
#
# Playlist penceresi artik ekran disina tasmamak icin yerlesimini ekrana
# gore secer (sag -> sol -> ekrana sikistir). O sanal ekranda panel hicbir
# yere sigmadigi icin zorunlu olarak videonun uzerine dusuyor ve "playlist
# videoyla kesismez" gibi GERCEK urun sozlesmeleri platform kisiti yuzunden
# kiriliyordu.
#
# Cozum TEK yerdedir: butun testlerde yerlesim hesabi gercekci bir ekrana
# baglanir. Dosya dosya yama YAPILMAZ. Ekranin KENDI kurali
# (sag -> sol -> sikistir) `tests/test_playlist_window_regressions.py`
# icinde saf `place_for()` ile ayrica ve dogrudan olculur; yani bu fixture
# o kurali gizlemez.
PLAYLIST_TEST_SCREEN = None


@pytest.fixture(autouse=True)
def _playlist_realistic_screen(monkeypatch):
    from PyQt6.QtCore import QRect

    from app import playlist_panel as _panel_module

    screen = QRect(0, 0, 2560, 1392)
    monkeypatch.setattr(_panel_module.WindowPlacement, "_screen_rect",
                        lambda self: screen, raising=False)
