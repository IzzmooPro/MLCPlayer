# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı görünüm stilinin MPV sözleşmesi (saf, Qt dialog'undan bağımsız).

Neden ayrı modül
----------------
Renk biçimi, arka plan kutusu ve ASS override kararları ölçülebilir ve
test edilebilir olmalı; dialog yerleşimi değiştiğinde bu sözleşme
değişmemeli.

Kanıtlanmış kök nedenler
------------------------
- Kod `#RRGGBBAA` üretiyordu; MPV **`#AARRGGBB`** bekler. Seçilen turuncu
  bu yüzden MPV tarafında başka renge dönüşüyordu.
- `sub-back-color`, MPV'nin varsayılan `outline-and-shadow` stilinde tam
  bir arka plan kutusu değil GÖLGE rengidir. Kullanıcının beklediği kutu
  için `sub-border-style=background-box` gerekir.
- ASS altyazılarda normal `sub_*` seçeneklerinin uygulanması için
  `sub-ass-override=force` gerekir; bool `True`/`"yes"` bütün seçenekleri
  zorlamaz.

Bu modül dosya sistemi, ağ veya kullanıcı arayüzü KULLANMAZ.
"""
from PyQt6.QtGui import QColor

from app.translate import tr_mark, translate_marked

# MPV `sub-border-style` değerleri.
BACKGROUND_BOX = "background-box"
OUTLINE_AND_SHADOW = "outline-and-shadow"

# ASS altyazıda normal stil seçeneklerini zorlayan tek geçerli değer.
ASS_OVERRIDE_FORCE = "force"
ASS_OVERRIDE_OFF = "no"

# `background-box` modunda kutunun altındaki gölge kapatılır; kutu zaten
# okunabilirliği sağlar ve gölge kenarları bulanıklaştırıyordu. Değer
# rastgele değil, açık bir sözleşme sabitidir.
BACKGROUND_BOX_SHADOW_OFFSET = 0.0

COLOR_KEYS = ("sub_color", "sub_back_color", "sub_border_color")
NUMBER_KEYS = ("sub_delay", "sub_scale", "sub_pos", "sub_border_size")
SETTINGS_PREFIX = "subtitle/"

# --- Hazır değerler ve merkezi sayısal doğrulama -------------------------
#
# Eski arayüz serbest sayısal alanlar veriyordu: senkron ±120 sn, boyut
# 0,5–3,0×, kenarlık 0–10 px. Kullanıcı yanlışlıkla 3× yazı veya 10 px
# kenarlık uygulayabiliyordu ve eski QSettings kayıtları bu değerleri
# doğrudan MPV'ye taşıyordu. Ürün kararı: yalnız HAZIR değerler.
#
# Doğrulama TEK yerdedir; pencere, `style_properties()`/`atomic_apply()`
# ve `MPVPlayer.restore_subtitle_settings()` aynı fonksiyonu çağırır.
DELAY_PRESETS = tuple(round(-5.0 + index * 0.25, 2) for index in range(41))
SCALE_PRESETS = (0.75, 0.85, 1.0, 1.15, 1.25, 1.5, 2.0)
BORDER_PRESETS = tuple(round(index * 0.5, 1) for index in range(11))

NUMERIC_PRESETS = {
    "sub_delay": DELAY_PRESETS,
    "sub_scale": SCALE_PRESETS,
    "sub_border_size": BORDER_PRESETS,
}
# `sub_pos` hazır listeye BAĞLANMAZ: kaydırıcı 0–100 arasında serbesttir.
NUMERIC_RANGES = {"sub_pos": (0.0, 100.0)}


def _numeric_default(name):
    from app.config import SUBTITLE_DEFAULTS      # döngüsel import olmasın

    return float(SUBTITLE_DEFAULTS[name])


def _finite(value):
    """Sayıya çevrilebilir ve SONLU mu? Değilse `None`.

    `None`, boş dize, liste, NaN ve sonsuzluk güvenli varsayılana düşer;
    QSettings ini biçiminde sayıların STRING döndüğü unutulmamalı.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def normalise_subtitle_numeric(name, value):
    """Sayısal altyazı ayarını GÜVENLİ ve hazır bir değere çevirir.

    Kurallar:

    1. Bozuk değer (string, `None`, NaN, ±sonsuz, liste) → ürün
       varsayılanı.
    2. Aralık dışındaki eski kayıt → en yakın alt/üst SINIRA çekilir.
    3. Aralık içindeki fakat listede olmayan değer → en yakın hazır
       değere yuvarlanır. **Eşit uzaklıkta KÜÇÜK olan seçilir**
       (kullanıcı için daha az agresif sonuç; `1.20` → `1.15`,
       `2.75` → `2.5`, `-0.125` → `-0.25`).
    4. `sub_pos` hazır listeye bağlı değildir; yalnız 0–100 arasına
       kırpılır.
    5. Tanınmayan ad olduğu gibi float'a çevrilir.
    """
    number = _finite(value)
    if number is None:
        try:
            return _numeric_default(name)
        except KeyError:
            return 0.0
    if name in NUMERIC_RANGES:
        low, high = NUMERIC_RANGES[name]
        return float(min(max(number, low), high))
    presets = NUMERIC_PRESETS.get(name)
    if not presets:
        return float(number)
    if number <= presets[0]:
        return float(presets[0])
    if number >= presets[-1]:
        return float(presets[-1])
    # Eşitlikte KÜÇÜK olanı seçmek için karşılaştırma katı ">" ile yapılır
    # ve liste artan sırada gezilir.
    best = presets[0]
    best_gap = abs(number - best)
    for candidate in presets[1:]:
        gap = abs(number - candidate)
        if gap < best_gap:
            best, best_gap = candidate, gap
    return float(best)

