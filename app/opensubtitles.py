# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""OpenSubtitles REST istemcisi, güvenli hata eşlemesi ve kimlik saklama.

Kurallar:

- Güncel REST API kullanılır; eski XML-RPC/VLSub yolu YOKTUR.
- API anahtarı kaynağa gömülmez; yoksa HİÇBİR ağ isteği gönderilmez.
- API anahtarı ve parola log'a, `repr()`'a veya kullanıcı mesajına yazılmaz.
- Parola VE API anahtarı düz ayar dosyasına yazılmaz; Windows Credential
  Manager varsa oraya, yoksa yalnızca oturum belleğine alınır. İkisi AYRI
  target altında tutulur ve birbirine karışmaz.
- Ağ katmanı enjekte edilebilir (`transport`); testler gerçek internete çıkmaz.
- Yeni bağımlılık yoktur: yalnızca standart kütüphane kullanılır.
"""
import ctypes
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# Qt'yi import aninda YUKLEMEZ (bkz. app/translate.py); bu modul ag
# katmanidir ve arayuzden bagimsiz kalir.
from app.translate import tr_mark, translate_marked

API_ROOT = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "MLC Player Subtitle Center v1"
DEFAULT_TIMEOUT = 15
MAX_RETRY = 2
_SRT_FORMATS = {"srt", "subrip"}

# OpenSubtitles kota aşımını 406 ile de bildirir; 429 ile aynı anlamdadır.
RATE_LIMIT_STATUSES = (406, 429)

#: Servisin RESMI siniri: en fazla saniyede 1 istek. Bugune kadar yalniz
#: TEPKISEL davraniliyordu (`429/406` -> `RateLimitError`); onleyici
#: araliklama YOKTU ve arama + indirme arka arkaya tetiklendiginde sinir
#: asilabiliyordu. Servis "uygulama basina tek anahtar" kuralini ihlal eden
#: istemcilerin erisimini engelleyebiliyor, bu yuzden sinir istemci
#: tarafinda da korunur.
MIN_REQUEST_INTERVAL_S = 1.0

# Altyazı dosyası için makul üst sınır. Daha büyük yanıt altyazı değildir;
# belleğe alınmaz ve diske yazılmaz.
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024


# --- Hatalar: mesajlar Türkçe ve HASSAS VERİ İÇERMEZ ---

class SubtitleServiceError(Exception):
    user_message = tr_mark("Altyazı servisinde beklenmeyen bir sorun oluştu.")


class MissingCredentialsError(SubtitleServiceError):
    user_message = tr_mark("OpenSubtitles API anahtarı tanımlı değil. "
                           "Altyazı Merkezi > Ayarlar bölümünden ekleyin.")


class AuthError(SubtitleServiceError):
    user_message = tr_mark("OpenSubtitles kimlik doğrulaması başarısız. "
                           "API anahtarı, kullanıcı adı ve parolayı kontrol edin.")


class RateLimitError(SubtitleServiceError):
    user_message = tr_mark("OpenSubtitles indirme/istek sınırına ulaşıldı. "
                           "Bir süre sonra tekrar deneyin.")


class ServerError(SubtitleServiceError):
    user_message = tr_mark("OpenSubtitles sunucusu şu anda yanıt veremiyor. "
                           "Daha sonra tekrar deneyin.")


class NetworkTimeoutError(SubtitleServiceError):
    user_message = tr_mark("Bağlantı zaman aşımına uğradı. "
                           "İnternet bağlantınızı kontrol edip tekrar deneyin.")


class NetworkError(SubtitleServiceError):
    user_message = tr_mark("Ağ bağlantısı kurulamadı. "
                           "İnternet bağlantınızı kontrol edin.")


class InvalidResponseError(SubtitleServiceError):
    user_message = tr_mark("Servis yanıtı geçersiz. "
                           "Daha sonra tekrar deneyin.")


class OversizedResponseError(SubtitleServiceError):
    user_message = tr_mark("İndirilen dosya beklenenden çok büyük; "
                           "güvenlik için reddedildi.")


class UntrustedUrlError(SubtitleServiceError):
    user_message = tr_mark("Güvenilmeyen bir indirme adresi reddedildi. "
                           "İndirme yapılmadı.")


# Yalnızca bu alan adlarından HTTPS ile indirme yapılır.
TRUSTED_HOST_SUFFIX = ".opensubtitles.com"
TRUSTED_HOSTS = {"opensubtitles.com", "api.opensubtitles.com"}


def _is_trusted_host(host):
    host = (host or "").lower().strip()
    if not host:
        return False
    return host in TRUSTED_HOSTS or host.endswith(TRUSTED_HOST_SUFFIX)


def is_trusted_download_url(url):
    """HTTPS ve güvenilir OpenSubtitles alan adı zorunludur."""
    try:
        parts = urllib.parse.urlsplit(url or "")
    except Exception:
        return False
    if parts.scheme != "https":
        return False
    return _is_trusted_host(parts.hostname)


def safe_message(error):
    """Kullanıcıya gösterilecek güvenli metin: traceback/gizli veri yok."""
    return translate_marked(
        getattr(error, "user_message", SubtitleServiceError.user_message))


# --- Ağ katmanı (enjekte edilebilir) ---

class TrustedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect zincirindeki HER hedefi yeniden doğrular.

    İlk URL güvenilir olsa bile sunucu bizi başka bir hosta ya da düz HTTP'ye
    yönlendirebilir. urllib bunu sessizce izlerdi; burada güvenilmeyen hedef
    REDDEDİLİR.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_trusted_download_url(newurl):
            raise UntrustedUrlError("untrusted redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibTransport:
    """Standart kütüphane tabanlı HTTPS taşıyıcı."""

    def __init__(self, context=None):
        self._context = context or ssl.create_default_context()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._context),
            TrustedRedirectHandler())

    def request(self, method, url, *, headers=None, body=None, timeout=None):
        request = urllib.request.Request(url, data=body, method=method,
                                         headers=headers or {})
        try:
            with self._opener.open(
                    request, timeout=timeout or DEFAULT_TIMEOUT) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                # ÜST SINIR: aşırı büyük gövde belleğe alınmaz.
                raw = response.read(MAX_DOWNLOAD_BYTES + 1)
                return status, dict(response.headers), raw
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers or {}), exc.read(
                MAX_DOWNLOAD_BYTES + 1)
        except UntrustedUrlError:
            raise
        except TimeoutError:
            raise
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise TimeoutError("timeout") from None
            raise ConnectionError("network") from None


# --- Kimlik saklama ---

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
# CredDeleteW zaten olmayan bir kaydı silmeye çalışınca bunu döner. Silme
# İDEMPOTENT olmalı: yok olan kayıt zaten istenen son durumdur.
ERROR_NOT_FOUND = 1168

# `set_secret()` sonuçları — kullanıcıya doğru kalıcılık sözü vermek için.
STORAGE_CREDENTIAL_MANAGER = "credential_manager"
STORAGE_SESSION_MEMORY = "session_memory"


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32),
                ("dwHighDateTime", ctypes.c_uint32)]


class CREDENTIALW(ctypes.Structure):
    """Windows `CREDENTIALW` — alanlar TYPED; sabit ofset kullanılmaz."""

    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


def _advapi32():
    library = ctypes.WinDLL("advapi32", use_last_error=True)
    library.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), ctypes.c_uint32]
    library.CredWriteW.restype = ctypes.c_bool
    library.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32,
                                  ctypes.c_uint32,
                                  ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
    library.CredReadW.restype = ctypes.c_bool
    library.CredDeleteW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32,
                                    ctypes.c_uint32]
    library.CredDeleteW.restype = ctypes.c_bool
    library.CredFree.argtypes = [ctypes.c_void_p]
    library.CredFree.restype = None
    return library


class CredentialStore:
    """Kullanıcı adı ayar dosyasında; PAROLA ve API ANAHTARI asla düz metinde.

    Oturum belleği fallback'i TARGET BAZLIDIR. Tek bir `_session_password`
    alanı kullanmak, A kullanıcısının parolasının B kullanıcısı sorulduğunda
    dönmesine yol açıyordu; burada her target'ın kendi girdisi vardır ve
    parola ile API anahtarı AYRI target'lar altındadır.
    """

    def __init__(self, namespace="MLCPlayer/OpenSubtitles", settings_dir=None,
                 use_credential_manager=True):
        self.namespace = namespace
        self.settings_dir = settings_dir
        # Testler gerçek Credential Manager'ı kirletmemek için bunu kapatabilir.
        self.use_credential_manager = use_credential_manager
        # target -> secret. Worker thread'lerden de okunabildiği için kilitli.
        self._session_secrets = {}
        self._session_lock = threading.Lock()

    def _settings_file(self):
        if not self.settings_dir:
            return None
        return os.path.join(self.settings_dir, "subtitle_center.json")

    def set_username(self, username):
        path = self._settings_file()
        if not path:
            return
        os.makedirs(self.settings_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"username": username or ""}, handle, ensure_ascii=False)

    def get_username(self):
        path = self._settings_file()
        if not path or not os.path.exists(path):
            return ""
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle).get("username", "")
        except Exception:
            return ""

    # --- Genel secret API'si (target bazlı) ---

    def set_secret(self, target, secret, account=None):
        """Secret'ı Credential Manager'a yazar; olmazsa OTURUM belleğine.

        Dönen değer çağırana gerçek kalıcılığı söyler:
        `STORAGE_CREDENTIAL_MANAGER` veya `STORAGE_SESSION_MEMORY`.
        """
        if self._write_windows_credential(target, secret, account):
            # Kalıcı yazıldı: aynı target'ın bayat oturum kopyası bırakılmaz.
            with self._session_lock:
                self._session_secrets.pop(target, None)
            return STORAGE_CREDENTIAL_MANAGER
        with self._session_lock:
            self._session_secrets[target] = secret
        return STORAGE_SESSION_MEMORY

    def get_secret(self, target):
        stored = self._read_windows_credential(target)
        if stored is not None:
            return stored
        with self._session_lock:
            # YALNIZCA bu target'ın oturum kopyası; başka kimliğinki değil.
            return self._session_secrets.get(target)

    def delete_secret(self, target):
        """İDEMPOTENT siler: kayıt zaten yoksa da başarı sayılır."""
        with self._session_lock:
            self._session_secrets.pop(target, None)
        if os.name != "nt" or not self.use_credential_manager:
            return True
        try:
            library = _advapi32()
            if library.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
                return True
            # "Zaten yok" istenen son durumdur; hata değildir.
            return ctypes.get_last_error() == ERROR_NOT_FOUND
        except Exception:
            return False

    # --- Parola (kullanıcı adına bağlı) ---

    def set_password(self, username, password):
        """Windows Credential Manager'a yazar; olmazsa yalnız oturum belleği."""
        return self.set_secret(self._target(username), password,
                               account=username or "default")

    def get_password(self, username):
        return self.get_secret(self._target(username))

    # --- API anahtarı (kullanıcı adından BAĞIMSIZ, ayrı target) ---

    def set_api_key(self, api_key):
        return self.set_secret(self._api_target(), api_key,
                               account="api-key")

    def get_api_key(self):
        return self.get_secret(self._api_target())

    def delete_api_key(self):
        return self.delete_secret(self._api_target())

    # -- Windows Credential Manager (ctypes; ek bağımlılık yok) --

    def _target(self, username):
        return f"{self.namespace}/{username or 'default'}"

    def _api_target(self):
        """API anahtarı target'ı parola target'larıyla ASLA çakışmaz.

        Parola target'ı `<namespace>/<kullanıcı>` biçimindedir; burada
        namespace'in kendisi farklıdır (`<namespace>.ApiKey/...`), bu yüzden
        kullanıcı adı ne olursa olsun iki uzay kesişmez.
        """
        return f"{self.namespace}.ApiKey/default"

    def _write_windows_credential(self, target, password, account=None):
        if os.name != "nt" or not self.use_credential_manager:
            return False
        try:
            blob = (password or "").encode("utf-16-le")
            buffer = ctypes.create_string_buffer(blob, len(blob))
            credential = CREDENTIALW()
            credential.Type = CRED_TYPE_GENERIC
            credential.TargetName = target
            credential.CredentialBlobSize = len(blob)
            credential.CredentialBlob = ctypes.cast(
                buffer, ctypes.POINTER(ctypes.c_byte))
            credential.Persist = CRED_PERSIST_LOCAL_MACHINE
            credential.UserName = account or "default"
            return bool(_advapi32().CredWriteW(ctypes.byref(credential), 0))
        except Exception:
            return False

    def _read_windows_credential(self, target):
        if os.name != "nt" or not self.use_credential_manager:
            return None
        try:
            pointer = ctypes.POINTER(CREDENTIALW)()
            if not _advapi32().CredReadW(target,
                                         CRED_TYPE_GENERIC, 0,
                                         ctypes.byref(pointer)):
                return None
            try:
                # TYPED yapı üzerinden okunur; sabit pointer ofseti YOKTUR.
                record = pointer.contents
                size = int(record.CredentialBlobSize)
                if size <= 0 or not record.CredentialBlob:
                    return ""
                raw = ctypes.string_at(record.CredentialBlob, size)
                return raw.decode("utf-16-le")
            finally:
                _advapi32().CredFree(pointer)
        except Exception:
            return None

    def delete_password(self, username):
        """Yalnız BU kullanıcının kaydını siler; diğerlerine dokunmaz."""
        return self.delete_secret(self._target(username))


