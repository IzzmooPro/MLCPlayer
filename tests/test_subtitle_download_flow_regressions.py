# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tek ve kesin altyazı indirme davranışı.

İstenen ürün sözleşmesi:

- Hedef her zaman `<video adı>.srt`, videonun KLASÖRÜNDE.
- Uzak dosya adı, dil eki, `.1`/`(1)` türevi ASLA kullanılmaz.
- Klasör, dosya adı veya ÜZERİNE YAZMA onayı SORULMAZ.
- Mevcut dosya yalnız DOĞRULANMIŞ yeni içerikle atomik değişir.
- Başarılı kayıttan sonra altyazı oynatılan videoya otomatik uygulanır.
- Ağ/doğrulama/yazma hatasında mevcut sağlam `.srt` bozulmaz.

Bu tur ayrıca işlevsiz `after_download` ayarını ve "Yalnızca İndir"
ikinci düğmesini kaldırır; eski QSettings değerleri hataya yol açmadan
YOK SAYILIR.

GERÇEK AĞA ÇIKILMAZ: fake client + tmp_path + fake MPV.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import (QApplication, QDialog, QFileDialog, QMainWindow,
                             QMessageBox)

from app import subtitle_service as service
from app.subtitle_center import SubtitleCenterDialog
from app.subtitle_download_controller import (STATUS_APPLIED, STATUS_PARTIAL,
                                              SubtitleDownloadController)

VIDEO_NAME = "Ornek Film.mkv"
TARGET_NAME = "Ornek Film.srt"
GOOD_URL = "https://dl.opensubtitles.com/download/abc.srt"
SRT_NEW = b"1\n00:00:01,000 --> 00:00:04,000\nYeni altyazi\n"
SRT_OLD = b"1\n00:00:09,000 --> 00:00:11,000\nEski altyazi\n"
HTML_ERROR = b"<html><body>403 Forbidden</body></html>"
RESULT = {"file_id": 4242, "name": "Uzak.Altyazi.Adi",
          # Uzak ad BİLEREK bambaşka; hedefi ETKİLEMEMELİ.
          "file_name": "BAMBASKA.turkish.HI.srt", "language": "Türkçe",
          "format": "srt", "moviehash_match": True, "downloads": 10,
          "ratings": 9.0, "hearing_impaired": False}


class FakeClient:
    def __init__(self, payload=SRT_NEW, link=GOOD_URL):
        self.payload = payload
        self.link = link
        self.download_calls = []

    def download_link(self, file_id):
        self.download_calls.append(file_id)
        return self.link

    def fetch(self, url):
        return self.payload


class FakeMpv:
    def __init__(self, fail_apply=False):
        self.track_list = [{"type": "sub", "id": 1, "selected": False}]
        self.sid = "no"
        self.sub_visibility = False
        self.added = []
        self.removed = []
        self._next = 2
        self._fail = fail_apply

    def sub_add(self, path, *args):
        if self._fail:
            raise RuntimeError("sentetik mpv hatasi")
        self.added.append(path)
        self.track_list.append({"type": "sub", "id": self._next,
                                "external-filename": path, "selected": False})
        self._next += 1

    def sub_remove(self, sid):
        self.removed.append(sid)
        self.track_list = [t for t in self.track_list if t.get("id") != sid]


@pytest.fixture
def bench(tmp_path):
    """Gerçek ürün pencereleri; kullanıcı klasörüne yazma YOK."""
    app = QApplication.instance() or QApplication([])
    created = []

    def factory(client=None, mpv=None, existing=None, video_name=VIDEO_NAME):
        video = tmp_path / video_name
        video.write_bytes(b"video")
        target = tmp_path / (os.path.splitext(video_name)[0] + ".srt")
        if existing is not None:
            target.write_bytes(existing)
        media = {
            "file_name": str(video), "title": "Ornek Film",
            "season": None, "episode": None, "is_series": False,
            "target_name": target.name, "movie_hash": "abc", "file_size": 5,
        }
        window = QMainWindow()
        window.show()
        dialog = SubtitleCenterDialog(window, media=media)
        dialog.show()
        mpv_obj = mpv if mpv is not None else FakeMpv()
        player = SimpleNamespace(mpv_player=mpv_obj, video_frame=None)
        controller = SubtitleDownloadController(
            dialog, client=client or FakeClient(), player=player, owner=window)
        dialog.show_results([RESULT])
        dialog.select_result(dialog.result_cards()[0])
        app.processEvents()
        created.append((window, dialog, controller))
        return SimpleNamespace(app=app, dialog=dialog, controller=controller,
                               mpv=mpv_obj, folder=tmp_path, target=target,
                               video=video)

    yield factory

    for window, dialog, controller in created:
        controller.shutdown(wait_ms=4000)
        for widget in (dialog, window):
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass
    (QApplication.instance() or QApplication([])).processEvents()


