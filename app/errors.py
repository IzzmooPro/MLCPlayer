"""Güvenli hata çekirdeği.

Sınır kuralı
------------
Kullanıcıya YALNIZ anlaşılır Türkçe mesaj gider. Ham traceback, ham
`str(exception)`, tam kullanıcı yolu, API anahtarı, parola,
`Authorization` başlığı ve URL token'ı kullanıcı penceresine ASLA
yazılmaz. Teknik tanı bilgisi geliştirici loguna gider, ama oraya da
merkezi `redact()` süzgecinden geçerek yazılır.

Her hata tek bir `ErrorEvent` kaydıdır: bir hata = bir kayıt numarası.
Kayıt numarası (`MLC-20260813-A7F2`) kullanıcıya hatanın AÇIKLAMASI gibi
sunulmaz; yalnız destek amacıyla kullanılır.

Bu modül güvenli hata sisteminin 1-3. aşamalarını taşır: hata çekirdeği,
merkezi `redact()`/`safe_console()` sınırları, ayrı ayrıntı penceresini
açan akış (`app/error_details_dialog.py`) ve sınırlı log saklama
politikası (`app/log_management_dialog.py` bu API'yi kullanır).

4. aşama olan "Hatayı Bildir/Gönder" BURADA YOKTUR: ağ erişimi,
backend veya otomatik veri gönderimi bulunmaz.
"""
import builtins
import os
import re
import secrets
import stat
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import Qt

# Maskeleme işaretleri ve kayıt numarası biçimi.
MASK = "<gizli>"
MASK_PATH = "<yol>"
# Maskeleme beklenmedik biçimde hata verirse konsola YAZILACAK tek
# metin. Ham mesaj fallback olarak ASLA yazılmaz.
CONSOLE_REDACTION_FAILED = "[konsol mesajı gizlilik nedeniyle gösterilmedi]"
# Ana hata kutusundaki IKINCIL eylem. Varsayilan dugme DEGILDIR.
DETAILS_BUTTON_TEXT = "Hata Ayrıntılarını Görüntüle"
RECORD_ID_PREFIX = "MLC"
RECORD_ID_PATTERN = r"MLC-\d{8}-[0-9A-F]{4}"

# Gizli değer taşıyan anahtar adları. Önek serbesttir (`client_secret`,
# `x-api-key`, `user_password`). BİLEREK yalnız tam anahtar adları
# listelenir: çıplak `key` eklenirse `keyboard=`/`monkey=` gibi zararsız
# tanılar da maskelenirdi.
_SECRET_KEY_CORE = (
    r"api[_-]?key|apikey|x[_-]api[_-]key|api[_-]?secret|client[_-]?secret|"
    r"client[_-]?id|private[_-]?key|password|passwd|pwd|passphrase|secret|"
    r"token|access[_-]?token|refresh[_-]?token|id[_-]?token|auth[_-]?token|"
    r"session[_-]?id|sessionid|authorization|auth|signature|sig")
_SECRET_KEYS = r"(?:[A-Za-z0-9]+[_-])?(?:" + _SECRET_KEY_CORE + r")"
# Ayraç: `=`, `:` ve URL-encoded `%3D`.
_SEPARATOR = r"\s*(?:=|:|%3[Dd])\s*"

# `Authorization` satırında kimlik bilgisi gövdesinin HİÇBİRİ kalmamalı;
# şema adı da dahil satırın kalanı maskelenir.
_AUTH_HEADER = re.compile(r'(\bAuthorization\b\s*[:=]\s*)\S.*', re.IGNORECASE)
# Tırnaklı değer gövdesi: KAPATAN tırnağa kadar her şey. Karşı tür tırnak
# (`password="abc'def"`) ve kaçışlı tırnak (`"abc\"def"`) da değerin
# parçasıdır. Satır sonu DIŞARIDA bırakılır: kalıp satırın kalanını veya
# sonraki log kaydını yutamaz.
def _quoted_value(group):
    # NOT: geri referans TEK ters bölü ile yazılmalıdır (`(?!\3)`). Çift
    # yazıldığında kalıp "ters bölü + 3" arıyor, değer kapanış tırnağını
    # da yutuyor ve satırın kalanı maskeye gidiyordu.
    return r'(?:\\.|(?!' + '\\' + str(group) + r')[^\\\r\n])*'


# Sözlük/JSON: {'token': 'değer'} ve {"token": "değer"}
_MAPPING_SECRET = re.compile(
    r'([\'"])(' + _SECRET_KEYS + r')\1(\s*:\s*)([\'"])' + _quoted_value(4) +
    r'\4', re.IGNORECASE)
# anahtar='değer' / anahtar="değer"
_KEY_VALUE_QUOTED = re.compile(
    r'\b(' + _SECRET_KEYS + r')(' + _SEPARATOR + r')([\'"])' +
    _quoted_value(3) + r'\3', re.IGNORECASE)
