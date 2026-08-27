# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Pytest sureci tek, guclu sahipli QApplication kullanir."""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


def test_the_session_keeps_qapplication_alive_after_local_references_drop():
    """Function fixture referansi dusse de Qt uygulamasi yok edilmemeli."""
    app = QApplication.instance() or QApplication([])
    assert QApplication.instance() is app

    del app
    gc.collect()

    assert QApplication.instance() is not None
