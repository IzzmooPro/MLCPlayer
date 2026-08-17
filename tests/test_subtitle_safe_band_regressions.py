# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Altyazının kontrol paneline yaklaşırken kesişmemesi: GÜVENLİ ALT BANT.

Gerçek video ölçümündeki kırmızı kanıt (1400×772 yüzey, `sub_pos=100`):

    altyazı bbox = (333, 635, 1065, 739)
    kontrol katmanı üst kenarı = 662
    boşluk = -77 px   → altyazı timeline'ın üstüne biniyordu
    sub_margin_y = 22 (MPV varsayılanı), sub_ass_force_margins = False

Ürün kararı SABİT YÜZDE DEĞİLDİR: `sub_pos` kullanıcının tercihidir,
0-100 aralığı ve %100 varsayılanı korunur. Bunun yerine MPV'ye GERÇEK
ayrılmış banttan türetilen bir alt marj (`sub-margin-y`) yazılır.

NOT: bu libmpv sürümünde (v0.36.0-131) `sub-margin-y-offset` YOKTUR;
ölçüldü. Var olan özellik `sub-margin-y`dir ve `sub-scale-by-window=yes`
iken 720 px referans yüksekliğine göre ölçeklenir.

Ölçüm sonrası (aynı yüzey): bbox alt kenarı 642, boşluk **20 px**;
`%90` → bbox alt kenarı 577, boşluk 85 px.

DÜZELTME (16 Ağustos 2026): bir dönem ölçek referansı RENDER EDİLEN
VİDEO ALANI (`h - mt - mb`) sanıldı. Ölçüm bunun yanlış olduğunu
gösterdi: aynı pencerede letterbox değiştirildiğinde marj eğimi SABİT
kalıyor (`osd h=1360 → 2,881`, `h=639 → 2,881`; iki motorda da).
Referans YÜZEY yüksekliğidir. Eski varsayım yalnız letterbox payı
küçükken (`mt=mb=8`/`28`) doğru sonuç veriyordu; playlist açıkken pay
159 olunca marj 193'e şişip altyazıyı 105 px yukarı atıyordu.
Ayrıca mpv 0.41 marjı `sub-scale` ile ÇARPAR (0.36 çarpmıyordu).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from app import video_frame as video_frame_module
from app.video_frame import (MPV_MARGIN_REFERENCE_HEIGHT, OVERLAY_HEIGHT,
                             SUBTITLE_BAND_GAP,
                             overlay_timeline_top_padding)

#: Altyazinin GERCEKTEN temizledigi bant. Katmanin tamami DEGILDIR:
#: timeline'in gorunmez tiklama payi (bkz. `overlay_timeline_top_padding`)
#: sayilmaz, cunku kullanici orada bir sey GORMUYOR. OSD bandi ise
#: `OVERLAY_HEIGHT` olarak KALIR.
SUBTITLE_RESERVED = OVERLAY_HEIGHT - overlay_timeline_top_padding()


class FakeOverlay:
    """`geometry().height()` ve fade yaşam döngüsü yüzeyi."""

    def __init__(self, height, log=None):
        self._height = height
        self._visible = True
        self._opacity = 1.0
        self.log = log if log is not None else []

    def geometry(self):
        from PyQt6.QtCore import QRect

        return QRect(0, 0, 1400, self._height)

    def isVisible(self):
        return self._visible

    def show(self):
        self._visible = True
        self.log.append("overlay.show")

    def hide(self):
        self._visible = False
        self.log.append("overlay.hide")

    def windowOpacity(self):
        return self._opacity

    def setWindowOpacity(self, value):
        self._opacity = float(value)


class FakeFade:
    """Animasyon vekili; bitiş ürünün kendi `_finish` yolundan sürülür."""

    def __init__(self, log=None):
        self.started = 0
        self.log = log if log is not None else []

    def stop(self):
        pass

    def setDuration(self, value):
        pass

    def setEasingCurve(self, value):
        pass

    def setStartValue(self, value):
        pass

    def setEndValue(self, value):
        pass

    def start(self):
        self.started += 1
        self.log.append("fade.start")


class FakeMpv:
    def __init__(self, fail=False, osd=None, codec="subrip", sid=1, log=None):
        self.written = {}
        self.order = []
        self.log = log if log is not None else []
        self._fail = fail
        self.osd_dimensions = osd
        self.sid = sid
        self.track_list = ([{"type": "sub", "id": sid, "codec": codec}]
                           if codec else [])

    @property
    def write_count(self):
        return len(self.order)

    def __setattr__(self, name, value):
        if name in ("written", "order", "log", "_fail", "osd_dimensions",
                    "sid", "track_list"):
            object.__setattr__(self, name, value)
            return
        if self._fail:
            raise RuntimeError("sentetik mpv hatasi")
        self.written[name] = value
        self.order.append(name)
        self.log.append(f"mpv.{name}")

    def __getattr__(self, name):
        try:
            return object.__getattribute__(self, "written")[name]
        except KeyError:
            raise AttributeError(name)


