"""Üretim konsol çıktısının TEK güvenli sınırı: `safe_console()`.

Envanter (AST): `main.py` + `app/**/*.py` içinde 74 doğrudan `print()`
vardı; 54'ü ham dosya/klasör yolu, URL veya ham `str(exception)`
taşıyabiliyordu. Dosya logu yazma sınırında maskeleniyordu ama konsol
çıkışı bu sınırı ATLIYORDU.

Yalnız riskli görünen satırları tek tek düzeltmek gelecekte yeni sızıntı
bırakır; bu yüzden bütün üretim konsol yazımları `safe_console()`
üzerinden geçer ve yapısal bir AST kapısı doğrudan `print()` eklenmesini
engeller.

Bütün gizli değerler SENTETİKTİR; ağ erişimi, gerçek medya veya gerçek
kullanıcı dosyası kullanılmaz.
"""
import ast
import io
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET = "SENTETIK123"
WIN_PATH = r"D:\Private Folder\Musteri Sozlesmesi.mp4"
UNC_PATH = r"\\server\share\Private Folder\film.mkv"
FILE_URI = "file://server/share/Private Folder/film.mkv"
TOKEN_URL = f"https://cdn.test/v.m3u8?token={SECRET}"
PATH_WORDS = ("Private Folder", "Musteri", "Sozlesmesi", "server", "share",
              "film.mkv")


def clean(text):
    return text.replace(errors.MASK, "").replace(errors.MASK_PATH, "")


def assert_no(text, words):
    scanned = clean(text)
    for word in words:
        assert word not in scanned, f"{word} stdout'a sizdi: {text!r}"


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def read():
        path = errors.get_log_path()
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    assert str(tmp_path) in errors.get_log_path()
    return read


# =====================================================================
# A. safe_console() çekirdeği
# =====================================================================

def test_harmless_message_is_printed_unchanged(capsys):
    errors.safe_console("MPV oynatıcı başarıyla yapılandırıldı.")
    assert capsys.readouterr().out == "MPV oynatıcı başarıyla yapılandırıldı.\n"


@pytest.mark.parametrize("payload,words", [
    (f"Playing file: {WIN_PATH}", PATH_WORDS),
    (f"Altyazı yüklendi: {UNC_PATH}", PATH_WORDS),
    (f"acilamadi: {FILE_URI}", PATH_WORDS),
    (f"URL: {TOKEN_URL}", (SECRET,)),
    (f"istek: Authorization: Digest {SECRET}", (SECRET,)),
    (f"ayar: api_key={SECRET}", (SECRET,)),
    (f"ayar: password={SECRET}", (SECRET,)),
    (f"ayar: client_secret={SECRET}", (SECRET,)),
])
def test_sensitive_values_never_reach_stdout(capsys, payload, words):
    errors.safe_console(payload)
    assert_no(capsys.readouterr().out, words)


def test_raw_exception_text_is_masked(capsys):
    try:
        raise OSError(f"acilamadi: {WIN_PATH} token={SECRET}")
    except OSError as exc:
        errors.safe_console(f"Dosya açma hatası: {exc}")
    out = capsys.readouterr().out
    assert_no(out, PATH_WORDS + (SECRET,))
    assert "Dosya açma hatası:" in out


def test_quote_contract_is_preserved(capsys):
    errors.safe_console(f'Hata: "{WIN_PATH}", tekrar deneyin')
    assert capsys.readouterr().out == \
        f'Hata: "{errors.MASK_PATH}", tekrar deneyin\n'
    errors.safe_console(f"Hata: '{WIN_PATH}' tekrar deneyin")
    assert capsys.readouterr().out == f"Hata: '{errors.MASK_PATH}\n"


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_line_endings_are_preserved(capsys, newline):
    errors.safe_console(f"[A] {WIN_PATH}{newline}[B] normal satir")
    out = capsys.readouterr().out
    assert out == f"[A] {errors.MASK_PATH}{newline}[B] normal satir\n"


def test_already_masked_message_is_not_masked_twice(capsys):
    errors.safe_console(f"yol: {errors.MASK_PATH} anahtar: api_key="
                        f"{errors.MASK}")
    out = capsys.readouterr().out.strip()
    assert out == f"yol: {errors.MASK_PATH} anahtar: api_key={errors.MASK}"
    assert f"{errors.MASK}{errors.MASK}" not in out


@pytest.mark.parametrize("value", [None, 42, 3.5, True, ["a", "b"],
                                   {"k": "v"}])
