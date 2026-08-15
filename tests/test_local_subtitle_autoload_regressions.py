"""Video acilisinda ayni klasordeki eslesen SRT'yi SESSIZ etkinlestirme (2B).

Sozlesme kaynagi: `docs/PROJECT_STATUS.md` (14 Agustos 2026 arastirmasi).

- `MPV_CONFIG` genis `sub_auto="fuzzy"` yerine `exact` kullanir; global
  `sub_visibility="no"` KALIR ve yalniz DOGRULANMIS yerel SRT bulununca acilir.
- Aday yalniz yerel videonun GERCEK klasorundeki `.srt` dosyasidir.
- Tam video govdesi zorunludur: `Film.2026.mkv` icin `Film.2026.srt`,
  `Film.2026.tr.srt`, `Film.2026.tur.srt`, `Film.2026.tr.forced.srt`,
  `Film.2026.tr.sdh.srt` gecerlidir; `Film.srt`, `Baska Film.srt` ve
  `Film.2026 Turkce.srt` gecerli DEGILDIR.
- Duz `<video-adi>.srt` birinci; yoksa Altyazi Merkezi'nin kayitli dili
  (`Türkçe` -> `tr`/`tur`); kalan esit adaylar DETERMINISTIK secilir.
- `sid`/gorunurluk yalniz `track-list` icinde `external=true`, uzanti `.srt`
  ve `external-filename` tam aday yolu DOGRULANDIKTAN sonra degisir.
- Basari tamamen SESSIZDIR: OSD, QMessageBox veya durum yazisi yoktur.
- Bozuk/okunamayan SRT onceki guvenli state'i bozmaz.
- Her medya icin YALNIZ BIR KEZ denenir; kullanici altyaziyi kapatirsa
  sonraki `track-list`/geometri olaylari onu tekrar acamaz.
- Playlistte yeni videoya gecince yeni medya icin yeniden degerlendirilir.
- URL'de calismaz.
"""
import os

import pytest

import app.local_subtitle as local_subtitle
import app.media_controls as media_controls
import app.player as player_module
from app.config import MPV_CONFIG
from app.local_subtitle import (activate_local_subtitle, choose_subtitle,
                                subtitle_candidates)
from app.player import MPVPlayer

VIDEO_NAME = "Film.2026.mkv"


class FakeMpv:
    def __init__(self, tracks=None):
        self.track_list = list(tracks or [])
        self.sid = None
        self.sub_visibility = False
        self.added = []
        self.fail_on_add = False
        self._next_id = max([t.get("id", 0) for t in self.track_list] or [0]) + 1

    def sub_add(self, path, *args):
        if self.fail_on_add:
            raise RuntimeError("sub-add reddedildi")
        self.added.append(path)
        self.track_list.append(loaded_track(path, self._next_id))
        self._next_id += 1

    def sub_remove(self, sid):
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


class FakeFrame:
    def __init__(self):
        self.osd = []
        self.playlist_panel = None

    def show_osd(self, text, *args, **kwargs):
        self.osd.append(text)

    def _update_overlay_subtitle_state(self):
        pass


class FakePlayer:
    """Urun metodlari OLDUGU GIBI baglanir; govde kopyalanmaz."""

    _activate_dropped_subtitle = MPVPlayer._activate_dropped_subtitle
    _subtitle_track_wait = MPVPlayer._subtitle_track_wait

    def __init__(self, mpv, current_file, language="Türkçe"):
        self.mpv_player = mpv
        self.video_frame = FakeFrame()
        self.current_file = current_file
        self.duration = 120.0
        self._auto_local_subtitle_file = None
        self._auto_local_subtitle_state = None
        self._auto_local_subtitle_target = None
        self._drop_subtitle_session = None
        self._pending_subs = []
        self.subtitle_language = language


def make_media(tmp_path, names=(), video=VIDEO_NAME):
    path = tmp_path / video
    path.write_bytes(b"0")
    for name in names:
        (tmp_path / name).write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nmerhaba\n", encoding="utf-8")
    return str(path)


def loaded_track(path, identifier=1):
    """mpv `sub_auto=exact` ile YUKLENMIS dis altyazi track'i."""
    return {"id": identifier, "type": "sub", "external": True,
            "external-filename": path}


# =====================================================================
# 1. Yapilandirma
# =====================================================================

def test_the_media_config_uses_exact_auto_subtitles():
    assert MPV_CONFIG["sub_auto"] == "exact"


