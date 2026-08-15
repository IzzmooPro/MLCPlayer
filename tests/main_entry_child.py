"""Gerçek `python main.py` giriş noktasını taklit eden ölçüm child'ı.

main.py'nin bağımlılık kurulum adımını (check_dependencies) aynen çalıştırır,
ardından MPVPlayer'ı main.py ile birebir aynı şekilde oluşturur ve varsayılan
arayüz durumunu raporlar. Hiçbir UI ortam değişkeni ayarlamaz.
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication

import main as main_module


def run():
    app = QApplication(sys.argv)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      os.environ["MLC_DEFAULT_UI_SETTINGS"])

    if not main_module.check_dependencies():
        print("DEFAULT_UI_JSON " + json.dumps({"error": "dependencies"}),
              flush=True)
        return 1

    from app.player import MPVPlayer
    player = MPVPlayer()
    player.show()
    app.processEvents()

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
        "overlay_created": player.video_frame.control_overlay is not None,
        "control_container_visible": player.control_container.isVisible(),
        "control_container_height": player.control_container.height(),
        "timeline_hit_height": (
            player.video_frame.overlay_timeline.height()
            if player.video_frame.control_overlay is not None else None),
    }

    if player.mpv_player is not None:
        player.mpv_player.terminate()
        player.mpv_player = None
    player.close()

    print("DEFAULT_UI_JSON " + json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    # ÜRÜNLE AYNI KAPANIŞ (`main.py` -> `os._exit(ret)`): libmpv yüklendikten
    # sonra normal Python finalizasyonu thread-safe olmayan DLL yıkımında
    # takılabiliyor. Ölçüm JSON'u bu noktadan ÖNCE basıldığı için veri
    # kaybı olmaz; kapanış artık asılı kalmaz.
    _code = run()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
