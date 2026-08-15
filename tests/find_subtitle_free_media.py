"""Sinirli, opt-in medya kesfi: gercekten altyazisiz bir video var mi?

- Recursive tarama YOK: yalniz `MLC_PLAYLIST_VIDEOS` girdileri ve
  `MLC_NATIVE_TEST_VIDEO` klasorundeki DOGRUDAN dosyalar.
- En fazla `MAX_CANDIDATES` aday.
- Her aday AYRI, timeout'lu child surecinde (`media_track_probe_child.py`)
  `vo=null`/`ao=null` ile yalniz metadata icin acilir.
- Kopyalama, donusturme, remux, indirme, ag erisimi YOK.
- Rapor yalniz basename yazar; tam kullanici yolu basilmaz.
- Opt-in: `MLC_MEDIA_PROBE=1`. Normal pytest bu dosyayi toplamaz.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.media_probe_rules import (MAX_CANDIDATES, candidate_paths,  # noqa: E402
                                     probe_problems, safe_summary_line)

PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "media_track_probe_child.py")
PROBE_TIMEOUT_S = 20.0


def run_probe(path, timeout_s=PROBE_TIMEOUT_S):
    """Adayi kendi child surecinde inceler. Yalniz KENDI PID'ini temizler."""
    env = dict(os.environ)
    env["MLC_MEDIA_PROBE"] = "1"
    proc = subprocess.Popen(
        [sys.executable, PROBE, "--path", path,
         "--seconds", str(max(2.0, timeout_s - 6.0))],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", env=env)
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            out, _ = proc.communicate(timeout=10)
        except Exception:
            out = ""
        out = (out or "") + "\nPROBE_TIMEOUT"
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
    for line in (out or "").splitlines():
        if line.startswith("PROBE_JSON "):
            try:
                return json.loads(line[len("PROBE_JSON "):])
            except ValueError:
                break
    return {"path": path, "loaded": False, "duration": 0.0,
            "video_tracks": 0, "audio_tracks": 0, "sub_tracks": 0,
            "error": "probe_timeout" if "PROBE_TIMEOUT" in (out or "")
                     else "probe_no_output"}


def main():
    if os.environ.get("MLC_MEDIA_PROBE") != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    test_video = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
    playlist = os.environ.get("MLC_PLAYLIST_VIDEOS", "")
    candidates = candidate_paths(test_video, playlist, os.listdir,
                                 os.path.isfile, limit=MAX_CANDIDATES)
    print(f"CANDIDATES count={len(candidates)} limit={MAX_CANDIDATES} "
          f"recursive=False", flush=True)
    suitable = []
    for path in candidates:
        summary = run_probe(path)
        problems = probe_problems(summary)
        print(f"PROBE {safe_summary_line(summary)} "
              f"duration_positive={float(summary.get('duration') or 0) > 0} "
              f"problems={problems or 'none'}", flush=True)
        if not problems:
            suitable.append(summary)
    if not suitable:
        print(f"BLOCKED: NO_REAL_SUBTITLE_FREE_VIDEO examined={len(candidates)}",
              flush=True)
        return 1
    best = suitable[0]
    print(f"SUITABLE {safe_summary_line(best)}", flush=True)
    print("SUITABLE_PATH " + best["path"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
