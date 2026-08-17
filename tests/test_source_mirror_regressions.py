# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Karşılık gelen kaynağın aynalanması: hangi arşiv indirilir, nasıl doğrulanır.

NEDEN VAR (GPLv3 §6). Dağıttığımız üçüncü taraf ikililerinin kaynağı şu an
YALNIZ upstream adreslerde duruyor. shinchiro'nun release'i, yt-dlp'nin
etiketi veya deno'nun sürümü silinirse gösterecek yerimiz kalmaz. Bu betik
manifestteki arşivleri indirip SHA-256 ile doğrular; çıktı klasörü
release'e ek asset olarak yüklenmeye hazırdır.

ÖLÇÜLEN TUZAK — MANİFESTİN HER SATIRI İNDİRİLEBİLİR ARŞİV DEĞİLDİR.
`bin/RUNTIME_MANIFEST.txt` yedi satır taşıyor ama SHA-256'nın neyin özeti
olduğu satırdan satıra DEĞİŞİYOR:

    mpv-2.dll        -> ozet DLL'in,  URL bir .7z arsivi       FARKLI
    deno.exe         -> ozet EXE'nin, URL bir .zip arsivi      FARKLI
    mpv-dev-....7z   -> ozet arsivin, URL o arsiv              AYNI
    yt-dlp.exe       -> ozet exe'nin, URL o exe                AYNI

Naif bir indirici `mpv-2.dll` satırının URL'ini indirip DLL'in özetiyle
karşılaştırır ve "dosya bozuk" der — oysa doğru dosyayı indirmiştir.

Ad karşılaştırması da YETMEZ: `yt-dlp-THIRD_PARTY_LICENSES.txt` satırının
adı URL'in sonundaki `THIRD_PARTY_LICENSES.txt` ile aynı değildir ama o
satır doğrudan indirilebilir ve özeti indirilene aittir.

Bu yüzden sınıflandırma AÇIK bir listedir ve her satır ya listede ya da
gerekçeli dışlamadadır; yeni bir bileşen sessizce unutulamaz (test kırılır).
"""

import importlib.util
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "bin" / "RUNTIME_MANIFEST.txt"


def module():
    path = ROOT / "packaging" / "fetch_sources.py"
    assert path.is_file(), "kaynak aynalama betiği yok"
    spec = importlib.util.spec_from_file_location("mlc_fetch", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def manifest_names():
    names = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "|" not in line:
            continue
        names.append(line.split("|")[0].strip())
    return names


# ── Sınıflandırma ────────────────────────────────────────────────────────

def test_every_manifest_row_is_classified():
    """Yeni bir bileşen eklendiğinde SESSİZCE atlanamaz."""
    fetch = module()
    classified = set(fetch.FETCHABLE) | set(fetch.NOT_FETCHABLE)
    assert set(manifest_names()) == classified, (
        "manifestte sınıflandırılmamış satır var: "
        f"{set(manifest_names()) ^ classified}")


def test_the_excluded_rows_carry_a_reason():
    """Dışlama gerekçesiz olmaz; yoksa bir gün yanlışlıkla eklenir."""
    fetch = module()
    for name, reason in fetch.NOT_FETCHABLE.items():
        assert reason.strip(), name


def test_the_archives_that_carry_their_own_digest_are_fetchable():
    """Özeti KENDİSİNE ait olan satırlar aynalanır."""
    fetch = module()
    for name in ("mpv-dev-x86_64-20260814-git-7b8915bc1d.7z",
                 "yt-dlp.exe",
                 "deno-x86_64-pc-windows-msvc.zip"):
        assert name in fetch.FETCHABLE, name


def test_the_rows_whose_digest_is_of_an_extracted_file_are_excluded():
    """`mpv-2.dll` ve `deno.exe` ARŞİVDEN çıkar; URL'i indirmek yanlış
    özetle karşılaştırma yapardı."""
    fetch = module()
    for name in ("mpv-2.dll", "deno.exe", "libmpv.dll.a"):
        assert name in fetch.NOT_FETCHABLE, name


def test_a_renamed_but_directly_downloadable_row_is_still_fetchable():
    """Ad karşılaştırması yetmez: bu satırın adı URL'in sonundan farklı."""
    fetch = module()
    assert "yt-dlp-THIRD_PARTY_LICENSES.txt" in fetch.FETCHABLE


# ── Plan: ağa çıkmadan ölçülebilir ───────────────────────────────────────

def test_the_plan_reads_url_size_and_digest_from_the_manifest():
    fetch = module()
    plan = {item.name: item for item in fetch.plan()}
    assert set(plan) == set(fetch.FETCHABLE)
    for item in plan.values():
        assert item.url.startswith("https://"), item.name
        assert item.size > 0
        assert len(item.sha256) == 64


def test_the_plan_never_leaves_the_trusted_hosts():
    """İndirme adresi denetlenmeden ağa çıkılmaz."""
    fetch = module()
    from urllib.parse import urlsplit

    for item in fetch.plan():
        host = urlsplit(item.url).hostname or ""
        assert host in fetch.TRUSTED_HOSTS, f"{item.name}: {host}"


# ── Doğrulama fail-closed ────────────────────────────────────────────────

def test_a_wrong_digest_is_rejected_and_the_file_is_removed(tmp_path):
    """Doğrulanamayan dosya SAKLANMAZ; yarım ayna işe yaramaz."""
    fetch = module()
    target = tmp_path / "bozuk.bin"
    target.write_bytes(b"yanlis icerik")

    ok = fetch.verify(target, size=len(b"yanlis icerik"),
                      sha256="0" * 64)

    assert ok is False
    assert not target.exists(), "bozuk dosya silinmedi"


def test_a_correct_digest_is_accepted(tmp_path):
    fetch = module()
    payload = b"dogru icerik"
    target = tmp_path / "iyi.bin"
    target.write_bytes(payload)

    ok = fetch.verify(target, size=len(payload),
                      sha256=hashlib.sha256(payload).hexdigest())

    assert ok is True
    assert target.exists()


def test_a_size_mismatch_is_rejected_before_hashing(tmp_path):
    """Boyut ucuz bir ön elemedir; 40 MB'ı boşuna özetlemeyiz."""
    fetch = module()
    payload = b"kisa"
    target = tmp_path / "kisa.bin"
    target.write_bytes(payload)

    ok = fetch.verify(target, size=999999,
                      sha256=hashlib.sha256(payload).hexdigest())

    assert ok is False


# ── Çıktı deposu izlenmez ────────────────────────────────────────────────

def test_the_mirror_folder_is_ignored_by_git():
    fetch = module()
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert fetch.OUTPUT_DIR_NAME in ignore, (
        "aynalanan arşivler depoya girmemeli")


def test_the_script_does_not_run_anything_on_import():
    """İçe aktarmak 90 MB indirmemelidir."""
    source = (ROOT / "packaging" / "fetch_sources.py").read_text(
        encoding="utf-8")
    assert 'if __name__ == "__main__":' in source
    assert "urlopen" not in source.split('if __name__ == "__main__":')[0] \
        .split("def ")[0]
