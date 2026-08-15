"""Opt-in TESHIS: libmpv ile tek karelik thumbnail cikarma asamalari.

Urun kodunu DEGISTIRMEZ; yalnizca `app.thumbnail_worker` ile ayni libmpv
yapilandirmasini kurup her asamayi marker'la olcer:

    MARK_MPV_CREATED / MARK_PLAY_CALLED / MARK_FILE_LOADED
    MARK_TRACKS / MARK_DURATION / MARK_TIME_POS / MARK_IDLE
    MARK_END_FILE / MARK_SEEK / MARK_SCREENSHOT / MARK_TEMP_FILE
    MARK_TERMINATE / RESULTS

GUVENLIK: mpv loglari YALNIZ bu teshis surecinin stdout'una yazilir; urun
log dosyalarina veya hata arayuzune gitmez. Video READ-ONLY acilir.

    MLC_NATIVE_SMOKE=1 MLC_THUMB_DIAG_VIDEO=<mkv> \\
        python tests/native_thumbnail_diag_child.py
"""
import os
import sys
import tempfile
import time
import uuid

if os.environ.get("MLC_NATIVE_SMOKE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]

VIDEO = os.environ.get("MLC_THUMB_DIAG_VIDEO", "")
TIMEOUT_S = float(os.environ.get("MLC_THUMB_DIAG_TIMEOUT", "30"))
START = time.time()
events = []


def mark(name, extra=""):
    print(f"{name} t={time.time() - START:.2f} {extra}".rstrip(), flush=True)


def main():
    import mpv

    if not (VIDEO and os.path.isfile(VIDEO)):
        print("RESULTS: failures=no_video (ORTAM EKSIGI)", flush=True)
        return 2

    workdir = tempfile.mkdtemp(prefix="mlc_thumb_diag_")
    temporary = os.path.join(workdir, uuid.uuid4().hex + ".tmp.jpg")
    log_lines = []

    def log_handler(level, component, message):
        if level in ("warn", "error", "fatal"):
            log_lines.append(f"[{level}][{component}] {message.strip()}")

    player = mpv.MPV(
        vo="null", audio="no", hwdec="no", screenshot_sw="yes",
        screenshot_format="jpg", screenshot_jpeg_quality=78,
        config=False, input_default_bindings=False,
        input_vo_keyboard=False, osc=False, log_handler=log_handler,
    )
    mark("MARK_MPV_CREATED", os.path.basename(VIDEO))

    @player.event_callback("file-loaded")
    def _loaded(event):
        events.append("file-loaded")

    @player.event_callback("end-file")
    def _end(event):
        try:
            data = event.as_dict() if hasattr(event, "as_dict") else {}
        except Exception:
            data = {}
        events.append(f"end-file:{data}")

    exit_code = 1
    try:
        player.play(VIDEO)
        mark("MARK_PLAY_CALLED")
        deadline = time.monotonic() + TIMEOUT_S
        loaded = False
        while time.monotonic() < deadline:
            if "file-loaded" in events:
                loaded = True
                break
            time.sleep(0.05)
        mark("MARK_FILE_LOADED", f"loaded={loaded} events={events[:3]}")

        def read(name, default=None):
            try:
                return getattr(player, name)
            except Exception as exc:
                return f"<{type(exc).__name__}>"

        tracks = read("track_list") or []
        video_tracks = [t for t in tracks if isinstance(t, dict)
                        and t.get("type") == "video"]
        mark("MARK_TRACKS",
             f"total={len(tracks)} video={len(video_tracks)} "
             f"first_video={video_tracks[0] if video_tracks else None}")
        mark("MARK_DURATION", f"duration={read('duration')} "
                              f"demuxer_duration={read('demuxer_start_time')}")
        mark("MARK_TIME_POS", f"time_pos={read('time_pos')} "
                              f"percent_pos={read('percent_pos')}")
        mark("MARK_IDLE", f"core_idle={read('core_idle')} "
                          f"idle_active={read('idle_active')} "
                          f"paused_for_cache={read('paused_for_cache')} "
                          f"width={read('width')} height={read('height')} "
                          f"video_format={read('video_format')} "
                          f"estimated_frame_count={read('estimated_frame_count')}")

        # Duration olmadan ABSOLUTE seek denemesi
        seek_error = None
        try:
            player.command("seek", "10", "absolute", "exact")
        except Exception as exc:
            seek_error = f"{type(exc).__name__}"
        pos_deadline = time.monotonic() + 10
        frame_ready = False
        while time.monotonic() < pos_deadline:
            pos = read("time_pos")
            if isinstance(pos, (int, float)) and pos and pos > 0:
                frame_ready = True
                break
            time.sleep(0.05)
        mark("MARK_SEEK", f"error={seek_error} time_pos={read('time_pos')} "
                          f"frame_ready={frame_ready}")

        shot_error = None
        try:
            player.command("screenshot-to-file", temporary, "video")
        except Exception as exc:
            shot_error = f"{type(exc).__name__}"
        mark("MARK_SCREENSHOT", f"error={shot_error}")
        file_deadline = time.monotonic() + 10
        size = 0
        while time.monotonic() < file_deadline:
            if os.path.isfile(temporary):
                size = os.path.getsize(temporary)
                if size > 0:
                    break
            time.sleep(0.05)
        mark("MARK_TEMP_FILE", f"exists={os.path.isfile(temporary)} size={size}")
        exit_code = 0 if size > 0 else 3
    finally:
        try:
            player.terminate()
            mark("MARK_TERMINATE", "ok")
        except Exception as exc:
            mark("MARK_TERMINATE", f"error={type(exc).__name__}")
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass
        try:
            os.rmdir(workdir)
        except OSError:
            pass

    # mpv uyari/hata satirlari YALNIZ bu teshis ciktisinda gorunur.
    for line in log_lines[:12]:
        print("MPVLOG " + line, flush=True)
    print(f"RESULTS: exit={exit_code} events={events[:4]}", flush=True)
    print("MARK_DONE", flush=True)
    return exit_code


if __name__ == "__main__":
    os._exit(main())
