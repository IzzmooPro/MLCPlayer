"""Altyazı stil sözleşmesi: MPV renk biçimi, arka plan kutusu, ASS override.

Kanıtlanmış kök nedenler:

1. `_qcolor_to_mpv()` `#RRGGBBAA` üretiyordu; MPV `#AARRGGBB` bekler.
   Bu yüzden seçilen turuncu MPV tarafında başka renge dönüşüyordu.
2. `_mpv_color_to_qcolor()` aynı yanlış sırayı tersine okuyordu.
3. `sub_back_color` varsayılan `outline-and-shadow` stilinde yalnız GÖLGE
   rengidir; kullanıcının beklediği arka plan kutusu için
   `sub_border_style=background-box` gerekir.
4. ASS altyazılarda normal `sub_*` seçeneklerinin uygulanması için
   `sub_ass_override="force"` gerekir; bool `True`/`"yes"` yetmez.
"""
import pytest
from PyQt6.QtGui import QColor

from app.config import SUBTITLE_DEFAULTS
from app.subtitle_style import (
    ASS_OVERRIDE_FORCE, BACKGROUND_BOX, COLOR_KEYS, OUTLINE_AND_SHADOW,
    SCHEMA_KEY, STYLE_SCHEMA_VERSION, atomic_apply, border_style_for,
    legacy_rgba_to_mpv_argb, migrate_settings, mpv_argb_to_qcolor,
    qcolor_to_mpv_argb, style_properties)

ORANGE = QColor(242, 106, 61, 255)


class FakeSettings:
    """QSettings benzeri; gerçek HKCU KULLANILMAZ."""

    def __init__(self, values=None, fail_on=None):
        self.values = dict(values or {})
        self.fail_on = fail_on
        self.writes = []
        self.synced = 0

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        if self.fail_on is not None and key == self.fail_on:
            raise OSError("settings backend failure")
        self.values[key] = value
        self.writes.append((key, value))

    def contains(self, key):
        return key in self.values

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        self.synced += 1


