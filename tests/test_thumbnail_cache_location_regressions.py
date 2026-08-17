# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Kucuk resim onbellegi UYGULAMA KIMLIGINDEN bagimsiz olmali.

OLCULEN REGRESYON (kurulu surumde bildirildi):
`default_cache_dir()` yolu `QStandardPaths.CacheLocation` uzerinden
cozuyordu ve bu yol `applicationName`/`organizationName` degerlerine
BAGLIDIR. Ikon turunda uygulamaya `MLC Player` kimligi verilince onbellek
yolu degisti ve mevcut kayitlar OKSUZ kaldi:

    %LOCALAPPDATA%\\python\\cache\\thumbnails                 -> 193 dosya
    %LOCALAPPDATA%\\MLC Player\\MLC Player\\cache\\thumbnails ->   1 dosya

Sonuc TEK degisiklikten iki belirti uretti:
  1. Her playlist satiri icin worker aciliyor; worker AYNI EXE oldugu icin
     kullanici "cift MLC Player.exe" goruyor.
  2. Worker `hwdec="no"` ile yazilimsal decode yapip ayni buyuk dosyayi
     okudugu icin ana oynaticinin atlamalari gecikiyor (logda
     `Audio device underrun`).

SOZLESME: onbellek yolu SABITTIR; uygulama adi, organizasyon adi, frozen
olup olmama veya calistirma bicimi onu DEGISTIREMEZ. Eski Qt turevli
dizinler YALNIZ OKUMA icin taninir; oraya asla yazilmaz.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import app.thumbnail_service as service


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def stable_root():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.getcwd()),
                        "MLCPlayer", "cache", "thumbnails")


# =====================================================================
# 1. Yol KIMLIKTEN bagimsiz
# =====================================================================

def test_the_cache_dir_is_a_fixed_application_owned_path(qt_app):
    assert service.default_cache_dir() == stable_root()


def test_changing_the_application_identity_never_moves_the_cache(qt_app):
    """ASIL REGRESYON: `setApplicationName` onbellegi tasiyordu."""
    before = service.default_cache_dir()
    original = (qt_app.applicationName(), qt_app.organizationName())
    try:
        qt_app.setApplicationName("Bambaska Ad")
        qt_app.setOrganizationName("Bambaska Kurum")

        assert service.default_cache_dir() == before
    finally:
        qt_app.setApplicationName(original[0])
        qt_app.setOrganizationName(original[1])


def test_a_frozen_build_uses_the_same_cache_as_development(qt_app,
                                                           monkeypatch):
    development = service.default_cache_dir()
    monkeypatch.setattr(service.sys, "frozen", True, raising=False)
    monkeypatch.setattr(service.sys, "_MEIPASS", "C:\\paket", raising=False)

    assert service.default_cache_dir() == development


def test_the_write_path_no_longer_depends_on_qstandardpaths(monkeypatch):
    """DAVRANISSAL olcum: Qt yolu tamamen bozulsa bile yazma yolu ayni.

    (Metin taramasi yapilmaz; aciklama satirlari da `QStandardPaths`
    kelimesini icerdigi icin yaniltici olurdu.)
    """
    class Broken:
        class StandardLocation:
            CacheLocation = object()

        @staticmethod
        def writableLocation(_location):
            raise RuntimeError("Qt yolu okunamadi")

    monkeypatch.setattr(service, "QStandardPaths", Broken)

    assert service.default_cache_dir() == stable_root()


# =====================================================================
# 2. Eski dizinler YALNIZ OKUNUR
# =====================================================================

