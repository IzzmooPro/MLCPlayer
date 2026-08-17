# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazı Merkezi çekirdeği: hedef ad, atomik yazma ve MPV track yaşam döngüsü.

KESİN ADLANDIRMA KURALI
-----------------------
İndirilen altyazının adı, video dosyasının uzantısız adıyla BİREBİR aynıdır:

    Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv
    Resident.Alien.S01E01.Pilot.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.srt

OpenSubtitles sonucundaki dosya adı KULLANILMAZ. `.tr.srt`, `.1.srt`,
`(1).srt` gibi türevler üretilmez ve dosya adına dil kodu eklenmez.

Bu modül ağ katmanından bağımsızdır; yalnızca yerel dosya ve MPV işlerini
yapar. Ağ tarafı için bkz. `app/opensubtitles.py`.
"""
import os
import re
import struct
import tempfile
import time

SUBTITLE_EXTENSION = ".srt"

# `apply()` track_list'in güncellenmesini beklerken kullanılan VARSAYILAN
# bütçe. Qt entegrasyonu kendi `wait` geri çağrısını verdiğinde hiç
# `time.sleep` çağrılmaz; bu bütçe yalnız UI dışı çağrılar içindir.
TRACK_WAIT_ATTEMPTS = 40
TRACK_WAIT_INTERVAL_S = 0.01


def _close_deferred(player):
    """`close()` isteği ERTELENDİ mi? (pencere hâlâ görünür)

    Altyazı Merkezi'nde çalışan iş varsa ürünün `closeEvent`'i kapanışı
    erteler ve `event.ignore()` yapar. Bunu "kapandı" saymak, MPV
    referansının çalışan iş sürerken bırakılmasına yol açardı.
    """
    is_visible = getattr(player, "isVisible", None)
    if not callable(is_visible):
        return False
    try:
        return bool(is_visible())
    except Exception:
        return False


def shutdown_player(player):
    """MPV/Qt kapanışının TEK kanonik sahibi.

    `stop()` çağrılır, ardından `close()` yapılır. `terminate()` BURADA
    çağrılmaz; onu ürünün `closeEvent`'i tek başına yönetir. Böylece aynı
    MPV nesnesi iki kez terminate edilmez.

    Kapanış ERTELENİRSE (bkz. `_close_deferred`) işlem TAMAMLANMIŞ SAYILMAZ:
    `False` döner ve MPV referansı KORUNUR. Sonraki çağrı kaldığı yerden
    devam eder; `stop()` yine de yalnız bir kez çağrılır.
    """
    # İDEMPOTENT: tamamlanmış kapanışta ikinci çağrı hiçbir şey yapmaz,
    # aksi halde closeEvent yeniden çalışıp terminate() ikinci kez çağrılırdı.
    if getattr(player, "_mlc_shutdown_done", False):
        return False

    # stop() EN FAZLA BİR KEZ; erteleme nedeniyle tekrar çağrılmaz.
    if not getattr(player, "_mlc_stop_done", False):
        try:
            player._mlc_stop_done = True
        except Exception:
            pass
        mpv = getattr(player, "mpv_player", None)
        if mpv is not None:
            try:
                mpv.stop()
            except Exception:
                pass

    close = getattr(player, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass

    if _close_deferred(player):
        # Henüz kapanmadı: sahiplik SÜRÜYOR, referans bırakılmaz.
        return False

    try:
        player._mlc_shutdown_done = True
    except Exception:
        pass
    # İkinci çağrıda tekrar terminate edilmesin diye referans ayrılır.
    try:
        player.mpv_player = None
    except Exception:
        pass
    return True

# 1) "1\n00:00:01,000 --> 00:00:02,000" biçimli gerçek SRT imzası.
_SRT_CUE = re.compile(
    r"^\s*\d+\s*\r?\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
    re.MULTILINE)
_SERIES_PATTERNS = (
    re.compile(r"[.\s_-]s(\d{1,2})e(\d{1,3})", re.IGNORECASE),
    re.compile(r"[.\s_-](\d{1,2})x(\d{1,3})[.\s_-]", re.IGNORECASE),
)
_YEAR = re.compile(r"[.\s(_-](19\d{2}|20\d{2})[.\s)_-]")
_NOISE = re.compile(
    r"\b(2160p|1080p|720p|480p|4k|uhd|hdr10|hdr|dv|web[-\s.]?dl|webrip|bluray|"
    r"bdrip|hdtv|remux|x264|x265|h\.?264|h\.?265|hevc|aac|ac3|dts(?:-hd)?|"
    r"ddp?5\.1|atmos|amzn|nf|dsnp|hybrid|proper|repack|extended)\b",
    re.IGNORECASE)


class SubtitleWriteError(Exception):
    """Altyazı dosyası güvenli biçimde yazılamadı."""


class NotSrtError(Exception):
    """İçerik gerçek bir SRT değil (ASS/VTT/ikili içerik uzantı değiştirilerek
    SRT yapılmaz)."""


class SubtitleEncodingError(NotSrtError):
    """İçerik bilinen kodlamalarla Unicode'a çözülemedi.

    `NotSrtError`'ın özel bir nedenidir: çözülemeyen içerik zaten geçerli bir
    SRT olamaz, bu yüzden çağıranlar tek bir `except NotSrtError` ile ikisini
    de yakalayabilir.
    """


class ConfirmationRequiredError(Exception):
    """Hedefte MLC'ye ait olmayan bir dosya var ve onay geri çağrısı yok.

    Fail-closed: onay mekanizması sağlanmadan yabancı dosya ASLA ezilmez.
    """


# Girdi bayt dizisi bu sırayla çözülür; hedef daima UTF-8 yazılır.
_DECODE_ORDER = ("utf-8-sig", "cp1254", "iso-8859-9")


def decode_subtitle_bytes(data):
    """Altyazı baytlarını Unicode'a çözer (BOM normalize edilir)."""
    if data is None:
        raise SubtitleEncodingError("Boş altyazı içeriği.")
    for encoding in _DECODE_ORDER:
        try:
            text = data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        # Çözülebilmiş ama kontrol karakteriyle dolu içerik gerçek altyazı
        # değildir; sessizce bozuk metin yazmaktansa reddedilir.
        if "\x00" in text:
            continue
        return text.lstrip("﻿")
    raise SubtitleEncodingError(
        "Altyazı içeriğinin karakter kodlaması çözülemedi.")


