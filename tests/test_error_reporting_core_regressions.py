"""Güvenli hata çekirdeği (1. aşama) sözleşmesi.

Sorun: `show_user_error()` yakalanan istisnanın HAM traceback'ini
`QMessageBox.setDetailedText()` ile kullanıcıya gösteriyordu. Traceback ve
istisna metinleri kullanıcı adı, tam medya yolu, API anahtarı, parola,
`Authorization` başlığı veya URL token'ı taşıyabilir.

Bu dosya şu sınırı kilitler:

- kullanıcıya YALNIZ güvenli Türkçe mesaj gider,
- geliştirici logunda tanı bilgisi kalır ama hassas değerler maskelenir,
- her hata TEK bir kayıt numarasıyla kaydedilir,
- eski çağrı biçimleri çalışmaya devam eder.

Testler gerçek `APPDATA` log dosyasına DOKUNMAZ; her test kendi geçici
dizinini kullanır.
"""
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

SECRET = "abcdef123456"
REAL_USER_PATH = r"C:\Users\GercekKullanici\Videos\film.mkv"


class BoxSpy:
    """`QMessageBox` yerine geçen kayıt tutucu."""

    instances = []

    class Icon:
        Critical = "critical"

    class StandardButton:
        Ok = "ok"

    class ButtonRole:
        # 2. asama: ana kutuya IKINCIL "Hata Ayrintilarini Goruntule"
        # dugmesi eklendi. Dublor yalnizca yeni Qt API'sini taniyacak
        # kadar genisletildi; olculen sozlesme DEGISMEDI.
        ActionRole = "action"

    def __init__(self, parent=None):
        self.parent = parent
        self.title = ""
        self.text = ""
        self.detailed = None
        self.executed = 0
        self.added_buttons = []
        self.default = None
        self.escape = None
        self._handles = []
        self._standard = {}
        BoxSpy.instances.append(self)

    def button(self, which):
        return self._standard.setdefault(which, object())

    def addButton(self, text, role):
        handle = object()
        self.added_buttons.append((text, role))
        self._handles.append(handle)
        return handle

    def setDefaultButton(self, button):
        self.default = button

    def setEscapeButton(self, button):
        self.escape = button

    def clickedButton(self):
        # Kullanici "Tamam"a basar: ayrinti penceresi ACILMAZ.
        return self.button(BoxSpy.StandardButton.Ok)

    def setIcon(self, icon):
        self.icon = icon

    def setWindowTitle(self, title):
        self.title = title

    def setText(self, text):
        self.text = text

    def setDetailedText(self, text):
        self.detailed = text

    def setStandardButtons(self, buttons):
        self.buttons = buttons

    def exec(self):
        self.executed += 1
        return 0


