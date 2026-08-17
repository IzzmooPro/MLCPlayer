# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Gerçek MPVPlayer kabuğunda başlık çubuğu ölçümü yapan child süreç.

Native MPV pytest sürecini kapanışta düşürebildiği için ölçüm ayrı süreçte
yapılır ve sonuç JSON olarak stdout'a yazılır.
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QPoint, QRect, QSettings, Qt
from PyQt6.QtWidgets import QApplication, QPushButton

from app.player import MPVPlayer


def rect_of(widget):
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def as_list(rect):
    return [rect.x(), rect.y(), rect.width(), rect.height()]


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      os.environ["MLC_TITLEBAR_SETTINGS"])

    player = MPVPlayer()
    player.show()
    app.processEvents()

    report = {"preview": os.environ.get("MLCPLAYER_OVERLAY_PREVIEW", "")}
    bar = getattr(player, "title_bar", None)

    report["has_title_bar"] = bar is not None
    report["frameless"] = bool(
        player.windowFlags() & Qt.WindowType.FramelessWindowHint)
    report["menu_bar_visible"] = player.menuBar().isVisible()
    report["menu_bar_action_count"] = len(player.menuBar().actions())
    report["window_minimum"] = [player.minimumWidth(), player.minimumHeight()]

    if bar is not None:
        report["title_bar_height"] = bar.height()
        report["title_bar_visible"] = bar.isVisible()
        report["overflow_titles"] = [
            action.text() for action in bar.build_overflow_menu().actions()
            if action.menu()]

    # --- Minimum pencere ---
    player.resize(400, 300)
    app.processEvents()
    report["window_rect_at_min"] = as_list(rect_of(player))
    if bar is not None:
        report["title_rect_at_min"] = as_list(rect_of(bar))
        buttons = {}
        for widget in bar.findChildren(QPushButton):
            if widget.objectName():
                buttons[widget.objectName()] = as_list(rect_of(widget))
        report["title_buttons_at_min"] = buttons
    report["video_rect_at_min"] = as_list(rect_of(player.video_frame))

    # --- Normal pencere ---
    player.resize(1000, 700)
    app.processEvents()
    if bar is not None:
        report["title_bar_visible_normal"] = bar.isVisible()

    # --- Fullscreen ---
    player.toggle_fullscreen()
    app.processEvents()
    report["window_is_fullscreen"] = player.isFullScreen()
    if bar is not None:
        report["title_bar_visible_fullscreen"] = bar.isVisible()
    report["menu_visible_fullscreen"] = player.menuBar().isVisible()
    report["video_rect_fullscreen"] = as_list(rect_of(player.video_frame))

    player.toggle_fullscreen()
    app.processEvents()
    report["window_is_fullscreen_after_exit"] = player.isFullScreen()
    report["has_ensure_helper"] = hasattr(player, "ensure_title_bar_on_top")
    report["has_raise_pending_flag"] = hasattr(player, "_title_bar_raise_pending")
    # Oynatma başlangıcı yolu: bayrak set edilir, tek update_ui ile temizlenir
    ensure_calls = []
    original_ensure = player.ensure_title_bar_on_top
    player.ensure_title_bar_on_top = lambda: (ensure_calls.append(1),
                                              original_ensure())[1]
    player.mark_title_bar_raise_pending()
    report["mark_sets_pending"] = player._title_bar_raise_pending
    player.duration = 10.0
    for _ in range(5):
        player.update_ui()
    report["raise_pending_cleared_after_one_update"] = (
        player._title_bar_raise_pending is False)
    report["ensure_calls_for_one_playback"] = len(ensure_calls)
    player.update_ui()
    report["raise_pending_stays_cleared"] = (
        player._title_bar_raise_pending is False)
    report["ensure_calls_after_extra_updates"] = len(ensure_calls)
    player.ensure_title_bar_on_top = original_ensure
    if bar is not None:
        siblings = [w for w in player.central_widget.children()
                    if hasattr(w, "isWidgetType") and w.isWidgetType()]
        report["title_bar_last_in_child_order_after_exit"] = (
            siblings[-1] is bar if siblings else False)
        # Video açılışı sonrası tek seferlik yeniden öne alma yolu
        player.ensure_title_bar_on_top()
        app.processEvents()
        siblings = [w for w in player.central_widget.children()
                    if hasattr(w, "isWidgetType") and w.isWidgetType()]
        report["title_bar_on_top_after_helper"] = (
            siblings[-1] is bar if siblings else False)
        report["title_bar_visible_after_helper"] = bar.isVisible()
    if bar is not None:
        report["title_bar_visible_after_exit"] = bar.isVisible()
    report["menu_visible_after_exit"] = player.menuBar().isVisible()
    report["overlay_created"] = player.video_frame.control_overlay is not None

    if player.mpv_player is not None:
        player.mpv_player.terminate()
        player.mpv_player = None
    player.close()

    print("TITLEBAR_JSON " + json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    # ÜRÜNLE AYNI KAPANIŞ (`main.py` -> `os._exit(ret)`): libmpv yüklendikten
    # sonra normal Python finalizasyonu takılabiliyor. Ölçüm JSON'u bu
    # noktadan ÖNCE basılır.
    _code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
