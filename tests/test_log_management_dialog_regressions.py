"""3. aşama — ayrı "Günlük Yönetimi" penceresi.

Sözleşme:

- Yardım menüsünde TEK bir `Günlük Yönetimi` aksiyonu bulunur; özel
  başlık çubuğundaki üç nokta menüsü menubar'ı yansıttığı için orada da
  görünür.
- Pencere açılırken dosya sistemi DEĞİŞMEZ; otomatik silme, otomatik
  pano veya ağ işlemi yoktur.
- Log İÇERİĞİ ve mutlak kullanıcı yolu ekranda gösterilmez.
- Klasör yalnız kullanıcı tıklarsa `QDesktopServices` ile açılır.
- `Günlükleri Temizle` doğrudan silmez: ayrı onay penceresi açar,
  `İptal` varsayılan ve Escape düğmesidir, iptal edilirse dosya sistemi
  değişmez.
- Onaydan sonra yalnız izinli iki dosya silinir; başarıda 0 bayt ve
  "Günlükler temizlendi." gösterilir, başarısızlıkta ham istisna
  kullanıcıya ULAŞMAZ.

Bütün değerler sentetiktir; testler geçici günlük dizini kullanır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton

from app import errors

WIN_PATH = r"C:\Users\Gercek Kullanici\Private Folder\film.mkv"
LOG_CONTENT = "GIZLI_LOG_SATIRI api_key=SENTETIK123"


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert str(tmp_path) in errors.get_log_path()
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(LOG_CONTENT + "\n")
    with open(path + ".1", "w", encoding="utf-8") as handle:
        handle.write("eski kayit\n")
    unrelated = os.path.join(os.path.dirname(path), "unrelated.txt")
    with open(unrelated, "w", encoding="utf-8") as handle:
        handle.write("dokunma")
    return type("Env", (), {"path": path, "backup": path + ".1",
                            "unrelated": unrelated, "dir": tmp_path})


class MenuPlayer(QMainWindow):
    """`setup_menu()` için minimum ama gerçek QMainWindow."""

    def __init__(self):
        super().__init__()
        self.__dict__["calls"] = []
        self.loop_file = False
        self.loop_playlist = False
        self.shuffle = False
        self.speed_actions = {}
        self.recent_files = []
        self.current_file = ""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def recorder(*args, **kwargs):
            self.__dict__["calls"].append(name)
        return recorder


# =====================================================================
# A. Menü erişim noktası
# =====================================================================

def test_help_menu_has_exactly_one_log_management_action():
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    setup_menu(window)
    menus = {action.text(): action.menu()
             for action in window.menuBar().actions() if action.menu()}
    assert "Yardım" in menus
    labels = [action.text() for action in menus["Yardım"].actions()]
    assert labels.count("Günlük Yönetimi") == 1, labels
    window.close()
    window.deleteLater()


def test_menu_action_calls_the_product_entry_point():
    from app.menu_actions import setup_menu

    window = MenuPlayer()
    setup_menu(window)
    action = next(item for menu in window.menuBar().actions() if menu.menu()
                  for item in menu.menu().actions()
                  if item.text() == "Günlük Yönetimi")
    action.trigger()
    assert "show_log_management" in window.calls
    window.close()
    window.deleteLater()


def test_player_exposes_the_entry_point():
    from app.player import MPVPlayer

    assert hasattr(MPVPlayer, "show_log_management")


# =====================================================================
# B. Pencere içeriği
# =====================================================================

def test_opening_the_dialog_changes_nothing_on_disk(log_env):
    from app.log_management_dialog import LogManagementDialog

    before = {path: os.path.getsize(path)
              for path in (log_env.path, log_env.backup, log_env.unrelated)}
    dialog = LogManagementDialog()
    try:
        after = {path: os.path.getsize(path) for path in before}
        assert after == before
    finally:
        dialog.deleteLater()


def test_dialog_shows_policy_and_usage_without_log_content(log_env):
    from app.log_management_dialog import LogManagementDialog

    dialog = LogManagementDialog()
    try:
        blob = dialog.visible_text()
        assert "Günlük Yönetimi" == dialog.windowTitle()
        assert "2 MiB" in blob and "1 yedek" in blob
        assert "GIZLI_LOG_SATIRI" not in blob, "log içeriği ekranda"
        assert "SENTETIK123" not in blob
        assert str(log_env.dir) not in blob, "mutlak kullanıcı yolu ekranda"
        assert "Gercek Kullanici" not in blob
        # Kullanıcı dostu boyut gösterimi.
        assert "bayt" in blob or "KB" in blob or "MB" in blob
    finally:
        dialog.deleteLater()


def test_dialog_has_only_the_three_expected_buttons(log_env):
    from app.log_management_dialog import LogManagementDialog

    dialog = LogManagementDialog()
    try:
        texts = [button.text() for button in dialog.findChildren(QPushButton)]
        assert texts == ["Günlük Klasörünü Aç", "Günlükleri Temizle", "Kapat"]
    finally:
        dialog.deleteLater()


def test_folder_opens_only_on_click(log_env, monkeypatch):
    from app import log_management_dialog as module

    opened = []
    monkeypatch.setattr(module.QDesktopServices, "openUrl",
                        staticmethod(lambda url: opened.append(url) or True))
    dialog = module.LogManagementDialog()
    try:
        assert opened == []
        dialog.open_button.click()
        assert len(opened) == 1
        assert opened[0].isLocalFile()
    finally:
        dialog.deleteLater()


def test_folder_open_failure_shows_no_raw_system_error(log_env, monkeypatch):
    from app import log_management_dialog as module

    def explode(_url):
        raise OSError(f"acilamadi: {WIN_PATH}")

    monkeypatch.setattr(module.QDesktopServices, "openUrl",
                        staticmethod(explode))
    dialog = module.LogManagementDialog()
    try:
        dialog.open_button.click()      # istisna firlatmamali
        blob = dialog.visible_text()
        assert "Gercek Kullanici" not in blob and "acilamadi" not in blob
    finally:
        dialog.deleteLater()


# =====================================================================
# C. Temizleme onayı
# =====================================================================

class ConfirmBox:
    """Onay penceresinin ölçülebilir dublörü."""

    instances = []
    accept = False

    class Icon:
        Warning = "warning"

    class StandardButton:
        # Gerçek Qt bayrakları `|` ile birleştirilir; dublör de aynı
        # işleci desteklemelidir (string olsaydı TypeError süreci
        # düşürürdü).
        Yes = 1
        Cancel = 2

    def __init__(self, parent=None):
        self.parent = parent
        self.title = ""
        self.text = ""
        self.standard = None
        self.default = None
        self.escape = None
        self.executed = 0
        self._handles = {}
        ConfirmBox.instances.append(self)

    def setIcon(self, icon):
        self.icon = icon

    def setWindowTitle(self, title):
        self.title = title

    def setText(self, text):
        self.text = text

    def setStandardButtons(self, buttons):
        self.standard = buttons

    def button(self, which):
        return self._handles.setdefault(which, object())

    def setDefaultButton(self, button):
        self.default = button

    def setEscapeButton(self, button):
        self.escape = button

    def exec(self):
        self.executed += 1
        return 0

    def clickedButton(self):
        which = (ConfirmBox.StandardButton.Yes if ConfirmBox.accept
                 else ConfirmBox.StandardButton.Cancel)
        return self.button(which)


@pytest.fixture
def confirm(monkeypatch):
    from app import log_management_dialog as module

    ConfirmBox.instances = []
    ConfirmBox.accept = False
    monkeypatch.setattr(module, "QMessageBox", ConfirmBox)
    return ConfirmBox


def test_clear_asks_for_confirmation_first(log_env, confirm):
    from app.log_management_dialog import LogManagementDialog

    dialog = LogManagementDialog()
    try:
        dialog.clear_button.click()
        assert len(confirm.instances) == 1
        box = confirm.instances[-1]
        assert "geri alınamaz" in box.text
        assert "kalıcı olarak silinecek" in box.text
        assert os.path.exists(log_env.path), "onaysız silindi"
    finally:
        dialog.deleteLater()


def test_cancel_is_default_and_escape_and_changes_nothing(log_env, confirm):
    from app.log_management_dialog import LogManagementDialog

    dialog = LogManagementDialog()
    try:
        dialog.clear_button.click()
        box = confirm.instances[-1]
        cancel = box.button(ConfirmBox.StandardButton.Cancel)
        assert box.default is cancel, "İptal varsayılan olmalı"
        assert box.escape is cancel
        assert os.path.exists(log_env.path)
        assert os.path.exists(log_env.backup)
        assert os.path.exists(log_env.unrelated)
    finally:
        dialog.deleteLater()


def test_confirmed_clear_removes_only_allowed_files(log_env, confirm):
    from app.log_management_dialog import LogManagementDialog

    confirm.accept = True
    dialog = LogManagementDialog()
    try:
        dialog.clear_button.click()
        assert not os.path.exists(log_env.path)
        assert not os.path.exists(log_env.backup)
        assert os.path.exists(log_env.unrelated)
        blob = dialog.visible_text()
        assert "Günlükler temizlendi." in blob
        assert "0 bayt" in blob
    finally:
        dialog.deleteLater()


def test_clear_failure_never_shows_a_raw_exception(log_env, confirm,
                                                   monkeypatch):
    from app import log_management_dialog as module

    def explode():
        raise OSError(f"erisim reddedildi: {WIN_PATH}")

    monkeypatch.setattr(module, "clear_logs", explode)
    confirm.accept = True
    dialog = module.LogManagementDialog()
    try:
        dialog.clear_button.click()     # istisna firlatmamali
        blob = dialog.visible_text()
        assert "Gercek Kullanici" not in blob
        assert "erisim reddedildi" not in blob
        assert "Traceback" not in blob
    finally:
        dialog.deleteLater()


def test_reported_failure_message_is_user_friendly(log_env, confirm,
                                                   monkeypatch):
    from app import log_management_dialog as module

    monkeypatch.setattr(module, "clear_logs",
                        lambda: errors.LogClearResult(
                            False, (), ("uygulama.log",),
                            errors.LOG_CLEAR_FAILED_MESSAGE))
    confirm.accept = True
    dialog = module.LogManagementDialog()
    try:
        dialog.clear_button.click()
        assert errors.LOG_CLEAR_FAILED_MESSAGE in dialog.visible_text()
    finally:
        dialog.deleteLater()


# =====================================================================
# D. Ayrı akış
# =====================================================================

def test_dialog_is_independent_from_the_error_details_window(log_env):
    from app.error_details_dialog import ErrorDetailsDialog
    from app.log_management_dialog import LogManagementDialog

    dialog = LogManagementDialog()
    try:
        assert not isinstance(dialog, ErrorDetailsDialog)
        texts = [button.text() for button in dialog.findChildren(QPushButton)]
        assert "Bilgileri Kopyala" not in texts
        # NOT: `hasattr(dialog, "event")` QObject.event() nedeniyle her
        # zaman True'dur; ölçülen şey pencerenin bir `ErrorEvent`
        # TAŞIMAMASIDIR.
        assert "event" not in vars(dialog)
    finally:
        dialog.deleteLater()


def test_no_report_or_send_feature_exists(log_env):
    """Ağ/gönderim KODU bulunmamalı.

    Türkçe "gönder"/"bildir" kelimeleri kaynakta yalnız "bu özellik
    YOKTUR" açıklaması olarak geçebilir; bu yüzden metin değil KOD
    aranır ve arayüzde böyle bir düğme olmadığı ayrıca ölçülür.
    """
    import ast

    from app import log_management_dialog as module
    from app.log_management_dialog import LogManagementDialog

    tree = ast.parse(open(module.__file__, encoding="utf-8").read())
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute)}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
    banned = {"requests", "urlopen", "urllib", "socket", "subprocess",
              "QNetworkAccessManager", "QTcpSocket", "os.system", "popen"}
    assert not (banned & (names | imported | attributes))
    assert not any(item.startswith("PyQt6.QtNetwork") for item in imported)

    dialog = LogManagementDialog()
    try:
        labels = " ".join(button.text()
                          for button in dialog.findChildren(QPushButton))
        assert "Gönder" not in labels and "Bildir" not in labels
    finally:
        dialog.deleteLater()


def test_opening_the_dialog_does_not_touch_the_clipboard(log_env):
    from app.log_management_dialog import LogManagementDialog

    clipboard = QApplication.clipboard()
    clipboard.setText("SENTINEL")
    dialog = LogManagementDialog()
    try:
        assert clipboard.text() == "SENTINEL"
    finally:
        dialog.deleteLater()
