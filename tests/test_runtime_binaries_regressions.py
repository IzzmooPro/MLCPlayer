"""Paketlenen internet-video calisma zamani: TEK kaynak, sistem fallback YOK.

URUN KARARI: MLC Player resmi `yt-dlp.exe` ve `deno.exe` dosyalarini KENDI
kurulumunda tasir. Kullanicinin bilgisayari taranmaz, sistem PATH'indeki bir
kopya fallback olarak KULLANILMAZ, calisma sirasinda bilesen INDIRILMEZ ve
sistem PATH'i kalici DEGISTIRILMEZ. Guncelleme yalniz MLC Player setup'i ile
gelir; runtime icinde `yt-dlp -U` / `deno upgrade` CALISTIRILMAZ.
"""
import hashlib
import os
import re

import pytest

import app.runtime_binaries as runtime

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(PROJECT, "MLCPlayer.spec")
REQUIREMENTS = os.path.join(PROJECT, "requirements.txt")
MANIFEST = os.path.join(PROJECT, "bin", "RUNTIME_MANIFEST.txt")
TRICKY_DIR = "Program Files (x86)\\MLC Player Türkçe Sürüm"


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture
def bundle(tmp_path):
    """Paketlenmis `bin` dizinini taklit eder."""
    def factory(*names, root=None):
        base = tmp_path / (root or "paket")
        bin_dir = base / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            (bin_dir / name).write_bytes(b"MZ")
        return str(bin_dir)
    return factory


# =====================================================================
# 1. Tek runtime kaynagi
# =====================================================================

def test_both_components_resolve_under_the_same_bin_root(bundle):
    bin_dir = bundle("yt-dlp.exe", "deno.exe")

    paths = runtime.runtime_paths(bin_dir)

    assert paths["yt-dlp"] == os.path.join(bin_dir, "yt-dlp.exe")
    assert paths["deno"] == os.path.join(bin_dir, "deno.exe")
    assert os.path.dirname(paths["yt-dlp"]) == os.path.dirname(paths["deno"])


def test_a_system_copy_is_never_selected(bundle, tmp_path, monkeypatch):
    """Sahte sistem PATH'inde ESKI/kotu bir yt-dlp.exe olsa bile secilmez."""
    system = tmp_path / "sistem"
    system.mkdir()
    (system / "yt-dlp.exe").write_bytes(b"ESKI")
    (system / "deno.exe").write_bytes(b"ESKI")
    monkeypatch.setenv("PATH", str(system))
    bin_dir = bundle("yt-dlp.exe", "deno.exe")

    paths = runtime.runtime_paths(bin_dir)

    for value in paths.values():
        assert str(system) not in value, f"sistem kopyası seçildi: {value}"


def test_a_missing_bundled_component_never_falls_back(bundle, tmp_path,
                                                      monkeypatch):
    system = tmp_path / "sistem"
    system.mkdir()
    (system / "yt-dlp.exe").write_bytes(b"ESKI")
    monkeypatch.setenv("PATH", str(system))
    bin_dir = bundle("deno.exe")          # yt-dlp EKSIK

    missing = runtime.missing_runtime_components(bin_dir)
    paths = runtime.runtime_paths(bin_dir)

    assert missing == ("yt-dlp",)
    assert str(system) not in paths["yt-dlp"]
    assert runtime.internet_video_ready(bin_dir) is False


def test_a_complete_bundle_is_ready(bundle):
    bin_dir = bundle("yt-dlp.exe", "deno.exe")

    assert runtime.missing_runtime_components(bin_dir) == ()
    assert runtime.internet_video_ready(bin_dir) is True


def test_a_path_with_spaces_and_turkish_letters_survives(bundle):
    bin_dir = bundle("yt-dlp.exe", "deno.exe", root=TRICKY_DIR)

    paths = runtime.runtime_paths(bin_dir)

    assert "Program Files (x86)" in paths["yt-dlp"]
    assert "Türkçe Sürüm" in paths["yt-dlp"]
    assert os.path.isfile(paths["yt-dlp"])


# =====================================================================
# 2. MPV'ye verilen EXACT ytdl yolu
# =====================================================================