# anahtar=değer (URL query, form ve düz metin; `%26` de ayraç sayılır).
_KEY_VALUE_PLAIN = re.compile(
    r'\b(' + _SECRET_KEYS + r')(' + _SEPARATOR +
    r')((?:(?!%26)[^\s&"\'#,;)\]}<>])+)', re.IGNORECASE)
# Başlıksız şema + jeton (`Bearer abc`, `Digest abc` ...).
_SCHEME_TOKEN = re.compile(
    r'\b(Bearer|Basic|Digest|Negotiate|NTLM|Token|OAuth|HOBA|Mutual)\s+'
    r'[A-Za-z0-9._~\-+/=]{3,}', re.IGNORECASE)
# --- Yol maskeleme: deterministik SATIR TARAYICISI -----------------------
#
# Neden regex değil
# -----------------
# Serbest metindeki TIRNAKSIZ, boşluklu ve uzantısız bir Windows yolunun
# nerede bittiği genel olarak belirlenemez: virgül, noktalı virgül,
# parantez ve boşluk Windows dosya adında geçerli karakterlerdir.
# Uzantıya/noktalamaya dayanan her regex istisnası yeni bir kaçak
# bıraktı (`D:\Private\gizli klasor` -> `<yol> klasor`). Bu yüzden yolun
# BAŞLANGICI küçük regex'lerle bulunur, SONU ise aşağıdaki deterministik
# tarayıcıyla belirlenir.
#
# Sözleşme
# --------
# 1. Tırnakla çevrili yol: eşleşen kapanış tırnağına kadar maskelenir;
#    tırnaklar ve sonraki cümle korunur.
# 2. Tırnaksız yol: güvenli sınır yoktur, gizlilik lehine SATIR SONUNA
#    kadar maskelenir (fail-closed). Sonraki satır ASLA yutulmaz.
# 3. Yalnız tırnaklı kaynak kod yollarında boşluksuz `.py`/`.pyw`
#    dosya adı tanı için korunur.
_PATH_ROOTS = (
    # \\?\UNC\server\share ve \\?\C:\uzun yol
    re.compile(r'\\\\\?\\UNC\\'),
    re.compile(r'\\\\\?\\[A-Za-z]:[\\/]'),
    # \\server\share
    re.compile(r'(?<![A-Za-z0-9])\\\\[^\\/\s"\']+[\\/]'),
    # //server/share — `https://` gibi şemalardan sonra GELMEZ.
    re.compile(r'(?<![A-Za-z0-9:/])//[^/\s"\']+/'),
    # file:///C:/... , file://server/share/... , file://localhost/C:/...
    # RFC şema adı ALPHA / DIGIT / `+` / `-` / `.` içerir; bunlardan
    # sonra gelen `file://` BAĞIMSIZ şema başlangıcı değildir
    # (`custom-file://`, `x.file://`, `abc+file://`, `myfile://`).
    re.compile(r'(?<![A-Za-z0-9+\-.])file://', re.IGNORECASE),
    # C:\ ve C:/
    re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]'),
)
# Yalnız gerçek satır ayraçları; `splitlines()` ek Unicode sınırlarında
# da bölerdi ve metni sessizce değiştirirdi.
_LINE_SPLIT = re.compile(r'(\r\n|\r|\n)')
# Tanı için korunabilecek TEK dosya türü: kaynak kod.
_SOURCE_SUFFIXES = (".py", ".pyw")


def _path_start(line, offset):
    """Satırda `offset`ten sonraki EN ERKEN yol kökü. Yoksa None."""
    best = None
    for pattern in _PATH_ROOTS:
        match = pattern.search(line, offset)
        if match is not None and (best is None or match.start() < best):
            best = match.start()
    return best


def _diagnostic_suffix(path_text):
    """Tırnaklı kaynak kod yolunda korunabilecek güvenli dosya adı."""
    final = re.split(r'[\\/]', path_text)[-1]
    if not final or any(char.isspace() for char in final):
        return ""
    if final.lower().endswith(_SOURCE_SUFFIXES):
        return f"\\{final}"
    return ""


def _mask_paths_in_line(line):
    """Satırdaki mutlak yolları sözleşmeye göre maskeler."""
    out = []
    index = 0
    while True:
        start = _path_start(line, index)
        if start is None:
            out.append(line[index:])
            return "".join(out)
        out.append(line[index:start])
        quote = line[start - 1] if start > 0 else ""
        # YALNIZ çift tırnak güvenli sınırdır: `"` Windows dosya adında
        # GEÇERSİZDİR, bu yüzden ilk eşleşme kesin kapanıştır. `'` ise
        # geçerlidir (`O'Brien`, `Rock 'n' Roll`, `Drivers' Backup`) ve
        # hangi tırnağın dış kapanış olduğu serbest metinde genel olarak
        # belirlenemez; sezgi denemesi hâlâ yol sızdırıyordu. Tek tırnak
        # artık tırnaksız yol gibi fail-closed işlenir.
        if quote == '"':
            end = line.find('"', start)
            if end == -1:
                # Kapanmamış tırnak: sınır belirsiz -> fail-closed.
                out.append(MASK_PATH)
                return "".join(out)
            out.append(MASK_PATH + _diagnostic_suffix(line[start:end]))
            index = end
            continue
        # Tırnaksız veya tek tırnaklı yol: satır sonuna kadar maskele.
        out.append(MASK_PATH)
        return "".join(out)


