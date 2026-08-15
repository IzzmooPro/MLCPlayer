"""Tek tırnaklı yollarda fail-closed + URI şema sınırı.

1. Tek tırnak sezgisi genel geçer DEĞİLDİ. `_closing_quote()` adaydan
   sonraki karaktere bakarak iç kesme işaretini dış kapanıştan ayırmaya
   çalışıyordu; boşluk içeren gerçek adlar hâlâ sızıyordu:

       'D:\\Music\\Rock 'n' Roll\\Private Folder\\film.mkv', devam
       -> "'<yol>' Roll\\Private Folder\\film.mkv', devam"
       'C:\\Users\\O' Brien\\Private Folder\\film.mkv', devam
       -> "'<yol>' Brien\\Private Folder\\film.mkv', devam"
       'D:\\Team\\Drivers' Backup\\secret folder' bitti
       -> "'<yol>' Backup\\secret folder' bitti"

   `'` Windows dosya ve klasör adında GEÇERLİDİR; serbest metinde hangi
   tek tırnağın dış kapanış olduğu genel olarak belirlenemez. Yeni sezgi
   eklenmez: tek tırnaklı yol her zaman satır sonuna kadar maskelenir.
   `"` dosya adında geçersiz olduğu için çift tırnak davranışı DEĞİŞMEZ.

2. `file://` bileşik şema soneki olarak da eşleşiyordu
   (`custom-file://settings/value` -> `custom-<yol>`). RFC şema adı
   ALPHA / DIGIT / `+` / `-` / `.` içerir; bu karakterlerden sonra gelen
   `file://` bağımsız şema başlangıcı DEĞİLDİR.

Bütün değerler sentetiktir; testler geçici log dizini kullanır.
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

# (girdi, beklenen) — tek tırnakta AÇILIŞ tırnağı ve öncesi korunur,
# yolun başlangıcından satır sonuna kadar her şey maskelenir.
SINGLE_QUOTE_CASES = [
    (r"Hata: 'D:\Music\Rock 'n' Roll\film.mkv', devam", "Hata: '<yol>"),
    (r"'C:\Users\O'Brien\Private Folder\film.mkv', tekrar", "'<yol>"),
    (r"'C:\Users\O' Brien\Private Folder\film.mkv', devam", "'<yol>"),
    (r"'D:\Team\Drivers' Backup\secret folder' bitti", "'<yol>"),
    (r"'D:\Murat'ın Videoları\gizli klasor' sonra", "'<yol>"),
    (r"'D:\A'B'C'D\cok kesme isareti\film.mkv' son", "'<yol>"),
    (r"'C:\Users\Gercek Kullanici\My Videos\film'", "'<yol>"),
]
SINGLE_QUOTE_LEAKS = ("Music", "Rock", "Roll", "film.mkv", "Brien",
                      "Private Folder", "Team", "Drivers", "Backup",
                      "secret", "folder", "Murat", "Videoları", "gizli",
                      "klasor", "kesme", "isareti", "Gercek Kullanici",
                      "My Videos")

# Bağımsız şema başlangıcı OLMAYAN biçimler.
COMPOUND_SCHEMES = [
    "custom-file://settings/value",
    "profile-file://settings/value",
    "x.file://settings/value",
    "abc+file://settings/value",
    "myfile://settings/value",
    "9file://settings/value",
]
REAL_FILE_URIS = [
    "file://server/share/Private Folder/film.mkv",
    "FILE://server/share/Private Folder/film.mkv",
    "file:///C:/Users/Gercek Kullanici/film.mkv",
]


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


# --- 1. Tek tırnak: her zaman fail-closed -------------------------------

@pytest.mark.parametrize("raw,expected", SINGLE_QUOTE_CASES)
def test_single_quoted_paths_are_always_masked_to_end_of_line(raw, expected):
    masked = errors.redact(raw)
    assert_no(masked, SINGLE_QUOTE_LEAKS)
    assert masked == expected, masked


def test_single_quote_does_not_try_to_keep_the_following_sentence():
    """SÖZLEŞME: tek tırnakta sonraki cümle KORUNMAZ (fail-closed)."""
    masked = errors.redact(r"Hata: 'D:\Private\film.mkv' tekrar deneyin")
    assert masked == "Hata: '<yol>"
    assert "tekrar deneyin" not in masked


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_single_quote_fail_closed_never_eats_the_next_record(newline):
    text = (f"[ERROR] 'D:\\Team\\Drivers' Backup\\secret folder' bitti"
            f"{newline}[INFO] sonraki")
    masked = errors.redact(text)
    assert_no(masked, SINGLE_QUOTE_LEAKS)
    assert masked == f"[ERROR] '<yol>{newline}[INFO] sonraki"


def test_single_quoted_source_file_name_is_not_kept():
    """Tanı istisnası YALNIZ çift tırnaklı traceback yolundadır."""
    masked = errors.redact(r"File 'C:\Users\X\proje\app\player.py', line 12")
    assert "player.py" not in masked
    assert masked == "File '<yol>"


# --- Çift tırnak davranışı değişmedi ------------------------------------

def test_double_quoted_behaviour_is_unchanged():
    assert errors.redact(r'"D:\Private\film.mkv", tekrar') \
        == '"<yol>", tekrar'
    assert errors.redact(r'File "C:\Users\X\proje\app\player.py", line 12') \
        == r'File "<yol>\player.py", line 12'
    assert errors.redact(r'"D:\a\bir.mkv" ve "E:\b\iki.mkv" bitti') \
        == '"<yol>" ve "<yol>" bitti'


def test_double_quoted_path_with_an_apostrophe_inside_still_works():
    masked = errors.redact(
        r'''"C:\Users\O'Brien\Private\film.mkv", devam''')
    assert_no(masked, SINGLE_QUOTE_LEAKS)
    assert masked == '"<yol>", devam'


# --- 2. URI şema sınırı --------------------------------------------------

@pytest.mark.parametrize("text", COMPOUND_SCHEMES)
def test_compound_schemes_are_not_file_uris(text):
    assert errors.redact(text) == text


@pytest.mark.parametrize("text", [
    "https://example.test/video",
    "http://example.test/video",
    "ftp://example.test/file",
    "profile://settings",
    "file.py:12",
    "Dosya adı file: olarak kaydedildi",
])
def test_known_negatives_stay_untouched(text):
    assert errors.redact(text) == text


@pytest.mark.parametrize("uri", REAL_FILE_URIS)
def test_standalone_file_uris_are_still_masked(uri):
    assert errors.redact(uri) == errors.MASK_PATH
    assert errors.redact(f"acilamadi: {uri} devam") \
        == f"acilamadi: {errors.MASK_PATH}"
    assert errors.redact(f'acilamadi: "{uri}", devam') \
        == f'acilamadi: "{errors.MASK_PATH}", devam'


@pytest.mark.parametrize("prefix", ["", " ", "(", "[", ",", ";", "\t"])
def test_file_uri_after_whitespace_or_punctuation_is_masked(prefix):
    masked = errors.redact(f"{prefix}file://server/share/film.mkv")
    assert masked == f"{prefix}{errors.MASK_PATH}"


def test_single_quoted_file_uri_fails_closed():
    masked = errors.redact("acilamadi: 'file://server/share/film.mkv' devam")
    assert masked == "acilamadi: '<yol>"


# --- 3. Kanallar ---------------------------------------------------------

@pytest.mark.parametrize("channel", ["user_message", "details", "exception",
                                     "log", "mpv"])
def test_contract_holds_on_every_channel(log_env, capsys, channel):
    payload = r"'D:\Music\Rock 'n' Roll\Private Folder\film.mkv' devam"
    if channel == "user_message":
        event = errors.build_error_event("Hata", f"Acilamadi: {payload}")
        errors.log_error_event(event)
        assert_no(event.user_message, SINGLE_QUOTE_LEAKS)
    elif channel == "details":
        event = errors.build_error_event("Hata", "Hata olustu.",
                                         details=f"yol: {payload}")
        errors.log_error_event(event)
        assert_no(event.developer_detail, SINGLE_QUOTE_LEAKS)
    elif channel == "exception":
        try:
            raise OSError(f"acilamadi: {payload}")
        except OSError as exc:
            event = errors.build_error_event("Hata", "Hata olustu.", exc=exc)
        errors.log_error_event(event)
        assert_no(event.developer_detail, SINGLE_QUOTE_LEAKS)
        # Çift tırnaklı traceback satırı tanı için korunmaya devam eder.
        assert "test_error_path_single_quote_regressions.py" in \
            event.developer_detail
    elif channel == "log":
        errors.log(f"tarama: {payload}")
    else:
        from app.player import MPVPlayer

        MPVPlayer.log_handler(object(), "warn", "cplayer", f"dosya: {payload}")
        assert_no(capsys.readouterr().out, SINGLE_QUOTE_LEAKS)

    assert_no(log_env(), SINGLE_QUOTE_LEAKS)


# --- 4. Korunan özellikler ----------------------------------------------

@pytest.mark.parametrize("raw", [case for case, _ in SINGLE_QUOTE_CASES] + [
    "custom-file://settings/value",
    "file://server/share/Private Folder/film.mkv",
    r'"D:\Private\film.mkv", tekrar',
    "Hata: D:\\Private\\gizli klasor\r\n[INFO] sonraki",
    "Dosya bulunamadı.",
])
def test_masking_is_idempotent(raw):
    once = errors.redact(raw)
    assert errors.redact(once) == once


def test_secret_and_authorization_masking_still_work():
    masked = errors.redact(
        "api_key=SENTETIK123 Authorization: Digest SENTETIK456")
    assert "SENTETIK123" not in masked and "SENTETIK456" not in masked
    assert "api_key" in masked and "Authorization" in masked


def test_line_endings_are_still_preserved():
    text = ("[A] 'D:\\Private\\bir klasor' x\r\n[B] normal satir\n"
            "[C] 'E:\\Private\\iki klasor' y\r[D] son satir")
    masked = errors.redact(text)
    assert masked == ("[A] '<yol>\r\n[B] normal satir\n"
                      "[C] '<yol>\r[D] son satir")


def test_scanner_stays_fast_on_a_100kb_input():
    # Bileşik şema AYRI satırdadır: tek tırnaklı yol kendi satırının
    # sonuna kadar maskelendiği için aynı satırda kalsaydı o da düşerdi.
    line = (r"Hata: 'D:\Music\Rock 'n' Roll\Private Folder\film.mkv', devam"
            "\r\ncustom-file://settings/value\r\n")
    payload = line * 1200
    assert len(payload) > 100_000
    started = time.time()
    masked = errors.redact(payload)
    elapsed = time.time() - started
    assert elapsed < 3.0, f"redact cok yavas: {elapsed:.2f}s"
    assert_no(masked, ("Rock", "Roll", "Private Folder", "film.mkv"))
    assert "custom-file://settings/value" in masked