class Frame:
    """`VideoFrame`in bant hesabını izole eden en küçük vekil.

    Gerçek `VideoFrame` bir `QWidget`tir ve kurulumu mpv/wid ister;
    burada YALNIZ ölçü sözleşmesi (`_osd_reserved_bottom` + yükseklik)
    ve ürünün kendi metotları çalıştırılır.
    """

    _osd_reserved_bottom = video_frame_module.VideoFrame._osd_reserved_bottom
    subtitle_safe_margin = video_frame_module.VideoFrame.subtitle_safe_margin
    subtitle_margin_scale = (
        video_frame_module.VideoFrame.subtitle_margin_scale)
    subtitle_scale_reference = (
        video_frame_module.VideoFrame.subtitle_scale_reference)
    sync_subtitle_safe_band = (
        video_frame_module.VideoFrame.sync_subtitle_safe_band)
    selected_subtitle_codec = (
        video_frame_module.VideoFrame.selected_subtitle_codec)
    # Gözlenen değer yolu: senkron libmpv okumasını gereksiz kılar.
    note_observed_property = (
        video_frame_module.VideoFrame.note_observed_property)
    _observed_property = video_frame_module.VideoFrame._observed_property
    _observed_mpv_values = video_frame_module.VideoFrame._observed_mpv_values
    _OBSERVED_MISSING = video_frame_module.VideoFrame._OBSERVED_MISSING
    subtitle_uses_ass_positioning = (
        video_frame_module.VideoFrame.subtitle_uses_ass_positioning)
    user_subtitle_position = (
        video_frame_module.VideoFrame.user_subtitle_position)
    subtitle_position_offset = (
        video_frame_module.VideoFrame.subtitle_position_offset)
    subtitle_surface_reference = (
        video_frame_module.VideoFrame.subtitle_surface_reference)
    effective_subtitle_position = (
        video_frame_module.VideoFrame.effective_subtitle_position)
    subtitle_reserved_bottom = (
        video_frame_module.VideoFrame.subtitle_reserved_bottom)
    invalidate_subtitle_band = (
        video_frame_module.VideoFrame.invalidate_subtitle_band)
    _set_subtitle_band_collapsed = (
        video_frame_module.VideoFrame._set_subtitle_band_collapsed)
    fade_overlay_in = video_frame_module.VideoFrame.fade_overlay_in
    fade_overlay_out = video_frame_module.VideoFrame.fade_overlay_out
    _finish_overlay_fade_out = (
        video_frame_module.VideoFrame._finish_overlay_fade_out)
    hide_overlay_for_inactivity = (
        video_frame_module.VideoFrame.hide_overlay_for_inactivity)
    hide_overlay_immediately = (
        video_frame_module.VideoFrame.hide_overlay_immediately)
    set_overlay_suppressed = (
        video_frame_module.VideoFrame.set_overlay_suppressed)
    _on_overlay_fade_finished = (
        video_frame_module.VideoFrame._on_overlay_fade_finished)
    _overlay_band_hidden = video_frame_module.VideoFrame._overlay_band_hidden
    _overlay_auto_hide_pending = (
        video_frame_module.VideoFrame._overlay_auto_hide_pending)
    _overlay_band_applied = (
        video_frame_module.VideoFrame._overlay_band_applied)

    # Ürünle AYNI başlangıç durumu (sınıf düzeyinde varsayılan).
    _subtitle_band_state = video_frame_module.VideoFrame._subtitle_band_state

    def __init__(self, height, overlay_height=OVERLAY_HEIGHT, mpv=None,
                 dpr=1.0):
        self._height = height
        self._dpr = float(dpr)
        # Katman, fade ve MPV yazımları TEK sıralı kayda düşer; böylece
        # "önce yukarı al, sonra göster" sırası ölçülebilir.
        self.log = mpv.log if mpv is not None else []
        self.control_overlay = (FakeOverlay(overlay_height, self.log)
                                if overlay_height is not None else None)
        self.overlay_fade = FakeFade(self.log)
        self._overlay_fade_target = 1.0
        self._overlay_suppressed = False
        self._overlay_auto_hidden = False
        self.overlay_subtitles_active = None
        self.overlay_hide_timer = None
        # Auto-hide KAPISI bu dosyanın konusu değildir; ayrı ölçülür.
        self._overlay_playback_active = lambda: True
        self._overlay_interaction_blocked = lambda: False

        class Window:
            pass

        class Settings:
            """Kullanıcının KAYITLI tercihi (MPV'deki efektif değil)."""

            def __init__(self, stored):
                self.stored = stored
                self.writes = []

            def value(self, key, default=None):
                return self.stored.get(key, default)

            def setValue(self, key, value):
                self.writes.append((key, value))
                self.stored[key] = value

        self.main_window = Window()
        self.main_window.mpv_player = mpv
        self.main_window.settings = Settings({"subtitle/sub_pos": 100.0})

    def height(self):
        return self._height

    def _device_ratio(self):
        return getattr(self, "_dpr", 1.0)


# --- Bant hesabı -------------------------------------------------------

def test_the_reserved_band_is_the_single_source_of_truth():
    """Ölçü `_osd_reserved_bottom()`tan gelir; ikinci kopya YOK."""
    frame = Frame(772)

    # OSD bandi DEGISMEDI; ALTYAZI bandi gorunmez tiklama payi kadar
    # kucuktur (bkz. `overlay_timeline_top_padding()`).
    assert frame._osd_reserved_bottom() == OVERLAY_HEIGHT
    assert frame.subtitle_reserved_bottom() == SUBTITLE_RESERVED
    assert SUBTITLE_RESERVED < OVERLAY_HEIGHT
    assert SUBTITLE_BAND_GAP == 12


def test_the_margin_matches_the_measured_real_video_value():
    """1400×772 yüzey, letterbox yokken referans = yüzey yüksekliği.

    Beklenen değer 114 → 93: bant artık timeline'ın GÖRÜNMEZ tıklama
    payını saymıyor (bkz. `overlay_timeline_top_padding()`).
    """
    frame = Frame(772)
    expected = round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 772)

    assert frame.subtitle_safe_margin() == expected == 93
    assert frame.subtitle_safe_margin(772) == expected


@pytest.mark.parametrize("height", [772, 600, 1080, 1440, 2160])
def test_the_margin_scales_with_the_surface_height(height):
    """`sub-scale-by-window` referansı 720 px'dir; marj oranlıdır."""
    frame = Frame(height)

    # OSD bandı `OVERLAY_HEIGHT`tır; ALTYAZI bandı görünmez tıklama
    # payını saymaz, bu yüzden `SUBTITLE_RESERVED` kullanılır.
    expected = round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP)
                     * MPV_MARGIN_REFERENCE_HEIGHT / height)

    assert frame.subtitle_safe_margin() == expected


def test_a_clamped_overlay_uses_the_real_reserved_height():
    """Kısa pencerede katman clamp olur; hesap GERÇEK banttan yapılır.

    Tek bir sihirli çözünürlük sabitine güvenilmez.
    """
    frame = Frame(140, overlay_height=140)

    # Ayrılmış bant = min(katman yüksekliği, video yüksekliği) = 140.
    assert frame._osd_reserved_bottom() == 140
    # Ham hesap 782 çıkar (bant videonun tamamına yakın); güvenlik üst
    # sınırı devreye girer, yoksa marj yüzeyi tamamen yutardı.
    raw = round((140 + SUBTITLE_BAND_GAP) * MPV_MARGIN_REFERENCE_HEIGHT / 140)
    assert raw == 782
    assert frame.subtitle_safe_margin() == MPV_MARGIN_REFERENCE_HEIGHT // 2


