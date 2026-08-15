"""Video açılışında aynı klasördeki eşleşen SRT'yi SESSİZ etkinleştirme.

Sözleşme `docs/PROJECT_STATUS.md` içindeki 14 Ağustos 2026 araştırmasıdır ve
teknik kaynağı mpv'nin `sub-auto=exact` davranışıdır.

Bu modül `SubtitleTrackWatcher`'dan AYRIDIR: watcher yalnız altyazının güvenli
bandından sorumludur, buraya seçim mantığı doldurulmaz. Etkinleştirme her medya
için TEK ATIMLIKTIR; yeni timer veya polling döngüsü eklenmez.

Ad eşleştirme yalnız tam video gövdesi üzerinden yapılır:

    Film.2026.mkv -> Film.2026.srt
                     Film.2026.tr.srt / Film.2026.tur.srt
                     Film.2026.tr.forced.srt / Film.2026.tr.sdh.srt

`Film.srt`, `Başka Film.srt` ve `Film.2026 Türkçe.srt` aday DEĞİLDİR.
"""
import os
import re

from app.errors import safe_console

SUBTITLE_SUFFIX = ".srt"

# mpv'nin tanıdığı etiketler; dil kodundan sonra gelebilir.
SUBTITLE_TAGS = ("forced", "default", "sdh", "hi", "cc")

# Altyazı Merkezi'nin kayıtlı dili -> ISO sonekleri.
LANGUAGE_SUFFIXES = {
    "Türkçe": ("tr", "tur"),
    "İngilizce": ("en", "eng"),
    "Almanca": ("de", "ger", "deu"),
    "Fransızca": ("fr", "fre", "fra"),
    "İspanyolca": ("es", "spa"),
}

# ISO 639-1/2 ve IETF biçimi (`tr`, `tur`, `pt-br`).
_LANGUAGE_TOKEN = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,4})?$")

_URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def is_local_media(path):
    """URL değil, gerçekten var olan yerel dosya mı?"""
    if not path or _URL_SCHEME.match(str(path)):
        return False
    return os.path.isfile(path)


def _suffix_tokens(name, stem):
    """`name` gövdesi `stem` ile başlıyorsa kalan noktalı parçaları verir.

    Tam eşleşmede boş liste, aday değilse `None` döner. Boşlukla ayrılmış
    ekler (`Film.2026 Türkçe`) aday sayılmaz: ayraç yalnız noktadır.
    """
    lowered = name.lower()
    base = stem.lower()
    if lowered == base:
        return []
    if not lowered.startswith(base + "."):
        return None
    return lowered[len(base) + 1:].split(".")


def _is_language(token):
    """İlk ek MUTLAKA dil kodudur; etiket adı dil yerine geçmez."""
    return token not in SUBTITLE_TAGS and bool(_LANGUAGE_TOKEN.match(token))


def _suffixes_match_exact(tokens):
    """mpv `sub-auto=exact` sözleşmesi: `<dil>[.<etiket>...]`.

    `Film.tr.srt`, `Film.tur.srt`, `Film.tr.sdh.srt`, `Film.tr.forced.srt`
    kabul; `Film.sdh.srt`, `Film.forced.srt`, `Film.sdh.tr.srt` REDDEDİLİR.
    """
    if not tokens:
        return True
    if not _is_language(tokens[0]):
        return False
    return all(token in SUBTITLE_TAGS for token in tokens[1:])


def subtitle_candidates(video_path):
    """Videonun GERÇEK klasöründeki sözleşmeye uyan `.srt` yolları.

    Sonuç deterministiktir (doğal ad sırası); klasörün ham sırasına güvenilmez.
    """
    if not is_local_media(video_path):
        return []
    folder = os.path.dirname(os.path.abspath(video_path))
    stem = os.path.splitext(os.path.basename(video_path))[0]
    try:
        entries = sorted(os.listdir(folder))
    except OSError as e:
        safe_console(f"Altyazı klasörü okunamadı: {type(e).__name__}")
        return []
    found = []
    for entry in entries:
        body, extension = os.path.splitext(entry)
        if extension.lower() != SUBTITLE_SUFFIX:
            continue
        tokens = _suffix_tokens(body, stem)
        if tokens is None or not _suffixes_match_exact(tokens):
            continue
        found.append(os.path.join(folder, entry))
    return found


def _priority(path, stem, wanted):
    """Küçük değer önce: düz ad, kayıtlı dil, kalanlar."""
    body = os.path.splitext(os.path.basename(path))[0]
    tokens = _suffix_tokens(body, stem) or []
    if not tokens:
        return 0
    if wanted and tokens[0] in wanted:
        return 1
    return 2


