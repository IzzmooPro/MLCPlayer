"""Medya Bilgisi SAF builder katmani (1. uygulama turu).

Bu tur YALNIZ `app/media_info.py` icindir: Qt, dialog, menu, QAction,
player yasam dongusu ve clipboard YOK. Builder girdileri aciktir
(`current_file`, `duration`, `track_list`, salt-okunur property okuyucu);
global player/mpv nesnesine baglanmaz.

Kilitlenen sozlesmeler
----------------------
- Tam yerel yol GORUNUR satirlara girmez; yalniz ayri `copy_value` alaninda
  bulunur ve UI onu ancak acik kullanici eylemiyle kullanir.
- URL'de yalniz `scheme://host` + guvenli son yol parcasi kalir; userinfo,
  query ve fragment ne gorunur metinde ne de `copy_value` icinde bulunur.
- Dosyadan/metadata'dan gelen her metin duz metindir ve kontrol
  karakterlerinden arindirilmistir.
- Ham track ID, `None`, Python repr, `demux-*` anahtar adlari ve ham
  bilinmeyen kodlar kullaniciya ULASMAZ.
- Alan yoksa satir gizlenir; bolum tamamen bossa tek bos-durum mesaji olur.
- HDR YOK. Guvenilir aspect kaynagi yoksa oran satiri YOK.
- Tazeleme anahtari `current_file`, normalize duration, secili vid/aid/sid ve
  track'lerin gosterimi etkileyen guvenli alanlarindan kararli tuple uretir;
  dict sirasina veya nesne kimligine dayanmaz.
"""
import os

import pytest

from app.media_info import (MediaInfoSnapshot, build_media_info,
                            media_info_refresh_key, sanitize_display_text,
                            sanitize_media_url)

SECRET_URL = ("https://user:s3cret@cdn.example.com:8443/videos/bolum-1.mkv"
              "?token=abcdef123456&exp=999#t=42")


def video_track(identifier=1, selected=True, width=1920, height=1080,
                codec="h264", fps=23.976, bitrate=8_000_000, **extra):
    track = {"id": identifier, "type": "video", "selected": selected,
             "codec": codec, "demux-w": width, "demux-h": height,
             "demux-fps": fps, "demux-bitrate": bitrate}
    track.update(extra)
    return track


def audio_track(identifier=1, selected=True, lang="tur", codec="eac3",
                channels=6, rate=48000, bitrate=640000, **extra):
    track = {"id": identifier, "type": "audio", "selected": selected,
             "lang": lang, "codec": codec, "demux-channel-count": channels,
             "demux-samplerate": rate, "demux-bitrate": bitrate}
    track.update(extra)
    return track


def subtitle_track(identifier=1, selected=False, lang="tur", codec="subrip",
                   external=False, filename=None, **extra):
    track = {"id": identifier, "type": "sub", "selected": selected,
             "lang": lang, "codec": codec, "external": external}
    if filename is not None:
        track["external-filename"] = filename
    track.update(extra)
    return track


def local_media(tmp_path, name="Bolum 1.mkv", payload=b"0" * 2048):
    folder = tmp_path / "Diziler" / "Seri 2"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(payload)
    return str(path)


def reader_for(values):
    """Salt-okunur mpv property okuyucusu (yalniz sozlukten okur)."""
    def read(name):
        return values[name]
    return read


# =====================================================================
# 1. Metin temizligi
# =====================================================================

@pytest.mark.parametrize("raw, expected", (
    ("Film\x00 Adi", "Film Adi"),
    ("satir\nsonu\tvar", "satir sonu var"),
    ("  bosluk  ", "bosluk"),
    ("‮gnitfihs", "gnitfihs"),        # bidi override kaldirilir
    ("\x1b[31mrenk", "[31mrenk"),          # ESC kaldirilir, metin kalir
))
def test_display_text_is_plain_and_control_free(raw, expected):
    assert sanitize_display_text(raw) == expected


@pytest.mark.parametrize("raw", (None, 3.5, object(), b"bayt", ["liste"]))
def test_non_text_never_becomes_a_python_repr(raw):
    cleaned = sanitize_display_text(raw)
    assert cleaned == "", f"metin olmayan deger sizdi: {cleaned!r}"


def test_long_text_is_shortened_with_an_ellipsis():
    cleaned = sanitize_display_text("A" * 400, limit=40)
    assert len(cleaned) == 40
    assert cleaned.endswith("…")


# =====================================================================
# 2. URL temizligi
# =====================================================================