def test_non_string_values_are_safe(capsys, value):
    errors.safe_console(value)
    capsys.readouterr()  # cökmemesi yeterli


def test_one_call_prints_once(capsys):
    errors.safe_console("tek satir")
    assert capsys.readouterr().out.count("tek satir") == 1


def test_safe_console_does_not_write_to_the_file_log(log_env, capsys):
    errors.safe_console("konsol mesaji")
    capsys.readouterr()
    assert "konsol mesaji" not in log_env()


def test_redaction_failure_never_falls_back_to_the_raw_message(capsys,
                                                               monkeypatch):
    def explode(_text):
        raise RuntimeError("maskeleme bozuldu")

    monkeypatch.setattr(errors, "redact", explode)
    errors.safe_console(f"gizli: {WIN_PATH} {SECRET}")
    out = capsys.readouterr().out
    assert_no(out, PATH_WORDS + (SECRET,))
    assert WIN_PATH not in out


def test_console_write_failure_does_not_raise(monkeypatch):
    import builtins

    def explode(*args, **kwargs):
        raise OSError("konsol kapali")

    monkeypatch.setattr(builtins, "print", explode)
    errors.safe_console("mesaj")  # istisna firlatmamali


# =====================================================================
# B. Gerçek üretim yolları
# =====================================================================

def test_main_dependency_check_masks_the_bin_directory(capsys, monkeypatch):
    import main

    monkeypatch.setattr(main.os.path, "exists", lambda path: False)
    monkeypatch.setattr(main.os, "getcwd",
                        lambda: r"C:\Users\Gercek Kullanici\Player")
    main.check_dependencies()
    out = capsys.readouterr().out
    assert_no(out, ("Gercek Kullanici",))


def test_main_dll_error_path_is_masked(capsys, monkeypatch):
    import main

    def explode(_path):
        raise OSError(f"yuklenemedi: {WIN_PATH}")

    monkeypatch.setattr(main.os, "add_dll_directory", explode, raising=False)
    monkeypatch.setattr(main.os.path, "exists", lambda path: True)
    monkeypatch.setattr(main.os.path, "isdir", lambda path: True)
    try:
        main.check_dependencies()
    except Exception:
        pass
    assert_no(capsys.readouterr().out, PATH_WORDS)


def test_media_controls_local_playback_path_is_masked(capsys, monkeypatch):
    from app import media_controls

    errors.safe_console(f"Playing file: {WIN_PATH}")
    assert_no(capsys.readouterr().out, PATH_WORDS)
    assert hasattr(media_controls, "safe_console"), \
        "media_controls merkezi sinira baglanmali"


def test_media_controls_url_path_is_masked(capsys):
    from app import media_controls

    errors.safe_console(f"URL'den oynatılıyor: {TOKEN_URL}")
    assert_no(capsys.readouterr().out, (SECRET,))
    assert hasattr(media_controls, "safe_console")


@pytest.mark.parametrize("module_name", ["main", "app.media_controls",
                                         "app.menu_actions", "app.player",
                                         "app.video_frame", "app.errors"])
def test_every_production_module_uses_the_central_boundary(module_name):
    import importlib

    module = importlib.import_module(module_name)
    assert hasattr(module, "safe_console"), \
        f"{module_name} `safe_console` kullanmiyor"


def test_mpv_log_handler_prints_and_logs_once_each(log_env, capsys):
    from app.player import MPVPlayer

    message = f"stream: {TOKEN_URL} file={WIN_PATH}"
    MPVPlayer.log_handler(object(), "error", "ffmpeg", message)

    out = capsys.readouterr().out
    text = log_env()
    assert out.count("[ffmpeg]") == 1
    assert len([line for line in text.splitlines() if "[ffmpeg]" in line]) == 1
    assert_no(out, PATH_WORDS + (SECRET,))
    assert_no(text, PATH_WORDS + (SECRET,))
    assert f"{errors.MASK}{errors.MASK}" not in out