def test_the_margin_never_swallows_the_whole_surface():
    frame = Frame(60, overlay_height=60)

    assert frame.subtitle_safe_margin() <= MPV_MARGIN_REFERENCE_HEIGHT // 2


def test_no_overlay_means_no_reserved_band():
    frame = Frame(772, overlay_height=None)

    assert frame._osd_reserved_bottom() == 0
    assert frame.subtitle_safe_margin() == round(
        SUBTITLE_BAND_GAP * MPV_MARGIN_REFERENCE_HEIGHT / 772)


# --- MPV'ye yazma ------------------------------------------------------

def test_the_band_is_written_to_mpv_with_the_margin_contract():
    # Referans YUZEY yuksekligidir (772); letterbox payi marji
    # ETKILEMEZ (olculdu: egim osd h'den bagimsiz).
    mpv = FakeMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = Frame(772, mpv=mpv)

    applied = frame.sync_subtitle_safe_band()

    assert applied == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 772) == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 772)
    assert mpv.written["sub_margin_y"] == applied
    assert mpv.written["sub_use_margins"] is True
    # ASS altyazıda da marjın geçerli olması için ZORUNLU.
    assert mpv.written["sub_ass_force_margins"] is True


def test_the_scale_reference_is_the_surface_height_not_the_video_area():
    """DÖNÜŞTÜRÜLDÜ (16 Ağustos 2026) — gevşetilmedi, DÜZELTİLDİ.

    Bu test eskiden referansın RENDER ALANI (`h - mt - mb` = 454) olmasını
    şart koşuyordu. Ölçüm bunun yanlış olduğunu gösterdi:

    1) Aynı pencerede letterbox değiştirildi, marj eğimi SABİT kaldı —
       `osd h=1360 → 2,881 px/birim`, `osd h=639 → 2,881 px/birim`
       (mpv 0.36 ve 0.41'de aynı). Eğim alana bağlı olsaydı değişirdi.
    2) Model gerçek kabul ölçümüyle birebir tutuyor:
       `alt_kenar = yüzey - marj × (yüzey/720) × sub_scale`.
       `single_line`: 772 - 116×(772/720) = 647,6; ÖLÇÜLEN 647.

    Eski referans yalnız letterbox payı küçükken (`mt=mb=8`/`28`) doğru
    sonuç veriyordu; playlist açıkken pay 159 olunca marj 193'e şişip
    altyazıyı 105 px yukarı atıyordu (beklenen 10-28).
    """
    mpv = FakeMpv(osd={"w": 840, "h": 772, "mt": 159, "mb": 159})
    frame = Frame(772, mpv=mpv)

    assert frame.subtitle_scale_reference() == 772
    applied = frame.sync_subtitle_safe_band()
    assert applied == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 772) == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 772)


def test_the_scale_reference_falls_back_to_the_widget_height():
    """`osd-dimensions` okunamazsa sihirli sabit uydurulmaz."""
    frame = Frame(772, mpv=FakeMpv(osd=None))

    assert frame.subtitle_scale_reference() == 772

    broken = Frame(772, mpv=FakeMpv(osd={"h": 0, "mt": 0, "mb": 0}))
    assert broken.subtitle_scale_reference() == 772


def test_the_stored_preference_is_never_written_by_the_band():
    """Kullanıcının KAYITLI tercihi bu yoldan DEĞİŞMEZ.

    ESKİ AD: `test_sub_pos_is_never_touched_by_the_band`. O sözleşme
    "MPV'ye `sub_pos` HİÇ yazılmaz" diyordu; ASS'te `sub-margin-y`
    etkisiz olduğu ölçüldüğü için ürün artık ASS'te MPV'ye EFEKTİF bir
    `sub_pos` yazar. Korunan garanti aynıdır ve daha sıkı ölçülür:
    QSettings'teki kullanıcı değeri değişmez.
    """
    mpv = FakeMpv(codec="subrip")
    frame = Frame(772, mpv=mpv)

    frame.sync_subtitle_safe_band()

    assert frame.main_window.settings.writes == []
    assert frame.main_window.settings.value("subtitle/sub_pos") == 100.0
    # SRT: efektif değer kullanıcı değeriyle AYNIDIR (çift kaydırma yok).
    assert mpv.written["sub_pos"] == 100.0


def test_a_missing_player_is_safe():
    frame = Frame(772, mpv=None)

    assert frame.sync_subtitle_safe_band() is None


def test_an_mpv_failure_does_not_raise(capsys):
    frame = Frame(772, mpv=FakeMpv(fail=True))

    assert frame.sync_subtitle_safe_band() is None
    combined = capsys.readouterr()
    assert "Traceback" not in combined.out + combined.err


def test_the_band_follows_the_band_state_not_raw_visibility():
    """YENİ KULLANICI KARARI — eski sözleşmenin yerine geçer.

    Eskiden bant görünürlükten TAMAMEN bağımsızdı. Artık timeline auto-hide
    ile tamamen gizlendiğinde altyazı aşağı iner. Karar ham `isVisible()`e
    DEĞİL, fade ve suppression'ı ayıran açık bant durumuna bağlıdır:
    `_osd_reserved_bottom()` hâlâ "gerçek katman yüksekliği" için TEK
    kaynaktır ve değişmez; ayrılan bant `subtitle_reserved_bottom()`
    üzerinden türetilir.
    """
    osd = {"w": 1400, "h": 772, "mt": 8, "mb": 8}
    up = Frame(772, mpv=FakeMpv(osd=osd))
    down = Frame(772, mpv=FakeMpv(osd=dict(osd)))
    down._overlay_band_hidden = True

    assert up._osd_reserved_bottom() == down._osd_reserved_bottom()
    assert up.subtitle_reserved_bottom() == SUBTITLE_RESERVED
    assert down.subtitle_reserved_bottom() == 0
    assert down.sync_subtitle_safe_band() < up.sync_subtitle_safe_band()


# --- Dinamik bant: timeline auto-hide / show döngüsü -------------------

def dynamic_frame(codec="subrip"):
    osd = {"w": 1400, "h": 772, "mt": 8, "mb": 8}
    return Frame(772, mpv=FakeMpv(osd=osd, codec=codec))


def margin_of(frame):
    return frame.main_window.mpv_player.written["sub_margin_y"]