def test_url_keeps_only_scheme_host_and_last_path_segment():
    assert sanitize_media_url(SECRET_URL) == \
        "https://cdn.example.com:8443/bolum-1.mkv"


@pytest.mark.parametrize("secret", ("user", "s3cret", "token", "abcdef123456",
                                    "exp=999", "t=42", "videos"))
def test_url_secrets_are_never_kept(secret):
    assert secret not in sanitize_media_url(SECRET_URL)


def test_url_without_a_path_keeps_only_the_host():
    assert sanitize_media_url("http://ornek.test/?k=v") == "http://ornek.test"


@pytest.mark.parametrize("raw", (None, "", "   ", 12))
def test_broken_url_yields_empty_text(raw):
    assert sanitize_media_url(raw) == ""


# =====================================================================
# 3. Medya yoksa snapshot da yoktur
# =====================================================================

@pytest.mark.parametrize("path", ("", None, "   "))
def test_no_media_yields_no_snapshot(path):
    assert build_media_info(path) is None


# =====================================================================
# 4. Yerel medya: Genel bolumu ve gizlilik
# =====================================================================

def test_local_general_section_shows_safe_fields(tmp_path):
    path = local_media(tmp_path)
    snapshot = build_media_info(
        path, duration=3725.4,
        property_reader=reader_for({"file-format": "matroska,webm",
                                    "metadata": {"title": "Bolum Bir"}}))

    assert isinstance(snapshot, MediaInfoSnapshot)
    general = snapshot.section("general")
    rows = {row.label: row.value for row in general.groups[0].rows}
    assert rows["Dosya"] == "Bolum 1.mkv"
    assert rows["Süre"] == "01:02:05"
    assert rows["Boyut"] == "2,0 KB"
    assert rows["Başlık"] == "Bolum Bir"
    # Klasor KISALTILMIS: yalniz son iki bilesen, koku sizmaz.
    assert rows["Konum"].startswith("…")
    assert "Seri 2" in rows["Konum"]


def test_the_full_local_path_never_appears_in_visible_text(tmp_path):
    path = local_media(tmp_path)
    snapshot = build_media_info(path, duration=60.0)

    visible = snapshot.visible_text()
    assert path not in visible
    assert os.path.dirname(path) not in visible
    assert str(tmp_path) not in visible


def test_the_full_path_is_available_only_for_an_explicit_copy(tmp_path):
    path = local_media(tmp_path)
    snapshot = build_media_info(path, duration=60.0)

    assert snapshot.copy_label == "Yolu Kopyala"
    assert snapshot.copy_value == path
    assert snapshot.is_local is True


def test_an_unreachable_file_hides_the_size_row(tmp_path):
    path = os.path.join(str(tmp_path), "yok", "kayip.mkv")
    snapshot = build_media_info(path, duration=0)

    rows = {row.label for row in snapshot.section("general").groups[0].rows}
    assert "Boyut" not in rows
    assert "Süre" not in rows, "duration<=0 iken sure satiri gizlenmeli"
    assert "Dosya" in rows


# =====================================================================
# 5. URL medyasi
# =====================================================================

def test_url_media_exposes_only_a_sanitized_address():
    snapshot = build_media_info(SECRET_URL, duration=120.0)

    assert snapshot.is_local is False
    assert snapshot.copy_label == "Adresi Kopyala"
    assert snapshot.copy_value == "https://cdn.example.com:8443/bolum-1.mkv"
    rows = {row.label: row.value for row in
            snapshot.section("general").groups[0].rows}
    assert rows["Adres"] == "https://cdn.example.com:8443/bolum-1.mkv"
    assert "Konum" not in rows and "Boyut" not in rows


@pytest.mark.parametrize("secret", ("s3cret", "token", "abcdef123456",
                                    "exp=999", "user:"))
def test_url_secrets_reach_neither_the_view_nor_the_copy_value(secret):
    snapshot = build_media_info(SECRET_URL, duration=120.0)

    assert secret not in snapshot.visible_text()
    assert secret not in snapshot.copy_value


# =====================================================================
# 6. Bozuk/eksik metadata pencereyi engellemez
# =====================================================================

def test_a_failing_property_reader_still_produces_a_snapshot(tmp_path):
    path = local_media(tmp_path)

    def angry(name):
        raise RuntimeError("mpv property okunamadi")

    snapshot = build_media_info(path, duration=90.0, property_reader=angry)

    assert snapshot is not None
    rows = {row.label for row in snapshot.section("general").groups[0].rows}
    assert "Kapsayıcı" not in rows and "Başlık" not in rows
    assert "Dosya" in rows


