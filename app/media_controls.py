import os
import re
import time
from urllib.parse import urlsplit
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QInputDialog, QLineEdit, QStyle
from PyQt6.QtCore import QDateTime, QStandardPaths
from PyQt6.QtGui import QColor

import mpv
from app.config import MEDIA_EXTENSIONS, SUBTITLE_EXTENSIONS, DEFAULT_VOLUME, MAX_VOLUME
from app.utils import format_time, time_to_seconds
from app.errors import show_user_error, safe_console
from app.media_info import sanitize_media_url
from app.runtime_binaries import (INTERNET_VIDEO_MISSING_MESSAGE,
                                  INTERNET_VIDEO_MISSING_TITLE)
from app.i18n import tr, tr_mark, translate_marked

def toggle_mute(player):
    try:
        current_volume = player.mpv_player.volume
    except Exception as e:
        safe_console(f"Ses seviyesi okunamadı: {e}")
        current_volume = 0

    if current_volume > 0:
        # Sessize al
        player.last_volume = current_volume
        player.mpv_player.volume = 0
        player.volume_slider.setValue(0)
        player.volume_label.setText("%0")
        player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
        player.is_muted = True
        if getattr(player, '_ui_ready', False):
            player.video_frame.show_osd(tr("Sessiz"))
    else:
        # Sessizden çık - last_volume 0 ise varsayılan ses seviyesine dön
        restore = player.last_volume if player.last_volume > 0 else DEFAULT_VOLUME
        restore = min(MAX_VOLUME, max(0, float(restore)))
        player.mpv_player.volume = restore
        player.volume_slider.setValue(int(restore))
        player.volume_label.setText(f"%{int(restore)}")
        player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        player.is_muted = False
        if getattr(player, '_ui_ready', False):
            player.video_frame.show_osd(f"{tr('Ses')}: %{int(restore)}")

def _refresh_overlay_subtitle_state(player):
    """Altyazı durumu değiştikten sonra overlay CC göstergesini tazeler."""
    frame = getattr(player, "video_frame", None)
    refresh = getattr(frame, "_update_overlay_subtitle_state", None)
    if callable(refresh):
        refresh()


def _reset_subtitle_timing_for_new_media(player):
    """Dosyaya özel altyazı gecikmesini yeni medyaya taşımayı önler."""
    try:
        player.mpv_player.sub_delay = 0.0
    except Exception:
        pass
    settings = getattr(player, "settings", None)
    if settings is not None:
        settings.setValue("subtitle/sub_delay", 0.0)


def _clear_title_bar_raise(player):
    """Gerçek yeni yükleme girişimi başlarken eski pending'i temizler."""
    clear = getattr(player, "clear_title_bar_raise_pending", None)
    if callable(clear):
        clear()


def _mark_title_bar_raise(player):
    """Başarılı oynatma sonrası tek seferlik başlık çubuğu z-order yenilemesi.

    Ürün yaşam döngüsü bağlantısı; test double'ları bu metodu tanımlamak
    zorunda değildir.
    """
    mark = getattr(player, "mark_title_bar_raise_pending", None)
    if callable(mark):
        mark()


def _hide_subtitles_for_new_media(player):
    """Yeni medya otomatik bulunan altyazıyla başlasa bile görünürlüğü kapatır."""
    try:
        player.mpv_player.sub_visibility = False
    except Exception:
        pass


def append_media_paths(player, paths):
    """Bırakılan medyaları mevcut sırayı bozmadan oynatma listesine ekler."""
    additions = [path for path in paths if path]
    if not additions:
        return
    start_index = len(player.playlist)
    player.playlist.extend(additions)
    if not getattr(player, "current_file", ""):
        play_from_playlist(player, start_index)
    else:
        _refresh_playlist_panel(player)


def open_file(player):
    file_path, _ = QFileDialog.getOpenFileName(
        player, tr("Dosya Aç"), player.last_dir,
        f"{tr('Medya Dosyaları')} ({MEDIA_EXTENSIONS})"
    )
    if file_path:
        open_path(player, file_path)

def media_suffixes():
    """`MEDIA_EXTENSIONS` filtresinden karşılaştırılabilir uzantı kümesi.

    Uzantı listesi TEK kaynaktan (`app.config`) okunur; dosya iletişim
    kutusu filtresi ile klasör taraması ayrışmaz. Uzantısız dosyalar,
    kısayollar ve desteklenmeyen türler bu kümede yer almadığı için
    otomatik olarak dışarıda kalır.
    """
    return {pattern.lstrip("*").lower()
            for pattern in MEDIA_EXTENSIONS.split() if pattern.strip()}


def natural_sort_key(name):
    """`Bölüm 2` < `Bölüm 10` veren doğal sıralama anahtarı.

    Sözlük sırası kullanıcıya `1, 10, 2` gösterirdi. Sayı blokları sayısal,
    metin blokları büyük/küçük harf duyarsız karşılaştırılır; yalnız harf
    büyüklüğüyle ayrışan adlar için ham ad deterministik eşitlik bozucudur.
    """
    chunks = []
    for part in re.split(r"(\d+)", name):
        if not part:
            continue
        if part.isdigit():
            chunks.append((1, int(part), ""))
        else:
            chunks.append((0, 0, part.casefold()))
    return (chunks, name)