def run_download(bench_obj, timeout_ms=4000):
    """Tek ana eylemi çalıştırır ve iş bitene kadar olayları işler."""
    assert bench_obj.controller.download_and_apply() is True
    deadline = 0
    while deadline < timeout_ms:
        bench_obj.app.processEvents()
        if bench_obj.controller.is_idle() and not bench_obj.controller.is_applying():
            break
        QApplication.instance().thread().msleep(10)
        deadline += 10
    bench_obj.app.processEvents()


def temp_leftovers(folder):
    return [name for name in os.listdir(folder) if name.startswith(".mlc-sub-")]


# --- 1-3: kesin hedef yolu --------------------------------------------

def test_target_is_the_video_name_with_srt_in_the_same_folder():
    """`C:\\Video\\Film.mkv` → `C:\\Video\\Film.srt`."""
    video = os.path.join(os.sep + "Video", "Film.mkv")
    target = service.subtitle_target_path(video)

    assert os.path.basename(target) == "Film.srt"
    assert os.path.dirname(target) == os.path.dirname(os.path.abspath(video))


@pytest.mark.parametrize("video_name, expected", [
    ("Ornek Film.mkv", "Ornek Film.srt"),
    ("Film.2024.4K.HDR.mkv", "Film.2024.4K.HDR.srt"),
    ("Bir. Iki. Uc.mp4", "Bir. Iki. Uc.srt"),
    ("The Movie (2021) [1080p].avi", "The Movie (2021) [1080p].srt"),
])
def test_multi_dot_and_spaced_names_are_preserved(video_name, expected):
    """Çok noktalı ve boşluklu adlar birebir korunur."""
    target = service.subtitle_target_path(os.path.join("D:" + os.sep, "M",
                                                       video_name))
    assert os.path.basename(target) == expected


def test_remote_subtitle_name_never_changes_the_target(bench):
    """OpenSubtitles'ın verdiği ad hedefi DEĞİŞTİRMEZ."""
    b = bench()
    run_download(b)

    files = sorted(os.listdir(b.folder))
    assert TARGET_NAME in files
    assert "BAMBASKA.turkish.HI.srt" not in files
    assert not any(name.endswith(".tr.srt") for name in files)


# --- 4-5: hiçbir onay/seçim penceresi açılmaz -------------------------

def test_no_file_or_folder_dialog_is_ever_opened(bench, monkeypatch):
    """Klasör/dosya adı seçme penceresi HİÇ açılmaz."""
    opened = []
    for name in ("getSaveFileName", "getOpenFileName", "getExistingDirectory"):
        monkeypatch.setattr(QFileDialog, name,
                            staticmethod(lambda *a, **k: opened.append(name)))
    monkeypatch.setattr(QFileDialog, "exec",
                        lambda self: opened.append("exec") or 0)

    b = bench(existing=SRT_OLD)
    run_download(b)

    assert opened == []


def test_no_overwrite_confirmation_is_ever_created(bench, monkeypatch):
    """Mevcut `.srt` varken üzerine yazma onayı OLUŞTURULMAZ."""
    shown = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: shown.append("messagebox") or 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: shown.append("dialog") or 0)

    b = bench(existing=SRT_OLD)
    run_download(b)

    assert shown == []
    assert b.target.read_bytes() == SRT_NEW


def test_the_controller_has_no_overwrite_confirmation_hook(bench):
    """Onay geri çağrısı sözleşmeden tamamen KALKTI."""
    b = bench(existing=SRT_OLD)

    assert not hasattr(b.controller, "confirm_overwrite")


