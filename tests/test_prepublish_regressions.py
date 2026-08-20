# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Yayin oncesi KAPI: `packaging/prepublish.py`.

NEDEN AYRI BIR KAPI (olculdu, 17 Agustos 2026):
`build_release.bat` tag'den tamamen habersizdir (`git`/`gh` gecmez) ve
`check_publishable.py` calisirken tag HENUZ YOKTUR.

OLCULEN OLGULAR (salt-okunur):

    v0.35 -> 2804c2f = 45de83c^   snapshot'inda APP_VERSION v0.34
    v0.36 -> 5b987d1 = 8284771^   snapshot'inda APP_VERSION v0.35
    release metadata: targetCommitish = master

CIKARIM (KANIT DEGIL): bu dizilim, bump commit'i uzaga ulasmadan release
olusturuldugunda beklenen sonuctur. Etiketin ne zaman atildigi
GOZLENMEDI.

OLCULMEDI: release EXE'lerinin IC surumu acilip bakilmadi; paket icerigi
hakkinda iddia yoktur.

Dogrulama bu yuzden build zincirine BAGLANMAZ; publish'ten HEMEN ONCE
calisan ayri bir kapidir.

KAPI FAIL-CLOSED'DUR ve AG KULLANMAZ. Hicbir Git YAZMA komutu
calistirmaz; tag olusturmaz, push etmez, release acmaz.

Testler gecici Git deposu + gecici anahtar kullanir; gercek tag'lere,
gercek artifact'lere ve yayinci anahtarina DOKUNMAZ.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packaging"))

import prepublish

from app import release_signature


CONFIG_TEMPLATE = '''APP_NAME = "MLC Player"
APP_VERSION = "{version}"
'''

ISS_TEMPLATE = '''#define MyAppVersion "{version}"
VersionInfoVersion={windows}
VersionInfoProductName=MLC Player
VersionInfoProductVersion={windows}
'''

MIRROR_CONTENTS = {
    "mpv-source.tar.gz": b"sahte mpv kaynak arsivi",
    "ffmpeg-source.tar.xz": b"sahte ffmpeg kaynak arsivi",
    "build-recipe-source.zip": b"sahte build tarifi",
}


def windows_form(version):
    parts = version.lstrip("v").split(".")
    return ".".join((parts + ["0", "0", "0"])[:4])


def git(repo, *args, identity=False):
    command = ["git"]
    if identity:
        command += ["-c", "user.name=MLC Test",
                    "-c", "user.email=test@example.invalid"]
    command += list(args)
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{' '.join(args)} basarisiz: {result.stderr.strip()}")
    return result.stdout.strip()


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def signing_key(monkeypatch):
    """Gecici yayinci anahtari. GERCEK anahtar KULLANILMAZ/OKUNMAZ."""
    private = Ed25519PrivateKey.generate()
    public = base64.b64encode(
        private.public_key().public_bytes_raw()).decode()
    monkeypatch.setattr(release_signature, "RELEASE_PUBLIC_KEY", public)
    return private


def write_signature(private, exe_path):
    digest = sha256_of(exe_path.read_bytes())
    signature = private.sign(digest.encode("ascii"))
    sig_path = exe_path.with_name(exe_path.name + ".sig")
    sig_path.write_text(base64.b64encode(signature).decode(), encoding="ascii")
    return sig_path


