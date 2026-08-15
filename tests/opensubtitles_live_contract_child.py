"""Opt-in CANLI OpenSubtitles REST sozlesme harness'i.

CALISTIRMA
----------
    $env:MLC_OPENSUBTITLES_LIVE='1'
    python tests/opensubtitles_live_contract_child.py

Gercek indirme AYRI ve acik izin ister (kota tuketir):

    $env:MLC_OPENSUBTITLES_LIVE_DOWNLOAD='1'

Degisken yoksa "SKIPPED: OPT_IN_REQUIRED" yazip 0 doner. Normal pytest ve
normal `python main.py` bu harness'i ASLA calistirmaz.

GUVENLIK
--------
- API anahtari / kullanici adi / parola / token: komut satirinda TASINMAZ,
  stdout/stderr'e YAZILMAZ, marker'lara maskeli bile eklenmez, yeni duz
  metin dosyaya yazilmaz.
- Kimlik bilgileri YALNIZCA mevcut `SubtitleSettingsStore` yolundan
  READ-ONLY okunur; kullanici ayarlari degistirilmez veya temizlenmez.
- Kullanicinin video adi, yolu veya hash'i servise GONDERILMEZ. Arama sabit
  ve kamusal sentetik sorgudur.
- Indirme yalnizca benzersiz %TEMP% dizinine yazar ve try/finally ile
  temizlenir; mevcut dosyanin uzerine yazilmaz, MPV'ye uygulanmaz.
"""
import os
import shutil
import sys
import tempfile

LIVE = os.environ.get("MLC_OPENSUBTITLES_LIVE") == "1"
LIVE_DOWNLOAD = os.environ.get("MLC_OPENSUBTITLES_LIVE_DOWNLOAD") == "1"

if not LIVE:
    print("SKIPPED: OPT_IN_REQUIRED", flush=True)
    raise SystemExit(0)