def subtitle_target_path(video_path, remote_name=None):
    """Video yolundan KESİN altyazı hedefini üretir.

    `remote_name` yalnızca API sonucundaki adın YOK SAYILDIĞINI açıkça
    belgelemek için kabul edilir; hedefi etkilemez. Dil kodu parametresi
    bilinçli olarak YOKTUR.
    """
    directory = os.path.dirname(os.path.abspath(video_path))
    stem = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(directory, stem + SUBTITLE_EXTENSION)


def is_srt_text(text):
    if text.lstrip().upper().startswith("WEBVTT"):
        return False
    if "[Script Info]" in text or "Dialogue:" in text:
        return False
    return bool(_SRT_CUE.search(text))


def is_srt_bytes(data):
    """İçerik gerçek SRT mi? (yalnızca ilk sürüm: SRT kabul edilir)"""
    if not data:
        return False
    try:
        return is_srt_text(decode_subtitle_bytes(data))
    except SubtitleEncodingError:
        return False


def parse_release(video_path):
    """Dosya adından dizi/film bilgisini ayrıştırır (S01E01 dâhil)."""
    name = os.path.splitext(os.path.basename(video_path))[0]
    season = episode = None
    cut = len(name)
    for pattern in _SERIES_PATTERNS:
        match = pattern.search(name)
        if match:
            season, episode = int(match.group(1)), int(match.group(2))
            cut = min(cut, match.start())
            break

    year = None
    year_match = _YEAR.search(name)
    if year_match and season is None:
        year = int(year_match.group(1))
        cut = min(cut, year_match.start())

    title = name[:cut]
    title = _NOISE.sub(" ", title)
    title = re.sub(r"[._]+", " ", title)
    title = re.sub(r"\s{2,}", " ", title).strip(" -_")
    return {
        "title": title,
        "season": season,
        "episode": episode,
        "is_series": season is not None,
        "year": year,
        "release": name,
    }