def folder_media_files(folder):
    """Klasördeki oynatılabilir medyayı DOĞAL sırayla döndürür.

    Alt klasörler taranmaz: kullanıcı seçtiği klasörün içeriğini bekler,
    derin bir ağacı sessizce oynatma listesine dökmek sürpriz olur.
    Okuma hatasında `None` döner; tek bir bozuk kayıt bütün taramayı
    düşürmez. Klasör okunamadıysa çağıran state'i DEĞİŞTİRMEZ.
    """
    suffixes = media_suffixes()
    try:
        names = os.listdir(folder)
    except OSError as e:
        safe_console(f"Klasör okunamadı: {e}")
        return None
    files = []
    seen = set()
    for name in sorted(names, key=natural_sort_key):
        if os.path.splitext(name)[1].lower() not in suffixes:
            continue
        path = os.path.join(folder, name)
        try:
            if not os.path.isfile(path):
                continue
        except OSError as e:
            safe_console(f"Klasör kaydı atlandı: {e}")
            continue
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        files.append(path)
    return files


def _folder_dialog_start(player):
    """Klasör diyaloğunun açılacağı güvenli başlangıç konumu."""
    last_dir = getattr(player, "last_dir", "") or ""
    if isinstance(last_dir, str) and os.path.isdir(last_dir):
        return last_dir
    return QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.MoviesLocation) or ""


def open_folder(player):
    """Bir klasörü seçip içindeki medyayı oynatma listesi olarak açar.

    State ATOMİK değişir: mevcut oynatma listesi ancak yeni liste eksiksiz
    hazırlandıktan sonra değiştirilir. İptal, boş klasör, okuma hatası ve
    diyalog hatasında hiçbir alan değişmez.
    """
    try:
        folder = QFileDialog.getExistingDirectory(
            player, tr("Klasör Aç"), _folder_dialog_start(player))
    except Exception as e:
        safe_console(f"Klasör seçme hatası: {e}")
        _folder_warning(player, tr("Klasör Açılamadı"),
                        tr("Klasör seçilemedi. Lütfen tekrar deneyin."))
        return
    if not folder:
        return
    try:
        files = folder_media_files(folder)
    except Exception as e:
        safe_console(f"Klasör tarama hatası: {e}")
        files = None
    if files is None:
        _folder_warning(player, tr("Klasör Açılamadı"),
                        tr("Klasör okunamadı. Klasöre erişim izniniz "
                           "olmayabilir."))
        return
    if not files:
        _folder_warning(player, tr("Klasör Aç"),
                        tr("Bu klasörde desteklenen medya dosyası "
                           "bulunamadı."))
        return
    # Yeni liste ancak tarama başarılıysa uygulanır; ilk dosya SENKRON
    # açılamazsa bu girişimin dokunduğu her alan eski değerine döner.
    # `play_from_playlist()` hatayı kendi içinde bildirdiği için burada
    # İKİNCİ bir mesaj gösterilmez.
    snapshot = _capture_playback_state(player)
    if snapshot["settings_status"] == SETTING_UNREADABLE:
        # Eski değer güvenilir biçimde yakalanamadı: geri alma garanti
        # edilemeyeceği için işlem HİÇ başlatılmaz.
        _folder_warning(player, tr("Klasör Açılamadı"),
                        tr("Oynatıcı ayarları okunamadığı için klasör güvenli "
                           "biçimde açılamadı. Lütfen tekrar deneyin."))
        return
    player.last_dir = folder
    player.playlist = files
    player.current_playlist_index = 0
    if not play_from_playlist(player, 0):
        _restore_playback_state(player, snapshot)


# `open_folder()` denemesinin dokunduğu oynatıcı alanları. Yalnız bu liste
# geri alınır; genel oynatma akışı değiştirilmez.
_PLAYBACK_STATE_FIELDS = (
    "playlist", "current_playlist_index", "current_file", "last_dir",
    "duration", "position", "is_paused", "_core_idle", "_audio_menu_file",
    "_chapter_menu_file", "_pending_subs", "_load_started_at",
    "_title_bar_raise_pending",
)
_MPV_STATE_FIELDS = ("sub_delay", "sub_visibility")
_SUB_DELAY_KEY = "subtitle/sub_delay"
_MISSING = object()

# Ayar anahtarının BİRBİRİNDEN AYRI üç durumu. "Yok" ile "okunamadı" aynı
# sentinel'le temsil edilirse var olan bir ayar yalnızca okunamadığı için
# silinebilir; bu atomik değildir.
SETTING_NO_STORE = "no_store"    # oynatıcının ayar nesnesi yok
SETTING_ABSENT = "absent"        # anahtar gerçekten yok
SETTING_READ = "read"            # eski değer güvenilir biçimde okundu
SETTING_UNREADABLE = "unreadable"  # okuma başarısız; eski değer BİLİNMİYOR


def _capture_sub_delay_setting(settings):
    """`subtitle/sub_delay` için (durum, değer) ikilisi."""
    if settings is None:
        return (SETTING_NO_STORE, None)
    try:
        contains = getattr(settings, "contains", None)
        if callable(contains) and not contains(_SUB_DELAY_KEY):
            return (SETTING_ABSENT, None)
        value = settings.value(_SUB_DELAY_KEY, _MISSING)
    except Exception as e:
        safe_console(f"Altyazı gecikmesi ayarı okunamadı: {e}")
        return (SETTING_UNREADABLE, None)
    if value is _MISSING:
        return (SETTING_ABSENT, None)
    return (SETTING_READ, value)


def _capture_playback_state(player):
    """Klasör denemesi öncesi geri alınabilir state fotoğrafı.

    `settings_status` `SETTING_UNREADABLE` ise geri alma GARANTİ EDİLEMEZ;
    çağıran işlemi hiç başlatmamalıdır.
    """
    state = {"player": {}, "mpv": {}}
    for name in _PLAYBACK_STATE_FIELDS:
        if not hasattr(player, name):
            continue
        value = getattr(player, name)
        state["player"][name] = list(value) if isinstance(value, list) else value
    mpv_player = getattr(player, "mpv_player", None)
    for name in _MPV_STATE_FIELDS:
        try:
            state["mpv"][name] = getattr(mpv_player, name)
        except Exception:
            pass
    status, value = _capture_sub_delay_setting(
        getattr(player, "settings", None))
    state["settings_status"] = status
    state["settings_value"] = value
    return state


