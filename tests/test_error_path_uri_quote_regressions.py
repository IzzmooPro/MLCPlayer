# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yol tarayıcısında kalan üç sınır.

1. Kesme işaretli yollar kısmen sızıyordu. `'` Windows dosya adında
   GEÇERLİDİR; `line.find("'", start)` ilk tırnağı kapanış sanıyordu:

       'C:\\Users\\O'Brien\\Private Folder\\film.mkv', tekrar deneyin
       -> "'<yol>'Brien\\Private Folder\\film.mkv', tekrar deneyin"

   (`"` Windows dosya adında GEÇERSİZDİR; çift tırnakta ilk eşleşme
   her zaman doğru kapanıştır ve davranışı değişmemelidir.)

2. `file://` URI biçimleri hiç maskelenmiyordu.

3. `_mask_paths()` satırları `split("\\n")` ile ayırdığı için `\\r\\n`
   ve tek `\\r` satır sonları `\\n` hâline geliyordu.

Bütün değerler sentetiktir; testler geçici log dizini kullanır.
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

# SÖZLEŞME GÜNCELLENDİ: kapanış tırnağını bulmaya çalışan sezgi
# kaldırıldı. `'` Windows dosya adında geçerli olduğu için hangi
# tırnağın dış kapanış olduğu belirlenemez (`Rock 'n' Roll`,
# `Drivers' Backup`); tek tırnaklı yol artık satır sonuna kadar
# fail-closed maskelenir. Ayrıntı:
# `tests/test_error_path_single_quote_regressions.py`.
APOSTROPHE_CASES = [
    (r"'C:\Users\O'Brien\Private Folder\film.mkv', tekrar deneyin", "'<yol>"),
    (r"'D:\Murat'ın Videoları\gizli klasor' sonra", "'<yol>"),
    (r"'D:\John's Files\secret folder' bitti", "'<yol>"),
]
# NOT: `ın` gibi çok kısa parçalar bilerek listede yok — log başlığındaki
# "Ayrıntı" gibi zararsız Türkçe kelimelerle çakışıp sahte hata üretirdi.
APOSTROPHE_LEAKS = ("Brien", "Private Folder", "film.mkv", "Murat",
                    "Videoları", "gizli", "klasor", "John", "Files",
                    "secret", "folder")

FILE_URIS = [
    "file://server/share/Private Folder/film.mkv",
    "FILE://server/share/Private Folder/film.mkv",
    "file:///C:/Users/Gercek Kullanici/Private Folder/film.mkv",
    "file://localhost/C:/Users/Gercek Kullanici/Private Folder/film.mkv",
    "file:///C:/Users/Gercek%20Kullanici/Private%20Folder/film.mkv",
    "File://server/share/Private%20Folder/film.mkv",
]
URI_LEAKS = ("server", "share", "Private", "Folder", "film.mkv",
             "Gercek", "Kullanici", "localhost", "%20")


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


def assert_no(text, words):
    scanned = text.replace(errors.MASK, "").replace(errors.MASK_PATH, "")
    for word in words:
        assert word not in scanned, f"{word} acikta kaldi: {text!r}"


# --- 1. Kesme işaretli yollar -------------------------------------------

@pytest.mark.parametrize("raw,expected", APOSTROPHE_CASES)
def test_single_quoted_path_with_an_apostrophe_fails_closed(raw, expected):
    """Eski adı `test_apostrophe_inside_a_quoted_path_is_not_a_closing_quote`.

    Eski beklenti kapanış tırnağının bulunup sonraki cümlenin korunması
    idi; sezgi `Rock 'n' Roll` ve `Drivers' Backup` gibi geçerli adlarda
    hâlâ yol sızdırıyordu. Artık tek tırnaklı yol satır sonuna kadar
    maskelenir.
    """
    masked = errors.redact(raw)
    assert_no(masked, APOSTROPHE_LEAKS)
    assert masked == expected, masked


def test_apostrophe_path_without_a_reliable_closing_quote_fails_closed():
    """Güvenilir kapanış yoksa satır sonuna kadar maskelenir."""
    masked = errors.redact(r"'C:\Users\O'Brien\Private Folder\film.mkv")
    assert_no(masked, APOSTROPHE_LEAKS)
    assert masked.endswith(errors.MASK_PATH), masked


def test_double_quoted_behaviour_is_unchanged():
    """`\"` Windows dosya adında geçersizdir; ilk eşleşme doğru kapanıştır."""
    masked = errors.redact(r'Hata: "D:\Private\gizli klasor", tekrar deneyin')
    assert masked == 'Hata: "<yol>", tekrar deneyin'
    masked = errors.redact(r'File "C:\Users\X\proje\app\player.py", line 12')
    assert masked == r'File "<yol>\player.py", line 12'


def test_two_quoted_paths_on_one_line_stay_separate():
    masked = errors.redact(r'"D:\a\bir.mkv" ve "E:\b\iki.mkv" bitti')
    assert masked == '"<yol>" ve "<yol>" bitti'


# --- 2. file:// URI biçimleri -------------------------------------------

@pytest.mark.parametrize("uri", FILE_URIS)
def test_file_uris_are_masked_unquoted(uri):
    masked = errors.redact(f"acilamadi: {uri} tekrar deneyin")
    assert_no(masked, URI_LEAKS)
    assert masked == f"acilamadi: {errors.MASK_PATH}", masked


