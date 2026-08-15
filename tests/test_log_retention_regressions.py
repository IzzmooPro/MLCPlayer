"""3. aşama — sınırlı ve KESİN log saklama politikası.

Doğrulanan kusur: rotasyon yalnız yazma ÖNCESİNDEKİ boyuta bakıyordu,
gelecek kaydın boyutunu hesaba katmıyordu. 2 MiB'ın hemen altındaki bir
dosyaya tek bir 500 KB'lık kayıt yazıldığında aktif log 2,48 MiB'a
çıkıyor ve yedek hiç oluşmuyordu.

Bu dosya şu sözleşmeyi kilitler:

- rotasyon "mevcut boyut + yazılacak satır" sınırı aşacaksa YAZMADAN
  ÖNCE yapılır,
- tek kayıt `MAX_LOG_RECORD_BYTES` sınırını aşarsa UTF-8 karakteri
  ORTADAN BÖLMEDEN kısaltılır,
- yalnız `uygulama.log` ve `uygulama.log.1` yönetilir,
- yazma/rotasyon/temizleme aynı process-wide kilit altındadır,
- `clear_logs()` idempotenttir ve izin verilen iki dosya dışında hiçbir
  şeye dokunmaz.

Testler gerçek kullanıcı logunu KULLANMAZ; her test geçici dizin alır.
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


def size_of(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# =====================================================================
# A. Rotasyon: yazmadan ÖNCE
# =====================================================================

def test_rotation_happens_before_a_write_that_would_exceed_the_limit(log_env):
    path = errors.get_log_path()
    limit = errors.MAX_LOG_FILE_BYTES
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (limit - 10))

    errors.log("A" * 100_000)

    assert size_of(path) <= limit, "aktif log sınırı aştı"
    assert os.path.exists(path + ".1"), "yedek oluşmadı"
    assert "A" * 100 in read(path), "yeni kayıt yeni dosyaya yazılmadı"


def test_write_that_fits_exactly_does_not_rotate(log_env):
    path = errors.get_log_path()
    message = "tam sinir"
    line = f"[0000-00-00 00:00:00] [INFO] {message}\n"
    payload = len(line.encode("utf-8"))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x" * (errors.MAX_LOG_FILE_BYTES - payload))

    errors.log(message)

    assert size_of(path) <= errors.MAX_LOG_FILE_BYTES
    assert not os.path.exists(path + ".1"), "tam sınırda gereksiz rotasyon"


def test_only_one_backup_is_kept(log_env):
    path = errors.get_log_path()
    for _round in range(4):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x" * (errors.MAX_LOG_FILE_BYTES - 10))
        errors.log("yeni tur")

    assert errors.LOG_BACKUP_COUNT == 1
    assert not os.path.exists(path + ".2")
    assert not os.path.exists(path + ".3")


def test_total_usage_stays_inside_the_documented_ceiling(log_env):
    path = errors.get_log_path()
    ceiling = errors.MAX_LOG_FILE_BYTES * (errors.LOG_BACKUP_COUNT + 1)
    for _round in range(6):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x" * (errors.MAX_LOG_FILE_BYTES - 50))
        errors.log("tur mesaji")

    total = size_of(path) + size_of(path + ".1")
    assert total <= ceiling, total
    assert errors.get_log_usage()["total_bytes"] <= ceiling


# =====================================================================
# B. Tek kayıt sınırı ve UTF-8 güvenliği
# =====================================================================

def test_a_single_huge_record_is_truncated_safely(log_env):
    errors.log("A" * (errors.MAX_LOG_RECORD_BYTES * 2))
    text = read(errors.get_log_path())
    line = text.splitlines()[0]

    assert len(line.encode("utf-8")) <= errors.MAX_LOG_RECORD_BYTES
    assert errors.LOG_TRUNCATED_MARK.strip() in line


def test_truncation_never_splits_a_multibyte_character(log_env):
    # Türkçe glifler 2 bayt; kesim noktası karakteri ORTADAN bölmemeli.
    errors.log("ğüşçöİĞÜŞÇÖ" * (errors.MAX_LOG_RECORD_BYTES // 4))
    raw = open(errors.get_log_path(), "rb").read()
    raw.decode("utf-8")  # UnicodeDecodeError yükseltmemeli
    line = read(errors.get_log_path()).splitlines()[0]
    assert len(line.encode("utf-8")) <= errors.MAX_LOG_RECORD_BYTES
    assert errors.LOG_TRUNCATED_MARK.strip() in line


def test_truncated_record_never_returns_to_raw_data(log_env):
    payload = (f"{WIN_PATH} api_key={SECRET} " * 20000)
    errors.log(payload)
    text = read(errors.get_log_path())
    assert SECRET not in text
    assert "Gercek Kullanici" not in text
    assert "Private Folder" not in text


def test_short_records_keep_their_existing_format(log_env):
    errors.log("kisa mesaj", "WARNING")
    line = read(errors.get_log_path()).strip()
    assert line.endswith("kisa mesaj")
    assert "[WARNING]" in line
    assert errors.LOG_TRUNCATED_MARK.strip() not in line
    assert line.startswith("[") and "] [WARNING] " in line


@pytest.mark.parametrize("writer", ["log", "debug", "info", "error"])
def test_every_level_still_passes_through_redaction(log_env, writer):
    getattr(errors, writer)(f"{WIN_PATH} token={SECRET}")
    text = read(errors.get_log_path())
    assert SECRET not in text and "Gercek Kullanici" not in text
    assert errors.MASK_PATH in text or errors.MASK in text


# =====================================================================
# C. Dayanıklılık ve eşzamanlılık
# =====================================================================

def test_logging_failure_never_reaches_the_caller(log_env, monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("disk dolu")

    monkeypatch.setattr(errors.os, "replace", explode)
    monkeypatch.setattr(errors, "get_log_path", explode)
    errors.log("mesaj")  # istisna firlatmamali


def test_concurrent_writes_and_clear_stay_consistent(log_env):
    errors.log("baslangic")
    failures = []

    def writer():
        try:
            for index in range(60):
                errors.log(f"yazan {index}")
        except Exception as exc:  # pragma: no cover
            failures.append(exc)

    def cleaner():
        try:
            for _index in range(20):
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
    path = errors.get_log_path()
    if os.path.exists(path):
        read(path)  # yarim rotasyon/bozuk UTF-8 olmamali


def test_a_shared_lock_guards_writing_and_clearing():
    assert isinstance(errors._LOG_LOCK, type(threading.RLock()))


# =====================================================================
# D. clear_logs()
# =====================================================================

def test_clear_logs_removes_only_the_allowed_files(log_env):
    path = errors.get_log_path()
    directory = os.path.dirname(path)
    errors.log("aktif kayit")
    with open(path + ".1", "w", encoding="utf-8") as handle:
        handle.write("eski kayit")
    unrelated = os.path.join(directory, "unrelated.txt")
    with open(unrelated, "w", encoding="utf-8") as handle:
        handle.write("dokunma")
    sub = os.path.join(directory, "altklasor")
    os.makedirs(sub, exist_ok=True)
    keep = os.path.join(sub, "keep.log")
    with open(keep, "w", encoding="utf-8") as handle:
        handle.write("dokunma")

    result = errors.clear_logs()

    assert result.ok is True
    assert not os.path.exists(path)
    assert not os.path.exists(path + ".1")
    assert os.path.exists(unrelated) and read(unrelated) == "dokunma"
    assert os.path.isdir(sub) and read(keep) == "dokunma"


def test_clear_logs_is_idempotent(log_env):
    first = errors.clear_logs()
    second = errors.clear_logs()
    assert first.ok is True and second.ok is True
    assert second.removed == ()


def test_clear_logs_does_not_write_a_new_log_record(log_env):
    errors.log("kayit")
    errors.clear_logs()
    assert not os.path.exists(errors.get_log_path())


def test_clear_logs_never_follows_a_link_to_damage_the_target(log_env):
    path = errors.get_log_path()
    directory = os.path.dirname(path)
    target = os.path.join(directory, "gercek_hedef.txt")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("HEDEF ICERIK")
    if os.path.exists(path):
        os.remove(path)
    try:
        os.symlink(target, path)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("symlink olusturulamiyor (yonetici izni yok)")

    errors.clear_logs()

    assert os.path.exists(target), "link hedefi silindi"
    assert read(target) == "HEDEF ICERIK", "link hedefi bozuldu"


def test_clear_logs_reports_failures_without_raw_os_text(log_env,
                                                         monkeypatch):
    errors.log("kayit")

    def explode(_path):
        raise OSError(f"erisim reddedildi: {WIN_PATH}")

    monkeypatch.setattr(errors.os, "remove", explode)
    result = errors.clear_logs()

    assert result.ok is False
    assert "Gercek Kullanici" not in result.message
    assert "erisim reddedildi" not in result.message
    assert result.message.strip()


# =====================================================================
# E. Sorgulama API'si
# =====================================================================

def test_log_directory_and_files_contract(log_env):
    errors.log("kayit")
    directory = errors.get_log_directory()
    assert os.path.isdir(directory)
    assert os.path.dirname(errors.get_log_path()) == directory

    files = errors.get_log_files()
    assert errors.get_log_path() in files
    assert all(os.path.dirname(item) == directory for item in files)


def test_log_usage_reports_total_and_limit(log_env):
    errors.log("kayit")
    usage = errors.get_log_usage()
    assert usage["total_bytes"] > 0
    assert usage["limit_bytes"] == \
        errors.MAX_LOG_FILE_BYTES * (errors.LOG_BACKUP_COUNT + 1)
    names = [name for name, _size in usage["files"]]
    assert "uygulama.log" in names


def test_usage_is_zero_after_clearing(log_env):
    errors.log("kayit")
    errors.clear_logs()
    assert errors.get_log_usage()["total_bytes"] == 0


def test_retention_constants_are_explicit():
    assert errors.MAX_LOG_FILE_BYTES == 2 * 1024 * 1024
    assert errors.LOG_BACKUP_COUNT == 1
    assert errors.MAX_LOG_RECORD_BYTES == 256 * 1024