def choose_subtitle(video_path, language=None, candidates=None):
    """Sözleşmeye uyan TEK adayı seçer; aday yoksa `None`."""
    paths = subtitle_candidates(video_path) if candidates is None else list(candidates)
    if not paths:
        return None
    stem = os.path.splitext(os.path.basename(video_path))[0]
    wanted = LANGUAGE_SUFFIXES.get(str(language or "").strip(), ())
    # Eşit öncelikte doğal ad sırası: aynı klasör her zaman aynı sonucu verir.
    return sorted(paths, key=lambda p: (_priority(p, stem, wanted),
                                        os.path.basename(p).lower()))[0]


def verified_track_id(track_list, target):
    """`track-list` içinde DOĞRULANMIŞ dış SRT track'inin `sid` değeri.

    `external=True`, uzantı `.srt` ve `external-filename` tam aday yolu
    olmadan hiçbir track kabul edilmez; yalnız ada bakarak seçim yapılmaz.
    """
    wanted = os.path.normcase(os.path.abspath(str(target)))
    for track in (track_list or []):
        if not isinstance(track, dict) or track.get("type") != "sub":
            continue
        if not track.get("external"):
            continue
        name = track.get("external-filename")
        if not name:
            continue
        if os.path.splitext(str(name))[1].lower() != SUBTITLE_SUFFIX:
            continue
        if os.path.normcase(os.path.abspath(str(name))) == wanted:
            return track.get("id")
    return None


STATE_PENDING = "pending"
STATE_DONE = "done"


def suppress_local_subtitle(player):
    """Açık kullanıcı seçimi bu medya için otomatik seçimi TÜKETİR.

    Yalnız BAŞARILI manuel/sürükle-bırak etkinleştirmesinden sonra çağrılır;
    başarısız bırakma otomatik altyazıyı engellemez.
    """
    player._auto_local_subtitle_file = getattr(player, "current_file", "")
    player._auto_local_subtitle_state = STATE_DONE
    player._auto_local_subtitle_target = None


def _reset_state_for(player, path):
    """Medya değişti: durum sıfırlanır ve hedef BİR KEZ hesaplanır."""
    player._auto_local_subtitle_file = path
    player._auto_local_subtitle_target = choose_subtitle(
        path, language=_saved_language(player))
    # Aday yoksa karar tamamlanmıştır; klasör her turda yeniden taranmaz.
    player._auto_local_subtitle_state = (
        STATE_PENDING if player._auto_local_subtitle_target else STATE_DONE)


def activate_local_subtitle(player):
    """Yüklenen medyanın yerel SRT'sini SESSİZCE seçer ve görünür yapar.

    Durum modeli medya başınadır: aday yoksa `done`, aday var ama doğrulanmış
    track henüz yoksa `pending`, seçim yapıldıysa `done`. `pending` sırasında
    klasör ve kayıtlı dil YENİDEN OKUNMAZ; her `update_ui` turunda yalnız ucuz
    `track-list` doğrulaması yapılır. Yeni timer, sleep veya ayrı polling
    döngüsü yoktur. Başarı tamamen sessizdir; OSD/pencere/durum yazısı olmaz.
    """
    path = getattr(player, "current_file", "")
    if not is_local_media(path):
        return False
    if float(getattr(player, "duration", 0) or 0) <= 0:
        return False
    mpv = getattr(player, "mpv_player", None)
    if mpv is None:
        return False
    try:
        if getattr(player, "_auto_local_subtitle_file", None) != path:
            _reset_state_for(player, path)
        if getattr(player, "_auto_local_subtitle_state", None) != STATE_PENDING:
            return False
        target = getattr(player, "_auto_local_subtitle_target", None)
        sid = verified_track_id(getattr(mpv, "track_list", None), target)
        if sid is None:
            # Track GEÇ gelebilir; karar tamamlanmaz, durum `pending` kalır.
            return False
        mpv.sid = sid
        mpv.sub_visibility = True
        player._auto_local_subtitle_state = STATE_DONE
    except Exception as e:
        # Otomatik yükleme hatası videoyu KESMEZ; yalnız maskelenmiş log.
        safe_console(f"Yerel altyazı etkinleştirilemedi: {type(e).__name__}")
        player._auto_local_subtitle_state = STATE_DONE
        return False
    refresh = getattr(getattr(player, "video_frame", None),
                      "_update_overlay_subtitle_state", None)
    if callable(refresh):
        try:
            refresh()
        except Exception:
            pass
    return True


def _saved_language(player):
    """Altyazı Merkezi'nin kayıtlı dili; okunamazsa ürün varsayılanı."""
    language = getattr(player, "subtitle_language", None)
    if language:
        return language
    try:
        from app.subtitle_settings import DEFAULT_LANGUAGE, SubtitleSettingsStore

        return SubtitleSettingsStore().load().get("language", DEFAULT_LANGUAGE)
    except Exception:
        return None
