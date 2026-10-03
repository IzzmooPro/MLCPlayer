# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""`docs/README.md` belge haritası ile `docs/` ağacı birebir eşleşir.

Neden (3 Ekim 2026): `docs/` kökünde 19 belge düz biçimde birikmişti; iki
SignPath belgesi aynı durumu üç kez tekrar ediyor, bir envanter hiçbir
belgeden atıf almıyor, canlı ve tarihsel belgeler aynı klasörde duruyordu.
Harita her belgenin tek sorumluluğunu yazar; bu test haritanın eskimesini
ve haritaya girmeden yeni belge eklenmesini engeller.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "README.md"
DOC_SUFFIXES = {".md", ".json"}


def _listed():
    text = INDEX.read_text(encoding="utf-8")
    return set(re.findall(r"`(docs/[^`\s]+\.(?:md|json))`", text))


def _present():
    return {
        path.relative_to(ROOT).as_posix()
        for path in DOCS.rglob("*")
        if path.is_file() and path.suffix in DOC_SUFFIXES and path != INDEX
    }


def test_every_listed_document_exists():
    missing = sorted(path for path in _listed() if not (ROOT / path).is_file())
    assert missing == []


def test_every_document_is_listed_in_the_index():
    unlisted = sorted(_present() - _listed())
    assert unlisted == [], "docs/README.md haritasına eklenmemiş belge"


def test_history_documents_declare_themselves_historical():
    for path in sorted((DOCS / "history").glob("*.md")):
        opening = "\n".join(path.read_text(encoding="utf-8").splitlines()[:12])
        assert "TARİHSEL" in opening.upper(), path.name
        assert "docs/CONTINUITY.md" in opening, path.name


def test_repository_root_holds_only_the_launcher_and_licence():
    allowed = {"Start.bat", "LICENSE", ".gitignore", ".gitattributes"}
    tracked_root = {
        path.name for path in ROOT.iterdir()
        if path.is_file() and path.name in _tracked_root_names()
    }
    assert tracked_root <= allowed, sorted(tracked_root - allowed)


def _tracked_root_names():
    import subprocess
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         encoding="utf-8", check=True).stdout
    return {line for line in out.splitlines() if line and "/" not in line}