@pytest.fixture
def release(tmp_path, signing_key):
    """Tam ve GECERLI bir yayin adayi kurar; her sey yerinde."""
    def build(version="v0.37", tag=None, tag_version=None):
        repo = tmp_path / "depo"
        (repo / "app").mkdir(parents=True)
        (repo / "packaging").mkdir(parents=True)
        (repo / "installer_output").mkdir(parents=True)
        (repo / "source_mirror").mkdir(parents=True)
        (repo / "bin").mkdir(parents=True)
        git(str(repo), "init", "-q")

        def write_sources(value):
            (repo / "app" / "config.py").write_text(
                CONFIG_TEMPLATE.format(version=value), encoding="utf-8")
            (repo / "packaging" / "MLCPlayer.iss").write_text(
                ISS_TEMPLATE.format(version=value,
                                    windows=windows_form(value)),
                encoding="utf-8")

        # Artifact ve mirror dosyalari izlenmez; aksi halde calisma agaci
        # kirli sayilirdi.
        (repo / ".gitignore").write_text(
            "installer_output/\nsource_mirror/\nbin/\n", encoding="utf-8")

        sources = []
        for name, data in MIRROR_CONTENTS.items():
            (repo / "source_mirror" / name).write_bytes(data)
            sources.append({
                "name": name,
                "url": f"https://github.com/example/source/{name}",
                "size": len(data),
                "sha256": sha256_of(data),
            })
        (repo / "packaging" / "corresponding_sources.json").write_text(
            json.dumps({"schema": 1, "status": "ready", "blockers": [],
                        "sources": sources}), encoding="utf-8")

        chosen_tag = tag or version
        if tag_version is not None:
            write_sources(tag_version)
            git(str(repo), "add", "-A")
            git(str(repo), "commit", "-q", "-m", tag_version, identity=True)
            git(str(repo), "tag", chosen_tag)
            write_sources(version)
            git(str(repo), "add", "-A")
            git(str(repo), "commit", "-q", "-m", version, identity=True)
        else:
            write_sources(version)
            git(str(repo), "add", "-A")
            git(str(repo), "commit", "-q", "-m", version, identity=True)
            git(str(repo), "tag", chosen_tag)

        for stem in ("MLCPlayer_Setup", "MLCPlayer_InternetVideo"):
            exe = repo / "installer_output" / f"{stem}_{version}.exe"
            exe.write_bytes(f"{stem} {version} govdesi".encode("utf-8"))
            write_signature(signing_key, exe)
        return str(repo)
    return build


# --- 1. Dogru durum ---------------------------------------------------

def test_a_complete_release_candidate_passes(release, capsys):
    repo = release()

    assert prepublish.run("v0.37", repo) is True
    assert "OK" in capsys.readouterr().out


def test_assets_are_derived_and_listed(release, capsys):
    """Dort installer girdisi ve sozlesmedeki kaynaklar raporlanir."""
    repo = release()
    assets = prepublish.expected_assets("v0.37", repo)

    assert len(assets) == 4 + len(MIRROR_CONTENTS)

    prepublish.run("v0.37", repo)
    output = capsys.readouterr().out
    for path in assets:
        assert os.path.basename(path) in output, f"raporda yok: {path}"


def test_the_mirror_names_come_from_the_source_contract(release):
    repo = release()
    assets = [os.path.basename(p)
              for p in prepublish.expected_assets("v0.37", repo)]

    for name in MIRROR_CONTENTS:
        assert name in assets, f"{name} beklenen varliklarda yok"


# --- 2. Calisma agaci TEMIZ olmali ------------------------------------

def test_a_staged_change_is_rejected(release, capsys):
    repo = release()
    (open(os.path.join(repo, "yeni.txt"), "w")).write("x")
    git(repo, "add", "yeni.txt")

    assert prepublish.run("v0.37", repo) is False
    assert "calisma agaci" in capsys.readouterr().out.lower()


def test_a_tracked_modification_is_rejected(release, capsys):
    repo = release()
    with open(os.path.join(repo, "app", "config.py"), "a",
              encoding="utf-8") as handle:
        handle.write("# sonradan\n")

    assert prepublish.run("v0.37", repo) is False
    assert "calisma agaci" in capsys.readouterr().out.lower()


def test_an_unignored_untracked_file_is_rejected(release):
    repo = release()
    with open(os.path.join(repo, "artik.txt"), "w", encoding="utf-8") as h:
        h.write("izlenmiyor ama ignore da edilmiyor\n")

    assert prepublish.run("v0.37", repo) is False


def test_ignored_files_do_not_make_the_tree_dirty(release):
    """`installer_output` ve `source_mirror` ignore'dur; kapiyi kapatmaz."""
    repo = release()

    assert prepublish.run("v0.37", repo) is True


# --- 3. Dort artifact ZORUNLU -----------------------------------------

@pytest.mark.parametrize("missing", [
    "MLCPlayer_Setup_v0.37.exe",
    "MLCPlayer_Setup_v0.37.exe.sig",
    "MLCPlayer_InternetVideo_v0.37.exe",
    "MLCPlayer_InternetVideo_v0.37.exe.sig",
])
def test_each_missing_installer_artifact_fails(release, capsys, missing):
    repo = release()
    os.remove(os.path.join(repo, "installer_output", missing))

    assert prepublish.run("v0.37", repo) is False
    assert missing in capsys.readouterr().out


@pytest.mark.parametrize("missing", sorted(MIRROR_CONTENTS))
def test_each_missing_mirror_asset_fails(release, capsys, missing):
    repo = release()
    os.remove(os.path.join(repo, "source_mirror", missing))

    assert prepublish.run("v0.37", repo) is False
    assert missing in capsys.readouterr().out


