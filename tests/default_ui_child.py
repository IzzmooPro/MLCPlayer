# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Varsayılan (sinematik) arayüzü gerçek MPVPlayer üzerinde ölçen child.

Bu script hiçbir UI ortam değişkeni varsaymaz; çağıran taraf istediği
değişkeni açıkça ayarlar. Sonuç JSON olarak stdout'a yazılır.
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QPoint, QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from app.player import MPVPlayer


def phase(name):
    """Açılış fazını STDERR'e işaretler.

    Ölçüm sözleşmesi (stdout'taki tek `DEFAULT_UI_JSON` satırı) DEĞİŞMEZ.
    Gerekçe: bu child aralıklarla HİÇ çıktı üretmeden asılı kalıyordu;
    `olcum uretilmis mi: HAYIR` kanıtı takılmanın açılış fazında olduğunu
    gösterdi ama hangi adımda olduğunu göstermedi. Faz işareti bir sonraki
    takılmada adımı doğrudan verir.
    """
    print(f"PHASE {name}", file=sys.stderr, flush=True)


def main():
    phase("qapplication")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      os.environ["MLC_DEFAULT_UI_SETTINGS"])

    phase("mpvplayer_init")
    player = MPVPlayer()
    phase("mpvplayer_ready")
    player.resize(1280, 800)
    player.show()
    app.processEvents()
    phase("shown")

    frame = player.video_frame
    overlay = frame.control_overlay
    bar = getattr(player, "title_bar", None)

    report = {
        "env_overlay_preview": os.environ.get("MLCPLAYER_OVERLAY_PREVIEW"),
        "env_classic_ui": os.environ.get("MLCPLAYER_CLASSIC_UI"),
        "cinematic_ui_enabled": getattr(player, "cinematic_ui_enabled", None),
        "frameless": bool(
            player.windowFlags() & Qt.WindowType.FramelessWindowHint),
        "has_title_bar": bar is not None,
        "title_bar_visible": bool(bar and bar.isVisible()),
        "menu_bar_visible": player.menuBar().isVisible(),
        "overlay_created": overlay is not None,
        "overlay_visible": bool(overlay and overlay.isVisible()),
        # Gizli uyumluluk nesneleri yaşamaya devam etmeli
        "has_control_container": hasattr(player, "control_container"),
        "has_position_slider": hasattr(player, "position_slider"),
        "has_volume_slider": hasattr(player, "volume_slider"),
        "menu_bar_action_count": len(player.menuBar().actions()),
    }
    if hasattr(player, "control_container"):
        report["control_container_visible"] = player.control_container.isVisible()
        report["control_container_height"] = player.control_container.height()

    if overlay is not None:
        report["timeline_hit_height"] = frame.overlay_timeline.height()
        report["overlay_height"] = overlay.height()
        report["has_auto_hide_timer"] = frame.overlay_hide_timer is not None
        report["auto_hide_interval"] = (
            frame.overlay_hide_timer.interval()
            if frame.overlay_hide_timer is not None else None)
        report["has_fade_animation"] = frame.overlay_fade is not None

        # Gerçek seek: timeline tıklaması slider ve mpv time_pos değiştirmeli
        player.duration = 600.0
        player.current_file = "<test-video>"
        timeline = frame.overlay_timeline
        timeline.setValue(0)
        player.mpv_player.time_pos = 0.0
        QTest.mouseClick(timeline, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier(0),
                         QPoint(int(timeline.width() * 0.5),
                                timeline.height() - 3))
        app.processEvents()
        report["timeline_click_value"] = timeline.value()
        try:
            report["timeline_click_time_pos"] = float(
                player.mpv_player.time_pos or 0.0)
        except Exception:
            report["timeline_click_time_pos"] = None

    if bar is not None:
        names = [b.objectName() for b in bar.findChildren(QPushButton)
                 if b.objectName()]
        report["title_bar_buttons"] = sorted(names)
        report["overflow_titles"] = [
            action.text() for action in bar.build_overflow_menu().actions()
            if action.menu()]

        calls = []
        player.open_file = lambda: calls.append("open_file")
        player.show_playlist = lambda: calls.append("show_playlist")
        for name in ("titleOpenFile", "titlePlaylist"):
            next(b for b in bar.findChildren(QPushButton)
                 if b.objectName() == name).click()
            app.processEvents()
        report["title_bar_calls"] = calls
        bar.toggle_maximized()
        app.processEvents()
        report["maximize_state"] = bar.maximize_button.accessibleName()
        bar.toggle_maximized()
        app.processEvents()
        report["restore_state"] = bar.maximize_button.accessibleName()

    # Fullscreen davranışı
    player.toggle_fullscreen()
    app.processEvents()
    report["fullscreen_active"] = player.isFullScreen()
    report["title_bar_visible_fullscreen"] = bool(bar and bar.isVisible())
    player.toggle_fullscreen()
    app.processEvents()
    report["title_bar_visible_after_fullscreen"] = bool(bar and bar.isVisible())
    report["overlay_visible_after_fullscreen"] = bool(
        overlay and overlay.isVisible())

    if player.mpv_player is not None:
        player.mpv_player.terminate()
        player.mpv_player = None
    player.close()

    print("DEFAULT_UI_JSON " + json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    # ÜRÜNLE AYNI KAPANIŞ. `main.py` bunu şöyle belgeliyor: "mpv DLL'leri bu
    # yapıda interpreter kapanışında takılıyor (thread-safe olmayan DLL
    # yıkımı)" ve bu yüzden `os._exit(ret)` kullanıyor. Bu child libmpv
    # yüklediği hâlde normal finalizasyona giriyordu; ölçüm (JSON) çoktan
    # basılmış olmasına rağmen süreç bazen kapanmıyor ve çağıran taraf
    # `subprocess.TimeoutExpired` alıyordu. Ölçülen kanıt: aynı child
    # doğrudan çalıştırıldığında 11/11 koşumda 0,3-0,5 sn'de exit=0, ama
    # tam pakette aralıklı olarak 180 sn boyunca asılı kalıyordu.
    _code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
