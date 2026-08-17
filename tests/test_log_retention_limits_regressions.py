# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Saklama politikasının KESİN üst sınırını bozan üç açık.

Denetimde doğrulanan davranışlar:

1. Rotasyon gerekli olduğu hâlde `os.replace`/`os.remove` başarısız
   olursa `_rotate_if_needed()` yalnız `False` dönüyor, `log()` ise
   dönüş değerini yok sayıp AYNI DOLU dosyaya yazmaya devam ediyordu.
   Sentetik 100 baytlık sınırda aktif dosya 135 bayta çıktı.
2. Eski sürümden kalan aşırı büyük aktif log olduğu gibi yedeğe
   taşınıyordu: 6 MiB eski log sonrası toplam 6.291.497 bayt, ilan
   edilen sınır 4.194.304 bayt.
3. `MAX_LOG_RECORD_BYTES = 262.144` olmasına rağmen `'\\n'` sonradan
   eklendiği için diskteki kayıt 262.145 bayt oluyordu.

Sözleşme: BAŞARILI bir `log()` çağrısından sonra
`aktif <= MAX_LOG_FILE_BYTES`, `yedek <= MAX_LOG_FILE_BYTES` ve
`toplam <= MAX_LOG_FILE_BYTES * (LOG_BACKUP_COUNT + 1)` GERÇEK dosya
boyutlarıyla doğrulanır. Sınır, gerekirse log kaybı pahasına
fail-closed korunur.
"""
import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

SECRET = "SENTETIK123"
WIN_PATH = r"C:\Users\Gercek Kullanici\Private Folder\film.mkv"


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert str(tmp_path) in errors.get_log_path()
    return tmp_path


@pytest.fixture
def small_limit(monkeypatch):
    """Sentetik küçük sınır: gerçek 2 MiB dosyalar yazmadan ölçüm."""
    monkeypatch.setattr(errors, "MAX_LOG_FILE_BYTES", 400)
    return 400


def size(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


def assert_within_ceiling():
    """Gerçek dosya boyutlarıyla sözleşme doğrulaması."""
    path = errors.get_log_path()
    active, backup = size(path), size(path + ".1")
    limit = errors.MAX_LOG_FILE_BYTES
    ceiling = limit * (errors.LOG_BACKUP_COUNT + 1)
    assert active <= limit, f"aktif {active} > {limit}"
    assert backup <= limit, f"yedek {backup} > {limit}"
    assert active + backup <= ceiling, f"toplam {active + backup} > {ceiling}"


# =====================================================================
# AÇIK 1 — rotasyon başarısızken sınır aşılıyor
# =====================================================================

@pytest.mark.parametrize("broken", ["replace", "remove"])
def test_failed_rotation_never_appends_to_a_full_file(log_env, small_limit,
                                                      monkeypatch, broken):
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (small_limit - 5))
    with open(path + ".1", "w", encoding="utf-8") as handle:
        handle.write("eski")
    before_active = size(path)
    before_backup = size(path + ".1")

    def explode(*args, **kwargs):
        raise OSError("bozuk dosya sistemi")

    monkeypatch.setattr(errors.os, broken, explode)
    errors.log("yeni kayit")           # istisna firlatmamali

    assert size(path) <= small_limit, "dolu dosyaya eklendi"
    assert size(path) <= before_active, "aktif dosya buyudu"
    assert size(path + ".1") <= max(before_backup, small_limit)
    assert_within_ceiling()


def test_failed_rotation_does_not_raise_or_recurse(log_env, small_limit,
                                                    monkeypatch, capsys):
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (small_limit - 5))

    def explode(*args, **kwargs):
        raise OSError(f"erisim reddedildi: {WIN_PATH}")

    monkeypatch.setattr(errors.os, "replace", explode)
    for _index in range(20):
        errors.log("tekrarlanan kayit")   # sonsuz tekrar/recursion olmamali

    out = capsys.readouterr().out
    assert "erisim reddedildi" not in out
    assert "Gercek Kullanici" not in out
    assert_within_ceiling()


def test_writing_resumes_after_rotation_becomes_possible(log_env, small_limit,
                                                          monkeypatch):
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (small_limit - 5))

    # NOT: `monkeypatch.undo()` KULLANILMAZ — `log_env`/`small_limit`
    # yamaları da geri alınır ve test gerçek kullanıcı log dizinine
    # yazardı. Bunun yerine hata geçici olarak açılıp kapatılır.
    state = {"broken": True}
    real_replace = errors.os.replace

    def maybe_explode(*args, **kwargs):
        if state["broken"]:
            raise OSError("gecici hata")
        return real_replace(*args, **kwargs)

    monkeypatch.setattr(errors.os, "replace", maybe_explode)
    errors.log("dusen kayit")
    state["broken"] = False

    errors.log("basarili kayit")
    with open(path, encoding="utf-8") as handle:
        assert "basarili kayit" in handle.read()
    assert_within_ceiling()


# =====================================================================
# AÇIK 2 — eskiden kalan aşırı büyük dosya
# =====================================================================

def test_oversized_legacy_active_log_is_not_moved_into_the_backup(log_env,
                                                                  small_limit):
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (small_limit * 6))

    errors.log("kucuk kayit")

    assert size(path + ".1") <= small_limit, "asiri buyuk dosya yedege tasindi"
    assert_within_ceiling()


def test_oversized_legacy_backup_is_normalised(log_env, small_limit):
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("kisa aktif\n")
    with open(path + ".1", "w", encoding="utf-8") as handle:
        handle.write("y" * (small_limit * 6))

    errors.log("kucuk kayit")

    assert size(path + ".1") <= small_limit
    assert_within_ceiling()


def test_short_record_can_still_be_written_after_normalisation(log_env,
                                                               small_limit):
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (small_limit * 6))

    errors.log("normalizasyon sonrasi")

    with open(path, encoding="utf-8") as handle:
        assert "normalizasyon sonrasi" in handle.read()
    assert_within_ceiling()


def test_normal_sized_backup_is_not_deleted(log_env, small_limit):
    path = errors.get_log_path()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("kisa aktif\n")
    with open(path + ".1", "w", encoding="utf-8") as handle:
        handle.write("TANI GECMISI\n")

    errors.log("yeni kayit")

    assert os.path.exists(path + ".1")
    with open(path + ".1", encoding="utf-8") as handle:
        assert "TANI GECMISI" in handle.read(), "normal yedek silindi"


def test_normal_rotation_still_keeps_the_diagnostic_history(log_env,
                                                            small_limit):
    path = errors.get_log_path()
    errors.log("BIRINCI KAYIT")
    # Aktif dosya sınırın ALTINDA kalmalı: sınırı zaten aşan dosya
    # "eskiden kalan aşırı büyük dosya" sayılıp düşürülür (AÇIK 2).
    padding = small_limit - size(path) - 5
    assert padding > 0
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("x" * padding)

    errors.log("IKINCI KAYIT")

    with open(path + ".1", encoding="utf-8") as handle:
        assert "BIRINCI KAYIT" in handle.read(), "tanı geçmişi kayboldu"
    assert_within_ceiling()


def test_unrelated_files_and_subfolders_survive_normalisation(log_env,
                                                              small_limit):
    path = errors.get_log_path()
    directory = os.path.dirname(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (small_limit * 6))
    unrelated = os.path.join(directory, "unrelated.txt")
    with open(unrelated, "w", encoding="utf-8") as handle:
        handle.write("DOKUNMA")
    sub = os.path.join(directory, "altklasor")
    os.makedirs(sub, exist_ok=True)
    keep = os.path.join(sub, "keep.log")
    with open(keep, "w", encoding="utf-8") as handle:
        handle.write("DOKUNMA")

    errors.log("kayit")

    assert open(unrelated, encoding="utf-8").read() == "DOKUNMA"
    assert open(keep, encoding="utf-8").read() == "DOKUNMA"
    assert os.path.isdir(sub)


def test_normalisation_never_follows_a_link_to_the_target(log_env,
                                                          small_limit):
    path = errors.get_log_path()
    directory = os.path.dirname(path)
    target = os.path.join(directory, "gercek_hedef.txt")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("H" * (small_limit * 6))
    if os.path.exists(path):
        os.remove(path)
    try:
        os.symlink(target, path)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("symlink olusturulamiyor (yonetici izni yok)")

    errors.log("kayit")

    assert os.path.exists(target), "link hedefi silindi"
    assert len(open(target, encoding="utf-8").read()) == small_limit * 6


def test_real_two_mib_policy_holds_for_a_legacy_six_mib_log(log_env):
    """Gerçek sabitlerle: 6 MiB eski log sonrası toplam <= 4 MiB."""
    path = errors.get_log_path()
    with open(path, "wb") as handle:
        handle.write(b"x" * (6 * 1024 * 1024))

    errors.log("kucuk kayit")

    total = size(path) + size(path + ".1")
    assert total <= errors.get_log_usage()["limit_bytes"], total
    assert_within_ceiling()


# =====================================================================
# AÇIK 3 — kayıt sınırı satır sonunu kapsamalı
# =====================================================================

@pytest.mark.parametrize("payload", [
    "A" * 400_000,
    "ğüşçöİĞÜŞÇÖ" * 40_000,
], ids=["ascii", "turkce"])   # kisa id: uzun payload gecici dizin adini tasirir
def test_a_single_record_including_the_newline_fits_the_limit(log_env,
                                                              payload):
    path = errors.get_log_path()
    errors.log(payload)

    on_disk = size(path)
    assert on_disk <= errors.MAX_LOG_RECORD_BYTES, on_disk
    raw = open(path, "rb").read()
    raw.decode("utf-8")                     # UTF-8 bolunmemis olmali
    assert raw.endswith(b"\n")
    line = raw.decode("utf-8").splitlines()[0]
    assert len(line.encode("utf-8")) + 1 <= errors.MAX_LOG_RECORD_BYTES
    assert errors.LOG_TRUNCATED_MARK.strip() in line


def test_truncation_mark_is_never_cut(log_env):
    errors.log("B" * 500_000)
    line = open(errors.get_log_path(), encoding="utf-8").read().splitlines()[0]
    assert line.endswith(errors.LOG_TRUNCATED_MARK)


def test_short_record_format_is_unchanged(log_env):
    errors.log("kisa mesaj", "WARNING")
    text = open(errors.get_log_path(), encoding="utf-8").read()
    assert text.endswith("kisa mesaj\n")
    assert "[WARNING]" in text
    assert errors.LOG_TRUNCATED_MARK.strip() not in text


# =====================================================================
# Korunan sözleşmeler
# =====================================================================

def test_redaction_boundary_still_applies(log_env):
    errors.log(f"{WIN_PATH} api_key={SECRET}")
    text = open(errors.get_log_path(), encoding="utf-8").read()
    assert SECRET not in text and "Gercek Kullanici" not in text


def test_clear_logs_contract_is_intact(log_env, small_limit):
    path = errors.get_log_path()
    directory = os.path.dirname(path)
    errors.log("kayit")
    unrelated = os.path.join(directory, "unrelated.txt")
    with open(unrelated, "w", encoding="utf-8") as handle:
        handle.write("DOKUNMA")

    result = errors.clear_logs()

    assert result.ok is True
    assert not os.path.exists(path)
    assert open(unrelated, encoding="utf-8").read() == "DOKUNMA"


def test_concurrent_log_and_clear_stay_under_the_lock(log_env, small_limit):
    failures = []

    def writer():
        try:
            for index in range(80):
                errors.log(f"yazan {index}")
        except Exception as exc:  # pragma: no cover
            failures.append(exc)

    def cleaner():
        try:
            for _index in range(30):
                errors.clear_logs()
        except Exception as exc:  # pragma: no cover
            failures.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(3)]
    threads += [threading.Thread(target=cleaner) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert failures == []
    assert_within_ceiling()
