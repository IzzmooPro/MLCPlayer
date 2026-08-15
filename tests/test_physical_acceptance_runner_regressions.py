"""Fiziksel kabul runner'inin SONUC MANTIGI regresyonlari.

Bu testler Qt/MPV baslatmaz; yalnizca `tests/run_physical_acceptance.py` icindeki
saf siniflandirma mantigini olcer.

Kesin kural
-----------
"Test edilemedi" ASLA "basarili" degildir. BLOCKED, TIMEOUT, INCOMPLETE,
FAIL, eksik RESULT satiri, eksik MARK_DONE ve child'in sifir olmayan exit
kodu genel kabulu BASARISIZ yapar. Yalniz butun secili gruplar gercek PASS
ise exit 0 verilir.
"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER_PATH = os.path.join(ROOT, "tests", "run_physical_acceptance.py")


@pytest.fixture(scope="module")
def runner():
    """Runner modulunu ICE AKTARIR (calistirmaz)."""
    os.environ.setdefault("MLC_NATIVE_SMOKE", "1")
    spec = importlib.util.spec_from_file_location(
        "mlc_physical_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def row(status, test="t", evidence=""):
    return {"test": test, "method": "m", "expected": "e", "measured": "x",
            "status": status, "evidence": evidence}


# =====================================================================
# 1. Grup siniflandirmasi
# =====================================================================

def test_all_passing_rows_are_a_pass(runner):
    status = runner.classify_group([row("PASS"), row("PASS")],
                                   timed_out=False, mark_done=True,
                                   exit_code=0)

    assert status == "PASS"


def test_blocked_row_blocks_the_group_even_with_passes(runner):
    """Once bir grupta PASS + BLOCKED karisimi PASS sayiliyordu."""
    status = runner.classify_group([row("PASS"), row("BLOCKED")],
                                   timed_out=False, mark_done=True,
                                   exit_code=0)

    assert status == "BLOCKED"


def test_only_blocked_rows_block_the_group(runner):
    status = runner.classify_group([row("BLOCKED")], timed_out=False,
                                   mark_done=True, exit_code=0)

    assert status == "BLOCKED"


def test_failed_row_beats_blocked(runner):
    status = runner.classify_group([row("PASS"), row("BLOCKED"), row("FAIL")],
                                   timed_out=False, mark_done=True,
                                   exit_code=0)

    assert status == "FAIL"


def test_timeout_wins_over_everything(runner):
    status = runner.classify_group([row("PASS")], timed_out=True,
                                   mark_done=True, exit_code=0)

    assert status == "TIMEOUT"


def test_missing_mark_done_is_incomplete(runner):
    status = runner.classify_group([row("PASS")], timed_out=False,
                                   mark_done=False, exit_code=0)

    assert status == "INCOMPLETE"


def test_missing_result_rows_are_never_a_pass(runner):
    status = runner.classify_group([], timed_out=False, mark_done=True,
                                   exit_code=0)

    assert status != "PASS"


def test_non_zero_child_exit_is_never_a_pass(runner):
    """Child crash'i, RESULT satirlari gecmis gorunse bile PASS degildir."""
    status = runner.classify_group([row("PASS"), row("PASS")],
                                   timed_out=False, mark_done=True,
                                   exit_code=1)

    assert status != "PASS"


@pytest.mark.parametrize("exit_code", [1, 2, 90, 3221225477, -1073741819])
def test_child_crash_codes_are_not_passes(runner, exit_code):
    status = runner.classify_group([row("PASS")], timed_out=False,
                                   mark_done=True, exit_code=exit_code)

    assert status != "PASS"


def test_unknown_child_exit_is_not_a_pass(runner):
    status = runner.classify_group([row("PASS")], timed_out=False,
                                   mark_done=True, exit_code=None)

    assert status != "PASS"


# =====================================================================
# 2. Genel kabul exit kodu
# =====================================================================

def test_all_pass_groups_exit_zero(runner):
    assert runner.overall_exit_code(["PASS", "PASS", "PASS"]) == 0


@pytest.mark.parametrize("bad", ["FAIL", "TIMEOUT", "INCOMPLETE", "BLOCKED",
                                 "CRASH"])
def test_any_non_pass_group_fails_the_run(runner, bad):
    assert runner.overall_exit_code(["PASS", bad, "PASS"]) != 0


def test_blocked_alone_fails_the_run(runner):
    """BLOCKED bulunan kabul kosumu exit 0 VEREMEZ."""
    assert runner.overall_exit_code(["BLOCKED"]) != 0


def test_empty_run_is_not_a_success(runner):
    """Hicbir grup kosmadiysa 'basarili' denemez."""
    assert runner.overall_exit_code([]) != 0


def test_importing_the_runner_does_not_execute_it(runner):
    """Modul ice aktarilinca gruplar KOSMAZ (guard mevcut)."""
    assert callable(runner.main)
    assert callable(runner.classify_group)
    assert callable(runner.overall_exit_code)
