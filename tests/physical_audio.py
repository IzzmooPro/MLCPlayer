# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fiziksel kabul child'i icin SESSIZ ses cikisi yardimcilari (saf, Qt'siz).

Buttons grubu ses seviyesini gercekten degistirir (44 -> 140). Gercek
hoparlorden yuksek ses cikmamasi icin YALNIZ test child surecinde
`ao=null` kullanilir. Urunun `app/config.py::MPV_CONFIG` sozlugu
degistirilmez; kullanicinin ses aygiti secimi ve QSettings'i etkilenmez.
"""

# Kabul edilen sessiz cikis adlari (`current-ao` bunlardan birini
# dondurmelidir).
NULL_AO_NAMES = ("null", "null/null")


def native_mpv_config(base_config, silent_audio=True):
    """Test child'i icin YENI bir config sozlugu dondurur.

    Orijinal sozluk MUTATE EDILMEZ.

    - `ao="null"`: ses parcasi ve `volume`/`mute` ozellikleri yasar, ama
      fiziksel cikis olmaz.
    - `audio="no"` EKLENMEZ: bazi dosyalarda mpv hicbir akis secmiyor.
    - `mute` sabitlenmez: buttons grubu fiziksel mute ac/kapat olcuyor.
    """
    config = dict(base_config or {})
    if not silent_audio:
        return config
    config["ao"] = "null"
    if config.get("audio") == "no":
        del config["audio"]
    if config.get("mute") == "yes":
        del config["mute"]
    return config


def audio_safety_problems(current_ao):
    """Yuksek ses olcumune izin verilebilir mi? Bos liste = guvenli.

    Dogrulanamayan cikis (None/bos/auto) GUVENLI SAYILMAZ.
    """
    if current_ao is None:
        return ["current_ao_unavailable"]
    name = str(current_ao).strip().lower()
    if not name:
        return ["current_ao_empty"]
    if name not in NULL_AO_NAMES:
        return [f"current_ao={name}"]
    return []
