# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Paketlenen internet-video calisma zamaninin TEK kaynagi.

URUN KARARI (kullanici onayli): MLC Player resmi `yt-dlp.exe` ve `deno.exe`
dosyalarini KENDI kurulumunda tasir.

- Kullanicinin bilgisayari Python/yt-dlp/Deno/Node icin TARANMAZ.
- Sistem PATH'indeki bir kopya fallback olarak KULLANILMAZ.
- Ilk calistirmada veya URL acilirken bilesen INDIRILMEZ. (17 Agustos 2026:
  ikililer ana kurulumdan CIKARILDI -- birlikte 110 MB tutuyorlardi ve yalniz
  URL oynatmada gerekiyorlar. Ayri "Internet Videosu" ek paketiyle gelirler;
  indirme kullanicinin ACIK eylemidir, program kendiliginden indirmez. Bu
  degismez BOZULMADI, yalnizca bilesenlerin gelis yolu degisti.)
- Sistem PATH'i kalici DEGISTIRILMEZ.
- Runtime icinde `yt-dlp -U`, `deno upgrade` veya baska self-update
  CALISTIRILMAZ; guncelleme yalniz MLC Player setup/guncellemesiyle gelir.

Bu modul saftir: Qt, alt surec, ag ve registry erisimi icermez. Yalniz yol
hesabi ve varlik durumu uretir. Ham yol veya istisna kullaniciya cikmaz.
"""
import os

# Qt'yi import aninda yuklemez (bkz. app/translate.py).
from app.translate import tr_mark

# Bilesen adi -> paketteki dosya adi. Tek kaynak burasidir.
RUNTIME_BINARIES = (
    ("yt-dlp", "yt-dlp.exe"),
    ("deno", "deno.exe"),
)

# Guvenli durum kodlari: loga bilesen adi + kod yazilabilir, YOL yazilmaz.
INTERNET_VIDEO_READY_CODE = "INTERNET_VIDEO_RUNTIME_READY"
INTERNET_VIDEO_MISSING_CODE = "INTERNET_VIDEO_RUNTIME_MISSING"

# Kullaniciya gosterilen TEK metin: ham yol, istisna, traceback veya
# kurulum komutu icermez.
INTERNET_VIDEO_MISSING_MESSAGE = tr_mark(
    "İnternet videosu bileşenleri kurulu değil. "
    "MLC Player İnternet Videosu ek paketini kurup tekrar deneyin."
)
INTERNET_VIDEO_MISSING_TITLE = tr_mark(
    "İnternet Videosu Kullanılamıyor")

# mpv `ytdl_hook` betiginin yt-dlp yolunu ALAN resmi script-opt adi.
YTDL_PATH_OPTION = "ytdl_hook-ytdl_path"


def runtime_paths(bin_dir):
    """Bilesen adi -> paketteki TAM yol.

    Yol her zaman verilen `bin_dir` altindadir; sistem araması YAPILMAZ.
    Dosya yoksa da beklenen yol dondurulur (varlik ayrica sorulur).
    """
    base = str(bin_dir or "")
    return {name: os.path.join(base, filename)
            for name, filename in RUNTIME_BINARIES}


def missing_runtime_components(bin_dir):
    """Pakette BULUNMAYAN bilesenlerin adlari (sabit sirada)."""
    paths = runtime_paths(bin_dir)
    missing = []
    for name, _filename in RUNTIME_BINARIES:
        try:
            present = os.path.isfile(paths[name])
        except (OSError, ValueError):
            present = False
        if not present:
            missing.append(name)
    return tuple(missing)


def internet_video_ready(bin_dir):
    """Site cikarimi icin gereken bilesenlerin tamami pakette mi?"""
    return missing_runtime_components(bin_dir) == ()


def internet_video_status(bin_dir):
    """Loga yazilabilecek GUVENLI durum kodu; yol icermez."""
    if internet_video_ready(bin_dir):
        return INTERNET_VIDEO_READY_CODE
    return INTERNET_VIDEO_MISSING_CODE


def ytdl_script_opt(bin_dir):
    """mpv'ye verilecek `ytdl_hook-ytdl_path=<tam yol>` degeri.

    Paketteki `yt-dlp.exe` yoksa BOS doner: mpv'nin varsayilan `yt-dlp`
    adiyla sistem PATH'inde arama yapmasina GUVENILMEZ, ama var olmayan
    bir yol da yazilmaz.
    """
    path = runtime_paths(bin_dir).get("yt-dlp", "")
    try:
        if not os.path.isfile(path):
            return ""
    except (OSError, ValueError):
        return ""
    return f"{YTDL_PATH_OPTION}={path}"
