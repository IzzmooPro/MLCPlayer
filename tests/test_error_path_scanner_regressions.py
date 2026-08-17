# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yol maskelemesinin GENEL sözleşmesi: fail-closed satır tarayıcısı.

Neden sözleşme değişti
----------------------
Serbest metindeki TIRNAKSIZ, boşluklu ve uzantısız bir Windows yolunun
nerede bittiği genel olarak belirlenemez: virgül, noktalı virgül,
parantez ve boşluk Windows dosya adında geçerlidir. Bu yüzden uzantıya
ve noktalama işaretlerine dayanan regex istisnaları hep kaçak bırakıyordu
(`D:\\Private\\gizli klasor` -> `<yol> klasor`).

Yeni sözleşme
-------------
1. Tırnakla çevrili mutlak yol: AÇILIŞ tırnağından eşleşen KAPANIŞ
   tırnağına kadar tamamı maskelenir; tırnaklar ve sonraki cümle kalır.
2. Tırnaksız mutlak yol: güvenli sınır YOKTUR, bu yüzden gizlilik lehine
   SATIR SONUNA kadar maskelenir (fail-closed). Sonraki satır yutulmaz.
3. Yalnız tırnakla sınırlanmış kaynak kod yollarında boşluksuz
   `.py`/`.pyw` dosya adı tanı için korunur. `.mkv`, `.mp4`, `.srt`,
   uzantısız dosya ve klasör adları KORUNMAZ.

Bütün değerler sentetiktir; testler geçici log dizini kullanır.
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

MASK = "<yol>"
SECRET_WORDS = ("Private", "gizli", "klasor", "Gercek Kullanici", "My Videos",
                "Musteri", "Sozlesmesi", "server", "share", "film", "Folder")


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


def assert_clean(text):
    # Maske işaretlerinin kendisi taramaya girmemeli: `<gizli>` işareti
    # "gizli" kelimesini içerir.
    scanned = text.replace(errors.MASK, "").replace(errors.MASK_PATH, "")
    for word in SECRET_WORDS:
        assert word not in scanned, f"{word} acikta kaldi: {text!r}"


# --- A. Tırnaklı yollar --------------------------------------------------

@pytest.mark.parametrize("raw", [
    r'"D:\Private\gizli klasor"',
    r'"D:/Private Folder/Musteri Sozlesmesi.mp4"',
    r'"\\server\share\Private Folder\film.mkv"',
    r'"//server/share/Private Folder/film.mkv"',
    r'"D:\Private\dosya, virgullu; adi (parantez) [kose].mkv"',
])
def test_double_quoted_paths_are_masked_up_to_the_closing_quote(raw):
    """SÖZLEŞME GÜNCELLENDİ: sınırlı maskeleme YALNIZ çift tırnakta.

    Eski ad `test_quoted_paths_are_masked_up_to_the_closing_quote` idi ve
    tek tırnaklı örnekleri de kapsıyordu. `'` Windows dosya adında
    geçerli olduğu için dış kapanış belirlenemez; tek tırnaklı yollar
    artık aşağıda fail-closed olarak ölçülür.
    """
    masked = errors.redact(raw)
    assert_clean(masked)
    assert MASK in masked
    # Tırnaklar korunur.
    assert masked[0] == raw[0] and masked[-1] == raw[-1]


@pytest.mark.parametrize("raw", [
    r"'C:\Users\Gercek Kullanici\My Videos\film'",
    r"'D:\Private\gizli klasor'",
])
def test_single_quoted_paths_are_masked_to_end_of_line(raw):
    masked = errors.redact(raw)
    assert_clean(masked)
    assert masked == f"'{MASK}", masked


def test_quoted_path_keeps_the_following_sentence():
    masked = errors.redact(
        'Hata: "D:\\Private\\gizli klasor", tekrar deneyin')
    assert masked == 'Hata: "<yol>", tekrar deneyin'


def test_unclosed_quote_fails_closed_to_end_of_line():
    masked = errors.redact('Hata: "D:\\Private\\gizli klasor tekrar deneyin')
    assert_clean(masked)
    assert "tekrar deneyin" not in masked, "kapanmamis tirnakta fail-closed"


# --- B. Tırnaksız yollar: fail-closed -----------------------------------

@pytest.mark.parametrize("raw", [
    r"D:\Private\gizli klasor",
    r"D:\Private\Musteri Sozlesmesi.mp4",
    r"C:\Users\Gercek Kullanici\My Videos\film",
    r"//server/share/Private Folder/film.mkv",
    r"\\server\share\Private Folder\film.mkv",
])
def test_unquoted_paths_are_masked_to_end_of_line(raw):
    masked = errors.redact(f"Hata: {raw} tekrar denenemedi")
    assert_clean(masked)
    assert masked == "Hata: <yol>", masked


def test_unquoted_path_does_not_swallow_the_next_line():
    text = ("[ERROR] acilamadi: D:\\Private\\gizli klasor devam\n"
            "[INFO] Altyazı parçası seçildi: 2 (tur)\n")
    masked = errors.redact(text)
    assert_clean(masked)
    assert "Altyazı parçası seçildi: 2 (tur)" in masked
    assert masked.count("[INFO]") == 1


def test_unquoted_path_keeps_the_text_before_it():
    masked = errors.redact("Açılamadı: D:\\Private\\gizli klasor")
    assert masked == "Açılamadı: <yol>"


# --- C. Kök biçimleri ----------------------------------------------------