def test_broken_metadata_values_never_leak_raw_text(tmp_path):
    path = local_media(tmp_path)
    snapshot = build_media_info(
        path, duration=90.0,
        property_reader=reader_for({"file-format": None,
                                    "metadata": {"title": "Kotu\x07Ad\x1b"}}))

    visible = snapshot.visible_text()
    assert "\x07" not in visible and "\x1b" not in visible
    assert "Kotu Ad" in visible
    assert "None" not in visible


# =====================================================================
# 7. Track bolumleri
# =====================================================================

def test_every_track_becomes_a_safe_group(tmp_path):
    path = local_media(tmp_path)
    tracks = [video_track(1), video_track(2, selected=False, width=1280,
                                         height=720, codec="hevc"),
              audio_track(1), audio_track(2, selected=False, lang="eng",
                                          codec="aac", channels=2,
                                          rate=44100, bitrate=128000),
              subtitle_track(1, selected=True),
              subtitle_track(2, lang="eng", codec="ass")]
    snapshot = build_media_info(path, duration=90.0, track_list=tracks)

    assert len(snapshot.section("video").groups) == 2
    assert len(snapshot.section("audio").groups) == 2
    assert len(snapshot.section("subtitle").groups) == 2

    audio = {row.label: row.value
             for row in snapshot.section("audio").groups[0].rows}
    assert audio["Dil"] == "Türkçe"
    assert audio["Codec"] == "E-AC-3"
    # YENI SOZLESME: kanal yerlesimi VE sayisi tek kullanici dostu satirda.
    assert audio["Kanal"] == "5.1 (6 kanal)"
    assert audio["Örnekleme"] == "48 kHz"
    assert audio["Bitrate"] == "640 kb/sn"
    assert audio["Durum"] == "Seçili"
    assert snapshot.section("audio").groups[1].rows[-1].value == "Kullanılmıyor"


def test_video_group_shows_resolution_without_any_aspect_claim(tmp_path):
    path = local_media(tmp_path)
    snapshot = build_media_info(path, duration=90.0,
                                track_list=[video_track(1)])

    rows = {row.label: row.value
            for row in snapshot.section("video").groups[0].rows}
    assert rows["Çözünürlük"] == "1920 × 1080"
    assert rows["Codec"] == "H264"
    assert rows["FPS"] == "23,976 fps"
    assert rows["Bitrate"] == "8000 kb/sn"
    # 1920x1080 OLDUGU ICIN `16:9` VARSAYILMAZ: piksel olculeri goruntu
    # oraninin guvenilir kaynagi degildir.
    assert "Görüntü oranı" not in rows


@pytest.mark.parametrize("width, height", ((1920, 1080), (720, 576),
                                           (1280, 720), (0, 1080), (1, 997)))
def test_no_track_ever_gets_an_aspect_ratio_row(tmp_path, width, height):
    """Anamorfik kaynak yanlis oran uretiyordu; satir KAPSAM DISI.

    720x576 PAL anamorfik kaynak gercekte 16:9 olabilir; piksel oranindan
    uretilen `5:4` kullaniciya YANLIS bilgi verir. HDR gibi bu satir da
    guvenilir MPV property sozlesmesi arastirilana kadar sonraki surume
    birakildi.
    """
    path = local_media(tmp_path)
    snapshot = build_media_info(
        path, duration=90.0,
        track_list=[video_track(1, width=width, height=height)])

    visible = snapshot.visible_text()
    rows = {row.label for row in snapshot.section("video").groups[0].rows}
    assert "Görüntü oranı" not in rows
    assert "Görüntü oranı" not in visible
    for wrong in ("5:4", "16:9", "4:3", "21:9"):
        assert wrong not in visible, f"oran iddiasi sizdi: {wrong}"


def test_an_external_subtitle_shows_only_its_basename(tmp_path):
    path = local_media(tmp_path)
    srt = os.path.join(os.path.dirname(path), "Bolum 1.tr.srt")
    snapshot = build_media_info(
        path, duration=90.0,
        track_list=[subtitle_track(1, external=True, filename=srt)])

    rows = {row.label: row.value
            for row in snapshot.section("subtitle").groups[0].rows}
    assert rows["Kaynak"] == "Harici"
    assert rows["Dosya"] == "Bolum 1.tr.srt"
    visible = snapshot.visible_text()
    assert os.path.dirname(srt) not in visible
    assert srt not in visible