def _restore_playback_state(player, state):
    """Başarısız klasör denemesinden ÖNCEKİ değerleri geri yazar."""
    for name, value in state["player"].items():
        setattr(player, name, value)
    mpv_player = getattr(player, "mpv_player", None)
    for name, value in state["mpv"].items():
        try:
            setattr(mpv_player, name, value)
        except Exception:
            pass
    settings = getattr(player, "settings", None)
    status = state["settings_status"]
    if settings is None or status == SETTING_NO_STORE:
        return
    if status == SETTING_READ:
        try:
            settings.setValue(_SUB_DELAY_KEY, state["settings_value"])
        except Exception as e:
            safe_console(f"Altyazı gecikmesi ayarı geri yazılamadı: {e}")
        return
    if status == SETTING_ABSENT:
        # Anahtar denemeden ÖNCE gerçekten yoktu: denemenin yazdığını da
        # bırakma. Okunamayan anahtar bu yola HİÇ düşmez.
        remove = getattr(settings, "remove", None)
        if callable(remove):
            try:
                remove(_SUB_DELAY_KEY)
            except Exception as e:
                safe_console(f"Altyazı gecikmesi ayarı silinemedi: {e}")


def _folder_warning(player, title, message):
    """Kullanıcıya güvenli mesaj: ham hata, traceback veya yol sızmaz."""
    QMessageBox.warning(player, title, message)


def is_network_path(path):
    """Ağ adresi mi? URL girdileri dosya varlığı kontrolüne SOKULMAZ."""
    text = str(path or "")
    scheme, separator, _rest = text.partition("://")
    return bool(separator) and scheme.isalpha() and len(scheme) > 1


def open_recent(player, path):
    """`Son Açılanlar` girdisini açar; eksik yerel dosyayı listeden siler.

    URL girdileri dosya sistemine sorulmaz. Yerel dosya artık yoksa
    oynatma DENENMEZ; mevcut oynatma ve liste korunur.
    """
    if not path:
        return
    if not is_network_path(path) and not os.path.isfile(path):
        remove = getattr(player, "remove_recent_file", None)
        if callable(remove):
            remove(path)
        QMessageBox.warning(
            player, tr("Dosya Bulunamadı"),
            tr("Dosya artık mevcut değil. Son Açılanlar listesinden "
               "kaldırıldı."))
        return
    player.open_path(path)


def open_path(player, path):
    """Belirli bir dosya yolunu doğrudan açar (dosya iletişim kutusu, sürükle-bırak veya komut satırı)."""
    if not path:
        return
    try:
        # Yeni medya yüklenirken eski dosyanın süre/konum bilgisi kullanılmasın.
        player.duration = 0
        player.position = 0
        player._core_idle = False
        player._audio_menu_file = ""
        player._chapter_menu_file = ""
        player._pending_subs = []
        player.current_file = path
        if os.path.isfile(path):
            player.last_dir = os.path.dirname(path)
        player._load_started_at = time.time()
        _clear_title_bar_raise(player)
        _reset_subtitle_timing_for_new_media(player)
        _hide_subtitles_for_new_media(player)
        player.mpv_player.play(path)
        # Başarıyla doğrudan açılan yerel medya da görünür playlist'in tek
        # öğesidir. Böylece ekranda oynayan dosya ile sağ panel aynı modeli taşır.
        player.playlist = [path]
        player.current_playlist_index = 0
        _mark_title_bar_raise(player)
        player.play_button.setIcon(player.pause_icon)
        player.is_paused = False
        if player.video_frame.control_overlay is not None:
            player.video_frame.update_overlay_play_state()
        player.video_frame.placeholder_label.hide()
        player.set_title()
        player.add_recent_file(path)
        _refresh_playlist_panel(player)
        safe_console(f"Playing file: {path}")
    except Exception as e:
        safe_console(f"Open file error: {e}")
        player.current_file = ""
        player.duration = 0
        player.position = 0
        player._load_started_at = 0
        player._pending_subs = []
        player.video_frame.placeholder_label.show()
        player.set_title()
        show_user_error(player, tr("Dosya Açılamadı"),
                        tr("Dosya açılamadı. Dosya silinmiş, taşınmış veya "
                           "desteklenmeyen bir format olabilir."),
                        exc=e)

# Bu sabitler import anında hesaplanır; o an çevirmen henüz YOKTUR. Bu
# yüzden `tr()` DEĞİL `tr_mark()` kullanılır (yalnız işaretler) ve çeviri
# kullanım anında `translate_marked()` ile uygulanır.
# `PLACEHOLDER_DEFAULT_TEXT` ürün ADIDIR; çevrilmez.
PLACEHOLDER_DEFAULT_TEXT = "MLC Player\nMedia Launch Codec Player"
URL_LOADING_TEXT = tr_mark("Bağlantı açılıyor…")
URL_INVALID_TITLE = tr_mark("Geçersiz Adres")
URL_INVALID_MESSAGE = tr_mark("Geçerli bir web adresi girin. Yalnız http:// ve "
                              "https:// ile başlayan bağlantılar açılabilir.")
URL_FAILED_TITLE = tr_mark("Bağlantı Açılamadı")
URL_FAILED_MESSAGE = tr_mark("Bu bağlantı açılamadı. Adresi ve internet "
                             "bağlantınızı kontrol edip tekrar deneyin.")
