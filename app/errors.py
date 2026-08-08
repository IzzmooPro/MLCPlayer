import os
import sys
import traceback
from datetime import datetime

from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import Qt

# Yol: APPDATA/MLCPlayer/logs/uygulama.log
def get_log_path():
    appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
    log_dir = os.path.join(appdata, 'MLCPlayer', 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.join(log_dir, 'uygulama.log')


def log(message, level='INFO'):
    """Hata/geliştirici günlüğü. EXE'de konsol olmasa bile dosyaya yazılır."""
    try:
        path = get_log_path()
        if os.path.exists(path) and os.path.getsize(path) > 2 * 1024 * 1024:
            backup = path + '.1'
            try:
                if os.path.exists(backup):
                    os.remove(backup)
                os.replace(path, backup)
            except OSError:
                pass
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}"
        with open(path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def debug(message):
    log(message, 'DEBUG')


def info(message):
    log(message, 'INFO')


def error(message):
    log(message, 'ERROR')


def _friendly_message(exc_type, exc_value):
    """Bilinen hataları anlaşılır Türkçe açıklamaya çevirir."""
    name = exc_type.__name__ if isinstance(exc_type, type) else str(exc_type)
    msg = str(exc_value) if exc_value else ''

    if name == 'FileNotFoundError':
        return ("Dosya bulunamadı. Dosya taşınmış veya silinmiş olabilir.\n\n"
                "Çözüm: Dosyanın yerini kontrol edip tekrar açmayı deneyin.")
    if name == 'PermissionError':
        return ("Dosyaya erişim izniniz yok.\n\n"
                "Çözüm: Dosyanın kilidini açın veya başka bir klasöre kopyalayın.")
    if name == 'NotADirectoryError' or name == 'IsADirectoryError':
        return "Seçilen konum geçerli bir medya dosyası değil."
    if 'mpv property does not exist' in msg:
        return ("Oynatıcı ayarı uygulanamadı (video ayarı desteklenmiyor).\n\n"
                "Bu işlem mpv'nin bu sürümünde bulunmayan bir özellik kullanmaya çalıştı. "
                "Diğer ayarlarla devam edebilirsiniz.")
    if name == 'OSError' and ('dxv' in msg.lower() or 'dll' in msg.lower() or 'cannot load' in msg.lower()):
        return ("MPV bileşeni yüklenemedi.\n\n"
                "Çözüm: Programın 'bin' klasörünün eksiksiz olduğundan emin olun. "
                "Programı kurulum klasöründen çalıştırın.")
    if name in ('ValueError', 'TypeError'):
        return ("Beklenmeyen bir veri hatası oluştu.\n\n"
                "Lütfen işlemi tekrar deneyin. Sorun devam ederse programı "
                "yeniden başlatın.")
    return None


def show_error(title, message, details=None):
    """Kullanıcıya anlaşılır hata penceresi gösterir."""
    log(f"Kullanıcı hatası gösterildi: {title} - {message}")
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def show_user_error(parent, title, user_message, exc=None, details=None):
    """Kullanıcıya sade bir hata mesajı gösterir; teknik ayrıntıyı log'a
    ve QMessageBox'un gizli 'Ayrıntılar' bölümüne yazar (geliştirici için).
    - user_message: Kullanıcının anlayacağı kısa açıklama (Türkçe).
    - exc: Yakalanan istisna (opsiyonel). Log'a tam hali yazılır."""
    if exc is not None:
        traceback_text = ''.join(traceback.format_exception(
            type(exc), exc, exc.__traceback__))
        details = traceback_text

    log_message = f"{title}: {user_message}"
    if details:
        log_message += f"\nTeknik ayrıntı:\n{details}"
    log(log_message, 'ERROR')

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(user_message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def _handle_exception(exc_type, exc_value, exc_tb):
    """Yakalanmamış her Python hatası buraya düşer."""
    traceback_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log(f"Yakalanmamış hata:\n{traceback_text}", 'ERROR')
    print(traceback_text)  # Geliştirici konsolu (varsa)

    friendly = _friendly_message(exc_type, exc_value)
    title = "Beklenmeyen Hata"
    if friendly:
        message = friendly
    else:
        message = ("Beklenmeyen bir hata oluştu.\n\n"
                   "Program çalışmaya devam ediyor, ancak bu işlem tamamlanamadı.\n"
                   "Sorun devam ederse programı yeniden başlatın.")

    try:
        show_error(title, message, details=traceback_text)
    except Exception:
        pass


def install_exception_handler():
    """Uygulama başlangıcında çağrılır - tüm yakalanmamış hataları yakalar."""
    sys.excepthook = _handle_exception
