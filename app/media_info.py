"""Medya Bilgisi SAF veri katmani: toplama + normalize etme.

Bu modulde Qt YOKTUR. Dialog, menu, QAction, player yasam dongusu ve
clipboard kodu barindirmaz; girdileri aciktir ve global bir player/mpv
nesnesine baglanmaz. Boylece gercek dosya, pencere veya libmpv olmadan
test edilebilir.

Gizlilik sozlesmesi
-------------------
- Tam yerel yol GORUNUR satirlara girmez. Yalniz `MediaInfoSnapshot.copy_value`
  alaninda bulunur; UI onu ANCAK acik kullanici eylemiyle kullanir.
- URL'de yalniz `scheme://host` + guvenli son yol parcasi kalir. `userinfo`,
  `query` ve `fragment` snapshot'a HIC girmez (maskelenmez, uretilmez).
- Dosyadan ve metadata'dan gelen her metin duz metindir; kontrol ve yon
  degistirme karakterlerinden arindirilir ve makul uzunlukta kirilir.
- Ham track ID, `None`, Python repr, `demux-*` anahtar adlari ve ham
  bilinmeyen kodlar kullaniciya ULASMAZ.
- Bu yol geliştirici logu URETMEZ: yazilmayan bir kayit sizamaz.

Saflik sozlesmesi
-----------------
Bu modul `app.errors` ve `app.utils` KULLANMAZ: ikisi de PyQt6 yukler ve saf
katmani dolayli olarak Qt'ye baglardi. Boyut ve sure metinleri bu modulun
kendi kucuk saf yardimcilarindan gelir ve mevcut Turkce ciktiyi korur.
`app.track_labels` hicbir import icermez, bu yuzden kullanilabilir.

Goruntu orani YALNIZ guvenilir kaynaktan uretilir: secili video icin
`video-params/aspect`, ya da track'te guvenilir `demux-par`. Piksel olculerini
(`demux-w`/`demux-h`) bolmek anamorfik kaynakta YANLIS bilgi uretir
(720x576 PAL gercekte 16:9 olabilirken piksel orani `5:4` gosterirdi); bu yol
KULLANILMAZ. HDR gostergesi hala kapsam disidir.

Pencere bir rapor dokumu DEGILDIR: unique ID, ham track/src/ff-index
kimlikleri, writing application/library, bits-per-pixel, stream size yuzdesi
ve dialnorm/compr gibi teshis alanlari BILINCLI olarak gosterilmez. Eksik veya
guvenilmez deger satiri gizler, pencereyi engellemez.
"""
import os
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.track_labels import (bitrate_label, channel_name, codec_name,
                              language_name, sample_rate_label)

# --- Bolum kimlikleri (UI ileride sekme olarak gosterecek) ---
SECTION_GENERAL = "general"
SECTION_VIDEO = "video"
SECTION_AUDIO = "audio"
SECTION_SUBTITLE = "subtitle"

SECTION_TITLES = {
    SECTION_GENERAL: "Genel",
    SECTION_VIDEO: "Video",
    SECTION_AUDIO: "Ses",
    SECTION_SUBTITLE: "Altyazı",
}

EMPTY_MESSAGES = {
    SECTION_VIDEO: "Video parçası yok.",
    SECTION_AUDIO: "Ses parçası yok.",
    SECTION_SUBTITLE: "Altyazı parçası yok.",
}

# Yalnız GEREKEN güvenli property'ler. Okuma hatası ilgili satırı gizler.
VIDEO_PARAM_PROPERTIES = ("video-params/aspect", "video-params/pixelformat",
                          "video-params/primaries",
                          "video-params/colorlevels")

# Renk STANDARDI (gamut/ana renkler) — renk ARALIĞI ile karıştırılmaz.
# `primaries` bir aralık değil, renk uzayı standardıdır; aralık ayrı bir
# alandan (`colorlevels`) gelir. Bilinmeyen değer GÖSTERİLMEZ.
PRIMARIES_NAMES = {
    "bt.709": "BT.709 (HD)",
    "bt.2020": "BT.2020 (UHD)",
    "bt.601-525": "BT.601 (SD)",
    "bt.601-625": "BT.601 (SD)",
    "dci-p3": "DCI-P3",
    "display-p3": "Display P3",
}