def test_subtitles_stay_globally_hidden_by_default():
    assert MPV_CONFIG["sub_visibility"] == "no"


# =====================================================================
# 2. Ad eslestirme
# =====================================================================

def test_the_plain_name_is_a_candidate(tmp_path):
    video = make_media(tmp_path, ["Film.2026.srt"])

    names = [os.path.basename(p) for p in subtitle_candidates(video)]

    assert names == ["Film.2026.srt"]


def test_language_suffixes_are_candidates(tmp_path):
    video = make_media(tmp_path, ["Film.2026.tr.srt", "Film.2026.tur.srt"])

    names = sorted(os.path.basename(p) for p in subtitle_candidates(video))

    assert names == ["Film.2026.tr.srt", "Film.2026.tur.srt"]


def test_forced_and_sdh_tags_are_candidates(tmp_path):
    video = make_media(tmp_path, ["Film.2026.tr.forced.srt",
                                  "Film.2026.tr.sdh.srt"])

    names = sorted(os.path.basename(p) for p in subtitle_candidates(video))

    assert names == ["Film.2026.tr.forced.srt", "Film.2026.tr.sdh.srt"]


def test_short_or_unrelated_names_are_not_candidates(tmp_path):
    video = make_media(tmp_path, ["Film.srt", "Baska Film.srt",
                                  "Film.2026 Turkce.srt", "notlar.srt"])

    assert subtitle_candidates(video) == []


def test_only_srt_files_are_candidates(tmp_path):
    video = make_media(tmp_path, [])
    for name in ("Film.2026.ass", "Film.2026.vtt", "Film.2026.sub"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    assert subtitle_candidates(video) == []


# =====================================================================
# 3. Secim onceligi
# =====================================================================

def test_the_plain_name_wins_over_language_variants(tmp_path):
    video = make_media(tmp_path, ["Film.2026.srt", "Film.2026.tr.srt",
                                  "Film.2026.en.srt"])

    chosen = choose_subtitle(video, language="Türkçe")

    assert os.path.basename(chosen) == "Film.2026.srt"


def test_the_saved_language_wins_when_there_is_no_plain_name(tmp_path):
    video = make_media(tmp_path, ["Film.2026.en.srt", "Film.2026.tr.srt",
                                  "Film.2026.de.srt"])

    chosen = choose_subtitle(video, language="Türkçe")

    assert os.path.basename(chosen) == "Film.2026.tr.srt"


def test_another_saved_language_selects_its_own_variant(tmp_path):
    video = make_media(tmp_path, ["Film.2026.en.srt", "Film.2026.tr.srt"])

    chosen = choose_subtitle(video, language="İngilizce")

    assert os.path.basename(chosen) == "Film.2026.en.srt"


def test_the_remaining_candidates_are_deterministic(tmp_path):
    video = make_media(tmp_path, ["Film.2026.pl.srt", "Film.2026.it.srt"])

    first = choose_subtitle(video, language="Türkçe")
    again = choose_subtitle(video, language="Türkçe")

    assert first == again
    assert os.path.basename(first) == "Film.2026.it.srt"


def test_no_candidate_yields_no_choice(tmp_path):
    video = make_media(tmp_path, ["baskasi.srt"])

    assert choose_subtitle(video, language="Türkçe") is None


# =====================================================================
# 4. Etkinlestirme: dogrulama ve sessizlik
# =====================================================================

def test_a_verified_track_is_selected_and_made_visible(tmp_path):
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}, loaded_track(srt, 2)])
    player = FakePlayer(mpv, video)

    assert activate_local_subtitle(player) is True
    assert mpv.sid == 2
    assert mpv.sub_visibility is True


def test_the_activation_is_completely_silent(tmp_path):
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    mpv = FakeMpv(tracks=[loaded_track(srt, 2)])
    player = FakePlayer(mpv, video)

    activate_local_subtitle(player)

    assert player.video_frame.osd == []


def test_an_embedded_track_is_never_selected(tmp_path):
    """Dis olmayan track (external=False) dogrulama gecmez."""
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    mpv = FakeMpv(tracks=[{"id": 1, "type": "sub", "lang": "tur"},
                          {"id": 2, "type": "sub", "external": False,
                           "external-filename": srt}])
    player = FakePlayer(mpv, video)

    assert activate_local_subtitle(player) is False
    assert mpv.sid is None
    assert mpv.sub_visibility is False


