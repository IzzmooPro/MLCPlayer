# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
from PyQt6.QtGui import QIcon, QPainter

# Simgelerin rengini değiştirmek için yardımcı fonksiyon
def create_colored_icon(icon, color):
    pixmap = icon.pixmap(24, 24)
    if pixmap.isNull():
        return icon
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return QIcon(pixmap)

# Zaman dönüştürme yardımcıları
def format_time(seconds):
    """Saniye cinsinden zamanı MM:SS (1 saatten kısaysa) veya HH:MM:SS formatına dönüştürür"""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def time_to_seconds(time_str):
    """MM:SS veya HH:MM:SS formatındaki zamanı saniyeye dönüştürür"""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 2:
            minutes, seconds = (int(part) for part in parts)
            if minutes < 0 or not 0 <= seconds < 60:
                return None
            return minutes * 60 + seconds
        elif len(parts) == 3:
            hours, minutes, seconds = (int(part) for part in parts)
            if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
                return None
            return hours * 3600 + minutes * 60 + seconds
        return None
    except (ValueError, IndexError):
        return None
