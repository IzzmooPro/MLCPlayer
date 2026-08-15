"""Ses ve altyazı parçaları için ORTAK, kullanıcı dostu etiket üreticisi.

Neden ortak modül
-----------------
Ana menü (`app/menu_actions.py`) ve video sağ-tık menüsü
(`app/video_frame.py`) etiketleri ayrı ayrı üretiyordu; ikisi de ham MPV
metadata'sını kullanıcıya gösteriyordu:

    Ses Kanalı 1 (ID: 1)      eng (ID: 2)      5.1(side)

Artık iki menü de buradaki saf fonksiyonları kullanır.

Sözleşme
--------
- Qt, MPV veya ağ bağımlılığı YOKTUR; hepsi saf fonksiyondur.
- Eksik, bozuk veya beklenmeyen metadata karşısında ASLA çökmez; bilgi
  uydurmaz ve boş ayraç üretmez.
- Kullanıcı metninde ham dil kodu (`eng`, `und`), teknik anahtar
  (`demux-bitrate`), MPV parça kimliği veya `None` bulunmaz.
- Parça kimliği çağıranın sorumluluğundadır (QAction.data / closure);
  etikete YAZILMAZ.
"""

# --- Dil kodları -----------------------------------------------------

LANGUAGE_NAMES = {
    "en": "İngilizce", "eng": "İngilizce",
    "tr": "Türkçe", "tur": "Türkçe",
    "de": "Almanca", "deu": "Almanca", "ger": "Almanca",
    "fr": "Fransızca", "fra": "Fransızca", "fre": "Fransızca",
    "es": "İspanyolca", "spa": "İspanyolca",
    "it": "İtalyanca", "ita": "İtalyanca",
    "pt": "Portekizce", "por": "Portekizce",
    "ru": "Rusça", "rus": "Rusça",
    "ar": "Arapça", "ara": "Arapça",
    "ja": "Japonca", "jpn": "Japonca",
    "ko": "Korece", "kor": "Korece",
    "zh": "Çince", "zho": "Çince", "chi": "Çince",
    "nl": "Felemenkçe", "nld": "Felemenkçe", "dut": "Felemenkçe",
    "pl": "Lehçe", "pol": "Lehçe",
    "uk": "Ukraynaca", "ukr": "Ukraynaca",
}

# Dil bilinmiyor demek olan MPV değerleri; kullanıcıya GÖSTERİLMEZ.
_UNKNOWN_LANGUAGES = {"und", "unknown", "none", "null", ""}

CODEC_NAMES = {
    "eac3": "E-AC-3", "e-ac-3": "E-AC-3", "ec-3": "E-AC-3",
    "ac3": "AC-3", "ac-3": "AC-3",
    "aac": "AAC", "dts": "DTS", "truehd": "TrueHD",
    "flac": "FLAC", "opus": "Opus", "mp3": "MP3",
}

# Yalnızca GÜVENİLİR ve açık eşlemeler; bilinmeyen başlık özgün kalır.
TITLE_TRANSLATIONS = {
    "director commentary": "Yönetmen Yorumu",
    "directors commentary": "Yönetmen Yorumu",
    "director's commentary": "Yönetmen Yorumu",
    "commentary": "Yorum",
}

AUDIO_FALLBACK = "Ses Parçası"
SUBTITLE_FALLBACK = "Altyazı Parçası"

# Menü ekran dışına taşmasın diye üst sınır. Ayırt edici teknik bilgi
# korunur; yalnızca serbest metin başlık kısaltılır.
MAX_LABEL_CHARS = 90
MAX_TITLE_CHARS = 42
ELLIPSIS = "…"

_SEPARATOR = " · "
_HEAD_SEPARATOR = " — "


