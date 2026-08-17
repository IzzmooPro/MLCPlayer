"""Tek kopya koruması: ikinci başlatma yeni pencere AÇMAZ.

NEDEN: iki kopya aynı `QSettings` deposunu paylaşır ve her biri KAPANIRKEN
kendi hâlini yazar. Sonuç: ikinci pencerede yapılan ses/pencere/son açılanlar
değişikliği, önce açılan kopya kapanınca sessizce geri gidebiliyordu.

DAVRANIŞ: ilk kopya bir yerel sunucu açar (`QLocalServer`). Sonraki her
başlatma bu sunucuya bağlanır, varsa dosya yolunu gönderir ve KENDİ SÜRECİNİ
sonlandırır; açık pencere öne gelir ve dosyayı o yükler.

SINIRLAR VE KASITLI KARARLAR:
- Küçük resim işçileri (`--thumbnail-worker`) AYNI exe'dir; onlar bu
  korumanın DIŞINDADIR, yoksa küçük resim üretimi tamamen durur.
- Yeni timer YOKTUR; bekleme, kısa ve sınırlı `waitFor...` çağrılarıyla
  yapılır (ürün değişmezi).
- Süreç çökerse Windows'ta yerel sunucu adı geride kalabilir; bağlanma
  başarısızsa ad BİR KEZ geri alınır (`removeServer`), aksi hâlde program
  bir daha hiç açılamazdı.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from app.errors import log

#: Sunucu adı kullanıcıya özeldir: aynı makinede farklı oturumlar
#: birbirinin kopyasını kapatmamalıdır.
SERVER_NAME = "MLCPlayer-SingleInstance"

#: Bağlanma/okuma için üst sınırlar (ms). Kısa tutulur: ikinci başlatma
#: kullanıcıyı bekletmemelidir.
CONNECT_TIMEOUT_MS = 300
TRANSFER_TIMEOUT_MS = 1000

#: Bu argümanla açılan süreç bir işçidir, ikinci kopya DEĞİLDİR.
WORKER_FLAG = "--thumbnail-worker"

#: Dosyasız ikinci başlatma da pencereyi öne getirmelidir. Bunu BOŞ yükle
#: anlatmak yetmez: canlılık yoklaması da veri göndermeden bağlanır ve
#: ayırt edilemezdi (ÖLÇÜLDÜ: birincil taraf iki hayalet istek aldı).
#: Bu yüzden istek her zaman AÇIK bir belirteç taşır; veri göndermeden
#: kapanan bağlantı YOK SAYILIR.
ACTIVATE_TOKEN = "\x01activate"

#: Birincil tarafın "isteği aldım" yanıtı.
ACK = b"\x06"


def is_worker_invocation(argv):
    """Küçük resim işçisi mi? Öyleyse tek kopya koruması UYGULANMAZ."""
    return len(argv) >= 2 and argv[1] == WORKER_FLAG


class SingleInstanceGuard(QObject):
    """İlk kopya sunucu olur; sonrakiler mesajı gönderip çıkar."""

    #: Başka bir başlatmadan gelen istek. Yük boş olabilir (dosyasız açılış).
    activation_requested = pyqtSignal(str)

    def __init__(self, name=SERVER_NAME, parent=None):
        super().__init__(parent)
        self._name = name
        self._server = None

    # -- birincil taraf --------------------------------------------------

    def acquire(self, payload=""):
        """`True`: bu süreç birincil kopyadır. `False`: istek devredildi.

        Yoklama ile mesaj AYNI bağlantıda taşınır. İki ayrı bağlantı
        denendi ve ÖLÇÜLDÜ ki çalışmıyor: yoklama bağlantısı birincil
        tarafta hayalet istek üretiyor, istemci hemen kapandığı için de
        ikinci bağlantının verisi okunamıyordu.
        """
        # ÖLÇÜLDÜ: Windows'ta `listen()` DIŞLAMA SAĞLAMAZ — adlandırılmış
        # boru aynı adla birden çok sunucu örneğine izin verir ve ikinci
        # `listen()` de başarılı olur. Bu yüzden karar, çalışan bir kopyaya
        # BAĞLANABİLİYOR MUYUZ sorusuyla verilir.
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if socket.waitForConnected(CONNECT_TIMEOUT_MS):
            try:
                self._hand_over(socket, payload)
            finally:
                socket.abort()
            return False

        # Çökme sonrası artakalan ad geri alınır; yoksa program bir daha
        # birincil olamazdı.
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        if self._server.listen(self._name):
            self._server.newConnection.connect(self._on_new_connection)
            return True

        log(f"Could not open the single-instance server: {self._server.errorString()}",
            "WARNING")
        self._server = None
        # Fail-open: koruma kurulamazsa program yine de AÇILIR.
        return True

    def _on_new_connection(self):
        connection = self._server.nextPendingConnection()
        if connection is None:
            return
        try:
            payload = bytes(connection.readAll()).decode("utf-8", "replace")
            if not payload and connection.waitForReadyRead(TRANSFER_TIMEOUT_MS):
                payload = bytes(connection.readAll()).decode("utf-8", "replace")
            payload = payload.strip()
            if not payload:
                return
            # Onay: gönderen taraf bunu görmeden kendi sürecini kapatmaz,
            # aksi hâlde istek yolda kaybolabiliyordu.
            connection.write(ACK)
            connection.flush()
            connection.waitForBytesWritten(TRANSFER_TIMEOUT_MS)
            self.activation_requested.emit(
                "" if payload == ACTIVATE_TOKEN else payload)
        finally:
            connection.disconnectFromServer()

    def release(self):
        """Sunucuyu kapatır. Kapanış kooperatiftir; zorla sonlandırma yok."""
        if self._server is None:
            return
        self._server.close()
        QLocalServer.removeServer(self._name)
        self._server = None

    # -- ikincil taraf ---------------------------------------------------

    def _hand_over(self, socket, payload):
        """İsteği çalışan kopyaya iletir ve ONAYINI bekler.

        Onay beklenmezse süreç kapanırken veri yolda kalabiliyordu
        (ÖLÇÜLDÜ: birincil taraf bağlantıyı görüyor ama yükü okuyamıyordu).
        """
        data = (payload or ACTIVATE_TOKEN).encode("utf-8")
        if socket.write(data) != len(data):
            return False
        socket.flush()
        socket.waitForBytesWritten(TRANSFER_TIMEOUT_MS)
        if not socket.waitForReadyRead(TRANSFER_TIMEOUT_MS):
            log("Single instance: the running copy did not acknowledge the request.", "WARNING")
            return False
        return bytes(socket.readAll()) == ACK


def activate_window(window, payload=""):
    """Açık pencereyi öne getirir ve istenen dosyayı yükler.

    Yeni bir always-on-top bayrağı KULLANILMAZ (ürün değişmezi); yalnız
    standart geri getirme çağrıları yapılır.
    """
    if window.isMinimized():
        window.showNormal()
    window.raise_()
    window.activateWindow()
    if payload:
        window.open_path(payload)
