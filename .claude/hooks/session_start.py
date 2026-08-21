"""Oturum acilisinda guncel devam noktasini ve Git durumunu sunar.

Kisa ve tek resmi devam noktasi docs/CONTINUITY.md'dir. Tarihsel
PROJECT_STATUS bu hook tarafindan okunmaz.

Bu adimlar elle yapildigi icin atlanabiliyordu: 15 Agustos 2026'da
PROJECT_STATUS dort tur geride kalmisti ve tamamlanmis maddeler yeniden
"siradaki is" gibi gorunuyordu. Hook, git durumunu ve CONTINUITY icindeki
siradaki tek adimi her oturumun basinda baglama enjekte eder.

Salt okunurdur: hicbir sey yazmaz, hicbir seyi degistirmez.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(ROOT, "docs", "CONTINUITY.md")
HEADING = "## Sıradaki tek adım"
MAX_LINES = 12


def git_status():
    try:
        completed = subprocess.run(
            ["git", "status", "--short", "--branch"], cwd=ROOT,
            capture_output=True, text=True, timeout=20)
    except Exception as error:
        return f"(git durumu okunamadi: {error!r})"
    lines = completed.stdout.splitlines()
    if len(lines) > 30:
        lines = lines[:30] + [f"... (+{len(lines) - 30} satir daha)"]
    return "\n".join(lines) or "(temiz)"


def next_step():
    if not os.path.isfile(STATUS):
        return "(docs/CONTINUITY.md bulunamadi)"
    with open(STATUS, encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()
    try:
        start = next(i for i, row in enumerate(lines) if row.strip() == HEADING)
    except StopIteration:
        return f"({HEADING!r} basligi bulunamadi)"
    collected = []
    for row in lines[start + 1:]:
        if row.startswith("## "):
            break
        collected.append(row)
        if len(collected) >= MAX_LINES:
            break
    return "\n".join(collected).strip() or "(bolum bos)"


def main():
    context = (
        "MLC Player oturum acilisi (AGENTS.md sozlesmesi, otomatik):\n\n"
        f"### git status --short --branch\n{git_status()}\n\n"
        f"### docs/CONTINUITY.md -> {HEADING}\n{next_step()}\n"
    )
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
