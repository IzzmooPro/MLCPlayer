"""Yayımlanamaz sürümü YAYIMDAN ÖNCE yakalar.

ÖLÇÜLEN TUZAK: `app/updater.is_newer_version()` sürümleri SAYISAL
karşılaştırır (`v0.31` → `(0, 31, 0)`). Kullanıcının numaralandırması
`v0.3 → v0.31 → v0.32` olduğu için bu doğru çalışır, AMA bir gün `v0.31`'den
sonra `v0.4` yayımlanırsa `31 > 4` olduğundan kurulu kopyalar güncellemeyi
HİÇ GÖRMEZ; sessizce "güncelsiniz" derler.

Karşılaştırma semantiğini değiştirmek yerine kural BURADA zorlanır:
yayımlanacak sürüm, halihazırda yayımlanmış sürümden istemcinin KENDİ
ölçütüne göre kesinlikle yeni olmalıdır. Böylece tuzağa düşen bir etiket
release olamadan durdurulur.

Çıkış kodları:
    0  yayımlanabilir (veya ağ yok — uyarı verilir, zincir durdurulmaz)
    1  YAYIMLANAMAZ (istemciler bu sürümü göremez ya da etiket zaten var)
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import APP_VERSION                      # noqa: E402
from app.updater import GITHUB_REPO, is_newer_version   # noqa: E402

TIMEOUT = 8


def published_tags():
    """Yayımlanmış etiketler (yeniden eskiye). Ağ yoksa `None`."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    request = urllib.request.Request(
        url, headers={"User-Agent": f"MLCPlayer/{APP_VERSION}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return [str(item.get("tag_name", "")).strip() for item in data
            if item.get("tag_name")]


def evaluate(version, tags):
    """`(yayimlanabilir, mesaj)`. Ağ yoksa `tags` None gelir."""
    if tags is None:
        return True, ("[UYARI] GitHub'a ulasilamadi; surum karsilastirmasi "
                      "YAPILAMADI. Yayindan once elle dogrulayin.")
    if version in tags:
        # Bilincli yeniden derleme (ornegin yalniz kurulum sarmalayicisi
        # degistiginde) engellenmemeli; ama sessizce de gecmemeli.
        if os.environ.get("MLC_ALLOW_REPUBLISH") == "1":
            return True, (f"[UYARI] {version} zaten yayimlanmis; "
                          f"MLC_ALLOW_REPUBLISH=1 verildigi icin devam ediliyor.")
        return False, (f"[HATA] {version} etiketi ZATEN yayimlanmis. Surumu "
                       f"yukseltin veya bilerek yeniden uretiyorsaniz "
                       f"MLC_ALLOW_REPUBLISH=1 ile calistirin.")
    if not tags:
        return True, f"[OK] Ilk yayin: {version}"
    latest = tags[0]
    if not is_newer_version(version, latest):
        return False, (
            f"[HATA] {version}, yayindaki {latest} surumunden YENI DEGIL "
            f"(istemci olcutune gore). Kurulu kopyalar bu guncellemeyi "
            f"GOREMEZ. Ornek: v0.31 varken v0.4 yayimlanamaz; v0.40 kullanin.")
    return True, f"[OK] {version} > {latest} (yayindaki en son surum)"


def main():
    publishable, message = evaluate(APP_VERSION, published_tags())
    print(message)
    return 0 if publishable else 1


if __name__ == "__main__":
    sys.exit(main())
