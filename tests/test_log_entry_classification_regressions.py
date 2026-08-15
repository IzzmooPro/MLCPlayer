"""Bağlantı sınıflandırmasının fail-closed sözleşmesi.

Bağımsız denetimde bulunan kusur: `_is_link_or_reparse_point()` İKİ
FARKLI durumu aynı `True` değerine indiriyordu —

1. yol gerçekten symlink/junction/reparse point,
2. `islink`/`isjunction`/`lstat` hata verdiği için yolun TÜRÜ
   belirlenemedi.

`_normalise_oversized()` her `True` sonucunu gerçek bağlantı sanıp
`_remove_log_entry()` çağırdığı için, yalnız incelenemeyen NORMAL bir
tanı logu SİLİNİYOR ve yerine yeni kayıt yazılıyordu. Bu fail-closed
değildir: bilinmeyen bir girdi silinmez, taşınmaz, üzerine yazılmaz.

İki durum artık aynı boolean ile temsil edilmiyor; `_classify_entry()`
açık bir sonuç döndürür:

- `MISSING`          → giriş yok, devam edilebilir.
- `REGULAR`          → normal düzenli dosya; boyutu AYNI `lstat`ten gelir.
- `LINK_OR_REPARSE`  → yalnız BAĞLANTI GİRDİSİ kaldırılabilir, hedefe
                       hiçbir sorgu yapılmaz.
- `UNKNOWN_OR_UNSAFE`→ hiçbir mutasyon yapılmaz, yazım durur.

Ayrıca `get_log_files()`/`get_log_usage()` bağlantı sınıflandırmasından
ÖNCE `os.path.isfile()` çağırıyor ve böylece hedefin metadata'sını
takip ediyordu; artık tek sınıflandırma önce çalışır.
"""
import os
import subprocess

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app import errors

ORIGINAL = b"ORIGINAL-DIAGNOSTIC"