# Renk ARALIĞI: mpv `video-params/colorlevels`.
COLOR_LEVEL_NAMES = {
    "limited": "Sınırlı",
    "full": "Tam",
}

# Yaygın ve GÜVENİLİR oranlar; kaynak `video-params/aspect` veya `demux-par`.
_COMMON_ASPECTS = ((16 / 9, "16:9"), (4 / 3, "4:3"), (16 / 10, "16:10"),
                   (21 / 9, "21:9"), (1.0, "1:1"), (2.39, "2.39:1"),
                   (2.35, "2.35:1"), (1.85, "1.85:1"), (3 / 2, "3:2"))
_ASPECT_TOLERANCE = 0.02
_ASPECT_LIMITS = (0.3, 4.0)

# Bit derinliği yalnız piksel biçimi AÇIKÇA söylüyorsa (`yuv420p10`).
_PIXEL_DEPTH = re.compile(r"p(\d{1,2})(le|be)?$")

# "Atmos" YALNIZ açıklama/profil bunu söylüyorsa; codec adından tahmin YOK.
_ATMOS_MARKS = ("atmos", "joc")

YES_TEXT = "Evet"

SELECTED_TEXT = "Seçili"
UNUSED_TEXT = "Kullanılmıyor"

COPY_PATH_LABEL = "Yolu Kopyala"
COPY_URL_LABEL = "Adresi Kopyala"

# Kirpma sinirlari: `track_labels` felsefesiyle ayni, tek kaynaktan.
MAX_TEXT_CHARS = 120
MAX_TITLE_CHARS = 90
MAX_NAME_CHARS = 80
ELLIPSIS = "…"

# Kisaltilmis konumda gosterilen en fazla klasor bileseni.
FOLDER_PARTS = 2

_URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)

# Yon degistirme / gorunmez bicimlendirme isaretleri: dosya adi kandirmacasi
# bu katmanda kesilir.
_BIDI_MARKS = "".join(chr(code) for code in
                      (0x200E, 0x200F, 0x061C, 0x2066, 0x2067, 0x2068, 0x2069,
                       0x202A, 0x202B, 0x202C, 0x202D, 0x202E))

# Kullaniciya gosterilebilir kapsayici adlari. Bilinmeyen deger kisa ise
# buyuk harfle gecer, uzunsa HIC gosterilmez (uydurma yapilmaz).
CONTAINER_NAMES = {
    "matroska": "Matroska", "matroska,webm": "Matroska", "webm": "WebM",
    "mov,mp4,m4a,3gp,3g2,mj2": "MP4", "mp4": "MP4", "mov": "QuickTime",
    "avi": "AVI", "mpegts": "MPEG-TS", "mpeg": "MPEG", "asf": "ASF",
    "flv": "FLV", "ogg": "Ogg", "wav": "WAV", "flac": "FLAC", "mp3": "MP3",
}


# =====================================================================
# Saf bicimlendirme (Qt'siz; mevcut Turkce cikti korunur)
# =====================================================================

def format_size_text(size):
    """`app.errors.format_bytes` ile AYNI cikti, Qt bagimliligi olmadan."""
    try:
        value = float(size)
    except (TypeError, ValueError):
        return "0 bayt"
    if value < 1024:
        return f"{int(value)} bayt"
    for unit in ("KB", "MB", "GB"):
        value /= 1024.0
        if value < 1024 or unit == "GB":
            return f"{value:.1f}".replace(".", ",") + f" {unit}"
    return f"{value:.1f} GB"


def format_duration_text(seconds):
    """`app.utils.format_time` ile AYNI cikti: `MM:SS` veya `HH:MM:SS`."""
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        return ""
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


# =====================================================================
# Guvenli metin
# =====================================================================

