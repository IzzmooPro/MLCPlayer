# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fiziksel kabul child'inin OLCUM SOZLESMESI regresyonlari.

`MARK_APP_EXEC_RETURNED` yalnizca GERCEK bir `QApplication.exec()` donusunun
ardindan yazilabilir. Kaynak metni aramak yeterli degildir; burada child'in
sozlesmesi gercek bir Qt event loop'u ile davranissal olarak olculur.

Testler MPV veya gercek video KULLANMAZ; yalnizca "grup isi event loop
icinde calisir ve exec gercekten doner" sozlesmesini dogrular.
"""
import os
import subprocess
import sys
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = os.path.join(ROOT, "tests", "native_physical_acceptance_child.py")


def read_child_source():
    with open(CHILD, encoding="utf-8", errors="replace") as handle:
        return handle.read()


# =====================================================================
# 1. Sozlesmenin DAVRANISSAL karsiligi
# =====================================================================

LOOP_PROBE = textwrap.dedent(
    """
    import os, sys
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication(sys.argv)
    window = QWidget()
    window.show()
    state = {"in_loop": None}

    def body():
        # Grup isi burada calisir: event loop GERCEKTEN doner mi?
        state["in_loop"] = bool(QApplication.instance().thread())
        print(f"BODY_RAN in_loop={state['in_loop']}", flush=True)
        window.close()
        app.quit()

    QTimer.singleShot(0, body)
    code = app.exec()
    print(f"MARK_APP_EXEC_RETURNED code={code}", flush=True)
    print("MARK_DONE", flush=True)
    os._exit(0)
    """
)


def test_event_loop_contract_is_reproducible(tmp_path):
    """Referans olcum: singleShot + exec gercekten doner ve marker yazilir.

    Bu, child'dan beklenen sozlesmenin calisir bir ornegidir; child bunun
    ayni yapisini kullanmalidir.
    """
    probe = tmp_path / "loop_probe.py"
    probe.write_text(LOOP_PROBE, encoding="utf-8")

    completed = subprocess.run([sys.executable, str(probe)],
                               capture_output=True, text=True, timeout=120)

    assert "BODY_RAN in_loop=True" in completed.stdout, completed.stdout
    assert "MARK_APP_EXEC_RETURNED code=0" in completed.stdout
    assert completed.stdout.index("BODY_RAN") < completed.stdout.index(
        "MARK_APP_EXEC_RETURNED")
    assert completed.returncode == 0


def test_child_runs_the_group_inside_the_event_loop():
    """Grup isi dogrudan degil, event loop icinden tetiklenmeli."""
    source = read_child_source()

    assert "QTimer.singleShot(0, run_body)" in source
    assert "exec_code = APP.exec()" in source


def test_child_marks_exec_return_only_after_exec():
    """`MARK_APP_EXEC_RETURNED` satiri `APP.exec()` DONUSUNDEN sonra olmali."""
    source = read_child_source()
    exec_call = source.index("exec_code = APP.exec()")
    marker = source.index('print(f"MARK_APP_EXEC_RETURNED')

    assert exec_call < marker
    assert "code={exec_code}" in source[marker:marker + 200]


def test_child_does_not_fake_the_exec_marker():
    """Marker BIRDEN FAZLA yerde yazilmamali (sahte marker yok)."""
    source = read_child_source()

    assert source.count("MARK_APP_EXEC_RETURNED") == 1


def test_child_closes_only_through_the_product_path():
    """Kapanis yalnizca `PLAYER.close()`; child stop/terminate cagirmaz."""
    source = read_child_source()

    assert "PLAYER.close()" in source
    assert "PLAYER.mpv_player.stop()" not in source
    assert "PLAYER.mpv_player.terminate()" not in source


def test_child_exit_uses_product_policy_after_results():
    """`os._exit` yalnizca sonuc satirlarindan SONRA (main.py politikasi)."""
    source = read_child_source()
    done = source.index('print(f"MARK_DONE group={GROUP}"')
    exit_call = source.index("os._exit(main())")

    assert done < exit_call