@pytest.fixture
def log_env(tmp_path, monkeypatch):
    """Gerçek kullanıcı log dizinine ASLA dokunulmaz."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert str(tmp_path) in errors.get_log_path()
    return tmp_path


@pytest.fixture
def small_limit(monkeypatch):
    monkeypatch.setattr(errors, "MAX_LOG_FILE_BYTES", 400)
    return 400


def write_file(path, payload):
    with open(path, "wb") as handle:
        handle.write(payload)
    return len(payload)


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


_REAL_LSTAT = os.lstat


def link_size(path):
    """Bağlantıyı takip etmeyen boyut.

    Testlerde `os.lstat` sentetik olarak bozulduğu için ÖLÇÜM her zaman
    yamalanmamış özgün fonksiyonla yapılır; aksi hâlde ölçüm aracı
    ürünle birlikte bozulur ve yanlış "0 bayt" okunur.
    """
    try:
        return _REAL_LSTAT(path).st_size
    except OSError:
        return 0


def break_lstat(monkeypatch, target_path):
    """YALNIZ verilen yolun `os.lstat()` incelemesi başarısız olur."""
    target = os.path.normcase(os.path.abspath(target_path))
    real_lstat = os.lstat

    def fake_lstat(path, *args, **kwargs):
        if os.path.normcase(os.path.abspath(path)) == target:
            raise OSError(13, "sentetik inceleme reddedildi")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", fake_lstat)


def break_link_probes(monkeypatch, target_path):
    """`islink`/`isjunction` incelemesi verilen yolda hata verir."""
    target = os.path.normcase(os.path.abspath(target_path))

    def guard(real):
        def wrapper(path, *args, **kwargs):
            if os.path.normcase(os.path.abspath(path)) == target:
                raise OSError(13, "sentetik inceleme reddedildi")
            return real(path, *args, **kwargs)
        return wrapper

    monkeypatch.setattr(os.path, "islink", guard(os.path.islink))
    if hasattr(os.path, "isjunction"):
        monkeypatch.setattr(os.path, "isjunction", guard(os.path.isjunction))


def count_target_following_calls(monkeypatch):
    """Hedefi TAKİP EDEN çağrıları sayar (`isfile`/`exists`/`getsize`)."""
    calls = []

    def guard(name, real):
        def wrapper(path, *args, **kwargs):
            calls.append((name, os.path.normcase(os.path.abspath(path))))
            return real(path, *args, **kwargs)
        return wrapper

    monkeypatch.setattr(os.path, "isfile", guard("isfile", os.path.isfile))
    monkeypatch.setattr(os.path, "exists", guard("exists", os.path.exists))
    monkeypatch.setattr(os.path, "getsize", guard("getsize", os.path.getsize))
    return calls


def calls_for(calls, path):
    wanted = os.path.normcase(os.path.abspath(path))
    return [name for name, seen in calls if seen == wanted]


def make_symlink(link, target):
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip("symlink oluşturulamadı (Windows'ta yönetici veya "
                    f"geliştirici modu gerekir): {type(exc).__name__}")
    if not os.path.islink(link):
        pytest.skip("symlink oluşturuldu ama bağlantı olarak görünmüyor")


def make_junction(link, target_dir):
    if os.name != "nt":
        pytest.skip("junction yalnız Windows'ta anlamlıdır")
    result = subprocess.run(["cmd", "/c", "mklink", "/J", link, target_dir],
                            capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(link):
        pytest.skip("mklink /J bu ortamda junction oluşturamadı")


def block_removal(monkeypatch, blocked):
    target = os.path.normcase(os.path.abspath(blocked))
    real_remove, real_unlink, real_rmdir = os.remove, os.unlink, os.rmdir

    def guard(real):
        def wrapper(path, *args, **kwargs):
            if os.path.normcase(os.path.abspath(path)) == target:
                raise OSError(13, "sentetik erisim reddedildi")
            return real(path, *args, **kwargs)
        return wrapper

    monkeypatch.setattr(os, "remove", guard(real_remove))
    monkeypatch.setattr(os, "unlink", guard(real_unlink))
    monkeypatch.setattr(os, "rmdir", guard(real_rmdir))


# --- Sınıflandırmanın kendisi -----------------------------------------

def test_classification_separates_link_from_unexaminable(log_env, tmp_path,
                                                         monkeypatch):
    """Gerçek bağlantı ile "incelenemedi" AYNI değer OLAMAZ."""
    target = tmp_path / "disarida.txt"
    write_file(target, b"12345678")
    link = str(tmp_path / "baglanti.log")
    make_symlink(link, str(target))
    normal = str(tmp_path / "normal.log")
    write_file(normal, ORIGINAL)

    assert errors._classify_entry(link).kind == errors.ENTRY_LINK_OR_REPARSE
    assert errors._classify_entry(normal).kind == errors.ENTRY_REGULAR
    assert errors._classify_entry(
        str(tmp_path / "yok")).kind == errors.ENTRY_MISSING

    break_lstat(monkeypatch, normal)
    unknown = errors._classify_entry(normal)
    assert unknown.kind == errors.ENTRY_UNKNOWN_OR_UNSAFE
    assert unknown.kind != errors.ENTRY_LINK_OR_REPARSE, (
        "incelenemeyen giriş bağlantı gibi ele alınamaz")


def test_classification_reports_size_from_the_same_lstat(log_env, tmp_path):
    """REGULAR boyutu AYNI `lstat` sonucundan gelir (ek sorgu yok)."""
    normal = str(tmp_path / "normal.log")
    write_file(normal, b"x" * 123)

    entry = errors._classify_entry(normal)

    assert entry.kind == errors.ENTRY_REGULAR
    assert entry.size == 123


def test_a_directory_is_unsafe_not_regular(log_env, tmp_path):
    """Dizin REGULAR sayılmaz; güvenli olmayan giriştir."""
    folder = str(tmp_path / "klasor")
    os.mkdir(folder)

    assert errors._classify_entry(folder).kind == errors.ENTRY_UNKNOWN_OR_UNSAFE


# --- SORUN 1: UNKNOWN girişte hiçbir mutasyon olmaz --------------------

def test_lstat_failure_preserves_the_existing_diagnostic_log(log_env,
                                                             monkeypatch):
    """Sentetik `lstat` hatasında mevcut log BYTE-FOR-BYTE korunur."""
    path = errors.get_log_path()
    write_file(path, ORIGINAL)
    break_lstat(monkeypatch, path)

    errors.log("NEW")

    assert read_bytes(path) == ORIGINAL, "mevcut tanı kaydı silinemez"


def test_lstat_failure_writes_no_new_record_and_no_backup(log_env,
                                                          monkeypatch):
    """UNKNOWN girişte yeni kayıt yazılmaz, yedek oluşmaz."""
    path = errors.get_log_path()
    write_file(path, ORIGINAL)
    break_lstat(monkeypatch, path)

    errors.log("NEW")

    assert b"NEW" not in read_bytes(path)
    assert b"[INFO]" not in read_bytes(path)
    assert not os.path.exists(path + ".1"), "yedek oluşmamalı"


def test_link_probe_failure_can_no_longer_delete_a_regular_entry(log_env,
                                                                 monkeypatch):
    """`islink`/`isjunction` artık sınıflandırma yolunda DEĞİL.

    Eski yardımcı bu iki sorgudan gelen `OSError`'ı da "bağlantı" sayıp
    girdiyi siliyordu. Tek `lstat` incelemesine geçildiği için bu hata
    yolu tamamen ORTADAN KALKTI: sorgular bozulsa bile normal dosya
    doğru sınıflandırılır, SİLİNMEZ ve tanı içeriği korunur.
    """
    path = errors.get_log_path()
    write_file(path, ORIGINAL)
    break_link_probes(monkeypatch, path)

    errors.log("NEW")

    assert os.path.exists(path), "normal giriş silinmemeli"
    assert read_bytes(path).startswith(ORIGINAL), "tanı içeriği korunur"


def test_unknown_oversized_active_is_not_moved_to_the_backup(
        log_env, small_limit, monkeypatch):
    """UNKNOWN durumdaki büyük aktif dosya yedeğe TAŞINMAZ."""
    path = errors.get_log_path()
    write_file(path, b"y" * 2400)
    break_lstat(monkeypatch, path)

    errors.log("NEW")

    assert link_size(path) == 2400
    assert not os.path.exists(path + ".1")


def test_unknown_oversized_backup_blocks_new_records(log_env, small_limit,
                                                     monkeypatch):
    """UNKNOWN durumdaki büyük yedek varken aktife kayıt EKLENMEZ."""
    path = errors.get_log_path()
    backup = path + ".1"
    write_file(path, ORIGINAL)
    write_file(backup, b"y" * 2400)
    break_lstat(monkeypatch, backup)

    errors.log("NEW")

    assert read_bytes(path) == ORIGINAL, "aktif dosya büyümemeli"
    assert link_size(backup) == 2400


def test_prepare_log_file_returns_false_for_unknown_entries(log_env,
                                                            monkeypatch):
    """Sözleşme doğrudan: UNKNOWN girişte `_prepare_log_file()` False."""
    path = errors.get_log_path()
    write_file(path, ORIGINAL)
    break_lstat(monkeypatch, path)

    assert errors._prepare_log_file(path, 64) is False


def test_writing_resumes_after_inspection_works_again(log_env, monkeypatch):
    """İnceleme düzelince sonraki çağrı normal biçimde yazar."""
    path = errors.get_log_path()
    write_file(path, ORIGINAL)
    break_lstat(monkeypatch, path)
    errors.log("NEW")
    assert read_bytes(path) == ORIGINAL

    monkeypatch.undo()
    monkeypatch.setenv("APPDATA", str(log_env))
    monkeypatch.setenv("LOCALAPPDATA", str(log_env))

    errors.log("NEW")

    assert b"NEW" in read_bytes(path)
    assert read_bytes(path).startswith(ORIGINAL), "mevcut tanı korunur"


# --- SORUN 2: okuma tarafı hedefi takip etmez -------------------------

def test_get_log_files_never_follows_a_symlink_target(log_env, tmp_path,
                                                      monkeypatch):
    """`get_log_files()` symlink için `isfile()` bile ÇAĞIRMAZ."""
    target = tmp_path / "disarida.txt"
    write_file(target, b"12345678")
    path = errors.get_log_path()
    make_symlink(path, str(target))
    calls = count_target_following_calls(monkeypatch)

    result = errors.get_log_files()

    assert path not in result
    assert calls_for(calls, path) == [], (
        f"hedefi takip eden çağrı yapıldı: {calls_for(calls, path)}")


def test_get_log_usage_never_follows_a_symlink_target(log_env, tmp_path,
                                                      monkeypatch):
    """`get_log_usage()` symlink için `isfile/exists/getsize` çağırmaz."""
    target = tmp_path / "disarida.txt"
    write_file(target, b"z" * 5000)
    path = errors.get_log_path()
    make_symlink(path, str(target))
    calls = count_target_following_calls(monkeypatch)

    usage = errors.get_log_usage()

    assert usage["total_bytes"] == 0
    assert calls_for(calls, path) == [], (
        f"hedefi takip eden çağrı yapıldı: {calls_for(calls, path)}")


def test_broken_symlink_target_is_never_queried(log_env, tmp_path,
                                                monkeypatch):
    """Kırık symlink: hedef sorgulanmaz, yalnız girdi yönetilir."""
    missing_target = str(tmp_path / "hic_olmayan.txt")
    path = errors.get_log_path()
    make_symlink(path, missing_target)
    calls = count_target_following_calls(monkeypatch)

    assert errors.get_log_files() == []
    assert errors.get_log_usage()["total_bytes"] == 0
    assert calls_for(calls, path) == []

    monkeypatch.undo()
    monkeypatch.setenv("APPDATA", str(log_env))
    monkeypatch.setenv("LOCALAPPDATA", str(log_env))
    errors.log("NEW")

    assert not os.path.islink(path), "kırık bağlantı kaldırılmalı"
    assert os.path.isfile(path)
    assert not os.path.exists(missing_target), "hedef ASLA oluşturulmaz"


def test_unknown_entry_is_not_listed_and_target_is_not_queried(
        log_env, monkeypatch):
    """UNKNOWN giriş listelenmez; ek hedef sorgusu yapılmaz."""
    path = errors.get_log_path()
    write_file(path, ORIGINAL)
    break_lstat(monkeypatch, path)
    calls = count_target_following_calls(monkeypatch)

    assert path not in errors.get_log_files()
    assert errors.get_log_usage()["total_bytes"] == 0
    assert calls_for(calls, path) == []


# --- Gerçek bağlantılar -----------------------------------------------

def test_real_file_symlink_target_is_untouched_and_path_becomes_regular(
        log_env, tmp_path):
    """Gerçek dosya symlink'i: hedef değişmez, aktif yol normal dosya olur."""
    target = tmp_path / "disarida.txt"
    write_file(target, b"12345678")
    path = errors.get_log_path()
    make_symlink(path, str(target))

    errors.log("NEW")

    assert read_bytes(target) == b"12345678", "hedef byte-for-byte korunur"
    assert not os.path.islink(path)
    assert errors._classify_entry(path).kind == errors.ENTRY_REGULAR
    assert b"NEW" in read_bytes(path)