# Şema işareti: eski `#RRGGBBAA` kayıtları TAM BİR KEZ dönüştürülür.
SCHEMA_KEY = "subtitle/style_schema_version"
STYLE_SCHEMA_VERSION = 2

# Kullanıcıya gösterilen tek güvenli mesaj: ham hata, traceback veya yol
# taşımaz.
APPLY_ERROR_MESSAGE = tr_mark(
    "Altyazı ayarları uygulanamadı. Önceki ayarlar korundu, lütfen tekrar deneyin.")


# Görüntü tabanlı (bitmap) altyazılar MPV'de metin stiliyle
# değiştirilemez; renk/kenarlık ayarları bu parçalara UYGULANMAZ.
BITMAP_SUB_CODECS = frozenset({
    "hdmv_pgs_subtitle", "pgs", "dvd_subtitle", "dvdsub", "vobsub",
    "dvb_subtitle", "dvbsub", "dvb_teletext", "xsub",
})
BITMAP_STYLE_NOTICE = tr_mark(
    "Seçili altyazı görüntü tabanlı olduğu için renk, arka plan ve "
    "kenarlık ayarları bu parçaya uygulanmaz.")


def is_bitmap_subtitle(codec):
    """Verilen codec metin stiliyle değiştirilemeyen bir bitmap mi?"""
    if not isinstance(codec, str):
        return False
    return codec.strip().lower() in BITMAP_SUB_CODECS


def selected_subtitle_codec(track_list, sid=None):
    """Seçili altyazı parçasının codec'i; bulunamazsa None."""
    for track in track_list or []:
        if not isinstance(track, dict) or track.get("type") != "sub":
            continue
        if sid is not None:
            if track.get("id") == sid:
                return track.get("codec")
            continue
        if track.get("selected"):
            return track.get("codec")
    return None


def style_notice(track_list, sid=None):
    """Kullanıcıya gösterilecek güvenli bilgi; gerekmiyorsa boş metin.

    Codec okunamıyorsa SESSİZ kalınır: sahte başarı da, asılsız uyarı da
    üretilmez.
    """
    codec = selected_subtitle_codec(track_list, sid)
    return (translate_marked(BITMAP_STYLE_NOTICE)
            if is_bitmap_subtitle(codec) else "")


def qcolor_to_mpv_argb(color):
    """QColor → canonical `#AARRGGBB` (büyük harf)."""
    if not isinstance(color, QColor) or not color.isValid():
        return "#FF000000"
    return (f"#{color.alpha():02X}{color.red():02X}"
            f"{color.green():02X}{color.blue():02X}")


