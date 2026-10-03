# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Worker süreci BAŞLAYAMAZSA kuyruk takılmamalı.

`QProcess` başlatılamadığında `finished` GÖNDERMEZ, yalnız
`errorOccurred(FailedToStart)` gönderir. `_current` temizlenmediği ve
zaman aşımı "çalışmıyor" süreçte hiçbir şey yapmadığı için bütün küçük
resim kuyruğu kalıcı olarak `loading` durumunda kalıyordu.
"""

import time

from PyQt6.QtWidgets import QApplication

from app import thumbnail_service


def test_failed_start_reports_failure_and_continues(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    missing = str(tmp_path / "yok" / "worker.exe")
    monkeypatch.setattr(thumbnail_service, "build_worker_command",
                        lambda media, output: (missing, []))
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    for path in (first, second):
        path.write_bytes(b"x" * 16)
    service = thumbnail_service.ThumbnailService(
        cache_dir=str(tmp_path / "cache"))
    failed = []
    service.thumbnail_failed.connect(failed.append)
    try:
        service.request(str(first))
        service.request(str(second))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(failed) < 2:
            app.processEvents()
            time.sleep(0.01)

        assert failed == [str(first), str(second)]
        assert service.pending_paths == ()
        assert service.status(str(first)) == "failed"
    finally:
        service.close()