def test_the_overwrite_dialog_class_is_removed():
    """Kullanılmayan `OverwriteConfirmDialog` güvenle kaldırıldı."""
    from app import subtitle_center_composition as composition

    assert not hasattr(composition, "OverwriteConfirmDialog")


# --- 6-7: veri bütünlüğü ----------------------------------------------

def test_an_existing_subtitle_is_replaced_atomically(bench):
    """Mevcut `.srt` doğrulanmış yeni içerikle değişir; artık kalmaz."""
    b = bench(existing=SRT_OLD)
    assert b.target.read_bytes() == SRT_OLD

    run_download(b)

    assert b.target.read_bytes() == SRT_NEW
    assert temp_leftovers(b.folder) == [], "geçici dosya kalmamalı"


def test_an_invalid_download_leaves_the_existing_file_byte_for_byte(bench):
    """HTML hata gövdesi mevcut dosyanın ÜZERİNE YAZMAZ."""
    b = bench(client=FakeClient(payload=HTML_ERROR), existing=SRT_OLD)

    run_download(b)

    assert b.target.read_bytes() == SRT_OLD
    assert temp_leftovers(b.folder) == []


def test_an_empty_download_leaves_the_existing_file_untouched(bench):
    """Boş/yarım indirme de mevcut dosyayı bozmaz."""
    b = bench(client=FakeClient(payload=b""), existing=SRT_OLD)

    run_download(b)

    assert b.target.read_bytes() == SRT_OLD


def test_repeated_downloads_only_update_the_same_file(bench):
    """Tekrarlanan indirme türev dosya ÜRETMEZ."""
    b = bench(existing=SRT_OLD)
    run_download(b)
    run_download(b)
    run_download(b)

    subtitles = sorted(name for name in os.listdir(b.folder)
                       if name.endswith(".srt"))
    assert subtitles == [TARGET_NAME]
    assert b.target.read_bytes() == SRT_NEW


# --- 8-9: otomatik uygulama ve dürüst durum metni ---------------------

def test_the_subtitle_is_applied_automatically_after_a_successful_save(bench):
    """Başarılı indirmede altyazı KESİN hedef yoluyla uygulanır."""
    b = bench()
    run_download(b)

    assert b.mpv.added, "MPV'ye altyazı eklenmedi"
    assert os.path.normcase(b.mpv.added[-1]) == os.path.normcase(str(b.target))
    assert b.dialog.status_text() == STATUS_APPLIED


def test_a_failed_apply_still_reports_the_save_as_successful(bench):
    """Uygulama başarısızsa KAYDETME başarısı hata gibi gösterilmez."""
    b = bench(mpv=FakeMpv(fail_apply=True))
    run_download(b)

    assert b.target.read_bytes() == SRT_NEW, "dosya yine de kaydedilmeli"
    status = b.dialog.status_text()
    assert status == STATUS_PARTIAL
    assert "indirildi" in status.lower(), "kaydetme başarısı belirtilmeli"


# --- 10-12: sadeleşen arayüz ve eski ayarlar --------------------------

@pytest.mark.parametrize("legacy", ["apply", "download_only", "", "bozuk"])
def test_legacy_after_download_values_do_not_change_behaviour(tmp_path,
                                                              monkeypatch,
                                                              legacy):
    """Eski `after_download` değerleri TOLERE edilir, davranışı etkilemez."""
    from PyQt6.QtCore import QSettings

    from app.subtitle_settings import SubtitleSettingsStore

    path = str(tmp_path / "sentetik.ini")
    settings = QSettings(path, QSettings.Format.IniFormat)
    store = SubtitleSettingsStore(settings=settings)
    settings.setValue("subtitle/after_download", legacy)
    settings.sync()

    values = store.load()

    assert "after_download" not in values, "işlevsiz anahtar okunmamalı"
    assert set(values) == {"username", "language"}


def test_saving_settings_ignores_a_legacy_after_download_value(tmp_path):
    """Eski anahtar gönderilse bile kaydetme hata vermez."""
    from PyQt6.QtCore import QSettings

    from app.subtitle_settings import SubtitleSettingsStore

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    store = SubtitleSettingsStore(settings=settings)

    result = store.save({"username": "ali", "language": "tr",
                         "after_download": "download_only"})

    assert result.ok is True
    assert store.load()["username"] == "ali"


