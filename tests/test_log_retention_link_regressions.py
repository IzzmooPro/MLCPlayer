# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Saklama sözleşmesinin son iki sınırı: normalleştirme hatası ve bağlantılar.

Bağımsız denetimde ölçülen iki açık:

1. **Normalleştirme hatası YUTULUYOR.** `_normalise_oversized()` aşırı
   büyük dosyayı silemediğinde yalnız `continue` ediyor;
   `_prepare_log_file()` bunun başarısız olduğunu bilmediği için yazmaya
   devam ediyor. Ölçülen: büyük AKTİF dosya silinemediğinde olduğu gibi
   yedeğe taşınıyor (aktif 35 + yedek 2.400 = 2.435 bayt, izinli 800) ve
   büyük YEDEK silinemediğinde aktife yeni kayıt ekleniyor
   (45 + 2.400 = 2.445 bayt, izinli 800).

2. **Bağlantı hedefine yazılıyor.** `uygulama.log` klasör dışındaki
   küçük bir dosyaya symlink ise `_normalise_oversized()` onu `size = 0`
   sayıyor, `_prepare_log_file()` ise `os.path.isfile()`/`getsize()` ile
   bağlantıyı TAKİP ediyor ve `open(path, "ab")` HEDEF dosyaya yazıyor.
   Ölçülen: 8 baytlık dış hedef `errors.log("short")` sonrası 43 bayt.

FİZİKSEL SINIR (bilinçli sözleşme): dosya sistemi ZATEN sınırı aşmışsa
ve işletim sistemi o dosyanın silinmesine izin vermiyorsa program mevcut
aşımı yok edemez. Bu durumda doğru davranış "yeni veri yazma, mevcut
aşımı büyütme, fail-closed kal"dır. `aktif <= 2 MiB`, `yedek <= 2 MiB`,
`toplam <= 4 MiB` garantisi programın başarıyla yönetebildiği NORMAL
dosyalar için verilir.
"""
import os
import stat
import subprocess

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

MARK = "SENTETIK-KAYIT"


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    """Gerçek kullanıcı log dizinine ASLA dokunulmaz."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert str(tmp_path) in errors.get_log_path()
    return tmp_path


@pytest.fixture
def small_limit(monkeypatch):
    """Sentetik küçük sınır: gerçek 2 MiB dosya yazmadan ölçüm."""
    monkeypatch.setattr(errors, "MAX_LOG_FILE_BYTES", 400)
    return 400


def size(path):
    """Bağlantıyı TAKİP ETMEDEN boyut (link ise linkin kendisi)."""
    try:
        return os.lstat(path).st_size
    except OSError:
        return 0