# MPV gerçekten `idle` dönmeden hata denmez. Bu süre yalnız yüklemenin ilk
# anındaki idle titremesini eler; TEK BAŞINA hata ölçütü DEĞİLDİR.
URL_LOAD_GRACE_SECONDS = 12.0
ALLOWED_URL_SCHEMES = ("http", "https")


def is_remote_media_url(path):
    """`http`/`https` ile baslayan UZAK adres mi?

    Kalici ayara yazma karari ve pencere basligi bu TEK olcute bakar.
    """
    if not isinstance(path, str):
        return False
    try:
        scheme = urlsplit(path.strip()).scheme.lower()
    except ValueError:
        return False
    return scheme in ALLOWED_URL_SCHEMES


def safe_media_host(path):
    """Kullaniciya gosterilebilir `host[:port]`; aksi halde bos.

    `userinfo`, `query`, `fragment`, yol ve video kimligi UretILMEZ.
    """
    if not isinstance(path, str):
        return ""
    try:
        parts = urlsplit(path.strip())
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        return ""
    host = host.strip()
    if not host:
        return ""
    return f"{host}:{port}" if port else host


def normalize_media_url(text):
    """Kabul edilebilir bir adres ise TRIM edilmiş hâlini döndürür.

    Yalnız `http`/`https` ve boş olmayan hostname kabul edilir. Yerel yol,
    `file:`, `javascript:`, `ftp:` ve bozuk adres MPV'ye HİÇ verilmez.
    """
    if not isinstance(text, str):
        return ""
    candidate = text.strip()
    if not candidate:
        return ""
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return ""
    if parts.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return ""
    try:
        host = parts.hostname or ""
    except ValueError:
        return ""
    return candidate if host.strip() else ""


def _placeholder(player):
    frame = getattr(player, "video_frame", None)
    return getattr(frame, "placeholder_label", None)


def _set_placeholder_text(player, text, visible):
    label = _placeholder(player)
    if label is None:
        return
    try:
        if label.text() != text:
            label.setText(text)
        label.setVisible(bool(visible))
    except RuntimeError:
        pass


def begin_url_loading(player):
    """Kullanıcıya `Bağlantı açılıyor…` durumunu gösterir.

    Ham adres bu durumda İKİNCİ KEZ saklanmaz; yalnız bayrak ve
    `time.monotonic()` başlangıcı tutulur.
    """
    player._url_loading_active = True
    player._url_loading_started_at = time.monotonic()
    _set_placeholder_text(player, translate_marked(URL_LOADING_TEXT), True)


def clear_url_loading(player):
    """Tek ve İDEMPOTENT temizlik yolu.

    Başarı, hata, yeni URL, yerel dosya, playlist geçişi, `stop` ve kapanış
    aynı noktadan geçer; `Bağlantı açılıyor…` metni sonraki videoya kalmaz.
    """
    active = bool(player.__dict__.get("_url_loading_active"))
    player._url_loading_active = False
    player._url_loading_started_at = 0.0
    if active:
        _set_placeholder_text(player, PLACEHOLDER_DEFAULT_TEXT, False)
    return active


def url_loading_active(player):
    return bool(player.__dict__.get("_url_loading_active"))


def update_url_loading(player):
    """`update_ui` turundan çağrılır. Yeni timer/thread/polling YOKTUR."""
    if not url_loading_active(player):
        return None
    try:
        duration = float(getattr(player, "duration", 0) or 0)
        position = float(getattr(player, "position", 0) or 0)
    except (TypeError, ValueError):
        duration = position = 0.0
    # Canlı yayında `duration` 0 kalabilir; time-pos ilerlemesi de başarıdır.
    if duration > 0 or position > 0:
        clear_url_loading(player)
        return True
    started = float(player.__dict__.get("_url_loading_started_at") or 0.0)
    elapsed = time.monotonic() - started if started else 0.0
    # SÜRE TEK BAŞINA HATA DEĞİLDİR: MPV hâlâ açmaya çalışıyorsa beklenir.
    if not getattr(player, "_core_idle", False):
        return None
    if elapsed <= URL_LOAD_GRACE_SECONDS:
        return None
    clear_url_loading(player)
    # Runtime eksikse ONARIM mesaji, tamsa genel baglanti mesaji. Ham yol,
    # URL, token, istisna veya traceback KULLANICIYA CIKMAZ.
    if getattr(player, "internet_video_ready", True):
        show_user_error(player, translate_marked(URL_FAILED_TITLE),
                        translate_marked(URL_FAILED_MESSAGE))
    else:
        show_user_error(player, INTERNET_VIDEO_MISSING_TITLE,
                        INTERNET_VIDEO_MISSING_MESSAGE)
    return False