@pytest.mark.parametrize("root", [
    r"C:\folder\file",
    r"C:/folder/file",
    r"D:\folder",
    r"\\server\share\folder",
    r"//server/share/folder",
    r"\\?\C:\very long path\file",
    r"\\?\UNC\server\share\folder",
])
def test_every_supported_root_is_detected(root):
    masked = errors.redact(f"yol: {root}")
    assert masked == "yol: <yol>", masked


# --- D. Negatif örnekler -------------------------------------------------

@pytest.mark.parametrize("harmless", [
    "https://example.test/video",
    "indiriliyor: https://example.test/video.mkv",
    "file.py:12",
    "12:30 itibariyle",
    "a/b klasoru",
    "Dosya bulunamadı. Dosya taşınmış veya silinmiş olabilir.",
    "Altyazı parçası seçildi: 2 (tur), devam ediliyor.",
    "[warn] [cplayer] Bilinmeyen anahtar: deinterlace",
    "Oynatma hızı 1.5x olarak ayarlandı; iyi seyirler.",
    "MPV oynatıcı başarıyla yapılandırıldı.",
])
def test_non_paths_are_never_touched(harmless):
    assert errors.redact(harmless) == harmless


# --- Tanı istisnası: yalnız tırnaklı .py --------------------------------

def test_quoted_source_file_name_is_kept_for_diagnosis():
    masked = errors.redact(r'File "C:\Users\X\proje\app\player.py", line 12')
    assert masked == r'File "<yol>\player.py", line 12'


def test_quoted_pyw_is_also_kept():
    masked = errors.redact(r'File "C:\proje\app\main.pyw", line 3')
    assert masked == r'File "<yol>\main.pyw", line 3'


@pytest.mark.parametrize("raw", [
    r'"C:\Users\X\Videos\film.mkv"',
    r'"C:\Users\X\Videos\film.mp4"',
    r'"C:\Users\X\Videos\altyazi.srt"',
    r'"C:\Users\X\Videos\uzantisiz"',
    r'"C:\Users\X\Videos"',
    r'"C:\Users\X\Videos\iki kelime.py"',
])
def test_media_and_ambiguous_names_are_never_kept(raw):
    masked = errors.redact(raw)
    for leak in ("film", "altyazi", "uzantisiz", "Videos", "iki kelime"):
        assert leak not in masked, f"{leak} acikta kaldi: {masked!r}"


def test_unquoted_python_file_is_not_kept():
    """Tanı istisnası YALNIZ tırnaklı yollar içindir."""
    masked = errors.redact(r"yol: C:\proje\app\player.py")
    assert masked == "yol: <yol>"


# --- E. Kanallar ---------------------------------------------------------

@pytest.mark.parametrize("channel", ["user_message", "details", "exception",
                                     "log", "mpv"])
def test_contract_holds_on_every_channel(log_env, capsys, channel):
    unquoted = r"D:\Private\gizli klasor"
    if channel == "user_message":
        event = errors.build_error_event("Hata", f"Acilamadi: {unquoted}")
        errors.log_error_event(event)
        assert_clean(event.user_message)
    elif channel == "details":
        event = errors.build_error_event("Hata", "Hata olustu.",
                                         details=f"yol: {unquoted}")
        errors.log_error_event(event)
        assert_clean(event.developer_detail)
    elif channel == "exception":
        try:
            raise OSError(f"acilamadi: {unquoted}")
        except OSError as exc:
            event = errors.build_error_event("Hata", "Hata olustu.", exc=exc)
        errors.log_error_event(event)
        assert_clean(event.developer_detail)
        # Traceback'teki kaynak dosya adı tanı için korunmalı.
        assert "test_error_path_scanner_regressions.py" in \
            event.developer_detail
    elif channel == "log":
        errors.log(f"tarama: {unquoted}")
    else:
        from app.player import MPVPlayer

        MPVPlayer.log_handler(object(), "warn", "cplayer",
                              f"dosya: {unquoted}")
        assert_clean(capsys.readouterr().out)

    assert_clean(log_env())


# --- F. Özellikler -------------------------------------------------------

@pytest.mark.parametrize("raw", [
    r"D:\Private\gizli klasor",
    r'"D:\Private\gizli klasor"',
    r"//server/share/Private Folder/film.mkv",
    r'File "C:\proje\app\player.py", line 12',
    "Dosya bulunamadı.",
])
def test_masking_is_idempotent(raw):
    once = errors.redact(raw)
    assert errors.redact(once) == once


def test_secret_masking_still_works_next_to_paths():
    masked = errors.redact(
        'api_key=SENTETIK123 ve "D:\\Private\\gizli klasor" bitti')
    assert "SENTETIK123" not in masked
    assert_clean(masked)
    assert "bitti" in masked


def test_authorization_masking_is_unchanged():
    masked = errors.redact("Authorization: Digest SENTETIK123")
    assert "SENTETIK123" not in masked
    assert "Authorization" in masked


def test_scanner_stays_fast_on_a_100kb_input():
    line = r'Hata: "D:\Private\gizli klasor", tekrar deneyin. '
    payload = (line * 1600) + "\n" + ("normal cumle " * 3000)
    assert len(payload) > 100_000
    started = time.time()
    masked = errors.redact(payload)
    elapsed = time.time() - started
    assert elapsed < 3.0, f"redact cok yavas: {elapsed:.2f}s"
    assert_clean(masked)
