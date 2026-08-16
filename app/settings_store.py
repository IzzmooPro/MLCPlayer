"""Kullanıcı ayarlarının TEK giriş noktası.

NEDEN VAR: Qt 6'da `QSettings(organization, application)` yapıcısı
`QSettings.setDefaultFormat()` değerini YOK SAYAR ve her zaman NativeFormat
ile açılır (Windows'ta doğrudan `HKCU\\Software\\...`). Test child'ları
`setDefaultFormat(IniFormat) + setPath(geçici dizin)` çağırdığı hâlde ürün
kodu gerçek kayıt defterine yazmaya devam ediyordu; görsel kabul koşumunun
sonda değeri kullanıcının gerçek altyazı rengine sızdı.

Ölçülen davranış (PyQt6 6.10, Windows):

    setDefaultFormat sonrası      -> Format.IniFormat
    QSettings(org, app)           -> Format.NativeFormat, \\HKEY_CURRENT_USER\\...
    QSettings(IniFormat, ...)     -> ...\\<dizin>\\MLCPlayer\\MLCPlayer.ini

Bu yüzden biçim BURADA açıkça verilir. Varsayılan biçim değiştirilmemişse
ürün davranışı aynen korunur (NativeFormat, kayıt defteri); test harness'i
varsayılanı Ini yaptığında yazımlar gerçekten izole dizine gider.

Ürün kodunda `QSettings(...)` doğrudan KURULMAZ; hepsi buradan geçer.
`tests/test_settings_isolation_regressions.py` bu kuralı korur.
"""

from PyQt6.QtCore import QSettings

SETTINGS_ORGANIZATION = "MLCPlayer"
SETTINGS_APPLICATION = "MLCPlayer"


def user_settings():
    """Kullanıcı kapsamlı ayar nesnesi; yürürlükteki varsayılan biçime uyar."""
    fmt = QSettings.defaultFormat()
    if fmt != QSettings.Format.NativeFormat:
        # Harness izolasyon kurmuş: biçimi AÇIKÇA vererek setPath'in
        # yönlendirdiği dizine yazılmasını sağlarız.
        return QSettings(fmt, QSettings.Scope.UserScope,
                         SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
