import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import QApplication

from app.player import MPVPlayer

app = QApplication(sys.argv)
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
settings_dir = os.environ.get(
    "MLCPLAYER_TEST_SETTINGS",
    os.path.join(os.environ.get("TEMP", project_root), "MLCPlayer-smoke-settings"),
)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_dir)
player = MPVPlayer()
player.show()
QTimer.singleShot(300, player.close)
QTimer.singleShot(600, app.quit)
app.exec()

if player.mpv_player is not None:
    raise SystemExit("MPV temiz kapanmadı")