def mpv_argb_to_qcolor(value, fallback="#FF000000"):
    """Canonical `#AARRGGBB` (veya `#RRGGBB`) → QColor.

    TAHMİN YAPILMAZ: 8 haneli değer her zaman ARGB okunur. Eski
    `#RRGGBBAA` kayıtları yalnız `legacy_rgba_to_mpv_argb()` ile,
    migrasyon sırasında dönüştürülür.
    """
    parsed = _parse_argb(value)
    if parsed is not None:
        return QColor(parsed[1], parsed[2], parsed[3], parsed[0])
    parsed = _parse_argb(fallback)
    if parsed is not None:
        return QColor(parsed[1], parsed[2], parsed[3], parsed[0])
    return QColor(0, 0, 0, 255)


def _parse_argb(value):
    """`#AARRGGBB` veya `#RRGGBB` → (a, r, g, b); geçersizse None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith("#"):
        return None
    digits = text[1:]
    if len(digits) not in (6, 8):
        return None
    try:
        parts = [int(digits[i:i + 2], 16) for i in range(0, len(digits), 2)]
    except ValueError:
        return None
    if len(parts) == 3:
        return (255, parts[0], parts[1], parts[2])
    return tuple(parts)


def legacy_rgba_to_mpv_argb(value):
    """Eski `#RRGGBBAA` kaydı → canonical `#AARRGGBB`. Uygun değilse None.

    YALNIZ migrasyonda çağrılır; normal okuma yolu bu tahmini yapmaz.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith("#") or len(text) != 9:
        return None
    try:
        red, green, blue, alpha = [int(text[i:i + 2], 16)
                                   for i in range(1, 9, 2)]
    except ValueError:
        return None
    return f"#{alpha:02X}{red:02X}{green:02X}{blue:02X}"


def color_alpha(value):
    """Canonical değerin alfası; okunamıyorsa 0."""
    parsed = _parse_argb(value)
    return parsed[0] if parsed else 0


def border_style_for(back_color):
    """Arka plan alfası > 0 ise gerçek kutu, değilse güvenli varsayılan."""
    return BACKGROUND_BOX if color_alpha(back_color) > 0 else OUTLINE_AND_SHADOW


def _canonical(value):
    if isinstance(value, QColor):
        return qcolor_to_mpv_argb(value)
    parsed = _parse_argb(value)
    if parsed is None:
        return "#FF000000"
    return f"#{parsed[0]:02X}{parsed[1]:02X}{parsed[2]:02X}{parsed[3]:02X}"


def style_properties(values):
    """Kullanıcı seçimlerinden MPV'ye yazılacak TAM özellik sözlüğü.

    Türetilen alanlar (`sub_border_style`, `sub_shadow_offset`,
    `sub_ass_override`) burada belirlenir; çağıran taraf tahmin etmez.
    """
    props = {}
    for key in NUMBER_KEYS:
        if key in values:
            # SINIR SAVUNMASI: dialog atlansa veya eski bir kayıt doğrudan
            # verilse bile aşırı değer MPV'ye ulaşmaz.
            props[key] = normalise_subtitle_numeric(key, values[key])
    for key in COLOR_KEYS:
        if key in values:
            props[key] = _canonical(values[key])
    back = props.get("sub_back_color", "#00000000")
    props["sub_border_style"] = border_style_for(back)
    props["sub_shadow_offset"] = (BACKGROUND_BOX_SHADOW_OFFSET
                                  if props["sub_border_style"] == BACKGROUND_BOX
                                  else 0.0)
    # ASS altyazıda normal seçeneklerin uygulanması için tek geçerli değer.
    props["sub_ass_override"] = ASS_OVERRIDE_FORCE
    return props


def _settings_ok(settings):
    """`sync()` sonrası backend durumu; hata başarı gibi raporlanmaz."""
    sync = getattr(settings, "sync", None)
    if callable(sync):
        try:
            sync()
        except Exception:
            return False
    status = getattr(settings, "status", None)
    if not callable(status):
        return True
    try:
        value = status()
    except Exception:
        return False
    name = getattr(value, "name", None)
    return (name or str(value)) in ("NoError", "0")


