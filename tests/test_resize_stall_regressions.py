# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Pencere yeniden boyutlandırılırken GUI thread'inin libmpv'de bloklanması.

KULLANICI RAPORU (17 Ağustos 2026): video oynarken pencere kenarı
sürüklenince görüntü takılıyor.

GERÇEK ÖLÇÜM (gerçek pencere, gerçek 4K HEVC, 120 adımlık sürükleme;
`tests/resize_stall_measure_child.py`):

    düzeltmeden ÖNCE   sürükleme 1191,6 ms | bantta 345,6 ms = %29,0
                       476 senkron / 11 yazım
                       yazanlar: ort 30,2 ms | medyan 38,5 | max 54,8

    düzeltmeden SONRA  sürükleme 1106,7 ms | bantta 4,7 ms = %0,4
                       120 senkron / 0 yazım
                       hepsi önbellekte: ort 0,039 ms | max 0,071

    sürükleme sonrası:  beklenen marj 114 = uygulanan 114
                        = MPV geri okuması 114

Yazımların kendisi pahalı değildir; mpv boyutlandırma sırasında
swapchain'i kurarken core lock'u tutar ve `mpv_set_property` o kilidi
bekler. 16 Ağustos turu bu tehlikenin OKUMA yarısını kapatmıştı; onu
doğrulayan test "boyutlandırma fırtınası" adını taşımasına rağmen boyutu
HİÇ değiştirmediği için yazma yolu hiç çalışmıyordu.

Sözleşme: sürükleme sürerken libmpv'ye YAZILMAZ; yazım boyut durulunca
BİR KEZ yapılır ve değeri adım adım yazılanla AYNIDIR.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import video_frame as video_frame_module
from test_subtitle_safe_band_regressions import FakeMpv, Frame


class Scheduler:
    """`QTimer.singleShot` yerine geçen deterministik sıra.

    Gerçek timer kullanılmaz: test, olay döngüsü turlarını KENDİSİ
    ilerletir; böylece erteleme mantığı zamanlamaya bağlı olmadan ölçülür.
    """

    def __init__(self):
        self.queue = []
        self.turns = 0

    def singleShot(self, _ms, callback):
        self.queue.append(callback)

    def run_turn(self):
        """Bir olay döngüsü turu: o an sırada olanlar çalışır."""
        pending, self.queue = self.queue, []
        self.turns += 1
        for callback in pending:
            callback()
        return len(pending)

    def drain(self, limit=50):
        while self.queue and limit > 0:
            self.run_turn()
            limit -= 1


class ResizingFrame(Frame):
    """Bant harness'ine GENİŞLİK ve ertelenmiş yazım yolunu ekler."""

    _schedule_subtitle_band_sync = (
        video_frame_module.VideoFrame._schedule_subtitle_band_sync)
    _flush_subtitle_band = (
        video_frame_module.VideoFrame._flush_subtitle_band)
    flush_subtitle_band = (
        video_frame_module.VideoFrame.flush_subtitle_band)
    _band_sync_pending = video_frame_module.VideoFrame._band_sync_pending
    _band_sync_size = video_frame_module.VideoFrame._band_sync_size

    def __init__(self, height, **kwargs):
        super().__init__(height, **kwargs)
        self._width = 1400

    def width(self):
        return self._width

    def set_height(self, value):
        """Gerçek bir resize adımı: boyut değişir, gözlenen yüzey de."""
        self._height = value
        self.note_observed_property(
            "osd-dimensions", {"h": value, "w": self._width, "mt": 0, "mb": 0})


@pytest.fixture
def scheduler(monkeypatch):
    fake = Scheduler()
    monkeypatch.setattr(video_frame_module.QTimer, "singleShot",
                        fake.singleShot)
    return fake


def _ready_frame(height=772):
    mpv = FakeMpv(osd={"h": height, "w": 1400, "mt": 0, "mb": 0})
    frame = ResizingFrame(height, mpv=mpv)
    frame.set_height(height)
    # İlk senkron sözleşmenin tamamını yazar; ölçüm ondan SONRA başlar.
    frame.sync_subtitle_safe_band()
    mpv.order.clear()
    return frame, mpv


def _burst(frame, scheduler, heights, turn_every=8):
    """Gerçek sürükleme: olaylar döngü boşalmadan YIĞILIR.

    Windows'un modal resize döngüsünde boyut olayları, ertelenen işin
    çalışmasından daha hızlı gelir. `turn_every` kadar adımda bir olay
    döngüsüne tur attırmak bu davranışı taklit eder. Her adımı tek
    başına durulmuş saymak GERÇEKÇİ DEĞİLDİR — öyle bir durumda yazmak
    zaten doğru davranıştır.
    """
    for index, height in enumerate(heights, start=1):
        frame.set_height(height)
        frame._schedule_subtitle_band_sync()
        if index % turn_every == 0:
            scheduler.run_turn()