# --- 4. Mirror BUTUNLUGU ----------------------------------------------

def test_a_same_size_corrupt_mirror_asset_fails_on_the_hash(release, capsys):
    """Ayni boyutta bozulma: boyut yolu degil HASH yolu yakalamali.

    Iddia KESINDIR. Ilk surumde `"boyut" not in out or "SHA-256" in out`
    yaziyordu; ikinci kosul her zaman dogru oldugu icin ifade her seyi
    kabul ediyordu ve boyut kisayolundan gecilse bile YESIL kalirdi.
    """
    repo = release()
    target = os.path.join(repo, "source_mirror", "ffmpeg-source.tar.xz")
    original = open(target, "rb").read()
    flipped = bytes([original[0] ^ 0xFF]) + original[1:]
    open(target, "wb").write(flipped)
    assert os.path.getsize(target) == len(original)

    passed = prepublish.run("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "SHA-256 UYUSMUYOR" in output, f"hash yoluna ulasilmadi: {output!r}"
    assert "boyut UYUSMUYOR" not in output, (
        "boyut yolundan gecti; bozulma ayni boyutta degil")


# --- 4b. Bozuk girdiler TRACEBACK degil, kontrollu hata ----------------

def test_a_signature_with_non_ascii_bytes_is_fail_closed(release, capsys):
    """`.sig` ASCII disi bayt tasirsa arac COKMEZ, False doner.

    `open(..., encoding="ascii")` `UnicodeDecodeError` firlatir; bu bir
    `OSError` DEGILDIR (ValueError soyundan). Yalniz `OSError` yakalayan
    surum burada traceback ile duserdi.
    """
    repo = release()
    sig = os.path.join(repo, "installer_output",
                       "MLCPlayer_Setup_v0.37.exe.sig")
    with open(sig, "wb") as handle:
        handle.write(b"\xff\xfe bozuk bayt \x9e")

    passed = prepublish.run("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "imza" in output.lower()
    assert "Traceback" not in output


def test_a_signature_with_non_ascii_bytes_exits_one(release):
    """Ayni durum giris noktasinda exit 1 uretir."""
    repo = release()
    sig = os.path.join(repo, "installer_output",
                       "MLCPlayer_InternetVideo_v0.37.exe.sig")
    with open(sig, "wb") as handle:
        handle.write(b"\xc3\x28 gecersiz")

    assert prepublish.main(["--tag", "v0.37"], repo) == 1


def test_a_non_numeric_source_size_is_fail_closed(release, capsys):
    """Manifest `size` alani sayisal degilse arac COKMEZ, False doner.

    `fetch_sources.plan()` icinde `int(size)` `ValueError` firlatir;
    yalniz `OSError` yakalayan surum traceback ile duserdi.
    """
    repo = release()
    manifest = os.path.join(repo, "packaging",
                            "corresponding_sources.json")
    source = {"name": "source.tar.gz", "url": "https://github.com/x/y",
              "size": "BOYUT_DEGIL", "sha256": "0" * 64}
    with open(manifest, "w", encoding="utf-8") as handle:
        json.dump({"schema": 1, "status": "ready", "blockers": [],
                   "sources": [source]}, handle)

    passed = prepublish.run("v0.37", repo)
    output = capsys.readouterr().out

    assert passed is False
    assert "kaynak sozlesmesi" in output.lower()
    assert "Traceback" not in output


def test_a_non_numeric_source_size_exits_one(release):
    repo = release()
    manifest = os.path.join(repo, "packaging",
                            "corresponding_sources.json")
    with open(manifest, "w", encoding="utf-8") as handle:
        json.dump({"schema": 1, "status": "ready", "blockers": [],
                   "sources": [{"name": "x", "url": "https://github.com/x",
                                "size": "???", "sha256": "abc"}]}, handle)

    assert prepublish.main(["--tag", "v0.37"], repo) == 1


def test_a_missing_source_contract_is_fail_closed(release, capsys):
    """Manifest hic yoksa da kontrollu hata."""
    repo = release()
    os.remove(os.path.join(repo, "packaging",
                           "corresponding_sources.json"))

    assert prepublish.run("v0.37", repo) is False
    assert "Traceback" not in capsys.readouterr().out


def test_a_wrong_size_mirror_asset_fails(release, capsys):
    repo = release()
    target = os.path.join(repo, "source_mirror", "ffmpeg-source.tar.xz")
    open(target, "ab").write(b"fazladan")

    assert prepublish.run("v0.37", repo) is False
    assert "boyut" in capsys.readouterr().out.lower()


# --- 5. Imzalar KRIPTOGRAFIK olarak dogrulanir ------------------------

def test_a_corrupt_signature_is_rejected(release, capsys):
    repo = release()
    sig = os.path.join(repo, "installer_output",
                       "MLCPlayer_Setup_v0.37.exe.sig")
    open(sig, "w", encoding="ascii").write("Ym96dWsgaW16YQ==")

    assert prepublish.run("v0.37", repo) is False
    assert "imza" in capsys.readouterr().out.lower()


def test_a_signature_for_a_different_exe_is_rejected(release, signing_key,
                                                     capsys):
    """BASKA bir EXE'nin gecerli imzasi kabul EDILMEZ.

    Imza kriptografik olarak saglamdir ama BU dosyanin ozetine ait
    degildir; yalnizca varlik denetimi bunu KACIRIRDI.
    """
    repo = release()
    other_digest = sha256_of(b"tamamen baska bir kurulum")
    signature = signing_key.sign(other_digest.encode("ascii"))
    sig = os.path.join(repo, "installer_output",
                       "MLCPlayer_Setup_v0.37.exe.sig")
    open(sig, "w", encoding="ascii").write(
        base64.b64encode(signature).decode())

    assert prepublish.run("v0.37", repo) is False
    assert "imza" in capsys.readouterr().out.lower()


def test_a_modified_exe_invalidates_its_signature(release):
    """EXE degisirse imza artik tutmaz."""
    repo = release()
    exe = os.path.join(repo, "installer_output", "MLCPlayer_Setup_v0.37.exe")
    open(exe, "ab").write(b"sonradan eklendi")

    assert prepublish.run("v0.37", repo) is False


# --- 6. Tag butunlugu (verify_release_ref uzerinden) ------------------

def test_a_tag_on_an_older_commit_fails(release, capsys):
    """Tarihsel kusurun birebir modeli: tag = bump^."""
    repo = release(version="v0.37", tag="v0.37", tag_version="v0.36")

    assert prepublish.run("v0.37", repo) is False
    assert "APP_VERSION" in capsys.readouterr().out


def test_a_missing_tag_fails(release):
    repo = release()
    git(repo, "tag", "-d", "v0.37")

    assert prepublish.run("v0.37", repo) is False


# --- 7. AG YOK, GIT YAZMA YOK -----------------------------------------

GIT_WRITE_VERBS = {
    "tag", "push", "commit", "checkout", "switch", "reset", "restore",
    "stash", "clean", "add", "rm", "mv", "fetch", "pull", "clone",
    "update-index", "gc", "prune",
}


def test_no_git_write_command_is_ever_run(release, monkeypatch):
    repo = release()
    seen = []
    original = subprocess.run

    def recording(command, **kwargs):
        seen.append(list(command))
        return original(command, **kwargs)

    monkeypatch.setattr(prepublish.subprocess, "run", recording)
    monkeypatch.setattr(
        prepublish.verify_release_ref.subprocess, "run", recording)
    prepublish.run("v0.37", repo)

    assert seen, "hic git cagrisi yapilmadi"
    for command in seen:
        assert command[0] == "git", command
        verbs = GIT_WRITE_VERBS & set(command[1:])
        assert not verbs, f"YAZMA komutu calisti: {command} ({verbs})"


def test_no_network_call_is_made(release, monkeypatch):
    """Kapi AG KULLANMAZ; herhangi bir baglanti girisimi testi dusurur."""
    import socket
    import urllib.request

    def forbidden(*args, **kwargs):
        raise AssertionError("kapi ag kullandi")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    repo = release()

    assert prepublish.run("v0.37", repo) is True


# --- 8. Giris noktasi -------------------------------------------------

def test_main_requires_an_explicit_tag(release):
    repo = release()

    assert prepublish.main([], repo) == 1


def test_main_returns_zero_when_everything_is_in_place(release):
    repo = release()

    assert prepublish.main(["--tag", "v0.37"], repo) == 0


def test_main_returns_one_on_any_failure(release):
    repo = release()
    os.remove(os.path.join(repo, "installer_output",
                           "MLCPlayer_Setup_v0.37.exe.sig"))

    assert prepublish.main(["--tag", "v0.37"], repo) == 1
