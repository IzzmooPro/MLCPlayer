# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""NATIVE-001 CDB kanitinin saf ve fail-closed ayrisma sozlesmesi."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from native_debugger_evidence import parse_debugger_evidence  # noqa: E402


COMMAND_ECHO = (
    '0:000> sxe -c ".echo ===FIRST-CHANCE-BEGIN===; '
    '.echo ===FIRST-CHANCE-END===; '
    '.echo ===REPEAT-FIRST-CHANCE-SKIPPED===" '
    '-c2 ".echo ===SECOND-CHANCE-BEGIN===; '
    '.echo ===SECOND-CHANCE-END-NO-AUTO-CONTINUE===" 0xe24c4a02\n'
)

SECTIONS = (
    "---EXR---",
    "---ECXR---",
    "---REGISTERS---",
    "---RIP-SYMBOL---",
    "---RIP-DISASM---",
    "---FAULT-STACK---",
    "---ALL-THREADS---",
    "---MODULES---",
    "---MODULE-AT-RIP---",
)


def evidence_log(*, repeats=13, second_chance=False):
    lines = [
        COMMAND_ECHO.rstrip("\n"),
        "(2014.302c): Unknown exception - code e24c4a02 (first chance)",
        "===FIRST-CHANCE-BEGIN===",
        *SECTIONS,
        '# 15 Id: 2014.302c Suspend: 1 Unfrozen "lua/stats"',
        '  14 Id: 2014.75b0 Suspend: 1 Unfrozen "lua/ytdl_hook"',
        '  18 Id: 2014.1020 Suspend: 1 Unfrozen "lua/select"',
        "===FIRST-CHANCE-END===",
    ]
    tids = ["75b0"] + ["1020"] * max(0, repeats - 2) + ["302c"]
    for tid in tids[:repeats]:
        lines.extend([
            f"(2014.{tid}): Unknown exception - code e24c4a02 (first chance)",
            "===REPEAT-FIRST-CHANCE-SKIPPED===",
        ])
    if second_chance:
        lines.extend([
            "(2014.302c): Unknown exception - code e24c4a02 (second chance)",
            "===SECOND-CHANCE-BEGIN===",
            "===SECOND-CHANCE-END-NO-AUTO-CONTINUE===",
        ])
    return "\n".join(lines) + "\n"


def test_command_echo_is_not_evidence_for_any_marker():
    result = parse_debugger_evidence(COMMAND_ECHO)

    assert result.first_block_count == 0
    assert result.repeat_count == 0
    assert result.second_chance_marker_count == 0
    assert result.problems, "yalniz komut yankisi kanit sayildi"


def test_an_empty_log_fails_closed():
    result = parse_debugger_evidence("")

    assert result.problems, "bos debugger logu TAMAM sayildi"


def test_a_real_second_chance_marker_is_high_priority_fail():
    result = parse_debugger_evidence(evidence_log(second_chance=True))

    assert result.second_chance_count == 1
    assert result.second_chance_marker_count == 1
    assert any("SECOND-CHANCE" in problem for problem in result.problems)


def test_the_measured_first_chance_counts_are_parsed_exactly():
    result = parse_debugger_evidence(evidence_log())

    assert result.first_chance_count == 14
    assert result.first_block_count == 1
    assert result.repeat_count == 13
    assert result.second_chance_count == 0
    assert result.second_chance_marker_count == 0
    assert result.problems == ()


def test_prefix_suffix_and_inline_marker_text_do_not_count():
    log = "\n".join([
        "x===SECOND-CHANCE-BEGIN===",
        "===SECOND-CHANCE-BEGIN===x",
        "prefix ===SECOND-CHANCE-BEGIN=== suffix",
    ])

    assert parse_debugger_evidence(log).second_chance_marker_count == 0


def test_fault_thread_is_lua_stats_not_the_mpv_event_handler():
    result = parse_debugger_evidence(
        evidence_log() +
        '  22 Id: 2014.7f70 Suspend: 1 Unfrozen "MPVEventHandlerThread"\n')

    assert result.first_fault_tid == "302c"
    assert result.first_fault_thread == "lua/stats"
    assert result.first_fault_thread != "MPVEventHandlerThread"
    assert result.thread_event_counts == {
        "lua/stats": 2,
        "lua/ytdl_hook": 1,
        "lua/select": 11,
    }


def test_a_partial_or_out_of_order_first_block_fails_closed():
    log = evidence_log().replace("---ECXR---\n", "")

    result = parse_debugger_evidence(log)

    assert any("FIRST-CHANCE" in problem for problem in result.problems)


def test_event_and_marker_counts_must_agree():
    result = parse_debugger_evidence(evidence_log(repeats=2).replace(
        "===REPEAT-FIRST-CHANCE-SKIPPED===\n", "", 1))

    assert any("sayilari AYRISIYOR" in problem for problem in result.problems)
