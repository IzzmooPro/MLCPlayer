# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Native resize harness'i hedef DIŞI fiziksel girdi göndermemeli.

`native_resize_diag_child.py::input_worker()` önkoşulları yalnız iş bittikten
SONRA `contract_problems()` ile denetliyordu. `SetCursorPos` etkisiz kaldığında
LEFTDOWN ve 24 adımlık sürükleme yine de gönderiliyordu; bu, gerçek koşumda
masaüstünde hedef dışı ~1100 px'lik bir sol-sürükleme üretti.

Sözleşme fail-closed olmalı: önkoşul sağlanmazsa TEK bir mouse olayı bile
gönderilmez, LEFTDOWN sonrası herhangi bir hatada sol tuş serbest bırakılır ve
başarısız `SendInput` başarı sayılmaz.

Bu test gerçek fare, pencere, video veya native child ÇALIŞTIRMAZ; yalnız
Win32 çağrılarını sahteler.
"""
import ctypes
import importlib.util
import os

import pytest

MODULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "native_resize_diag_child.py")
EXPECTED_HWND = 4242
TARGET = (303, 916)
DESTINATION = (233, 986)


@pytest.fixture(scope="module")
def child_module():
    """Child modülünü opt-in kapısıyla içe aktarır (GUI kurulmaz).

    Child AYRI SÜREÇTE gerçek pencereyle koşmak için tasarlandığından modül
    düzeyinde `QT_QPA_PLATFORM` anahtarını siler. Süreç İÇİNDE çalıştırıldığı
    bu yolda o silme pytest sürecinin ortamını kalıcı bozuyordu: QApplication
    sonradan gerçek `windows` platformunda kuruluyor ve tam pakette overlay
    görünürlük/opaklık/geometri testleri düşüyordu. Child davranışı
    DEĞİŞTİRİLMEZ; anahtar burada geri yüklenir.
    """
    previous = os.environ.get("MLC_NATIVE_SMOKE")
    previous_platform = os.environ.get("QT_QPA_PLATFORM")
    os.environ["MLC_NATIVE_SMOKE"] = "1"
    try:
        spec = importlib.util.spec_from_file_location(
            "native_resize_diag_child_under_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            os.environ.pop("MLC_NATIVE_SMOKE", None)
        else:
            os.environ["MLC_NATIVE_SMOKE"] = previous
        if previous_platform is None:
            os.environ.pop("QT_QPA_PLATFORM", None)
        else:
            os.environ["QT_QPA_PLATFORM"] = previous_platform
    return module


class FakeUser32:
    """Yalnız `input_worker`'ın kullandığı Win32 yüzeyini taklit eder."""

    def __init__(self, module, cursor=(1336, 823), move_works=True,
                 hwnd=EXPECTED_HWND, button_down=False,
                 sendinput_result=1, raise_on_move_index=None):
        self._module = module
        self.cursor = cursor
        self.move_works = move_works
        self.hwnd = hwnd
        self.button = button_down
        self.sendinput_result = sendinput_result
        self.raise_on_move_index = raise_on_move_index
        self.calls = []
        self._move_count = 0

    # --- Win32 taklitleri ---

    def SetCursorPos(self, x, y):
        self._move_count += 1
        self.calls.append(("SetCursorPos", int(x), int(y)))
        if (self.raise_on_move_index is not None
                and self._move_count == self.raise_on_move_index):
            raise OSError("SetCursorPos patladi")
        if self.move_works:
            self.cursor = (int(x), int(y))
        return 1

    def GetCursorPos(self, ref):
        ref._obj.x, ref._obj.y = self.cursor
        return 1

    def GetAsyncKeyState(self, _vk):
        return 0x8000 if self.button else 0

    def WindowFromPoint(self, _point):
        return self.hwnd

    def SendInput(self, _count, array, _size):
        flag = array[0].mi.dwFlags
        self.calls.append(("SendInput", flag))
        if self.sendinput_result == 1:
            if flag == self._module.MOUSEEVENTF_LEFTDOWN:
                self.button = True
            elif flag == self._module.MOUSEEVENTF_LEFTUP:
                self.button = False
        return self.sendinput_result

    # --- Ölçüm yardımcıları ---

    def sent_flags(self):
        return [flag for name, flag in
                ((c[0], c[1]) for c in self.calls) if name == "SendInput"]

    def mouse_event_count(self):
        return len(self.sent_flags())