def test_the_subtitle_stays_up_while_the_fade_out_is_still_running():
    """(a) Fade sürerken erken aşağı inip panelle kesişmemeli."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    before = margin_of(frame)

    frame.hide_overlay_for_inactivity()

    assert frame.overlay_fade.started == 1, "fade başlamadı"
    assert frame._overlay_band_hidden is False
    assert margin_of(frame) == before


def test_the_subtitle_moves_down_only_after_the_fade_completed():
    """(b) Animasyon TAMAMEN bittikten sonra aşağı iner."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    before = margin_of(frame)

    frame.hide_overlay_for_inactivity()
    frame._finish_overlay_fade_out()

    assert frame._overlay_band_hidden is True
    assert margin_of(frame) < before


def test_the_subtitle_is_raised_before_the_overlay_is_shown_again():
    """(c) Tek karelik kesişme yok: marj yazımı `show()`/fade'den ÖNCE."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    frame.hide_overlay_for_inactivity()
    frame._finish_overlay_fade_out()
    down = margin_of(frame)
    frame.log.clear()

    frame.fade_overlay_in()

    assert frame._overlay_band_hidden is False
    assert margin_of(frame) > down
    steps = list(frame.log)
    assert "mpv.sub_margin_y" in steps, steps
    appear = [index for index, step in enumerate(steps)
              if step in ("overlay.show", "fade.start")]
    assert appear, f"katman hiç gösterilmedi: {steps}"
    assert steps.index("mpv.sub_margin_y") < appear[0], steps


def test_every_cycle_moves_the_band_again():
    """(d) Davranış TEK SEFERLİK değil; iki tam döngü de doğru."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    up = margin_of(frame)
    seen = []

    for _ in range(2):
        frame.hide_overlay_for_inactivity()
        frame._finish_overlay_fade_out()
        seen.append(("down", margin_of(frame)))
        frame.fade_overlay_in()
        seen.append(("up", margin_of(frame)))

    assert [state for state, _v in seen] == ["down", "up", "down", "up"]
    assert seen[0][1] == seen[2][1] < up
    assert seen[1][1] == seen[3][1] == up


def test_the_ass_effective_position_moves_with_the_band():
    """(f) ASS yolunda efektif `sub_pos` değişir."""
    frame = dynamic_frame(codec="ass")
    frame.sync_subtitle_safe_band()
    up_position = frame.main_window.mpv_player.written["sub_pos"]

    frame.hide_overlay_for_inactivity()
    frame._finish_overlay_fade_out()
    down_position = frame.main_window.mpv_player.written["sub_pos"]

    assert up_position < down_position <= 100.0
    assert frame.effective_subtitle_position() == down_position


def test_the_stored_preference_is_never_written():
    """(g) Kayıtlı %90 tercihi DEĞİŞMEZ."""
    frame = dynamic_frame(codec="ass")
    frame.main_window.settings.stored["subtitle/sub_pos"] = 90.0
    frame.sync_subtitle_safe_band()

    frame.hide_overlay_for_inactivity()
    frame._finish_overlay_fade_out()
    frame.fade_overlay_in()

    assert frame.main_window.settings.writes == []
    assert frame.main_window.settings.stored["subtitle/sub_pos"] == 90.0


def test_the_gap_survives_so_the_subtitle_never_touches_the_bottom():
    """(5) Ayrılan yükseklik 0 olur ama SUBTITLE_BAND_GAP korunur."""
    frame = dynamic_frame()
    frame.hide_overlay_for_inactivity()
    frame._finish_overlay_fade_out()

    assert frame.subtitle_reserved_bottom() == 0
    assert margin_of(frame) > 0


def test_repeating_the_same_state_writes_nothing_extra():
    """(h) Aynı durumda 50 tekrar = 0 ek MPV yazımı."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    frame.hide_overlay_for_inactivity()
    frame._finish_overlay_fade_out()
    baseline = frame.main_window.mpv_player.write_count

    for _ in range(50):
        frame._finish_overlay_fade_out()
        frame._set_subtitle_band_collapsed(True)
        frame.sync_subtitle_safe_band()

    assert frame.main_window.mpv_player.write_count == baseline


@pytest.mark.parametrize("trigger", ("suppress", "immediate"))
def test_a_queued_fade_finish_after_an_immediate_hide_keeps_the_band_up(
        trigger):
    """(i) GERÇEK yarış: auto-hide fade'i BAŞLADI, sonra bastırma geldi.

    Önceki sürüm bu yarışı üretmiyordu: auto-hide hiç başlatmadan doğrudan
    `_finish_overlay_fade_out()` çağırıyordu. Gerçek sıra şudur —
    `hide_overlay_for_inactivity()` fade'i başlatır, araya
    `set_overlay_suppressed(True)` / minimize-deactivate yolundaki
    `hide_overlay_immediately()` girer ve KUYRUKTAKİ fade-finished
    geri çağrısı sonradan çalışır. Bant çökmemeli.
    """
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    before = margin_of(frame)

    frame.hide_overlay_for_inactivity()          # auto-hide fade'i BAŞLADI
    assert frame.overlay_fade.started == 1

    if trigger == "suppress":
        frame.set_overlay_suppressed(True)
    else:
        frame.hide_overlay_immediately()

    frame._on_overlay_fade_finished()            # geç gelen ESKİ callback

    assert frame._overlay_band_hidden is False
    assert margin_of(frame) == before


def test_an_immediate_hide_does_not_undo_a_completed_auto_hide():
    """Tamamlanmış auto-hide durumu bozulmamalı.

    Aksi halde minimize/odak kaybından sonra aktivasyonda timeline
    kendiliğinden geri gelirdi (`_restore_overlay_if_owner_visible`
    `_overlay_auto_hidden` bayrağına bakar).
    """
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    frame.hide_overlay_for_inactivity()
    frame._on_overlay_fade_finished()            # auto-hide GERÇEKTEN bitti
    down = margin_of(frame)
    assert frame._overlay_band_hidden is True

    frame.hide_overlay_immediately()             # minimize / odak kaybı

    assert frame._overlay_auto_hidden is True
    assert frame._overlay_band_hidden is True
    assert margin_of(frame) == down


def test_a_reshow_cancels_a_pending_auto_hide_completion():
    """Fade sürerken kullanıcı fareyi oynattı: geç callback çökertmemeli."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    up = margin_of(frame)

    frame.hide_overlay_for_inactivity()
    frame.fade_overlay_in()                      # kullanıcı geri getirdi
    frame._on_overlay_fade_finished()            # eski fade-out callback'i

    assert frame._overlay_band_hidden is False
    assert margin_of(frame) == up


