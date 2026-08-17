# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Güvenli hata çekirdeği — bağımsız incelemede bulunan üç açık.

1. Nihai log çıkışı güvenli değildi: `log()` mesajı doğrudan diske
   yazıyordu, bu yüzden `debug/info/error` ve `MPVPlayer.log_handler`
   üzerinden gelen libmpv tanıları `redact()` yolunu ATLAYABİLİYORDU.
2. `redact()` yaygın biçimleri kaçırıyordu (dict/JSON tek tırnak,
   tırnaklı değerler, `client_secret`, `Bearer` dışındaki
   `Authorization` şemaları, URL-encoded ayraç).
3. Yol maskeleme dardı: boşluklu kullanıcı adı/klasör, `Users` dışındaki
   sürücü yolları ve UNC paylaşımları maskelenmiyordu.

Bütün değerler SENTETİKTİR. Testler gerçek kullanıcının log dosyasına
dokunmaz: `APPDATA` ve `LOCALAPPDATA` geçici dizine yönlendirilir.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

# --- sentetik girdiler ---
FAKE_SECRET = "s3nt3t1k-degeR"
FAKE_USER = "Gerçek Kullanıcı"
USER_PATH = r"C:\Users\Gerçek Kullanıcı\My Videos\film.mkv"
DRIVE_PATH = r"D:\Private Folder\clip.mp4"
UNC_PATH = r"\\server\share\Private Folder\clip.mp4"
PATH_LEAKS = (FAKE_USER, "My Videos", "Private Folder", "server", "share",
              USER_PATH, DRIVE_PATH, UNC_PATH)


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    """Geçici log dizini; gerçek kullanıcı logu KORUNUR."""
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


# --- 1. Nihai yazma sınırı ----------------------------------------------

@pytest.mark.parametrize("writer", ["log", "debug", "info", "error"])
def test_every_log_level_is_masked_at_the_write_boundary(log_env, writer):
    message = (f"tani: api_key={FAKE_SECRET} {USER_PATH} "
               f"Authorization: Digest {FAKE_SECRET}")
    getattr(errors, writer)(message)

    text = log_env()
    assert message.split()[0] in text, "mesaj hiç yazılmamış"
    assert FAKE_SECRET not in text
    for leak in PATH_LEAKS:
        assert leak not in text, f"yol sızdı: {leak}"


def test_direct_log_call_with_unc_path_is_masked(log_env):
    """SÖZLEŞME DEĞİŞTİ: medya dosya adı artık tanı için KORUNMAZ.

    Eski beklenti `clip.mp4` adının logda kalmasıydı. Kullanıcı medya
    adı kişisel içerik taşıyabildiği için yolun tamamı maskelenir; tanı
    istisnası yalnız tırnaklı kaynak kod yolları (`.py`/`.pyw`) içindir.
    """
    errors.log(f"altyazı okunamadı: {UNC_PATH}", "WARNING")
    text = log_env()
    assert "server" not in text and "share" not in text
    assert "Private Folder" not in text
    assert "clip.mp4" not in text
    assert errors.MASK_PATH in text


def test_mpv_log_handler_diagnostics_are_masked_in_the_log(log_env):
    """libmpv tanısı ürün yolundan geçerek loga maskelenmiş düşmeli."""
    from app.player import MPVPlayer

    message = (f"stream error: https://cdn.test/v.m3u8?token={FAKE_SECRET}"
               f"&sig={FAKE_SECRET} Authorization: Bearer {FAKE_SECRET} "
               f"file={USER_PATH}")
    MPVPlayer.log_handler(object(), "error", "ffmpeg", message)

    text = log_env()
    assert "[ffmpeg]" in text, "libmpv tanısı loga düşmedi"
    assert FAKE_SECRET not in text
    for leak in PATH_LEAKS:
        assert leak not in text


def test_masking_at_the_boundary_is_idempotent(log_env):
    exc = RuntimeError(f"api_key={FAKE_SECRET} {USER_PATH}")
    errors.show_user_error(None, "Hata", "Bir hata oluştu.", exc=exc) \
        if False else None
    event = errors.build_error_event("Hata", "Bir hata oluştu.", exc=exc)
    errors.log_error_event(event)

    text = log_env()
    assert FAKE_SECRET not in text
    assert errors.MASK in text
    assert f"{errors.MASK}{errors.MASK}" not in text, "çift maskeleme"


# --- 2. redact() kapsamı -------------------------------------------------

