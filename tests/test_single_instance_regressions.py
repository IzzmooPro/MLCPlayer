"""İkinci başlatma yeni pencere açmaz; açık pencereye devreder.

NEDEN: iki kopya aynı ayar deposunu paylaşır ve her biri KAPANIRKEN kendi
hâlini yazar; ikinci pencerede yapılan değişiklik, önce açılan kopya
kapanınca sessizce geri gidebiliyordu.

Testler GERÇEK `QLocalServer`/`QLocalSocket` kullanır — sahte nesne
"ikinci süreç bağlanabiliyor mu" sorusunu ölçemez. Sunucu adı her testte
benzersizdir: kullanıcının çalışan kopyasına DOKUNULMAZ.
"""

import subprocess
import time
import sys
import textwrap
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from app.single_instance import (SingleInstanceGuard, activate_window,
                                 is_worker_invocation)


@pytest.fixture
def qt_app():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def name():
    return f"MLCPlayerTest-{uuid.uuid4().hex}"


ROOT = Path(__file__).resolve().parent.parent


def _second_launch(name, payload, tmp_path):
    """İkinci başlatmayı GERÇEK ayrı süreçte yapar.

    Aynı süreçte denendi ve ÖLÇÜLDÜ ki ölçemiyor: gönderen taraf onayı
    beklerken bloke olur, birincil taraf ise aynı iş parçacığında olduğu
    için olay döngüsünü çeviremez — yapay bir çıkmaz oluşur. Ürünün
    gerçek durumu iki ayrı süreçtir.
    """
    script = textwrap.dedent(f"""
        import os, sys
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        sys.path.insert(0, {str(ROOT)!r})
        from PyQt6.QtWidgets import QApplication
        from app.single_instance import SingleInstanceGuard
        app = QApplication([])
        guard = SingleInstanceGuard({name!r})
        print("PRIMARY" if guard.acquire({payload!r}) else "SECONDARY")
    """)
    path = tmp_path / "second_launch.py"
    path.write_text(script, encoding="utf-8")
    return subprocess.run([sys.executable, str(path)], capture_output=True,
                          text=True, timeout=60)


def _pump(qt_app, received, seconds=20):
    """İstek gelene kadar olay döngüsünü çevirir.

    Sabit sayıda `processEvents()` YETMİYOR: ikinci süreç henüz başlamadan
    döngü bitiyor ve bağlantı hiç işlenmiyordu.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not received:
        qt_app.processEvents()
        time.sleep(0.01)


def test_first_launch_becomes_the_primary(qt_app, name):
    guard = SingleInstanceGuard(name)
    try:
        assert guard.acquire() is True
    finally:
        guard.release()


def test_second_launch_is_refused_and_hands_over_the_file(qt_app, name,
                                                          tmp_path):
    primary = SingleInstanceGuard(name)
    received = []
    try:
        assert primary.acquire() is True
        primary.activation_requested.connect(received.append)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_second_launch, name, r"I:\film.mkv", tmp_path)
            _pump(qt_app, received)
            result = future.result(timeout=60)

        assert result.stdout.strip() == "SECONDARY", result.stderr
        assert received == [r"I:\film.mkv"]
    finally:
        primary.release()


def test_launch_without_a_file_only_asks_for_activation(qt_app, name,
                                                        tmp_path):
    """Dosyasız ikinci başlatma da pencereyi öne getirmelidir."""
    primary = SingleInstanceGuard(name)
    received = []
    try:
        assert primary.acquire() is True
        primary.activation_requested.connect(received.append)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_second_launch, name, "", tmp_path)
            _pump(qt_app, received)
            result = future.result(timeout=60)

        assert result.stdout.strip() == "SECONDARY", result.stderr
        assert received == [""], "boş yük = yalnız pencereyi öne getir"
    finally:
        primary.release()


def test_released_name_can_be_acquired_again(qt_app, name):
    """Kapanan kopyanın adı geride kalmamalı; yoksa program bir daha açılamaz."""
    first = SingleInstanceGuard(name)
    assert first.acquire() is True
    first.release()

    second = SingleInstanceGuard(name)
    try:
        assert second.acquire() is True
    finally:
        second.release()


def test_stale_server_name_is_reclaimed(qt_app, name):
    """Çökme sonrası artakalan ad BİR KEZ geri alınır (fail-open)."""
    from PyQt6.QtNetwork import QLocalServer

    stale = QLocalServer()
    assert stale.listen(name)
    stale.close()          # dinlemeyi bırakır, ad geride kalabilir

    guard = SingleInstanceGuard(name)
    try:
        assert guard.acquire() is True
    finally:
        guard.release()


@pytest.mark.parametrize("argv,expected", [
    (["main.py", "--thumbnail-worker", "video.mkv", "out.jpg"], True),
    (["main.py", "video.mkv"], False),
    (["main.py"], False),
    ([], False),
])
def test_thumbnail_workers_are_outside_the_guard(argv, expected):
    """İşçiler AYNI exe'dir; korumaya girerlerse küçük resim üretimi durur."""
    assert is_worker_invocation(argv) is expected


def test_activation_raises_the_window_and_opens_the_file():
    """Yeni always-on-top bayrağı KULLANILMAZ; standart geri getirme yapılır."""
    calls = []

    class FakeWindow:
        def isMinimized(self):
            return True

        def showNormal(self):
            calls.append("showNormal")

        def raise_(self):
            calls.append("raise")

        def activateWindow(self):
            calls.append("activate")

        def open_path(self, path):
            calls.append(("open", path))

        def setWindowFlag(self, *args):        # çağrılmamalı
            calls.append("FLAG_DEGISTI")

    activate_window(FakeWindow(), r"I:\film.mkv")
    assert calls == ["showNormal", "raise", "activate", ("open", r"I:\film.mkv")]


def test_activation_without_a_file_only_raises():
    calls = []

    class FakeWindow:
        def isMinimized(self):
            return False

        def raise_(self):
            calls.append("raise")

        def activateWindow(self):
            calls.append("activate")

        def open_path(self, path):
            calls.append("ACILDI")

    activate_window(FakeWindow(), "")
    assert calls == ["raise", "activate"]