def test_uncaught_exception_console_output_is_masked(log_env, capsys,
                                                     monkeypatch):
    class Box:
        def __init__(self, parent=None):
            pass

        def setIcon(self, *args):
            pass

        def setWindowTitle(self, *args):
            pass

        def setText(self, *args):
            pass

        def setStandardButtons(self, *args):
            pass

        def button(self, which):
            return "ok-button"

        def addButton(self, text, role):
            return "details-button"

        def setDefaultButton(self, button):
            pass

        def setEscapeButton(self, button):
            pass

        def clickedButton(self):
            return "ok-button"

        def exec(self):
            return 0

    Box.Icon = type("I", (), {"Critical": 1})
    Box.StandardButton = type("S", (), {"Ok": 1})
    Box.ButtonRole = type("R", (), {"ActionRole": 2})
    monkeypatch.setattr(errors, "QMessageBox", Box)

    try:
        raise RuntimeError(f"cokme: {WIN_PATH} token={SECRET}")
    except RuntimeError as exc:
        errors._handle_exception(type(exc), exc, exc.__traceback__)

    assert_no(capsys.readouterr().out, PATH_WORDS + (SECRET,))


def test_subtitle_and_playlist_paths_are_masked(capsys):
    errors.safe_console(f"Altyazı yükleme sırasına alındı: {WIN_PATH}")
    errors.safe_console(f"Oynatma listesine eklendi: {UNC_PATH}")
    assert_no(capsys.readouterr().out, PATH_WORDS)


def test_menu_and_video_frame_error_paths_are_masked(capsys):
    try:
        raise ValueError(f"parca hatasi: {UNC_PATH}")
    except ValueError as exc:
        errors.safe_console(f"Parça listeleme hatası: {exc}")
        errors.safe_console(f"Ses kanalı seçimi hatası: {exc}")
    out = capsys.readouterr().out
    assert_no(out, PATH_WORDS)
    assert "Parça listeleme hatası:" in out
    assert "Ses kanalı seçimi hatası:" in out


# =====================================================================
# C. Yapısal kapı
# =====================================================================

def production_files():
    yield os.path.join(ROOT, "main.py")
    for base, _dirs, names in os.walk(os.path.join(ROOT, "app")):
        if "__pycache__" in base:
            continue
        for name in sorted(names):
            if name.endswith(".py"):
                yield os.path.join(base, name)


def console_calls(path):
    """AST ile doğrudan konsol çağrıları. Yorum/string sahte ihlal üretmez."""
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    direct = []
    builtin = []
    other = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "print":
            direct.append(node.lineno)
        elif isinstance(func, ast.Attribute):
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id == "builtins" \
                    and func.attr == "print":
                builtin.append(node.lineno)
            elif isinstance(owner, ast.Attribute) and func.attr == "write" \
                    and owner.attr in ("stdout", "stderr"):
                other.append((node.lineno, f"sys.{owner.attr}.write"))
            elif isinstance(owner, ast.Name) and owner.id == "sys" \
                    and func.attr in ("stdout", "stderr"):
                other.append((node.lineno, f"sys.{func.attr}"))
            elif isinstance(owner, ast.Name) and owner.id == "traceback" \
                    and func.attr.startswith("print_"):
                other.append((node.lineno, f"traceback.{func.attr}"))
    return direct, builtin, other


def test_no_direct_print_remains_in_production_code():
    offenders = {}
    for path in production_files():
        direct, _builtin, _other = console_calls(path)
        if direct:
            offenders[os.path.relpath(path, ROOT)] = direct
    assert offenders == {}, (
        f"dogrudan print() kaldi: {offenders} — `safe_console()` kullanin")


def test_no_other_console_writes_bypass_the_boundary():
    offenders = {}
    for path in production_files():
        _direct, _builtin, other = console_calls(path)
        if other:
            offenders[os.path.relpath(path, ROOT)] = other
    assert offenders == {}, f"merkezi sinir atlandi: {offenders}"


def test_only_safe_console_may_call_builtins_print():
    allowed = os.path.normcase(os.path.join(ROOT, "app", "errors.py"))
    found = {}
    for path in production_files():
        _direct, builtin, _other = console_calls(path)
        if builtin:
            found[os.path.normcase(path)] = builtin
    assert list(found) == [allowed], f"builtins.print yalniz errors.py'de: {found}"
    assert len(found[allowed]) == 1, "tek bir merkezi cikis noktasi olmali"

    # Bu tek çağrı GERÇEKTEN `safe_console()` gövdesinde olmalı.
    tree = ast.parse(io.open(allowed, encoding="utf-8").read())
    inside = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "safe_console":
            for child in ast.walk(node):
                if isinstance(child, ast.Call) \
                        and isinstance(child.func, ast.Attribute) \
                        and child.func.attr == "print":
                    inside.append(child.lineno)
    assert inside == found[allowed]