def _text(value):
    """Güvenli metin: `None`, sayı ve beklenmeyen tip sorun çıkarmaz."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return ""


def _int(value):
    try:
        if isinstance(value, bool) or value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def language_name(code):
    """Dil kodu → Türkçe ad. Bilinmiyorsa BOŞ döner (ham kod sızmaz)."""
    text = _text(code).lower()
    if not text or text in _UNKNOWN_LANGUAGES:
        return ""
    return LANGUAGE_NAMES.get(text, "")


def codec_name(codec):
    """Codec kodu → okunabilir ad. Bilinmeyen codec büyük harfle gösterilir."""
    text = _text(codec).lower()
    if not text:
        return ""
    known = CODEC_NAMES.get(text)
    if known:
        return known
    # Bilinmeyen codec'i uydurmadan, ama okunur biçimde göster.
    return text.upper() if len(text) <= 8 else ""


def channel_name(count, layout=None):
    """Kanal sayısı/yerleşimi → Mono / Stereo / 5.1 / 7.1.

    `5.1(side)` gibi DAHİLİ yerleşim eki kullanıcıya gösterilmez.
    """
    text = _text(layout)
    if text:
        base = text.split("(")[0].strip()
        if base in ("5.1", "7.1", "mono", "stereo"):
            return {"mono": "Mono", "stereo": "Stereo"}.get(base, base)
    number = _int(count)
    return {1: "Mono", 2: "Stereo", 6: "5.1", 8: "7.1"}.get(number, "")


def sample_rate_label(hertz):
    """48000 → `48 kHz`, 44100 → `44,1 kHz` (Türkçe ondalık ayracı)."""
    value = _int(hertz)
    if value <= 0:
        return ""
    khz = value / 1000.0
    if abs(khz - round(khz)) < 0.05:
        return f"{int(round(khz))} kHz"
    return f"{khz:.1f}".replace(".", ",") + " kHz"


def bitrate_label(bits_per_second):
    """640000 → `640 kb/sn`."""
    value = _int(bits_per_second)
    if value <= 0:
        return ""
    return f"{int(round(value / 1000.0))} kb/sn"


def _channel_layout(track):
    """Kanal YERLEŞİMİ alanı.

    Gerçek libmpv `track_list` sözlüğünde yerleşim `demux-channels`
    anahtarındadır (ör. `5.1(side)`, `stereo`). `demux-channel-layout`
    gerçek bir alan DEĞİLDİR; yalnızca eski test double'ları için geriye
    dönük uyumluluk olarak okunur.
    """
    for key in ("demux-channels", "demux-channel-layout"):
        text = _text(track.get(key))
        if text:
            return text
    return ""


def _channel_count(track):
    """Kanal SAYISI alanı. Yerleşimle KARIŞTIRILMAZ."""
    for key in ("demux-channel-count", "audio-channels"):
        value = _int(track.get(key))
        if value > 0:
            return value
    return 0


def _flag(track, *names):
    for name in names:
        if bool(track.get(name)):
            return True
    return False


def _status_flags(track):
    flags = []
    if _flag(track, "default"):
        flags.append("Varsayılan")
    if _flag(track, "forced"):
        flags.append("Zorunlu")
    if _flag(track, "external"):
        flags.append("Harici")
    return flags


def _title(track):
    """Anlamlı başlık; yalnızca güvenilir eşlemeler Türkçeleştirilir."""
    text = _text(track.get("title"))
    if not text:
        return ""
    return TITLE_TRANSLATIONS.get(text.lower(), text)


def _shorten(text, limit=MAX_TITLE_CHARS):
    if len(text) <= limit:
        return text
    return text[:max(1, limit - 1)].rstrip() + ELLIPSIS


def _compose(head, parts, fallback):
    head = head or ""
    parts = [part for part in parts if part]
    if not head and not parts:
        return fallback
    if not head:
        head, parts = parts[0], parts[1:]
    if not parts:
        return head
    label = head + _HEAD_SEPARATOR + _SEPARATOR.join(parts)
    if len(label) <= MAX_LABEL_CHARS:
        return label
    # Uzun serbest metin kısaltılır; teknik ayrıntı KORUNUR.
    fixed = len(head) + len(_HEAD_SEPARATOR) + len(
        _SEPARATOR.join(parts[1:])) + (len(_SEPARATOR) if parts[1:] else 0)
    room = max(8, MAX_LABEL_CHARS - fixed)
    parts = [_shorten(parts[0], room)] + parts[1:]
    label = head + _HEAD_SEPARATOR + _SEPARATOR.join(parts)
    if len(label) <= MAX_LABEL_CHARS:
        return label
    return _shorten(label, MAX_LABEL_CHARS)


def _as_dict(track):
    return track if isinstance(track, dict) else {}


def audio_track_label(track):
    """Tek ses parçası için kullanıcı metni."""
    track = _as_dict(track)
    language = language_name(track.get("lang") or track.get("language"))
    title = _title(track)
    parts = []
    # Başlık dil adının aynısıysa TEKRARLANMAZ ("Türkçe — Türkçe · Harici").
    # İndirilen altyazıya `title=<dil adı>` metadata'sı yazıldığında oluşur.
    if language and title and title.casefold() != language.casefold():
        parts.append(_shorten(title))
    parts.append(codec_name(track.get("codec")))
    parts.append(channel_name(_channel_count(track), _channel_layout(track)))
    parts.append(sample_rate_label(track.get("demux-samplerate")))
    parts.append(bitrate_label(track.get("demux-bitrate")))
    parts.extend(_status_flags(track))

    head = language or (_shorten(title) if title else "")
    return _compose(head, parts, AUDIO_FALLBACK)


def subtitle_track_label(track):
    """Tek altyazı parçası için kullanıcı metni."""
    track = _as_dict(track)
    language = language_name(track.get("lang") or track.get("language"))
    title = _title(track)
    parts = []
    # Başlık dil adının aynısıysa TEKRARLANMAZ ("Türkçe — Türkçe · Harici").
    # İndirilen altyazıya `title=<dil adı>` metadata'sı yazıldığında oluşur.
    if language and title and title.casefold() != language.casefold():
        parts.append(_shorten(title))
    if _flag(track, "hearing_impaired", "hearing-impaired"):
        parts.append("SDH")
    if _flag(track, "forced"):
        parts.append("Zorunlu")
    if _flag(track, "external"):
        parts.append("Harici")

    head = language or (_shorten(title) if title else "")
    if not head:
        # SON ÇARE: dil ve anlamlı başlık gerçekten yoksa dosya adı.
        # Durum etiketleri (Harici/Zorunlu) baş metnin yerine GEÇMEZ.
        name = _text(track.get("external-filename"))
        if name:
            base = name.replace("\\", "/").rsplit("/", 1)[-1]
            if base.lower().endswith(".srt"):
                base = base[:-4]
            head = _shorten(base, MAX_TITLE_CHARS)
    return _compose(head, parts, SUBTITLE_FALLBACK)


def _disambiguate(labels):
    """Aynı görünen satırlar YALNIZCA gerekiyorsa numaralanır."""
    counts = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    seen = {}
    result = []
    for label in labels:
        if counts[label] < 2:
            result.append(label)
            continue
        seen[label] = seen.get(label, 0) + 1
        result.append(f"{label} — Parça {seen[label]}")
    return result


def audio_track_labels(tracks):
    """Ses parçası listesi → aynı sıradaki kullanıcı metinleri."""
    labels = [audio_track_label(track) for track in (tracks or [])]
    return _disambiguate(labels)


def subtitle_track_labels(tracks):
    """Altyazı parçası listesi → aynı sıradaki kullanıcı metinleri."""
    labels = [subtitle_track_label(track) for track in (tracks or [])]
    return _disambiguate(labels)