@pytest.mark.parametrize("payload", [
    "{'token': '%s'}",
    '{"token": "%s"}',
    "{'api_key': '%s', 'user': 'x'}",
    "password='%s'",
    'api_key="%s"',
    "client_secret=%s",
    "client_secret: %s",
    "Authorization: Digest %s",
    "Authorization: Negotiate %s",
    "Authorization: NTLM %s",
    "Authorization: Basic %s",
    "Authorization: Bearer %s",
    "https://site.test/v?token=%s",
    "https://site.test/v?api_key=%s&x=1",
    "https://site.test/v?client_secret=%s",
    "https://site.test/v?token%%3D%s",
    "X-Api-Key: %s",
    "access_token=%s",
    "refresh_token=%s",
    "passphrase=%s",
    "sig=%s",
])
def test_common_secret_shapes_are_masked(payload):
    text = payload % FAKE_SECRET
    masked = errors.redact(text)
    assert FAKE_SECRET not in masked, f"maskelenmedi: {text}"


def test_authorization_line_keeps_no_credential_body():
    for scheme in ("Bearer", "Basic", "Digest", "Negotiate", "NTLM"):
        masked = errors.redact(f"Authorization: {scheme} {FAKE_SECRET}")
        assert FAKE_SECRET not in masked
        assert "Authorization" in masked


@pytest.mark.parametrize("text", [
    "Dosya bulunamadı. Dosya taşınmış veya silinmiş olabilir.",
    "Oynatıcı ayarı uygulanamadı (video ayarı desteklenmiyor).",
    "mpv property does not exist",
    "[warn] [cplayer] Bilinmeyen anahtar: deinterlace",
    "Altyazı parçası seçildi: 2 (tur)",
    "keyboard=on ve monkey=1 zararsız",
])
def test_harmless_text_is_untouched(text):
    assert errors.redact(text) == text


@pytest.mark.parametrize("text", [
    "api_key=%s",
    "{'token': '%s'}",
    "Authorization: Digest %s",
    "https://site.test/v?token=%s",
    r"C:\Users\Gerçek Kullanıcı\My Videos\film.mkv",
    r"\\server\share\Private Folder\clip.mp4",
    "Dosya bulunamadı.",
])
def test_redaction_is_idempotent(text):
    once = errors.redact(text % FAKE_SECRET if "%s" in text else text)
    assert errors.redact(once) == once


# --- 3. Yol maskeleme ----------------------------------------------------

@pytest.mark.parametrize("path", [
    USER_PATH, DRIVE_PATH, UNC_PATH,
    r"C:\Users\Gerçek Kullanıcı\Desktop\Program Klasörü\app\player.py",
])
def test_paths_leak_no_directory_user_or_share(path):
    """SÖZLEŞME DEĞİŞTİ: tırnaksız yolda dosya adı ve sonraki cümle düşer.

    Eski beklenti `kept in masked` (son dosya adı korunur) ve
    `"tekrar deneyin" in masked` idi. Tırnaksız yolun sınırı
    belirlenemediği için artık satır sonuna kadar maskelenir. Kaynak kod
    adının korunduğu tanı istisnası aşağıda TIRNAKLI biçimde ölçülür.
    """
    masked = errors.redact(f"okunamadı: {path} (tekrar deneyin)")
    for leak in PATH_LEAKS:
        assert leak not in masked, f"{leak} sızdı: {masked}"
    assert masked == f"okunamadı: {errors.MASK_PATH}"


def test_quoted_source_path_still_keeps_the_module_name():
    masked = errors.redact(
        r'File "C:\Users\Gerçek Kullanıcı\Desktop\Program Klasörü'
        r'\app\player.py", line 12')
    assert masked == f'File "{errors.MASK_PATH}\\player.py", line 12'


def test_path_without_a_safe_file_name_is_fully_masked():
    masked = errors.redact(r"D:\Private Folder\gizli klasor")
    assert "Private Folder" not in masked
    assert "gizli" not in masked


@pytest.mark.parametrize("channel", ["user_message", "details", "exception",
                                     "log"])
def test_path_contract_holds_on_every_channel(log_env, channel):
    if channel == "user_message":
        event = errors.build_error_event("Hata", f"Açılamadı: {USER_PATH}")
        errors.log_error_event(event)
        assert USER_PATH not in event.user_message
        assert FAKE_USER not in event.user_message
    elif channel == "details":
        event = errors.build_error_event("Hata", "Bir hata oluştu.",
                                         details=f"yol: {UNC_PATH}")
        errors.log_error_event(event)
        assert "server" not in event.developer_detail
    elif channel == "exception":
        try:
            raise OSError(f"açılamadı: {DRIVE_PATH}")
        except OSError as exc:
            event = errors.build_error_event("Hata", "Bir hata oluştu.",
                                             exc=exc)
        errors.log_error_event(event)
        assert "Private Folder" not in event.developer_detail
    else:
        errors.log(f"tarama: {USER_PATH}")

    text = log_env()
    for leak in PATH_LEAKS:
        assert leak not in text, f"{leak} loga sızdı"


def test_real_user_log_is_never_touched(log_env, tmp_path):
    errors.log("izolasyon")
    assert str(tmp_path) in errors.get_log_path()
    assert "MLCPlayer" in errors.get_log_path()
