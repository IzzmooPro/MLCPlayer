# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""`subtitles/no_subtitle_osd` aday secim sozlesmesi regresyonlari.

Bu testler DISKE DOKUNMAZ ve medya acmaz: `candidate_paths` dosya
sistemi erisimini disaridan alir, boylece normal `pytest` kosumu
kullanicinin medya klasorlerini taramaz.
"""
import os

from tests.media_probe_rules import (MAX_CANDIDATES, candidate_paths,
                                     count_tracks, is_suitable,
                                     probe_problems, safe_summary_line)

MAIN = r"X:\media\Main.Movie.mkv"


def fake_fs(folder_names, extra_files=()):
    files = {os.path.normcase(os.path.join(r"X:\media", name))
             for name in folder_names}
    files |= {os.path.normcase(p) for p in extra_files}

    def listdir(path):
        assert os.path.normcase(path) == os.path.normcase(r"X:\media")
        return list(folder_names)

    def isfile(path):
        return os.path.normcase(os.path.abspath(path)) in {
            os.path.normcase(os.path.abspath(p)) for p in files}

    return listdir, isfile


def summary(**kwargs):
    base = {"path": r"X:\media\A.mkv", "loaded": True, "duration": 120.0,
            "video_tracks": 1, "audio_tracks": 1, "sub_tracks": 0, "error": ""}
    base.update(kwargs)
    return base


def test_candidate_discovery_is_not_recursive_and_skips_main_video():
    listdir, isfile = fake_fs(["Main.Movie.mkv", "Other.mkv", "notes.txt"])
    found = candidate_paths(MAIN, "", listdir, isfile)
    assert [os.path.basename(p) for p in found] == ["Other.mkv"]


def test_playlist_entries_come_first_and_are_not_duplicated():
    listdir, isfile = fake_fs(["Main.Movie.mkv", "A.mkv", "B.mkv"])
    spec = r"X:\media\B.mkv|X:\media\A.mkv"
    found = [os.path.basename(p) for p in candidate_paths(MAIN, spec, listdir,
                                                          isfile)]
    assert found == ["B.mkv", "A.mkv"]


def test_audio_only_files_are_never_candidates():
    listdir, isfile = fake_fs(["Main.Movie.mkv", "song.mp3", "voice.wav",
                               "clip.mp4"])
    found = [os.path.basename(p) for p in candidate_paths(MAIN, "", listdir,
                                                          isfile)]
    assert found == ["clip.mp4"]


def test_candidate_count_is_bounded():
    names = ["Main.Movie.mkv"] + [f"v{i:03d}.mkv" for i in range(50)]
    listdir, isfile = fake_fs(names)
    assert len(candidate_paths(MAIN, "", listdir, isfile)) == MAX_CANDIDATES


def test_missing_files_are_dropped():
    listdir, isfile = fake_fs(["Main.Movie.mkv", "A.mkv"])
    found = candidate_paths(MAIN, r"X:\media\Ghost.mkv", listdir, isfile)
    assert [os.path.basename(p) for p in found] == ["A.mkv"]


def test_suitable_candidate_requires_video_track_and_zero_subtitles():
    assert is_suitable(summary())
    assert probe_problems(summary(sub_tracks=1)) == ["sub_tracks=1"]
    assert probe_problems(summary(video_tracks=0)) == ["no_video_track"]
    assert probe_problems(summary(duration=0.0)) == ["duration_not_positive"]
    assert probe_problems(summary(loaded=False, error="timeout_no_tracks"))[0] \
        == "load_failed:timeout_no_tracks"
    assert probe_problems(None) == ["probe_summary_missing"]


def test_safe_summary_line_never_leaks_full_path():
    line = safe_summary_line(summary(path=r"C:\Users\Someone\Videos\Film.mkv"))
    assert "Film.mkv" in line
    assert "Users" not in line and "\\" not in line


def test_count_tracks_ignores_malformed_entries():
    tracks = [{"type": "sub"}, {"type": "video"}, "bogus", None,
              {"type": "sub"}]
    assert count_tracks(tracks, "sub") == 2
    assert count_tracks(tracks, "video") == 1
    assert count_tracks(None, "sub") == 0


def test_discovery_scripts_are_opt_in():
    root = os.path.dirname(os.path.abspath(__file__))
    for name in ("find_subtitle_free_media.py", "media_track_probe_child.py"):
        text = open(os.path.join(root, name), encoding="utf-8").read()
        assert 'os.environ.get("MLC_MEDIA_PROBE") != "1"' in text
        assert "SKIPPED: OPT_IN_REQUIRED" in text
        # Ag erisimi ve donusturme/kopyalama YOK.
        for banned in ("urllib", "requests", "http", "shutil.copy", "ffmpeg"):
            assert banned not in text