def test_a_broken_subtitle_leaves_the_previous_state_untouched(tmp_path):
    """Bozuk SRT mpv tarafindan yuklenemez: track olusmaz, state korunur."""
    video = make_media(tmp_path, ["Film.2026.srt"])
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}])
    player = FakePlayer(mpv, video)

    assert activate_local_subtitle(player) is False
    assert mpv.sid is None
    assert mpv.sub_visibility is False
    assert player.video_frame.osd == []


def test_a_url_is_never_auto_activated(tmp_path):
    mpv = FakeMpv()
    player = FakePlayer(mpv, "https://example.com/film.2026.mkv")

    assert activate_local_subtitle(player) is False
    assert mpv.sub_visibility is False


# =====================================================================
# 5. Tek atim ve playlist
# =====================================================================

def test_the_activation_happens_only_once_per_media(tmp_path):
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    mpv = FakeMpv(tracks=[loaded_track(srt, 2)])
    player = FakePlayer(mpv, video)
    assert activate_local_subtitle(player) is True

    # Kullanici altyaziyi KAPATTI; sonraki olaylar tekrar acmamali.
    mpv.sub_visibility = False
    mpv.sid = None

    assert activate_local_subtitle(player) is False
    assert mpv.sub_visibility is False
    assert mpv.sid is None


def test_a_new_playlist_item_is_evaluated_again(tmp_path):
    first = make_media(tmp_path, ["Film.2026.srt"])
    first_srt = str(tmp_path / "Film.2026.srt")
    second = make_media(tmp_path, ["Bolum.2.tr.srt"], video="Bolum.2.mkv")
    second_srt = str(tmp_path / "Bolum.2.tr.srt")
    mpv = FakeMpv(tracks=[loaded_track(first_srt, 2)])
    player = FakePlayer(mpv, first)
    assert activate_local_subtitle(player) is True

    # Playlist sonraki parcaya gecti: yeni medya, yeni track listesi.
    player.current_file = second
    mpv.track_list = [loaded_track(second_srt, 3)]
    mpv.sid = None
    mpv.sub_visibility = False

    assert activate_local_subtitle(player) is True
    assert mpv.sid == 3
    assert mpv.sub_visibility is True


# =====================================================================
# 6. GEC GELEN TRACK YARISI (durum modeli)
# =====================================================================

def test_a_late_external_track_is_still_activated(tmp_path):
    """`track_list` once yalniz video/audio icerir; SRT SONRA gelir."""
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"},
                          {"id": 1, "type": "audio"}])
    player = FakePlayer(mpv, video)

    assert activate_local_subtitle(player) is False   # karar BITMEDI
    assert mpv.sub_visibility is False

    mpv.track_list.append(loaded_track(srt, 2))       # track gecikmeli geldi

    assert activate_local_subtitle(player) is True
    assert mpv.sid == 2
    assert mpv.sub_visibility is True


def test_a_late_track_activation_is_not_repeated_after_the_user_closes_it(tmp_path):
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}])
    player = FakePlayer(mpv, video)
    activate_local_subtitle(player)
    mpv.track_list.append(loaded_track(srt, 2))
    assert activate_local_subtitle(player) is True

    mpv.sub_visibility = False                        # kullanici KAPATTI
    mpv.sid = None

    assert activate_local_subtitle(player) is False
    assert mpv.sub_visibility is False
    assert mpv.sid is None


def test_a_media_without_candidates_is_decided_immediately(tmp_path):
    """Aday yoksa karar TAMAMLANIR; her turda yeniden taranmaz."""
    video = make_media(tmp_path, ["baskasi.srt"])
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}])
    player = FakePlayer(mpv, video)

    assert activate_local_subtitle(player) is False
    assert player._auto_local_subtitle_state == "done"


def test_a_pending_media_does_not_rescan_the_folder_every_turn(tmp_path, monkeypatch):
    """PENDING sirasinda klasor/QSettings YENIDEN taranmaz; hedef onbellekte."""
    video = make_media(tmp_path, ["Film.2026.srt"])
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}])
    player = FakePlayer(mpv, video)
    calls = []
    real = local_subtitle.choose_subtitle
    monkeypatch.setattr(local_subtitle, "choose_subtitle",
                        lambda *a, **k: (calls.append(1), real(*a, **k))[1])

    activate_local_subtitle(player)
    activate_local_subtitle(player)
    activate_local_subtitle(player)

    assert player._auto_local_subtitle_state == "pending"
    assert len(calls) == 1