def test_the_script_opt_carries_the_exact_bundled_path(bundle):
    bin_dir = bundle("yt-dlp.exe", "deno.exe", root=TRICKY_DIR)
    expected = os.path.join(bin_dir, "yt-dlp.exe")

    option = runtime.ytdl_script_opt(bin_dir)

    assert option.startswith("ytdl_hook-ytdl_path=")
    assert option.split("=", 1)[1] == expected


def test_no_script_opt_without_the_bundled_binary(bundle):
    bin_dir = bundle("deno.exe")

    assert runtime.ytdl_script_opt(bin_dir) == ""


def test_the_runtime_module_never_shells_out_or_self_updates():
    """Gercek sozlesme IMPORT'lardir; docstring metni taranmaz.

    Alt surec, ag, registry veya PATH aramasi yapabilmek icin bir modul
    IMPORT edilmek zorundadir. `os` disinda hicbir sey ice aktarilmaz.
    """
    import ast

    tree = ast.parse(read(os.path.join(PROJECT, "app",
                                       "runtime_binaries.py")))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported == {"os"}, f"beklenmeyen import: {sorted(imported)}"
    for forbidden in ("subprocess", "urllib", "requests", "winreg",
                      "shutil", "socket"):
        assert forbidden not in imported


# =====================================================================
# 3. PATH yalniz SUREC icinde ve idempotent
# =====================================================================

def test_the_process_path_gains_the_bin_dir_only_once(monkeypatch, bundle):
    import main

    bin_dir = bundle("yt-dlp.exe", "deno.exe")
    monkeypatch.setenv("PATH", "C:\\Windows\\system32")

    for _ in range(5):
        main.prepend_process_path(bin_dir)

    entries = os.environ["PATH"].split(os.pathsep)
    assert entries.count(bin_dir) == 1, f"PATH çoğaldı: {entries}"
    assert entries[0] == bin_dir


