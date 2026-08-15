"""Opt-in CANLI urun smoke'u: gercek koordinator + gercek dialog + gercek API.

    $env:MLC_OPENSUBTITLES_LIVE='1'
    python tests/subtitle_center_live_smoke_child.py

Indirme dugmelerine BASILMAZ (kota tuketmez). Gercek indirme sozlesmesi icin
`opensubtitles_live_contract_child.py --download izni` kullanilir.

GUVENLIK
--------
- Sabit, kamusal sentetik sorgu: "The Matrix" / tr.
- Kullanicinin video adi, yolu veya hash'i SERVISE GITMEZ. Yer tutucu medya
  benzersiz %TEMP% icindedir ve hash esiginin (128 KiB) ALTINDA tutulur;
  boylece plana hash adimi hic girmez.
- Kimlik bilgileri READ-ONLY okunur; hicbir secret yazdirilmaz.
- Gercek MPVPlayer acilmaz; MPV'ye uygulama yapilmaz.
"""
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

if os.environ.get("MLC_OPENSUBTITLES_LIVE") != "1":
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from app import opensubtitles as osub  # noqa: E402
from app.subtitle_center_composition import (  # noqa: E402
    SubtitleCenterCoordinator)
from app.subtitle_settings import SubtitleSettingsStore  # noqa: E402

# Hash esiginin ALTINDA: plana hash adimi girmesin.
PLACEHOLDER_NAME = "The.Matrix.1999.1080p.mkv"
PLACEHOLDER_BYTES = 4 * 1024
failures = []


def mark(name, value=""):
    print(f"{name}={value}" if value != "" else name, flush=True)


class StubVideoFrame:
    def show_osd(self, text, duration=1200):
        pass

    def _update_overlay_subtitle_state(self):
        pass


class StubPlayer(QMainWindow):
    def __init__(self, current_file):
        super().__init__()
        self.current_file = current_file
        self.video_frame = StubVideoFrame()
        self.mpv_player = SimpleNamespace(
            track_list=[], sid="no", sub_visibility=False,
            sub_add=lambda p, *a: None, sub_remove=lambda s: None)


def pump_until(app, predicate, timeout_ms=30000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def main():
    store = SubtitleSettingsStore()
    # READ-ONLY: `load_api_key()` legacy gocunu tetikleyip kullanici
    # ayarlarina yazabilir; harness bunu yapmaz.
    try:
        api_key = store.credentials.get_api_key() or ""
    except Exception:
        api_key = ""
    mark("LIVE_OPT_IN", "True")
    mark("LIVE_CREDENTIALS_AVAILABLE", str(bool(api_key)))
    if not api_key:
        mark("LIVE_UI_SEARCH", "SKIPPED_NO_API_KEY")
        mark("LIVE_SECRET_LEAK", "False")
        mark("LIVE_EXIT", "0")
        return 0

    workspace = tempfile.mkdtemp(prefix="mlc-live-ui-")
    placeholder = os.path.join(workspace, PLACEHOLDER_NAME)
    with open(placeholder, "wb") as handle:
        handle.write(b"\0" * PLACEHOLDER_BYTES)

    app = QApplication([sys.argv[0]])
    player = StubPlayer(placeholder)
    coordinator = SubtitleCenterCoordinator(player, settings_store=store)
    player._subtitle_center = coordinator
    try:
        opened = coordinator.open()
        dialog = coordinator.dialog
        mark("LIVE_DIALOG_OPEN", str(bool(opened and dialog)))
        if dialog is None:
            failures.append("dialog_not_opened")
            return 1

        # SABIT sentetik sorgu; kullanici medyasi kullanilmaz.
        dialog.title_field.setText("The Matrix")
        dialog.language_box.setCurrentText("Türkçe")

        ticks = {"n": 0}
        timer = QTimer()
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
        timer.start()
        started = time.monotonic()
        dialog.search_button.click()
        settled = pump_until(app, lambda: coordinator.is_idle(), 30000)
        elapsed = time.monotonic() - started
        timer.stop()

        cards = dialog.result_cards()
        status = dialog.status_text()
        mark("LIVE_UI_SEARCH_SETTLED", str(settled))
        mark("LIVE_UI_RESULT_COUNT", str(len(cards)))
        mark("LIVE_UI_TICKS", str(ticks["n"]))
        mark("LIVE_UI_ELAPSED_S", f"{elapsed:.1f}")
        if api_key in status:
            failures.append("secret_in_status")
            status = "<redacted>"
        mark("LIVE_UI_STATUS_SAFE", str(api_key not in status))
        if not settled:
            failures.append("search_did_not_settle")
        if ticks["n"] <= 3:
            failures.append("ui_frozen_during_live_search")
        # Sonuc bulunmamasi HATA DEGILDIR; sema/akis dogrulanir.
        mark("LIVE_UI_HAS_RESULTS", str(bool(cards)))

        # Indirme dugmelerine BASILMAZ: kota tuketilmez.
        mark("LIVE_UI_DOWNLOAD", "SKIPPED_NOT_AUTHORIZED")

        dialog.close()
        drained = pump_until(app, lambda: coordinator.is_fully_drained(), 20000)
        mark("LIVE_UI_DRAINED", str(drained))
        if not drained:
            failures.append("worker_not_drained")
    finally:
        coordinator.shutdown(wait_ms=8000)
        try:
            player.close()
        except RuntimeError:
            pass
        app.processEvents()
        shutil.rmtree(workspace, ignore_errors=True)
        mark("LIVE_TEMP_CLEANED", str(not os.path.exists(workspace)))

    mark("LIVE_SECRET_LEAK", str(any(f.startswith("secret_in_")
                                     for f in failures)))
    if failures:
        mark("LIVE_FAILURES", ",".join(sorted(set(failures))))
    code = 1 if failures else 0
    mark("LIVE_EXIT", str(code))
    return code


raise SystemExit(main())
