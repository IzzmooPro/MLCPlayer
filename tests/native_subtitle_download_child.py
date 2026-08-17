# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""GERÇEK Windows penceresiyle altyazı indirme kabulü.

Ölçülen ürün akışı:

  gerçek `QMainWindow` + gerçek `SubtitleCenterDialog` +
  gerçek `SubtitleDownloadController`
  → geçici klasörde `Ornek Film.mkv` ve ÖNCEDEN VAR OLAN `Ornek Film.srt`
  → tek düğme ("İndir ve Uygula")
  → onay penceresi ÇIKMADAN atomik değişim
  → MPV'ye KESİN hedef yolun uygulanması
  → geçersiz indirmede eski içeriğin korunması
  → pencere kapanırken QThread hatası olmaması

KAPSAM SINIRI (dürüstlük): ağ istemcisi deterministik yerel bir sahtedir
(gerçek OpenSubtitles API anahtarı gerekmez) ve MPV yerine çağrıları
kaydeden bir nesne kullanılır. Ölçülen şey ÜRÜN AKIŞI ve GERÇEK Qt
pencere davranışıdır; gerçek libmpv altyazı görüntüsü bu child'ın
kapsamında DEĞİLDİR.

Çalıştırma:

    set MLC_DIALOG_REAL_PLATFORM=1
    python tests\\native_subtitle_download_child.py
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Gerçek Windows platformu şarttır; offscreen çalıştırma kabul sayılmaz.
if os.environ.get("MLC_DIALOG_REAL_PLATFORM") != "1":
    print("SKIP: MLC_DIALOG_REAL_PLATFORM=1 gerekir")
    raise SystemExit(0)
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import QEvent, QObject, QTimer                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMainWindow,    # noqa: E402
                             QMessageBox)

from app.subtitle_center import SubtitleCenterDialog                # noqa: E402
from app.subtitle_download_controller import (                      # noqa: E402
    SubtitleDownloadController)

VIDEO_NAME = "Ornek Film.mkv"
TARGET_NAME = "Ornek Film.srt"
OLD = b"1\n00:00:09,000 --> 00:00:11,000\nESKI ICERIK\n"
NEW = b"1\n00:00:01,000 --> 00:00:04,000\nYENI ICERIK\n"
BAD = b"<html><body>403 Forbidden</body></html>"
RESULT = {"file_id": 4242, "name": "Uzak.Ad",
          "file_name": "BAMBASKA.turkish.HI.srt", "language": "Türkçe",
          "format": "srt", "moviehash_match": True, "downloads": 5,
          "ratings": 8.0, "hearing_impaired": False}


class LocalClient:
    """Deterministik yerel istemci: ağ YOK, API anahtarı YOK."""

    def __init__(self, payload):
        self.payload = payload

    def download_link(self, file_id):
        return "https://dl.opensubtitles.com/download/deterministik.srt"

    def fetch(self, url):
        return self.payload


class RecordingMpv:
    """MPV yerine geçen kayıt nesnesi (gerçek libmpv KULLANILMAZ)."""

    def __init__(self):
        self.track_list = [{"type": "sub", "id": 1, "selected": False}]
        self.sid = "no"
        self.sub_visibility = False
        self.applied = []
        self._next = 2

    def sub_add(self, path, *args):
        self.applied.append(path)
        self.track_list.append({"type": "sub", "id": self._next,
                                "external-filename": path, "selected": False})
        self._next += 1

    def sub_remove(self, sid):
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


class DialogSpy(QObject):
    """GÖSTERİLEN her yeni pencereyi sayar (onay penceresi kaçmasın)."""

    def __init__(self, allowed):
        super().__init__()
        self.allowed = allowed
        self.extra = []

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            if isinstance(obj, (QDialog, QMessageBox)) and obj not in self.allowed:
                self.extra.append(type(obj).__name__)
        return False


class Player:
    def __init__(self, mpv):
        self.mpv_player = mpv
        self.video_frame = None


def pump(app, predicate, timeout_ms=8000):
    waited = 0
    while waited < timeout_ms:
        app.processEvents()
        if predicate():
            return True
        app.thread().msleep(10)
        waited += 10
    app.processEvents()
    return predicate()