# --- İstemci ---

class OpenSubtitlesClient:
    def __init__(self, api_key=None, transport=None, username=None,
                 password=None, timeout=DEFAULT_TIMEOUT):
        self._api_key = api_key or ""
        self._username = username or ""
        self._password = password or ""
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._token = None            # YALNIZ bellekte tutulur
        self._base_url = API_ROOT
        self._login_rejected = False  # 401 sonrasi tekrar giris denenmez
        # HIZ SINIRI durumu. Ag cagrilari QThread worker'larinda calisir
        # (bkz. `subtitle_search_controller`); GUI thread'i BLOKLANMAZ.
        # Saat ve uyku ayri isim olarak tutulur: testler gercek zaman
        # beklemeden deterministik olcum yapabilsin.
        self._monotonic = time.monotonic
        self._sleep = time.sleep
        self._request_lock = threading.Lock()
        self._last_request_at = None

    def has_token(self):
        return bool(self._token)

    def login(self):
        """POST /login — token yalnız bellekte, base_url dogrulanir.

        401 alindiginda bayrak set edilir ve TEKRAR giris denenmez.
        """
        if not self._api_key:
            raise MissingCredentialsError()
        if self._login_rejected:
            raise AuthError("login previously rejected")
        if not (self._username and self._password):
            raise MissingCredentialsError()
        try:
            payload = self._call("POST", "/login",
                                 body={"username": self._username,
                                       "password": self._password},
                                 retry=False, use_base=False)
        except AuthError:
            self._login_rejected = True
            raise
        self._token = (payload or {}).get("token") or None
        base = (payload or {}).get("base_url") or ""
        if base:
            host = base if "//" in base else f"https://{base}"
            parsed = urllib.parse.urlsplit(host)
            # Guvenilmeyen base_url YOK SAYILIR; varsayilan kok korunur.
            if _is_trusted_host(parsed.hostname):
                self._base_url = f"https://{parsed.hostname}/api/v1"
        return bool(self._token)

    # Gizli veri repr/str'a SIZDIRILMAZ.
    def __repr__(self):
        return (f"<OpenSubtitlesClient configured={bool(self._api_key)} "
                f"user_set={bool(self._username)}>")

    __str__ = __repr__

    @property
    def configured(self):
        return bool(self._api_key)

    def _headers(self):
        headers = {"Api-Key": self._api_key, "User-Agent": USER_AGENT,
                   "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _respect_rate_limit(self):
        """Bir onceki istekten bu yana ARALIK dolmadiysa bekler.

        Servisin resmi siniri saniyede 1 istektir. Bekleme worker
        thread'indedir; GUI donmaz (bkz. `__init__` notu). Kilit, es
        zamanli worker'larin ayni pencerede iki istek gondermesini
        engeller.

        Saat GERI giderse (NTP duzeltmesi, uyku) fark negatif cikar ve
        sinirsiz bekleme dogardi; bu yuzden bekleme aralikla SINIRLANIR.
        """
        with self._request_lock:
            now = self._monotonic()
            previous = self._last_request_at
            if previous is not None:
                waited = now - previous
                remaining = MIN_REQUEST_INTERVAL_S - waited
                if remaining > 0:
                    self._sleep(min(remaining, MIN_REQUEST_INTERVAL_S))
                    now = self._monotonic()
            self._last_request_at = now

    def _call(self, method, path, params=None, body=None, retry=True,
              use_base=True):
        if not self._api_key:
            # ANAHTAR YOKSA AĞA ÇIKILMAZ.
            raise MissingCredentialsError()
        url = (self._base_url if use_base else API_ROOT) + path
        if params:
            pairs = "&".join(
                f"{key}={urllib.request.quote(str(value))}"
                for key, value in params.items() if value not in (None, ""))
            if pairs:
                url = f"{url}?{pairs}"
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = self._headers()
        if payload is not None:
            headers["Content-Type"] = "application/json"

        self._respect_rate_limit()

        # KOTA GÜVENLİĞİ: yalnız idempotent GET tekrar denenir. POST
        # (/download, /login) timeout veya 5xx sonrasi ASLA tekrarlanmaz.
        budget = MAX_RETRY if (retry and method.upper() == "GET") else 0
        last_error = None
        for attempt in range(budget + 1):
            try:
                status, _, raw = self._transport.request(
                    method, url, headers=headers, body=payload,
                    timeout=self._timeout)
            except TimeoutError:
                last_error = NetworkTimeoutError()
                if attempt >= budget:
                    raise last_error from None
                continue
            except SubtitleServiceError:
                # POLİTİKA/GÜVENLİK hatası (ör. güvenilmeyen redirect).
                # Sıradan bir ağ arızası DEĞİLDİR: türü korunur ve ASLA
                # tekrar denenmez. Aksi halde kullanıcı "ağ bağlantısı
                # kurulamadı" görüyor ve istek yeniden gönderiliyordu.
                raise
            except Exception:
                last_error = NetworkError()
                if attempt >= budget:
                    raise last_error from None
                continue

            if status in (401, 403):
                raise AuthError(str(status))
            if status in RATE_LIMIT_STATUSES:
                raise RateLimitError(str(status))
            if status >= 500:
                if attempt >= budget:
                    raise ServerError(str(status))
                continue
            if status >= 400:
                raise SubtitleServiceError(str(status))
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                # Geçersiz JSON BOŞ SONUÇ gibi gösterilmez.
                raise InvalidResponseError("invalid json") from None
        raise last_error or SubtitleServiceError()

    def search(self, **params):
        """`/subtitles` — ŞEMA doğrulanır.

        Boş `data` listesi geçerli bir "sonuç yok" yanıtıdır. Ancak `data`
        anahtarının hiç olmaması ya da liste olmaması sözleşme ihlalidir ve
        sessizce "sonuç yok" gibi gösterilmez.
        """
        payload = self._call("GET", "/subtitles", params=params)
        if not isinstance(payload, dict) or "data" not in payload:
            raise InvalidResponseError("missing data")
        data = payload.get("data")
        if not isinstance(data, list):
            raise InvalidResponseError("data is not a list")
        return data

    def download_link(self, file_id):
        # retry=False: kota tüketen POST tekrar gönderilmez.
        payload = self._call("POST", "/download", body={"file_id": file_id},
                             retry=False)
        link = (payload or {}).get("link", "")
        if not link:
            # Sessiz boş bağlantı, çağırana "güvenilmeyen adres" gibi
            # görünüyordu; gerçek neden ŞEMA ihlalidir.
            raise InvalidResponseError("missing link")
        if not is_trusted_download_url(link):
            raise UntrustedUrlError("untrusted link")
        return link

    def fetch(self, url):
        if not self._api_key:
            raise MissingCredentialsError()
        if not is_trusted_download_url(url):
            raise UntrustedUrlError("untrusted url")
        try:
            status, _, raw = self._transport.request(
                "GET", url, headers={"User-Agent": USER_AGENT},
                timeout=self._timeout)
        except TimeoutError:
            raise NetworkTimeoutError() from None
        except SubtitleServiceError:
            # Politika/güvenlik hatası aynen korunur (bkz. `_call`).
            raise
        except Exception:
            raise NetworkError() from None
        if status in (401, 403):
            raise AuthError(str(status))
        if status == 429:
            raise RateLimitError(str(status))
        if status >= 500:
            raise ServerError(str(status))
        if status >= 400:
            # 404/410 gibi cevapların GÖVDESİ altyazı verisi değildir;
            # SRT'ye benzese bile döndürülmez.
            raise SubtitleServiceError(str(status))
        if raw is not None and len(raw) > MAX_DOWNLOAD_BYTES:
            # Aşırı büyük içerik altyazı değildir: diske YAZILMAZ.
            raise OversizedResponseError("response too large")
        return raw


# --- Sonuç işleme ---

def _attributes(item):
    return item.get("attributes", item) if isinstance(item, dict) else {}


def normalize_results(raw_items):
    """Resmî `/subtitles` yanıtını düz sonuç kayıtlarına çevirir.

    `file_id` NESTED `attributes.files[]` içinden alınır; üst seviyedeki
    `id` (subtitle id) indirme için kullanılamaz. `files` boşsa kayıt düşer.
    """
    normalized = []
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        # Zaten düzleştirilmiş kayıtlar (ör. testlerin sade şeması) olduğu
        # gibi geçer; iki kez normalize edilmez.
        if "attributes" not in item and item.get("file_id") is not None:
            normalized.append(dict(item))
            continue
        data = _attributes(item)
        files = data.get("files") or []
        if not files:
            continue
        first = files[0] if isinstance(files[0], dict) else {}
        file_id = first.get("file_id")
        if file_id is None:
            continue
        normalized.append({
            "file_id": file_id,
            "file_name": first.get("file_name") or "",
            "name": (data.get("release") or data.get("feature_details", {})
                     .get("title") if isinstance(
                         data.get("feature_details"), dict) else None)
            or data.get("release") or first.get("file_name") or "",
            "release": data.get("release") or "",
            "language": str(data.get("language") or "").lower(),
            "format": str(data.get("format")
                          or data.get("file_format") or "srt").lower(),
            "downloads": data.get("download_count") or data.get("downloads") or 0,
            "ratings": data.get("ratings") or 0,
            "fps": data.get("fps"),
            "moviehash_match": bool(data.get("moviehash_match")),
            "hearing_impaired": bool(data.get("hearing_impaired")),
        })
    return normalized


def filter_results(results, language):
    """Yalnız seçili dil ve GERÇEK SRT sonuçları."""
    kept = []
    for item in results or []:
        data = _attributes(item)
        if str(data.get("language", "")).lower() != str(language).lower():
            continue
        fmt = str(data.get("format") or data.get("file_format") or "srt").lower()
        if fmt not in _SRT_FORMATS:
            continue
        kept.append(item)
    return kept


def rank_results(results):
    """Hash eşleşmeleri en üstte; sonra indirme/puan."""
    def sort_key(item):
        data = _attributes(item)
        return (
            0 if data.get("moviehash_match") else 1,
            -float(data.get("downloads") or 0),
            -float(data.get("ratings") or 0),
        )

    ranked = sorted(results or [], key=sort_key)
    for index, item in enumerate(ranked):
        item["best_match"] = index == 0
    return ranked


def build_search_plan(video_path, movie_hash, file_size, parsed, language):
    """Arama sırası: 1) hash+boyut 2) temizlenmiş ad 3) elle sezon/bölüm."""
    plan = []
    if movie_hash:
        plan.append({"moviehash": movie_hash, "moviebytesize": file_size,
                     "languages": language})
    query = {"query": parsed.get("title") or "", "languages": language}
    if parsed.get("is_series"):
        query["season_number"] = parsed.get("season")
        query["episode_number"] = parsed.get("episode")
    elif parsed.get("year"):
        query["year"] = parsed.get("year")
    plan.append(query)
    return plan


# --- Arama worker'ı (iptal edilebilir, zorla sonlandırma YOK) ---

class SubtitleSearchWorker:
    """Ağ aramasını ana thread dışında yürütmek için taşınabilir gövde.

    Qt tarafı bu gövdeyi bir QThread'e taşır. İptal bayrağı kooperatiftir;
    thread zorla öldürülmez, `finished` sonrası temizlenir.
    """

    def __init__(self, client, plan, on_results=None, on_error=None):
        self.client = client
        self.plan = list(plan or [])
        self.on_results = on_results
        self.on_error = on_error
        self._cancelled = False
        self._finished = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    def is_finished(self):
        return self._finished

    def run(self, language="tr"):
        try:
            for step in self.plan:
                if self._cancelled:
                    return []
                results = self.client.search(**step)
                if self._cancelled:
                    return []
                # GERÇEK zincir: search -> normalize -> filter -> rank.
                # normalize_results resmî nested `attributes.files[]`
                # şemasından düz `file_id` çıkarır; kullanılabilir dosyası
                # olmayan kayıtlar güvenle düşer.
                ranked = rank_results(
                    filter_results(normalize_results(results), language))
                if ranked:
                    if self.on_results:
                        self.on_results(ranked)
                    return ranked
            if self.on_results:
                self.on_results([])
            return []
        except SubtitleServiceError as error:
            if self.on_error and not self._cancelled:
                self.on_error(safe_message(error))
            return []
        finally:
            self._finished = True
