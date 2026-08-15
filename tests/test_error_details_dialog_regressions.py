"""2. aşama: ayrı ve güvenli "Hata Ayrıntıları" penceresi.

Sözleşme:

- Ana hata kutusu SADE kalır: yalnız simge, Türkçe başlık, kullanıcı
  mesajı, `Tamam` ve ikincil `Hata Ayrıntılarını Görüntüle` düğmesi.
  Kayıt numarası, istisna sınıfı, teknik özet ve traceback ana kutuya
  ULAŞMAZ; `setDetailedText()` kullanılmaz.
- Ayrıntılar KENDİLİĞİNDEN açılmaz. Yalnız kullanıcı düğmeye basarsa
  ayrı bir `QDialog` açılır ve AYNI `ErrorEvent` gösterilir: yeni kayıt
  numarası üretilmez, ikinci log kaydı yazılmaz.
- Pencerede ve panoda ham yol, token, `Authorization`, parola veya ham
  `str(exception)` bulunmaz; gösterim ve kopyalama sınırlarında
  `redact()` savunma amaçlı TEKRAR uygulanır.

Bütün değerler SENTETİKTİR.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from app import errors

WIN_PATH = r"C:\Users\Gercek Kullanici\Private Folder\film.mkv"
UNC_PATH = r"\\server\share\Private Folder\film.mkv"
FILE_URI = "file://server/share/Private Folder/film.mkv"
TOKEN_URL = "https://cdn.test/v.m3u8?token=SENTETIK123"
AUTH_LINE = "Authorization: Digest SENTETIK456"
PASSWORD = 'password="SENTETIK789"'
SINGLE_QUOTED = r"'D:\Private Folder\gizli klasor'"
DOUBLE_QUOTED = r'"D:\Private Folder\film.mkv"'

RAW_MARKERS = ("Gercek Kullanici", "Private Folder", "film.mkv", "server",
               "share", "SENTETIK123", "SENTETIK456", "SENTETIK789",
               "gizli klasor")


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def read():
        path = errors.get_log_path()
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    assert str(tmp_path) in errors.get_log_path()
    return read


def scrub(text):
    return str(text).replace(errors.MASK, "").replace(errors.MASK_PATH, "")


def assert_safe(text):
    scanned = scrub(text)
    for marker in RAW_MARKERS:
        assert marker not in scanned, f"{marker} sizdi: {text!r}"


def noisy_exception():
    """Ham yol, token, Authorization ve parola taşıyan sentetik istisna."""
    try:
        raise OSError(
            f"acilamadi: {WIN_PATH} | {UNC_PATH} | {FILE_URI} | {TOKEN_URL} | "
            f"{AUTH_LINE} | {PASSWORD} | {SINGLE_QUOTED} | {DOUBLE_QUOTED}")
    except OSError as exc:
        return exc


class FakeBox:
    """Ana hata kutusunun ölçülebilir dublörü."""

    instances = []

    class Icon:
        Critical = "critical"

    class StandardButton:
        Ok = "ok"

    class ButtonRole:
        ActionRole = "action"

    click_details = False

    def __init__(self, parent=None):
        self.parent = parent
        self.title = ""
        self.text = ""
        self.detailed = None
        self.buttons = []
        self.standard = None
        self.default = None
        self.escape = None
        self.executed = 0
        self._handles = []
        self._standard_handles = {}
        FakeBox.instances.append(self)

    def setIcon(self, icon):
        self.icon = icon

    def setWindowTitle(self, title):
        self.title = title

    def setText(self, text):
        self.text = text

    def setDetailedText(self, text):
        self.detailed = text

    def setStandardButtons(self, buttons):
        self.standard = buttons

    def button(self, which):
        # Gerçek Qt aynı düğme NESNESİNİ döndürür; ürün kodu `is` ile
        # karşılaştırdığı için dublör de kalıcı nesneler vermelidir.
        return self._standard_handles.setdefault(which, object())

    def addButton(self, text, role):
        handle = object()
        self.buttons.append((text, role))
        self._handles.append(handle)
        return handle

    def setDefaultButton(self, button):
        self.default = button

    def setEscapeButton(self, button):
        self.escape = button

    def clickedButton(self):
        if FakeBox.click_details and self._handles:
            return self._handles[0]
        return self.button(FakeBox.StandardButton.Ok)

    def exec(self):
        self.executed += 1
        return 0


@pytest.fixture
def fake_box(monkeypatch):
    FakeBox.instances = []
    FakeBox.click_details = False
    monkeypatch.setattr(errors, "QMessageBox", FakeBox)
    return FakeBox


# =====================================================================
# A. Ana hata kutusu
# =====================================================================

def test_main_box_keeps_title_and_user_message(log_env, fake_box):
    event = errors.show_user_error(None, "Dosya Açılamadı",
                                   "Dosya açılamadı. Tekrar deneyin.",
                                   exc=noisy_exception())
    box = fake_box.instances[-1]
    assert box.title == "Dosya Açılamadı"
    assert box.text == "Dosya açılamadı. Tekrar deneyin."
    assert box.executed == 1
    assert event.record_id


def test_main_box_never_uses_detailed_text(log_env, fake_box):
    errors.show_user_error(None, "Hata", "Bir sorun oluştu.",
                           exc=noisy_exception())
    errors.show_error("Başlık", "Kullanıcı mesajı", details="teknik metin")
    for box in fake_box.instances:
        assert box.detailed is None


def test_main_box_hides_record_id_summary_and_traceback(log_env, fake_box):
    event = errors.show_user_error(None, "Hata", "Bir sorun oluştu.",
                                   exc=noisy_exception())
    box = fake_box.instances[-1]
    combined = f"{box.title}\n{box.text}"
    assert event.record_id not in combined
    assert event.technical_summary not in combined
    assert "Traceback" not in combined
    assert "OSError" not in combined
    assert_safe(combined)


def test_main_box_offers_the_details_button(log_env, fake_box):
    errors.show_user_error(None, "Hata", "Bir sorun oluştu.",
                           exc=noisy_exception())
    box = fake_box.instances[-1]
    assert box.buttons, "ayrıntı düğmesi eklenmedi"
    text, role = box.buttons[0]
    assert text == errors.DETAILS_BUTTON_TEXT
    assert role == FakeBox.ButtonRole.ActionRole


def test_ok_is_the_default_and_escape_button(log_env, fake_box):
    errors.show_user_error(None, "Hata", "Bir sorun oluştu.")
    box = fake_box.instances[-1]
    expected = box.button(FakeBox.StandardButton.Ok)
    assert box.default == expected, "Enter ayrıntıları açmamalı"
    assert box.escape == expected


def test_details_dialog_is_not_created_without_a_click(log_env, fake_box,
                                                      monkeypatch):
    opened = []
    monkeypatch.setattr(errors, "_open_error_details",
                        lambda parent, event: opened.append(event))
    errors.show_user_error(None, "Hata", "Bir sorun oluştu.",
                           exc=noisy_exception())
    assert opened == []


def test_clipboard_is_untouched_when_the_dialog_is_not_opened(log_env,
                                                              fake_box):
    clipboard = QApplication.clipboard()
    clipboard.setText("SENTINEL")
    errors.show_user_error(None, "Hata", "Bir sorun oluştu.",
                           exc=noisy_exception())
    assert clipboard.text() == "SENTINEL"


# =====================================================================
# B. Ayrı pencere
# =====================================================================

def test_details_dialog_opens_only_on_click(log_env, fake_box, monkeypatch):
    opened = []
    monkeypatch.setattr(errors, "_open_error_details",
                        lambda parent, event: opened.append(event))
    fake_box.click_details = True
    event = errors.show_user_error(None, "Hata", "Bir sorun oluştu.",
                                   exc=noisy_exception())
    assert len(opened) == 1
    assert opened[0] is event


def test_opening_details_creates_no_second_event_or_log(log_env, fake_box,
                                                        monkeypatch):
    import re

    from app.error_details_dialog import ErrorDetailsDialog

    shown = []
    monkeypatch.setattr(ErrorDetailsDialog, "exec",
                        lambda self: shown.append(self) or 0)
    fake_box.click_details = True
    event = errors.show_user_error(None, "Hata", "Bir sorun oluştu.",
                                   exc=noisy_exception())
    text = log_env()
    ids = set(re.findall(errors.RECORD_ID_PATTERN, text))
    assert ids == {event.record_id}, ids
    assert len(shown) == 1
    assert shown[0].event is event


def test_dialog_shows_every_expected_field(log_env):
    from app.error_details_dialog import ErrorDetailsDialog

    event = errors.build_error_event("Dosya Açılamadı", "Tekrar deneyin.",
                                     exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        labels = [label for label, _value in dialog.fields()]
        assert labels == ["Kayıt numarası", "Tarih", "Kategori",
                          "Hata başlığı", "Kullanıcı mesajı", "Hata türü",
                          "Teknik özet"]
        values = dict(dialog.fields())
        assert values["Kayıt numarası"] == event.record_id
        assert values["Hata türü"] == "OSError"
        assert values["Kategori"] == event.category
        assert dialog.windowTitle() == "Hata Ayrıntıları"
        assert "otomatik olarak gizlenmiştir" in dialog.intro_text()
    finally:
        dialog.deleteLater()


def test_detail_view_is_read_only_and_scrollable(log_env):
    from app.error_details_dialog import ErrorDetailsDialog

    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        assert dialog.detail_view.isReadOnly()
        assert dialog.detail_view.verticalScrollBarPolicy() is not None
        assert dialog.detail_text().strip()
    finally:
        dialog.deleteLater()


def test_empty_developer_detail_shows_a_safe_notice(log_env):
    from app.error_details_dialog import EMPTY_DETAIL, ErrorDetailsDialog

    event = errors.build_error_event("Hata", "Mesaj")
    dialog = ErrorDetailsDialog(event)
    try:
        assert dialog.detail_text() == EMPTY_DETAIL
    finally:
        dialog.deleteLater()


def test_dialog_does_not_rebuild_the_traceback_from_the_exception(log_env):
    from app.error_details_dialog import ErrorDetailsDialog

    exc = noisy_exception()
    event = errors.build_error_event("Hata", "Mesaj", exc=exc)
    dialog = ErrorDetailsDialog(event)
    try:
        assert dialog.detail_text() == errors.redact(event.developer_detail)
        assert not hasattr(dialog, "exception")
    finally:
        dialog.deleteLater()


def test_dialog_has_only_copy_and_close_buttons(log_env):
    from app.error_details_dialog import ErrorDetailsDialog
    from PyQt6.QtWidgets import QPushButton

    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        texts = [button.text() for button in dialog.findChildren(QPushButton)]
        assert texts == ["Bilgileri Kopyala", "Kapat"]
    finally:
        dialog.deleteLater()


def test_dialog_keeps_its_parent_and_closes_cleanly(log_env):
    from PyQt6.QtWidgets import QWidget

    from app.error_details_dialog import ErrorDetailsDialog

    parent = QWidget()
    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event, parent)
    try:
        assert dialog.parent() is parent
        dialog.close_button.click()
        assert not dialog.isVisible()
    finally:
        dialog.deleteLater()
        parent.deleteLater()


# =====================================================================
# C. Güvenlik
# =====================================================================

def test_no_raw_value_appears_anywhere_in_the_dialog(log_env):
    from app.error_details_dialog import ErrorDetailsDialog

    event = errors.build_error_event(f"Hata {WIN_PATH}", f"Mesaj {TOKEN_URL}",
                                     exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        blob = dialog.intro_text() + "\n" + dialog.detail_text()
        for label, value in dialog.fields():
            blob += f"\n{label}: {value}"
        assert_safe(blob)
        assert errors.MASK_PATH in blob or errors.MASK in blob
    finally:
        dialog.deleteLater()


def test_display_applies_redaction_again_defensively(log_env, monkeypatch):
    from app import error_details_dialog

    calls = []
    real = errors.redact

    def counting(text):
        calls.append(text)
        return real(text)

    monkeypatch.setattr(error_details_dialog, "redact", counting)
    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = error_details_dialog.ErrorDetailsDialog(event)
    try:
        assert calls, "gösterimden önce redact uygulanmadı"
    finally:
        dialog.deleteLater()


def test_masked_output_is_idempotent(log_env):
    from app.error_details_dialog import ErrorDetailsDialog

    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        once = dialog.detail_text()
        assert errors.redact(once) == once
    finally:
        dialog.deleteLater()


# =====================================================================
# D. Pano
# =====================================================================

def test_clipboard_changes_only_after_the_copy_click(log_env):
    from app.error_details_dialog import ErrorDetailsDialog

    clipboard = QApplication.clipboard()
    clipboard.setText("SENTINEL")
    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        assert clipboard.text() == "SENTINEL"
        dialog.copy_button.click()
        assert clipboard.text() != "SENTINEL"
        assert_safe(clipboard.text())
        assert event.record_id in clipboard.text()
        assert event.technical_summary in clipboard.text()
    finally:
        dialog.deleteLater()


def test_copy_writes_once_and_stays_safe(log_env):
    from app.error_details_dialog import ErrorDetailsDialog

    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        writes = []
        dialog._write_clipboard = lambda text: writes.append(text)
        dialog.copy_button.click()
        assert len(writes) == 1
        assert_safe(writes[0])
    finally:
        dialog.deleteLater()


def test_clipboard_failure_never_leaks_or_raises(log_env, capsys):
    from app.error_details_dialog import ErrorDetailsDialog

    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        def explode(_text):
            raise OSError(f"pano yok: {WIN_PATH}")

        dialog._write_clipboard = explode
        dialog.copy_button.click()          # istisna firlatmamali
        assert_safe(capsys.readouterr().out)
    finally:
        dialog.deleteLater()


def test_copy_does_not_read_the_log_file(log_env, monkeypatch):
    from app import error_details_dialog
    from app.error_details_dialog import ErrorDetailsDialog

    monkeypatch.setattr(error_details_dialog, "__file__",
                        error_details_dialog.__file__)
    event = errors.build_error_event("Hata", "Mesaj", exc=noisy_exception())
    dialog = ErrorDetailsDialog(event)
    try:
        errors.log("LOG_ONLY_MARKER")
        dialog.copy_button.click()
        assert "LOG_ONLY_MARKER" not in QApplication.clipboard().text()
    finally:
        dialog.deleteLater()


# =====================================================================
# E. Uyum
# =====================================================================

def test_legacy_call_styles_still_work(log_env, fake_box):
    errors.show_user_error(None, "Başlık", "Mesaj")
    errors.show_user_error(None, "Başlık", "Mesaj", RuntimeError("konumsal"))
    errors.show_user_error(None, "Başlık", "Mesaj", exc=RuntimeError("adli"))
    errors.show_user_error(None, "Başlık", "Mesaj", details="teknik")
    errors.show_error("Başlık", "Mesaj")
    errors.show_error("Başlık", "Mesaj", details="teknik")
    assert len(fake_box.instances) == 6
    assert all(box.executed == 1 for box in fake_box.instances)


def test_uncaught_exception_still_makes_one_event_and_one_log(log_env,
                                                              fake_box):
    import re

    exc = noisy_exception()
    event = errors._handle_exception(type(exc), exc, exc.__traceback__)
    text = log_env()
    assert set(re.findall(errors.RECORD_ID_PATTERN, text)) == {event.record_id}
    assert fake_box.instances[-1].detailed is None


def test_details_dialog_failure_does_not_break_the_error_flow(log_env,
                                                              fake_box,
                                                              monkeypatch,
                                                              capsys):
    def explode(event, parent=None):
        raise RuntimeError(f"acilamadi: {WIN_PATH}")

    import app.error_details_dialog as module

    monkeypatch.setattr(module, "ErrorDetailsDialog", explode)
    fake_box.click_details = True
    event = errors.show_user_error(None, "Hata", "Mesaj",
                                   exc=noisy_exception())
    assert event.record_id
    out = capsys.readouterr().out
    assert_safe(out)
    assert "Traceback" not in out