def test_windows_junction_is_either_removed_safely_or_fails_closed(
        log_env, tmp_path):
    """Gerçek junction: ya güvenle kaldırılır ya da yazım durur."""
    target_dir = tmp_path / "hedef_klasor"
    target_dir.mkdir()
    inner = target_dir / "icerik.txt"
    write_file(inner, b"12345678")
    path = errors.get_log_path()
    make_junction(path, str(target_dir))
    assert errors._classify_entry(path).kind == errors.ENTRY_LINK_OR_REPARSE

    errors.log("NEW")

    # Hedef her iki sonuçta da byte-for-byte korunur.
    assert os.path.isdir(target_dir)
    assert read_bytes(inner) == b"12345678"
    assert sorted(os.listdir(target_dir)) == ["icerik.txt"]

    if errors._classify_entry(path).kind == errors.ENTRY_LINK_OR_REPARSE:
        # Kaldırılamadı → fail-closed: hiçbir yeni kayıt yazılmadı.
        assert os.path.exists(path)
        assert errors.get_log_files() == []
    else:
        # Güvenle kaldırıldı → aktif yol normal dosya, kayıt YALNIZ burada.
        assert not os.path.isdir(path)
        assert errors._classify_entry(path).kind == errors.ENTRY_REGULAR
        assert b"NEW" in read_bytes(path)