@pytest.mark.parametrize("uri", FILE_URIS)
def test_quoted_file_uris_keep_the_following_sentence(uri):
    masked = errors.redact(f'acilamadi: "{uri}", tekrar deneyin')
    assert_no(masked, URI_LEAKS)
    assert masked == f'acilamadi: "{errors.MASK_PATH}", tekrar deneyin'


@pytest.mark.parametrize("harmless", [
    "https://example.test/video",
    "http://example.test/video",
    "ftp://example.test/file",
    "file.py:12",
    "profile://settings",
    "Dosya adı file: olarak kaydedildi",
    "yeni file olusturuldu",
])
def test_non_file_uris_are_untouched(harmless):
    assert errors.redact(harmless) == harmless


# --- 3. Satır sonları birebir korunur -----------------------------------

@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_line_endings_are_preserved(newline):
    text = f"Hata: D:\\Private\\gizli klasor{newline}[INFO] sonraki"
    masked = errors.redact(text)
    assert masked == f"Hata: {errors.MASK_PATH}{newline}[INFO] sonraki"


def test_mixed_line_endings_are_preserved():
    text = ("[A] D:\\Private\\bir klasor\r\n"
            "[B] normal satir\n"
            "[C] E:\\Private\\iki klasor\r"
            "[D] son satir")
    masked = errors.redact(text)
    assert masked == (f"[A] {errors.MASK_PATH}\r\n"
                      "[B] normal satir\n"
                      f"[C] {errors.MASK_PATH}\r"
                      "[D] son satir")


@pytest.mark.parametrize("suffix", ["", "\n", "\r\n", "\r"])
def test_trailing_newline_is_preserved(suffix):
    text = f"Hata: D:\\Private\\gizli klasor{suffix}"
    assert errors.redact(text) == f"Hata: {errors.MASK_PATH}{suffix}"


def test_harmless_text_keeps_its_line_endings():
    text = "birinci\r\nikinci\rucuncu\ndorduncu"
    assert errors.redact(text) == text


# --- 4. Kanallar ---------------------------------------------------------

@pytest.mark.parametrize("channel", ["user_message", "details", "exception",
                                     "log", "mpv"])
def test_contract_holds_on_every_channel(log_env, capsys, channel):
    payload = (r"'C:\Users\O'Brien\Private Folder\film.mkv'"
               " ve file://server/share/Private Folder/film.mkv")
    words = APOSTROPHE_LEAKS + URI_LEAKS
    if channel == "user_message":
        event = errors.build_error_event("Hata", f"Acilamadi: {payload}")
        errors.log_error_event(event)
        assert_no(event.user_message, words)
    elif channel == "details":
        event = errors.build_error_event("Hata", "Hata olustu.",
                                         details=f"yol: {payload}")
        errors.log_error_event(event)
        assert_no(event.developer_detail, words)
    elif channel == "exception":
        try:
            raise OSError(f"acilamadi: {payload}")
        except OSError as exc:
            event = errors.build_error_event("Hata", "Hata olustu.", exc=exc)
        errors.log_error_event(event)
        assert_no(event.developer_detail, words)
        assert "test_error_path_uri_quote_regressions.py" in \
            event.developer_detail
    elif channel == "log":
        errors.log(f"tarama: {payload}")
    else:
        from app.player import MPVPlayer

        MPVPlayer.log_handler(object(), "warn", "cplayer", f"dosya: {payload}")
        assert_no(capsys.readouterr().out, words)

    assert_no(log_env(), words)


# --- 5. Korunan özellikler ----------------------------------------------

@pytest.mark.parametrize("raw", [
    r"'C:\Users\O'Brien\Private Folder\film.mkv', tekrar deneyin",
    "file://server/share/Private Folder/film.mkv",
    'acilamadi: "file:///C:/Users/X/film.mkv", devam',
    "Hata: D:\\Private\\gizli klasor\r\n[INFO] sonraki",
    "Dosya bulunamadı.",
])
def test_masking_is_idempotent(raw):
    once = errors.redact(raw)
    assert errors.redact(once) == once


def test_secret_and_authorization_masking_still_work():
    masked = errors.redact(
        'api_key=SENTETIK123 Authorization: Digest SENTETIK456')
    assert "SENTETIK123" not in masked and "SENTETIK456" not in masked
    assert "api_key" in masked and "Authorization" in masked


def test_unquoted_path_still_does_not_swallow_the_next_line():
    text = ("[ERROR] acilamadi: D:\\Private\\gizli klasor devam\r\n"
            "[INFO] Altyazı parçası seçildi: 2 (tur)\r\n")
    masked = errors.redact(text)
    assert "Altyazı parçası seçildi: 2 (tur)" in masked
    assert masked.count("[INFO]") == 1
    assert masked.endswith("\r\n")


def test_scanner_stays_fast_on_a_100kb_input():
    line = (r"Hata: 'C:\Users\O'Brien\Private Folder\film.mkv', tekrar "
            "deneyin. file://server/share/Private Folder/film.mkv\r\n")
    payload = line * 1200
    assert len(payload) > 100_000
    started = time.time()
    masked = errors.redact(payload)
    elapsed = time.time() - started
    assert elapsed < 3.0, f"redact cok yavas: {elapsed:.2f}s"
    assert_no(masked, ("Brien", "Private Folder", "film.mkv", "server"))