def sanitize_display_text(value, limit=MAX_TEXT_CHARS):
    """Duz metin, kontrol karakteri yok, tek bosluk, makul uzunluk.

    Metin OLMAYAN degerler (None, sayi, bytes, nesne) bos donerler; Python
    `repr` gosterimi kullaniciya asla ulasmaz.
    """
    if not isinstance(value, str):
        return ""
    cleaned = []
    for char in value:
        if char in _BIDI_MARKS:
            continue
        category = unicodedata.category(char)
        # Cc: kontrol, Cf: bicimlendirme, Cs: surrogate, Co: ozel kullanim.
        if category in ("Cc", "Cf", "Cs", "Co"):
            cleaned.append(" ")
            continue
        cleaned.append(char)
    text = " ".join("".join(cleaned).split())
    if limit and len(text) > limit:
        return text[:max(1, limit - 1)].rstrip() + ELLIPSIS
    return text


def sanitize_media_url(value):
    """`scheme://host[:port]` + guvenli SON yol parcasi.

    `userinfo`, `query` ve `fragment` sonuca HIC girmez.
    """
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return ""
    scheme = sanitize_display_text(parts.scheme, limit=16).lower()
    host = sanitize_display_text(parts.hostname or "", limit=MAX_NAME_CHARS)
    if not scheme or not host:
        return ""
    try:
        port = parts.port
    except ValueError:
        port = None
    authority = f"{host}:{port}" if port else host
    address = f"{scheme}://{authority}"
    segments = [segment for segment in (parts.path or "").split("/") if segment]
    if segments:
        last = sanitize_display_text(segments[-1], limit=MAX_NAME_CHARS)
        if last:
            address = f"{address}/{last}"
    return address


def _is_url(path):
    return bool(_URL_SCHEME.match(path))


def _shortened_folder(path):
    """Son bilesenler; kok ve tam yol GOSTERILMEZ."""
    folder = os.path.dirname(path)
    if not folder:
        return ""
    parts = [part for part in re.split(r"[\\/]+", folder) if part]
    if not parts:
        return ""
    tail = parts[-FOLDER_PARTS:]
    text = " \\ ".join(sanitize_display_text(part, limit=MAX_NAME_CHARS)
                       for part in tail if part)
    if not text:
        return ""
    return f"{ELLIPSIS} \\ {text}" if len(parts) > len(tail) else text


def _file_size_text(path):
    try:
        return format_size_text(os.path.getsize(path))
    except OSError:
        return ""


# =====================================================================
# Guvenli modeller
# =====================================================================

@dataclass(frozen=True)
class InfoRow:
    """Tek satir: hazir Turkce etiket ve hazir gosterim metni."""

    label: str
    value: str


@dataclass(frozen=True)
class InfoGroup:
    """Bir blok (Genel govdesi veya tek bir track)."""

    title: str
    rows: tuple = ()


@dataclass(frozen=True)
class InfoSection:
    """UI'da bir sekme."""

    key: str
    title: str
    groups: tuple = ()
    empty_message: str = ""

    @property
    def is_empty(self):
        return not self.groups


@dataclass(frozen=True)
class MediaInfoSnapshot:
    """Kullaniciya gosterilecek HAZIR metinlerin tamami.

    `copy_value` GORUNUR degildir: `visible_text()` icine girmez ve UI onu
    yalniz acik kullanici eylemiyle panoya koyar.
    """

    title: str
    is_local: bool
    copy_label: str
    copy_value: str
    sections: tuple = field(default=())

    def section(self, key):
        for section in self.sections:
            if section.key == key:
                return section
        return None

    def visible_text(self):
        """Ekranda GERCEKTEN gorunen butun metin (sizinti kilidi + test)."""
        lines = [self.title, self.copy_label]
        for section in self.sections:
            lines.append(section.title)
            if section.is_empty:
                lines.append(section.empty_message)
                continue
            for group in section.groups:
                lines.append(group.title)
                for row in group.rows:
                    lines.append(f"{row.label}: {row.value}")
        return "\n".join(line for line in lines if line)


def _rows(pairs):
    """Degeri bos olan satir GIZLENIR."""
    return tuple(InfoRow(label, value) for label, value in pairs if value)