def open_url(player):
    raw, ok = QInputDialog.getText(player, tr("URL'den Oynat"),
                                   tr("Video URL'si giriniz:"),
                                   QLineEdit.EchoMode.Normal, "https://")
    if ok and raw:
        url = normalize_media_url(raw)
        if not url:
            # GEÇERSİZ: mevcut oynatma, `current_file`, playlist ve son
            # açılanlar HİÇ değişmez; MPV'ye hiçbir şey verilmez.
            show_user_error(player, translate_marked(URL_INVALID_TITLE),
                            translate_marked(URL_INVALID_MESSAGE))
            return
        try:
            clear_url_loading(player)
            player.duration = 0
            player.position = 0
            player._core_idle = False
            player._audio_menu_file = ""
            player._chapter_menu_file = ""
            player._pending_subs = []
            player.playlist = []
            player.current_playlist_index = -1
            player.current_file = url
            # URL yaşam döngüsü yerel dosyanınkinden AYRIDIR: yerel
            # 3 saniyelik hata yolu URL yüklenirken çalışmaz.
            player._load_started_at = 0
            begin_url_loading(player)
            _clear_title_bar_raise(player)
            _reset_subtitle_timing_for_new_media(player)
            _hide_subtitles_for_new_media(player)
            player.mpv_player.play(url)
            _mark_title_bar_raise(player)
            player.play_button.setIcon(player.pause_icon)
            player.is_paused = False
            if player.video_frame.control_overlay is not None:
                player.video_frame.update_overlay_play_state()
            player.set_title()
            # YALNIZ komut kabul edildikten SONRA listeye girer; hata
            # yolunda `add_recent_file` hic cagrilmaz.
            player.add_recent_file(url)
            # HAM URL LOGA YAZILMAZ: yalnız `scheme://host` + son yol
            # parçası. `userinfo`, `query` ve `fragment` hiç üretilmez.
            safe_console(f"Bağlantı açılıyor: {sanitize_media_url(url)}")
        except Exception as e:
            clear_url_loading(player)
            safe_console(f"Bağlantı açma hatası: {type(e).__name__}")
            show_user_error(player, translate_marked(URL_FAILED_TITLE),
                            translate_marked(URL_FAILED_MESSAGE), exc=e)

def open_subtitle(player):
    if not player.current_file:
        QMessageBox.warning(player, tr("Uyarı"),
                            tr("Önce bir video dosyası açın."))
        return

    subtitle_path, _ = QFileDialog.getOpenFileName(
        player, tr("Altyazı Ekle"), "",
        f"{tr('Altyazı Dosyaları')} ({SUBTITLE_EXTENSIONS})"
    )
    if not subtitle_path:
        return

    # Dosya mevcut değilse mpv -12 (command) hatası verir
    if not os.path.isfile(subtitle_path):
        show_user_error(player, tr("Altyazı Bulunamadı"),
                        tr("Altyazı dosyası bulunamadı. Dosyanın yerini "
                           "kontrol edin."),
                        details=f"{tr('Altyazı yolu:')} {subtitle_path}")
        return

    # Video henüz yüklenmediyse (duration=0) mpv sub_add'i reddeder (-12).
    # Altyazıyı bekleme listesine al; video yüklenince otomatik eklenecek.
    if player.duration <= 0:
        player._pending_subs.append(subtitle_path)
        safe_console(f"Altyazı yükleme sırasına alındı: {subtitle_path}")
        player.video_frame.show_osd(tr("Altyazı yükleniyor..."))
        return

    try:
        player.mpv_player.sub_add(subtitle_path)
        _refresh_overlay_subtitle_state(player)
        safe_console(f"Subtitle added: {subtitle_path}")
        player.video_frame.show_osd(tr("Altyazı eklendi"))
    except Exception as e:
        safe_console(f"Open subtitle error: {e}")
        show_user_error(player, tr("Altyazı Eklenemedi"),
                        tr("Altyazı eklenemedi. Dosyanın hasarlı veya "
                           "desteklenmeyen bir format olması mümkün."),
                        exc=e)

def select_subtitle_language(player, sid):
    try:
        player.mpv_player.sid = sid
        _refresh_overlay_subtitle_state(player)
        safe_console(f"Selected subtitle ID: {sid}")
    except Exception as e:
        safe_console(f"Altyazı seçimi hatası: {e}")
        show_user_error(player, tr("Altyazı Seçilemedi"),
                        tr("Altyazı seçilemedi. Lütfen başka bir altyazı "
                           "parçasını deneyin."),
                        exc=e)

def toggle_subtitles(player):
    try:
        try:
            tracks = list(player.mpv_player.track_list or [])
        except Exception:
            tracks = []
        subtitle_tracks = [track for track in tracks
                           if isinstance(track, dict)
                           and track.get("type") == "sub"]
        if not subtitle_tracks:
            player.video_frame.show_osd(tr("Altyazı bulunamadı"), duration=1800)
            _refresh_overlay_subtitle_state(player)
            return False

        current_visibility = player.mpv_player.sub_visibility
        if not current_visibility:
            sid = getattr(player.mpv_player, "sid", None)
            disabled = sid is None or sid is False or str(sid).strip().lower() in {
                "", "0", "no", "none", "false"
            }
            if disabled:
                selected = next((track for track in subtitle_tracks
                                 if track.get("selected")), subtitle_tracks[0])
                if selected.get("id") is not None:
                    player.mpv_player.sid = selected["id"]
        player.mpv_player.sub_visibility = not current_visibility
        _refresh_overlay_subtitle_state(player)
        safe_console(f"Subtitles visibility set to: {not current_visibility}")
        return True
    except Exception as e:
        safe_console(f"Altyazıları gösterme/gizleme hatası: {e}")
        show_user_error(player, tr("Altyazı Değiştirilemedi"),
                        tr("Altyazılar açılıp kapatılamadı. Lütfen tekrar "
                           "deneyin."),
                        exc=e)

def seek_position(player, position):
    # Konum slider'ının programatik güncellemesinden gelen sinyalleri yoksay
    if getattr(player, '_updating_position_slider', False):
        return
    if player.duration > 0:
        try:
            seek_time = (position * player.duration) / 1000.0
            player.mpv_player.time_pos = float(seek_time)
        except Exception as e:
            safe_console(f"Seeking error: {e}")