def _mask_paths(text):
    """Her satır AYRI işlenir; sonraki kayıt veya traceback satırı
    fail-closed maskelemeden etkilenmez.

    Satır sonları BİREBİR korunur: `\\r\\n` ve tek `\\r` ayraçları
    `\\n`'e çevrilmez. Maskeleme yalnız satır İÇERİĞİNE uygulanır,
    özgün ayraç aynen geri eklenir.
    """
    parts = _LINE_SPLIT.split(text)
    # `re.split` yakalama grubuyla: [içerik, ayraç, içerik, ayraç, ...]
    for index in range(0, len(parts), 2):
        parts[index] = _mask_paths_in_line(parts[index])
    return "".join(parts)


def redact(text):
    """Hassas değerleri maskeleyen MERKEZİ süzgeç.

    Zararsız açıklamalara dokunmaz; yalnız gizli değerleri `<gizli>`,
    yolları `<yol>` ile değiştirir. Kullanıcı mesajı, istisna metni,
    traceback ve NİHAİ log yazımı bu fonksiyondan geçer.

    `redact(redact(x)) == redact(x)`: maskelenmiş çıktı yeniden
    maskelendiğinde değişmez.
    """
    if text is None:
        return ""
    value = text if isinstance(text, str) else str(text)
    value = _AUTH_HEADER.sub(r"\1" + MASK, value)
    value = _MAPPING_SECRET.sub(r"\1\2\1\3\4" + MASK + r"\4", value)
    value = _KEY_VALUE_QUOTED.sub(r"\1\2\3" + MASK + r"\3", value)
    value = _KEY_VALUE_PLAIN.sub(r"\1\2" + MASK, value)
    value = _SCHEME_TOKEN.sub(r"\1 " + MASK, value)
    value = _mask_paths(value)
    return value


@dataclass(frozen=True)
class ErrorEvent:
    """Tek bir hatanın değiştirilemez merkezi kaydı."""

    record_id: str
    timestamp: str
    category: str
    title: str
    user_message: str
    exception_type: str
    technical_summary: str
    developer_detail: str


# Aynı süreçte iki kaydın aynı numarayı almaması için son verilenler
# hatırlanır (bellek sınırlıdır).
_ISSUED_IDS = []
_ISSUED_LIMIT = 512


def _new_record_id(now=None):
    stamp = (now or datetime.now()).strftime("%Y%m%d")
    while True:
        candidate = f"{RECORD_ID_PREFIX}-{stamp}-{secrets.randbelow(0x10000):04X}"
        if candidate not in _ISSUED_IDS:
            _ISSUED_IDS.append(candidate)
            del _ISSUED_IDS[:-_ISSUED_LIMIT]
            return candidate


def _category_for(exc, title=""):
    """Ham istisna YALNIZ sınıflandırma için kullanılır."""
    if exc is None:
        return "bildirilen"
    name = type(exc).__name__
    message = str(exc).lower()
    if name in ("FileNotFoundError", "IsADirectoryError", "NotADirectoryError"):
        return "dosya"
    if name == "PermissionError":
        return "izin"
    if "mpv property does not exist" in message:
        return "oynatici"
    if name == "OSError":
        return "oynatici" if ("dll" in message or "cannot load" in message
                              or "dxv" in message) else "sistem"
    if name in ("ValueError", "TypeError", "KeyError", "IndexError"):
        return "veri"
    if name in ("ConnectionError", "TimeoutError"):
        return "ag"
    return "genel"


def _technical_summary(exc):
    """Sınıf adı + hatanın oluştuğu modül/fonksiyon/satır (yol içermez)."""
    if exc is None:
        return "istisna yok"
    name = type(exc).__name__
    frame = exc.__traceback__
    last = None
    while frame is not None:
        last = frame
        frame = frame.tb_next
    if last is None:
        return name
    code = last.tb_frame.f_code
    return (f"{name} @ {os.path.basename(code.co_filename)}:"
            f"{code.co_name}:{last.tb_lineno}")


def _traceback_text(exc):
    if exc is None:
        return ""
    return "".join(traceback.format_exception(type(exc), exc,
                                              exc.__traceback__))


def build_error_event(title, user_message, exc=None, details=None,
                      category=None):
    """Merkezi hata kaydını üretir. Diske veya ekrana YAZMAZ."""
    safe_message = redact(user_message)
    pieces = []
    if exc is not None:
        pieces.append(_traceback_text(exc))
    if details:
        pieces.append(str(details))
    return ErrorEvent(
        record_id=_new_record_id(),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        category=category or _category_for(exc, title),
        title=redact(title),
        user_message=safe_message,
        exception_type=type(exc).__name__ if exc is not None else "",
        technical_summary=redact(_technical_summary(exc)),
        developer_detail=redact("\n".join(piece for piece in pieces if piece)),
    )


