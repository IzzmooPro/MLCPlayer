# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in gerçek pencere + ikinci süreç IPC smoke'u.

Birincil süreç gerçek ``MPVPlayer`` penceresini açar. Aynı dosya ikinci kez
çalıştırıldığında yalnız ``SingleInstanceGuard`` istemcisi olur, ACK alır ve
çıkar; birincil pencere dosya ve güvenli HTTP hedefini ortak ürün yoluyla alır.
"""
import os
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OPT_IN = "MLC_NATIVE_WINDOW_IPC"


def pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def secondary(name, payload):
    from PyQt6.QtWidgets import QApplication
    from app.single_instance import SingleInstanceGuard
    app = QApplication([])
    guard = SingleInstanceGuard(name)
    primary = guard.acquire(payload)
    print("PRIMARY" if primary else "SECONDARY", flush=True)
    if primary:
        guard.release()
        return 2
    return 2 if guard.handoff_failed else 0


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--secondary":
        return secondary(sys.argv[2], sys.argv[3])
    if os.environ.get(OPT_IN) != "1":
        print("SKIPPED: OPT_IN_REQUIRED", flush=True)
        return 0
    video = os.environ.get("MLC_NATIVE_TEST_VIDEO", "")
    if not os.path.isfile(video):
        print("BLOCKED invalid_explicit_media", flush=True)
        return 2

    os.environ["PATH"] = os.path.join(ROOT, "bin") + os.pathsep + os.environ["PATH"]
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    from app.player import MPVPlayer
    from app.single_instance import SingleInstanceGuard, activate_window

    app = QApplication([])
    old = QSettings.defaultFormat()
    checks = []
    with tempfile.TemporaryDirectory(prefix="mlc-native-ipc-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          settings)
        player = MPVPlayer()
        player.resize(1000, 650)
        player.show()
        player.open_path(video)
        deadline = time.monotonic() + 8
        while player.duration <= 0 and time.monotonic() < deadline:
            pump(app, 0.05)

        name = "MLCNativeWindowIPC-" + uuid.uuid4().hex
        instance = SingleInstanceGuard(name)
        if not instance.acquire():
            print("FAIL primary_acquire", flush=True)
            return 1
        received = []
        instance.activation_requested.connect(
            lambda payload: (received.append(payload), activate_window(player, payload)))
        for label, payload in (("file", os.path.abspath(video)),
                               ("url", "http://127.0.0.1:9/mlc-ipc-probe.m3u8")):
            child = subprocess.Popen([sys.executable, __file__, "--secondary",
                                      name, payload], cwd=ROOT,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True)
            deadline = time.monotonic() + 20
            while child.poll() is None and time.monotonic() < deadline:
                pump(app, 0.03)
            if child.poll() is None:
                child.kill()
            stdout, stderr = child.communicate(timeout=5)
            ok = (child.returncode == 0 and stderr == ""
                  and stdout.strip() == "SECONDARY" and received[-1:] == [payload]
                  and player.current_file == payload)
            checks.append(ok)
            print(f"CHECK {'PASS' if ok else 'FAIL'} ipc_{label} "
                  f":: exit={child.returncode} received={received[-1:] == [payload]} "
                  f"loaded={player.current_file == payload} stderr={bool(stderr)}", flush=True)
        instance.release()
        player.close()
        pump(app, 0.4)
    QSettings.setDefaultFormat(old)
    failures = checks.count(False)
    print(f"RESULT failures={failures}", flush=True)
    print("MARK_DONE", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
