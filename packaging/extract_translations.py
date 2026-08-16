"""`tr("...")` çağrılarını toplayıp `.ts` çeviri dosyalarını günceller.

NEDEN KENDİ ÇIKARICIMIZ: `pylupdate6` YALNIZ `QCoreApplication.translate(...)`
biçimini tanıyor; `app/i18n.tr()` sarmalayıcısını GÖREMİYOR (ölçüldü). Her
çağrı yerine tam ifadeyi yazmak menü ve diyalog kodunu okunmaz hâle
getirirdi. Çalışma zamanı yine standart Qt'dir; yalnız ÇIKARMA bize aittir.

Ölçüm AST üzerindedir, metin araması değil: yorum satırındaki veya
docstring'deki bir `tr("...")` benzeri metin yanlışlıkla toplanmaz ve
değişken içeren çağrılar (`tr(baslik)`) sessizce atlanmaz — RAPOR EDİLİR,
çünkü çevrilemeyen metin kullanıcıya kaynak dilde görünür.

MEVCUT ÇEVİRİLER KORUNUR: `.ts` dosyası varsa çevrilmiş karşılıklar okunur
ve yeniden yazılırken kaybolmaz. Kaynak metin değişmişse çeviri
`type="unfinished"` olarak işaretlenir.

Kullanım:
    python packaging/extract_translations.py            # hepsini guncelle
    python packaging/extract_translations.py --check    # degisiklik var mi
"""

import ast
import os
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.i18n import (SOURCE_LANGUAGE, SUPPORTED_LANGUAGES,  # noqa: E402
                      TRANSLATION_CONTEXT, TRANSLATION_PREFIX,
                      TRANSLATIONS_DIR_NAME)

#: Taranan kaynaklar. Testler ve paketleme betikleri KULLANICIYA görünmez.
SOURCE_DIRECTORIES = ("app",)
SOURCE_FILES = ("main.py",)


class Collector(ast.NodeVisitor):
    """`tr(...)` çağrılarını toplar; sabit olmayanları ayrı raporlar."""

    def __init__(self, path):
        self.path = path
        self.texts = []          # (metin, satir)
        self.dynamic = []        # sabit metin OLMAYAN cagrilar

    def visit_Call(self, node):
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name == "tr" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.texts.append((first.value, node.lineno))
            else:
                self.dynamic.append(node.lineno)
        self.generic_visit(node)


def python_files():
    for relative in SOURCE_FILES:
        yield os.path.join(ROOT, relative)
    for directory in SOURCE_DIRECTORIES:
        base = os.path.join(ROOT, directory)
        for entry in sorted(os.listdir(base)):
            if entry.endswith(".py"):
                yield os.path.join(base, entry)


def collect():
    """Dönüş: `(metin -> [(dosya, satir)], dinamik_cagrilar)`"""
    found = {}
    dynamic = []
    for path in python_files():
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        collector = Collector(path)
        collector.visit(tree)
        relative = os.path.relpath(path, ROOT).replace("\\", "/")
        for text, line in collector.texts:
            found.setdefault(text, []).append((relative, line))
        dynamic.extend((relative, line) for line in collector.dynamic)
    return found, dynamic


def existing_translations(path):
    """Var olan `.ts` dosyasındaki çevirileri korur."""
    if not os.path.isfile(path):
        return {}
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return {}
    translations = {}
    for message in tree.iter("message"):
        source = message.findtext("source") or ""
        node = message.find("translation")
        if node is None:
            continue
        text = node.text or ""
        if text and node.get("type") != "unfinished":
            translations[source] = text
    return translations


def build_document(language, texts, translations):
    root = ET.Element("TS", version="2.1", language=language,
                      sourcelanguage=SOURCE_LANGUAGE)
    context = ET.SubElement(root, "context")
    ET.SubElement(context, "name").text = TRANSLATION_CONTEXT
    for text in sorted(texts):
        message = ET.SubElement(context, "message")
        for path, line in texts[text]:
            ET.SubElement(message, "location", filename=path, line=str(line))
        ET.SubElement(message, "source").text = text
        node = ET.SubElement(message, "translation")
        if text in translations:
            node.text = translations[text]
        else:
            node.set("type", "unfinished")
            node.text = ""
    return ET.ElementTree(root)


def translations_directory():
    return os.path.join(ROOT, TRANSLATIONS_DIR_NAME)


def target_path(language):
    return os.path.join(translations_directory(),
                        f"{TRANSLATION_PREFIX}{language}.ts")


def update(check_only=False):
    texts, dynamic = collect()
    os.makedirs(translations_directory(), exist_ok=True)

    print(f"[BILGI] {len(texts)} cevrilebilir metin bulundu.")
    if dynamic:
        print(f"[UYARI] {len(dynamic)} cagri sabit metin TASIMIYOR; bunlar "
              f"cevrilemez ve kullaniciya kaynak dilde gorunur:")
        for path, line in dynamic[:10]:
            print(f"         {path}:{line}")

    changed = []
    for language in SUPPORTED_LANGUAGES:
        if language == SOURCE_LANGUAGE:
            continue                      # kaynak dil cevrilmez
        path = target_path(language)
        document = build_document(language, texts, existing_translations(path))
        ET.indent(document, space="    ")
        before = open(path, "rb").read() if os.path.isfile(path) else b""
        payload = ET.tostring(document.getroot(), encoding="utf-8",
                              xml_declaration=True)
        if payload != before:
            changed.append(os.path.basename(path))
            if not check_only:
                with open(path, "wb") as handle:
                    handle.write(payload)

    if check_only:
        if changed:
            print("[HATA] Guncel degil: " + ", ".join(changed))
            print("       Calistirin: python packaging/extract_translations.py")
            return 1
        print("[OK] Ceviri dosyalari guncel.")
        return 0

    print("[OK] Yazilan: " + (", ".join(changed) if changed else "degisiklik yok"))
    return 0


if __name__ == "__main__":
    sys.exit(update(check_only="--check" in sys.argv))