# --- Başarısız yazım: durum ile UYGULANMIŞ durum ayrıdır ---------------

def test_a_failed_band_write_is_not_treated_as_applied():
    """Başarısız geçiş cachelenmemeli; MPV düzelince YENİDEN denenmeli."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    mpv = frame.main_window.mpv_player
    up = margin_of(frame)

    mpv._fail = True
    frame.hide_overlay_for_inactivity()
    frame._on_overlay_fade_finished()            # yazım BAŞARISIZ
    assert margin_of(frame) == up, "başarısız yazım MPV'ye uygulanmış sayıldı"

    mpv._fail = False
    changed = frame._set_subtitle_band_collapsed(True)   # AYNI hedef durum

    assert changed is True, "başarısız durum 'zaten uygulandı' sayıldı"
    assert margin_of(frame) < up


def test_a_successful_state_still_writes_nothing_extra_afterwards():
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    mpv = frame.main_window.mpv_player
    frame.hide_overlay_for_inactivity()
    frame._on_overlay_fade_finished()
    baseline = mpv.write_count

    for _ in range(50):
        frame._set_subtitle_band_collapsed(True)

    assert mpv.write_count == baseline


# --- Belge ile davranış çelişmemeli ------------------------------------

def test_the_margin_docstring_describes_the_new_decision():
    text = video_frame_module.VideoFrame.subtitle_safe_margin.__doc__ or ""

    assert "zıplamaz" not in text, "eski (geçersiz) sözleşme hâlâ yazılı"
    assert "auto-hide" in text
    assert "subtitle_reserved_bottom" in text


def test_a_late_callback_after_shutdown_is_a_safe_no_op():
    """(j) Kapanışta mpv bırakıldıysa geç callback ham hata üretmez."""
    frame = dynamic_frame()
    frame.sync_subtitle_safe_band()
    frame.hide_overlay_for_inactivity()    # GERÇEK auto-hide sırası
    frame.main_window.mpv_player = None    # kapanış: mpv bırakıldı

    frame._on_overlay_fade_finished()      # ham hata ÇIKMAMALI

    assert frame._overlay_band_hidden is True
    # Yazım yapılamadı: UYGULANMIŞ sayılmaz.
    assert frame._overlay_band_applied is None


# --- `sub_pos` sözleşmesi korunur --------------------------------------

def test_the_position_range_and_default_are_unchanged():
    from app.config import SUBTITLE_DEFAULTS
    from app.subtitle_style import NUMERIC_RANGES, normalise_subtitle_numeric

    assert NUMERIC_RANGES["sub_pos"] == (0.0, 100.0)
    assert float(SUBTITLE_DEFAULTS["sub_pos"]) == 100.0
    assert normalise_subtitle_numeric("sub_pos", 90) == 90.0
    assert normalise_subtitle_numeric("sub_pos", 150) == 100.0


def test_a_stored_ninety_percent_is_restored_untouched(tmp_path):
    """Kullanıcının kayıtlı `%90` tercihi SESSİZCE değiştirilmez."""
    from types import SimpleNamespace

    from PyQt6.QtCore import QSettings

    from app.player import MPVPlayer

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    settings.setValue("subtitle/sub_pos", 90.0)
    mpv = SimpleNamespace()
    frame = SimpleNamespace(sync_subtitle_safe_band=lambda: 114)
    player = SimpleNamespace(settings=settings, mpv_player=mpv,
                             video_frame=frame)

    MPVPlayer.restore_subtitle_settings(player)

    assert mpv.sub_pos == pytest.approx(90.0)
    assert float(settings.value("subtitle/sub_pos")) == pytest.approx(90.0)


def test_restore_applies_the_safe_band_once(tmp_path):
    from types import SimpleNamespace

    from PyQt6.QtCore import QSettings

    from app.player import MPVPlayer

    calls = []
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    player = SimpleNamespace(
        settings=settings, mpv_player=SimpleNamespace(),
        video_frame=SimpleNamespace(
            sync_subtitle_safe_band=lambda: calls.append(1) or 114))

    MPVPlayer.restore_subtitle_settings(player)

    assert calls == [1]


def test_restore_survives_a_failing_band(tmp_path):
    from types import SimpleNamespace

    from PyQt6.QtCore import QSettings

    from app.player import MPVPlayer

    def boom():
        raise RuntimeError("sentetik")

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    player = SimpleNamespace(
        settings=settings, mpv_player=SimpleNamespace(),
        video_frame=SimpleNamespace(sync_subtitle_safe_band=boom))

    MPVPlayer.restore_subtitle_settings(player)   # istisna TAŞMAZ


# --- Ayarlar penceresi yönü DEĞİŞMEDİ ----------------------------------

def test_the_position_slider_direction_is_unchanged(tmp_path):
    """Büyük değer AŞAĞI; önizleme yönü gerçek MPV ile aynı kalır."""
    from PyQt6.QtCore import QSettings

    from app.subtitle_appearance_dialog import SubtitleAppearanceDialog

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    dialog = SubtitleAppearanceDialog()
    try:
        dialog.show()
        app.processEvents()
        dialog.position_slider.setValue(20)
        app.processEvents()
        high = dialog.preview.text_rect().center().y()
        dialog.position_slider.setValue(95)
        app.processEvents()
        low = dialog.preview.text_rect().center().y()

        assert low > high, (high, low)
        assert dialog.position_slider.minimum() == 0
        assert dialog.position_slider.maximum() == 100
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_reset_returns_to_one_hundred(tmp_path):
    from PyQt6.QtCore import QSettings

    from app.subtitle_appearance_dialog import SubtitleAppearanceDialog

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    dialog = SubtitleAppearanceDialog(values={"sub_pos": 60.0})
    try:
        assert dialog.current_values()["sub_pos"] == pytest.approx(60.0)
        dialog.reset_to_defaults()

        assert dialog.current_values()["sub_pos"] == pytest.approx(100.0)
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


# --- Tekrarlanan libmpv yazımları --------------------------------------
#
# `update_overlay_geometry()` overlay üzerindeki FARE HAREKETLERİNDE de
# çağrılır. Ölçülen kusur: geometri hiç değişmese bile her senkron üç
# libmpv özelliğini yeniden yazıyordu — 100 çağrı = 300 yazım. Oynatma
# sırasında gereksiz ctypes/libmpv trafiği ve takılma riski.

def band_frame(height=772, osd=None, mpv=None):
    osd = osd if osd is not None else {"w": 1400, "h": height, "mt": 8,
                                       "mb": 8}
    return Frame(height, mpv=mpv or FakeMpv(osd=osd))


class CountingMpv(FakeMpv):
    """Her property YAZIMINI sayar."""

    def __init__(self, fail=False, osd=None, codec="subrip", sid=1):
        object.__setattr__(self, "writes", [])
        super().__init__(fail=fail, osd=osd, codec=codec, sid=sid)

    def __setattr__(self, name, value):
        # NOT: `order`/`log` taban sahtenin KENDİ defteridir, MPV property
        # yazımı değildir; sayıma girmemeli.
        if name not in ("written", "_fail", "osd_dimensions", "writes",
                        "sid", "track_list", "order", "log"):
            object.__getattribute__(self, "writes").append((name, value))
        super().__setattr__(name, value)


def test_the_first_sync_writes_the_whole_contract():
    # NOT: sözleşmeye `sub_pos` EKLENDİ (ASS'te marj etkisiz olduğu için
    # efektif konum MPV'ye yazılır); yazım sayısı 3 → 4.
    mpv = CountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=mpv)

    frame.sync_subtitle_safe_band()

    assert [name for name, _ in mpv.writes] == [
        "sub_use_margins", "sub_ass_force_margins", "sub_margin_y",
        "sub_pos"]


def test_repeated_syncs_with_the_same_geometry_write_nothing():
    """100 aynı senkron → İLK üç yazımdan sonra SIFIR ek yazım."""
    mpv = CountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=mpv)

    first = frame.sync_subtitle_safe_band()
    after_first = len(mpv.writes)
    for _ in range(99):
        assert frame.sync_subtitle_safe_band() == first

    assert after_first == 4
    assert len(mpv.writes) == 4, mpv.writes


def test_a_changed_margin_writes_only_the_margin():
    mpv = CountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=mpv)
    frame.sync_subtitle_safe_band()
    mpv.writes.clear()

    # DONUSTURULDU: eskiden "playlist acilinca (letterbox) marj
    # degismeli" deniyordu. Olcum bunun YANLIS oldugunu gosterdi;
    # marj yalniz YUZEY yuksekligine baglidir. Gercek marj degisimi
    # yuzey yuksekligi degistiginde olur (tam ekran gibi).
    mpv.osd_dimensions = {"w": 1400, "h": 1440, "mt": 28, "mb": 28}
    applied = frame.sync_subtitle_safe_band()

    assert [name for name, _ in mpv.writes] == ["sub_margin_y"]
    assert applied == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 1440)


def test_a_real_margin_change_is_never_missed():
    """Önbellek gerçek değişimi YUTMAZ."""
    mpv = CountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=mpv)
    seen = [frame.sync_subtitle_safe_band()]

    # DONUSTURULDU: supurulen buyukluk artik RENDER ALANI degil YUZEY
    # yuksekligidir; marj yalniz ona baglidir.
    for surface in (454, 1384, 756, 300):
        mpv.osd_dimensions = {"w": 1400, "h": surface, "mt": 8, "mb": 8}
        seen.append(frame.sync_subtitle_safe_band())

    assert seen[1:] == [round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / surface)
                        for surface in (454, 1384, 756, 300)]
    assert mpv.written["sub_margin_y"] == seen[-1]


def test_a_new_mpv_object_gets_the_whole_contract_again():
    """MPV oturumu yenilenirse önbellek eski nesneye ait sayılmaz."""
    first = CountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=first)
    frame.sync_subtitle_safe_band()

    second = CountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame.main_window.mpv_player = second
    frame.sync_subtitle_safe_band()

    assert [name for name, _ in second.writes] == [
        "sub_use_margins", "sub_ass_force_margins", "sub_margin_y",
        "sub_pos"]


def test_a_failed_write_is_not_cached():
    """Yazım başarısızsa durum ÖNBELLEKLENMEZ; sonraki çağrı dener."""
    mpv = CountingMpv(fail=True, osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=mpv)

    assert frame.sync_subtitle_safe_band() is None
    assert frame.sync_subtitle_safe_band() is None
    # Her denemede GERÇEKTEN yeniden denendi (sessizce vazgeçilmedi).
    assert len(mpv.writes) >= 2

    working = CountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame.main_window.mpv_player = working

    assert frame.sync_subtitle_safe_band() == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 772)
    assert [name for name, _ in working.writes] == [
        "sub_use_margins", "sub_ass_force_margins", "sub_margin_y",
        "sub_pos"]


def test_the_band_is_converted_to_device_pixels_at_high_dpi():
    """%150 DPI: bant MANTIKSAL, `osd-dimensions` CİHAZ pikselindedir.

    Ölçülen kusur: birim karıştırıldığında marj 1,5 kat küçük çıkıyor ve
    altyazı kontrol bandına 19 px giriyordu (gerçek video, dpr=1.5).
    """
    osd = {"w": 2100, "h": 1158, "mt": 8, "mb": 8}
    normal = Frame(772, mpv=FakeMpv(osd=dict(osd)), dpr=1.0)
    high = Frame(772, mpv=FakeMpv(osd=dict(osd)), dpr=1.5)

    # Referans YÜZEY yüksekliğidir; letterbox payı çıkarılmaz.
    assert high.subtitle_scale_reference() == 1158
    assert normal.sync_subtitle_safe_band() == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 1158)
    assert high.sync_subtitle_safe_band() == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 1.5 * 720 / 1158)
    # %150'de marj tam 1,5 kat büyük olmalı.
    assert high.sync_subtitle_safe_band() > normal.sync_subtitle_safe_band()


def test_dpr_one_keeps_the_measured_values_unchanged():
    """dpr=1.0 ölçümleri: referans artık YÜZEY (772), alan (756) değil."""
    frame = Frame(772, mpv=FakeMpv(osd={"w": 1400, "h": 772, "mt": 8,
                                        "mb": 8}), dpr=1.0)

    assert frame.sync_subtitle_safe_band() == round((SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 720 / 772)


# --- ASS: `sub-margin-y` etkisiz, `sub-pos` etkili ---------------------
#
# Gerçek video ölçümü: ASS altyazıda marj 116 → 300 yapıldığında hareket
# 0 px; buna karşılık `sub_pos` 100 → 80 arasında ~149 px yukarı hareket
# var. Bu yüzden ASS'te güvenli bant EFEKTİF `sub_pos` ile sağlanır.
# Kullanıcının KAYITLI tercihi değişmez.

def ass_frame(height=772, osd=None, stored_pos=100.0, dpr=1.0,
              codec="ass"):
    osd = osd if osd is not None else {"w": 1400, "h": height, "mt": 8,
                                       "mb": 8}
    frame = Frame(height, mpv=CountingMpv(osd=osd), dpr=dpr)
    frame.main_window.mpv_player.track_list = [
        {"type": "sub", "id": 1, "codec": codec}]
    frame.main_window.settings.stored["subtitle/sub_pos"] = stored_pos
    return frame


def test_an_ass_track_is_detected_from_the_selected_track():
    assert ass_frame(codec="ass").subtitle_uses_ass_positioning() is True
    assert ass_frame(codec="ssa").subtitle_uses_ass_positioning() is True
    assert ass_frame(codec="subrip").subtitle_uses_ass_positioning() is False
    assert ass_frame(codec="").subtitle_uses_ass_positioning() is False


def test_the_effective_position_moves_ass_up_by_the_band():
    """ASS: efektif konum = kullanıcı değeri - bant yüzdesi."""
    frame = ass_frame()

    offset = frame.subtitle_position_offset()
    # ASS yüzdesi PENCERE yüksekliğine (772) oranlanır (ölçüldü:
    # 7,43 px/puan). Bant artık görünmez tıklama payını saymaz.
    assert round(offset, 1) == round(
        (SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 100 / 772, 1)
    assert frame.effective_subtitle_position() == round(100.0 - offset, 2)
    assert frame.effective_subtitle_position() < 100.0


def test_srt_keeps_the_user_position_exactly():
    """SRT `sub-margin-y` yolunu kullanır; İKİ KEZ yukarı taşınmaz."""
    frame = ass_frame(codec="subrip")

    assert frame.subtitle_uses_ass_positioning() is False
    assert frame.effective_subtitle_position() == 100.0
    frame.sync_subtitle_safe_band()
    assert frame.main_window.mpv_player.written["sub_pos"] == 100.0


def test_the_user_ninety_preference_gets_the_offset_on_top():
    """`%90` tercihi korunur; düzeltme onun ÜZERİNE uygulanır."""
    frame = ass_frame(stored_pos=90.0)

    effective = frame.effective_subtitle_position()

    assert effective < 90.0
    assert effective == round(90.0 - frame.subtitle_position_offset(), 2)
    frame.sync_subtitle_safe_band()
    # KAYITLI değer değişmedi.
    assert frame.main_window.settings.writes == []
    assert frame.main_window.settings.value("subtitle/sub_pos") == 90.0


def test_the_effective_position_never_goes_negative():
    frame = ass_frame(height=200, stored_pos=0.0)

    assert frame.effective_subtitle_position() >= 0.0


def test_switching_from_ass_to_srt_restores_the_user_value():
    """ASS → SRT: kullanıcının GERÇEK değeri geri uygulanır."""
    frame = ass_frame(stored_pos=90.0, codec="ass")
    frame.sync_subtitle_safe_band()
    mpv = frame.main_window.mpv_player
    ass_value = mpv.written["sub_pos"]
    assert ass_value < 90.0

    mpv.track_list = [{"type": "sub", "id": 1, "codec": "subrip"}]
    mpv.writes.clear()
    frame.sync_subtitle_safe_band()

    assert mpv.written["sub_pos"] == 90.0
    assert [name for name, _ in mpv.writes] == ["sub_pos"]


def test_switching_from_srt_to_ass_applies_the_correction():
    frame = ass_frame(stored_pos=100.0, codec="subrip")
    frame.sync_subtitle_safe_band()
    mpv = frame.main_window.mpv_player
    assert mpv.written["sub_pos"] == 100.0

    mpv.track_list = [{"type": "sub", "id": 1, "codec": "ass"}]
    mpv.writes.clear()
    frame.sync_subtitle_safe_band()

    assert mpv.written["sub_pos"] < 100.0
    assert [name for name, _ in mpv.writes] == ["sub_pos"]


def test_repeated_syncs_with_an_ass_track_write_nothing_extra():
    """Önbellek altyazı türünü ve efektif konumu da içerir."""
    frame = ass_frame()
    frame.sync_subtitle_safe_band()
    mpv = frame.main_window.mpv_player
    assert len(mpv.writes) == 4

    for _ in range(99):
        frame.sync_subtitle_safe_band()

    assert len(mpv.writes) == 4, mpv.writes


def test_a_geometry_change_updates_both_margin_and_position():
    frame = ass_frame()
    frame.sync_subtitle_safe_band()
    mpv = frame.main_window.mpv_player
    mpv.writes.clear()

    # DÖNÜŞTÜRÜLDÜ: playlist yalnız letterbox payını değiştirir
    # (`mt/mb` 8 → 159), YÜZEY 772'de kalır. Ölçüm marjın letterbox'tan
    # BAĞIMSIZ olduğunu gösterdi, bu yüzden artık hiçbir şey yeniden
    # yazılmaz. Marjı gerçekten değiştiren şey yüzey yüksekliğidir.
    mpv.osd_dimensions = {"w": 840, "h": 772, "mt": 159, "mb": 159}
    frame.sync_subtitle_safe_band()

    assert [name for name, _ in mpv.writes] == []
    assert mpv.written["sub_pos"] == round(
        100.0 - (SUBTITLE_RESERVED + SUBTITLE_BAND_GAP) * 100 / 772, 2)


def test_a_failed_position_write_is_not_cached():
    frame = ass_frame()
    frame.main_window.mpv_player = CountingMpv(
        fail=True, osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})

    assert frame.sync_subtitle_safe_band() is None
    assert frame._subtitle_band_state is None


# --------------------------------------------------------------------------
# Boyutlandirma donmasi: senkron libmpv OKUMALARI
# --------------------------------------------------------------------------

class ReadCountingMpv(FakeMpv):
    """Her property OKUMASINI sayar (yazim degil).

    KULLANICI RAPORU (16 Agustos 2026): oynatma sirasinda pencere
    boyutlandirilinca video donuk donuk geciyor.

    OLCULEN KANIT (gercek pencere, gercek 4K video, ayni prob, arka arkaya):

        sync_subtitle_safe_band()   ortalama  medyan   p95     max
          mpv v0.36 (eski)           0,37 ms   0,35    0,42    1,24
          mpv v0.41 (yeni)           3,84 ms   0,41   41,70   84,55

    Medyan neredeyse ayni; p95 100 kat, en kotu durum 68 kat kotulesti.
    60 Hz'de 84 ms = BES kare. Sebep okumalarin kendisi DEGIL (bostayken
    ucu toplam 0,2 ms): boyutlandirma sirasinda yeni mpv swapchain'i
    yeniden kurarken core lock'u uzun tutuyor ve GUI thread'indeki senkron
    okuma o kilidi bekliyor.

    `SubtitleTrackWatcher` bu uc ozelligi (`sid`, `track-list`,
    `osd-dimensions`) ZATEN gozluyor ve degerler push ile geliyor. Sozlesme:
    gozlemci degeri biliyorsa senkron okuma YAPILMAZ.
    """

    def __init__(self, fail=False, osd=None, codec="subrip", sid=1):
        object.__setattr__(self, "reads", [])
        super().__init__(fail=fail, osd=osd, codec=codec, sid=sid)

    def __getattribute__(self, name):
        if name in ("osd_dimensions", "sid", "track_list"):
            object.__getattribute__(self, "reads").append(name)
        return object.__getattribute__(self, name)


def test_a_sync_reads_libmpv_when_no_observed_value_is_available():
    """Gozlemci yoksa DAVRANIS DEGISMEZ: senkron okuma mesrudur."""
    mpv = ReadCountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=mpv)

    frame.sync_subtitle_safe_band()

    assert mpv.reads, "gozlemci yokken senkron okuma beklenir"


def test_repeated_syncs_do_not_read_libmpv_when_the_watcher_knows():
    """Bir boyutlandirma firtinasinda TEK bir senkron okuma bile olmamali."""
    osd = {"w": 1400, "h": 772, "mt": 8, "mb": 8}
    mpv = ReadCountingMpv(osd=osd)
    frame = band_frame(mpv=mpv)
    frame.note_observed_property("osd-dimensions", osd)
    frame.note_observed_property("sid", 1)
    frame.note_observed_property("track-list",
                                 [{"type": "sub", "id": 1, "codec": "subrip"}])

    frame.sync_subtitle_safe_band()
    mpv.reads.clear()
    for _ in range(100):
        frame.sync_subtitle_safe_band()

    assert mpv.reads == [], (
        f"100 senkronda {len(mpv.reads)} senkron libmpv okumasi yapildi; "
        "boyutlandirma sirasinda bunlar core lock'u bekleyip GUI'yi donduruyor")


def test_the_observed_value_is_what_the_band_actually_uses():
    """Onbellek yalnız hizli degil, DOGRU olmali: yeni alan hemen etkili."""
    mpv = ReadCountingMpv(osd={"w": 1400, "h": 772, "mt": 8, "mb": 8})
    frame = band_frame(mpv=mpv)
    frame.note_observed_property("sid", 1)
    frame.note_observed_property("track-list",
                                 [{"type": "sub", "id": 1, "codec": "subrip"}])

    frame.note_observed_property("osd-dimensions",
                                 {"w": 1400, "h": 772, "mt": 8, "mb": 8})
    windowed = frame.sync_subtitle_safe_band()
    # Tam ekrana gecildi: YUZEY yuksekligi degisti. Gozlemci bunu bildirir.
    # (Letterbox payi degisimi marji ETKILEMEZ; olculdu.)
    frame.note_observed_property("osd-dimensions",
                                 {"w": 2560, "h": 1440, "mt": 28, "mb": 28})
    fullscreen = frame.sync_subtitle_safe_band()

    assert fullscreen != windowed, "gozlenen yeni yuzey banda YANSIMADI"


# --------------------------------------------------------------------------
# Bant GORUNMEZ tiklama alanini degil, CIZILEN kontrolleri temizler
# --------------------------------------------------------------------------

def test_the_band_clears_the_painted_groove_not_the_invisible_hit_area():
    """KULLANICI RAPORU: "guzel konumlandirma ama biraz daha asagiya".

    OLCULDU (gercek pencere, 1376x790): katman yuksekligi 110 px ve
    `overlay_timeline` katmanin EN USTUNDEN basliyor (y=0..47). Ama o 47
    px'in cogu TIKLAMA alanidir: `OVERLAY_TIMELINE_HIT_HEIGHT = 48`,
    gorunen groove ise 3 px ve ORTALANMIS. Yani cizilen cubugun ustunde
    ~22 px GORUNMEZ pay var ve altyazi onu da temizledigi icin gereksiz
    yukarida duruyordu (altyazi alti 672, gorunen cubuk 708 -> 36 px).

    Sozlesme: ayrilan bant gorunmez tiklama payini SAYMAZ. Kullanicinin
    gordugu kontrollerle cakisma yine imkansizdir; yalnizca bosa harcanan
    pay geri verilir.
    """
    frame = band_frame()

    reserved = frame.subtitle_reserved_bottom()
    osd_reserved = frame._osd_reserved_bottom()

    padding = video_frame_module.overlay_timeline_top_padding()
    assert padding > 0, "gorunmez tiklama payi sifir olamaz"
    # OSD bandi DEGISMEZ: `_osd_reserved_bottom()` OSD ile paylasilan olcudur.
    assert osd_reserved == OVERLAY_HEIGHT
    assert reserved == OVERLAY_HEIGHT - padding


def test_the_invisible_padding_comes_from_the_real_constants():
    """Pay elle uydurulmaz; tiklama alani ve groove yuksekliginden turer."""
    padding = video_frame_module.overlay_timeline_top_padding()

    expected = (video_frame_module.OVERLAY_TIMELINE_HIT_HEIGHT
                - video_frame_module.OVERLAY_TIMELINE_GROOVE_HEIGHT) // 2

    assert padding == expected


def test_a_collapsed_band_is_still_zero():
    """Katman TAMAMEN gizliyken bant 0 kalir; kullanici bunu onayladi."""
    frame = band_frame()
    frame._overlay_band_hidden = True

    assert frame.subtitle_reserved_bottom() == 0