def seek_relative(player, seconds):
    try:
        if player.is_paused and not player.current_file:
            return
        player.mpv_player.check_core_alive()
        if player.mpv_player.time_pos is not None:
            player.mpv_player.seek(float(seconds), reference="relative")
            direction = tr("İleri") if seconds > 0 else tr("Geri")
            target = max(0, min(player.duration, (player.position or 0) + seconds))
            player.video_frame.show_osd(
                f"{direction}: {abs(seconds):g} {tr('saniye')}"
                f"\n{format_time(target)}")
    except mpv.ShutdownError:
        safe_console("MPV çekirdeği kapatılmış. Göreceli arama yapılamıyor.")
    except Exception as e:
        safe_console(f"Relative seek error: {e}")


def seek_chapter(player, delta):
    """Bir sonraki/önceki medya bölümüne geçer."""
    try:
        chapters = player.mpv_player.chapter_list or []
        current = int(player.mpv_player.chapter)
        if not chapters or current < 0:
            player.video_frame.show_osd(tr("Bölüm bilgisi yok"))
            return
        target = max(0, min(len(chapters) - 1, current + delta))
        player.mpv_player.chapter = target
        title = (chapters[target].get("title")
                 or f"{tr('Bölüm')} {target + 1}")
        player.video_frame.show_osd(title)
    except Exception as e:
        safe_console(f"Bölüm değiştirme hatası: {e}")

def play_pause(player):
    # Eğer video yüklenmemişse, dosya gezgini aç
    if not player.current_file:
        open_file(player)
        return

    if not player.is_paused:
        player.mpv_player.pause = True
        player.play_button.setIcon(player.play_icon)
        player.is_paused = True
    else:
        player.mpv_player.pause = False
        player.play_button.setIcon(player.pause_icon)
        player.is_paused = False
    if player.video_frame.control_overlay is not None:
        player.video_frame.update_overlay_play_state()

def stop(player):
    try:
        player.mpv_player.stop()
    except Exception as e:
        safe_console(f"MPV durdurma hatası: {e}")
    player.play_button.setIcon(player.play_icon)
    player.is_paused = True
    player.duration = 0
    player.position = 0
    player._load_started_at = 0
    player._core_idle = False
    player._audio_menu_file = ""
    player._chapter_menu_file = ""
    player._pending_subs = []
    player.current_file = ""
    clear_url_loading(player)
    if player.video_frame.control_overlay is not None:
        player.video_frame.update_overlay_play_state()
    player.set_title()
    # duration'ı önce sıfırla ki slider sıfırlanması gereksiz seek tetiklemesin
    player._updating_position_slider = True
    player.position_slider.setValue(0)
    player._updating_position_slider = False
    if hasattr(player, 'current_time_label'):
        player.current_time_label.setText("00:00")
    if hasattr(player, 'total_time_label'):
        player.total_time_label.setText("00:00")
    player.video_frame.placeholder_label.show()

