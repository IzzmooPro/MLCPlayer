"""Ayrı süreçte libmpv ile güvenli bir video karesi çıkarır."""

import os
import time
import uuid

# Duration okunamayan dosyalarda kullanılan güvenli mutlak konum. Yüzde
# tabanlı seek burada anlamsızdır (toplam süre bilinmiyor).
FALLBACK_SEEK_SECONDS = 10
# Kare/zaman hazır olana kadar beklenecek üst sınır (toplam bütçeyi aşmaz).
READY_BUDGET_S = 4.0
# Seek sonrasi karenin GERCEKTEN decode edilmesi icin kisa oynatma.
FRAME_DECODE_S = 0.5


def _read(player, name):
    """MPV özelliğini güvenle okur; okunamayan değer `None` sayılır."""
    try:
        return getattr(player, name)
    except Exception:
        return None


def _video_tracks(player):
    tracks = _read(player, "track_list") or []
    return [track for track in tracks
            if isinstance(track, dict) and track.get("type") == "video"]


def generate_thumbnail(media_path, output_path, timeout_s=8.0):
    """Tek kare üretir. 0 = başarı; sıfır olmayan değer başarısızlıktır.

    Hazır olma koşulu YALNIZCA `duration > 0` değildir: bazı dosyalarda
    (ör. çift katmanlı DV/HEVC) süre gelmese de video akışı vardır. Karar
    akışı: dosya yüklendi mi → video track var mı → süre biliniyorsa %10'a,
    bilinmiyorsa güvenli mutlak saniyeye seek → kare hazır olunca
    `screenshot-to-file` → dosya gerçekten oluştuysa atomik taşıma.
    """
    import mpv

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temporary = output_path + f".{uuid.uuid4().hex}.tmp.jpg"
    player = None
    try:
        # NOT: `audio="no"` KULLANILMAZ. Bazı dosyalarda bu seçenek mpv'nin
        # hiçbir akışı seçmemesine yol açıyor ("no audio or video data
        # played", boş `track_list`). Ses yalnızca ÇIKIŞ seviyesinde
        # kapatılır; parça seçimi bozulmaz.
        player = mpv.MPV(
            vo="null", ao="null", mute="yes", hwdec="no", screenshot_sw="yes",
            screenshot_format="jpg", screenshot_jpeg_quality=78,
            config=False, input_default_bindings=False,
            input_vo_keyboard=False, osc=False,
        )
        player.play(media_path)
        deadline = time.monotonic() + timeout_s

        # 1) Video akışı var mı? (duration'dan BAĞIMSIZ)
        duration = 0.0
        tracks = []
        while time.monotonic() < deadline:
            try:
                duration = float(_read(player, "duration") or 0.0)
            except (TypeError, ValueError):
                duration = 0.0
            tracks = _video_tracks(player)
            if tracks or duration > 0:
                break
            time.sleep(0.05)
        if not tracks:
            return 2

        # 2) Video parçasını AÇIKÇA seç. Bazı dosyalarda (ör. çift katmanlı
        # DV/HEVC + mjpeg kapak) mpv'nin otomatik seçimi hiçbir video
        # seçmiyor (`vid=False`) ve `screenshot-to-file` "Taking screenshot
        # failed" ile düşüyordu.
        try:
            player.vid = tracks[0].get("id", 1)
        except Exception:
            pass

        # 3) Süre biliniyorsa yüzde, bilinmiyorsa güvenli mutlak seek.
        if duration > 0:
            player.command("seek", "10", "absolute-percent", "exact")
        else:
            player.command("seek", str(FALLBACK_SEEK_SECONDS), "absolute",
                           "exact")

        # 4) ÇÖZÜLMÜŞ kare hazır olana kadar sınırlı bekleme. Yalnız
        # `dwidth` yeterli değildir: seek sonrası kare gerçekten decode
        # edilmeden `screenshot-to-file` "Taking screenshot failed" veriyor.
        # Bu yüzden kısa süre oynatılır, sonra tekrar duraklatılır.
        ready_deadline = min(deadline, time.monotonic() + READY_BUDGET_S)
        frame_ready = False
        while time.monotonic() < ready_deadline:
            if _read(player, "dwidth") or _read(player, "width"):
                frame_ready = True
                break
            time.sleep(0.05)
        if not frame_ready:
            return 2
        try:
            player.pause = False
            time.sleep(FRAME_DECODE_S)
            player.pause = True
        except Exception:
            pass

        player.command("screenshot-to-file", temporary, "video")

        # 5) Dosya GERÇEKTEN oluştuysa atomik taşıma.
        while time.monotonic() < deadline:
            if os.path.isfile(temporary) and os.path.getsize(temporary) > 0:
                os.replace(temporary, output_path)
                return 0
            time.sleep(0.05)
        return 3
    except Exception:
        return 1
    finally:
        if player is not None:
            try:
                player.terminate()
            except Exception:
                pass
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass
