"""Altyazisiz gercek medya adayi secim kurallari (saf, Qt'siz, ag'siz).

Bu modul YALNIZ karar mantigi icerir: dosya sistemi taramaz, surec
baslatmaz, medya acmaz. Boylece normal `pytest` kosumunda kullanicinin
medya klasorleri ISLENMEZ.

Kabul sozlesmesi (`subtitles/no_subtitle_osd`):
- gercek dosya
- video track sayisi > 0 (audio-only WAV/MP3 KABUL EDILMEZ)
- subtitle track sayisi == 0
- duration > 0
- yukleme hatasi yok
"""
import os

# Yalniz gercek video tasiyabilen uzantilar. Audio-only uzantilar
# (mp3/wav/flac/ogg/m4a) bu kabul icin BILEREK disaridadir; yine de
# nihai karar probe sonucundaki video track sayisina baglidir.
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv",
                    ".mpeg", ".mpg", ".m4v")

MAX_CANDIDATES = 20


def is_video_file(path):
    return os.path.splitext(str(path))[1].lower() in VIDEO_EXTENSIONS


def candidate_paths(test_video, playlist_spec, listdir, isfile,
                    limit=MAX_CANDIDATES):
    """Sinirli aday listesi. Recursive tarama YOKTUR.

    Kaynaklar, bu sirayla:
    1. `playlist_spec` icinde ZATEN verilmis dosyalar (`|` ayrilmis),
    2. `test_video` dosyasinin bulundugu klasordeki DOGRUDAN dosyalar.

    `listdir`/`isfile` disaridan verilir; bu modul kendisi diske
    dokunmaz ve test edilebilir kalir. Ana test videosunun kendisi aday
    degildir (altyazili oldugu zaten olculuyor). En fazla `limit` aday.
    """
    seen = set()
    out = []
    skip = os.path.normcase(os.path.abspath(test_video)) if test_video else None

    def add(path):
        if len(out) >= limit:
            return
        key = os.path.normcase(os.path.abspath(path))
        if key == skip or key in seen:
            return
        if not is_video_file(path) or not isfile(path):
            return
        seen.add(key)
        out.append(path)

    for entry in str(playlist_spec or "").split("|"):
        if entry.strip():
            add(entry.strip())

    folder = os.path.dirname(os.path.abspath(test_video)) if test_video else ""
    if folder:
        try:
            names = sorted(listdir(folder))
        except OSError:
            names = []
        for name in names:
            add(os.path.join(folder, name))
    return out[:limit]


def probe_problems(summary):
    """Bir probe ozetinin kabul sartlarina uymayan yonleri. Bos = uygun."""
    problems = []
    if not isinstance(summary, dict):
        return ["probe_summary_missing"]
    if not summary.get("loaded"):
        problems.append(f"load_failed:{summary.get('error') or 'unknown'}")
    if int(summary.get("video_tracks") or 0) <= 0:
        problems.append("no_video_track")
    if int(summary.get("sub_tracks") or 0) != 0:
        problems.append(f"sub_tracks={summary.get('sub_tracks')}")
    if float(summary.get("duration") or 0.0) <= 0.0:
        problems.append("duration_not_positive")
    return problems


def is_suitable(summary):
    return not probe_problems(summary)


def count_tracks(track_list, kind):
    return len([t for t in (track_list or [])
                if isinstance(t, dict) and t.get("type") == kind])


def safe_summary_line(summary):
    """Rapora yazilabilir tek satir: TAM YOL ICERMEZ, yalniz basename."""
    name = os.path.basename(str(summary.get("path") or ""))
    return (f"{name} loaded={bool(summary.get('loaded'))} "
            f"video={int(summary.get('video_tracks') or 0)} "
            f"audio={int(summary.get('audio_tracks') or 0)} "
            f"sub={int(summary.get('sub_tracks') or 0)}")
