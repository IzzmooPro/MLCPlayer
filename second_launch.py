# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only

import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, 'C:\\Users\\Universe\\Desktop\\Programlar TEST\\2026 YENİLER\\MLC Player')
from PyQt6.QtWidgets import QApplication
from app.single_instance import SingleInstanceGuard
app = QApplication([])
guard = SingleInstanceGuard('MLCProbe-b84de3fadbaf4a67be999f9ee1759940')
print("PRIMARY" if guard.acquire('I:\\film.mkv') else "SECONDARY")
