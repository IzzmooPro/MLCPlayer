import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from app.playlist_panel import PlaylistRow
from app.thumbnail_service import (ThumbnailService, build_worker_command,
                                   thumbnail_cache_path)


def test_thumbnail_cache_key_tracks_file_identity_and_metadata(tmp_path):
    media = tmp_path / "clip.mkv"
    media.write_bytes(b"first")
    first = thumbnail_cache_path(str(media), str(tmp_path / "cache"))
    media.write_bytes(b"changed and larger")
    second = thumbnail_cache_path(str(media), str(tmp_path / "cache"))

    assert first != second
    assert os.path.commonpath([first, str(tmp_path / "cache")]) == str(
        tmp_path / "cache")


def test_worker_command_is_source_and_frozen_safe(monkeypatch, tmp_path):
    source_program, source_args = build_worker_command("in.mkv", "out.jpg")
    assert source_program == sys.executable
    assert source_args[0].endswith("main.py")
    assert source_args[1:] == ["--thumbnail-worker", "in.mkv", "out.jpg"]

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    frozen_program, frozen_args = build_worker_command("in.mkv", "out.jpg")
    assert frozen_program == sys.executable
    assert frozen_args == ["--thumbnail-worker", "in.mkv", "out.jpg"]


def test_row_renders_cached_real_frame_without_play_overlay(tmp_path):
    app = QApplication.instance() or QApplication([])
    image_path = tmp_path / "frame.jpg"
    image = QImage(160, 90, QImage.Format.Format_RGB32)
    image.fill(QColor("#3A7EA5"))
    assert image.save(str(image_path), "JPG")
    row = PlaylistRow(str(tmp_path / "clip.mkv"), True)

    assert row.set_thumbnail(str(image_path))

    pixmap = row.thumbnail_label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    assert pixmap.size() == QSize(82, 50)
    assert row.thumbnail_label.property("thumbnailState") == "ready"
    assert row.findChild(type(row.thumbnail_label), "playlistPlayingIndicator") is None
    row.deleteLater()
    app.processEvents()


def test_thumbnail_service_rejects_urls_and_missing_files(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ThumbnailService(cache_dir=str(tmp_path / "cache"))

    assert service.request("https://example.com/video.mp4") is None
    assert service.request(str(tmp_path / "missing.mkv")) is None
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"not-a-video")
    assert service.request(str(audio)) is None
    assert service.pending_paths == ()
    service.close()
    app.processEvents()
