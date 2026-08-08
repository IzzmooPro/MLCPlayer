"""Gerçek MPVPlayer kabuğunun düzenini ölçen child süreç.

Native MPV örneği pytest sürecini kapanışta düşürebildiği için ölçüm ayrı
süreçte yapılır ve sonuç JSON olarak stdout'a yazılır. Sabit ekran
koordinatı kullanılmaz; her şey gerçek layout geometrisinden okunur.
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QPoint, QRect, QSettings
from PyQt6.QtWidgets import QApplication

from app.player import MPVPlayer


def rect_of(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def as_list(rect):
    return [rect.x(), rect.y(), rect.width(), rect.height()]


def visible_top_levels(app, player):
    """Overlay ve OSD dışında görünen top-level pencereler."""
    ignored = {id(player.video_frame.osd_label)}
    if player.video_frame.control_overlay is not None:
        ignored.add(id(player.video_frame.control_overlay))
    names = []
    for widget in app.topLevelWidgets():
        if id(widget) in ignored or not widget.isVisible():
            continue
        names.append(f"{type(widget).__name__}:{widget.objectName()}")
    return names


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      os.environ["MLC_LAYOUT_SETTINGS"])

    player = MPVPlayer()
    player.show()
    app.processEvents()

    report = {"preview": os.environ.get("MLCPLAYER_OVERLAY_PREVIEW", "")}

    overlay = player.video_frame.control_overlay
    report["overlay_created"] = overlay is not None
    report["has_position_slider"] = hasattr(player, "position_slider")
    report["has_play_button"] = hasattr(player, "play_button")
    report["has_control_container"] = hasattr(player, "control_container")

    # --- Gerçek minimum pencere ölçümü ---
    player.resize(400, 300)
    app.processEvents()
    player.video_frame.update_overlay_geometry()
    app.processEvents()

    report["window_minimum"] = [player.minimumWidth(), player.minimumHeight()]
    report["window_size_at_min"] = [player.width(), player.height()]
    report["window_rect_at_min"] = as_list(rect_of(player))
    report["video_rect_at_min"] = as_list(rect_of(player.video_frame))
    report["video_minimum"] = [player.video_frame.minimumWidth(),
                               player.video_frame.minimumHeight()]
    if hasattr(player, "control_container"):
        report["control_container_visible_at_min"] = \
            player.control_container.isVisible()
        report["control_container_height_at_min"] = player.control_container.height()
        report["control_rect_at_min"] = as_list(rect_of(player.control_container))
    if overlay is not None:
        report["overlay_rect_at_min"] = as_list(overlay.geometry())
        report["overlay_timeline_rect_at_min"] = as_list(
            rect_of(player.video_frame.overlay_timeline))
        report["overlay_play_rect_at_min"] = as_list(
            rect_of(player.video_frame.overlay_play_pause_button))
        report["overlay_current_label_rect_at_min"] = as_list(
            rect_of(player.video_frame.overlay_current_time_label))
        report["overlay_fullscreen_rect_at_min"] = as_list(rect_of(
            next(b for b in overlay.findChildren(type(
                player.video_frame.overlay_play_pause_button))
                if b.objectName() == "overlayFullscreen")))

    # --- Normal pencere ---
    player.resize(1000, 700)
    app.processEvents()
    player.video_frame.update_overlay_geometry()
    app.processEvents()
    report["menu_visible_normal"] = player.menuBar().isVisible()
    if hasattr(player, "control_container"):
        report["control_container_visible_normal"] = \
            player.control_container.isVisible()
        report["control_container_height_normal"] = player.control_container.height()
    report["video_rect_normal"] = as_list(rect_of(player.video_frame))
    report["geometry_before_fullscreen"] = as_list(player.geometry())
    report["maximized_before_fullscreen"] = player.isMaximized()

    # --- Fullscreen ---
    player.toggle_fullscreen()
    app.processEvents()
    report["fullscreen_flag"] = player.video_frame.is_video_fullscreen
    report["window_is_fullscreen"] = player.isFullScreen()
    report["visible_top_levels_fullscreen"] = visible_top_levels(app, player)
    report["menu_visible_fullscreen"] = player.menuBar().isVisible()
    if hasattr(player, "control_container"):
        report["control_container_visible_fullscreen"] = \
            player.control_container.isVisible()
    report["video_rect_fullscreen"] = as_list(rect_of(player.video_frame))
    report["screen_rect"] = as_list(app.primaryScreen().geometry())
    if overlay is not None:
        report["overlay_rect_fullscreen"] = as_list(overlay.geometry())
        report["overlay_owner_is_main_window_fullscreen"] = \
            overlay.parent() is player

    # --- Fullscreen çıkışı ---
    player.toggle_fullscreen()
    app.processEvents()
    report["fullscreen_flag_after_exit"] = player.video_frame.is_video_fullscreen
    report["window_is_fullscreen_after_exit"] = player.isFullScreen()
    report["menu_visible_after_exit"] = player.menuBar().isVisible()
    if hasattr(player, "control_container"):
        report["control_container_visible_after_exit"] = \
            player.control_container.isVisible()
    report["geometry_after_exit"] = as_list(player.geometry())
    report["visible_top_levels_after_exit"] = visible_top_levels(app, player)

    if player.mpv_player is not None:
        player.mpv_player.terminate()
        player.mpv_player = None
    player.close()

    print("LAYOUT_JSON " + json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
