# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""QPainter tabanlı, küçük ve yeniden kullanılabilir medya ikonları.

Windows tema ikonlarına bağımlı kalmamak için sade beyaz glifleri doğrudan
çizeriz. Harici ikon paketi veya indirilen asset kullanılmaz.
"""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ICON_KINDS = ("play", "pause", "previous", "next", "fullscreen",
              "subtitles", "volume", "volume_muted", "settings",
              "open_folder", "playlist", "more", "minimize",
              "maximize", "restore", "close")


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
    width = size * 0.38
    height = size * 0.48
    painter.translate((size - width) / 2.0 + size * 0.03, (size - height) / 2.0)
    painter.fillPath(_triangle(width, height), colour)


def _draw_pause(painter, size, colour):
    bar_width = size * 0.14
    height = size * 0.48
    gap = size * 0.11
    top = (size - height) / 2.0
    left = (size - (bar_width * 2 + gap)) / 2.0
    radius = bar_width / 2.5
    for index in range(2):
        x = left + index * (bar_width + gap)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, top, bar_width, height), radius, radius)
        painter.fillPath(path, colour)


def _draw_skip(painter, size, colour, forward):
    height = size * 0.48
    triangle_width = size * 0.34
    bar_width = size * 0.11
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


def _draw_subtitles(painter, size, colour):
    """Referanstaki gibi ince beyaz çerçeve içinde CC."""
    pen = QPen(colour)
    pen.setWidthF(max(1.1, size * 0.055))
    painter.setPen(pen)
    inset = size * 0.14
    rect = QRectF(inset, inset + size * 0.06,
                  size - inset * 2, size - inset * 2 - size * 0.12)
    painter.drawRoundedRect(rect, size * 0.09, size * 0.09)

    font = painter.font()
    font.setPixelSize(max(6, int(size * 0.42)))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "CC")


def _speaker_path(size):
    path = QPainterPath()
    body_h = size * 0.26
    body_w = size * 0.16
    left = size * 0.16
    top = (size - body_h) / 2.0
    path.addRect(QRectF(left, top, body_w, body_h))
    cone = QPainterPath()
    cone.moveTo(QPointF(left + body_w, top - size * 0.06))
    cone.lineTo(QPointF(left + body_w + size * 0.20, top - size * 0.14))
    cone.lineTo(QPointF(left + body_w + size * 0.20, top + body_h + size * 0.14))
    cone.lineTo(QPointF(left + body_w, top + body_h + size * 0.06))
    cone.closeSubpath()
    return path.united(cone)


def _draw_volume(painter, size, colour):
    painter.fillPath(_speaker_path(size), colour)
    pen = QPen(colour)
    pen.setWidthF(max(1.1, size * 0.055))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    centre_y = size / 2.0
    for index, radius in enumerate((size * 0.14, size * 0.24)):
        rect = QRectF(size * 0.56 - radius + index * size * 0.02,
                      centre_y - radius, radius * 2, radius * 2)
        painter.drawArc(rect, -55 * 16, 110 * 16)


def _draw_volume_muted(painter, size, colour):
    painter.fillPath(_speaker_path(size), colour)
    pen = QPen(colour)
    pen.setWidthF(max(1.2, size * 0.065))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    left = size * 0.60
    right = size * 0.86
    top = size * 0.36
    bottom = size * 0.64
    painter.drawLine(QPointF(left, top), QPointF(right, bottom))
    painter.drawLine(QPointF(right, top), QPointF(left, bottom))


def _draw_settings(painter, size, colour):
    """Sade dişli: dış dişler + orta halka."""
    centre = size / 2.0
    outer = size * 0.36
    inner = size * 0.22
    tooth = size * 0.09
    pen = QPen(colour)
    pen.setWidthF(max(1.2, size * 0.075))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    import math
    for index in range(8):
        angle = math.radians(index * 45.0)
        dx, dy = math.cos(angle), math.sin(angle)
        painter.drawLine(
            QPointF(centre + dx * (outer - tooth), centre + dy * (outer - tooth)),
            QPointF(centre + dx * outer, centre + dy * outer))
    painter.drawEllipse(QPointF(centre, centre), inner, inner)
    painter.drawEllipse(QPointF(centre, centre), size * 0.08, size * 0.08)



def _stroke_pen(painter, size, colour, weight=0.065):
    pen = QPen(colour)
    pen.setWidthF(max(1.1, size * weight))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    return pen


def _draw_open_folder(painter, size, colour):
    _stroke_pen(painter, size, colour)
    left, right = size * 0.14, size * 0.86
    top, bottom = size * 0.28, size * 0.76
    path = QPainterPath()
    path.moveTo(QPointF(left, bottom))
    path.lineTo(QPointF(left, top))
    path.lineTo(QPointF(left + size * 0.22, top))
    path.lineTo(QPointF(left + size * 0.30, top + size * 0.10))
    path.lineTo(QPointF(right, top + size * 0.10))
    painter.drawPath(path)
    painter.drawLine(QPointF(left, bottom), QPointF(right, bottom))
    painter.drawLine(QPointF(right, top + size * 0.10), QPointF(right, bottom))


def _draw_playlist(painter, size, colour):
    _stroke_pen(painter, size, colour)
    left, right = size * 0.16, size * 0.84
    for index in range(3):
        y = size * 0.30 + index * size * 0.20
        painter.drawLine(QPointF(left, y), QPointF(right, y))


def _draw_more(painter, size, colour):
    painter.setPen(Qt.PenStyle.NoPen)
    radius = size * 0.075
    for index in range(3):
        centre_y = size * 0.26 + index * size * 0.24
        path = QPainterPath()
        path.addEllipse(QPointF(size / 2.0, centre_y), radius, radius)
        painter.fillPath(path, colour)


def _draw_minimize(painter, size, colour):
    _stroke_pen(painter, size, colour, 0.055)
    painter.drawLine(QPointF(size * 0.22, size / 2.0),
                     QPointF(size * 0.78, size / 2.0))


def _draw_maximize(painter, size, colour):
    _stroke_pen(painter, size, colour, 0.055)
    inset = size * 0.24
    painter.drawRect(QRectF(inset, inset, size - inset * 2, size - inset * 2))


def _draw_restore(painter, size, colour):
    _stroke_pen(painter, size, colour, 0.055)
    inset = size * 0.20
    span = size * 0.44
    painter.drawRect(QRectF(inset, inset + size * 0.12, span, span))
    path = QPainterPath()
    path.moveTo(QPointF(inset + size * 0.12, inset + size * 0.12))
    path.lineTo(QPointF(inset + size * 0.12, inset))
    path.lineTo(QPointF(inset + span + size * 0.12, inset))
    path.lineTo(QPointF(inset + span + size * 0.12, inset + span))
    path.lineTo(QPointF(inset + span, inset + span))
    painter.drawPath(path)


def _draw_close(painter, size, colour):
    _stroke_pen(painter, size, colour, 0.055)
    left, right = size * 0.26, size * 0.74
    painter.drawLine(QPointF(left, left), QPointF(right, right))
    painter.drawLine(QPointF(right, left), QPointF(left, right))


_PAINTERS = {
    "play": _draw_play,
    "pause": _draw_pause,
    "previous": lambda p, s, c: _draw_skip(p, s, c, forward=False),
    "next": lambda p, s, c: _draw_skip(p, s, c, forward=True),
    "fullscreen": _draw_fullscreen,
    "subtitles": _draw_subtitles,
    "volume": _draw_volume,
    "volume_muted": _draw_volume_muted,
    "settings": _draw_settings,
    "open_folder": _draw_open_folder,
    "playlist": _draw_playlist,
    "more": _draw_more,
    "minimize": _draw_minimize,
    "maximize": _draw_maximize,
    "restore": _draw_restore,
    "close": _draw_close,
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
