"""Bağımsız doğrulamada bulunan ÜÇ EK açık.

1. `MPVPlayer.log_handler` libmpv mesajını `print()` ile HAM olarak
   stdout'a yazıyordu; dosya logu maskeliyken bile konsoldan
   çalıştırmada veya stdout yönlendirildiğinde token, `Authorization`
   değeri ve tam medya yolu sızıyordu.
2. Boşluk içeren son dosya adı KISMEN sızıyordu:
   `D:\\Private Folder\\Musteri Sozlesmesi.mp4` -> `<yol> Sozlesmesi.mp4`
3. Karşı tür tırnak içeren gizli değerler hiç maskelenmiyordu:
   `password="abc'def"` -> değişmeden kalıyordu.

Bütün gizli değerler SENTETİKTİR ve testler geçici log dizini kullanır.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

FAKE_SECRET = "sentetik-sir"
AUTH_LINE = "Authorization: Digest sentetik-sir"
TOKEN_URL = "https://cdn.test/v.m3u8?token=sentetik-sir"
SPACED_DRIVE = r"D:\Private Folder\Musteri Sozlesmesi.mp4"
SPACED_USER = r"C:\Users\Gercek Kullanici\My Videos\Ozel Tatil Videosu.mkv"
SPACED_UNC = r"\\server\share\Private Folder\Musteri Sozlesmesi.mp4"
# Yolun HİÇBİR parçası kalmamalı; kısmi dosya adı da sızıntıdır.
SPACED_LEAKS = ("Musteri", "Sozlesmesi", "Ozel", "Tatil", "Videosu",
                "Private Folder", "My Videos", "Gercek Kullanici",
                "server", "share", FAKE_SECRET)

MIXED_A = "AAA111'BBB222"
MIXED_B = 'AAA111"BBB222'
MIXED_LEAKS = ("AAA111", "BBB222")


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


# --- 1. Ham MPV konsol çıktısı ------------------------------------------

def test_mpv_log_handler_console_output_is_masked(log_env, capsys):
    from app.player import MPVPlayer

    message = f"stream: {TOKEN_URL} {AUTH_LINE} file={SPACED_DRIVE}"
    MPVPlayer.log_handler(object(), "error", "ffmpeg", message)

    stdout = capsys.readouterr().out
    text = log_env()
    assert "[ffmpeg]" in stdout, "libmpv tanısı konsola hiç basılmadı"
    for leak in (FAKE_SECRET, "Authorization: Digest", "Private Folder",
                 "Musteri", "Sozlesmesi"):
        assert leak not in stdout, f"stdout'a sızdı: {leak}"
        assert leak not in text, f"log dosyasına sızdı: {leak}"


@pytest.mark.parametrize("level,printed", [("warn", True), ("error", True),
                                           ("fatal", True), ("info", False),
                                           ("v", False)])
def test_mpv_log_handler_keeps_its_level_policy(log_env, capsys, level,
                                                printed):
    from app.player import MPVPlayer

    MPVPlayer.log_handler(object(), level, "cplayer", "durum mesaji")
    stdout = capsys.readouterr().out
    assert ("cplayer" in stdout) is printed
    assert ("cplayer" in log_env()) is printed


def test_mpv_log_handler_writes_one_record_without_double_masking(log_env,
                                                                  capsys):
    from app.player import MPVPlayer

    MPVPlayer.log_handler(object(), "error", "ffmpeg",
                          f"hata: api_key={FAKE_SECRET}")
    capsys.readouterr()
    lines = [line for line in log_env().splitlines() if "[ffmpeg]" in line]
    assert len(lines) == 1, f"cift kayit: {lines}"
    assert f"{errors.MASK}{errors.MASK}" not in lines[0]


# --- 2. Boşluk içeren son dosya adı -------------------------------------

@pytest.mark.parametrize("path", [SPACED_DRIVE, SPACED_USER, SPACED_UNC])
def test_spaced_file_names_never_leak_partially(path):
    masked = errors.redact(path)
    for leak in SPACED_LEAKS:
        assert leak not in masked, f"{leak} acikta kaldi: {masked!r}"


def test_unquoted_spaced_path_is_masked_to_end_of_line():
    """SÖZLEŞME DEĞİŞTİ: tırnaksız yolda sonraki cümle KORUNMAZ.

    Eski adı `test_spaced_path_does_not_eat_the_following_sentence` idi
    ve `(tekrar deneyin)` ifadesinin korunmasını bekliyordu. Boşluk ve
    parantez Windows dosya adında geçerli olduğu için tırnaksız yolun
    nerede bittiği belirlenemez; gizlilik lehine fail-closed davranılır.
    Yolun ÖNÜNDEKİ metin korunur.
    """
    masked = errors.redact(f"Açılamadı: {SPACED_DRIVE} (tekrar deneyin)")
    for leak in SPACED_LEAKS:
        assert leak not in masked, f"{leak} acikta kaldi: {masked!r}"
    assert masked == f"Açılamadı: {errors.MASK_PATH}"


def test_quoted_spaced_path_still_keeps_the_following_sentence():
    """Sınırın kesin olduğu TIRNAKLI biçimde cümle korunmaya devam eder."""
    masked = errors.redact(f'Açılamadı: "{SPACED_DRIVE}" (tekrar deneyin)')
    for leak in SPACED_LEAKS:
        assert leak not in masked, f"{leak} acikta kaldi: {masked!r}"
    assert masked == f'Açılamadı: "{errors.MASK_PATH}" (tekrar deneyin)'


@pytest.mark.parametrize("path", [SPACED_DRIVE, SPACED_USER, SPACED_UNC])
def test_spaced_path_masking_is_idempotent(path):
    once = errors.redact(f"yol: {path} bitti")
    assert errors.redact(once) == once
    # `bitti` artık tırnaksız yolla birlikte düşer (fail-closed); aynı
    # metin tırnaklı verildiğinde korunur.
    assert once == f"yol: {errors.MASK_PATH}"
    quoted = errors.redact(f'yol: "{path}" bitti')
    assert quoted == f'yol: "{errors.MASK_PATH}" bitti'
    assert errors.redact(quoted) == quoted


@pytest.mark.parametrize("channel", ["user_message", "details", "exception",
                                     "log", "mpv"])
def test_spaced_path_contract_on_every_channel(log_env, capsys, channel):
    if channel == "user_message":
        event = errors.build_error_event("Hata", f"Açılamadı: {SPACED_DRIVE}")
        errors.log_error_event(event)
        for leak in SPACED_LEAKS:
            assert leak not in event.user_message
    elif channel == "details":
        event = errors.build_error_event("Hata", "Bir hata oluştu.",
                                         details=f"yol: {SPACED_UNC}")
        errors.log_error_event(event)
        for leak in SPACED_LEAKS:
            assert leak not in event.developer_detail
    elif channel == "exception":
        try:
            raise OSError(f"acilamadi: {SPACED_USER}")
        except OSError as exc:
            event = errors.build_error_event("Hata", "Bir hata oluştu.",
                                             exc=exc)
        errors.log_error_event(event)
        for leak in SPACED_LEAKS:
            assert leak not in event.developer_detail
    elif channel == "log":
        errors.log(f"tarama: {SPACED_DRIVE}")
    else:
        from app.player import MPVPlayer

        MPVPlayer.log_handler(object(), "warn", "cplayer",
                              f"dosya: {SPACED_UNC}")
        stdout = capsys.readouterr().out
        for leak in SPACED_LEAKS:
            assert leak not in stdout

    text = log_env()
    for leak in SPACED_LEAKS:
        assert leak not in text, f"{leak} loga sizdi"


def test_module_file_names_are_still_kept_for_diagnosis():
    """Boşluksuz dosya adı tanı için korunmaya devam etmeli."""
    masked = errors.redact(r'File "C:\Users\X\Desktop\proje\app\player.py"')
    assert "player.py" in masked
    assert "Desktop" not in masked and "proje" not in masked


# --- 3. Karşı tür tırnak içeren gizli değerler --------------------------

@pytest.mark.parametrize("payload", [
    'password="' + MIXED_A + '"',
    "password='" + MIXED_B + "'",
    '{"token": "' + MIXED_A + '"}',
    "{'token': '" + MIXED_B + "'}",
    '{"api_key": "AAA111\\"BBB222"}',
    "{'client_secret': 'AAA111\\'BBB222'}",
    'password="AAA111\\"BBB222"',
    "api_key='" + MIXED_B + "' sonrasi",
])
def test_values_with_the_opposite_quote_are_masked(payload):
    masked = errors.redact(payload)
    for leak in MIXED_LEAKS:
        assert leak not in masked, f"{leak} acikta kaldi: {masked!r}"
    assert errors.MASK in masked


def test_masking_a_quoted_value_does_not_swallow_the_rest_of_the_line():
    text = ('password="' + MIXED_A + '" ve sonra: '
            'kullanici="Ahmet" islem=devam SONMARKER')
    masked = errors.redact(text)
    for leak in MIXED_LEAKS:
        assert leak not in masked
    assert "SONMARKER" in masked
    assert "kullanici=" in masked and "Ahmet" in masked
    assert "islem=devam" in masked


def test_masking_a_quoted_value_does_not_swallow_the_next_record():
    text = ('[ERROR] password="' + MIXED_A + '"\n'
            '[INFO] Altyazı parçası seçildi: 2 (tur)\n')
    masked = errors.redact(text)
    for leak in MIXED_LEAKS:
        assert leak not in masked
    assert "Altyazı parçası seçildi: 2 (tur)" in masked
    assert masked.count("[INFO]") == 1


@pytest.mark.parametrize("harmless", [
    'kullanici="Ahmet" dosya="film.mkv"',
    "mesaj='Dosya bulunamadı' kod=2",
    '{"user": "x", "count": 3}',
])
def test_harmless_quoted_text_is_untouched(harmless):
    assert errors.redact(harmless) == harmless


@pytest.mark.parametrize("payload", [
    'password="' + MIXED_A + '"',
    "{'token': '" + MIXED_B + "'}",
])
def test_mixed_quote_masking_is_idempotent(payload):
    once = errors.redact(payload)
    assert errors.redact(once) == once


@pytest.mark.parametrize("payload", [
    'password="' + MIXED_A + '"',
    "{'token': '" + MIXED_B + "'}",
])
def test_mixed_quote_values_are_masked_through_the_log_boundary(log_env,
                                                                payload):
    errors.log(f"ayar: {payload}")
    text = log_env()
    for leak in MIXED_LEAKS:
        assert leak not in text, f"{leak} loga sizdi: {text!r}"