PROJECT_ROOT = os.environ.get(
    "MLC_NATIVE_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from app import opensubtitles as osub  # noqa: E402
from app import subtitle_service as service  # noqa: E402
from app.subtitle_settings import SubtitleSettingsStore  # noqa: E402

# SABIT, kamusal, sentetik sorgu. Kullanici medyasi ASLA kullanilmaz.
QUERY = "The Matrix"
LANGUAGE = "tr"
failures = []
_secret_values = []


def mark(name, value=""):
    print(f"{name}={value}" if value != "" else name, flush=True)


def guard(text):
    """Metinde secret var mi? (Deger ASLA yazilmaz, yalnizca varligi.)"""
    blob = str(text)
    for secret in _secret_values:
        if secret and secret in blob:
            return True
    return False


def read_credentials():
    """Kimlik bilgilerini READ-ONLY okur. Hicbir yere yazmaz.

    NOT: `store.load_api_key()` KULLANILMAZ; o yol legacy duz metin gocunu
    tetikler ve gercek kullanici ayarlarina YAZABILIR. Harness kullanicinin
    ayarlarini degistirmemelidir, bu yuzden dogrudan kimlik deposundan
    okunur.
    """
    store = SubtitleSettingsStore()
    values = store.load()
    username = values.get("username", "")
    try:
        api_key = store.credentials.get_api_key() or ""
    except Exception:
        api_key = ""
    password = store.load_password(username) if username else ""
    for secret in (api_key, password):
        if secret:
            _secret_values.append(secret)
    return api_key, username, password


def check_schema(raw_items):
    """Yanit semasini GUVENLI bicimde dogrular; govde DUMP EDILMEZ."""
    if not isinstance(raw_items, list):
        return False, None, False
    if not raw_items:
        # Sonuc bulunmamasi API hatasi DEGILDIR.
        return True, None, False
    normalized = osub.normalize_results(raw_items)
    if not normalized:
        return False, None, False
    first = normalized[0]
    has_file_id = isinstance(first.get("file_id"), int)
    language_ok = str(first.get("language", "")).lower() == LANGUAGE
    schema_ok = bool(has_file_id and first.get("name") is not None)
    return schema_ok, first if has_file_id else None, language_ok


def run_download(client, file_id):
    """EN FAZLA BIR download istegi. Kota tuketir."""
    mark("LIVE_DOWNLOAD_REQUESTED", "True")
    mark("LIVE_DOWNLOAD_QUOTA_NOTICE",
         "bu adim OpenSubtitles indirme kotasini TUKETIR")
    workspace = tempfile.mkdtemp(prefix="mlc-live-dl-")
    target = os.path.join(workspace, "mlc-live-contract.srt")
    try:
        link = client.download_link(file_id)
        # `download_link` guvenilmeyen/eksik baglantiyi zaten reddeder.
        payload = client.fetch(link)
        mark("LIVE_DOWNLOAD_OK", "True")
        mark("LIVE_DOWNLOAD_BYTES", str(len(payload or b"")))

        if os.path.exists(target):
            failures.append("target_already_exists")
            return
        store = service.SubtitleStore()
        # `save` gercek SRT dogrulamasi yapar; HTML/JSON/zip kabul etmez.
        store.save(target, payload)
        mark("LIVE_SRT_VALID", "True")
    except service.NotSrtError:
        mark("LIVE_DOWNLOAD_OK", "True")
        mark("LIVE_SRT_VALID", "False")
        failures.append("content_not_srt")
    except osub.SubtitleServiceError as error:
        mark("LIVE_DOWNLOAD_OK", "False")
        message = osub.safe_message(error)
        if guard(message):
            failures.append("secret_in_download_message")
            message = "<redacted>"
        mark("LIVE_DOWNLOAD_MESSAGE", message)
        failures.append("download_failed")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
        mark("LIVE_TEMP_CLEANED", str(not os.path.exists(workspace)))


def main():
    mark("LIVE_OPT_IN", "True")
    api_key, username, password = read_credentials()
    mark("LIVE_CREDENTIALS_AVAILABLE", str(bool(api_key)))
    if not api_key:
        # Sahte deger UYDURULMAZ; kullanici anahtari uygulamanin
        # "Altyazi Merkezi > Ayarlar" bolumunden girmelidir.
        mark("LIVE_SEARCH", "SKIPPED_NO_API_KEY")
        mark("LIVE_SECRET_LEAK", "False")
        mark("LIVE_EXIT", "0")
        return 0

    client = osub.OpenSubtitlesClient(api_key=api_key, username=username,
                                      password=password)

    # --- Login sozlesmesi (opsiyonel) ---
    if username and password:
        try:
            client.login()
            mark("LIVE_LOGIN", "OK" if client.has_token() else "NO_TOKEN")
            if not client.has_token():
                failures.append("login_without_token")
        except osub.SubtitleServiceError as error:
            message = osub.safe_message(error)
            if guard(message):
                failures.append("secret_in_login_message")
                message = "<redacted>"
            mark("LIVE_LOGIN", "FAILED")
            mark("LIVE_LOGIN_MESSAGE", message)
            failures.append("login_failed")
    else:
        mark("LIVE_LOGIN", "SKIPPED_NO_USER_CREDENTIALS")

    # --- Arama sozlesmesi ---
    first = None
    try:
        raw = client.search(query=QUERY, languages=LANGUAGE)
        mark("LIVE_SEARCH_OK", "True")
        mark("LIVE_RESULT_COUNT", str(len(raw)))
        schema_ok, first, language_ok = check_schema(raw)
        mark("LIVE_SCHEMA_OK", str(schema_ok))
        mark("LIVE_HAS_FILE_ID", str(first is not None))
        mark("LIVE_LANGUAGE_MATCH", str(language_ok))
        if not schema_ok:
            failures.append("schema_mismatch")
    except osub.SubtitleServiceError as error:
        message = osub.safe_message(error)
        if guard(message):
            failures.append("secret_in_search_message")
            message = "<redacted>"
        mark("LIVE_SEARCH_OK", "False")
        mark("LIVE_SEARCH_MESSAGE", message)
        failures.append("search_failed")

    # --- Indirme: AYRI acik izin ---
    if not LIVE_DOWNLOAD:
        mark("LIVE_DOWNLOAD", "SKIPPED_NOT_AUTHORIZED")
    elif first is None:
        mark("LIVE_DOWNLOAD", "SKIPPED_NO_FILE_ID")
    else:
        run_download(client, first["file_id"])

    leaked = any(name.startswith("secret_in_") for name in failures)
    mark("LIVE_SECRET_LEAK", str(leaked))
    if failures:
        mark("LIVE_FAILURES", ",".join(sorted(set(failures))))
    code = 1 if failures else 0
    mark("LIVE_EXIT", str(code))
    return code


raise SystemExit(main())