@pytest.fixture
def run_worker(child_module, monkeypatch):
    """Sahte Win32 ile `input_worker`'ı çalıştırır; uykular kaldırılır."""
    monkeypatch.setattr(child_module.time, "sleep", lambda _s: None)

    def runner(**kwargs):
        fake = FakeUser32(child_module, **kwargs)
        monkeypatch.setattr(child_module, "user32", fake)
        report = {}
        child_module.input_worker(TARGET[0], TARGET[1],
                                  DESTINATION[0], DESTINATION[1],
                                  EXPECTED_HWND, report)
        return fake, report

    return runner


# --- Fail-closed: önkoşul sağlanmazsa hiç girdi gönderilmez ---

def test_noop_setcursorpos_sends_no_mouse_input_at_all(run_worker):
    """Bu turdaki gerçek arıza: imleç hedefe gitmedi, tıklama yine gitti."""
    fake, report = run_worker(move_works=False)

    assert fake.mouse_event_count() == 0, (
        f"hedef dışı mouse olayı gönderildi: {fake.sent_flags()}")
    assert not report.get("ok")
    assert "cursor" in report.get("blocked", ""), report
    # Sürükleme adımları da hiç çalışmamalı: yalnız tek konumlandırma denemesi.
    assert sum(1 for c in fake.calls if c[0] == "SetCursorPos") == 1


def test_button_already_down_blocks_before_any_win32_action(run_worker):
    fake, report = run_worker(button_down=True)

    assert fake.mouse_event_count() == 0
    assert not any(c[0] == "SetCursorPos" for c in fake.calls), (
        "sol tuş basılıyken imleç yine de taşındı")
    assert report.get("blocked") == "button_already_down"
    assert not report.get("ok")


def test_wrong_window_under_cursor_sends_no_mouse_input(run_worker):
    fake, report = run_worker(hwnd=EXPECTED_HWND + 7)

    assert fake.mouse_event_count() == 0, (
        f"yabancı pencereye girdi gönderildi: {fake.sent_flags()}")
    assert not report.get("ok")
    assert str(EXPECTED_HWND) in report.get("blocked", ""), report


def test_failed_sendinput_is_not_reported_as_success(run_worker):
    fake, report = run_worker(sendinput_result=0)

    assert not report.get("ok"), "başarısız SendInput başarı sayıldı"
    assert report.get("blocked"), report
    assert fake.mouse_event_count() == 1, (
        f"başarısız LEFTDOWN'dan sonra girdi akmaya devam etti: "
        f"{fake.sent_flags()}")


# --- LEFTDOWN sonrası hata: tuş basılı kalmamalı ---

def test_error_after_leftdown_still_releases_the_button(run_worker, child_module):
    # 1. SetCursorPos hedefe konumlandırma, 2. çağrı ilk sürükleme adımı.
    fake, report = run_worker(raise_on_move_index=2)

    flags = fake.sent_flags()
    assert flags[0] == child_module.MOUSEEVENTF_LEFTDOWN
    assert child_module.MOUSEEVENTF_LEFTUP in flags, (
        f"hata sonrası LEFTUP denenmedi: {flags}")
    assert fake.button is False, "sol tuş basılı bırakıldı"
    assert not report.get("ok")
    assert report.get("error") == "OSError"


# --- Önkoşullar sağlanınca akış aynen çalışır ---

def test_healthy_run_still_performs_press_drag_release(run_worker, child_module):
    fake, report = run_worker()

    flags = fake.sent_flags()
    assert flags == [child_module.MOUSEEVENTF_LEFTDOWN,
                     child_module.MOUSEEVENTF_LEFTUP]
    assert report.get("ok") is True
    assert report.get("blocked") is None
    assert report["cursor_after_move"] == TARGET
    assert report["cursor_final"] == DESTINATION
    assert report["done"] is True