# =====================================================================
# Track normalizasyonu
# =====================================================================

def _track_dict(track):
    return track if isinstance(track, dict) else {}


def _track_text(track, *names):
    for name in names:
        value = track.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _track_int(track, *names):
    for name in names:
        value = track.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    return 0


def _track_float(track, *names):
    for name in names:
        value = track.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return 0.0


def _clean_track_text(track, *names, limit=MAX_TEXT_CHARS):
    """Track metni: temizlenir, güvenilmez değerler BOŞ döner."""
    text = sanitize_display_text(_track_text(track, *names), limit=limit)
    if not text or text.lower() in ("unknown", "none", "und", "n/a"):
        return ""
    return text


def _yes_or_hidden(track, name):
    return YES_TEXT if bool(track.get(name)) else ""


def _aspect_text(value):
    """Güvenilir bir orandan kullanıcı dostu etiket; aksi halde BOŞ."""
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return ""
    if not (_ASPECT_LIMITS[0] <= ratio <= _ASPECT_LIMITS[1]):
        return ""
    for known, label in _COMMON_ASPECTS:
        if abs(ratio - known) <= _ASPECT_TOLERANCE:
            return label
    return f"{ratio:.2f}".replace(".", ",") + ":1"


def _pixel_format_text(track, params):
    raw = (_clean_track_text(track, "format-name", limit=MAX_NAME_CHARS)
           or sanitize_display_text(params.get("video-params/pixelformat"),
                                    limit=MAX_NAME_CHARS))
    if not raw or len(raw) > 24:
        return ""
    return raw.upper()


def _bit_depth_text(pixel_format):
    match = _PIXEL_DEPTH.search(str(pixel_format).lower())
    if not match:
        return ""
    depth = int(match.group(1))
    return f"{depth} bit" if 8 <= depth <= 16 else ""


def _primaries_text(params):
    """Renk STANDARDI (gamut). Bilinmeyen değer ham gösterilmez."""
    raw = sanitize_display_text(params.get("video-params/primaries"),
                                limit=MAX_NAME_CHARS).lower()
    return PRIMARIES_NAMES.get(raw, "")


def _color_range_text(params):
    """Renk ARALIĞI (`colorlevels`). Bilinmeyen değer ham gösterilmez."""
    raw = sanitize_display_text(params.get("video-params/colorlevels"),
                                limit=MAX_NAME_CHARS).lower()
    return COLOR_LEVEL_NAMES.get(raw, "")


def _dolby_vision_text(track):
    value = track.get("dolby-vision-profile")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    profile = int(value)
    return f"Profil {profile}" if profile > 0 else ""


def _audio_format_text(track):
    """`Dolby Atmos` YALNIZ açıklama/profil açıkça söylüyorsa."""
    haystack = " ".join((_track_text(track, "codec-desc"),
                         _track_text(track, "codec-profile"))).lower()
    if any(mark in haystack for mark in _ATMOS_MARKS):
        return "Dolby Atmos"
    return ""


def _channels_text(track):
    """Yerleşim ve kanal sayısı TEK kullanıcı dostu satırda."""
    layout = channel_name(_track_int(track, "demux-channel-count",
                                     "audio-channels"),
                          _channel_layout_text(track))
    count = _track_int(track, "demux-channel-count", "audio-channels")
    if layout and count > 0:
        return f"{layout} ({count} kanal)"
    if layout:
        return layout
    return f"{count} kanal" if count > 0 else ""


def _selection_text(track):
    return SELECTED_TEXT if track.get("selected") else UNUSED_TEXT


def _group_title(index, kind, track):
    title = sanitize_display_text(_track_text(track, "title"),
                                  limit=MAX_TITLE_CHARS)
    head = f"{index}. {kind}"
    return f"{head} — {title}" if title else head


def _fps_text(track):
    value = _track_float(track, "demux-fps")
    if value <= 0:
        return ""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + " fps"


