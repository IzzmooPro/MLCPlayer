# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Saf WIN-P0-03 track fixture ve secim sozlesmesi."""


DISABLED_TRACK_IDS = {"", "no", "none", "false", "auto"}


def normalise_track_id(value):
    """mpv'nin int/numeric-string ID varyantlarini tek kanonik int yapar."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip().lower()
    if text in DISABLED_TRACK_IDS:
        return None
    try:
        number = int(text, 10)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def track_snapshot(track_list, kind, current, visibility=None):
    """Bir tur icin normalize edilmis kimlik ve selected gorunumu."""
    rows = []
    invalid_ids = 0
    for track in track_list or []:
        if not isinstance(track, dict) or track.get("type") != kind:
            continue
        track_id = normalise_track_id(track.get("id"))
        if track_id is None:
            invalid_ids += 1
            continue
        rows.append((track_id, bool(track.get("selected"))))
    rows = tuple(rows)
    ids = tuple(item[0] for item in rows)
    return {
        "kind": kind,
        "ids": ids,
        "selected": tuple(item[0] for item in rows if item[1]),
        "current": normalise_track_id(current),
        "visibility": None if visibility is None else bool(visibility),
        "invalid_ids": invalid_ids,
        "duplicates": len(ids) != len(set(ids)),
        "signature": (kind, rows, normalise_track_id(current),
                      None if visibility is None else bool(visibility),
                      invalid_ids),
    }


def fixture_problems(audio, subtitles, video_count, duration):
    problems = []
    if not duration or float(duration) <= 0:
        problems.append("duration_not_positive")
    if int(video_count or 0) <= 0:
        problems.append("video_track_missing")
    for name, snapshot in (("audio", audio), ("sub", subtitles)):
        if snapshot["invalid_ids"]:
            problems.append(f"{name}_invalid_id")
        if snapshot["duplicates"]:
            problems.append(f"{name}_duplicate_id")
        if len(snapshot["ids"]) < 2:
            problems.append(f"{name}_needs_two_tracks")
        if snapshot["current"] not in snapshot["ids"]:
            problems.append(f"{name}_current_missing")
        if snapshot["selected"] != (snapshot["current"],):
            problems.append(f"{name}_selected_mismatch")
    return problems


def fixture_block_code(problems):
    values = tuple(str(problem) for problem in problems or ())
    if any(value.startswith("current_ao") for value in values):
        return "AUDIO_ISOLATION"
    if any(value in {"duration_not_positive", "video_track_missing"}
           for value in values):
        return "MEDIA_FIXTURE"
    if "TRACK_INVENTORY_UNSTABLE" in values:
        return "TRACK_INVENTORY_UNSTABLE"
    if "MULTI_TRACK_MEDIA_REQUIRED" in values:
        return "MULTI_TRACK_MEDIA_REQUIRED"
    return "TRACK_ID_SELECTED_CONTRACT"


def alternate_track_id(snapshot):
    current = snapshot.get("current")
    return next((track_id for track_id in snapshot.get("ids", ())
                 if track_id != current), None)


def unique_target_index(values, target):
    """Hedef ID exact bir kez varsa indeksini, aksi halde None dondurur."""
    target = normalise_track_id(target)
    matches = [index for index, value in enumerate(values)
               if normalise_track_id(value) == target]
    return matches[0] if target is not None and len(matches) == 1 else None


def selected_track_matches(snapshot, target, require_visible=False):
    target = normalise_track_id(target)
    if target is None:
        return False
    if snapshot.get("current") != target:
        return False
    if tuple(snapshot.get("selected", ())) != (target,):
        return False
    if require_visible and snapshot.get("visibility") is not True:
        return False
    return True


class StableSelection:
    """Ayni tam snapshot eslesmesini N ardışık ornekte ister."""

    def __init__(self, target, require_visible=False, required=3,
                 expected_ids=None):
        self.target = normalise_track_id(target)
        self.require_visible = bool(require_visible)
        self.required = max(1, int(required))
        self.expected_ids = (None if expected_ids is None else
                             tuple(normalise_track_id(value)
                                   for value in expected_ids))
        self._count = 0
        self._signature = None

    def observe(self, snapshot):
        signature = snapshot.get("signature")
        inventory_ok = (
            self.expected_ids is None
            or (not snapshot.get("invalid_ids")
                and not snapshot.get("duplicates")
                and len(snapshot.get("ids", ())) == len(self.expected_ids)
                and set(snapshot.get("ids", ())) == set(self.expected_ids)))
        if (inventory_ok
                and selected_track_matches(snapshot, self.target,
                                           self.require_visible)
                and signature == self._signature):
            self._count += 1
        elif (inventory_ok
              and selected_track_matches(snapshot, self.target,
                                         self.require_visible)):
            self._signature = signature
            self._count = 1
        else:
            self._signature = None
            self._count = 0
        return self._count >= self.required
