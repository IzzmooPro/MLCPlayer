"""Produces the Windows version resource (VS_VERSION_INFO) text.

WHY IT EXISTS: the packaged EXE had NO version resource. Windows reads the
`FileDescription` field for the "Open with" list and for the file
properties; because that field was empty, the program showed up as
**"MLC Player.exe"**, that is, by its file name. Measured:
`dist\\MLC Player\\MLC Player.exe` -> ProductVersion empty.

The values derive from the single source in `app/config.py`
(`APP_VERSION` / `WINDOWS_VERSION`); `MLCPlayer.spec` writes this text at
build time and hands it to PyInstaller through `version=`.
"""

COMPANY_NAME = "IzzmooPro"
FILE_DESCRIPTION = "MLC Player"      # the name Windows shows in the list
PRODUCT_NAME = "MLC Player"
INTERNAL_NAME = "MLC Player"
ORIGINAL_FILENAME = "MLC Player.exe"
LEGAL_COPYRIGHT = "© IzzmooPro — GNU GPL v3"

# LANGUAGE CODE - MEASURED TRAP: the `StringTable` key and the
# `Translation` entry inside `VarFileInfo` MUST name the SAME language. The
# first attempt paired key `040E` (Hungarian) with Translation `1055`
# (0x041F, Turkish); the resource DID reach the EXE (1404 bytes) but
# Windows could not resolve it and every field looked empty. So the US
# English + Unicode pair, which Windows resolves on every installation, is
# used and the strings are ASCII.
LANGUAGE_ID = 0x0409          # US English
CHARSET_ID = 1200             # Unicode
STRING_TABLE_KEY = f"{LANGUAGE_ID:04X}{CHARSET_ID:04X}"

TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers},
    prodvers={numbers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '{table_key}',
        [StringStruct('CompanyName', '{company}'),
         StringStruct('FileDescription', '{description}'),
         StringStruct('FileVersion', '{app_version}'),
         StringStruct('InternalName', '{internal}'),
         StringStruct('LegalCopyright', '{copyright}'),
         StringStruct('OriginalFilename', '{original}'),
         StringStruct('ProductName', '{product}'),
         StringStruct('ProductVersion', '{app_version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [{language}, {charset}])])
  ]
)
"""


def version_numbers(windows_version):
    """`0.2.0.0` -> `(0, 2, 0, 0)`; Windows wants four numbers."""
    parts = [int(part) for part in windows_version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def render(app_version, windows_version):
    """Returns the text PyInstaller reads through `version=`."""
    return TEMPLATE.format(
        numbers=version_numbers(windows_version),
        table_key=STRING_TABLE_KEY,
        language=LANGUAGE_ID,
        charset=CHARSET_ID,
        company=COMPANY_NAME,
        description=FILE_DESCRIPTION,
        app_version=app_version,
        internal=INTERNAL_NAME,
        copyright=LEGAL_COPYRIGHT,
        original=ORIGINAL_FILENAME,
        product=PRODUCT_NAME,
    )


def write(path, app_version, windows_version):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render(app_version, windows_version))
    return path
