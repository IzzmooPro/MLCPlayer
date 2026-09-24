# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Ana pencerenin her süreç açılışında varsayılan boyutta ortalanması."""

from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import QPoint, QRect, QSize

from app.player import centered_startup_position


ROOT = Path(__file__).resolve().parent.parent


def test_startup_position_centers_the_existing_window_size():
    available = QRect(1920, 40, 1920, 1040)
    current_size = QSize(913, 517)

    target = centered_startup_position(available, current_size)

    assert target == QPoint(
        available.x() + (available.width() - current_size.width()) // 2,
        available.y() + (available.height() - current_size.height()) // 2,
    )


def test_oversized_window_keeps_its_title_bar_on_the_screen():
    # Kayıtlı boyut daha büyük bir monitörden kalmışsa ortalama negatif
    # konum üretir; başlık çubuğu ekranın dışına düşer ve tutulamaz.
    available = QRect(1920, 40, 1366, 728)
    saved_size = QSize(1900, 1000)

    target = centered_startup_position(available, saved_size)

    assert target == QPoint(available.x(), available.y())


def test_main_centers_the_window_before_showing_it():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    center = source.index("player.center_on_active_screen()")
    show = source.index("player.show()", center)
    assert center < show


def test_startup_move_uses_the_active_screen_without_resizing(monkeypatch):
    from app import player as player_module

    available = QRect(300, 70, 1600, 900)
    screen = SimpleNamespace(availableGeometry=lambda: available)
    moves = []
    window = SimpleNamespace(
        size=lambda: QSize(913, 517),
        move=lambda point: moves.append(point),
    )
    monkeypatch.setattr(
        player_module, "QApplication",
        SimpleNamespace(screenAt=lambda _point: screen,
                        primaryScreen=lambda: None))
    monkeypatch.setattr(
        player_module, "QCursor", SimpleNamespace(pos=lambda: QPoint()))

    player_module.MPVPlayer.center_on_active_screen(window)

    assert moves == [QPoint(643, 261)]


def test_saved_size_and_other_geometry_behaviour_are_left_intact():
    source = (ROOT / "app" / "player.py").read_text(encoding="utf-8")
    assert "restoreGeometry(saved_geometry)" in source
    assert 'setValue("geometry", self.saveGeometry())' in source
