"""`.ts` çeviri kaynaklarını `.qm` ikililerine derler.

NEDEN AYRI ADIM. `.qm` ÜRETİLMİŞ dosyadır ve `.gitignore` içindedir;
`MLCPlayer.spec` onları `translations/` klasöründen toplar. Ama zinciri
kuran hiçbir adım onları derlemiyordu: temiz bir kopyada
`packaging/build_release.bat` çalıştırıldığında klasör boş kalıyor,
paket çevirisiz çıkıyor ve kullanıcı hiçbir uyarı almadan yalnız Türkçe
görüyordu. Bu betik o boşluğu kapatır ve `build_release.bat` içinde
PyInstaller'dan ÖNCE çalışır.

BOŞ ÇEVİRİLER DERLENMEZ. Tamamı `unfinished` olan bir `.ts` dosyası
geçerli ama İÇİ BOŞ bir `.qm` üretir. Onu paketlemek anlamsızdır:
`app.i18n.available_languages()` boş çeviriyi zaten reddeder, ama
paketin içinde ölü dosya taşımanın da bir yararı yoktur. Atlanan diller
RAPOR EDİLİR, sessizce yutulmaz.

Kullanım:
    python packaging/compile_translations.py
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATIONS_DIR = os.path.join(ROOT, "translations")

#: Qt'nin derleyicisi. PySide6 ile gelir; `pylupdate6` DEĞİL `lrelease`.
COMPILER = "pyside6-lrelease"


def translated_count(ts_path):
    """`.ts` dosyasındaki GERÇEKTEN çevrilmiş dizge sayısı.

    Bozuk XML sayı üretmez; dosya atlanır ve çağıran bunu rapor eder.
    """
    try:
        tree = ET.parse(ts_path)
    except ET.ParseError:
        return 0
    count = 0
    for message in tree.iter("message"):
        node = message.find("translation")
        if node is None:
            continue
        if node.get("type") != "unfinished" and (node.text or "").strip():
            count += 1
    return count


def compile_one(ts_path, qm_path):
    """Tek dosyayı derler. Dönüş: başarılıysa `True`."""
    result = subprocess.run([COMPILER, ts_path, "-qm", qm_path],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "")
        return False
    return os.path.isfile(qm_path)


def compile_all(source_dir=TRANSLATIONS_DIR, target_dir=None):
    """Bütün `.ts` dosyalarını derler.

    Dönüş: `(yazilan_qm_yollari, atlanan_dosya_adlari)`
    """
    target_dir = target_dir or source_dir
    os.makedirs(target_dir, exist_ok=True)
    written = []
    skipped = []
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith(".ts"):
            continue
        ts_path = os.path.join(source_dir, name)
        if translated_count(ts_path) == 0:
            # Çevirisi olmayan dil: boş `.qm` paketlemenin yararı yok.
            skipped.append(name)
            continue
        qm_path = os.path.join(target_dir, name[:-3] + ".qm")
        if compile_one(ts_path, qm_path):
            written.append(qm_path)
        else:
            skipped.append(name)
    return written, skipped


def main():
    try:
        written, skipped = compile_all()
    except FileNotFoundError:
        print(f"[HATA] {COMPILER} bulunamadi. Kurulum: pip install pyside6")
        return 1
    for path in written:
        print(f"[OK] {os.path.basename(path)}")
    for name in skipped:
        print(f"[ATLANDI] {name} (ceviri yok)")
    if not written:
        print("[HATA] Hicbir ceviri derlenemedi; paket cevirisiz cikar.")
        return 1
    print(f"[BILGI] {len(written)} ceviri derlendi, {len(skipped)} atlandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
