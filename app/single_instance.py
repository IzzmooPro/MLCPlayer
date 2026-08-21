# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tek kopya koruması: ikinci başlatma yeni pencere AÇMAZ.

İlk kopya atomik bir süreç mutex'i alır ve kullanıcı/oturum kapsamlı bir
`QLocalServer` açar. Sonraki başlatma varsa hedefi sürümlü bir mesajla açık
pencereye devreder. Küçük resim işçileri bu korumanın dışındadır.

Birincil GUI iş parçacığında bloklayan ağ beklemesi veya yeni timer yoktur.
İkinci süreç yalnız kısa ve sınırlı bağlantı/onay beklemeleri yapar.
"""

import ctypes
import getpass
import hashlib
import os
import struct
import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from app.errors import log


SERVER_NAME = "MLCPlayer-SingleInstance"
# Inno ana kaldırıcısı bu sabit, oturum kapsamlı mutex'i denetler. Handle
# bilerek süreç bitene kadar kapatılmaz: pencere kapanışı ile Windows'un EXE/DLL
# image kilitlerini tamamen bırakması arasındaki kısa aralık korunmalıdır.
INSTALLER_APP_MUTEX = "MLCPlayer-Running"
_INSTALLER_APP_MUTEX_HANDLE = None
CONNECT_TIMEOUT_MS = 300
TRANSFER_TIMEOUT_MS = 1000
HANDOFF_ATTEMPTS = 3
HANDOFF_RETRY_SECONDS = 0.05
WORKER_FLAG = "--thumbnail-worker"
ACTIVATE_TOKEN = "\x01activate"
ACK = b"\x06"

# Sabit imza + sürüm + unsigned 32-bit yük uzunluğu.
FRAME_MAGIC = b"MLCP"
PROTOCOL_VERSION = 1
FRAME_HEADER = struct.Struct(">4sBI")
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_PENDING_CONNECTIONS = 8


def _ensure_installer_lifecycle_mutex():
    """Kaldırıcının açık/henüz kapanan ürünü fail-closed görmesini sağla."""
    global _INSTALLER_APP_MUTEX_HANDLE
    if os.name != "nt" or _INSTALLER_APP_MUTEX_HANDLE is not None:
        return

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool,
                                      ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, INSTALLER_APP_MUTEX)
    if not handle:
        log("Installer lifecycle mutex could not be created.", "WARNING")
        return
    # CloseHandle YOK: resmî AppMutex sözleşmesi mutex'in gerçek süreç
    # sonlanmasına kadar yaşamasını ister. Windows süreç çıkışında kapatır.
    _INSTALLER_APP_MUTEX_HANDLE = handle


def is_worker_invocation(argv):
    """Küçük resim işçisi mi? Öyleyse tek kopya koruması uygulanmaz."""
    return len(argv) >= 2 and argv[1] == WORKER_FLAG


def _session_id():
    """Windows oturum kimliği; bulunamazsa süreç üstü kararlı yedek."""
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        kernel32.ProcessIdToSessionId.argtypes = [
            ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.ProcessIdToSessionId.restype = ctypes.c_bool
        value = ctypes.c_ulong()
        if kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(value)):
            return str(value.value)
    return os.environ.get("SESSIONNAME", "default")


def _scoped_name(name):
    """Sunucu adını kullanıcı ve oturum sınırına taşır."""
    identity = f"{getpass.getuser()}\0{_session_id()}".encode(
        "utf-8", "surrogatepass")
    suffix = hashlib.sha256(identity).hexdigest()[:16]
    return f"{name}-{suffix}"


def _encode_frame(payload):
    data = (payload or ACTIVATE_TOKEN).encode("utf-8")
    if len(data) > MAX_PAYLOAD_BYTES:
        raise ValueError("single-instance payload is too large")
    return FRAME_HEADER.pack(FRAME_MAGIC, PROTOCOL_VERSION, len(data)) + data


class _ProcessMutex:
    """Windows adlandırılmış mutex'i ile atomik birincil süreç seçimi."""

    ERROR_ALREADY_EXISTS = 183

    def __init__(self, name):
        safe_name = hashlib.sha256(name.encode("utf-8")).hexdigest()
        self._name = f"Local\\MLCPlayer-{safe_name}"
        self._handle = None
        self._fallback_owned = False

    def acquire(self):
        if self._handle is not None or self._fallback_owned:
            return True
        if os.name != "nt":
            # Ürün Windows içindir. Bu yedek yalnız geliştirme ortamında
            # aynı süreçte iki sahip oluşmasını engeller.
            owners = getattr(_ProcessMutex, "_fallback_owners", set())
            _ProcessMutex._fallback_owners = owners
            if self._name in owners:
                return False
            owners.add(self._name)
            self._fallback_owned = True
            return True

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool,
                                          ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.GetLastError.restype = ctypes.c_ulong
        kernel32.SetLastError(0)
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            # Koruma kurulamadı diye oynatıcıyı tamamen kullanılamaz yapma.
            log("Single instance: process mutex could not be created.",
                "WARNING")
            return True
        if kernel32.GetLastError() == self.ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self):
        if self._handle is not None:
            kernel32 = ctypes.windll.kernel32
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_bool
            kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._fallback_owned:
            _ProcessMutex._fallback_owners.discard(self._name)
            self._fallback_owned = False