def test_a_new_media_resets_the_pending_state(tmp_path):
    first = make_media(tmp_path, ["Film.2026.srt"])
    second = make_media(tmp_path, ["Bolum.2.srt"], video="Bolum.2.mkv")
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}])
    player = FakePlayer(mpv, first)
    activate_local_subtitle(player)
    assert player._auto_local_subtitle_state == "pending"

    player.current_file = second
    mpv.track_list = [loaded_track(str(tmp_path / "Bolum.2.srt"), 5)]

    assert activate_local_subtitle(player) is True
    assert mpv.sid == 5


# =====================================================================
# 7. ADAY ADI: ilk ek DIL, sonrakiler ETIKET
# =====================================================================

@pytest.mark.parametrize("name", ["Film.2026.srt", "Film.2026.tr.srt",
                                  "Film.2026.tur.srt", "Film.2026.tr.sdh.srt",
                                  "Film.2026.tr.forced.srt"])
def test_accepted_candidate_names(tmp_path, name):
    video = make_media(tmp_path, [name])

    assert [os.path.basename(p) for p in subtitle_candidates(video)] == [name]


@pytest.mark.parametrize("name", ["Film.2026.sdh.srt", "Film.2026.forced.srt",
                                  "Film.2026.sdh.tr.srt", "Film.srt",
                                  "Baska Film.srt", "Film.2026 Turkce.srt"])
def test_rejected_candidate_names(tmp_path, name):
    video = make_media(tmp_path, [name])

    assert subtitle_candidates(video) == []


# =====================================================================
# 8. KULLANICI SECIMI OTOMASYON TARAFINDAN EZILMEZ
# =====================================================================

def test_a_successful_manual_choice_is_not_overridden(tmp_path):
    """Kullanici Custom.srt birakti: otomatik Film.2026.srt onu EZMEZ."""
    video = make_media(tmp_path, ["Film.2026.srt"])
    custom = tmp_path / "Custom.srt"
    custom.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}])
    player = FakePlayer(mpv, video)

    assert player._activate_dropped_subtitle(str(custom)) is True
    chosen = mpv.sid
    assert chosen is not None

    # mpv `sub_auto=exact` yerel SRT'yi de yuklemis olabilir.
    mpv.track_list.append(loaded_track(str(tmp_path / "Film.2026.srt"), 9))

    assert activate_local_subtitle(player) is False
    assert mpv.sid == chosen
    assert mpv.sub_visibility is True


def test_a_failed_manual_drop_does_not_block_the_automation(tmp_path, monkeypatch):
    # Basarisiz birakma gercek `QMessageBox` acar; testte yalniz cagri sayilir.
    monkeypatch.setattr(player_module, "show_user_error", lambda *a, **k: None)
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    custom = tmp_path / "Custom.srt"
    custom.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
    mpv = FakeMpv(tracks=[{"id": 1, "type": "video"}, loaded_track(srt, 2)])
    player = FakePlayer(mpv, video)
    mpv.fail_on_add = True

    assert player._activate_dropped_subtitle(str(custom)) is False

    assert activate_local_subtitle(player) is True
    assert mpv.sid == 2
    assert mpv.sub_visibility is True


def test_an_unloaded_media_is_not_activated(tmp_path):
    video = make_media(tmp_path, ["Film.2026.srt"])
    srt = str(tmp_path / "Film.2026.srt")
    mpv = FakeMpv(tracks=[loaded_track(srt, 2)])
    player = FakePlayer(mpv, video)
    player.duration = 0.0

    assert activate_local_subtitle(player) is False
    assert mpv.sub_visibility is False


# =====================================================================
# 12. `Klasor Ac` + parca degisimi + sessiz yerel SRT BIRLESIMI
# =====================================================================