def opensubtitles_hash(path):
    """OpenSubtitles 64-bit dosya hash'i (ilk+son 64 KiB + boyut)."""
    chunk = 65536
    size = os.path.getsize(path)
    if size < chunk * 2:
        raise ValueError("Dosya hash için çok küçük")
    value = size
    fmt = "<%dQ" % (chunk // 8)
    with open(path, "rb") as handle:
        for offset in (0, size - chunk):
            handle.seek(offset)
            for piece in struct.unpack(fmt, handle.read(chunk)):
                value = (value + piece) & 0xFFFFFFFFFFFFFFFF
    return "%016x" % value


class SubtitleStore:
    """Atomik yazma + oturum bazlı üzerine yazma onayı."""

    def __init__(self):
        # MLC'nin bu oturumda yazdığı hedefler: tekrar onay istenmez.
        self._owned = set()

    def owns(self, target):
        return os.path.normcase(os.path.abspath(target)) in self._owned

    def _mark_owned(self, target):
        self._owned.add(os.path.normcase(os.path.abspath(target)))

    def save(self, target, data, confirm=None):
        """Gerçek SRT içeriğini hedefe atomik olarak yazar.

        `confirm(target) -> bool` yalnızca hedef ZATEN VARSA ve bu oturumda
        MLC tarafından yazılmamışsa çağrılır. Kullanıcı reddederse dosya
        değişmez ve False döner.
        """
        # 1) Kodlamayı çöz (BOM normalize) — çözülemeyen içerik reddedilir.
        text = decode_subtitle_bytes(data)
        if not is_srt_text(text):
            raise NotSrtError("İndirilen içerik geçerli bir SRT değil.")
        # 2) Hedef DAİMA gerçek UTF-8 yazılır; girdi baytları doğrudan
        #    kopyalanmaz.
        payload = text.encode("utf-8")

        if os.path.exists(target) and not self.owns(target):
            # FAIL-CLOSED: onay geri çağrısı yoksa yabancı dosya ezilmez.
            if confirm is None:
                raise ConfirmationRequiredError(
                    "Hedefte MLC'ye ait olmayan bir altyazı dosyası var; "
                    "üzerine yazmak için kullanıcı onayı gerekir.")
            if not confirm(target):
                return False

        directory = os.path.dirname(os.path.abspath(target)) or "."
        handle = None
        temporary = None
        try:
            os.makedirs(directory, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".mlc-sub-", suffix=".tmp", dir=directory)
            handle = os.fdopen(descriptor, "wb")
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            handle = None
            # Atomik yer değiştirme: yarım dosya görünmez, eski dosya
            # yalnızca yeni içerik tam yazıldıktan sonra değişir.
            os.replace(temporary, target)
            temporary = None
        except Exception as exc:
            raise SubtitleWriteError(
                "Altyazı dosyası kaydedilemedi.") from exc
        finally:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            if temporary and os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except Exception:
                    pass

        self._mark_owned(target)
        return True


class SubtitleSession:
    """MPV altyazı track yaşam döngüsü: tek MLC track, yinelenme yok."""

    def __init__(self, store=None):
        self.store = store or SubtitleStore()
        self._sid = None

    @staticmethod
    def _sub_tracks(mpv):
        try:
            return [t for t in (mpv.track_list or [])
                    if isinstance(t, dict) and t.get("type") == "sub"]
        except Exception:
            return []

    @staticmethod
    def _same_path(a, b):
        if not a or not b:
            return False
        return (os.path.normcase(os.path.abspath(str(a)))
                == os.path.normcase(os.path.abspath(str(b))))

    def _remove_previous(self, mpv, target, keep=None):
        """Önceki MLC track'lerini KALDIRIR.

        Yalnızca bellekteki `self._sid`'e güvenilmez: oturum yeniden
        oluşturulmuş olabilir. Aynı normalized `external-filename` yoluna ait
        bütün track'ler `track_list` üzerinden bulunup kaldırılır.

        `keep` YENİ doğrulanmış track'tir ve asla kaldırılmaz: aynı yol
        yeniden yüklendiğinde eski ve yeni track'in yolu AYNIDIR.
        """
        remover = getattr(mpv, "sub_remove", None)
        if not callable(remover):
            self._sid = None
            return
        victims = []
        for track in self._sub_tracks(mpv):
            identifier = track.get("id")
            if keep is not None and identifier == keep:
                continue
            if self._same_path(track.get("external-filename"), target):
                victims.append(identifier)
        if (self._sid is not None and self._sid != keep
                and self._sid not in victims):
            victims.append(self._sid)
        for sid in victims:
            if sid is None:
                continue
            try:
                remover(sid)
            except Exception:
                pass
        self._sid = None

    def _add_subtitle(self, mpv, target, language=None, title=None):
        """Altyazıyı ekler; mümkünse dil/başlık metadata'sıyla.

        Tercih edilen semantik `sub-add <path> select <title> <lang>`. Eski
        python-mpv sarmalayıcıları veya test double'ları çok argümanlı
        çağrıyı kabul etmeyebilir; bu durumda güvenli tek argümanlı çağrıya
        DÖNÜLÜR. Fallback aynı altyazıyı İKİNCİ kez eklemez: yalnızca
        metadata denemesi sırasında hiçbir track oluşmadıysa çalışır.
        """
        code = str(language or "").strip().lower()
        label = str(title or "").strip()
        if code and not label:
            from app.track_labels import language_name

            label = language_name(code)
        if not (code or label):
            mpv.sub_add(target)
            return

        before = len(self._sub_tracks(mpv))
        try:
            mpv.sub_add(target, "select", label or code, code)
            return
        except TypeError:
            # İmza desteklenmiyor: HİÇBİR çağrı yapılmadı, güvenle geri dön.
            pass
        except Exception:
            # Komut reddedildi. Track gerçekten eklenmediyse fallback yapılır;
            # eklendiyse ikinci kez EKLENMEZ.
            if len(self._sub_tracks(mpv)) > before:
                return
        mpv.sub_add(target)

    def apply(self, player, target, wait=None, attempts=TRACK_WAIT_ATTEMPTS,
              is_cancelled=None, language=None, title=None):
        """İndirilen altyazıyı etkinleştirir: eski MLC track'i kaldırır,
        yenisini ekler, seçer ve görünür yapar.

        NOT: Sıra TRANSACTIONAL'dır — önce eklenip DOĞRULANIR, sonra seçilir
        ve ancak ondan sonra eski track kaldırılır. Aynı yol tekrar
        yüklendiğinde MPV eski içeriği göstermez (yeni track dosyayı yeniden
        okur), ama başarısız bir ekleme ÇALIŞAN altyazıyı yok etmez.

        `is_cancelled()` OPSİYONELDİR ve verilmezse davranış değişmez.
        Verildiğinde her polling turunda kontrol edilir: iptalde bekleme
        derhal biter, hiçbir track seçilmez ve False dönülür. Qt tarafı
        gerçek bekleme sırasında olay işlediği için (kullanıcı dialogu
        kapatabilir) bu kontrol gereklidir.
        """
        def cancelled():
            if not callable(is_cancelled):
                return False
            try:
                return bool(is_cancelled())
            except Exception:
                return False

        mpv = getattr(player, "mpv_player", None)
        if mpv is None:
            return False
        if cancelled():
            return False
        # TRANSACTIONAL: eski track'e doğrulamadan ÖNCE dokunulmaz. Ekleme
        # veya doğrulama başarısız olursa çalışan altyazı yerinde kalır.
        # `known` eski aynı-yol track'ini de içerir; bu yüzden aşağıdaki
        # doğrulama YENİ eklenen track'i seçer, eskisini değil.
        known = {track.get("id") for track in self._sub_tracks(mpv)}
        self._add_subtitle(mpv, target, language=language, title=title)

        # track_list GECİKMELİ güncellenebilir. Doğrulanmamış "son track"
        # seçilmez; yalnızca eklenen dosyaya ait GERÇEK id kabul edilir.
        sid = None
        for _ in range(max(1, attempts)):
            if cancelled():
                # İptal: doğrulanmamış track ASLA seçilmez.
                self._refresh_indicator(player)
                return False
            for track in self._sub_tracks(mpv):
                identifier = track.get("id")
                if identifier in known:
                    continue
                if self._same_path(track.get("external-filename"), target):
                    sid = identifier
                    break
            if sid is not None:
                break
            if callable(wait):
                # UI thread yolu: bekleme çağıranın (örn. processEvents)
                # denetimindedir; burada ASLA time.sleep kullanılmaz.
                wait()
            else:
                time.sleep(TRACK_WAIT_INTERVAL_S)

        if sid is None or cancelled():
            # Kimlik doğrulanamadı ya da iş iptal edildi: yanlış track'i
            # seçmektense hiçbir şey seçmeyiz. Görünürlük de zorlanmaz ve
            # ÇALIŞAN eski track'e dokunulmaz.
            self._refresh_indicator(player)
            return False

        # Yalnız doğrulama bittikten SONRA: seç, göster, eskiyi kaldır.
        # Aynı yol yeniden yüklendiğinde de eski içerik böylece kalmaz.
        mpv.sid = sid
        mpv.sub_visibility = True
        self._remove_previous(mpv, target, keep=sid)
        self._sid = sid
        self._refresh_indicator(player)
        return True

    def download_only(self, player, target, data, confirm=None):
        """Dosyayı yazar ama ÇALIŞAN MPV track'ine dokunmaz."""
        return self.store.save(target, data, confirm=confirm)

    def _refresh_indicator(self, player):
        frame = getattr(player, "video_frame", None)
        refresh = getattr(frame, "_update_overlay_subtitle_state", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