class FakeMPV:
    def __init__(self, fail_on=None, **props):
        object.__setattr__(self, "_props", dict(props))
        object.__setattr__(self, "_fail_on", fail_on)
        object.__setattr__(self, "writes", [])

    def __getattr__(self, name):
        props = object.__getattribute__(self, "_props")
        if name in props:
            return props[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == object.__getattribute__(self, "_fail_on"):
            raise RuntimeError("mpv property rejected")
        object.__getattribute__(self, "_props")[name] = value
        object.__getattribute__(self, "writes").append((name, value))

    def snapshot(self):
        return dict(object.__getattribute__(self, "_props"))


def base_values(**over):
    values = {"sub_delay": 0.0, "sub_scale": 1.0, "sub_pos": 100.0,
              "sub_border_size": 3.0, "sub_color": QColor(255, 255, 255, 255),
              "sub_back_color": QColor(0, 0, 0, 0),
              "sub_border_color": QColor(0, 0, 0, 255)}
    values.update(over)
    return values


# --- A) Canonical renk modeli ---

@pytest.mark.parametrize("color,expected", [
    (QColor(255, 0, 0, 255), "#FFFF0000"),
    (QColor(0, 0, 0, 255), "#FF000000"),
    (QColor(255, 255, 255, 255), "#FFFFFFFF"),
    (QColor(0, 0, 0, 0), "#00000000"),
    (ORANGE, "#FFF26A3D"),
    (QColor(128, 128, 128, 192), "#C0808080"),
])
def test_qcolor_becomes_canonical_argb(color, expected):
    assert qcolor_to_mpv_argb(color) == expected


def test_canonical_value_round_trips_through_qcolor():
    for color in (ORANGE, QColor(1, 2, 3, 4), QColor(0, 0, 0, 0)):
        value = qcolor_to_mpv_argb(color)
        back = mpv_argb_to_qcolor(value, "#FF000000")
        assert (back.red(), back.green(), back.blue(), back.alpha()) == (
            color.red(), color.green(), color.blue(), color.alpha())


def test_lowercase_input_is_accepted_and_output_is_uppercase():
    color = mpv_argb_to_qcolor("#fff26a3d", "#FF000000")
    assert qcolor_to_mpv_argb(color) == "#FFF26A3D"


@pytest.mark.parametrize("bad", [None, "", "#FFF", "#GGGGGGGG", "yellowish",
                                 "FFF26A3D", 42, "#FFF26A3D00"])
def test_broken_values_fall_back_safely(bad):
    color = mpv_argb_to_qcolor(bad, "#FF000000")
    assert qcolor_to_mpv_argb(color) == "#FF000000"


def test_plain_rgb_hex_is_read_as_opaque():
    color = mpv_argb_to_qcolor("#F26A3D", "#FF000000")
    assert qcolor_to_mpv_argb(color) == "#FFF26A3D"


def test_legacy_rgba_is_only_converted_by_the_explicit_migration_helper():
    # Eski kayit: #RRGGBBAA (opak turuncu)
    assert legacy_rgba_to_mpv_argb("#F26A3DFF") == "#FFF26A3D"
    assert legacy_rgba_to_mpv_argb("#000000FF") == "#FF000000"
    assert legacy_rgba_to_mpv_argb("#00000000") == "#00000000"
    # Normal parser TAHMIN ETMEZ: ayni metni canonical ARGB olarak okur.
    parsed = mpv_argb_to_qcolor("#F26A3DFF", "#FF000000")
    assert qcolor_to_mpv_argb(parsed) == "#F26A3DFF"


def test_legacy_helper_keeps_unusable_values_untouched():
    for bad in (None, "", "#FFF", "bogus"):
        assert legacy_rgba_to_mpv_argb(bad) is None


# --- B) Varsayilanlar ---

def test_defaults_are_canonical_argb_and_force_ass_override():
    assert SUBTITLE_DEFAULTS["sub_color"] == "#FFFFFFFF"
    assert SUBTITLE_DEFAULTS["sub_back_color"] == "#00000000"
    assert SUBTITLE_DEFAULTS["sub_border_color"] == "#FF000000"
    assert SUBTITLE_DEFAULTS["sub_ass_override"] == ASS_OVERRIDE_FORCE
    assert not isinstance(SUBTITLE_DEFAULTS["sub_ass_override"], bool)


# --- C) Arka plan kutusu ---

def test_opaque_background_selects_background_box():
    assert border_style_for("#FF000000") == BACKGROUND_BOX
    assert border_style_for("#01000000") == BACKGROUND_BOX


def test_fully_transparent_background_keeps_outline_and_shadow():
    assert border_style_for("#00000000") == OUTLINE_AND_SHADOW
    assert border_style_for(None) == OUTLINE_AND_SHADOW
    assert border_style_for("bogus") == OUTLINE_AND_SHADOW


def test_style_properties_derive_border_style_from_the_background_alpha():
    opaque = style_properties(base_values(
        sub_back_color=QColor(0, 0, 0, 255)))
    assert opaque["sub_back_color"] == "#FF000000"
    assert opaque["sub_border_style"] == BACKGROUND_BOX

    clear = style_properties(base_values())
    assert clear["sub_back_color"] == "#00000000"
    assert clear["sub_border_style"] == OUTLINE_AND_SHADOW


def test_background_box_uses_an_explicit_shadow_offset_constant():
    from app.subtitle_style import BACKGROUND_BOX_SHADOW_OFFSET

    opaque = style_properties(base_values(
        sub_back_color=QColor(0, 0, 0, 255)))
    assert opaque["sub_shadow_offset"] == BACKGROUND_BOX_SHADOW_OFFSET
    assert BACKGROUND_BOX_SHADOW_OFFSET >= 0


def test_border_colour_and_size_survive_in_background_box_mode():
    props = style_properties(base_values(
        sub_back_color=QColor(0, 0, 0, 255),
        sub_border_color=QColor(255, 0, 0, 255), sub_border_size=4.0))
    assert props["sub_border_color"] == "#FFFF0000"
    assert props["sub_border_size"] == 4.0
    assert props["sub_border_style"] == BACKGROUND_BOX


def test_style_properties_always_force_ass_override():
    props = style_properties(base_values())
    assert props["sub_ass_override"] == ASS_OVERRIDE_FORCE
    assert props["sub_ass_override"] not in (True, "yes")


def test_style_properties_accept_canonical_strings_as_well_as_qcolor():
    props = style_properties(base_values(sub_color="#FFF26A3D"))
    assert props["sub_color"] == "#FFF26A3D"


# --- D) Migrasyon ---

def test_legacy_settings_are_migrated_once_and_marked():
    settings = FakeSettings({
        "subtitle/sub_color": "#F26A3DFF",
        "subtitle/sub_back_color": "#000000FF",
        "subtitle/sub_border_color": "#00000080",
        "subtitle/sub_ass_override": True,
    })

    assert migrate_settings(settings) is True

    assert settings.value("subtitle/sub_color") == "#FFF26A3D"
    assert settings.value("subtitle/sub_back_color") == "#FF000000"
    assert settings.value("subtitle/sub_border_color") == "#80000000"
    assert settings.value("subtitle/sub_ass_override") == ASS_OVERRIDE_FORCE
    assert settings.value(SCHEMA_KEY) == STYLE_SCHEMA_VERSION


def test_migration_is_idempotent():
    settings = FakeSettings({"subtitle/sub_color": "#F26A3DFF"})
    migrate_settings(settings)
    first = dict(settings.values)

    assert migrate_settings(settings) is False
    assert settings.values == first


def test_missing_keys_are_never_invented_by_the_migration():
    settings = FakeSettings({"subtitle/sub_color": "#F26A3DFF"})

    migrate_settings(settings)

    for key in COLOR_KEYS:
        if key != "sub_color":
            assert not settings.contains(f"subtitle/{key}")


def test_legacy_boolean_override_becomes_force_and_false_stays_disabled():
    on = FakeSettings({"subtitle/sub_ass_override": True})
    off = FakeSettings({"subtitle/sub_ass_override": False})

    migrate_settings(on)
    migrate_settings(off)

    assert on.value("subtitle/sub_ass_override") == ASS_OVERRIDE_FORCE
    # Kullanicinin KAPALI tercihi "force" yapilamaz; MPV'nin kendi
    # devre disi degeri kullanilir.
    assert off.value("subtitle/sub_ass_override") == "no"


def test_a_failed_migration_leaves_no_half_written_settings():
    original = {"subtitle/sub_color": "#F26A3DFF",
                "subtitle/sub_back_color": "#000000FF"}
    settings = FakeSettings(dict(original),
                            fail_on="subtitle/sub_back_color")

    assert migrate_settings(settings) is False

    assert settings.values == original
    assert not settings.contains(SCHEMA_KEY)


def test_already_canonical_settings_with_marker_are_left_alone():
    settings = FakeSettings({SCHEMA_KEY: STYLE_SCHEMA_VERSION,
                             "subtitle/sub_color": "#FFF26A3D"})

    assert migrate_settings(settings) is False
    assert settings.value("subtitle/sub_color") == "#FFF26A3D"


# --- E) Atomik uygulama ---

def test_successful_apply_writes_every_property_and_stores_them():
    mpv = FakeMPV(sub_color="#FFFFFFFF", sub_back_color="#00000000",
                  sub_border_color="#FF000000", sub_border_size=3.0,
                  sub_scale=1.0, sub_pos=100.0, sub_delay=0.0,
                  sub_border_style=OUTLINE_AND_SHADOW, sub_shadow_offset=0.0,
                  sub_ass_override=ASS_OVERRIDE_FORCE)
    settings = FakeSettings()

    ok, error = atomic_apply(mpv, settings, base_values(
        sub_color=ORANGE, sub_back_color=QColor(0, 0, 0, 255), sub_delay=2.5))

    assert ok and error is None
    assert mpv.sub_color == "#FFF26A3D"
    assert mpv.sub_border_style == BACKGROUND_BOX
    assert mpv.sub_ass_override == ASS_OVERRIDE_FORCE
    assert settings.value("subtitle/sub_color") == "#FFF26A3D"
    assert settings.value(SCHEMA_KEY) == STYLE_SCHEMA_VERSION
    # Gecikme oturumlar arasinda 0 saklanir, ama MPV'ye uygulanir.
    assert mpv.sub_delay == 2.5
    assert settings.value("subtitle/sub_delay") == 0.0


def test_a_rejected_mpv_property_rolls_everything_back():
    mpv = FakeMPV(fail_on="sub_border_style", sub_color="#FFFFFFFF",
                  sub_back_color="#00000000", sub_border_color="#FF000000",
                  sub_border_size=3.0, sub_scale=1.0, sub_pos=100.0,
                  sub_delay=0.0, sub_shadow_offset=0.0,
                  sub_ass_override=ASS_OVERRIDE_FORCE)
    before = mpv.snapshot()
    settings = FakeSettings({"subtitle/sub_color": "#FFFFFFFF"})

    ok, error = atomic_apply(mpv, settings, base_values(
        sub_color=ORANGE, sub_back_color=QColor(0, 0, 0, 255)))

    assert ok is False and error is not None
    assert mpv.sub_color == before["sub_color"], "MPV yarim durumda kaldi"
    assert mpv.sub_back_color == before["sub_back_color"]
    assert settings.value("subtitle/sub_color") == "#FFFFFFFF"
    assert not settings.contains(SCHEMA_KEY)


def test_a_failing_settings_write_rolls_back_mpv_too():
    mpv = FakeMPV(sub_color="#FFFFFFFF", sub_back_color="#00000000",
                  sub_border_color="#FF000000", sub_border_size=3.0,
                  sub_scale=1.0, sub_pos=100.0, sub_delay=0.0,
                  sub_border_style=OUTLINE_AND_SHADOW, sub_shadow_offset=0.0,
                  sub_ass_override=ASS_OVERRIDE_FORCE)
    before = mpv.snapshot()
    settings = FakeSettings(fail_on="subtitle/sub_border_color")

    ok, error = atomic_apply(mpv, settings, base_values(sub_color=ORANGE))

    assert ok is False and error is not None
    assert mpv.snapshot() == before, "settings hatasinda MPV geri alinmadi"
    assert settings.values == {}


def test_keys_absent_before_a_failed_apply_are_removed_again():
    mpv = FakeMPV(sub_color="#FFFFFFFF", sub_back_color="#00000000",
                  sub_border_color="#FF000000", sub_border_size=3.0,
                  sub_scale=1.0, sub_pos=100.0, sub_delay=0.0,
                  sub_border_style=OUTLINE_AND_SHADOW, sub_shadow_offset=0.0,
                  sub_ass_override=ASS_OVERRIDE_FORCE)
    settings = FakeSettings({"subtitle/sub_scale": 1.0},
                            fail_on="subtitle/sub_border_color")

    atomic_apply(mpv, settings, base_values(sub_color=ORANGE))

    assert settings.values == {"subtitle/sub_scale": 1.0}


def test_a_settings_backend_error_after_sync_is_not_reported_as_success():
    class BrokenSettings(FakeSettings):
        def sync(self):
            self.synced += 1

        def status(self):
            return "AccessError"

    mpv = FakeMPV(sub_color="#FFFFFFFF", sub_back_color="#00000000",
                  sub_border_color="#FF000000", sub_border_size=3.0,
                  sub_scale=1.0, sub_pos=100.0, sub_delay=0.0,
                  sub_border_style=OUTLINE_AND_SHADOW, sub_shadow_offset=0.0,
                  sub_ass_override=ASS_OVERRIDE_FORCE)
    before = mpv.snapshot()
    settings = BrokenSettings()

    ok, error = atomic_apply(mpv, settings, base_values(sub_color=ORANGE))

    assert ok is False and error is not None
    assert mpv.snapshot() == before


# --- F) Bitmap/PGS altyazi sozlesmesi ---

@pytest.mark.parametrize("codec", ["hdmv_pgs_subtitle", "dvd_subtitle",
                                   "VOBSUB", "dvb_subtitle", "xsub"])
def test_bitmap_subtitles_are_recognised(codec):
    from app.subtitle_style import is_bitmap_subtitle

    assert is_bitmap_subtitle(codec)


@pytest.mark.parametrize("codec", ["subrip", "ass", "webvtt", None, "", 7])
def test_text_subtitles_are_not_treated_as_bitmap(codec):
    from app.subtitle_style import is_bitmap_subtitle

    assert not is_bitmap_subtitle(codec)


def test_a_selected_bitmap_track_produces_a_safe_notice():
    from app.subtitle_style import BITMAP_STYLE_NOTICE, style_notice

    tracks = [{"type": "sub", "id": 1, "codec": "hdmv_pgs_subtitle",
               "selected": True}]

    notice = style_notice(tracks)
    assert notice == BITMAP_STYLE_NOTICE
    assert "Traceback" not in notice and ":\\" not in notice


def test_a_selected_text_track_produces_no_notice():
    tracks = [{"type": "sub", "id": 1, "codec": "subrip", "selected": True}]

    from app.subtitle_style import style_notice

    assert style_notice(tracks) == ""


def test_an_unknown_track_list_stays_silent_instead_of_guessing():
    from app.subtitle_style import style_notice

    assert style_notice(None) == ""
    assert style_notice([{"type": "sub", "id": 1, "selected": True}]) == ""
    assert style_notice(["bozuk", None]) == ""


def test_apply_never_leaks_raw_errors_or_paths_to_the_user_message():
    from app.subtitle_style import APPLY_ERROR_MESSAGE

    assert "Traceback" not in APPLY_ERROR_MESSAGE
    assert ":\\" not in APPLY_ERROR_MESSAGE and "/" not in APPLY_ERROR_MESSAGE