def _wire_playback(player, mpv, loads):
    """`play_from_playlist()` govdesinin GERCEKTEN dokundugu uclar.

    Yalniz bu ornege eklenir; dosyanin ortak fake'leri degistirilmez.
    `_refresh_playlist_panel`, `_clear_title_bar_raise` ve
    `_mark_title_bar_raise` urunde zaten `getattr` korumalidir.
    """
    def play(path):
        # Gercek mpv gibi: yukleme BASLAR. Yeni dosyanin `track-list`i bu
        # anda HAZIR DEGILDIR; onceki liste kisa sure bayat kalir.
        loads.append({"path": path,
                      "current_file": player.current_file,
                      "sub_visibility": mpv.sub_visibility})

    mpv.play = play
    player.settings = None
    player.play_button = type("_Button", (), {"setIcon": lambda self, i: None})()
    player.pause_icon = object()
    player.is_paused = True
    player.video_frame.control_overlay = None
    player.video_frame.placeholder_label = type(
        "_Label", (), {"hide": lambda self: None})()
    player.set_title = lambda: None
    player.add_recent_file = lambda path: None


def test_a_folder_playlist_activates_each_media_own_subtitle(tmp_path):
    """Klasorden gelen listede HER video kendi SRT'sini sessizce alir.

    Zincir gercek urun kodudur: `folder_media_files()` ->
    `play_from_playlist()` -> `_hide_subtitles_for_new_media()` ->
    `activate_local_subtitle()`. Kritik nokta, ikinci medya yuklenirken
    `track-list`in kisa sure BAYAT kalmasidir: o pencerede Film1'in sid'i
    Film2 adina secilmemeli, karar `pending` kalmalidir.
    """
    first = make_media(tmp_path, ["Film1.srt"], video="Film1.mkv")
    first_srt = str(tmp_path / "Film1.srt")
    second = make_media(tmp_path, ["Film2.srt"], video="Film2.mkv")
    second_srt = str(tmp_path / "Film2.srt")

    # 1. Dogal playlist sirasi (urunun kendi klasor taramasi).
    files = media_controls.folder_media_files(str(tmp_path))
    assert files == [first, second], f"klasor sirasi: {files}"

    mpv = FakeMpv()
    player = FakePlayer(mpv, "")
    player.playlist = list(files)
    player.current_playlist_index = 0
    loads = []
    _wire_playback(player, mpv, loads)

    # --- Film1: gercek oynatma yolu ---
    assert media_controls.play_from_playlist(player, 0) is True
    assert loads[0]["current_file"] == first
    mpv.track_list = [{"id": 1, "type": "video"}, loaded_track(first_srt, 2)]
    player.duration = 120.0

    # 2. Film1.srt TAM `external-filename` dogrulamasiyla secilir.
    assert activate_local_subtitle(player) is True
    assert mpv.sid == 2
    assert mpv.sub_visibility is True

    # 7a. Kullanicinin acik secimi YALNIZ Film1 icin otomasyonu tuketir.
    local_subtitle.suppress_local_subtitle(player)
    assert player._auto_local_subtitle_state == local_subtitle.STATE_DONE

    # --- Film2: ayni gercek oynatma yolu ---
    assert media_controls.play_from_playlist(player, 1) is True

    # 3. `current_file` mpv.play() cagrilmadan ONCE Film2 olmustur.
    assert loads[1]["path"] == second
    assert loads[1]["current_file"] == second
    # 4. Gecis aninda gorunurluk kapatilmistir.
    assert loads[1]["sub_visibility"] is False
    assert mpv.sub_visibility is False

    # 5. `track-list` hala Film1'in: hicbir sey secilmez, karar bitmez.
    player.duration = 120.0
    assert activate_local_subtitle(player) is False
    assert player._auto_local_subtitle_state == local_subtitle.STATE_PENDING
    assert player._auto_local_subtitle_target == second_srt
    assert mpv.sid == 2, "bayat Film1 sid'i Film2 adina degistirildi"
    assert mpv.sub_visibility is False

    # 6. Film2'nin track'i geldi: kendi SRT'si secilir ve gorunur olur.
    mpv.track_list = [{"id": 1, "type": "video"}, loaded_track(second_srt, 3)]
    assert activate_local_subtitle(player) is True
    assert mpv.sid == 3
    assert mpv.sub_visibility is True

    # 7b. Film1'in `done`/suppress durumu Film2'yi ENGELLEMEDI.
    assert player._auto_local_subtitle_file == second
    assert player._auto_local_subtitle_state == local_subtitle.STATE_DONE

    # 8. Secili track Film2'ye aittir; Film1 altyazisi sizmaz.
    chosen = local_subtitle.verified_track_id(mpv.track_list, second_srt)
    assert chosen == mpv.sid
    assert local_subtitle.verified_track_id(mpv.track_list, first_srt) is None