def _capture_settings(settings, keys):
    state = {}
    for key in keys:
        try:
            existed = bool(settings.contains(key))
            state[key] = (existed, settings.value(key) if existed else None)
        except Exception:
            state[key] = (False, None)
    return state


def _restore_settings(settings, state):
    for key, (existed, value) in state.items():
        try:
            if existed:
                settings.setValue(key, value)
            else:
                settings.remove(key)
        except Exception:
            # Geri alma en iyi çaba ile yapılır; ikinci hata yutulur ki
            # kalan anahtarlar da denensin.
            continue


def _restore_mpv(mpv, previous):
    for name, (existed, value) in previous.items():
        if not existed:
            continue
        try:
            setattr(mpv, name, value)
        except Exception:
            continue


def atomic_apply(mpv, settings, values):
    """Stili ya TAMAMEN uygular ya da hiç uygulamaz.

    Dönüş: `(ok, error)`. `ok=False` iken MPV özellikleri ve QSettings
    anahtarları çağrı öncesi hâline döndürülür; dialog sahte başarıyla
    kapanmamalıdır.

    `sub_delay` politikası korunur: MPV'ye uygulanır ama oturumlar
    arasında 0 saklanır.
    """
    props = style_properties(values)
    stored = {f"{SETTINGS_PREFIX}{name}":
              (0.0 if name == "sub_delay" else value)
              for name, value in props.items()}
    stored[SCHEMA_KEY] = STYLE_SCHEMA_VERSION

    previous_mpv = {}
    for name in props:
        try:
            previous_mpv[name] = (True, getattr(mpv, name))
        except Exception:
            previous_mpv[name] = (False, None)
    previous_settings = _capture_settings(settings, stored)

    try:
        for name, value in props.items():
            setattr(mpv, name, value)
        for key, value in stored.items():
            settings.setValue(key, value)
        if not _settings_ok(settings):
            raise OSError("settings_backend_error")
    except Exception as exc:
        _restore_mpv(mpv, previous_mpv)
        _restore_settings(settings, previous_settings)
        return False, exc
    return True, None


def migrate_settings(settings):
    """Eski `#RRGGBBAA` kayıtlarını TAM BİR KEZ canonical ARGB'ye çevirir.

    - Şema işareti güncelse hiçbir şey yapılmaz (idempotent).
    - Yalnız GERÇEKTEN var olan anahtarlar dönüştürülür; eksik anahtar
      icat edilmez, varsayılan yanlışlıkla migrate edilmez.
    - Yazma hatasında ayarlar yarım kalmaz; önceki hâl geri yüklenir ve
      şema işareti yazılmaz.

    Dönüş: gerçekten bir değişiklik yapıldıysa True.
    """
    try:
        current = int(settings.value(SCHEMA_KEY, 0) or 0)
    except (TypeError, ValueError):
        current = 0
    if current >= STYLE_SCHEMA_VERSION:
        return False

    planned = {}
    for name in COLOR_KEYS:
        key = f"{SETTINGS_PREFIX}{name}"
        try:
            if not settings.contains(key):
                continue
            converted = legacy_rgba_to_mpv_argb(settings.value(key))
        except Exception:
            continue
        if converted is not None:
            planned[key] = converted

    override_key = f"{SETTINGS_PREFIX}sub_ass_override"
    try:
        has_override = bool(settings.contains(override_key))
    except Exception:
        has_override = False
    if has_override:
        raw = settings.value(override_key)
        enabled = str(raw).strip().lower() in ("1", "true", "yes", "force")
        planned[override_key] = (ASS_OVERRIDE_FORCE if enabled
                                 else ASS_OVERRIDE_OFF)

    keys = set(planned) | {SCHEMA_KEY}
    previous = _capture_settings(settings, keys)
    try:
        for key, value in planned.items():
            settings.setValue(key, value)
        settings.setValue(SCHEMA_KEY, STYLE_SCHEMA_VERSION)
        if not _settings_ok(settings):
            raise OSError("settings_backend_error")
    except Exception:
        _restore_settings(settings, previous)
        return False
    return bool(planned)
