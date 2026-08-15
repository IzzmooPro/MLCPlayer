import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ["PATH"]

from PyQt6.QtCore import QPoint, QSettings, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app.player import MPVPlayer

app = QApplication(sys.argv)
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
settings_dir = os.environ.get(
    "MLCPLAYER_TEST_SETTINGS",
    os.path.join(os.environ.get("TEMP", project_root), "MLCPlayer-timeline-settings"),
)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_dir)
player = MPVPlayer()
player.show()
app.processEvents()
player.duration = 100.0
player.position = 10.0
slider = player.position_slider
center_y = slider.height() // 2
start = QPoint(max(2, slider.width() // 4), center_y)
end = QPoint(max(3, slider.width() // 2), center_y)

QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
pressed_slider_value = slider.value()
pressed_time_pos = player.mpv_player.time_pos
QTest.mouseMove(slider, end, 50)
assert slider.isSliderDown()
dragged_value = slider.value()
dragged_time_pos = player.mpv_player.time_pos
assert dragged_value != pressed_slider_value
assert dragged_time_pos != pressed_time_pos
player.position = 10.0
player.update_ui()
assert slider.value() == dragged_value
QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
assert not slider.isSliderDown()

player.close()
QTimer.singleShot(100, app.quit)
app.exec()

# ÜRÜNLE AYNI KAPANIŞ (`main.py` -> `os._exit(ret)`): libmpv yüklendikten
# sonra normal Python finalizasyonu takılabiliyor. Buraya ulaşmak bütün
# assert'lerin geçtiği anlamına gelir; başarısızlıkta zaten istisna ile
# non-zero exit üretilir.
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