@pytest.fixture
def error_env(tmp_path, monkeypatch):
    """İzole log dizini + `QMessageBox.exec()` engellenmiş kutu."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    BoxSpy.instances = []
    monkeypatch.setattr(errors, "QMessageBox", BoxSpy)

    def read_log():
        path = errors.get_log_path()
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    return type("Env", (), {"tmp_path": tmp_path, "boxes": BoxSpy.instances,
                            "read_log": staticmethod(read_log)})


def raise_and_catch(exception):
    """Gerçek `__traceback__` taşıyan bir istisna üretir."""
    try:
        raise exception
    except type(exception) as caught:
        return caught


def test_log_is_written_into_the_temporary_directory(error_env):
    errors.log("izolasyon kontrolü", "INFO")
    assert str(error_env.tmp_path) in errors.get_log_path()
    assert "izolasyon kontrolü" in error_env.read_log()


# --- 1. Kullanıcı penceresi ---------------------------------------------

def test_user_box_never_shows_a_raw_traceback(error_env):
    exc = raise_and_catch(RuntimeError("dahili çökme"))
    errors.show_user_error(None, "Dosya Açılamadı",
                           "Dosya açılamadı. Tekrar deneyin.", exc=exc)

    box = error_env.boxes[-1]
    assert box.executed == 1
    assert "Traceback" not in box.text
    assert "raise_and_catch" not in box.text
    assert box.detailed is None, (
        "teknik ayrıntı kullanıcı penceresine verilmemeli")


def test_detailed_text_is_never_called_with_technical_data(error_env):
    exc = raise_and_catch(ValueError(f"api_key={SECRET}"))
    errors.show_user_error(None, "Veri Hatası", "Beklenmeyen veri hatası.",
                           exc=exc)
    errors.show_error("Başlık", "Kullanıcı mesajı", details="traceback...")

    for box in error_env.boxes:
        assert box.detailed is None


def test_user_box_hides_the_secret_from_the_exception_message(error_env):
    exc = raise_and_catch(RuntimeError(
        f"istek reddedildi: Authorization: Bearer {SECRET}"))
    errors.show_user_error(None, "URL Oynatılamadı",
                           "Bu adresten video oynatılamadı.", exc=exc)

    box = error_env.boxes[-1]
    assert SECRET not in box.text
    assert "Bearer" not in box.text


def test_full_windows_path_never_reaches_the_user_text(error_env):
    errors.show_user_error(None, "Dosya Açılamadı",
                           f"Dosya açılamadı: {REAL_USER_PATH}")

    box = error_env.boxes[-1]
    assert "GercekKullanici" not in box.text
    assert REAL_USER_PATH not in box.text


def test_friendly_turkish_message_is_preserved(error_env):
    message = ("Dosya bulunamadı. Dosya taşınmış veya silinmiş olabilir.\n\n"
               "Çözüm: Dosyanın yerini kontrol edip tekrar açmayı deneyin.")
    errors.show_user_error(None, "Dosya Açılamadı", message)
    assert error_env.boxes[-1].text == message


# --- 2. Geliştirici logu -------------------------------------------------

@pytest.mark.parametrize("payload,secret", [
    (f"api_key={SECRET}", SECRET),
    (f"password={SECRET}", SECRET),
    (f"Authorization: Bearer {SECRET}", SECRET),
    (f"https://site.test/video?token={SECRET}", SECRET),
    (f'{{"token": "{SECRET}", "user": "x"}}', SECRET),
    (f'{{"api_key":"{SECRET}"}}', SECRET),
    (REAL_USER_PATH, "GercekKullanici"),
])
def test_sensitive_values_are_masked_in_the_log(error_env, payload, secret):
    exc = raise_and_catch(RuntimeError(payload))
    errors.show_user_error(None, "Hata", "Bir hata oluştu.", exc=exc)

    text = error_env.read_log()
    assert secret not in text, f"maskelenmedi: {payload}"


def test_log_keeps_the_record_id_and_the_exception_class(error_env):
    exc = raise_and_catch(FileNotFoundError("dosya yok"))
    event = errors.show_user_error(None, "Dosya Açılamadı",
                                   "Dosya bulunamadı.", exc=exc)

    text = error_env.read_log()
    assert event is not None
    assert event.record_id in text
    assert "FileNotFoundError" in text


def test_log_keeps_a_traceback_structure_for_diagnosis(error_env):
    exc = raise_and_catch(RuntimeError("bozuk durum"))
    errors.show_user_error(None, "Hata", "Bir hata oluştu.", exc=exc)

    text = error_env.read_log()
    assert "test_error_reporting_core_regressions" in text
    assert "raise_and_catch" in text


def test_log_write_failure_does_not_break_the_dialog(error_env, monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("disk dolu")

    monkeypatch.setattr(errors, "get_log_path", explode)
    exc = raise_and_catch(RuntimeError("kayıt yok"))
    errors.show_user_error(None, "Hata", "Bir hata oluştu.", exc=exc)

    assert error_env.boxes[-1].executed == 1
    assert error_env.boxes[-1].text == "Bir hata oluştu."


# --- 3. Kayıt numarası ---------------------------------------------------

def test_record_id_uses_the_safe_support_format(error_env):
    event = errors.show_user_error(None, "Hata", "Bir hata oluştu.")
    assert re.fullmatch(r"MLC-\d{8}-[0-9A-F]{4}", event.record_id), \
        event.record_id


def test_two_errors_get_different_record_ids(error_env):
    first = errors.show_user_error(None, "Hata", "Bir hata oluştu.")
    second = errors.show_user_error(None, "Hata", "Bir hata oluştu.")
    assert first.record_id != second.record_id


def test_record_id_is_not_presented_as_the_explanation(error_env):
    event = errors.show_user_error(None, "Hata", "Bir hata oluştu.")
    assert event.record_id not in error_env.boxes[-1].text


# --- 4. Tek kayıt --------------------------------------------------------

def test_uncaught_exception_is_logged_with_a_single_record_id(error_env):
    exc = raise_and_catch(RuntimeError("yakalanmamış"))
    errors._handle_exception(type(exc), exc, exc.__traceback__)

    text = error_env.read_log()
    ids = set(re.findall(r"MLC-\d{8}-[0-9A-F]{4}", text))
    assert len(ids) == 1, f"tek kayıt bekleniyordu: {ids}"
    assert text.count("RuntimeError") >= 1
    assert error_env.boxes[-1].detailed is None


# --- 5. Maskeleme dengeli mi? -------------------------------------------

@pytest.mark.parametrize("harmless", [
    "Dosya bulunamadı. Dosya taşınmış veya silinmiş olabilir.",
    "Oynatıcı ayarı uygulanamadı (video ayarı desteklenmiyor).",
    "Beklenmeyen bir veri hatası oluştu.",
    "mpv property does not exist",
])
def test_redaction_keeps_harmless_text_intact(harmless):
    assert errors.redact(harmless) == harmless


def test_redaction_masks_only_the_value_not_the_whole_line():
    masked = errors.redact(f"istek: api_key={SECRET} bitti")
    assert SECRET not in masked
    assert "istek:" in masked and "bitti" in masked and "api_key" in masked


def test_redaction_survives_non_string_input():
    assert errors.redact(None) == ""
    assert errors.redact(1234) == "1234"


# --- 6. Uyumluluk --------------------------------------------------------

def test_legacy_call_styles_still_work(error_env):
    errors.show_user_error(None, "Başlık", "Mesaj")
    errors.show_user_error(None, "Başlık", "Mesaj", RuntimeError("konumsal"))
    errors.show_user_error(None, "Başlık", "Mesaj",
                           exc=RuntimeError("anahtarli"))
    errors.show_user_error(None, "Başlık", "Mesaj", details="teknik metin")
    errors.show_error("Başlık", "Mesaj")
    errors.show_error("Başlık", "Mesaj", details="teknik metin")
    errors.log("mesaj")
    errors.debug("d")
    errors.info("i")
    errors.error("e")
    assert len(error_env.boxes) == 6
    assert all(box.executed == 1 for box in error_env.boxes)


def test_friendly_message_helper_is_unchanged():
    assert errors._friendly_message(FileNotFoundError, None).startswith(
        "Dosya bulunamadı")
    assert errors._friendly_message(PermissionError, None).startswith(
        "Dosyaya erişim izniniz yok")
    assert errors._friendly_message(KeyError, None) is None


def test_install_exception_handler_sets_the_hook(monkeypatch):
    import sys

    original = sys.excepthook
    try:
        errors.install_exception_handler()
        assert sys.excepthook is errors._handle_exception
    finally:
        sys.excepthook = original


# --- 7. Merkezi kayıt ----------------------------------------------------

def test_build_error_event_carries_the_expected_fields(error_env):
    exc = raise_and_catch(PermissionError(f"password={SECRET}"))
    event = errors.build_error_event("Başlık", "Kullanıcı mesajı", exc=exc)

    assert event.title == "Başlık"
    assert event.user_message == "Kullanıcı mesajı"
    assert event.exception_type == "PermissionError"
    assert event.category
    assert SECRET not in event.developer_detail
    assert SECRET not in event.technical_summary
    assert "PermissionError" in event.technical_summary


def test_error_event_is_immutable(error_env):
    event = errors.build_error_event("Başlık", "Mesaj")
    with pytest.raises(Exception):
        event.record_id = "MLC-19700101-0000"
