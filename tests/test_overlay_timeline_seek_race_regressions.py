# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Timeline %90 tiklama yarisi: tiklama urune ulasiyor mu, hedef eziliyor mu?

Fiziksel kabulde gorulen kirmizi (2026-08-14, `timeline` grubu):

    click_90_on[open]  expected_value=899 actual_value=99  start=99
    actual_time=1180.8 (baslangic zamani), down=False

Yani %90 hedefine yapilan tek kullanici tiklamasindan sonra hem slider hem
`time_pos` BASLANGIC degerinde kalmis. Iki bagimsiz aciklama vardir:

  (A) URUN yarisi: tiklama urune ULASTI, `seek_position(900)` cagrildi, ama
      hemen ardindan gelen periyodik guncelleme (`update_overlay_state()`)
      mpv'nin HENUZ ESKI `position` degerini okuyup slider'i geri cekti ve
      bu geri cekis YENI bir seek yayarak kullanicinin hedefini EZDI.
  (B) GIRDI/harness: fiziksel tiklama urune hic ulasmadi; hicbir seek
      yayilmadi ve deger dogal olarak yerinde kaldi.

Bu dosya ikisini deterministik olarak ayirir: gercek `ClickableSlider`
uzerine QTest ile TEK tiklama gonderilir, sonra `position` BILEREK eski
degerde birakilarak (seek ucusta) periyodik guncelleme calistirilir.
Olculen: hangi seek cagrilari yayildi, slider ne oldu.

Not: burada mpv YOKTUR; `seek_position` cagrilari kaydedilir. Amac zaten
mpv'yi degil, URUNUN kendi hedef-koruma davranisini olcmektir.
"""
from PyQt6.QtCore import QPoint, QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from app.video_frame import VideoFrame

DURATION = 100.0
START_RATIO = 0.10
TARGET_RATIO = 0.90


def make_window(monkeypatch, tmp_path):
    """`tests/test_overlay_sync_regressions.py` ile ayni offscreen kurulum."""
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.central_widget = QWidget(window)
    window.setCentralWidget(window.central_widget)
    window.main_layout = QVBoxLayout(window.central_widget)
    window.duration = DURATION
    window.position = DURATION * START_RATIO
    window.is_paused = True
    window.seek_calls = []
    window.play_previous = lambda: None
    window.play_next = lambda: None
    window.play_pause = lambda: None
    window.toggle_fullscreen = lambda: None
    window.seek_position = lambda value: window.seek_calls.append(value)
    frame = VideoFrame(window)
    window.video_frame = frame
    window.main_layout.addWidget(frame)
    window.resize(1400, 820)
    window.show()
    app.processEvents()
    frame.update_overlay_state()
    app.processEvents()
    return app, window, frame


def click_at_ratio(app, timeline, ratio):
    """Timeline uzerine TEK gercek Qt tiklamasi (press + release)."""
    x = int(timeline.width() * ratio)
    y = timeline.height() // 2
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
    app.processEvents()
    return int(round(1000 * x / max(1, timeline.width())))


def test_a_click_at_ninety_percent_reaches_the_product(monkeypatch, tmp_path):
    """(1) Tiklama urune ULASIYOR mu ve HANGI seek yayiliyor?"""
    app, window, frame = make_window(monkeypatch, tmp_path)
    timeline = frame.overlay_timeline
    assert timeline.value() == 100  # baslangic ~%10 kuruldu

    wanted = click_at_ratio(app, timeline, TARGET_RATIO)

    assert window.seek_calls == [wanted]
    assert abs(timeline.value() - wanted) <= 2
    window.close()
    app.processEvents()


def test_a_stale_position_refresh_does_not_reseek_to_the_old_spot(
        monkeypatch, tmp_path):
    """(2) Seek UCUSTAYKEN gelen periyodik guncelleme hedefi EZIYOR mu?

    `window.position` BILEREK eski degerde birakilir: mpv'nin seek'i henuz
    tamamlamadigi an budur. Guncelleme slider'i geri cekebilir, ancak YENI
    bir `seek_position` YAYMAMALIDIR; aksi halde kullanicinin hedefi
    iptal edilir ve deger baslangicta kalir.
    """
    app, window, frame = make_window(monkeypatch, tmp_path)
    timeline = frame.overlay_timeline
    wanted = click_at_ratio(app, timeline, TARGET_RATIO)
    assert window.seek_calls == [wanted]

    # Seek ucusta: pozisyon HALA eski.
    frame.update_overlay_state()
    app.processEvents()

    assert window.seek_calls == [wanted], (
        "eski pozisyonlu guncelleme kullanicinin hedefini ezdi: "
        f"{window.seek_calls}")
    window.close()
    app.processEvents()


def test_the_target_is_restored_once_the_seek_lands(monkeypatch, tmp_path):
    """(3) Seek tamamlandiginda slider kullanicinin hedefine DONUYOR mu?"""
    app, window, frame = make_window(monkeypatch, tmp_path)
    timeline = frame.overlay_timeline
    wanted = click_at_ratio(app, timeline, TARGET_RATIO)

    frame.update_overlay_state()          # ucusta: eski pozisyon
    window.position = DURATION * (wanted / 1000.0)   # seek tamamlandi
    frame.update_overlay_state()
    app.processEvents()

    assert abs(timeline.value() - wanted) <= 2
    assert window.seek_calls == [wanted]
    window.close()
    app.processEvents()


def test_a_press_marks_the_slider_down_and_a_release_clears_it(
        monkeypatch, tmp_path):
    """Fiziksel olcumun `down=False` sozlesmesi: birakma durumu temizler."""
    app, window, frame = make_window(monkeypatch, tmp_path)
    timeline = frame.overlay_timeline
    x = int(timeline.width() * TARGET_RATIO)
    y = timeline.height() // 2

    QTest.mousePress(timeline, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
    app.processEvents()
    down_during_press = timeline.isSliderDown()
    QTest.mouseRelease(timeline, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
    app.processEvents()

    assert down_during_press is True
    assert timeline.isSliderDown() is False
    window.close()
    app.processEvents()