def _video_aspect_text(track, params):
    """Oran YALNIZ güvenilir kaynaktan.

    Piksel ölçüsünü bölmek anamorfik kaynakta yanlış bilgi üretir
    (720x576 PAL gerçekte 16:9 olabilir). Kabul edilen kaynaklar:
    seçili video için `video-params/aspect`, ya da track'te güvenilir
    `demux-par` ile birlikte piksel ölçüsü.
    """
    if track.get("selected"):
        text = _aspect_text(params.get("video-params/aspect"))
        if text:
            return text
    par = _track_float(track, "demux-par")
    width = _track_int(track, "demux-w")
    height = _track_int(track, "demux-h")
    if par > 0 and width > 0 and height > 0:
        return _aspect_text(width * par / height)
    return ""


def _video_group(index, track, params=None):
    params = params or {}
    width = _track_int(track, "demux-w")
    height = _track_int(track, "demux-h")
    resolution = f"{width} × {height}" if width > 0 and height > 0 else ""
    pixel_format = _pixel_format_text(track, params)
    return InfoGroup(_group_title(index, "Video Parçası", track), _rows((
        ("Codec", codec_name(_track_text(track, "codec"))),
        ("Codec açıklaması", _clean_track_text(track, "codec-desc",
                                               limit=MAX_TITLE_CHARS)),
        ("Profil", _clean_track_text(track, "codec-profile",
                                     limit=MAX_NAME_CHARS)),
        ("Çözünürlük", resolution),
        ("Görüntü oranı", _video_aspect_text(track, params)),
        ("FPS", _fps_text(track)),
        ("Bitrate", bitrate_label(_track_int(track, "demux-bitrate"))),
        ("Piksel biçimi", pixel_format),
        ("Bit derinliği", _bit_depth_text(pixel_format)),
        # İkisi AYRI alandır: standart gamut, aralık ise siyah/beyaz
        # seviyeleridir. Yalnız SEÇİLİ video için okunur.
        ("Renk standardı", _primaries_text(params) if track.get("selected")
         else ""),
        ("Renk aralığı", _color_range_text(params) if track.get("selected")
         else ""),
        ("Dolby Vision", _dolby_vision_text(track)),
        ("Varsayılan", _yes_or_hidden(track, "default")),
        ("Durum", _selection_text(track)),
    )))


def _channel_layout_text(track):
    """Okuma sirasi `app/track_labels.py` ile AYNI.

    Gercek libmpv alani `demux-channels` (ornek: `5.1(side)`).
    `demux-channel-layout` gercek bir alan DEGILDIR; yalniz eski test
    double'lari icin geriye donuk uyumluluk olarak okunur.
    """
    return _track_text(track, "demux-channels", "demux-channel-layout")


def _audio_group(index, track, params=None):
    duration = _track_float(track, "demux-duration")
    return InfoGroup(_group_title(index, "Ses Parçası", track), _rows((
        ("Dil", language_name(_track_text(track, "lang"))),
        ("Codec", codec_name(_track_text(track, "codec"))),
        ("Codec açıklaması", _clean_track_text(track, "codec-desc",
                                               limit=MAX_TITLE_CHARS)),
        ("Profil", _clean_track_text(track, "codec-profile",
                                     limit=MAX_NAME_CHARS)),
        ("Ses biçimi", _audio_format_text(track)),
        ("Kanal", _channels_text(track)),
        ("Örnekleme", sample_rate_label(_track_int(track, "demux-samplerate"))),
        ("Bitrate", bitrate_label(_track_int(track, "demux-bitrate"))),
        ("Parça süresi", format_duration_text(duration) if duration > 0
         else ""),
        ("Varsayılan", _yes_or_hidden(track, "default")),
        ("Zorunlu", _yes_or_hidden(track, "forced")),
        ("Durum", _selection_text(track)),
    )))