class SingleInstanceGuard(QObject):
    """İlk kopya sunucu olur; sonrakiler mesajı gönderip çıkar."""

    activation_requested = pyqtSignal(str)

    def __init__(self, name=SERVER_NAME, parent=None):
        super().__init__(parent)
        self._name = _scoped_name(name)
        self._server = None
        self._mutex = _ProcessMutex(self._name)
        self._connections = {}
        self.handoff_failed = False

    def acquire(self, payload=""):
        """`True`: birincil. `False`: ikincil veya teslimat başarısız."""
        self.handoff_failed = False
        _ensure_installer_lifecycle_mutex()
        # Windows'ta QLocalServer.listen aynı ad için iki kez başarılı
        # olabilir; birincil seçim bu yüzden önce mutex ile yapılır.
        if not self._mutex.acquire():
            for attempt in range(HANDOFF_ATTEMPTS):
                socket = QLocalSocket()
                socket.connectToServer(self._name)
                connected = socket.waitForConnected(CONNECT_TIMEOUT_MS)
                accepted = False
                if connected:
                    try:
                        accepted = self._hand_over(socket, payload)
                    finally:
                        socket.abort()
                if accepted:
                    return False
                if attempt + 1 < HANDOFF_ATTEMPTS:
                    time.sleep(HANDOFF_RETRY_SECONDS)
            self.handoff_failed = True
            log("Single instance: request could not be delivered to the "
                "running copy.", "WARNING")
            return False

        # Mutex yalnız bu kullanıcı/oturumdaki tek sürece ait olduğundan
        # artakalan sunucu adını burada geri almak güvenlidir.
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(
            QLocalServer.SocketOption.UserAccessOption)
        if self._server.listen(self._name):
            self._server.newConnection.connect(self._on_new_connection)
            return True

        log(f"Could not open the single-instance server: "
            f"{self._server.errorString()}", "WARNING")
        self._server = None
        self._mutex.release()
        # Fail-open: koruma kurulamazsa program yine de açılır.
        return True

    def _close_connection(self, connection, abort=False):
        self._connections.pop(connection, None)
        if abort:
            connection.abort()
        else:
            connection.disconnectFromServer()

    def _read_connection(self, connection):
        """Birincil GUI'yi bloklamadan gelen çerçeveyi biriktirir."""
        buffer = self._connections.get(connection)
        if buffer is None:
            return
        buffer.extend(bytes(connection.readAll()))
        if len(buffer) < FRAME_HEADER.size:
            return
        magic, version, payload_size = FRAME_HEADER.unpack_from(buffer)
        if (magic != FRAME_MAGIC or version != PROTOCOL_VERSION
                or payload_size > MAX_PAYLOAD_BYTES):
            self._close_connection(connection, abort=True)
            return
        expected = FRAME_HEADER.size + payload_size
        if len(buffer) < expected:
            return
        if len(buffer) != expected:
            self._close_connection(connection, abort=True)
            return
        try:
            payload = bytes(buffer[FRAME_HEADER.size:]).decode("utf-8")
        except UnicodeDecodeError:
            self._close_connection(connection, abort=True)
            return
        if not payload:
            self._close_connection(connection, abort=True)
            return
        connection.write(ACK)
        connection.flush()
        self.activation_requested.emit(
            "" if payload == ACTIVATE_TOKEN else payload)
        # disconnectFromServer bekleyen ACK yazısını tamamlayıp kapatır.
        self._close_connection(connection)

    def _on_new_connection(self):
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is None:
                return
            if len(self._connections) >= MAX_PENDING_CONNECTIONS:
                connection.abort()
                continue
            connection.setReadBufferSize(
                FRAME_HEADER.size + MAX_PAYLOAD_BYTES + 1)
            self._connections[connection] = bytearray()
            connection.readyRead.connect(
                lambda connection=connection: self._read_connection(connection))
            connection.disconnected.connect(
                lambda connection=connection:
                self._connections.pop(connection, None))
            self._read_connection(connection)

    def release(self):
        """Sunucuyu kapatır. Kapanış kooperatiftir."""
        for connection in list(self._connections):
            self._close_connection(connection, abort=True)
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self._name)
            self._server = None
        self._mutex.release()

    def _hand_over(self, socket, payload):
        """İsteği çalışan kopyaya iletir ve ACK bekler."""
        try:
            data = _encode_frame(payload)
        except (TypeError, ValueError, UnicodeEncodeError):
            log("Single instance: request payload is invalid.", "WARNING")
            return False
        if socket.write(data) != len(data):
            return False
        socket.flush()
        if not socket.waitForBytesWritten(TRANSFER_TIMEOUT_MS):
            return False
        if not socket.waitForReadyRead(TRANSFER_TIMEOUT_MS):
            log("Single instance: the running copy did not acknowledge the "
                "request.", "WARNING")
            return False
        return bytes(socket.readAll()) == ACK


def activate_window(window, payload=""):
    """Açık pencereyi standart çağrılarla öne getirir ve hedefi yükler."""
    if window.isMinimized():
        window.showNormal()
    window.raise_()
    window.activateWindow()
    if payload:
        window.open_external_target(payload)
