"""TEK bir medya dosyasinin track_list'ini sinirli sekilde okur.

- `vo=null`, `ao=null`: pencere acilmaz, hoparlorden ses CIKMAZ.
- Yalniz metadata okunur; oynatma, donusturme, kopyalama, indirme YOK.
- Sonuc tek satir JSON olarak `PROBE_JSON ...` seklinde basilir.
- Opt-in: `MLC_MEDIA_PROBE=1` gerekir; normal pytest bu dosyayi
  toplamaz (adi `test_` ile baslamaz) ve calistirmaz.

Cagiran taraf bu child'i KENDI baslattigi PID ile ve timeout'la
yonetir (bkz. `tests/find_subtitle_free_media.py`).
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# libmpv, urunun kullandigi `bin/` dizininden yuklenir (bkz. main.py).
_BIN = os.path.join(ROOT, "bin")
os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")
try:
    _dll_dir_handle = os.add_dll_directory(_BIN)
except Exception:
    _dll_dir_handle = None

from tests.media_probe_rules import count_tracks  # noqa: E402


def probe(path, deadline_s):
    summary = {"path": path, "loaded": False, "duration": 0.0,
               "video_tracks": 0, "audio_tracks": 0, "sub_tracks": 0,
               "error": ""}
    if not os.path.isfile(path):
        summary["error"] = "not_a_file"
        return summary
    import mpv
    player = mpv.MPV(vo="null", ao="null", audio_display="no",
                     idle=True, pause=True, terminal=False)
    try:
        player.play(path)
        end = time.time() + deadline_s
        while time.time() < end:
            try:
                duration = player.duration or 0.0
                tracks = player.track_list or []
            except Exception:
                duration, tracks = 0.0, []
            video = count_tracks(tracks, "video")
            if duration > 0 and video > 0:
                # track_list stabil hale gelsin diye kisa bir ek bekleme.
                time.sleep(0.4)
                tracks = player.track_list or []
                summary.update({
                    "loaded": True,
                    "duration": float(player.duration or duration),
                    "video_tracks": count_tracks(tracks, "video"),
                    "audio_tracks": count_tracks(tracks, "audio"),
                    "sub_tracks": count_tracks(tracks, "sub"),
                })
                return summary
            time.sleep(0.2)
        summary["error"] = "timeout_no_tracks"
        return summary
    except Exception as exc:
        summary["error"] = type(exc).__name__
        return summary
    finally:
        try:
            player.stop()
        except Exception:
            pass
        try:
            player.terminate()
        except Exception:
            pass


def main():
    if os.environ.get("MLC_MEDIA_PROBE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--seconds", type=float, default=12.0)
    args = parser.parse_args()
    summary = probe(args.path, args.seconds)
    print("PROBE_JSON " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    # Qt yok, ama libmpv finalizasyon riski icin urunle ayni cikis
    # politikasi: butun ciktilar flush edildikten SONRA cik.
    os._exit(main())
