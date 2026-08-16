"""Windows sürüm kaynağı (VS_VERSION_INFO) metnini üretir.

NEDEN VAR: paketlenen EXE'de sürüm kaynağı YOKTU. Windows "Birlikte aç"
listesinde ve dosya özelliklerinde `FileDescription` alanını okur; alan
boş olduğu için program **"MLC Player.exe"** olarak, yani dosya adıyla
görünüyordu. Ölçüm: `dist\\MLC Player\\MLC Player.exe` → ProductVersion boş.

Değerler `app/config.py` → `APP_VERSION` / `WINDOWS_VERSION` tek kaynağından
türer; `MLCPlayer.spec` bu metni build sırasında yazar ve PyInstaller'a
`version=` ile verir.
"""

COMPANY_NAME = "IzzmooPro"
FILE_DESCRIPTION = "MLC Player"      # Windows'un listede gösterdiği ad
PRODUCT_NAME = "MLC Player"
INTERNAL_NAME = "MLC Player"
ORIGINAL_FILENAME = "MLC Player.exe"
LEGAL_COPYRIGHT = "© IzzmooPro — GNU GPL v3"

# DİL KODU — ÖLÇÜLEN TUZAK: `StringTable` anahtarı ile `VarFileInfo`
# içindeki `Translation` AYNI dili göstermek ZORUNDADIR. İlk denemede
# anahtar `040E` (Macarca), Translation ise `1055` (0x041F, Türkçe) idi;
# kaynak EXE'ye GİRDİ (1404 bayt) ama Windows çözemedi ve bütün alanlar
# boş göründü. Bu yüzden Windows'un her kurulumda çözebildiği
# US English + Unicode çifti kullanılır; metinler ASCII'dir.
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
    """`0.2.0.0` → `(0, 2, 0, 0)`; Windows dört sayı ister."""
    parts = [int(part) for part in windows_version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def render(app_version, windows_version):
    """PyInstaller'ın `version=` ile okuduğu metni döndürür."""
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