def test_empty_sections_get_a_single_clear_message(tmp_path):
    path = local_media(tmp_path)
    snapshot = build_media_info(path, duration=90.0, track_list=[])

    for key, message in (("video", "Video parçası yok."),
                         ("audio", "Ses parçası yok."),
                         ("subtitle", "Altyazı parçası yok.")):
        section = snapshot.section(key)
        assert section.groups == ()
        assert section.empty_message == message


def test_unknown_codes_and_raw_keys_never_reach_the_user(tmp_path):
    path = local_media(tmp_path)
    tracks = [video_track(1, codec="cok-uzun-bilinmeyen-codec"),
              audio_track(1, lang="und", codec="", channels=0, rate=0,
                          bitrate=0),
              subtitle_track(1, lang="unknown", codec="")]
    snapshot = build_media_info(path, duration=90.0, track_list=tracks)

    visible = snapshot.visible_text()
    for forbidden in ("demux-", "None", "und", "unknown", "id=", "external",
                      "cok-uzun-bilinmeyen-codec", "{", "}", "'"):
        assert forbidden not in visible, f"ham deger sizdi: {forbidden}"
    audio_rows = {row.label for row
                  in snapshot.section("audio").groups[0].rows}
    assert audio_rows == {"Durum"}, f"bos alanlar gizlenmedi: {audio_rows}"


def test_hdr_is_not_part_of_the_first_version(tmp_path):
    path = local_media(tmp_path)
    snapshot = build_media_info(
        path, duration=90.0,
        track_list=[video_track(1)],
        property_reader=reader_for({"file-format": "matroska",
                                    "metadata": {},
                                    "video-params/gamma": "pq"}))

    assert "HDR" not in snapshot.visible_text()


# =====================================================================
# 8. Tazeleme anahtari
# =====================================================================

def test_the_refresh_key_is_stable_for_equal_input(tmp_path):
    path = local_media(tmp_path)
    tracks = [video_track(1), audio_track(1), subtitle_track(1)]
    copies = [dict(reversed(list(track.items()))) for track in tracks]

    first = media_info_refresh_key(path, 90.2, tracks)
    second = media_info_refresh_key(path, 90.4, copies)

    assert first == second, "dict sirasi veya kesirli saniye anahtari degistirdi"


def test_a_selection_change_moves_the_key_without_changing_track_count(tmp_path):
    path = local_media(tmp_path)
    before = [audio_track(1, selected=True), audio_track(2, selected=False)]
    after = [audio_track(1, selected=False), audio_track(2, selected=True)]

    assert len(before) == len(after)
    assert media_info_refresh_key(path, 90.0, before) != \
        media_info_refresh_key(path, 90.0, after)


def test_a_late_track_and_a_new_media_both_move_the_key(tmp_path):
    path = local_media(tmp_path)
    other = local_media(tmp_path, name="Bolum 2.mkv")
    base = [video_track(1)]

    assert media_info_refresh_key(path, 90.0, base) != \
        media_info_refresh_key(path, 90.0, base + [subtitle_track(9)])
    assert media_info_refresh_key(path, 90.0, base) != \
        media_info_refresh_key(other, 90.0, base)
    assert media_info_refresh_key(path, 90.0, base) != \
        media_info_refresh_key(path, 91.0, base)


def test_the_refresh_key_survives_broken_tracks(tmp_path):
    path = local_media(tmp_path)

    key = media_info_refresh_key(path, 90.0, [None, "bozuk", {"type": "sub"}])

    assert isinstance(key, tuple)


# =====================================================================
# 9. GERCEK Qt bagimsizligi
# =====================================================================