def set_volume(player, volume):
    try:
        # Üst/alt sınır: mpv volume 1000'e kadar izin verir; burada MAX_VOLUME ile sınırla
        volume = min(MAX_VOLUME, max(0, float(volume)))

        # 100 üstü amplifikasyon için mpv'nin üst sınırını yükselt (varsayılan 130)
        if volume > 100:
            player.mpv_player.volume_max = MAX_VOLUME

        player.mpv_player.volume = volume
        player.volume_label.setText(f"%{int(volume)}")
        if volume == 0:
            player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
            player.is_muted = True
            osd_text = "Sessiz"
        else:
            player.volume_icon.setIcon(player.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
            player.is_muted = False
            player.last_volume = volume
            osd_text = f"Ses: %{int(volume)}"
        if getattr(player, '_ui_ready', False):
            player.video_frame.show_osd(osd_text)
    except Exception as e:
        safe_console(f"Set volume error: {e}")


def change_volume(player, delta):
    """Ses seviyesini mevcut değere göre değiştirir."""
    try:
        current = min(MAX_VOLUME, max(0, float(player.mpv_player.volume)))
        player.volume_slider.setValue(int(current + delta))
    except Exception as e:
        safe_console(f"Ses değiştirme hatası: {e}")

def add_to_playlist(player):
    files, _ = QFileDialog.getOpenFileNames(
        player, tr("Oynatma Listesine Dosya Ekle"), "",
        f"{tr('Medya Dosyaları')} ({MEDIA_EXTENSIONS})"
    )
    if files:
        for file in files:
            player.playlist.append(file)
            safe_console(f"Oynatma listesine eklendi: {file}")

        # Eğer şu an bir dosya oynatılmıyorsa, ilk dosyayı oynat
        if not player.current_file and player.playlist:
            player.current_playlist_index = 0
            play_from_playlist(player, player.current_playlist_index)

        _refresh_playlist_panel(player)


def _refresh_playlist_panel(player):
    frame = getattr(player, "video_frame", None)
    refresh = getattr(frame, "refresh_playlist_panel", None)
    if callable(refresh):
        refresh()

def show_playlist(player):
    if getattr(player, "cinematic_ui_enabled", False):
        frame = getattr(player, "video_frame", None)
        toggle = getattr(frame, "toggle_playlist_panel", None)
        if callable(toggle):
            toggle()
            return

    # Klasik teşhis modu eski modal pencereyi korur.
    if not player.playlist:
        QMessageBox.information(player, tr("Oynatma Listesi"),
                                tr("Oynatma listesi boş."))
        return

    playlist_dialog = QDialog(player)
    playlist_dialog.setWindowTitle(tr("Oynatma Listesi"))
    playlist_dialog.setMinimumSize(400, 300)

    layout = QVBoxLayout(playlist_dialog)

    list_widget = QListWidget()
    sync_playlist_view(player, list_widget)

    layout.addWidget(list_widget)

    button_layout = QHBoxLayout()

    play_button = QPushButton(tr("Oynat"))
    play_button.clicked.connect(lambda: play_from_playlist(player, list_widget.currentRow()))

    remove_button = QPushButton(tr("Kaldır"))
    def remove_selected():
        remove_from_playlist(player, list_widget.currentRow())
        sync_playlist_view(player, list_widget)

    remove_button.clicked.connect(remove_selected)

    clear_button = QPushButton(tr("Listeyi Temizle"))
    def clear_list():
        clear_playlist(player)
        sync_playlist_view(player, list_widget)

    clear_button.clicked.connect(clear_list)

    button_layout.addWidget(play_button)
    button_layout.addWidget(remove_button)
    button_layout.addWidget(clear_button)

    layout.addLayout(button_layout)
    playlist_dialog.exec()


def sync_playlist_view(player, list_widget):
    """Playlist görünümünü tek kaynak olan player.playlist ile eşitler."""
    list_widget.clear()
    for index, file_path in enumerate(player.playlist):
        item = QListWidgetItem(os.path.basename(file_path))
        item.setToolTip(file_path)
        if index == player.current_playlist_index:
            item.setBackground(QColor(46, 155, 216, 60))
        list_widget.addItem(item)

def play_from_playlist(player, index):
    """Listedeki `index` girdisini oynatır.

    Dönüş değeri çağıranın GERİ ALMA kararı içindir: geçersiz index veya
    senkron oynatma hatasında `False`, başarıda `True`. Mevcut çağıranlar
    dönüşü yok sayar; davranışları değişmez.
    """
    if 0 <= index < len(player.playlist):
        try:
            player.current_playlist_index = index
            file_path = player.playlist[index]
            player.duration = 0
            player.position = 0
            player._core_idle = False
            player._audio_menu_file = ""
            player._chapter_menu_file = ""
            player._pending_subs = []
            clear_url_loading(player)
            player.current_file = file_path
            player._load_started_at = time.time()
            _clear_title_bar_raise(player)
            _reset_subtitle_timing_for_new_media(player)
            _hide_subtitles_for_new_media(player)
            player.mpv_player.play(file_path)
            _mark_title_bar_raise(player)
            player.play_button.setIcon(player.pause_icon)
            player.is_paused = False
            if player.video_frame.control_overlay is not None:
                player.video_frame.update_overlay_play_state()
            player.video_frame.placeholder_label.hide()
            player.set_title()
            player.add_recent_file(file_path)
            _refresh_playlist_panel(player)
            safe_console(f"Oynatılıyor: {file_path}")
            return True
        except Exception as e:
            safe_console(f"Oynatma listesinden oynatma hatası: {e}")
            show_user_error(player, tr("Dosya Açılamadı"),
                            tr("Oynatma listesindeki dosya açılamadı. Dosya "
                               "taşınmış veya silinmiş olabilir."),
                            exc=e)
            return False
    return False

def remove_from_playlist(player, index):
    if 0 <= index < len(player.playlist):
        player.playlist.pop(index)
        if index == player.current_playlist_index:
            # Eğer oynatılan dosya kaldırıldıysa
            if player.playlist:
                # Listede başka dosyalar varsa, sıradakini oynat
                new_index = min(index, len(player.playlist) - 1)
                play_from_playlist(player, new_index)
            else:
                # Liste boşaldıysa oynatmayı durdur
                stop(player)
                player.current_playlist_index = -1
        elif index < player.current_playlist_index:
            # Eğer oynatılan dosyadan önceki bir dosya kaldırıldıysa, indeksi güncelle
            player.current_playlist_index -= 1
        _refresh_playlist_panel(player)

def clear_playlist(player):
    if player.current_file:
        stop(player)
    player.playlist = []
    player.current_playlist_index = -1
    _refresh_playlist_panel(player)

def save_playlist(player):
    if not player.playlist:
        QMessageBox.information(player, tr("Oynatma Listesi"),
                                tr("Kaydedilecek oynatma listesi yok."))
        return
    file_path, _ = QFileDialog.getSaveFileName(
        player, tr("Oynatma Listesini Kaydet"), "",
        f"{tr('Oynatma Listesi')} (*.m3u)"
    )
    if not file_path:
        return
    if not file_path.lower().endswith(".m3u"):
        file_path += ".m3u"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in player.playlist:
                f.write(f"#EXTINF:0,{os.path.basename(item)}\n")
                f.write(f"{item}\n")
        safe_console(f"Oynatma listesi kaydedildi: {file_path}")
    except Exception as e:
        safe_console(f"Oynatma listesi kaydetme hatası: {e}")
        show_user_error(player, tr("Kaydedilemedi"),
                        tr("Oynatma listesi kaydedilemedi. Dosyanın "
                           "yazılabileceği bir konum seçmeyi deneyin."),
                        exc=e)

def load_playlist(player):
    file_path, _ = QFileDialog.getOpenFileName(
        player, tr("Oynatma Listesi Aç"), "",
        f"{tr('Oynatma Listesi')} (*.m3u)"
    )
    if not file_path:
        return
    try:
        entries = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # M3U listeleri mutlak veya liste dosyasına göreli yol içerebilir.
                    entry = line if os.path.isabs(line) else os.path.join(
                        os.path.dirname(file_path), line)
                    if os.path.isfile(entry):
                        entries.append(os.path.normpath(entry))
        if not entries:
            QMessageBox.warning(
                player, tr("Uyarı"),
                tr("Oynatma listesinde geçerli dosya bulunamadı."))
            return
        if player.current_file:
            stop(player)
        player.playlist = entries
        player.current_playlist_index = -1
        play_from_playlist(player, 0)
        _refresh_playlist_panel(player)
        safe_console(f"Oynatma listesi yüklendi ({len(entries)} dosya): {file_path}")
    except Exception as e:
        safe_console(f"Oynatma listesi açma hatası: {e}")
        show_user_error(player, tr("Açılamadı"),
                        tr("Oynatma listesi açılamadı. Dosya bozuk veya "
                           "okunamıyor olabilir."),
                        exc=e)

def take_screenshot(player):
    if not player.current_file:
        QMessageBox.warning(
            player, tr("Uyarı"),
            tr("Ekran görüntüsü almak için bir video oynatılıyor "
               "olmalıdır."))
        return

    # Varsayılan kayıt klasörü: Masaüstü
    screenshots_folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    if not screenshots_folder:
        screenshots_folder = os.path.expanduser("~")

    # Milisaniye ve çakışma eki kullan: aynı saniyedeki görüntüler ezilmesin.
    timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss_zzz")
    screenshot_path = os.path.join(screenshots_folder, f"screenshot_{timestamp}.png")
    suffix = 2
    while os.path.exists(screenshot_path):
        screenshot_path = os.path.join(
            screenshots_folder, f"screenshot_{timestamp}_{suffix}.png")
        suffix += 1

    try:
        # Ekran görüntüsü al
        player.mpv_player.screenshot_to_file(screenshot_path)
        QMessageBox.information(
            player, tr("Başarılı"),
            f"{tr('Ekran görüntüsü kaydedildi:')}\n{screenshot_path}")
    except Exception as e:
        safe_console(f"Ekran görüntüsü alma hatası: {e}")
        show_user_error(player, tr("Ekran Görüntüsü Alınamadı"),
                        tr("Ekran görüntüsü kaydedilemedi. Masaüstüne yazma "
                           "iznini ve boş alanı kontrol edin."),
                        exc=e)

def play_next(player):
    if player.playlist:
        if player.current_playlist_index < len(player.playlist) - 1:
            player.current_playlist_index += 1
            play_from_playlist(player, player.current_playlist_index)
        elif player.loop_playlist:
            # SARMA: son parçadan ilk parçaya. İndeks de güncellenir; aksi
            # halde menü ve sonraki adım bayat indeksle çalışırdı.
            player.current_playlist_index = 0
            play_from_playlist(player, 0)
        else:
            QMessageBox.information(player, tr("Oynatma Listesi"),
                                    tr("Listenin sonuna ulaştınız."))
    else:
        QMessageBox.information(player, tr("Oynatma Listesi"),
                                tr("Oynatma listesi boş."))

def play_previous(player):
    if player.playlist and player.current_playlist_index > 0:
        player.current_playlist_index -= 1
        play_from_playlist(player, player.current_playlist_index)
    elif (player.playlist and player.loop_playlist
            and player.current_playlist_index == 0):
        # SARMA: YALNIZCA ilk parçadan son parçaya. `play_next` zaten
        # sarıyordu; `play_previous` sarmıyordu ve menü durumu ürün
        # davranışıyla çelişiyordu.
        #
        # `index == 0` koşulu şarttır: liste henüz başlamamışsa (-1)
        # "önceki" son parçayı AÇMAMALIDIR.
        player.current_playlist_index = len(player.playlist) - 1
        play_from_playlist(player, player.current_playlist_index)
    else:
        QMessageBox.information(player, tr("Oynatma Listesi"),
                                tr("Listenin başındasınız."))

def toggle_fullscreen(player):
    video_frame = player.video_frame
    if not video_frame.is_video_fullscreen:
        video_frame.enter_fullscreen()
    else:
        video_frame.exit_fullscreen()

def goto_time(player):
    if not player.current_file:
        QMessageBox.warning(player, tr("Uyarı"),
                            tr("Önce bir video dosyası açın."))
        return

    current_time = format_time(player.position)
    time_str, ok = QInputDialog.getText(
        player, tr("Zamana Git"),
        tr("Zaman pozisyonunu girin (MM:SS veya HH:MM:SS formatında):"),
        QLineEdit.EchoMode.Normal,
        current_time
    )

    if ok and time_str:
        try:
            # MM:SS / HH:MM:SS formatını saniyeye çevir
            total_seconds = time_to_seconds(time_str)

            # Geçerli süre kontrolü
            if total_seconds is not None and 0 <= total_seconds <= player.duration:
                player.mpv_player.time_pos = float(total_seconds)
            else:
                QMessageBox.warning(
                    player, tr("Geçersiz Zaman"),
                    tr("Zamanı MM:SS veya HH:MM:SS biçiminde ve 0 ile "
                       "%1 saniye arasında girin.").replace(
                        "%1", str(int(player.duration))))
        except Exception as e:
            show_user_error(player, tr("Zamana Gidilemedi"),
                            tr("Girilen zaman konumuna gidilemedi. Zamanı "
                               "tekrar kontrol edin."),
                            exc=e)

def set_playback_speed(player, speed):
    try:
        if player.mpv_player:
            player.mpv_player.speed = float(speed)
            # Hız etiketini güncelle
            if hasattr(player, 'speed_label'):
                player.speed_label.setText(f"{speed}x")
            # Menü öğelerini güncelle
            for s, action in player.speed_actions.items():
                action.setChecked(s == speed)
    except Exception as e:
        safe_console(f"Oynatma hızı değiştirme hatası: {e}")
        show_user_error(player, tr("Oynatma Hızı Değiştirilemedi"),
                        tr("Oynatma hızı değiştirilemedi. Lütfen başka bir "
                           "hız deneyin."),
                        exc=e)
