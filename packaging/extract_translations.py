# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Collects `tr("...")` calls and updates the `.ts` translation files.

WHY OUR OWN EXTRACTOR: `pylupdate6` recognises ONLY the
`QCoreApplication.translate(...)` form and CANNOT SEE the `app/i18n.tr()`
wrapper (measured). Writing the full expression at every call site would
make the menu and dialog code unreadable. The runtime is still plain Qt;
only the EXTRACTION is ours.

The scan runs over the AST, not over raw text: something that merely looks
like `tr("...")` inside a comment or a docstring is not collected by
mistake, and calls carrying a variable (`tr(title)`) are not silently
skipped - they are REPORTED, because text that cannot be translated
reaches the user in the source language.

EXISTING TRANSLATIONS ARE KEPT: when a `.ts` file is already there, its
translations are read and survive the rewrite. If the source text changed,
the translation is marked `type="unfinished"`.

Usage:
    python packaging/extract_translations.py            # update everything
    python packaging/extract_translations.py --check    # is anything stale
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

#: Sources that are scanned. Tests and packaging scripts are NOT visible
#: to the user.
SOURCE_DIRECTORIES = ("app",)
SOURCE_FILES = ("main.py",)


#: Calls that PUT text into the translation files. `tr()` translates right
#: away; `tr_mark()` only marks (for module-level constants, where the
#: translation happens at use time through `translate_marked()`). Both must
#: carry a literal string.
EXTRACTING_CALLS = ("tr", "tr_mark")


class Collector(ast.NodeVisitor):
    """Collects translation calls; reports non-literal ones separately."""

    def __init__(self, path):
        self.path = path
        self.texts = []          # (text, line)
        self.dynamic = []        # calls WITHOUT a literal string

    def visit_Call(self, node):
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name in EXTRACTING_CALLS and node.args:
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
    """Returns `(text -> [(file, line)], dynamic_calls)`."""
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
    """Keeps the translations already present in a `.ts` file."""
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

    print(f"[INFO] {len(texts)} translatable strings found.")
    if dynamic:
        print(f"[WARNING] {len(dynamic)} calls carry NO literal string; "
              f"they cannot be translated and reach the user in the "
              f"source language:")
        for path, line in dynamic[:10]:
            print(f"         {path}:{line}")

    changed = []
    for language in SUPPORTED_LANGUAGES:
        if language == SOURCE_LANGUAGE:
            continue                      # the source language is not translated
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
            print("[ERROR] Out of date: " + ", ".join(changed))
            print("        Run: python packaging/extract_translations.py")
            return 1
        print("[OK] The translation files are up to date.")
        return 0

    print("[OK] Written: " + (", ".join(changed) if changed else "no changes"))
    return 0


if __name__ == "__main__":
    sys.exit(update(check_only="--check" in sys.argv))