def test_a_legacy_cached_frame_is_reused_instead_of_respawning(qt_app,
                                                               tmp_path,
                                                               monkeypatch):
    media = tmp_path / "Film.mkv"
    media.write_bytes(b"0" * 2048)
    fresh = tmp_path / "yeni"
    legacy = tmp_path / "eski"
    fresh.mkdir()
    legacy.mkdir()
    monkeypatch.setattr(service, "legacy_cache_dirs", lambda: (str(legacy),))

    # Eski dizinde AYNI kimlikle uretilmis kare var.
    name = os.path.basename(service.thumbnail_cache_path(str(media),
                                                         str(fresh)))
    (legacy / name).write_bytes(b"JPEG")

    instance = service.ThumbnailService(cache_dir=str(fresh))
    try:
        found = instance.request(str(media))

        assert found == str(legacy / name), "eski kare yeniden kullanılmadı"
        assert instance.pending_paths == (), "gereksiz worker kuyruğa girdi"
    finally:
        instance.close()


def test_the_legacy_directory_is_never_written_to(qt_app, tmp_path,
                                                  monkeypatch):
    media = tmp_path / "Film.mkv"
    media.write_bytes(b"0" * 2048)
    fresh = tmp_path / "yeni"
    legacy = tmp_path / "eski"
    fresh.mkdir()
    legacy.mkdir()
    monkeypatch.setattr(service, "legacy_cache_dirs", lambda: (str(legacy),))

    instance = service.ThumbnailService(cache_dir=str(fresh))
    try:
        output = service.thumbnail_cache_path(str(media), instance.cache_dir)

        assert str(fresh) in output
        assert str(legacy) not in output
        # Kuyruk hedefi de HER ZAMAN yeni dizindir.
        instance.request(str(media))
        assert all(str(legacy) not in entry[1] for entry in instance._queue)
    finally:
        instance.close()


def test_a_missing_legacy_directory_is_harmless(qt_app, tmp_path,
                                                monkeypatch):
    media = tmp_path / "Film.mkv"
    media.write_bytes(b"0" * 2048)
    fresh = tmp_path / "yeni"
    fresh.mkdir()
    monkeypatch.setattr(service, "legacy_cache_dirs",
                        lambda: (str(tmp_path / "hic-yok"),))

    instance = service.ThumbnailService(cache_dir=str(fresh))
    try:
        assert instance.request(str(media)) is None
        assert instance.pending_paths == (str(media),)
    finally:
        instance.close()


def test_the_status_call_also_sees_a_legacy_frame(qt_app, tmp_path,
                                                  monkeypatch):
    media = tmp_path / "Film.mkv"
    media.write_bytes(b"0" * 2048)
    fresh = tmp_path / "yeni"
    legacy = tmp_path / "eski"
    fresh.mkdir()
    legacy.mkdir()
    monkeypatch.setattr(service, "legacy_cache_dirs", lambda: (str(legacy),))
    name = os.path.basename(service.thumbnail_cache_path(str(media),
                                                         str(fresh)))
    (legacy / name).write_bytes(b"JPEG")

    instance = service.ThumbnailService(cache_dir=str(fresh))
    try:
        assert instance.status(str(media)) == "ready"
    finally:
        instance.close()


# =====================================================================
# 3. Degismemesi gerekenler
# =====================================================================

def test_the_cache_identity_still_follows_size_and_mtime(qt_app, tmp_path):
    media = tmp_path / "Film.mkv"
    media.write_bytes(b"0" * 2048)
    first = service.thumbnail_cache_path(str(media), str(tmp_path))

    media.write_bytes(b"0" * 4096)
    second = service.thumbnail_cache_path(str(media), str(tmp_path))

    assert first != second, "dosya değişti ama kimlik aynı kaldı"


def test_the_worker_command_contract_is_unchanged(monkeypatch):
    monkeypatch.setattr(service.sys, "frozen", True, raising=False)
    monkeypatch.setattr(service.sys, "executable", "C:\\app\\MLC Player.exe")

    program, args = service.build_worker_command("C:\\v.mkv", "C:\\o.jpg")

    assert program == "C:\\app\\MLC Player.exe"
    assert args == ["--thumbnail-worker", "C:\\v.mkv", "C:\\o.jpg"]
