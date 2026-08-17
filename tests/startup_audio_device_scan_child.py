# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Baslangic ses cikisi taramasinin KALICI davranis olcumu (ayri surec).

Neden ayri surec
----------------
Olcum gercek `MPVPlayer` constructor akisini ve gercek libmpv yasam
dongusunu gerektirir. Native MPV `wid` yuzeyi izole edilsin ve pytest
surecine sizmasin diye child surecte kosar.

GUVENLIK
--------
- QSettings gecici dizine yonlendirilir; kullanicinin gercek ayarlarina
  DOKUNULMAZ.
- Harici uygulama acilmaz; yalniz bu surec kendini kapatir.
- Kapanis TEK sahipli sira ile yapilir (`service.shutdown_player`).

Ciktilar:
    STARTUP_SCAN_COUNT=<n>
    AFTER_MAIN_MENU_COUNT=<n>
    AFTER_CONTEXT_MENU_COUNT=<n>
    RESULTS: failures=...
"""
import os
import shutil
import sys
import tempfile

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]
# MPV native `wid` yuzeyi GERCEK pencere ister.
os.environ.pop("QT_QPA_PLATFORM", None)

WORKSPACE = tempfile.mkdtemp(prefix="mlc-audio-scan-")
failures = []

from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMenu  # noqa: E402

from app import menu_actions  # noqa: E402
from app import subtitle_service as service  # noqa: E402


def mark(name, value):
    print(f"{name}={value}", flush=True)


def main():
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      WORKSPACE)

    # DAVRANISSAL spy: gercek tarama fonksiyonu sayilir (kaynak metni degil).
    scans = {"n": 0}
    real_detect = menu_actions.detect_audio_devices

    def counting_detect(player):
        scans["n"] += 1
        return real_detect(player)

    menu_actions.detect_audio_devices = counting_detect
    # `refresh_audio_devices` modul icinden cagrildigi icin yamalanmis adi
    # gormesi adina yeniden tanimlanir.
    real_refresh = menu_actions.refresh_audio_devices

    def counting_refresh(player):
        counting_detect(player)
        menu_actions.populate_audio_device_menu(player,
                                                player.audio_device_menu)

    menu_actions.refresh_audio_devices = counting_refresh

    from app import player as player_module  # noqa: E402

    player_module.refresh_audio_devices = counting_refresh

    from app.player import MPVPlayer  # noqa: E402

    app = QApplication([sys.argv[0]])
    player = MPVPlayer()
    player.show()
    app.processEvents()

    mark("STARTUP_SCAN_COUNT", scans["n"])
    if scans["n"] != 1:
        failures.append(f"startup_scan={scans['n']}")

    try:
        # Ana menu ses cikisi listesine IKI kez eris
        for _ in range(2):
            menu_actions.populate_audio_device_menu(player, QMenu())
            app.processEvents()
        mark("AFTER_MAIN_MENU_COUNT", scans["n"])
        if scans["n"] != 1:
            failures.append(f"after_main_menu={scans['n']}")

        # Sag-tik menusunu IKI kez olustur
        frame = player.video_frame
        for _ in range(2):
            frame.build_context_menu()
            app.processEvents()
        mark("AFTER_CONTEXT_MENU_COUNT", scans["n"])
        if scans["n"] != 1:
            failures.append(f"after_context_menu={scans['n']}")
    finally:
        menu_actions.detect_audio_devices = real_detect
        menu_actions.refresh_audio_devices = real_refresh
        # Kapanis asamalari AYRI marker'larla; aralikli native cokme
        # gorulurse hangi asamada oldugu tabloda okunabilsin.
        mark("MARK_SHUTDOWN", "before")
        try:
            service.shutdown_player(player)
        except Exception as exc:
            print(f"CLOSE_WARNING {exc}", flush=True)
        mark("MARK_SHUTDOWN", "after")
        app.processEvents()
        mark("MARK_EVENTS", "after")
        shutil.rmtree(WORKSPACE, ignore_errors=True)
        mark("MARK_CLEANUP", "after")

    print(f"RESULTS: failures={','.join(failures) or 'none'}", flush=True)

    # Qt/MPV nesnelerinin yok edilme SIRASI burada acikca sahiplenilir.
    # Yorumlayici cikisinda rastgele siraya birakilirsa native yuzey ile
    # QApplication birbirini bekleyebiliyor. Crash gizlenmez: bu asamada
    # olusursa marker eksik kalir ve exit code non-zero olur.
    player.deleteLater()
    app.processEvents()
    mark("MARK_DELETE_LATER", "after")
    app.quit()
    mark("MARK_QUIT", "after")
    return 1 if failures else 0


EXIT_CODE = main()
mark("MARK_MAIN_RETURNED", EXIT_CODE)
raise SystemExit(EXIT_CODE)
