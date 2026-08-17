# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Klasik (eski) kabuk hiçbir koşulda GÖRÜNÜR pencere olarak açılmamalı.

Kullanıcının gördüğü eski pencerenin kaynağı ölçülerek kanıtlandı:

    MLCPLAYER_CLASSIC_UI=1 -> cinematic_ui_enabled()=False
                           -> menubar_visible=True (9 menü)
                           -> title_bar=None, control_overlay=None
                           -> classic_control_panel_visible=True (54 px)
                           -> window_visible=True

Bu ortam değişkenini `tests/run_native_overlay_matrix.py` içindeki
`--include-classic` / `diagnostic_classic_video_focus` yolu gerçek Windows
koşumunda veriyordu.

Ürün kararı: sinematik tasarım TEK kullanıcı arayüzüdür. Legacy anahtar
verilse bile ürün sinematik açılır.

NOT: Gizli klasik nesneler (QMenuBar aksiyonları, control_container,
position_slider, volume_slider) uyumluluk katmanı olarak YAŞAMAYA devam eder;
yalnızca kullanıcıya görünmezler. Bu testler onların varlığını da korur.
"""
import json
import os
import subprocess
import sys

import pytest

CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "default_ui_child.py")
MAIN_CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "main_entry_child.py")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "run_native_overlay_matrix.py")
SMOKE_CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "native_overlay_smoke_child.py")

# Kullanıcının deneyebileceği her türlü legacy değer.
LEGACY_VALUES = ("1", "true", "TRUE", "yes", "on", "0", "false", "", "evet")


def run_child(script, settings_dir, env_overrides=None):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MLC_DEFAULT_UI_SETTINGS"] = str(settings_dir)
    for name in ("MLCPLAYER_OVERLAY_PREVIEW", "MLCPLAYER_CLASSIC_UI"):
        env.pop(name, None)
    env.update(env_overrides or {})
    proc = subprocess.run([sys.executable, script], env=env, cwd=PROJECT_ROOT,
                          capture_output=True, text=True, timeout=180)
    prefix = "DEFAULT_UI_JSON "
    line = next((l for l in proc.stdout.splitlines() if l.startswith(prefix)),
                None)
    if line is None:
        raise AssertionError(
            f"Ölçüm alınamadı (exit={proc.returncode})\n"
            f"stdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}")
    return json.loads(line[len(prefix):])


# --- 1. Ürün kapısı: legacy değer ne olursa olsun sinematik ---

def test_cinematic_is_enabled_when_no_env_is_set(monkeypatch):
    from app.config import cinematic_ui_enabled

    monkeypatch.delenv("MLCPLAYER_CLASSIC_UI", raising=False)
    assert cinematic_ui_enabled() is True


@pytest.mark.parametrize("value", LEGACY_VALUES)
def test_legacy_classic_env_can_no_longer_disable_cinematic(monkeypatch, value):
    from app.config import cinematic_ui_enabled

    monkeypatch.setenv("MLCPLAYER_CLASSIC_UI", value)
    assert cinematic_ui_enabled() is True, (
        f"MLCPLAYER_CLASSIC_UI={value!r} hâlâ klasik kabuğu açıyor")


# --- 2. Gerçek MPVPlayer: legacy env verilse bile sinematik ---

@pytest.fixture(scope="module")
def legacy_classic_one(tmp_path_factory):
    return run_child(CHILD, tmp_path_factory.mktemp("legacy-classic-1"),
                     {"MLCPLAYER_CLASSIC_UI": "1"})


@pytest.fixture(scope="module")
def legacy_classic_true(tmp_path_factory):
    return run_child(CHILD, tmp_path_factory.mktemp("legacy-classic-true"),
                     {"MLCPLAYER_CLASSIC_UI": "true"})


@pytest.fixture(scope="module")
def main_entry_with_legacy(tmp_path_factory):
    return run_child(MAIN_CHILD, tmp_path_factory.mktemp("main-legacy"),
                     {"MLCPLAYER_CLASSIC_UI": "1"})


@pytest.mark.parametrize("fixture_name",
                         ("legacy_classic_one", "legacy_classic_true"))
def test_player_stays_cinematic_with_legacy_env(request, fixture_name):
    report = request.getfixturevalue(fixture_name)

    assert report["cinematic_ui_enabled"] is True
    assert report["frameless"] is True
    assert report["has_title_bar"] is True
    assert report["title_bar_visible"] is True
    assert report["overlay_created"] is True


@pytest.mark.parametrize("fixture_name",
                         ("legacy_classic_one", "legacy_classic_true"))
def test_classic_menu_bar_is_never_visible(request, fixture_name):
    report = request.getfixturevalue(fixture_name)

    assert report["menu_bar_visible"] is False, (
        "klasik QMenuBar kullanıcıya görünüyor")


@pytest.mark.parametrize("fixture_name",
                         ("legacy_classic_one", "legacy_classic_true"))
def test_classic_control_panel_is_never_visible(request, fixture_name):
    report = request.getfixturevalue(fixture_name)

    assert report["control_container_visible"] is False, (
        "eski klasik kontrol paneli kullanıcıya görünüyor")
    assert report["control_container_height"] == 0


def test_main_entry_is_cinematic_even_with_legacy_env(main_entry_with_legacy):
    """`python main.py` legacy env ile bile modern kabuğu kullanmalı."""
    report = main_entry_with_legacy

    assert report["cinematic_ui_enabled"] is True
    assert report["has_title_bar"] is True
    assert report["overlay_created"] is True
    assert report["menu_bar_visible"] is False


# --- 3. Uyumluluk katmanı korunmalı (topluca silinmemeli) ---

def test_hidden_compatibility_objects_still_exist(legacy_classic_one):
    report = legacy_classic_one

    assert report["has_control_container"] is True
    assert report["has_position_slider"] is True
    assert report["has_volume_slider"] is True
    assert report["menu_bar_action_count"] > 0, (
        "menü aksiyonları uyumluluk katmanıdır; kaldırılmamalı")


# --- 3b. Kaynak yorumları çalışan ürün kararıyla çelişmemeli ---

def test_player_source_has_no_stale_diagnostic_classic_comment():
    """Kaynakta 'teşhis amaçlı klasik mod' iddiası kalmamalı."""
    path = os.path.join(PROJECT_ROOT, "app", "player.py")
    source = open(path, encoding="utf-8").read()

    stale = [line.strip() for line in source.splitlines()
             if "Teşhis amaçlı klasik" in line
             or "teşhis anahtarıyla açılır" in line]
    assert not stale, f"geçersiz klasik mod yorumu kaldı: {stale}"


# --- 4. Native matris: görünür klasik senaryo kalmamalı ---

def test_matrix_has_no_visible_classic_scenario():
    import importlib.util

    spec = importlib.util.spec_from_file_location("matrix_mod", MATRIX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cases = module.base_matrix("dummy.mkv")
    classic = [case for case in cases if case.get("ui") == "classic"]
    assert not classic, f"matriste görünür klasik senaryo var: {classic}"
    names = [case["name"] for case in cases]
    assert "diagnostic_classic_video_focus" not in names
    assert len(cases) == 6, f"varsayılan sinematik matris 6 senaryo olmalı: {names}"


def test_matrix_no_longer_exposes_include_classic_option():
    source = open(MATRIX, encoding="utf-8").read()
    assert "--include-classic" not in source, (
        "--include-classic eski player penceresini açabiliyor; kaldırılmalı")
    assert "include_classic" not in source


def test_matrix_never_sets_the_classic_env():
    source = open(MATRIX, encoding="utf-8").read()
    assert 'env["MLCPLAYER_CLASSIC_UI"] = "1"' not in source, (
        "matris hâlâ klasik kabuğu açan env'i ayarlıyor")


def test_native_smoke_child_never_sets_the_classic_env():
    source = open(SMOKE_CHILD, encoding="utf-8").read()
    assert 'env["MLCPLAYER_CLASSIC_UI"] = "1"' not in source
    assert 'os.environ["MLCPLAYER_CLASSIC_UI"] = "1"' not in source


def test_base_matrix_signature_has_no_classic_switch():
    import importlib.util
    import inspect

    spec = importlib.util.spec_from_file_location("matrix_mod2", MATRIX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    params = inspect.signature(module.base_matrix).parameters
    assert "include_classic" not in params
