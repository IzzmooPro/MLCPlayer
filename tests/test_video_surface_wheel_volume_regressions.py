# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Video yuzeyi uzerinde fare tekerlegiyle ses kontrolu sozlesmesi.

Kullanici video sahnesinin uzerinde tekerlegi cevirdiginde ses degismelidir.
Sozlesme, mevcut ses akisini YENIDEN YAZMAZ: tek ses kaynagi urunun kendi
`change_volume()` -> `volume_slider` -> `set_volume()` yoludur; sinirlar,
etiket, mute durumu, overlay slider'i ve OSD oradan gelir.

Olculen kurallar:
- Dikey teker video sahnesi uzerinde sesi bir kademe (+-5) degistirir.
- Tek teker olayi ses akisini BIR KEZ tetikler.
- Yuksek cozunurluklu kucuk `angleDelta` olaylari tek tek kademe URETMEZ;
  standart 120 birimlik kademe mantigiyla birikir.
- Yatay teker sesi degistirmez.
- Video yokken (yer tutucu ekran) teker sesi degistirmez.
- Kaydirilabilir COCUK kontrollerin tekerlegi ELE GECIRILMEZ. (Playlist
  artik ayri bir penceredir ve bu agacin icinde degildir.)
- Overlay gizli ya da gorunur olsun ayni merkezi davranis calisir.
- Ses cubugunun KENDI `wheelEvent` davranisi bozulmaz.
- Ses akisindaki bir hata kullanici arayuzune ham teknik metin dokmez.
"""
from PyQt6.QtCore import QPoint, QPointF, QSettings, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import (QApplication, QListWidget, QMainWindow,
                             QVBoxLayout, QWidget)

from app.config import MAX_VOLUME
from app.ui_components import VolumeSlider
from app.video_frame import VideoFrame

WHEEL_STEP = 120


def make_window(monkeypatch, tmp_path, with_video=True):
    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.central_widget = QWidget(window)
    window.setCentralWidget(window.central_widget)
    window.main_layout = QVBoxLayout(window.central_widget)
    window.duration = 100.0 if with_video else 0.0
    window.position = 10.0
    window.current_file = r"D:\video.mkv" if with_video else None
    window.is_paused = True
    window.volume_calls = []
    window.play_previous = lambda: None
    window.play_next = lambda: None
    window.play_pause = lambda: None
    window.toggle_fullscreen = lambda: None
    window.seek_position = lambda value: None
    window.change_volume = lambda delta: window.volume_calls.append(delta)
    frame = VideoFrame(window)
    window.video_frame = frame
    window.main_layout.addWidget(frame)
    window.resize(1400, 820)
    window.show()
    if with_video:
        # Urun medya acilinca yer tutucuyu gizler (`app/media_controls.py`);
        # video sahnesi durumu birebir kurulur.
        frame.placeholder_label.hide()
    app.processEvents()
    return app, window, frame


def wheel(app, widget, dy=0, dx=0, pos=None):
    """Gercek bir QWheelEvent gonderir (sentetik urun cagrisi degil)."""
    point = QPointF(pos if pos is not None
                    else QPointF(widget.width() / 2, widget.height() / 2))
    event = QWheelEvent(point, widget.mapToGlobal(point.toPoint()).toPointF(),
                        QPoint(0, 0), QPoint(dx, dy),
                        Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)
    app.processEvents()
    return event


def close(app, window):
    window.close()
    app.processEvents()


# =====================================================================
# 1. Temel davranis
# =====================================================================

def test_wheel_up_over_the_video_raises_the_volume_one_step(monkeypatch, tmp_path):
    app, window, frame = make_window(monkeypatch, tmp_path)

    wheel(app, frame, dy=WHEEL_STEP)

    assert window.volume_calls == [5]
    close(app, window)


def test_wheel_down_over_the_video_lowers_the_volume_one_step(monkeypatch, tmp_path):
    app, window, frame = make_window(monkeypatch, tmp_path)

    wheel(app, frame, dy=-WHEEL_STEP)

    assert window.volume_calls == [-5]
    close(app, window)


def test_one_wheel_event_is_applied_only_once(monkeypatch, tmp_path):
    """Cift uygulama (hem yerel hem ust widget) olmamali."""
    app, window, frame = make_window(monkeypatch, tmp_path)

    wheel(app, frame, dy=WHEEL_STEP)
    wheel(app, frame, dy=WHEEL_STEP)

    assert window.volume_calls == [5, 5]
    close(app, window)


def test_the_single_volume_source_is_the_product_flow(monkeypatch, tmp_path):
    """Ses YALNIZ `change_volume()` uzerinden degisir; yan yol yok."""
    app, window, frame = make_window(monkeypatch, tmp_path)
    window.set_volume = lambda value: window.volume_calls.append(("set", value))

    wheel(app, frame, dy=WHEEL_STEP)

    assert window.volume_calls == [5]
    close(app, window)


# =====================================================================
# 2. Yuksek cozunurluklu teker
# =====================================================================

def test_small_high_resolution_deltas_do_not_each_make_a_step(
        monkeypatch, tmp_path):
    """40 + 40 + 40 = 120 -> TEK kademe, uc kademe DEGIL."""
    app, window, frame = make_window(monkeypatch, tmp_path)

    wheel(app, frame, dy=40)
    assert window.volume_calls == []
    wheel(app, frame, dy=40)
    assert window.volume_calls == []
    wheel(app, frame, dy=40)

    assert window.volume_calls == [5]
    close(app, window)


def test_a_large_delta_makes_proportional_steps(monkeypatch, tmp_path):
    """Iki kademelik tek olay iki kademe uygular (kayip yok)."""
    app, window, frame = make_window(monkeypatch, tmp_path)

    wheel(app, frame, dy=2 * WHEEL_STEP)

    assert window.volume_calls == [10]
    close(app, window)


def test_direction_change_does_not_leak_leftovers(monkeypatch, tmp_path):
    """Yonu degisen kucuk artiklar ters yonde sahte kademe uretmemeli."""
    app, window, frame = make_window(monkeypatch, tmp_path)

    wheel(app, frame, dy=40)
    wheel(app, frame, dy=-40)

    assert window.volume_calls == []
    close(app, window)


# =====================================================================
# 3. Ele gecirilmemesi gerekenler
# =====================================================================

def test_horizontal_wheel_does_not_change_the_volume(monkeypatch, tmp_path):
    app, window, frame = make_window(monkeypatch, tmp_path)

    wheel(app, frame, dx=WHEEL_STEP)

    assert window.volume_calls == []
    close(app, window)


def test_wheel_without_media_does_not_change_the_volume(monkeypatch, tmp_path):
    """Yer tutucu ekranda (video yok) teker sesi degistirmez."""
    app, window, frame = make_window(monkeypatch, tmp_path, with_video=False)

    wheel(app, frame, dy=WHEEL_STEP)

    assert window.volume_calls == []
    close(app, window)


def test_a_scrollable_child_keeps_its_own_wheel(monkeypatch, tmp_path):
    """Kaydirilabilir COCUK yuzeylerin tekerlegi ele gecirilmez.

    OZNE DEGISTI (17 Agustos 2026), sozlesme DEGISMEDI. Bu test eskiden
    playlist panelini kullaniyordu; panel artik ayri bir top-level
    penceredir ve video cerceve agacinin icinde DEGILDIR, yani `childAt()`
    korumasinin oznesi olamaz. Urun mekanizmasi (`_wheel_targets_video_scene`
    -> `childAt(...) is None`) hic degismedi; burada gercek bir cocuk
    widget ile olculur.
    """
    app, window, frame = make_window(monkeypatch, tmp_path)
    child = QListWidget(frame)
    child.setGeometry(0, 0, 300, frame.height())
    child.show()
    app.processEvents()

    wheel(app, frame, dy=WHEEL_STEP, pos=QPointF(20, frame.height() / 2))

    assert window.volume_calls == []
    close(app, window)


def test_the_volume_slider_keeps_its_own_wheel_behaviour():
    """Ses cubugu uzerindeki mevcut `wheelEvent` DEGISMEDI."""
    app = QApplication.instance() or QApplication([])
    slider = VolumeSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, MAX_VOLUME)
    slider.setValue(50)

    slider.wheelEvent(QWheelEvent(
        QPointF(1.0, 1.0), QPointF(1.0, 1.0), QPoint(0, 0),
        QPoint(0, WHEEL_STEP), Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
    app.processEvents()

    assert slider.value() == 55


# =====================================================================
# 4. Overlay durumu ve hata guvenligi
# =====================================================================

def test_the_same_behaviour_applies_while_the_overlay_is_hidden(
        monkeypatch, tmp_path):
    """Overlay gizliyken de ayni merkezi davranis calisir."""
    app, window, frame = make_window(monkeypatch, tmp_path)
    frame.hide_overlay_immediately()
    app.processEvents()

    wheel(app, frame, dy=WHEEL_STEP)

    assert window.volume_calls == [5]
    close(app, window)


def test_a_volume_error_does_not_reach_the_user_as_raw_text(
        monkeypatch, tmp_path):
    """Ses akisindaki hata ham teknik metin olarak yuzeye cikmaz."""
    app, window, frame = make_window(monkeypatch, tmp_path)

    def boom(delta):
        raise RuntimeError("mpv volume property write failed at 0x7ffd")

    window.change_volume = boom
    shown = []
    monkeypatch.setattr(frame, "show_osd", lambda text, *a, **k: shown.append(text))

    wheel(app, frame, dy=WHEEL_STEP)

    assert all("RuntimeError" not in text and "0x7ffd" not in text
               for text in shown)
    close(app, window)