def test_no_permanent_environment_write_exists():
    source = read(os.path.join(PROJECT, "main.py"))

    for forbidden in ("winreg", "setx", "SetEnvironmentVariable",
                      "HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
        assert forbidden not in source, f"kalıcı ortam yazımı: {forbidden}"


# =====================================================================
# 4. Eksik bilesen yerel oynatmayi ENGELLEMEZ
# =====================================================================

def test_a_missing_runtime_never_blocks_local_playback():
    source = read(os.path.join(PROJECT, "main.py"))
    start = source.index("def check_dependencies")
    block = source[start:source.index("\nif __name__", start)]

    assert "yt-dlp" not in block or "return False" not in block.split(
        "yt-dlp")[1][:200], (
        "internet bileşeni eksikken program başlatılmıyor")


def test_the_missing_message_is_safe_and_turkish():
    message = runtime.INTERNET_VIDEO_MISSING_MESSAGE

    assert "MLC Player" in message
    for forbidden in ("Traceback", "pip install", "yt-dlp", "deno", "C:\\",
                      "http"):
        assert forbidden not in message, f"mesajda teknik sızıntı: {forbidden}"
    assert runtime.INTERNET_VIDEO_MISSING_CODE.isupper()


def test_the_status_code_is_safe_for_the_log():
    code = runtime.internet_video_status(os.path.join("yok", "bin"))

    assert code == runtime.INTERNET_VIDEO_MISSING_CODE
    assert "\\" not in code and "/" not in code


# =====================================================================
# 5. requirements ve spec sozlesmesi
# =====================================================================

def test_requirements_no_longer_pulls_python_yt_dlp():
    lines = [line.strip() for line in read(REQUIREMENTS).splitlines()
             if line.strip() and not line.strip().startswith("#")]

    assert not any(line.lower().startswith("yt-dlp") for line in lines), lines
    assert any(line.lower().startswith("python-mpv") for line in lines)


def test_the_spec_is_onedir_with_collect():
    spec = read(SPEC)

    assert "exclude_binaries=True" in spec
    assert "COLLECT(" in spec
    assert "name='MLC Player'" in spec or 'name="MLC Player"' in spec


def test_the_spec_places_the_three_runtime_files_in_internal_bin():
    spec = read(SPEC)

    for name in ("mpv-2.dll", "yt-dlp.exe", "deno.exe"):
        assert f"bin/{name}" in spec, f"spec'te yok: {name}"
    assert "'bin'" in spec or '"bin"' in spec


def test_the_spec_ships_the_license_texts():
    spec = read(SPEC)

    assert "licenses" in spec
    for name in ("yt-dlp-LICENSE.txt", "deno-LICENSE.txt"):
        assert os.path.isfile(os.path.join(PROJECT, "licenses", name)), name


def test_the_spec_no_longer_packages_the_static_import_library():
    assert "libmpv.dll.a" not in read(SPEC)


def test_the_spec_does_not_force_upx_on():
    spec = read(SPEC)

    assert "upx=True" not in spec, "UPX zorla açık"
    assert "upx=False" in spec


def test_the_spec_excludes_tests_and_caches():
    spec = read(SPEC)

    assert "'pytest'" in spec or '"pytest"' in spec


# =====================================================================
# 6. Provenance manifesti
# =====================================================================

def test_the_manifest_records_version_url_size_and_hash():
    text = read(MANIFEST)

    for needed in ("yt-dlp.exe", "deno.exe", "2026.07.04", "v2.9.5",
                   "https://github.com/yt-dlp/yt-dlp/releases/download/",
                   "https://github.com/denoland/deno/releases/download/"):
        assert needed in text, f"manifestte yok: {needed}"
    assert "latest" not in text, "`latest` kalıcı build girdisi olmuş"
    assert len(re.findall(r"\b[0-9a-f]{64}\b", text)) >= 3


@pytest.mark.parametrize("name", ("yt-dlp.exe", "deno.exe"))
def test_the_binary_matches_the_manifest(name):
    path = os.path.join(PROJECT, "bin", name)
    if not os.path.isfile(path):
        pytest.skip(f"BLOCKED: {name} kaynak ağacında yok "
                    "(binary Git'e alınmaz; sahte PASS üretilmez)")
    expected = ""
    for line in read(MANIFEST).splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 4 and parts[0] == name:
            expected = parts[-1].lower()
            break

    assert expected, f"manifestte satır yok: {name}"
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    assert sha.hexdigest().lower() == expected


def test_the_binaries_are_not_tracked_by_git():
    ignore = read(os.path.join(PROJECT, ".gitignore"))

    assert "bin/yt-dlp.exe" in ignore
    assert "bin/deno.exe" in ignore
    # Manifest ve mevcut mpv sözleşmesi izlenmeye DEVAM eder.
    assert "bin/RUNTIME_MANIFEST.txt" not in ignore
    assert "bin/mpv-2.dll" in ignore

# =====================================================================
# 7. GERCEK sistem fallback kapatilmasi (MPV config)
# =====================================================================

def mpv_config(bin_dir):
    """Urunun MPV'ye VERDIGI ytdl kararini uretir."""
    from app.player import build_ytdl_config

    return build_ytdl_config(bin_dir)


def test_a_complete_bundle_enables_site_extraction(bundle):
    bin_dir = bundle("yt-dlp.exe", "deno.exe")

    config = mpv_config(bin_dir)

    assert config["ytdl"] is True
    assert config["script_opts"] == (
        f"ytdl_hook-ytdl_path={os.path.join(bin_dir, 'yt-dlp.exe')}")


def test_a_missing_bundled_ytdlp_disables_site_extraction(bundle, tmp_path,
                                                          monkeypatch):
    """Sahte sistem PATH'inde CALISAN yt-dlp olsa bile acilmaz."""
    system = tmp_path / "sistem"
    system.mkdir()
    (system / "yt-dlp.exe").write_bytes(b"MZ")
    monkeypatch.setenv("PATH", str(system))
    bin_dir = bundle("deno.exe")

    config = mpv_config(bin_dir)

    assert config["ytdl"] is False, "mpv sistem yt-dlp'sini arayabilir"
    assert "script_opts" not in config or "ytdl" not in config["script_opts"]


def test_a_missing_bundled_deno_disables_site_extraction(bundle, tmp_path,
                                                         monkeypatch):
    """yt-dlp paketli ama Deno eksik: sistem Deno'su KULLANILMAZ."""
    system = tmp_path / "sistem"
    system.mkdir()
    (system / "deno.exe").write_bytes(b"MZ")
    monkeypatch.setenv("PATH", str(system))
    bin_dir = bundle("yt-dlp.exe")

    config = mpv_config(bin_dir)

    assert config["ytdl"] is False
    assert "script_opts" not in config or "ytdl" not in config["script_opts"]


def test_an_unresolvable_exact_path_still_disables_site_extraction(
        bundle, tmp_path, monkeypatch):
    """FAIL-CLOSED: paket tam gorunse bile exact yol uretilemezse ytdl KAPALI.

    Ilk varlik kontrolu ile yol uretimi arasinda dosya kaybolabilir. Eskiden
    `ytdl=True` + `script_opts` YOK donuluyordu; bu, mpv'nin varsayilan
    sistem aramasina dusmesine izin verebilirdi.
    """
    import app.player as player_module

    system = tmp_path / "sistem"
    system.mkdir()
    (system / "yt-dlp.exe").write_bytes(b"MZ")
    monkeypatch.setenv("PATH", str(system))
    bin_dir = bundle("yt-dlp.exe", "deno.exe")
    monkeypatch.setattr(player_module, "ytdl_script_opt", lambda _dir: "")

    config = player_module.build_ytdl_config(bin_dir)

    assert config == {"ytdl": False}
    assert "script_opts" not in config


def test_disabling_ytdl_never_disables_plain_network_playback():
    """`ytdl=False` MPV'nin KENDI HTTP/HLS oynatmasini kapatmaz."""
    import inspect

    from app.player import build_ytdl_config

    source = inspect.getsource(build_ytdl_config)
    for forbidden in ("network", "stream-lavf", "demuxer-lavf", "vo=null"):
        assert forbidden not in source, f"ag oynatmasina dokunuldu: {forbidden}"


# =====================================================================
# 8. Guvenli mesaj GERCEK urun zincirine bagli
# =====================================================================

def url_failure_message(monkeypatch, tmp_path, ready):
    """GERCEK zincir: open_url -> update_url_loading -> show_user_error."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget

    import app.media_controls as media_controls

    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.setCentralWidget(QWidget(window))

    class Mpv:
        def play(self, url):
            self.url = url

    class Frame:
        control_overlay = None

    window.mpv_player = Mpv()
    window.video_frame = Frame()
    window.video_frame.placeholder_label = QLabel(window)
    window.duration = 0.0
    window.position = 0.0
    window.is_paused = True
    window._core_idle = False
    window._load_started_at = 0
    window._audio_menu_file = ""
    window._chapter_menu_file = ""
    window._pending_subs = []
    window._url_loading_active = False
    window._url_loading_started_at = 0.0
    window.playlist = []
    window.current_playlist_index = -1
    window.current_file = ""
    window.set_title = lambda: None
    window.add_recent_file = lambda path: None
    window.play_button = type("_B", (), {"setIcon": lambda self, i: None})()
    window.pause_icon = object()
    window.internet_video_ready = ready

    monkeypatch.setattr(media_controls.QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (
                            "https://user:s3cret@site.test/v?token=deadbeef",
                            True)))
    seen = []
    monkeypatch.setattr(media_controls, "show_user_error",
                        lambda player, title, message, **kw:
                        seen.append((title, message, kw)))
    console = []
    monkeypatch.setattr(media_controls, "safe_console", console.append)

    media_controls.open_url(window)
    # MPV GERCEKTEN idle'a dondu ve hicbir ilerleme yok.
    window._core_idle = True
    window._url_loading_started_at -= media_controls.URL_LOAD_GRACE_SECONDS + 1
    for _ in range(5):
        media_controls.update_url_loading(window)

    window.close()
    app.processEvents()
    return seen, console


def test_a_missing_runtime_produces_the_repair_message(monkeypatch, tmp_path):
    seen, console = url_failure_message(monkeypatch, tmp_path, ready=False)

    assert len(seen) == 1, f"mesaj tekrar gosterildi: {len(seen)}"
    title, message, _kw = seen[0]
    assert title == runtime.INTERNET_VIDEO_MISSING_TITLE
    assert message == runtime.INTERNET_VIDEO_MISSING_MESSAGE
    joined = title + message + "\n".join(console)
    for secret in ("s3cret", "token", "deadbeef", "Traceback", "yt-dlp.exe",
                   "deno.exe", "bin\\"):
        assert secret not in joined, f"sizinti: {secret}"


def test_a_ready_runtime_keeps_the_generic_connection_message(monkeypatch,
                                                              tmp_path):
    import app.media_controls as media_controls

    seen, _console = url_failure_message(monkeypatch, tmp_path, ready=True)

    assert len(seen) == 1
    title, message, _kw = seen[0]
    assert title == media_controls.URL_FAILED_TITLE
    assert message == media_controls.URL_FAILED_MESSAGE


def test_the_player_stores_the_runtime_state_as_a_plain_flag():
    import inspect

    from app.player import MPVPlayer

    source = inspect.getsource(MPVPlayer.init_mpv_player)
    assert "internet_video_ready" in source


# =====================================================================
# 9. Ucuncu taraf lisanslari
# =====================================================================

THIRD_PARTY = os.path.join(PROJECT, "licenses",
                           "yt-dlp-THIRD_PARTY_LICENSES.txt")
THIRD_PARTY_SIZE = 231397
THIRD_PARTY_SHA = ("b085c65586a953cdb4b13c6390d63ec984d66912e4b6a19e66ba3582"
                   "f2ed104b")


def test_the_third_party_license_is_present_with_the_exact_bytes():
    assert os.path.isfile(THIRD_PARTY), "ucuncu taraf lisansi pakette yok"
    assert os.path.getsize(THIRD_PARTY) == THIRD_PARTY_SIZE

    sha = hashlib.sha256()
    with open(THIRD_PARTY, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    assert sha.hexdigest().lower() == THIRD_PARTY_SHA


def test_all_three_license_texts_are_packaged():
    spec = read(SPEC)

    for name in ("yt-dlp-LICENSE.txt", "yt-dlp-THIRD_PARTY_LICENSES.txt",
                 "deno-LICENSE.txt"):
        assert os.path.isfile(os.path.join(PROJECT, "licenses", name)), name
        assert name in spec, f"spec paketlemiyor: {name}"


def test_the_manifest_records_the_third_party_license():
    text = read(MANIFEST)

    assert "THIRD_PARTY_LICENSES.txt" in text
    assert str(THIRD_PARTY_SIZE) in text
    assert THIRD_PARTY_SHA in text


def test_the_plan_states_the_combined_executable_licence_correctly():
    plan = read(os.path.join(PROJECT, "docs", "PACKAGING_PLAN.md"))

    assert "GPL-3.0 DEGILDIR" not in plan and "GPL-3.0 değildir" not in plan
    assert "GPLv3+" in plan
    assert "Unlicense" in plan


# =====================================================================
# 10. Spec ve belge determinismi
# =====================================================================

def test_the_spec_pins_the_contents_directory():
    spec = read(SPEC)

    assert "contents_directory='_internal'" in spec or \
        'contents_directory="_internal"' in spec


@pytest.mark.parametrize("relative", (
    os.path.join("docs", "PACKAGING_PLAN.md"),
    os.path.join("bin", "RUNTIME_MANIFEST.txt"),
    os.path.join("bin", "SHA256SUMS.txt"),
))
def test_no_control_characters_in_the_tracked_texts(relative):
    with open(os.path.join(PROJECT, relative), "rb") as handle:
        data = handle.read()

    bad = sorted({byte for byte in data
                  if byte < 32 and byte not in (9, 10, 13)})
    assert bad == [], f"{relative}: kontrol karakteri {[hex(b) for b in bad]}"


def test_the_plan_shows_the_runtime_paths_as_plain_text():
    plan = read(os.path.join(PROJECT, "docs", "PACKAGING_PLAN.md"))

    for name in ("mpv-2.dll", "yt-dlp.exe", "deno.exe"):
        assert f"_internal\\bin\\{name}" in plan, f"duz metin yol yok: {name}"
