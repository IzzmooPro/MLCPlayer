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


def git_query(args):
    try:
        completed = subprocess.run(
            ["git", *args], cwd=ROOT,
            capture_output=True, text=True, timeout=20)
    except Exception as error:
        return f"(git sorgusu okunamadi: {error!r})"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        return f"(git exit {completed.returncode}: {detail or 'cikti yok'})"
    lines = completed.stdout.splitlines()
    if len(lines) > 30:
        lines = lines[:30] + [f"... (+{len(lines) - 30} satir daha)"]
    return "\n".join(lines) or "(cikti yok)"


def latest_evidence():
    if not os.path.isfile(STATUS):
        return "(docs/CONTINUITY.md bulunamadi)"
    with open(STATUS, encoding="utf-8", errors="replace") as handle:
        for row in handle:
            if row.startswith("- Son kanıt:"):
                return row.removeprefix("- ").strip()
    return "(Son kanıt satiri bulunamadi)"


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
        "### git rev-parse --show-toplevel\n"
        f"{git_query(['rev-parse', '--show-toplevel'])}\n\n"
        "### git status --short --branch\n"
        f"{git_query(['status', '--short', '--branch'])}\n\n"
        "### git log -1 --oneline --decorate\n"
        f"{git_query(['log', '-1', '--oneline', '--decorate'])}\n\n"
        "### git rev-list --left-right --count HEAD...origin/master\n"
        f"{git_query(['rev-list', '--left-right', '--count',
                      'HEAD...origin/master'])}\n\n"
        f"### Son kanıt\n{latest_evidence()}\n\n"
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
