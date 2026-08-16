"""Test harness'i GERCEK kullanici ayarlarina yazmamali.

OLCULEN KUSUR (16 Agustos 2026): child betikler
`QSettings.setDefaultFormat(IniFormat)` + `QSettings.setPath(...)` cagiriyordu
ama Qt 6'da `QSettings(org, app)` yapicisi `defaultFormat`'i YOK SAYIYOR ve
NativeFormat ile dogrudan HKCU'ya yaziyor. Sonuc: gorsel kabul kosumunun
PROBE_GREEN degeri kullanicinin gercek altyazi rengine sizdi; izole dizinde
(`%TEMP%\\mlc_subtitle_settings`) 439 klasorun hepsi BOS kaldi.

Kanit (probe):
    setDefaultFormat sonrasi = Format.IniFormat
    QSettings(org, app)      -> Format.NativeFormat \\HKEY_CURRENT_USER\\...

Bu testler alt surecte kosar: `setDefaultFormat`/`setPath` sureç genelinde
kalici Qt durumudur, test surecinde birakilamaz. Gercek kayit defterine de
BU testler hicbir sey yazmaz; yalnizca izole dizine yazip dogrular.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SENTINEL = "#FF00FF00-ISOLATION-PROBE"
PROBE_GROUP = "isolation_probe"


def _run_child(body: str, tmp_path: Path) -> dict:
    """Alt surecte Qt kodu kosar, sonucu JSON olarak dondurur."""
    script = textwrap.dedent(f"""
        import json, os, sys
        sys.path.insert(0, {str(ROOT)!r})
        from PyQt6.QtCore import QSettings
        {body}
    """)
    script_path = tmp_path / "isolation_child.py"
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script_path)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def _registry_has_probe() -> bool:
    """Gercek kullanici anahtarinda probe grubu olustu mu?"""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\MLCPlayer\MLCPlayer\{PROBE_GROUP}"):
            return True
    except FileNotFoundError:
        return False


def test_isolated_settings_do_not_touch_real_registry(tmp_path):
    """Izolasyon kurulunca yazim izole dosyaya gider, kayit defterine GITMEZ."""
    assert not _registry_has_probe(), (
        "Test oncesi gercek kayit defterinde probe grubu var; onceki bir "
        "kosum sizdirmis olabilir.")

    settings_dir = tmp_path / "isolated"
    settings_dir.mkdir()
    result = _run_child(f"""
        from app.settings_store import user_settings
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,
                          QSettings.Scope.UserScope, {str(settings_dir)!r})
        s = user_settings()
        s.setValue("{PROBE_GROUP}/sentinel", "{SENTINEL}")
        s.sync()
        print(json.dumps({{"format": str(s.format()),
                          "fileName": s.fileName()}}))
    """, tmp_path)

    assert "IniFormat" in result["format"], result
    written = [p for p in settings_dir.rglob("*.ini")]
    assert written, f"izole dizine hic .ini yazilmadi: {settings_dir}"
    assert any(SENTINEL in p.read_text(encoding="utf-8") for p in written)
    assert not _registry_has_probe(), (
        "IZOLASYON KACAGI: yazim gercek kayit defterine gitti.")


def test_product_run_still_uses_native_settings(tmp_path):
    """Izolasyon YOKKEN urun normal davranisini korur (HKCU, NativeFormat).

    Yazim yapilmaz; yalnizca hedefin dogru oldugu dogrulanir.
    """
    result = _run_child("""
        from app.settings_store import user_settings
        s = user_settings()
        print(json.dumps({"format": str(s.format()),
                          "fileName": s.fileName()}))
    """, tmp_path)

    assert "NativeFormat" in result["format"], result
    assert result["fileName"].endswith(r"Software\MLCPlayer\MLCPlayer"), result


def test_product_code_has_single_settings_entry_point():
    """Urun kodu QSettings'i dogrudan kurmaz; hepsi tek yardimcidan gecer.

    Aksi halde ayni kacak yeni bir cagri yerinde sessizce geri gelir.
    """
    offenders = []
    for path in (ROOT / "app").glob("*.py"):
        if path.name == "settings_store.py":
            continue
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if "QSettings(" in line and "user_settings" not in line:
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, offenders