def test_a_resize_drag_does_not_write_to_libmpv_while_it_is_still_moving(
        scheduler):
    """Sürükleme sürerken TEK bir libmpv yazımı bile olmamalı."""
    frame, mpv = _ready_frame()

    _burst(frame, scheduler, range(772, 652, -1))

    assert mpv.order == [], (
        f"surukleme surerken {len(mpv.order)} libmpv yazimi yapildi; "
        "bunlar mpv core lock'unda bekleyip GUI'yi donduruyor")


def test_the_write_happens_once_the_size_settles(scheduler):
    """Boyut durulunca yazım YAPILIR; bant bayat kalmaz."""
    frame, mpv = _ready_frame()

    _burst(frame, scheduler, range(772, 652, -1))
    assert mpv.order == [], "surukleme sirasinda yazim beklenmiyordu"

    # Sürükleme durdu: boyut artık değişmiyor, sıradaki tur yazmalı.
    scheduler.drain()

    assert mpv.order != [], "boyut durulmasina ragmen bant HIC yazilmadi"


def test_the_settled_value_matches_a_direct_write(scheduler):
    """Geciktirme DAVRANIŞI değiştirmemeli: son değer adım adımla aynı."""
    frame, stepwise = _ready_frame()
    _burst(frame, scheduler, range(772, 652, -1))
    scheduler.drain()

    # Aynı son boyuta DOĞRUDAN giden ikinci bir yüzey.
    direct = FakeMpv(osd={"h": 653, "w": 1400, "mt": 0, "mb": 0})
    other = ResizingFrame(653, mpv=direct)
    other.set_height(653)
    other.sync_subtitle_safe_band()

    assert stepwise.written["sub_margin_y"] == direct.written["sub_margin_y"]
    assert stepwise.written["sub_pos"] == direct.written["sub_pos"]


def test_a_pending_sync_is_not_scheduled_twice(scheduler):
    """Sıraya YALNIZ bir iş konur; her resize olayı yeni iş üretmez."""
    frame, _ = _ready_frame()

    for height in range(772, 762, -1):
        frame.set_height(height)
        frame._schedule_subtitle_band_sync()

    assert len(scheduler.queue) == 1, (
        f"10 resize adimi {len(scheduler.queue)} is siraya koydu")


def test_the_recorded_size_is_not_refreshed_while_pending(scheduler):
    """Bekleyen iş varken kayıtlı boyut GÜNCELLENMEZ.

    Güncellenirse karşılaştırma daima eşit çıkar, erteleme hiç işlemez ve
    kusur sessizce geri gelir.
    """
    frame, mpv = _ready_frame()

    frame.set_height(700)
    frame._schedule_subtitle_band_sync()
    recorded = frame._band_sync_size
    frame.set_height(680)
    frame._schedule_subtitle_band_sync()

    assert frame._band_sync_size == recorded
    # Tur çalışınca boyut değişmiş olduğu için YAZMAMALI.
    scheduler.run_turn()
    assert mpv.order == []


def test_a_pending_flush_on_a_deleted_widget_is_dropped(scheduler):
    """Kapanışta silinmiş widget'a bekleyen yazım ÇÖKMEMELİ.

    `QTimer.singleShot(ms, slot)` context almaz (bu PyQt6 sürümünde
    `(ms, nesne, slot)` aşırı yüklemesi YOKTUR — ölçüldü), yani geri
    çağrı pencere kapandıktan SONRA da ateşlenebilir. Silinmiş bir C++
    nesnesine `width()` sormak `RuntimeError` verir.
    """
    frame, mpv = _ready_frame()
    frame.set_height(600)
    frame._schedule_subtitle_band_sync()

    def deleted():
        raise RuntimeError("wrapped C/C++ object has been deleted")

    frame.width = deleted

    frame._flush_subtitle_band()  # çökmemeli

    assert mpv.order == [], "silinmis widget icin libmpv'ye yazildi"
    assert frame._band_sync_pending is False


def test_flush_applies_a_pending_write_immediately():
    """`flush_subtitle_band()` bekleyen yazımı HEMEN uygular."""
    frame, mpv = _ready_frame()

    frame.set_height(600)
    frame._schedule_subtitle_band_sync()
    assert mpv.order == []

    frame.flush_subtitle_band()

    assert mpv.order != [], "flush bekleyen yazimi uygulamadi"
    assert frame._band_sync_pending is False