# --- Saklama politikası (3. aşama) --------------------------------------
#
# ÜST SINIR: aktif dosya en fazla `MAX_LOG_FILE_BYTES`, yedek sayısı en
# fazla `LOG_BACKUP_COUNT`. Programın YÖNETEBİLDİĞİ normal dosyalarda
# toplam kullanım `MAX_LOG_FILE_BYTES * (LOG_BACKUP_COUNT + 1)` değerini
# aşmaz.
#
# Bu garanti "her koşulda" değildir ve olamaz: dosya sistemi ZATEN sınırı
# aşmışsa ve işletim sistemi o dosyanın silinmesine izin vermiyorsa
# program mevcut aşımı fiziksel olarak yok edemez. O durumda sözleşme
# şudur: yeni veri YAZILMAZ, mevcut aşım BÜYÜTÜLMEZ, akış fail-closed
# kalır (bkz. `_normalise_oversized()`).
#
# Rotasyon "mevcut boyut + YAZILACAK satır" hesabıyla, yazmadan ÖNCE
# yapılır. Eski kod yalnız mevcut boyuta bakıyordu; 2 MiB'ın hemen
# altındaki bir dosyaya tek bir 500 KB'lık kayıt yazıldığında aktif log
# 2,48 MiB'a çıkıyor ve yedek hiç oluşmuyordu.
MAX_LOG_FILE_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 1
MAX_LOG_RECORD_BYTES = 256 * 1024
LOG_TRUNCATED_MARK = " [kayıt boyut nedeniyle kısaltıldı]"
LOG_FILE_NAME = 'uygulama.log'

# Yazma, rotasyon ve temizleme AYNI kilidi paylaşır; yarım rotasyon veya
# temizleme sırasında yazma yarışı oluşmaz.
_LOG_LOCK = threading.RLock()

LOG_CLEARED_MESSAGE = "Günlükler temizlendi."
LOG_CLEAR_FAILED_MESSAGE = ("Günlükler temizlenemedi. Dosyalar başka bir "
                            "program tarafından kullanılıyor olabilir.")


@dataclass(frozen=True)
class LogClearResult:
    """`clear_logs()` sonucunun arayüze GÜVENLİ özeti."""

    ok: bool
    removed: tuple
    failed: tuple
    message: str


