"""Sinematik arayüzün ürünün VARSAYILANI olduğunu doğrulayan testler.

Normal `python main.py` çalıştırmasında hiçbir ortam değişkeni gerekmemeli.
Klasik görünüm yalnızca açık teşhis anahtarı MLCPLAYER_CLASSIC_UI=1 ile gelir.
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

UI_ENV_VARS = ("MLCPLAYER_OVERLAY_PREVIEW", "MLCPLAYER_CLASSIC_UI")


# ÖLÇÜLEN SÜRE: child tek başına 0,3-0,5 sn (11/11 koşum), pytest altında
# 1,4 sn (3/3 koşum). Eski 180 sn sınırı gerçek süreden ~100 kat büyüktü;
# seyrek takılmalarda tur 3 dakika boyunca sessizce bekliyordu. Sınır gerçek
# ölçüme göre daraltıldı: sağlıklı koşum için hâlâ 40 kat pay var.
CHILD_TIMEOUT_S = 60


def run_child(script, settings_dir, env_overrides=None):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MLC_DEFAULT_UI_SETTINGS"] = str(settings_dir)
    for name in UI_ENV_VARS:
        env.pop(name, None)
    env.update(env_overrides or {})
    try:
        proc = subprocess.run([sys.executable, script], env=env,
                              cwd=PROJECT_ROOT, capture_output=True,
                              text=True, timeout=CHILD_TIMEOUT_S)
    except subprocess.TimeoutExpired as expired:
        # Çıplak `TimeoutExpired` bir sonraki incelemeye HİÇBİR kanıt
        # bırakmıyordu. Asıl ayırt edici bilgi şudur: ölçüm zaten üretilmiş
        # de child sadece kapanamıyor mu, yoksa hiç ölçüm alınamadı mı?
        partial = expired.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        produced = "DEFAULT_UI_JSON " in partial
        stalled = expired.stderr or ""
        if isinstance(stalled, bytes):
            stalled = stalled.decode("utf-8", "replace")
        phases = [row for row in stalled.splitlines()
                  if row.startswith("PHASE ")]
        raise AssertionError(
            f"Child {os.path.basename(script)} {CHILD_TIMEOUT_S} sn icinde "
            f"kapanmadi.\n"
            f"olcum uretilmis mi: {'EVET (takilma kapanista)' if produced else 'HAYIR'}\n"
            f"son faz: {phases[-1] if phases else '(faz isareti yok)'}\n"
            f"butun fazlar: {phases}\n"
            f"env: {env_overrides or {}}\n"
            f"stdout(son 2000):\n{partial[-2000:]}") from expired
    prefix = "DEFAULT_UI_JSON "
    line = next((l for l in proc.stdout.splitlines() if l.startswith(prefix)),
                None)
    if line is None:
        raise AssertionError(
            f"Ölçüm alınamadı (exit={proc.returncode})\n"
            f"stdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}")
    return json.loads(line[len(prefix):])


@pytest.fixture(scope="module")
def clean_env(tmp_path_factory):
    """Hiçbir UI değişkeni ayarlanmamış normal ürün açılışı."""
    return run_child(CHILD, tmp_path_factory.mktemp("default-clean"))


@pytest.fixture(scope="module")
def legacy_preview_zero(tmp_path_factory):
    return run_child(CHILD, tmp_path_factory.mktemp("legacy-zero"),
                     {"MLCPLAYER_OVERLAY_PREVIEW": "0"})


@pytest.fixture(scope="module")
def legacy_preview_one(tmp_path_factory):
    return run_child(CHILD, tmp_path_factory.mktemp("legacy-one"),
                     {"MLCPLAYER_OVERLAY_PREVIEW": "1"})


@pytest.fixture(scope="module")
def diagnostic_classic(tmp_path_factory):
    return run_child(CHILD, tmp_path_factory.mktemp("classic"),
                     {"MLCPLAYER_CLASSIC_UI": "1"})


@pytest.fixture(scope="module")
def main_entry(tmp_path_factory):
    return run_child(MAIN_CHILD, tmp_path_factory.mktemp("main-entry"))


# --- 1. Temiz ortamda varsayılan sinematik arayüz ---

def test_default_launch_is_frameless_with_title_bar(clean_env):
    assert clean_env["cinematic_ui_enabled"] is True
    assert clean_env["frameless"] is True
    assert clean_env["has_title_bar"] is True
    assert clean_env["title_bar_visible"] is True


def test_default_launch_hides_classic_menu_bar(clean_env):
    assert clean_env["menu_bar_visible"] is False


def test_default_launch_creates_cinematic_overlay(clean_env):
    assert clean_env["overlay_created"] is True
    assert clean_env["overlay_visible"] is True
    assert clean_env["overlay_height"] == 110


def test_default_launch_hides_classic_control_panel(clean_env):
    assert clean_env["has_control_container"] is True
    assert clean_env["control_container_visible"] is False
    assert clean_env["control_container_height"] == 0


# --- 2/3. Eski env değişkeni artık ürün anahtarı değil ---

def test_legacy_preview_zero_still_gets_cinematic_ui(legacy_preview_zero):
    assert legacy_preview_zero["env_overlay_preview"] == "0"
    assert legacy_preview_zero["cinematic_ui_enabled"] is True
    assert legacy_preview_zero["frameless"] is True
    assert legacy_preview_zero["overlay_created"] is True
    assert legacy_preview_zero["menu_bar_visible"] is False


def test_legacy_preview_one_gets_the_same_cinematic_ui(legacy_preview_one):
    assert legacy_preview_one["env_overlay_preview"] == "1"
    assert legacy_preview_one["cinematic_ui_enabled"] is True
    assert legacy_preview_one["frameless"] is True
    assert legacy_preview_one["overlay_created"] is True


def test_product_code_no_longer_reads_the_legacy_variable():
    for name in ("player.py", "video_frame.py", "ui_components.py",
                 "title_bar.py"):
        path = os.path.join(PROJECT_ROOT, "app", name)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        assert "MLCPLAYER_OVERLAY_PREVIEW" not in source, (
            f"app/{name} hâlâ eski değişkeni okuyor")


def test_main_entry_does_not_inject_ui_environment():
    with open(os.path.join(PROJECT_ROOT, "main.py"), encoding="utf-8") as handle:
        source = handle.read()
    for name in UI_ENV_VARS:
        assert f'environ["{name}"]' not in source
        assert f"environ['{name}']" not in source


# --- 4. Gerçek main.py giriş noktası ---

def test_main_entry_starts_with_cinematic_ui(main_entry):
    assert main_entry["env_overlay_preview"] is None
    assert main_entry["env_classic_ui"] is None
    assert main_entry["cinematic_ui_enabled"] is True
    assert main_entry["frameless"] is True
    assert main_entry["has_title_bar"] is True
    assert main_entry["menu_bar_visible"] is False
    assert main_entry["overlay_created"] is True


# --- 5/6. Timeline hit alanı ve gerçek seek ---

def test_default_launch_keeps_the_wide_timeline_hit_area(clean_env):
    assert clean_env["timeline_hit_height"] == 48


def test_timeline_click_seeks_on_default_launch(clean_env):
    assert clean_env["timeline_click_value"] > 0
    assert clean_env["timeline_click_time_pos"] > 0
    expected = (clean_env["timeline_click_value"] * 600.0) / 1000.0
    assert abs(clean_env["timeline_click_time_pos"] - expected) < 0.5


# --- 7. Başlık çubuğu bağlantıları ---

def test_title_bar_exposes_all_expected_buttons(clean_env):
    assert clean_env["title_bar_buttons"] == [
        "titleClose", "titleMaximize", "titleMinimize", "titleMore",
        "titleOpenFile", "titlePlaylist"]


def test_title_bar_commands_and_menu_work_on_default_launch(clean_env):
    assert clean_env["title_bar_calls"] == ["open_file", "show_playlist"]
    assert clean_env["overflow_titles"] == [
        "Ortam", "Oynatma", "Ses", "Görüntü", "Alt Yazı",
        "Araçlar", "Gezinim", "Görünüm", "Yardım"]


def test_maximize_and_restore_states_toggle(clean_env):
    assert clean_env["maximize_state"] == "Geri Yükle"
    assert clean_env["restore_state"] == "Büyüt"


# --- 8. Fullscreen ---

def test_fullscreen_hides_and_restores_title_bar_on_default_launch(clean_env):
    assert clean_env["fullscreen_active"] is True
    assert clean_env["title_bar_visible_fullscreen"] is False
    assert clean_env["title_bar_visible_after_fullscreen"] is True
    assert clean_env["overlay_visible_after_fullscreen"] is True


# --- 9. Auto-hide / fade korunuyor ---

def test_auto_hide_and_fade_exist_on_default_launch(clean_env):
    assert clean_env["has_auto_hide_timer"] is True
    assert clean_env["auto_hide_interval"] == 2500
    assert clean_env["has_fade_animation"] is True


# --- 10. Teşhis amaçlı klasik mod ---

def test_legacy_classic_env_no_longer_restores_the_old_shell(diagnostic_classic):
    """Ürün kararı: eski kabuk artık hiçbir env ile geri gelmez.

    Bu test eskiden klasik kabuğun döndüğünü doğruluyordu. Kullanıcı eski
    pencereyi gerçek Windows'ta gördüğü için karar değişti: sinematik tasarım
    tek arayüzdür (bkz. test_classic_ui_removal_regressions).
    """
    assert diagnostic_classic["cinematic_ui_enabled"] is True
    assert diagnostic_classic["frameless"] is True
    assert diagnostic_classic["has_title_bar"] is True
    assert diagnostic_classic["menu_bar_visible"] is False
    assert diagnostic_classic["overlay_created"] is True
    assert diagnostic_classic["control_container_visible"] is False
    assert diagnostic_classic["control_container_height"] == 0


# --- 11. Gizli uyumluluk nesneleri korunuyor ---

def test_hidden_compatibility_objects_survive_on_default_launch(clean_env):
    assert clean_env["has_control_container"] is True
    assert clean_env["has_position_slider"] is True
    assert clean_env["has_volume_slider"] is True
    assert clean_env["menu_bar_action_count"] == 9
