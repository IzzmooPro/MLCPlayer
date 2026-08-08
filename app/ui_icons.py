"""QPainter tabanlı, küçük ve yeniden kullanılabilir medya ikonları.

Windows tema ikonlarına bağımlı kalmamak için sade beyaz glifleri doğrudan
çizeriz. Harici ikon paketi veya indirilen asset kullanılmaz.
"""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ICON_KINDS = ("play", "pause", "previous", "next", "fullscreen")


def _triangle(width, height, offset_x=0.0, pointing_right=True):
    path = QPainterPath()
    if pointing_right:
        path.moveTo(QPointF(offset_x, 0.0))
        path.lineTo(QPointF(offset_x + width, height / 2.0))
        path.lineTo(QPointF(offset_x, height))
    else:
        path.moveTo(QPointF(offset_x + width, 0.0))
        path.lineTo(QPointF(offset_x, height / 2.0))
        path.lineTo(QPointF(offset_x + width, height))
    path.closeSubpath()
    return path


def _draw_play(painter, size, colour):
    width = size * 0.34
    height = size * 0.42
    painter.translate((size - width) / 2.0 + size * 0.03, (size - height) / 2.0)
    painter.fillPath(_triangle(width, height), colour)


def _draw_pause(painter, size, colour):
    bar_width = size * 0.12
    height = size * 0.42
    gap = size * 0.12
    top = (size - height) / 2.0
    left = (size - (bar_width * 2 + gap)) / 2.0
    radius = bar_width / 2.5
    for index in range(2):
        x = left + index * (bar_width + gap)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, top, bar_width, height), radius, radius)
        painter.fillPath(path, colour)


def _draw_skip(painter, size, colour, forward):
    height = size * 0.40
    triangle_width = size * 0.30
    bar_width = size * 0.09
    total = triangle_width + bar_width + size * 0.04
    top = (size - height) / 2.0
    left = (size - total) / 2.0
    painter.translate(0.0, top)
    if forward:
        painter.fillPath(_triangle(triangle_width, height, left, True), colour)
        bar_x = left + triangle_width + size * 0.04
    else:
        bar_x = left
        painter.fillPath(
            _triangle(triangle_width, height, left + bar_width + size * 0.04, False),
            colour)
    path = QPainterPath()
    path.addRoundedRect(QRectF(bar_x, 0.0, bar_width, height),
                        bar_width / 2.5, bar_width / 2.5)
    painter.fillPath(path, colour)


def _draw_fullscreen(painter, size, colour):
    pen = QPen(colour)
    pen.setWidthF(max(1.4, size * 0.075))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    inset = size * 0.24
    arm = size * 0.16
    left, top = inset, inset
    right, bottom = size - inset, size - inset
    for x, y, dx, dy in (
        (left, top, 1, 1),
        (right, top, -1, 1),
        (left, bottom, 1, -1),
        (right, bottom, -1, -1),
    ):
        painter.drawLine(QPointF(x, y), QPointF(x + arm * dx, y))
        painter.drawLine(QPointF(x, y), QPointF(x, y + arm * dy))


_PAINTERS = {
    "play": _draw_play,
    "pause": _draw_pause,
    "previous": lambda p, s, c: _draw_skip(p, s, c, forward=False),
    "next": lambda p, s, c: _draw_skip(p, s, c, forward=True),
    "fullscreen": _draw_fullscreen,
}


def make_media_pixmap(kind, size=24, colour="#FFFFFF"):
    if kind not in _PAINTERS:
        raise ValueError(f"Bilinmeyen ikon türü: {kind}")
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        _PAINTERS[kind](painter, float(size), QColor(colour))
    finally:
        painter.end()
    return pixmap


def make_media_icon(kind, size=24, colour="#FFFFFF"):
    """Verilen türde sade, tek renkli bir medya ikonu üretir."""
    return QIcon(make_media_pixmap(kind, size, colour))
