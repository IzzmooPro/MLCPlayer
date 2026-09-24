# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Açılamayan dosya için hata penceresi bir kez açılmalı.

Hata penceresi modal `exec()` ile açılır; modal döngü sürerken 100 ms'lik
`update_ui` timer'ı çalışmaya devam eder. Koşul pencere kapanana kadar
doğru kaldığından her tik yeni bir pencere daha açıyordu.
"""

import time

from app import player as player_module
from app.player import MPVPlayer

from tests.test_overlay_integration_regressions import make_product_window


def test_open_failure_dialog_is_not_reopened_by_timer_ticks(monkeypatch, tmp_path):
    app, window, _frame = make_product_window(monkeypatch, tmp_path)
    # Gerçek `MPVPlayer.__init__` varsayılanları (update_ui'nin okuduğu).
    for name, value in (("_title_bar_raise_pending", False),
                        ("_eof_rewound", False), ("loop_file", False),
                        ("loop_playlist", False), ("shuffle", False),
                        ("_shuffle_signature", ()), ("_shuffle_order", []),
                        ("_shuffle_cursor", -1), ("_url_loading_active", False),
                        ("_url_loading_started_at", 0.0)):
        setattr(window, name, value)
    window.current_file = "bozuk.mkv"
    window.duration = 0
    window._core_idle = True
    window._load_started_at = time.time() - 10
    shown = []

    def modal_error(*_args, **_kwargs):
        shown.append(True)
        if len(shown) < 5:
            # Modal döngü içindeki timer tikini taklit eder.
            MPVPlayer.update_ui(window)

    monkeypatch.setattr(player_module, "show_user_error", modal_error)
    errors = []
    monkeypatch.setattr(player_module, "safe_console", errors.append)
    try:
        MPVPlayer.update_ui(window)
        assert errors == []
        assert len(shown) == 1
        # Pencere kapandıktan sonra durum sıfırlandı; yeni tik tekrar açmaz.
        MPVPlayer.update_ui(window)
        assert len(shown) == 1
    finally:
        window.close()
        app.processEvents()