def real_size(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


def write_file(path, count):
    with open(path, "wb") as handle:
        handle.write(b"x" * count)
    return count


def block_removal(monkeypatch, blocked):
    """`blocked` yolunun SİLİNMESİ işletim sistemi tarafından reddedilir."""
    target = os.path.normcase(os.path.abspath(blocked))
    real_remove, real_unlink = os.remove, os.unlink

    def guard(real):
        def wrapper(path, *args, **kwargs):
            if os.path.normcase(os.path.abspath(path)) == target:
                raise OSError(13, "sentetik erisim reddedildi")
            return real(path, *args, **kwargs)
        return wrapper

    monkeypatch.setattr(os, "remove", guard(real_remove))
    monkeypatch.setattr(os, "unlink", guard(real_unlink))


def make_symlink(link, target):
    """Symlink kurar; ortam izin vermiyorsa gerekçeli skip."""
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip("symlink oluşturulamadı (Windows'ta yönetici veya "
                    f"geliştirici modu gerekir): {type(exc).__name__}")
    if not os.path.islink(link):
        pytest.skip("symlink oluşturuldu ama bağlantı olarak görünmüyor")


def make_junction(link, target_dir):
    """Gerçek Windows junction; desteklenmiyorsa gerekçeli skip."""
    if os.name != "nt":
        pytest.skip("junction yalnız Windows'ta anlamlıdır")
    result = subprocess.run(["cmd", "/c", "mklink", "/J", link, target_dir],
                            capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(link):
        pytest.skip("mklink /J bu ortamda junction oluşturamadı")


# --- AÇIK 1: normalleştirme hatası yutuluyor ---------------------------

def test_unremovable_oversized_active_file_is_not_moved_to_the_backup(
        log_env, small_limit, monkeypatch):
    """Büyük aktif dosya silinemiyorsa yedeğe TAŞINMAZ."""
    path = errors.get_log_path()
    write_file(path, 2400)
    block_removal(monkeypatch, path)

    errors.log(MARK)

    assert size(path) == 2400, "aktif dosya değişmemeli"
    assert not os.path.exists(path + ".1"), "aşım yedeğe taşınmamalı"


def test_unremovable_oversized_active_file_does_not_receive_new_records(
        log_env, small_limit, monkeypatch):
    """Silinemeyen aşım BÜYÜTÜLMEZ: fail-closed."""
    path = errors.get_log_path()
    write_file(path, 2400)
    block_removal(monkeypatch, path)

    before = size(path)
    errors.log(MARK)
    after = size(path)

    assert after == before == 2400
    with open(path, "rb") as handle:
        assert MARK.encode("utf-8") not in handle.read()


def test_unremovable_oversized_backup_blocks_new_records(
        log_env, small_limit, monkeypatch):
    """Büyük yedek silinemiyorsa aktife YENİ kayıt eklenmez."""
    path = errors.get_log_path()
    backup = path + ".1"
    write_file(path, 10)
    write_file(backup, 2400)
    block_removal(monkeypatch, backup)

    errors.log(MARK)

    assert size(path) == 10, "aktif dosya büyümemeli"
    assert size(backup) == 2400, "yedek dosya değişmemeli"


def test_normalisation_failure_does_not_grow_the_total_usage(
        log_env, small_limit, monkeypatch):
    """Her iki senaryoda da TOPLAM kullanım artmaz."""
    path = errors.get_log_path()
    backup = path + ".1"
    write_file(path, 10)
    write_file(backup, 2400)
    block_removal(monkeypatch, backup)

    before = size(path) + size(backup)
    for _ in range(5):
        errors.log(MARK)
    assert size(path) + size(backup) == before


def test_normalisation_failure_does_not_raise_to_the_caller(
        log_env, small_limit, monkeypatch):
    """Hata çağırana taşmaz."""
    path = errors.get_log_path()
    write_file(path, 2400)
    block_removal(monkeypatch, path)

    assert errors.log(MARK) is None
    assert errors.error(MARK) is None


def test_normalisation_failure_does_not_leak_raw_oserror_text(
        log_env, small_limit, monkeypatch, capsys):
    """Ham `OSError` metni konsola/kullanıcıya çıkmaz."""
    path = errors.get_log_path()
    write_file(path, 2400)
    block_removal(monkeypatch, path)

    errors.log(MARK)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "sentetik erisim reddedildi" not in combined
    assert "OSError" not in combined
    assert "Traceback" not in combined


def test_writing_resumes_once_the_file_system_works_again(
        log_env, small_limit, monkeypatch):
    """Dosya sistemi düzelince sonraki çağrı normalleştirip yazar."""
    path = errors.get_log_path()
    write_file(path, 2400)
    block_removal(monkeypatch, path)
    errors.log(MARK)
    assert size(path) == 2400

    monkeypatch.undo()
    monkeypatch.setenv("APPDATA", str(log_env))
    monkeypatch.setenv("LOCALAPPDATA", str(log_env))
    monkeypatch.setattr(errors, "MAX_LOG_FILE_BYTES", 400)

    errors.log(MARK)

    assert size(path) <= 400
    with open(path, "rb") as handle:
        assert MARK.encode("utf-8") in handle.read()


# --- AÇIK 2: symlink / reparse point hedefine yazılıyor ----------------

def test_active_symlink_to_a_small_file_never_receives_log_records(
        log_env, tmp_path):
    """Küçük dış hedefe işaret eden aktif bağlantı: hedef DEĞİŞMEZ."""
    target = tmp_path / "disarida.txt"
    write_file(target, 8)
    path = errors.get_log_path()
    make_symlink(path, str(target))

    errors.log("short")

    assert real_size(target) == 8, "dış hedef büyümemeli"
    with open(target, "rb") as handle:
        assert handle.read() == b"x" * 8


def test_active_symlink_is_replaced_by_a_real_file(log_env, tmp_path):
    """Bağlantı güvenli biçimde kaldırıldıktan sonra gerçek dosya oluşur."""
    target = tmp_path / "disarida.txt"
    write_file(target, 8)
    path = errors.get_log_path()
    make_symlink(path, str(target))

    errors.log(MARK)

    assert not os.path.islink(path), "aktif yol artık bağlantı olmamalı"
    assert os.path.isfile(path)
    with open(path, "rb") as handle:
        assert MARK.encode("utf-8") in handle.read()
    assert real_size(target) == 8


def test_active_symlink_to_a_large_file_is_not_rotated_into_the_backup(
        log_env, small_limit, tmp_path):
    """Büyük hedefe işaret eden bağlantı, büyük dosya sayılıp taşınmaz."""
    target = tmp_path / "buyuk.txt"
    write_file(target, 2400)
    path = errors.get_log_path()
    make_symlink(path, str(target))

    errors.log(MARK)

    assert real_size(target) == 2400, "dış hedef değişmemeli"
    assert not os.path.islink(path + ".1"), "bağlantı yedeğe taşınmamalı"
    assert real_size(path + ".1") == 0 or not os.path.exists(path + ".1")


def test_backup_symlink_targets_are_never_touched(log_env, small_limit,
                                                  tmp_path):
    """Yedek adı bağlantıysa küçük ve büyük hedefler değişmez."""
    for name, count in (("kucuk.txt", 8), ("buyuk.txt", 2400)):
        target = tmp_path / name
        write_file(target, count)
        path = errors.get_log_path()
        backup = path + ".1"
        for leftover in (path, backup):
            if os.path.islink(leftover) or os.path.exists(leftover):
                os.unlink(leftover)
        write_file(path, 380)
        make_symlink(backup, str(target))

        errors.log(MARK * 20)

        assert real_size(target) == count, f"{name} hedefi değişmemeli"


def test_log_usage_and_files_do_not_follow_links(log_env, tmp_path):
    """`get_log_usage()`/`get_log_files()` dış hedefi günlük saymaz."""
    target = tmp_path / "disarida.txt"
    write_file(target, 5000)
    path = errors.get_log_path()
    make_symlink(path, str(target))

    usage = errors.get_log_usage()

    assert usage["total_bytes"] == 0, "hedef boyutu sayılmamalı"
    assert path not in errors.get_log_files()


def test_unremovable_symlink_blocks_writing_and_changes_nothing(
        log_env, tmp_path, monkeypatch, capsys):
    """Bağlantı girdisi kaldırılamıyorsa yazım fail-closed durur."""
    target = tmp_path / "disarida.txt"
    write_file(target, 8)
    path = errors.get_log_path()
    make_symlink(path, str(target))
    block_removal(monkeypatch, path)

    errors.log(MARK)

    assert os.path.islink(path), "bağlantı yerinde kalmalı"
    assert real_size(target) == 8, "hedef değişmemeli"
    combined = capsys.readouterr()
    assert "sentetik erisim reddedildi" not in combined.out + combined.err


def test_windows_junction_target_directory_is_untouched(log_env, tmp_path):
    """Gerçek junction/reparse point: hedef klasör ve içeriği korunur."""
    target_dir = tmp_path / "hedef_klasor"
    target_dir.mkdir()
    inner = target_dir / "icerik.txt"
    write_file(inner, 8)
    path = errors.get_log_path()
    make_junction(path, str(target_dir))

    errors.log(MARK)

    assert os.path.isdir(target_dir)
    assert real_size(inner) == 8, "junction hedefindeki dosya değişmemeli"
    assert len(os.listdir(target_dir)) == 1, "hedef klasöre dosya eklenmemeli"


# Bu iki testin ESKİ hâli boolean `_is_link_or_reparse_point()` üzerineydi.
# O yardımcı "bağlantı" ile "incelenemedi" durumunu aynı `True` değerine
# indirdiği ve bilinmeyen bir girişin SİLİNMESİNE yol açtığı için
# `_classify_entry()` ile değiştirildi. Testler gevşetilmedi; aynı
# davranış daha güçlü sözleşmeyle yeniden yazıldı (ayrıntılı UNKNOWN
# kapsamı `tests/test_log_entry_classification_regressions.py` içinde).

def test_classification_recognises_links_without_following_the_target(
        log_env, tmp_path):
    """Bağlantı, hedefi takip etmeden LINK_OR_REPARSE olarak görülür."""
    target = tmp_path / "disarida.txt"
    write_file(target, 8)
    link = tmp_path / "baglanti.log"
    make_symlink(str(link), str(target))

    assert errors._classify_entry(
        str(link)).kind == errors.ENTRY_LINK_OR_REPARSE
    assert errors._classify_entry(str(target)).kind == errors.ENTRY_REGULAR
    assert errors._classify_entry(
        str(tmp_path / "yok")).kind == errors.ENTRY_MISSING


def test_classification_uses_lstat_reparse_attributes():
    """Windows dosya niteliği (`FILE_ATTRIBUTE_REPARSE_POINT`) okunur."""
    assert hasattr(errors, "_classify_entry")
    assert stat.FILE_ATTRIBUTE_REPARSE_POINT  # sabit gerçekten var
    # "bağlantı" ve "incelenemedi" AYRI değerlerdir.
    assert errors.ENTRY_LINK_OR_REPARSE != errors.ENTRY_UNKNOWN_OR_UNSAFE


# --- Normal dosyaların davranışı DEĞİŞMEZ ------------------------------

def test_normal_files_still_rotate_and_stay_within_the_ceiling(
        log_env, small_limit):
    """Gerçek aktif/yedek dosyalarda sözleşme aynen sürer."""
    path = errors.get_log_path()
    for _ in range(40):
        errors.log(MARK * 5)
    active, backup = size(path), size(path + ".1")
    assert active <= 400 and backup <= 400
    assert active + backup <= 800
    assert os.path.isfile(path + ".1"), "normal rotasyon yedeği korunur"


def test_clear_logs_contract_is_preserved(log_env):
    """`clear_logs()` yalnız izinli dosyalara dokunur; idempotent."""
    path = errors.get_log_path()
    errors.log(MARK)
    unrelated = os.path.join(errors.get_log_directory(), "unrelated.txt")
    write_file(unrelated, 12)

    result = errors.clear_logs()

    assert result.ok is True
    assert not os.path.exists(path)
    assert real_size(unrelated) == 12
    assert errors.clear_logs().ok is True