def _subtitle_group(index, track, params=None):
    external = bool(track.get("external"))
    name = ""
    if external:
        raw = _track_text(track, "external-filename")
        # Yalniz dosya adi: klasor bilgisi SNAPSHOT'A GIRMEZ.
        name = sanitize_display_text(os.path.basename(raw),
                                     limit=MAX_NAME_CHARS)
    return InfoGroup(_group_title(index, "Altyazı Parçası", track), _rows((
        ("Dil", language_name(_track_text(track, "lang"))),
        ("Tür", codec_name(_track_text(track, "codec"))),
        ("Kaynak", "Harici" if external else "Gömülü"),
        ("Dosya", name),
        ("Varsayılan", _yes_or_hidden(track, "default")),
        ("Zorunlu", _yes_or_hidden(track, "forced")),
        ("İşitme engelliler için", _yes_or_hidden(track, "hearing-impaired")),
        ("Durum", _selection_text(track)),
    )))


_TRACK_BUILDERS = (
    (SECTION_VIDEO, "video", _video_group),
    (SECTION_AUDIO, "audio", _audio_group),
    (SECTION_SUBTITLE, "sub", _subtitle_group),
)


def _track_sections(track_list, params=None):
    sections = []
    for key, wanted, builder in _TRACK_BUILDERS:
        groups = []
        for track in (track_list or []):
            data = _track_dict(track)
            if data.get("type") != wanted:
                continue
            groups.append(builder(len(groups) + 1, data, params))
        sections.append(InfoSection(key, SECTION_TITLES[key], tuple(groups),
                                    "" if groups else EMPTY_MESSAGES[key]))
    return sections


# =====================================================================
# Genel bolumu
# =====================================================================

def _read_property(property_reader, name):
    """Salt okunur ve hata sinirinda: okunamayan deger satiri gizler."""
    if property_reader is None:
        return None
    try:
        return property_reader(name)
    except Exception:
        return None


def _video_params(property_reader):
    """Gereken video property'leri TEK seferde; hata satırı gizler."""
    if property_reader is None:
        return {}
    return {name: _read_property(property_reader, name)
            for name in VIDEO_PARAM_PROPERTIES}


def _container_text(property_reader):
    raw = sanitize_display_text(_read_property(property_reader, "file-format"),
                                limit=MAX_NAME_CHARS)
    if not raw:
        return ""
    known = CONTAINER_NAMES.get(raw.lower())
    if known:
        return known
    head = raw.split(",")[0].strip()
    return head.upper() if 0 < len(head) <= 10 else ""


