# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""NATIVE-001 CDB metnini yan etkisiz ve fail-closed ayrıştırır."""

from dataclasses import dataclass
import re


FIRST_BEGIN = "===FIRST-CHANCE-BEGIN==="
FIRST_END = "===FIRST-CHANCE-END==="
REPEAT = "===REPEAT-FIRST-CHANCE-SKIPPED==="
SECOND_BEGIN = "===SECOND-CHANCE-BEGIN==="
SECOND_END = "===SECOND-CHANCE-END-NO-AUTO-CONTINUE==="

REQUIRED_FIRST_SECTIONS = (
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

_EVENT_RE = re.compile(
    r"^\((?P<pid>[0-9a-f]+)\.(?P<tid>[0-9a-f]+)\): Unknown exception - "
    r"code e24c4a02 \((?P<chance>first|second) chance\)$",
    re.IGNORECASE,
)
_THREAD_RE = re.compile(
    r'^\s*#?\s*\d+\s+Id:\s+[0-9a-f]+\.(?P<tid>[0-9a-f]+)\s+.*?'
    r'"(?P<name>[^"]+)"\s*$',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DebuggerEvidence:
    """Ayrıştırılmış CDB kanıtı ve fail-closed sözleşme sorunları."""

    first_chance_count: int
    second_chance_count: int
    first_block_count: int
    repeat_count: int
    second_chance_marker_count: int
    first_fault_tid: str | None
    first_fault_thread: str | None
    thread_event_counts: dict[str, int]
    problems: tuple[str, ...]


def _exact_positions(lines, marker):
    return [index for index, line in enumerate(lines) if line == marker]


def parse_debugger_evidence(text):
    """CDB çıktısını ayrıştırır; eksik/çelişkili kanıtı sorun olarak döndürür."""
    lines = text.splitlines()
    problems = []

    events = []
    for line in lines:
        match = _EVENT_RE.fullmatch(line)
        if match:
            events.append((match["tid"].lower(), match["chance"].lower()))

    first_events = [tid for tid, chance in events if chance == "first"]
    second_events = [tid for tid, chance in events if chance == "second"]

    first_begins = _exact_positions(lines, FIRST_BEGIN)
    first_ends = _exact_positions(lines, FIRST_END)
    repeats = _exact_positions(lines, REPEAT)
    second_begins = _exact_positions(lines, SECOND_BEGIN)
    second_ends = _exact_positions(lines, SECOND_END)

    first_block_count = min(len(first_begins), len(first_ends))
    if len(first_begins) != 1 or len(first_ends) != 1:
        problems.append("FIRST-CHANCE kanit blogu tam ve tekil DEGIL")
    elif first_begins[0] >= first_ends[0]:
        problems.append("FIRST-CHANCE kanit blogu sirasi GECERSIZ")
    else:
        block = lines[first_begins[0] + 1:first_ends[0]]
        cursor = -1
        for section in REQUIRED_FIRST_SECTIONS:
            try:
                cursor = block.index(section, cursor + 1)
            except ValueError:
                problems.append(
                    f"FIRST-CHANCE kanit blogunda bolum eksik/sirasiz: {section}")
                break

    if len(second_begins) != len(second_ends):
        problems.append("SECOND-CHANCE marker cifti tam DEGIL")
    if second_events or second_begins or second_ends:
        problems.append("SECOND-CHANCE kaniti bulundu; kabul DURUR")

    if len(first_events) != first_block_count + len(repeats):
        problems.append(
            "first-chance olay ve marker sayilari AYRISIYOR: "
            f"olay={len(first_events)}, blok={first_block_count}, "
            f"tekrar={len(repeats)}")

    thread_names = {}
    for line in lines:
        match = _THREAD_RE.fullmatch(line)
        if match:
            thread_names[match["tid"].lower()] = match["name"]

    thread_event_counts = {}
    for tid in first_events:
        name = thread_names.get(tid, f"tid:{tid}")
        thread_event_counts[name] = thread_event_counts.get(name, 0) + 1

    first_fault_tid = first_events[0] if first_events else None
    first_fault_thread = (
        thread_names.get(first_fault_tid, f"tid:{first_fault_tid}")
        if first_fault_tid is not None else None
    )

    return DebuggerEvidence(
        first_chance_count=len(first_events),
        second_chance_count=len(second_events),
        first_block_count=first_block_count,
        repeat_count=len(repeats),
        second_chance_marker_count=len(second_begins),
        first_fault_tid=first_fault_tid,
        first_fault_thread=first_fault_thread,
        thread_event_counts=thread_event_counts,
        problems=tuple(problems),
    )
