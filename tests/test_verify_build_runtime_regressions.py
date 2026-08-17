# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yayin on-kontrolu: paketlenen UC runtime'in tamami dogrulanmali.

KANITLANMIS KUSUR (17 Agustos 2026):
`packaging/verify_build.py::check_pre()` icinde IKI AYRI liste vardi.
`SOURCE_FILES` uc runtime'i da sayiyordu ama yalnizca VARLIK denetimi
yapiyordu; SHA-256 dogrulamasi ise ayri bir demette (`yt-dlp.exe`,
`deno.exe`) yapiliyordu ve `mpv-2.dll` orada YOKTU.

Sonuc: bozuk ya da yanlis surum bir `mpv-2.dll` on-kontrolden GECIP
release zincirine girebiliyordu. Paketin %59'u o dosyadir.

SOZLESME:
1. Uc runtime da manifest'teki BOYUT ve SHA-256 ile dogrulanir.
2. Kayit eksik, boyut yanlis veya hash yanlissa `--pre` exit 1 verir.
3. Runtime listesi TEK kaynaktan turer; ikinci bir liste olusturulmaz,
   yoksa mpv yeniden unutulabilir.

NOT: testler gercek 119 MB'lik DLL'i KOPYALAMAZ. Kucuk gecici dosyalar
uretilir ve manifest onlarin gercek boyut/hash'iyle yazilir; dogrulanan
sey mekanizmadir, dosyanin buyuklugu degil.
"""
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packaging"))

import verify_build


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


def corrupt_same_size(path):
    """Dosyayi UZUNLUGUNU DEGISTIRMEDEN bozar.

    OLCULEN TEST KUSURU (17 Agustos 2026): bu dosyanin ilk surumu bozuk
    icerigi farkli uzunlukta yaziyordu. Dogrulama boyutu ONCE denetledigi
    icin testler `SIZE DOES NOT MATCH` ile geciyor, SHA-256 yoluna HIC
    ULASMIYORDU. Yani hash korumasi yesil testlere ragmen KANITSIZDI.

    Burada yalnizca ICERIK degisir: ilk bayt XOR 0xFF ile cevrilir, boylece
    yeni deger eskisinden KESINLIKLE farklidir ve uzunluk aynidir.
    """
    original = path.read_bytes()
    assert original, "bos dosya bozulamaz; fixture icerik yazmali"
    flipped = bytes([original[0] ^ 0xFF]) + original[1:]
    assert flipped != original, "bayt gercekten degismedi"
    path.write_bytes(flipped)
    assert path.stat().st_size == len(original), (
        "bozma uzunlugu degistirdi; test yine boyut yolundan gecer")
    return original


def build_fake_root(tmp_path, contents=None, manifest_rows=None):
    """Uc runtime + on-kontrolun bekledigi diger dosyalarla sahte kok.

    `contents`: dosya adi -> bayt. Verilmeyen runtime varsayilan icerikle
    yazilir. `manifest_rows`: ad -> (boyut, hash) — verilmezse gercek
    degerlerden turetilir.
    """
    contents = dict(contents or {})
    for name in verify_build.RUNTIME_FILES:
        contents.setdefault(name, f"{name} icerigi".encode("utf-8"))

    binary_dir = tmp_path / "bin"
    binary_dir.mkdir(parents=True, exist_ok=True)
    for name, data in contents.items():
        (binary_dir / name).write_bytes(data)

    # On-kontrolun VARLIK aradigi diger dosyalar (icerikleri onemsiz).
    for relative in verify_build.SOURCE_FILES:
        target = tmp_path / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")

    rows = ["# sahte manifest", "# ad | surum | url | boyut | sha256"]
    for name in verify_build.RUNTIME_FILES:
        if manifest_rows is not None and name not in manifest_rows:
            continue
        if manifest_rows is not None:
            size, digest = manifest_rows[name]
        else:
            data = contents[name]
            size, digest = len(data), sha256_of(data)
        rows.append(f"{name} | v1 | https://ornek/{name} | {size} | {digest}")
    manifest = tmp_path / "RUNTIME_MANIFEST.txt"
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(tmp_path), str(manifest)


# --- 1. TEK KAYNAK ----------------------------------------------------

def test_the_runtime_list_has_a_single_source():
    """Ikinci bir liste OLMAMALI; mpv boylece yeniden unutulamaz."""
    assert "mpv-2.dll" in verify_build.RUNTIME_FILES
    assert "yt-dlp.exe" in verify_build.RUNTIME_FILES
    assert "deno.exe" in verify_build.RUNTIME_FILES

    # `SOURCE_FILES` icindeki bin/ girdileri AYNI kaynaktan turemeli.
    in_sources = {os.path.basename(relative)
                  for relative in verify_build.SOURCE_FILES
                  if os.path.dirname(relative) == "bin"}
    assert in_sources == set(verify_build.RUNTIME_FILES), (
        f"bin/ girdileri runtime listesinden turemiyor: {in_sources}")


# --- 2. Dogrulama mekanizmasi -----------------------------------------

def test_correct_runtimes_pass(tmp_path):
    """Dogru dosyalarla dogrulama YESIL kalir."""
    root, manifest = build_fake_root(tmp_path)

    assert verify_build.verify_runtime_binaries(root, manifest, log=lambda *_: None)


def test_a_corrupt_mpv_dll_is_rejected(tmp_path, capsys):
    """ASIL KIRMIZI: bozuk mpv-2.dll on-kontrolden GECMEMELI.

    Bozulma AYNI BOYUTTA yapilir; aksi halde dogrulama boyut adiminda
    durur ve bu test hash yolunu hic sinamamis olur.
    """
    root, manifest = build_fake_root(tmp_path)
    # Manifest dogru dosyaya gore yazildi; simdi DLL icerigi bozuluyor.
    corrupt_same_size(tmp_path / "bin" / "mpv-2.dll")

    # SOZLESME DEGISTI (17 Agustos 2026): hatalar artik VERILEN logger'a
    # gider, kosulsuz `print`e degil. Mesajlar bu yuzden capsys yerine
    # dogrudan toplanir; olculen sey aynidir, kaynagi kesinlesti.
    messages = []
    passed = verify_build.verify_runtime_binaries(
        root, manifest, log=messages.append)
    output = chr(10).join(messages)

    assert not passed, "bozuk mpv-2.dll dogrulamadan gecti"
    assert "SHA-256 DOES NOT MATCH" in output, (
        f"hash yoluna ulasilmadi; uretilen cikti: {output!r}")
    assert "SIZE DOES NOT MATCH" not in output, (
        "boyut yolundan gecti; bozulma ayni boyutta degil")


@pytest.mark.parametrize("name", ["mpv-2.dll", "yt-dlp.exe", "deno.exe"])
def test_every_runtime_is_hash_checked(tmp_path, capsys, name):
    """UCU DE HASH ile denetlenir; biri bile atlanmaz.

    Boyut korumasi ayri bir testte kanitlanir; burada olculen sey YALNIZ
    SHA-256 yoludur, bu yuzden bozulma ayni boyuttadir.
    """
    root, manifest = build_fake_root(tmp_path)
    corrupt_same_size(tmp_path / "bin" / name)

    # SOZLESME DEGISTI (17 Agustos 2026): hatalar artik VERILEN logger'a
    # gider, kosulsuz `print`e degil. Mesajlar bu yuzden capsys yerine
    # dogrudan toplanir; olculen sey aynidir, kaynagi kesinlesti.
    messages = []
    passed = verify_build.verify_runtime_binaries(
        root, manifest, log=messages.append)
    output = chr(10).join(messages)

    assert not passed, f"{name} hash denetimi atlandi"
    assert "SHA-256 DOES NOT MATCH" in output, (
        f"{name} hash yoluna ulasilmadi; cikti: {output!r}")
    assert name in output, f"hata mesaji dosyayi adlandirmiyor: {output!r}"


def test_a_wrong_size_is_rejected_even_when_the_hash_line_exists(
        tmp_path, capsys):
    """Boyut yanlissa reddedilir -- HASH DOGRU olsa bile.

    Bu, hash testinin AYNASIdir: orada icerik bozuk/boyut dogru, burada
    icerik dogru/boyut yanlis. Iki koruma ayri ayri kanitlanir.
    """
    data = b"mpv-2.dll icerigi"
    root, manifest = build_fake_root(
        tmp_path,
        contents={"mpv-2.dll": data},
        manifest_rows={
            # Hash DOGRU, yalnizca boyut yanlis.
            "mpv-2.dll": (len(data) + 999, sha256_of(data)),
            "yt-dlp.exe": (len(b"yt-dlp.exe icerigi"),
                           sha256_of(b"yt-dlp.exe icerigi")),
            "deno.exe": (len(b"deno.exe icerigi"),
                         sha256_of(b"deno.exe icerigi")),
        })

    # SOZLESME DEGISTI (17 Agustos 2026): hatalar artik VERILEN logger'a
    # gider, kosulsuz `print`e degil. Mesajlar bu yuzden capsys yerine
    # dogrudan toplanir; olculen sey aynidir, kaynagi kesinlesti.
    messages = []
    passed = verify_build.verify_runtime_binaries(
        root, manifest, log=messages.append)
    output = chr(10).join(messages)

    assert not passed, "yanlis boyut kabul edildi"
    assert "SIZE DOES NOT MATCH" in output, (
        f"boyut yolu calismadi; cikti: {output!r}")
    assert "SHA-256 DOES NOT MATCH" not in output, (
        "hash dogruyken hash hatasi uretildi")


def test_a_missing_manifest_entry_is_rejected(tmp_path):
    """Manifest kaydi yoksa SESSIZCE gecilmez."""
    root, manifest = build_fake_root(
        tmp_path,
        manifest_rows={
            "yt-dlp.exe": (len(b"yt-dlp.exe icerigi"),
                           sha256_of(b"yt-dlp.exe icerigi")),
            "deno.exe": (len(b"deno.exe icerigi"),
                         sha256_of(b"deno.exe icerigi")),
        })

    messages = []
    assert not verify_build.verify_runtime_binaries(
        root, manifest, log=messages.append), "eksik manifest kaydi kabul edildi"
    assert any("no manifest entry" in m for m in messages), messages


# --- 3. Gercek giris noktasi: `--pre` exit kodu -----------------------

def test_pre_returns_one_when_the_mpv_dll_is_corrupt(
        tmp_path, capsys, monkeypatch):
    """`--pre` bozuk mpv ile exit 1 vermeli (zincir DURMALI).

    Bozulma AYNI BOYUTTA: uctan uca yol da boyut kisayoluna degil, gercek
    SHA-256 denetimine dayanmali.
    """
    root, manifest = build_fake_root(tmp_path)
    corrupt_same_size(tmp_path / "bin" / "mpv-2.dll")
    monkeypatch.setattr(verify_build, "ROOT", root)
    monkeypatch.setattr(verify_build, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["verify_build.py", "--pre"])

    code = verify_build.main()
    output = capsys.readouterr().out

    assert code == 1
    assert "SHA-256 DOES NOT MATCH" in output, (
        f"uctan uca yol hash denetimine ulasmadi; cikti: {output!r}")
    assert "mpv-2.dll" in output


def test_pre_returns_zero_when_every_runtime_matches(tmp_path, monkeypatch):
    """Dogru dosyalarla `--pre` YESIL kalir."""
    root, manifest = build_fake_root(tmp_path)
    monkeypatch.setattr(verify_build, "ROOT", root)
    monkeypatch.setattr(verify_build, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["verify_build.py", "--pre"])

    assert verify_build.main() == 0


# --- 3b. Bozuk manifest: TRACEBACK degil, kontrollu hata --------------

def test_a_missing_manifest_is_fail_closed(tmp_path, capsys):
    """Manifest hic yoksa arac COKMEZ, False doner."""
    root, manifest = build_fake_root(tmp_path)
    os.remove(manifest)

    passed = verify_build.verify_runtime_binaries(root, manifest)
    output = capsys.readouterr().out

    assert passed is False
    assert "Traceback" not in output
    assert "manifest" in output.lower()


def test_invalid_utf8_in_the_manifest_is_fail_closed(tmp_path, capsys):
    """Manifest gecersiz UTF-8 tasirsa arac COKMEZ.

    `manifest_entries()` dosyayi `encoding="utf-8"` ile acar; gecersiz
    bayt `UnicodeDecodeError` firlatir ve bu bir `OSError` DEGILDIR.
    """
    root, manifest = build_fake_root(tmp_path)
    with open(manifest, "ab") as handle:
        handle.write(b"\nbozuk bayt: \xff\xfe\n")

    passed = verify_build.verify_runtime_binaries(root, manifest)
    output = capsys.readouterr().out

    assert passed is False
    assert "Traceback" not in output


def test_pre_returns_one_when_the_manifest_is_unreadable(tmp_path,
                                                         monkeypatch):
    """`--pre` bozuk manifest ile exit 1 verir (traceback degil)."""
    root, manifest = build_fake_root(tmp_path)
    with open(manifest, "ab") as handle:
        handle.write(b"\xff\xfe\n")
    monkeypatch.setattr(verify_build, "ROOT", root)
    monkeypatch.setattr(verify_build, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["verify_build.py", "--pre"])

    assert verify_build.main() == 1


# --- 3c. Logger sozlesmesi: HATA da verilen log'a gider ---------------

def test_error_messages_go_to_the_injected_logger(tmp_path, capsys):
    """`log=` verildiginde HATA mesajlari da oraya gider.

    Ilk surumde `fail()` kosulsuz `print` kullaniyordu: cagiran bir
    logger verse bile hatalar stdout'a KACIYORDU ve toplanamiyordu.
    """
    root, manifest = build_fake_root(tmp_path)
    corrupt_same_size(tmp_path / "bin" / "mpv-2.dll")
    messages = []

    passed = verify_build.verify_runtime_binaries(
        root, manifest, log=messages.append)
    leaked = capsys.readouterr().out

    assert passed is False
    assert any("SHA-256 DOES NOT MATCH" in m for m in messages), (
        f"hata verilen logger'a gitmedi: {messages}")
    assert "SHA-256 DOES NOT MATCH" not in leaked, (
        f"hata stdout'a kacti: {leaked!r}")


def test_a_missing_manifest_entry_also_reaches_the_logger(tmp_path, capsys):
    root, manifest = build_fake_root(
        tmp_path,
        manifest_rows={"yt-dlp.exe": (len(b"yt-dlp.exe icerigi"),
                                      sha256_of(b"yt-dlp.exe icerigi"))})
    messages = []

    verify_build.verify_runtime_binaries(root, manifest, log=messages.append)
    leaked = capsys.readouterr().out

    assert any("no manifest entry" in m for m in messages), messages
    assert "no manifest entry" not in leaked


def test_the_default_logger_is_still_print(tmp_path, capsys):
    """`log=` verilmezse davranis DEGISMEZ: stdout'a yazar."""
    root, manifest = build_fake_root(tmp_path)
    corrupt_same_size(tmp_path / "bin" / "mpv-2.dll")

    verify_build.verify_runtime_binaries(root, manifest)

    assert "SHA-256 DOES NOT MATCH" in capsys.readouterr().out


# --- 4. Gercek depo dosyalari -----------------------------------------

def test_the_real_repository_runtimes_still_verify():
    """SOZLESME 5: mevcut dogru dosyalarla `--pre` YESIL kalmali.

    Gercek dosyalar okunur ama KOPYALANMAZ; `digest()` parcali okur.
    """
    if not all(os.path.isfile(os.path.join(verify_build.ROOT, "bin", name))
               for name in verify_build.RUNTIME_FILES):
        pytest.skip("runtime ikilileri bu makinede yok")

    assert verify_build.verify_runtime_binaries(log=lambda *_: None)