def _metadata_title(property_reader):
    metadata = _read_property(property_reader, "metadata")
    if not isinstance(metadata, dict):
        return ""
    for key in ("title", "TITLE", "Title"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return sanitize_display_text(value, limit=MAX_TITLE_CHARS)
    return ""


def _overall_bitrate_text(path, is_local, seconds):
    """YALNIZ yerel dosyada, güvenilir boyut ve süre varsa."""
    if not is_local or seconds <= 0:
        return ""
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    if size <= 0:
        return ""
    return bitrate_label(int(size * 8 / seconds))


def _general_section(path, is_local, address, duration, property_reader):
    duration_text = ""
    try:
        seconds = float(duration or 0)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds > 0:
        duration_text = format_duration_text(seconds)
    if is_local:
        head = (("Dosya", sanitize_display_text(os.path.basename(path),
                                                limit=MAX_NAME_CHARS)),
                ("Konum", _shortened_folder(path)),
                ("Boyut", _file_size_text(path)))
    else:
        head = (("Adres", address),)
    rows = _rows(head + (
        ("Süre", duration_text),
        ("Kapsayıcı", _container_text(property_reader)),
        ("Genel bitrate", _overall_bitrate_text(path, is_local, seconds)),
        ("Başlık", _metadata_title(property_reader)),
    ))
    return InfoSection(SECTION_GENERAL, SECTION_TITLES[SECTION_GENERAL],
                       (InfoGroup("", rows),), "")


def build_media_info(current_file, duration=0, track_list=None,
                     property_reader=None):
    """Gosterime HAZIR snapshot; medya yoksa `None`.

    `property_reader` opsiyoneldir ve YALNIZ okuma yapar: `file-format` ve
    `metadata`. Hatasi satiri gizler, snapshot'i engellemez.
    """
    path = current_file.strip() if isinstance(current_file, str) else ""
    if not path:
        return None
    is_local = not _is_url(path)
    address = "" if is_local else sanitize_media_url(path)
    if not is_local and not address:
        return None
    if is_local:
        title = sanitize_display_text(os.path.basename(path),
                                      limit=MAX_NAME_CHARS)
        copy_label, copy_value = COPY_PATH_LABEL, path
    else:
        title = address
        copy_label, copy_value = COPY_URL_LABEL, address
    params = _video_params(property_reader)
    sections = [_general_section(path, is_local, address, duration,
                                 property_reader)]
    sections.extend(_track_sections(track_list, params))
    return MediaInfoSnapshot(title, is_local, copy_label, copy_value,
                             tuple(sections))


# =====================================================================
# Tazeleme anahtari
# =====================================================================

def _track_signature(track):
    """Yalniz GOSTERIMI etkileyen guvenli alanlar; sabit SIRA.

    Dict sirasina ve nesne kimligine dayanmaz; bozuk kayit da kararli bir
    imza uretir.
    """
    data = _track_dict(track)
    external = bool(data.get("external"))
    name = os.path.basename(_track_text(data, "external-filename")) \
        if external else ""
    return (
        _track_text(data, "type"),
        bool(data.get("selected")),
        _track_int(data, "id"),
        _track_text(data, "codec"),
        _track_text(data, "lang"),
        _track_text(data, "title"),
        _track_int(data, "demux-w"),
        _track_int(data, "demux-h"),
        round(_track_float(data, "demux-fps"), 3),
        _track_int(data, "demux-channel-count", "audio-channels"),
        _channel_layout_text(data),
        _track_int(data, "demux-samplerate"),
        _track_int(data, "demux-bitrate"),
        _track_text(data, "codec-desc"),
        _track_text(data, "codec-profile"),
        _track_text(data, "format-name"),
        round(_track_float(data, "demux-par"), 4),
        round(_track_float(data, "demux-duration"), 2),
        _track_int(data, "dolby-vision-profile"),
        bool(data.get("default")),
        bool(data.get("forced")),
        bool(data.get("hearing-impaired")),
        external,
        name,
    )


def _selected_ids(track_list):
    """Secili vid/aid/sid; yoksa 0. Ekranda GOSTERILMEZ, yalniz anahtardir."""
    chosen = {"video": 0, "audio": 0, "sub": 0}
    for track in (track_list or []):
        data = _track_dict(track)
        kind = _track_text(data, "type")
        if kind in chosen and data.get("selected") and not chosen[kind]:
            chosen[kind] = _track_int(data, "id")
    return (chosen["video"], chosen["audio"], chosen["sub"])


def media_info_refresh_key(current_file, duration=0, track_list=None,
                           property_reader=None):
    """Acik pencerenin tazelenmesi gereken durumu tanimlayan KARARLI anahtar.

    Kesirli saniye gurultusu anahtari degistirmez; secili track degisimi,
    kanal yerlesimi degisimi, gec gelen track, gec gelen kapsayici/baslik ve
    medya degisimi degistirir.

    `property_reader` opsiyoneldir ve anahtara YALNIZ sanitize edilmis
    kapsayici/baslik metni girer: ham metadata sozlugu, ham deger veya
    exception ne anahtara ne de loga tasinir. Okuma hatasi anahtar uretimini
    bozmaz; okuyucu verilmemesiyle AYNI sonucu verir. Bu okumalar ileride
    yalniz Medya Bilgisi penceresi ACIKKEN yapilir, genel oynatma maliyeti
    olusturmaz.
    """
    path = current_file if isinstance(current_file, str) else ""
    try:
        seconds = int(float(duration or 0))
    except (TypeError, ValueError):
        seconds = 0
    signatures = tuple(_track_signature(track) for track in (track_list or []))
    params = _video_params(property_reader)
    late = (_container_text(property_reader), _metadata_title(property_reader),
            _aspect_text(params.get("video-params/aspect")),
            sanitize_display_text(params.get("video-params/pixelformat"),
                                  limit=MAX_NAME_CHARS),
            _primaries_text(params), _color_range_text(params))
    return ((path, seconds) + _selected_ids(track_list)
            + (signatures,) + late)