def run_case(app, folder, payload, spy_holder):
    """Tek indirme turu; gerçek pencere açılır ve kapatılır."""
    video = os.path.join(folder, VIDEO_NAME)
    target = os.path.join(folder, TARGET_NAME)
    media = {"file_name": video, "title": "Ornek Film", "season": None,
             "episode": None, "is_series": False, "target_name": TARGET_NAME,
             "movie_hash": "", "file_size": 0}

    window = QMainWindow()
    window.resize(900, 600)
    window.show()
    dialog = SubtitleCenterDialog(window, media=media)
    dialog.show()
    spy = DialogSpy(allowed={dialog})
    app.installEventFilter(spy)
    spy_holder.append(spy)

    mpv = RecordingMpv()
    controller = SubtitleDownloadController(
        dialog, client=LocalClient(payload), player=Player(mpv), owner=window)
    dialog.show_results([RESULT])
    dialog.select_result(dialog.result_cards()[0])
    app.processEvents()

    # GERÇEK düğme tıklaması (doğrudan metot çağrısı değil).
    dialog.apply_button.click()
    finished = pump(app, lambda: controller.is_idle()
                    and not controller.is_applying())

    dialog.close()
    window.close()
    app.processEvents()
    closed_cleanly = controller.shutdown(wait_ms=5000)
    app.removeEventFilter(spy)
    dialog.deleteLater()
    window.deleteLater()
    app.processEvents()

    return {
        "finished": bool(finished),
        "closed_cleanly": bool(closed_cleanly),
        "applied": list(mpv.applied),
        "status": dialog.status_text() if finished else "",
        "target": target,
        "extra_dialogs": list(spy.extra),
    }


def main():
    app = QApplication(sys.argv)
    folder = tempfile.mkdtemp(prefix="mlc-native-sub-")
    report = {"checks": [], "problems": []}
    spies = []

    def check(name, ok, detail=""):
        report["checks"].append({"name": name, "ok": bool(ok),
                                 "detail": str(detail)})
        if not ok:
            report["problems"].append(name)

    try:
        with open(os.path.join(folder, VIDEO_NAME), "wb") as handle:
            handle.write(b"sahte video")
        target = os.path.join(folder, TARGET_NAME)
        with open(target, "wb") as handle:
            handle.write(OLD)

        # 1) Geçerli indirme: onaysız, atomik, uygulanmış.
        good = run_case(app, folder, NEW, spies)
        with open(target, "rb") as handle:
            content = handle.read()
        entries = sorted(os.listdir(folder))

        check("download_finished", good["finished"])
        check("no_confirmation_dialog", good["extra_dialogs"] == [],
              good["extra_dialogs"])
        check("content_replaced", content == NEW, len(content))
        check("only_one_subtitle_file",
              [n for n in entries if n.endswith(".srt")] == [TARGET_NAME],
              entries)
        check("no_temporary_leftovers",
              [n for n in entries if n.startswith(".mlc-sub-")] == [], entries)
        check("exact_path_applied",
              [os.path.normcase(p) for p in good["applied"]]
              == [os.path.normcase(target)], good["applied"])
        check("status_reports_applied", "uygulandı" in good["status"].lower(),
              good["status"])
        check("thread_closed_cleanly", good["closed_cleanly"])

        # 2) Geçersiz indirme: eski (artık YENİ) içerik byte-for-byte kalır.
        bad = run_case(app, folder, BAD, spies)
        with open(target, "rb") as handle:
            after_bad = handle.read()
        check("invalid_download_preserves_file", after_bad == NEW,
              len(after_bad))
        check("invalid_download_no_confirmation", bad["extra_dialogs"] == [],
              bad["extra_dialogs"])
        check("invalid_download_thread_closed", bad["closed_cleanly"])
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    report["ok"] = not report["problems"]
    print("REPORT " + json.dumps(report, ensure_ascii=False))
    print("MARK_DONE")
    # `os._exit()` tamponu BOŞALTMAZ; rapor açıkça diske yazılır.
    sys.stdout.flush()
    sys.stderr.flush()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    # Ürünün çıkış politikası: yorumlayıcı finalizasyonuna girilmez.
    QTimer.singleShot(0, lambda: None)
    os._exit(main())
