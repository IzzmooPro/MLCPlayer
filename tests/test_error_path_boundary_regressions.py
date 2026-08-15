"""Yol maskelemesinde kalan iki kaçış: noktalama sınırı ve kelime sınırı.

Doğrulanan kaçışlar:

    redact(r"D:\\Private\\Musteri Sozlesmesi.mp4, tekrar deneyin")
    -> "<yol> Sozlesmesi.mp4, tekrar deneyin"

    redact(r"D:\\Private\\Bir Iki Uc Dort Bes Alti Yedi Sekiz Video.mkv")
    -> "<yol> Iki Uc Dort Bes Alti Yedi Sekiz Video.mkv"

Sebep: `_PATH_FINAL` boşluklu dosya adını `{0,6}` ile sınırlıyor ve
uzantıdan sonraki `,` `;` `)` `]` işaretlerini güvenli sınır saymıyordu;
kalıp yolun yalnız ilk kelimesini eşleyip adın kalanını açıkta bırakıyor.

Bütün değerler sentetiktir; testler geçici log dizini kullanır.
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

# Noktalama sınırı örnekleri.
PUNCT_BASE = r"D:\Private\Musteri Sozlesmesi.mp4"
PUNCT_CASES = [
    PUNCT_BASE + ", tekrar deneyin",
    PUNCT_BASE + "; tekrar deneyin",
    PUNCT_BASE + ") tekrar deneyin",
    PUNCT_BASE + "] tekrar deneyin",
    "Açılamadı: " + PUNCT_BASE + ", tekrar deneyin.",
]
# Sabit kelime sınırını aşan uzun dosya adları.
LONG_DRIVE = r"D:\Private\Bir Iki Uc Dort Bes Alti Yedi Sekiz Video.mkv"
LONG_USER = (r"C:\Users\X\My Videos"
             r"\Bir Iki Uc Dort Bes Alti Yedi Sekiz Dokuz Video.mp4")
LONG_UNC = (r"\\server\share\Private Folder"
            r"\Bir Iki Uc Dort Bes Alti Yedi Sekiz Video.mkv")
LONG_CASES = [LONG_DRIVE, LONG_USER, LONG_UNC]

# Maskelemeden sonra HİÇBİRİ kalmamalı.
NAME_WORDS = ("Musteri", "Sozlesmesi", "Bir", "Iki", "Uc", "Dort", "Bes",
              "Alti", "Yedi", "Sekiz", "Dokuz", "Video", "Private",
              "My Videos", "server", "share")


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


def assert_no_path_words(text):
    for word in NAME_WORDS:
        assert word not in text, f"{word} acikta kaldi: {text!r}"
    assert errors.MASK_PATH in text, f"yol isareti yok: {text!r}"


# --- 1. Uzantıdan sonra noktalama ---------------------------------------

@pytest.mark.parametrize("text", PUNCT_CASES)
def test_punctuation_after_the_extension_is_a_safe_boundary(text):
    masked = errors.redact(text)
    assert_no_path_words(masked)


def test_unquoted_path_with_punctuation_is_masked_to_end_of_line():
    """SÖZLEŞME DEĞİŞTİ: tırnaksız yolda noktalama sınır SAYILMAZ.

    Eski beklenti "yolun ardından gelen `, tekrar deneyin` korunur"
    idi. Virgül, noktalı virgül ve parantez Windows dosya adında
    geçerli olduğu için bu beklenti güvenli değildi ve `gizli klasor`
    gibi uzantısız adlarda kaçak bırakıyordu. Artık tırnaksız yol
    fail-closed biçimde satır sonuna kadar maskelenir; yolun ÖNÜNDEKİ
    metin korunur. Sonraki cümlenin korunması yalnız TIRNAKLI yollarda
    garanti edilir (bkz.
    `tests/test_error_path_scanner_regressions.py`).
    """
    assert errors.redact(PUNCT_BASE + ", tekrar deneyin") == errors.MASK_PATH
    assert errors.redact("Açılamadı: " + PUNCT_BASE + ", tekrar deneyin.") \
        == f"Açılamadı: {errors.MASK_PATH}"


@pytest.mark.parametrize("mark", [",", ";", ")", "]", "}", ".", "!", "?"])
def test_closing_marks_do_not_stop_an_unquoted_path(mark):
    """Tırnaksız yolda hiçbir noktalama güvenli sınır değildir."""
    assert errors.redact(f"{PUNCT_BASE}{mark} devam") == errors.MASK_PATH


@pytest.mark.parametrize("mark", [",", ";", ")", "]", "}", ".", "!", "?"])
def test_closing_marks_survive_when_the_path_is_quoted(mark):
    """TIRNAKLI yolda sınır kesindir; noktalama ve cümle korunur."""
    masked = errors.redact(f'"{PUNCT_BASE}"{mark} devam')
    assert masked == f'"{errors.MASK_PATH}"{mark} devam'


# --- 2. Uzun (çok kelimeli) dosya adları --------------------------------

@pytest.mark.parametrize("path", LONG_CASES)
def test_long_multi_word_file_names_are_fully_masked(path):
    assert_no_path_words(errors.redact(path))


def test_no_fixed_word_limit_remains():
    """Kelime sayısına bağlı sabit üst sınır OLMAMALI.

    Beklenen çıktı fail-closed sözleşmeyle güncellendi: tırnaksız yolda
    ad kaç kelime olursa olsun satır sonuna kadar maskelenir. Tırnaklı
    biçimde ise ad tamamen maskelenip sonraki metin korunur.
    """
    for count in (2, 5, 8, 12, 20, 40):
        name = " ".join(f"Kelime{index}" for index in range(count))
        assert errors.redact(rf"D:\Private\{name}.mkv" + " (devam)") \
            == errors.MASK_PATH, count
        assert errors.redact(rf'"D:\Private\{name}.mkv" (devam)') \
            == f'"{errors.MASK_PATH}" (devam)', count


@pytest.mark.parametrize("path", LONG_CASES + PUNCT_CASES)
def test_path_masking_stays_idempotent(path):
    once = errors.redact(path)
    assert errors.redact(once) == once


# --- 3. Korunması gerekenler --------------------------------------------

def test_module_file_names_are_still_kept_for_diagnosis():
    masked = errors.redact(r'File "C:\Users\X\proje\app\player.py", line 12')
    assert "player.py" in masked
    assert "proje" not in masked
    assert ", line 12" in masked


@pytest.mark.parametrize("harmless", [
    "Dosya bulunamadı. Dosya taşınmış veya silinmiş olabilir.",
    "Altyazı parçası seçildi: 2 (tur), devam ediliyor.",
    "Oynatma hızı 1.5x olarak ayarlandı; iyi seyirler.",
    "[warn] [cplayer] Bilinmeyen anahtar: deinterlace",
])
def test_harmless_sentences_are_untouched(harmless):
    assert errors.redact(harmless) == harmless


def test_redaction_stays_fast_on_long_input():
    """Uzun girdide belirgin performans sorunu olmamalı."""
    payload = ((r"D:\Private\Bir Iki Uc Dort Bes Video.mkv, tekrar deneyin. ")
               * 400) + " ".join(f"kelime{index}" for index in range(4000))
    started = time.time()
    masked = errors.redact(payload)
    elapsed = time.time() - started
    assert elapsed < 3.0, f"redact cok yavas: {elapsed:.2f}s"
    for word in ("Musteri", "Sozlesmesi", "Private"):
        assert word not in masked


# --- 4. Bütün kanallar ---------------------------------------------------

@pytest.mark.parametrize("channel", ["user_message", "details", "exception",
                                     "log", "mpv"])
def test_boundary_contract_on_every_channel(log_env, capsys, channel):
    if channel == "user_message":
        event = errors.build_error_event(
            "Hata", f"Açılamadı: {LONG_DRIVE}, tekrar deneyin")
        errors.log_error_event(event)
        assert_no_path_words(event.user_message)
        # SÖZLEŞME DEĞİŞTİ: tırnaksız yol satır sonuna kadar maskelendiği
        # için ardından gelen açıklama da düşer; yolun ÖNÜNDEKİ metin
        # korunur.
        assert event.user_message == f"Açılamadı: {errors.MASK_PATH}"
        assert "tekrar deneyin" not in event.user_message
    elif channel == "details":
        event = errors.build_error_event("Hata", "Hata olustu.",
                                         details=f"yol: {LONG_UNC};")
        errors.log_error_event(event)
        assert_no_path_words(event.developer_detail)
    elif channel == "exception":
        try:
            raise OSError(f"acilamadi: {LONG_USER})")
        except OSError as exc:
            event = errors.build_error_event("Hata", "Hata olustu.",
                                             exc=exc)
        errors.log_error_event(event)
        assert_no_path_words(event.developer_detail)
    elif channel == "log":
        errors.log(f"tarama: {LONG_DRIVE}, bitti")
    else:
        from app.player import MPVPlayer

        MPVPlayer.log_handler(object(), "warn", "cplayer",
                              f"dosya: {LONG_UNC}]")
        stdout = capsys.readouterr().out
        assert_no_path_words(stdout)

    text = log_env()
    for word in NAME_WORDS:
        assert word not in text, f"{word} loga sizdi"