def test_unremovable_junction_stops_writing(log_env, tmp_path, monkeypatch):
    """Junction kaldırılamıyorsa yazım durur, hedef değişmez."""
    target_dir = tmp_path / "hedef_klasor"
    target_dir.mkdir()
    inner = target_dir / "icerik.txt"
    write_file(inner, b"12345678")
    path = errors.get_log_path()
    make_junction(path, str(target_dir))
    block_removal(monkeypatch, path)

    errors.log("NEW")

    assert errors._classify_entry(path).kind == errors.ENTRY_LINK_OR_REPARSE
    assert read_bytes(inner) == b"12345678"
    assert sorted(os.listdir(target_dir)) == ["icerik.txt"]


def test_unremovable_symlink_stops_writing(log_env, tmp_path, monkeypatch):
    """Bağlantı girdisi kaldırılamıyorsa yazım fail-closed durur."""
    target = tmp_path / "disarida.txt"
    write_file(target, b"12345678")
    path = errors.get_log_path()
    make_symlink(path, str(target))
    block_removal(monkeypatch, path)

    errors.log("NEW")

    assert os.path.islink(path)
    assert read_bytes(target) == b"12345678"


# --- Normal dosyaların sözleşmesi DEĞİŞMEZ ----------------------------

def test_normal_rotation_and_managed_ceiling_are_unchanged(log_env,
                                                           small_limit):
    """Yönetilen normal dosyalarda rotasyon ve sınır aynen sürer."""
    path = errors.get_log_path()
    for _ in range(40):
        errors.log("KAYIT" * 5)

    active, backup = link_size(path), link_size(path + ".1")
    assert active <= 400 and backup <= 400
    assert active + backup <= 800
    assert os.path.isfile(path + ".1")
    assert errors.get_log_files() == [path, path + ".1"]


def test_real_ceiling_constants_are_unchanged():
    """2 MiB / 1 yedek / 256 KiB politikası bu turda değişmedi."""
    assert errors.MAX_LOG_FILE_BYTES == 2 * 1024 * 1024
    assert errors.LOG_BACKUP_COUNT == 1
    assert errors.MAX_LOG_RECORD_BYTES == 256 * 1024
    assert errors.get_log_usage()["limit_bytes"] == 4 * 1024 * 1024