# Yol: APPDATA/MLCPlayer/logs/uygulama.log
def get_log_directory():
    """Günlük klasörü; oluşturulamazsa da yol döner."""
    appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
    log_dir = os.path.join(appdata, 'MLCPlayer', 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        pass
    return log_dir


def get_log_path():
    return os.path.join(get_log_directory(), LOG_FILE_NAME)


def _allowed_log_paths():
    """Uygulamanın yönettiği TEK dosya kümesi.

    Glob, recursive tarama veya kullanıcıdan gelen serbest yol YOKTUR.
    """
    base = get_log_path()
    return [base] + [f"{base}.{index}"
                     for index in range(1, LOG_BACKUP_COUNT + 1)]


# İzinli bir günlük girdisinin TÜRÜ. "Bağlantı" ile "incelenemedi" AYNI
# değerle temsil EDİLEMEZ: eski boolean yardımcı ikisini de `True`
# döndürüyor, `_normalise_oversized()` her `True`'yu gerçek bağlantı
# sanıp SİLİYORDU. Sentetik `lstat` hatasında mevcut tanı logu
# (`ORIGINAL-DIAGNOSTIC`) silinip yerine yeni kayıt yazıldı — bu
# fail-closed değildir.
ENTRY_MISSING = "missing"                  # giriş yok
ENTRY_REGULAR = "regular"                  # normal düzenli dosya
ENTRY_LINK_OR_REPARSE = "link_or_reparse"  # symlink / junction / reparse
ENTRY_UNKNOWN_OR_UNSAFE = "unknown"        # tür belirlenemedi: DOKUNMA


@dataclass(frozen=True)
class LogEntry:
    """`_classify_entry()` sonucu: tür + (yalnız REGULAR için) boyut."""

    kind: str
    size: int = 0


def _classify_entry(path):
    """İzinli bir yolu HEDEFİ TAKİP ETMEDEN sınıflandırır.

    TEK bir `os.lstat()` incelemesi yapılır; hedef dosya açılmaz,
    boyutu okunmaz ve `isfile/exists/getsize` gibi hedefi izleyen
    sorgular ÇAĞRILMAZ. `os.path.islink()` Windows'ta junction'ları
    görmediği için `st_file_attributes` içindeki
    `FILE_ATTRIBUTE_REPARSE_POINT` niteliği de aynı sonuçtan okunur;
    nitelik alanı olmayan platformlarda `os.path.islink()` yeterlidir.

    Dönüş:
      - `ENTRY_MISSING`           → giriş yok.
      - `ENTRY_REGULAR`           → normal dosya; `size` AYNI `lstat`ten.
      - `ENTRY_LINK_OR_REPARSE`   → yalnız GİRDİ kaldırılabilir.
      - `ENTRY_UNKNOWN_OR_UNSAFE` → dizin, izin hatası, beklenmeyen
        giriş türü. HİÇBİR mutasyon yapılmaz; `ENTRY_LINK_OR_REPARSE`
        gibi ele alınıp SİLİNMEZ.
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return LogEntry(ENTRY_MISSING)
    except (OSError, ValueError):
        return LogEntry(ENTRY_UNKNOWN_OR_UNSAFE)
    mode = info.st_mode
    if stat.S_ISLNK(mode):
        return LogEntry(ENTRY_LINK_OR_REPARSE)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if reparse and getattr(info, "st_file_attributes", 0) & reparse:
        return LogEntry(ENTRY_LINK_OR_REPARSE)
    if stat.S_ISREG(mode):
        return LogEntry(ENTRY_REGULAR, info.st_size)
    return LogEntry(ENTRY_UNKNOWN_OR_UNSAFE)     # dizin, FIFO, aygıt…


def get_log_files():
    """Var olan izinli günlük dosyalarının tam yolları.

    Yalnız `ENTRY_REGULAR` girdiler listelenir. Sınıflandırma ÖNCE
    yapılır: eski kod `os.path.isfile(path) and not _is_link…(path)`
    yazdığı için `and` soldan sağa değerlendiriliyor ve bağlantının
    HEDEF metadata'sı yine de sorgulanıyordu.
    """
    return [path for path in _allowed_log_paths()
            if _classify_entry(path).kind == ENTRY_REGULAR]


def get_log_usage():
    """Arayüz için güvenli kullanım özeti."""
    files = []
    total = 0
    with _LOG_LOCK:
        for path in _allowed_log_paths():
            # Sınıflandırma ÖNCE: bağlantı veya bilinmeyen girişte
            # `isfile/exists/getsize` çağrılmaz, hedef boyutu sayılmaz.
            entry = _classify_entry(path)
            size = entry.size if entry.kind == ENTRY_REGULAR else 0
            if entry.kind != ENTRY_MISSING:
                files.append((os.path.basename(path), size))
            total += size
    return {
        "files": tuple(files),
        "total_bytes": total,
        "limit_bytes": MAX_LOG_FILE_BYTES * (LOG_BACKUP_COUNT + 1),
    }


def format_bytes(size):
    """Kullanıcı dostu boyut metni (Türkçe ondalık ayracı)."""
    try:
        value = float(size)
    except (TypeError, ValueError):
        return "0 bayt"
    if value < 1024:
        return f"{int(value)} bayt"
    for unit in ("KB", "MB", "GB"):
        value /= 1024.0
        if value < 1024 or unit == "GB":
            return f"{value:.1f}".replace(".", ",") + f" {unit}"
    return f"{value:.1f} GB"


def _remove_log_entry(path):
    """İzinli TEK dosyayı siler. Link ise YALNIZ linkin kendisi silinir.

    Symlink/junction hedefi ASLA takip edilmez; hedef dosya truncate
    edilmez veya silinmez.
    """
    entry = _classify_entry(path)
    if entry.kind == ENTRY_MISSING:
        return False                # idempotent
    if entry.kind == ENTRY_LINK_OR_REPARSE:
        # YALNIZ bağlantı girdisi. `os.rmdir()` bir junction'da yalnız
        # reparse point'i kaldırır, hedef klasörün içeriğine dokunmaz.
        # (`os.path.islink()` Windows'ta junction'a `False` der; eski kod
        # bu yüzden junction'ı "dizin" sanıp hata veriyordu.)
        try:
            os.unlink(path)
        except OSError:
            os.rmdir(path)
        return True
    if entry.kind == ENTRY_REGULAR:
        os.remove(path)
        return True
    raise OSError("log_path_is_not_a_regular_file")   # dizin, aygıt…


def clear_logs():
    """İzinli günlük dosyalarını siler. Sonuç arayüz için güvenlidir.

    - Yalnız `uygulama.log` ve `uygulama.log.1`.
    - Dosya yoksa BAŞARILI sayılır (idempotent).
    - Dizinler ve ilgisiz dosyalar korunur.
    - Başarılı temizlikten sonra "temizlendi" diye YENİ kayıt yazılmaz.
    - Ham `OSError` metni kullanıcıya taşınmaz.
    """
    removed = []
    failed = []
    with _LOG_LOCK:
        for path in _allowed_log_paths():
            try:
                if _remove_log_entry(path):
                    removed.append(os.path.basename(path))
            except OSError:
                failed.append(os.path.basename(path))
    ok = not failed
    return LogClearResult(
        ok=ok, removed=tuple(removed), failed=tuple(failed),
        message=LOG_CLEARED_MESSAGE if ok else LOG_CLEAR_FAILED_MESSAGE)


def _truncate_record(line):
    """Tek kaydı `MAX_LOG_RECORD_BYTES` içine sığdırır.

    `MAX_LOG_RECORD_BYTES` DİSKE YAZILAN kaydın tamamını ifade eder;
    satır sonu baytı da bütçeden düşülür (eskiden `'\\n'` sonradan
    ekleniyor ve gerçek kayıt 262.145 bayt oluyordu).

    Kesim UTF-8 karakterini ORTADAN BÖLMEZ (`errors="ignore"` yarım
    kalan baytı düşürür), kısaltma işareti tam korunur ve maskelemeden
    SONRA yapıldığı için ham veriye dönüş olmaz.
    """
    limit = MAX_LOG_RECORD_BYTES - 1        # '\n' baytı ayrılır
    raw = line.encode('utf-8')
    if len(raw) <= limit:
        return line
    budget = limit - len(LOG_TRUNCATED_MARK.encode('utf-8'))
    clipped = raw[:max(0, budget)].decode('utf-8', errors='ignore')
    return clipped + LOG_TRUNCATED_MARK


def _normalise_oversized(path):
    """İzinli kümeyi yazılabilir hâle getirir; BAŞARIYI döndürür.

    İki iş yapar:

    1. **Bağlantı girdisi.** Aktif veya yedek ad symlink/junction/reparse
       point ise hedefi (uygulamanın yönetmediği bir dosya) okumak,
       boyutunu almak, truncate/append/replace etmek veya silmek YASAK.
       Yalnız bağlantı GİRDİSİNİN kendisi kaldırılır.
    2. **Aşırı büyük dosya.** Eski sürümden kalan, `MAX_LOG_FILE_BYTES`
       üstündeki izinli dosya silinir ve yeni aktif dosyayla devam
       edilir.

    Eski sürüm başarısızlığı YUTUYORDU (`continue`): silinemeyen büyük
    aktif dosya yine de yedeğe taşınıyor, silinemeyen büyük yedek varken
    aktife yeni kayıt ekleniyordu. Artık gerekli bir normalleştirme
    tamamlanamazsa `False` döner ve çağıran fail-closed davranır.

    FİZİKSEL SINIR: dosya sistemi zaten sınırı aşmışsa ve işletim
    sistemi silmeye izin vermiyorsa program mevcut aşımı yok EDEMEZ.
    Verilen garanti "yeni veri yazılmaz, mevcut aşım büyütülmez"dir.

    Yalnız izinli küme işlenir; glob, recursive silme veya serbest yol
    YOKTUR.
    """
    ok = True
    for candidate in _allowed_log_paths():
        entry = _classify_entry(candidate)
        if entry.kind == ENTRY_MISSING:
            continue
        if entry.kind == ENTRY_UNKNOWN_OR_UNSAFE:
            # Tür belirlenemedi: SİLİNMEZ, taşınmaz, üzerine yazılmaz.
            # Bilinmeyen bir girişi bağlantı sanıp kaldırmak gerçek bir
            # tanı logunu yok ediyordu.
            ok = False
            continue
        if entry.kind == ENTRY_LINK_OR_REPARSE:
            try:
                _remove_log_entry(candidate)    # YALNIZ girdi, hedef değil
            except OSError:
                ok = False      # bağlantı kaldırılamadı: yazma durur
            continue
        if entry.size > MAX_LOG_FILE_BYTES:     # ENTRY_REGULAR
            try:
                _remove_log_entry(candidate)
            except OSError:
                ok = False      # aşım duruyor: büyütülmez, taşınmaz
    return ok


def _prepare_log_file(path, incoming_bytes):
    """Yazmadan önce saklama sözleşmesini garanti eder.

    Dönüş `False` ise kayıt YAZILMAZ (fail-closed): normalleştirme veya
    rotasyon gerekli olduğu hâlde tamamlanamamıştır ve dolu dosyaya —
    ya da bir bağlantının hedefine — yazmak ilan edilen sözleşmeyi
    bozardı.
    """
    if not _normalise_oversized(path):
        return False
    # Normalleştirmeden sonra izinli girdiler YA yok YA normal dosyadır;
    # boyut yine hedefi takip etmeyen sınıflandırmadan okunur.
    active = _classify_entry(path)
    if active.kind == ENTRY_MISSING:
        return True
    if active.kind != ENTRY_REGULAR:
        return False                    # savunma amaçlı: yazma durur
    current = active.size
    if current == 0 or current + incoming_bytes <= MAX_LOG_FILE_BYTES:
        return True
    try:
        if LOG_BACKUP_COUNT >= 1:
            backup = f"{path}.1"
            if _classify_entry(backup).kind != ENTRY_MISSING:
                _remove_log_entry(backup)
            os.replace(path, backup)
        else:
            _remove_log_entry(path)
    except OSError:
        # Rotasyon gerekliydi ama yapılamadı: sınırı korumak için kayıt
        # DÜŞÜRÜLÜR. Konsola/kullanıcıya ham hata verilmez ve yeniden
        # loglama denenmez (özyineleme olmaz).
        return False
    return True


def log(message, level='INFO'):
    """Hata/geliştirici günlüğü. EXE'de konsol olmasa bile dosyaya yazılır.

    NİHAİ YAZMA SINIRI: mesaj diske yazılmadan önce her seviyede
    `redact()` süzgecinden geçer. Böylece `debug/info/error`, doğrudan
    `log()` çağrıları ve `MPVPlayer.log_handler` üzerinden gelen libmpv
    tanıları — yeni veya unutulmuş çağıranlar dahil — korunur.
    Maskeleme idempotenttir; zaten maskelenmiş kayıtlar değişmez.
    """
    try:
        safe = redact(message)
        line = _truncate_record(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] "
            f"{safe}")
        payload = (line + '\n').encode('utf-8')
        with _LOG_LOCK:
            path = get_log_path()
            if not _prepare_log_file(path, len(payload)):
                return          # fail-closed: sınır log kaybına yeğlenir
            with open(path, 'ab') as handle:
                handle.write(payload)
    except Exception:
        pass


def log_error_event(event):
    """Kaydı geliştirici loguna TEK kez yazar. Hata fırlatmaz."""
    try:
        header = (f"{event.record_id} | {event.category} | {event.title} | "
                  f"{event.user_message}")
        if event.exception_type:
            header += f" | {event.exception_type} | {event.technical_summary}"
        message = header
        if event.developer_detail:
            message += f"\nAyrıntı (maskelenmiş):\n{event.developer_detail}"
        log(message, 'ERROR')
    except Exception:
        # Kayıt tutulamaması kullanıcıya hata gösterimini ENGELLEMEZ.
        pass


def safe_console(message):
    """Üretim konsol çıktısının TEK güvenli sınırı.

    `main.py` ve `app/**/*.py` içindeki bütün konsol yazımları buradan
    geçer; stdout'a yazmadan hemen önce merkezi `redact()` uygulanır.
    Böylece ham yol, URL token'ı, `Authorization` değeri veya ham
    `str(exception)` konsola ULAŞMAZ ve yeni bir çağıran güvenlik
    sınırını sessizce atlayamaz (yapısal AST kapısı bunu kilitler).

    - Zararsız mesajlar aynen yazılır; `redact()` idempotenttir.
    - `None` ve string olmayan değerler güvenlidir.
    - Dosya loguna kayıt YAZMAZ: konsol ve dosya logu ayrı çıkışlardır.
    - Maskeleme beklenmedik biçimde hata verirse HAM mesaj yazılmaz;
      yerine sabit ve hassas olmayan bir metin yazılır.
    - Konsolun kapalı/yönlendirilmiş/bozuk olması uygulamayı çökertmez.
    """
    try:
        text = redact(message)
    except Exception:
        text = CONSOLE_REDACTION_FAILED
    try:
        # Merkezi çıkış noktası: yapısal kapı YALNIZ bu çağrıya izin
        # verir, üretim kodunda başka doğrudan `print()` bulunmaz.
        builtins.print(text)
    except Exception:
        # Konsol yoksa (EXE) veya yazma başarısızsa sessizce geçilir.
        pass


def debug(message):
    log(message, 'DEBUG')


def info(message):
    log(message, 'INFO')


def error(message):
    log(message, 'ERROR')


def _friendly_message(exc_type, exc_value):
    """Bilinen hataları anlaşılır Türkçe açıklamaya çevirir."""
    name = exc_type.__name__ if isinstance(exc_type, type) else str(exc_type)
    msg = str(exc_value) if exc_value else ''

    if name == 'FileNotFoundError':
        return ("Dosya bulunamadı. Dosya taşınmış veya silinmiş olabilir.\n\n"
                "Çözüm: Dosyanın yerini kontrol edip tekrar açmayı deneyin.")
    if name == 'PermissionError':
        return ("Dosyaya erişim izniniz yok.\n\n"
                "Çözüm: Dosyanın kilidini açın veya başka bir klasöre kopyalayın.")
    if name == 'NotADirectoryError' or name == 'IsADirectoryError':
        return "Seçilen konum geçerli bir medya dosyası değil."
    if 'mpv property does not exist' in msg:
        return ("Oynatıcı ayarı uygulanamadı (video ayarı desteklenmiyor).\n\n"
                "Bu işlem mpv'nin bu sürümünde bulunmayan bir özellik kullanmaya çalıştı. "
                "Diğer ayarlarla devam edebilirsiniz.")
    if name == 'OSError' and ('dxv' in msg.lower() or 'dll' in msg.lower() or 'cannot load' in msg.lower()):
        return ("MPV bileşeni yüklenemedi.\n\n"
                "Çözüm: Programın 'bin' klasörünün eksiksiz olduğundan emin olun. "
                "Programı kurulum klasöründen çalıştırın.")
    if name in ('ValueError', 'TypeError'):
        return ("Beklenmeyen bir veri hatası oluştu.\n\n"
                "Lütfen işlemi tekrar deneyin. Sorun devam ederse programı "
                "yeniden başlatın.")
    return None


def _open_error_details(parent, event):
    """Ayrı "Hata Ayrıntıları" penceresini açar.

    Yeni `ErrorEvent` ÜRETMEZ, ikinci log kaydı YAZMAZ, kayıt numarasını
    değiştirmez. Pencere açılamazsa ana hata akışı çökmez ve ikinci hata
    penceresi oluşturulmaz; yalnız güvenli tür bilgisi konsola yazılır.
    """
    try:
        # Lazy import: `app.error_details_dialog` bu modülü kullanır,
        # döngüsel import oluşmasın.
        from app.error_details_dialog import ErrorDetailsDialog

        dialog = ErrorDetailsDialog(event, parent)
        dialog.exec()
    except Exception as exc:
        safe_console("Hata ayrıntıları penceresi açılamadı: "
                     f"{type(exc).__name__}")


def _show_message_box(parent, event):
    """Kullanıcı penceresi. TEKNİK AYRINTI VERİLMEZ.

    `setDetailedText()` bilerek KULLANILMAZ. Ana kutuda kayıt numarası,
    istisna sınıfı, teknik özet ve traceback BULUNMAZ; bunlar yalnız
    kullanıcı `Hata Ayrıntılarını Görüntüle` düğmesine basarsa ayrı
    pencerede gösterilir.

    `Tamam` varsayılan VE Escape düğmesidir: Enter yanlışlıkla
    ayrıntıları açmaz.
    """
    box = QMessageBox(parent) if parent is not None else QMessageBox()
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(event.title)
    box.setText(event.user_message)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    ok_button = box.button(QMessageBox.StandardButton.Ok)
    details_button = box.addButton(DETAILS_BUTTON_TEXT,
                                   QMessageBox.ButtonRole.ActionRole)
    box.setDefaultButton(ok_button)
    box.setEscapeButton(ok_button)
    box.exec()
    # Ayrıntılar KENDİLİĞİNDEN açılmaz; ana kutu kapandıktan sonra ve
    # yalnız düğmeye basıldıysa açılır.
    if box.clickedButton() is details_button:
        _open_error_details(parent, event)
    return box


def show_error(title, message, details=None):
    """Kullanıcıya anlaşılır hata penceresi gösterir.

    `details` GERİYE DÖNÜK uyumluluk için kabul edilir; artık kullanıcıya
    gösterilmez, yalnız maskelenmiş biçimde loga girer.
    """
    event = build_error_event(title, message, details=details)
    log_error_event(event)
    _show_message_box(None, event)
    return event


def show_user_error(parent, title, user_message, exc=None, details=None):
    """Kullanıcıya sade bir hata mesajı gösterir.

    - `user_message`: Kullanıcının anlayacağı kısa Türkçe açıklama.
    - `exc` / `details`: YALNIZ geliştirici logu için; maskelenerek
      yazılır ve kullanıcı penceresine ULAŞMAZ.

    Dönüş: üretilen `ErrorEvent`. Mevcut çağrılar dönüşü kullanmadığı
    için geriye dönük uyumluluk korunur.
    """
    event = build_error_event(title, user_message, exc=exc, details=details)
    log_error_event(event)
    _show_message_box(parent, event)
    return event


def _handle_exception(exc_type, exc_value, exc_tb):
    """Yakalanmamış her Python hatası buraya düşer.

    Hata TEK kayıt numarasıyla bir kez loglanır; kullanıcı penceresi
    aynı traceback'i ikinci kez YAZMAZ.
    """
    friendly = _friendly_message(exc_type, exc_value)
    message = friendly or ("Beklenmeyen bir hata oluştu.\n\n"
                           "Program çalışmaya devam ediyor, ancak bu işlem "
                           "tamamlanamadı.\n"
                           "Sorun devam ederse programı yeniden başlatın.")
    title = "Beklenmeyen Hata"

    if exc_value is not None and getattr(exc_value, "__traceback__", None) is None:
        try:
            exc_value = exc_value.with_traceback(exc_tb)
        except Exception:
            pass
    detail = None
    if exc_value is None:
        detail = "".join(traceback.format_exception(exc_type, exc_value,
                                                    exc_tb))
    event = build_error_event(title, message, exc=exc_value, details=detail)
    log_error_event(event)
    # Geliştirici konsolu (varsa) da maskelenmiş metni görür.
    safe_console(event.developer_detail or event.technical_summary)

    try:
        _show_message_box(None, event)
    except Exception:
        pass
    return event


def install_exception_handler():
    """Uygulama başlangıcında çağrılır - tüm yakalanmamış hataları yakalar."""
    sys.excepthook = _handle_exception