def test_the_settings_dialog_has_no_after_download_box(tmp_path):
    """Ayarlar penceresinde işlevsiz seçim kutusu YOK."""
    # NOT: dönüş DEĞERİ tutulmalıdır. Referanssız bırakılan yeni
    # QApplication Python tarafında toplanıyor ve sonraki widget
    # oluşturma yorumlayıcıyı 0xC0000409 ile düşürüyordu.
    app = QApplication.instance() or QApplication([])
    from app.subtitle_center_settings_dialog import (
        SubtitleCenterSettingsDialog)

    from PyQt6.QtWidgets import QComboBox

    media = {"file_name": str(tmp_path / VIDEO_NAME), "title": "Ornek Film",
             "target_name": TARGET_NAME, "movie_hash": "", "file_size": 0}
    # Sahiplik zinciri GERÇEK üründeki gibidir: pencere → merkez → ayarlar.
    # Sahipsiz (`parent=None`) merkez penceresiyle kurulan ayar penceresi
    # teardown sırasında yorumlayıcıyı düşürüyordu.
    window = QMainWindow()
    center = SubtitleCenterDialog(window, media=media)
    dialog = SubtitleCenterSettingsDialog(center)
    try:
        assert not hasattr(dialog, "after_download_box")
        items = []
        for box in dialog.findChildren(QComboBox):
            items.extend(box.itemText(i) for i in range(box.count()))
        assert "Yalnızca indir" not in items
        assert "İndir ve uygula" not in items
    finally:
        for widget in (dialog, center, window):
            widget.close()
        app.processEvents()


def test_the_result_actions_offer_a_single_download_behaviour(bench):
    """Sonuç kartında çelişkili İKİ indirme düğmesi yok."""
    b = bench()

    assert not hasattr(b.dialog, "download_button")
    assert b.dialog.apply_button.text() == "İndir ve Uygula"
    # NOT: Türkçe "İ" küçültülünce birleşik noktalı 'i̇' üretir; bu yüzden
    # eşleştirme küçük harfe çevirmeden, ortak gövdeyle yapılır.
    buttons = [w for w in b.dialog.findChildren(type(b.dialog.apply_button))
               if "ndir" in w.text()]
    assert len(buttons) == 1, [w.text() for w in buttons]


def test_the_controller_exposes_a_single_download_entry_point(bench):
    """`download_only` akışı kaldırıldı; tek giriş noktası kaldı."""
    b = bench()

    assert hasattr(b.controller, "download_and_apply")
    assert not hasattr(b.controller, "download_only")


# --- 14-15: güvenlik ve yaşam döngüsü ---------------------------------

def test_no_raw_path_or_secret_reaches_the_user_error_text(bench, tmp_path):
    """Ham yol/token kullanıcı metnine ULAŞMAZ."""
    class LeakyClient:
        def download_link(self, file_id):
            raise RuntimeError(
                f"api_key=SECRET123 Bearer TOKEN456 dosya {tmp_path}")

        def fetch(self, url):
            raise AssertionError("çağrılmamalı")

    b = bench(client=LeakyClient())
    run_download(b)

    text = b.dialog.status_text() or ""
    for secret in ("SECRET123", "TOKEN456", str(tmp_path)):
        assert secret not in text, f"sızıntı: {secret}"


def test_the_worker_thread_finishes_cleanly_and_shutdown_is_safe(bench):
    """QThread yaşam döngüsü ve kapanış güvenliği korunur."""
    b = bench()
    run_download(b)

    assert b.controller.is_idle()
    assert not b.controller.thread_is_running()
    assert b.controller.shutdown(wait_ms=4000) is True


def test_closing_the_dialog_during_a_download_does_not_crash(bench):
    """İndirme sürerken pencere kapanırsa kooperatif iptal çalışır."""
    b = bench()
    b.controller.download_and_apply()
    b.dialog.close()
    b.app.processEvents()

    assert b.controller.shutdown(wait_ms=4000) is True
    assert b.controller.is_cancelled()