def test_the_builder_never_pulls_qt_into_the_process():
    """`app.media_info` SAF olmali: import zinciri Qt YUKLEMEMELI.

    `app.errors` PyQt6.QtWidgets, `app.utils` PyQt6.QtGui yukler; bu iki
    modul uzerinden Qt DOLAYLI olarak geliyordu. Olcum ayri bir surecte
    yapilir, cunku bu test surecine Qt baska testlerden zaten girmis olabilir.
    """
    import subprocess
    import sys

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    probe = (
        "import sys; import app.media_info as m; "
        "print(','.join(sorted(n for n in sys.modules "
        "if n == 'PyQt6' or n.startswith('PyQt6.') "
        "or n in ('app.errors', 'app.utils'))))")
    result = subprocess.run([sys.executable, "-c", probe], cwd=root,
                            capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    leaked = [name for name in result.stdout.strip().split(",") if name]
    assert leaked == [], f"saf katmana sizan modul: {leaked}"


def test_the_builder_source_does_not_import_qt_backed_modules():
    """Kaynak seviyesinde de kilitlenir; dolayli zincir geri gelmesin."""
    import app.media_info as media_info

    with open(media_info.__file__, encoding="utf-8") as handle:
        source = handle.read()

    for forbidden in ("app.errors", "app.utils", "PyQt6"):
        assert f"import {forbidden}" not in source and \
            f"from {forbidden}" not in source, f"yasak import: {forbidden}"
    # `app.track_labels` SAFTIR (hic import'u yoktur) ve kullanilabilir.
    assert "from app.track_labels import" in source


@pytest.mark.parametrize("size, expected", (
    (2048, "2,0 KB"),
    (512, "512 bayt"),
    (3 * 1024 * 1024, "3,0 MB"),
))
def test_the_local_size_text_keeps_its_turkish_format(tmp_path, size,
                                                      expected):
    # NOT: Govde parametre OLARAK gecirilmez; pytest test kimligine girip
    # `PYTEST_CURRENT_TEST` ortam degiskenini tasiriyordu.
    path = local_media(tmp_path, name=f"B{size}.mkv", payload=b"0" * size)
    snapshot = build_media_info(path, duration=1.0)

    rows = {row.label: row.value
            for row in snapshot.section("general").groups[0].rows}
    assert rows["Boyut"] == expected


@pytest.mark.parametrize("seconds, expected", (
    (3725.4, "01:02:05"),
    (330.0, "05:30"),
    (59.9, "00:59"),
    (7200, "02:00:00"),
))
def test_the_duration_text_keeps_its_existing_format(tmp_path, seconds,
                                                     expected):
    path = local_media(tmp_path)
    snapshot = build_media_info(path, duration=seconds)

    rows = {row.label: row.value
            for row in snapshot.section("general").groups[0].rows}
    assert rows["Süre"] == expected


# =====================================================================
# 10. GERCEK ses kanal yerlesimi (`demux-channels`)
# =====================================================================

def test_the_real_libmpv_channel_layout_field_is_read(tmp_path):
    """Gercek alan `demux-channels`; sayi alani HIC olmayabilir."""
    path = local_media(tmp_path)
    track = {"id": 1, "type": "audio", "selected": True, "lang": "tur",
             "codec": "eac3", "demux-channels": "5.1(side)"}

    snapshot = build_media_info(path, duration=90.0, track_list=[track])

    rows = {row.label: row.value
            for row in snapshot.section("audio").groups[0].rows}
    assert rows["Kanal"] == "5.1"
    assert "(side)" not in snapshot.visible_text()


def test_the_layout_field_wins_over_the_legacy_double_field(tmp_path):
    path = local_media(tmp_path)
    track = {"id": 1, "type": "audio", "selected": True,
             "demux-channels": "stereo", "demux-channel-layout": "5.1"}

    snapshot = build_media_info(path, duration=90.0, track_list=[track])

    rows = {row.label: row.value
            for row in snapshot.section("audio").groups[0].rows}
    assert rows["Kanal"] == "Stereo"


def test_a_channel_layout_change_moves_the_refresh_key(tmp_path):
    path = local_media(tmp_path)
    before = [{"id": 1, "type": "audio", "selected": True,
               "demux-channels": "stereo"}]
    after = [{"id": 1, "type": "audio", "selected": True,
              "demux-channels": "5.1(side)"}]

    assert media_info_refresh_key(path, 90.0, before) != \
        media_info_refresh_key(path, 90.0, after)


# =====================================================================
# 11. GEC GELEN kapsayici / metadata refresh key'i oynatmali
# =====================================================================

def test_a_late_container_moves_the_refresh_key(tmp_path):
    path = local_media(tmp_path)
    tracks = [video_track(1)]

    empty = media_info_refresh_key(path, 90.0, tracks,
                                   property_reader=reader_for(
                                       {"file-format": None, "metadata": {}}))
    arrived = media_info_refresh_key(path, 90.0, tracks,
                                     property_reader=reader_for(
                                         {"file-format": "matroska",
                                          "metadata": {}}))

    assert empty != arrived


def test_a_late_metadata_title_moves_the_refresh_key(tmp_path):
    path = local_media(tmp_path)
    tracks = [video_track(1)]

    empty = media_info_refresh_key(path, 90.0, tracks,
                                   property_reader=reader_for(
                                       {"file-format": "matroska",
                                        "metadata": {}}))
    arrived = media_info_refresh_key(path, 90.0, tracks,
                                     property_reader=reader_for(
                                         {"file-format": "matroska",
                                          "metadata": {"title": "Bolum Bir"}}))

    assert empty != arrived


def test_the_refresh_key_without_a_reader_stays_backwards_compatible(tmp_path):
    """Okuyucu verilmezse anahtar, okunamayan okuyucuyla AYNI olmali."""
    path = local_media(tmp_path)
    tracks = [video_track(1)]

    def angry(name):
        raise RuntimeError("mpv property okunamadi")

    assert media_info_refresh_key(path, 90.0, tracks) == \
        media_info_refresh_key(path, 90.0, tracks, property_reader=angry)


def test_raw_metadata_never_reaches_the_refresh_key(tmp_path):
    path = local_media(tmp_path)
    reader = reader_for({"file-format": "matroska,webm",
                         "metadata": {"title": "Kotu\x07Ad", "comment": "gizli",
                                      "encoder": "x265"}})

    key = media_info_refresh_key(path, 90.0, [video_track(1)],
                                 property_reader=reader)
    flat = repr(key)

    assert "\x07" not in flat
    assert "gizli" not in flat and "encoder" not in flat and "x265" not in flat
    assert "Kotu Ad" in flat, "sanitize edilmis baslik anahtarda olmali"

# =====================================================================
# 12. KULLANICI DOSTU tek sayfa alanlari (yeni sozlesme)
# =====================================================================

def rows_of(section, index=0):
    return {row.label: row.value for row in section.groups[index].rows}


def test_the_general_section_shows_an_overall_bitrate(tmp_path):
    """Yerel dosyada guvenilir boyut + sure varsa genel bitrate."""
    path = local_media(tmp_path, name="B.mkv", payload=b"0" * 1_000_000)
    snapshot = build_media_info(path, duration=80.0)

    rows = rows_of(snapshot.section("general"))
    # 1_000_000 * 8 / 80 = 100_000 bit/sn
    assert rows["Genel bitrate"] == "100 kb/sn"


@pytest.mark.parametrize("duration", (0, -5))
def test_no_overall_bitrate_without_a_reliable_duration(tmp_path, duration):
    path = local_media(tmp_path, name="C.mkv", payload=b"0" * 4096)
    snapshot = build_media_info(path, duration=duration)

    assert "Genel bitrate" not in rows_of(snapshot.section("general"))


def test_a_url_never_gets_an_overall_bitrate():
    snapshot = build_media_info(SECRET_URL, duration=120.0)

    assert "Genel bitrate" not in rows_of(snapshot.section("general"))


def test_the_video_group_shows_the_safe_extra_fields(tmp_path):
    path = local_media(tmp_path)
    track = video_track(1, codec="hevc")
    track.update({"codec-desc": "H.265 / HEVC (Main 10)",
                  "codec-profile": "Main 10",
                  "format-name": "yuv420p10",
                  "dolby-vision-profile": 8,
                  "default": True})
    snapshot = build_media_info(
        path, duration=90.0, track_list=[track],
        property_reader=reader_for({"file-format": "matroska",
                                    "metadata": {},
                                    "video-params/aspect": 1.7777777,
                                    "video-params/pixelformat": "yuv420p10",
                                    "video-params/primaries": "bt.2020"}))

    rows = rows_of(snapshot.section("video"))
    assert rows["Codec"] == "HEVC"
    assert rows["Codec açıklaması"] == "H.265 / HEVC (Main 10)"
    assert rows["Profil"] == "Main 10"
    assert rows["Çözünürlük"] == "1920 × 1080"
    assert rows["Görüntü oranı"] == "16:9"
    assert rows["Piksel biçimi"] == "YUV420P10"
    assert rows["Bit derinliği"] == "10 bit"
    # `primaries` GAMUT'tur, renk ARALIGI degildir.
    assert rows["Renk standardı"] == "BT.2020 (UHD)"
    assert "Renk aralığı" not in rows
    assert rows["Dolby Vision"] == "Profil 8"
    assert rows["Varsayılan"] == "Evet"
    assert rows["Durum"] == "Seçili"


def test_the_aspect_never_comes_from_plain_pixel_size(tmp_path):
    """Anamorfik 720x576: guvenilir kaynak YOKSA oran satiri da yok."""
    path = local_media(tmp_path)
    snapshot = build_media_info(
        path, duration=90.0,
        track_list=[video_track(1, width=720, height=576)])

    rows = rows_of(snapshot.section("video"))
    assert "Görüntü oranı" not in rows
    assert "5:4" not in snapshot.visible_text()


def test_a_reliable_par_produces_the_real_aspect(tmp_path):
    """Anamorfik kaynak + guvenilir `demux-par` -> gercek oran."""
    path = local_media(tmp_path)
    track = video_track(1, width=720, height=576)
    track["demux-par"] = 1.4222222
    snapshot = build_media_info(path, duration=90.0, track_list=[track])

    assert rows_of(snapshot.section("video"))["Görüntü oranı"] == "16:9"


def test_the_audio_group_shows_channels_and_extra_fields(tmp_path):
    path = local_media(tmp_path)
    track = audio_track(1, codec="eac3")
    track.update({"demux-channels": "5.1(side)", "codec-desc": "E-AC-3 JOC",
                  "codec-profile": "Dolby Digital Plus + Dolby Atmos",
                  "demux-duration": 3725.0, "default": True, "forced": True})
    snapshot = build_media_info(path, duration=90.0, track_list=[track])

    rows = rows_of(snapshot.section("audio"))
    assert rows["Kanal"] == "5.1 (6 kanal)"
    assert rows["Örnekleme"] == "48 kHz"
    assert rows["Parça süresi"] == "01:02:05"
    assert rows["Ses biçimi"] == "Dolby Atmos"
    assert rows["Varsayılan"] == "Evet"
    assert rows["Zorunlu"] == "Evet"


def test_atmos_is_never_guessed_from_the_codec_name(tmp_path):
    path = local_media(tmp_path)
    track = audio_track(1, codec="truehd")
    track["codec-desc"] = "TrueHD"
    snapshot = build_media_info(path, duration=90.0, track_list=[track])

    rows = rows_of(snapshot.section("audio"))
    assert "Ses biçimi" not in rows
    assert "Atmos" not in snapshot.visible_text()


def test_the_subtitle_group_shows_the_user_friendly_flags(tmp_path):
    path = local_media(tmp_path)
    srt = os.path.join(os.path.dirname(path), "Bolum 1.tr.srt")
    track = subtitle_track(1, external=True, filename=srt)
    track.update({"default": True, "forced": True, "hearing-impaired": True,
                  "title": "Türkçe SDH"})
    snapshot = build_media_info(path, duration=90.0, track_list=[track])

    rows = rows_of(snapshot.section("subtitle"))
    assert rows["Kaynak"] == "Harici"
    assert rows["Dosya"] == "Bolum 1.tr.srt"
    assert rows["Varsayılan"] == "Evet"
    assert rows["Zorunlu"] == "Evet"
    assert rows["İşitme engelliler için"] == "Evet"


def test_the_diagnostic_fields_are_deliberately_hidden(tmp_path):
    """Rapor dokumune donusmemeli: kimlikler ve teshis alanlari YOK."""
    path = local_media(tmp_path)
    track = video_track(1)
    track.update({"src-id": 7, "ff-index": 3,
                  "decoder-desc": "libx264 (H.264)",
                  "replaygain-track-peak": 0.98,
                  "demux-rotation": 0})
    audio = audio_track(1)
    audio["ff-index"] = 4
    snapshot = build_media_info(path, duration=90.0,
                                track_list=[track, audio])

    visible = snapshot.visible_text()
    for forbidden in ("src-id", "ff-index", "Unique", "libx264",
                      "replaygain", "dialnorm", "compr", "Writing",
                      "Bits/(Pixel", "demux-", "None"):
        assert forbidden not in visible, f"teşhis alanı sızdı: {forbidden}"


@pytest.mark.parametrize("value", (None, "", "   ", 0, -1, "unknown"))
def test_unreliable_extra_values_hide_their_rows(tmp_path, value):
    path = local_media(tmp_path)
    track = video_track(1)
    track.update({"codec-desc": value, "codec-profile": value,
                  "format-name": value, "dolby-vision-profile": value})
    snapshot = build_media_info(path, duration=90.0, track_list=[track])

    rows = rows_of(snapshot.section("video"))
    for label in ("Codec açıklaması", "Profil", "Piksel biçimi",
                  "Bit derinliği", "Dolby Vision"):
        assert label not in rows, f"güvenilmez değer satır üretti: {label}"


def test_a_broken_video_params_read_hides_only_those_rows(tmp_path):
    path = local_media(tmp_path)

    def angry(name):
        raise RuntimeError("property okunamadı")

    snapshot = build_media_info(path, duration=90.0,
                                track_list=[video_track(1)],
                                property_reader=angry)

    rows = rows_of(snapshot.section("video"))
    assert "Çözünürlük" in rows
    assert "Görüntü oranı" not in rows
    assert "Renk standardı" not in rows
    assert "Renk aralığı" not in rows


def test_the_new_display_fields_move_the_refresh_key(tmp_path):
    path = local_media(tmp_path)
    plain = [video_track(1)]
    rich = [dict(video_track(1), **{"codec-desc": "H.264", "default": True})]

    assert media_info_refresh_key(path, 90.0, plain) != \
        media_info_refresh_key(path, 90.0, rich)


def test_the_video_params_move_the_refresh_key(tmp_path):
    path = local_media(tmp_path)
    tracks = [video_track(1)]
    base = {"file-format": "matroska", "metadata": {}}

    without = media_info_refresh_key(
        path, 90.0, tracks, property_reader=reader_for(dict(base)))
    with_params = media_info_refresh_key(
        path, 90.0, tracks,
        property_reader=reader_for(dict(base, **{
            "video-params/aspect": 1.7777777,
            "video-params/pixelformat": "yuv420p10",
            "video-params/primaries": "bt.2020"})))

    assert without != with_params

# =====================================================================
# 13. Renk standardi (gamut) ile renk araligi (levels) AYRIDIR
# =====================================================================

def color_rows(tmp_path, **params):
    path = local_media(tmp_path, name="Renk.mkv")
    values = {"file-format": "matroska", "metadata": {}}
    values.update(params)
    snapshot = build_media_info(path, duration=90.0,
                                track_list=[video_track(1)],
                                property_reader=reader_for(values))
    return rows_of(snapshot.section("video"))


@pytest.mark.parametrize("levels, expected", (("limited", "Sınırlı"),
                                              ("full", "Tam")))
def test_the_colour_range_comes_from_colorlevels(tmp_path, levels, expected):
    rows = color_rows(tmp_path, **{"video-params/colorlevels": levels})

    assert rows["Renk aralığı"] == expected


def test_the_colour_standard_comes_from_primaries(tmp_path):
    rows = color_rows(tmp_path, **{"video-params/primaries": "bt.709"})

    assert rows["Renk standardı"] == "BT.709 (HD)"
    assert "Renk aralığı" not in rows


def test_both_fields_appear_side_by_side(tmp_path):
    rows = color_rows(tmp_path, **{"video-params/primaries": "bt.2020",
                                   "video-params/colorlevels": "limited"})

    assert rows["Renk standardı"] == "BT.2020 (UHD)"
    assert rows["Renk aralığı"] == "Sınırlı"


def test_only_colorlevels_yields_only_the_range(tmp_path):
    rows = color_rows(tmp_path, **{"video-params/colorlevels": "full"})

    assert rows["Renk aralığı"] == "Tam"
    assert "Renk standardı" not in rows


@pytest.mark.parametrize("primaries, levels", (
    ("uydurma-gamut", "uydurma-levels"),
    ("unknown", "unknown"),
    (None, None),
    ("", ""),
))
def test_unknown_colour_values_are_never_shown_raw(tmp_path, primaries,
                                                   levels):
    rows = color_rows(tmp_path, **{"video-params/primaries": primaries,
                                   "video-params/colorlevels": levels})

    assert "Renk standardı" not in rows
    assert "Renk aralığı" not in rows


def test_colour_fields_are_only_used_for_the_selected_video(tmp_path):
    path = local_media(tmp_path, name="Ikili.mkv")
    snapshot = build_media_info(
        path, duration=90.0,
        track_list=[video_track(1, selected=True),
                    video_track(2, selected=False)],
        property_reader=reader_for({
            "file-format": "matroska", "metadata": {},
            "video-params/primaries": "bt.2020",
            "video-params/colorlevels": "limited"}))

    first = rows_of(snapshot.section("video"), 0)
    second = rows_of(snapshot.section("video"), 1)
    assert first["Renk standardı"] == "BT.2020 (UHD)"
    assert first["Renk aralığı"] == "Sınırlı"
    assert "Renk standardı" not in second
    assert "Renk aralığı" not in second


def test_colorlevels_is_part_of_the_safe_property_set():
    from app.media_info import VIDEO_PARAM_PROPERTIES

    assert "video-params/colorlevels" in VIDEO_PARAM_PROPERTIES


def test_a_colour_change_moves_the_refresh_key(tmp_path):
    path = local_media(tmp_path, name="Anahtar.mkv")
    tracks = [video_track(1)]
    base = {"file-format": "matroska", "metadata": {},
            "video-params/primaries": "bt.709"}

    limited = media_info_refresh_key(
        path, 90.0, tracks,
        property_reader=reader_for(dict(base, **{
            "video-params/colorlevels": "limited"})))
    full = media_info_refresh_key(
        path, 90.0, tracks,
        property_reader=reader_for(dict(base, **{
            "video-params/colorlevels": "full"})))

    assert limited != full
