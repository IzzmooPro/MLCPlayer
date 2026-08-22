# MLC Player yayın süreci

**Bu dosya yayın sürecinin TEK RESMÎ KAYNAĞIDIR.** `CLAUDE.md`,
`docs/PACKAGING_PLAN.md` ve `packaging/prepublish.py` yalnız kritik
değişmezleri özetler ve buraya bağlanır. Sıra burada değişir, başka
yerde tekrarlanmaz.

Sözleşme: `tests/test_release_documentation_regressions.py`.

## Amaç

Yayımlanan sürümün üç şeyi aynı olsun: **tag adı**, **tag içindeki kaynak
sürümü** ve **kurulumu üreten commit**. Bunlar ayrıştığında kullanıcı
yanlış sürüm numarasıyla bir paket indirir ve güncelleyici zinciri
sessizce bozulur.

## Yetkilendirme sınırları

**Build, commit, push, tag ve release AYRI AYRI kullanıcı onayı ister.**
Biri için verilen onay diğerine geçmez. Ajan bu adımlardan hiçbirini
kendiliğinden yapmaz; hepsi kullanıcının açık talimatıyla çalışır.

Salt-okunur denetimler (`verify_build.py --pre`, `verify_release_ref.py`,
`prepublish.py`) onay gerektirmez. Bunlar:

- **repo veya dış sistem durumunu DEĞİŞTİRMEZ** — tag oluşturmaz, push
  etmez, commit atmaz, checkout/reset yapmaz, dosya silmez;
- yalnız **salt-okunur ve YEREL Git sorguları** çalıştırabilir
  (`git rev-parse`, `git show`, `git status`);
- **ağ kullanmaz.**

Bu ayrım kasıtlıdır: araçlar Git'i **çağırır**, ama yalnız okumak için.
"Git kullanmaz" demek yanlış olurdu; doğru olan, **durumu
değiştirmedikleridir**.

## Kod imzalama katmanları

SignPath is not currently part of the active release chain. Mevcut kurulumlar
Windows Authenticode imzası taşımaz; `CODE_SIGNING_POLICY.md` yalnız ücretsiz
SignPath başvurusu için hazırlık durumunu açıklar.

SignPath kabulü alınır ve ayrıca süreç değişikliği onaylanırsa Authenticode must happen before the existing detached Ed25519 signature is created.
Ed25519 `.sig`, Authenticode uygulanmış **son EXE baytlarının** SHA-256 değerini
imzalamalıdır. İki katman birbirinin yerine geçmez. SignPath kabulü, hosted
unsigned-build kapısı ve son installer kabul testleri tamamlanmadan aşağıdaki
kesin yayın sırası değiştirilmez.

**`git ls-remote` bu listede DEĞİLDİR.** Yalnız uzak doğrulama adımı
**(g)**'de çalışır ve **ağ kullanır**. `prepublish.py`,
`verify_release_ref.py` ve `verify_build.py --pre` tarafından
**çağrılmaz**; o üç araç ağsızdır ve ağsız kalmalıdır.

## Kesin yayın sırası

`master` PR kapısı aktifse sürüm alanı commit'i önce
`docs/CHANGE_WORKFLOW.md` sırasıyla PR üzerinden **merge commit** olarak
origin/master'a ulaşır. PR üzerindeki hosted `test` yeşil olmadan merge
yapılmaz. Rutin merge push'u otomatik CI başlatmadığı için sürüm adayında
ayrıca `workflow_dispatch` ile `master` üzerindeki exact merge commit tam
hosted testten geçirilir; bu koşum yeşil olmadan build başlamaz. Yerel
`master`, build öncesinde aynı exact merge commit'e fast-forward edilir.

    a) Sürüm alanlarını güncelle -> commit
         app/config.py            APP_VERSION
         packaging/MLCPlayer.iss  MyAppVersion
                                  VersionInfoVersion
                                  VersionInfoProductVersion
       GİRİŞ  : sürüm yükseltilecek, ağaç istenirse kirli
       ÇIKIŞ  : çalışma ağacı TEMİZ (staged/tracked/untracked yok)

    b) Hedef testler + packaging\build_release.bat
       GİRİŞ  : temiz ağaç
       ÇIKIŞ  : dört installer artifact'i üretildi ve imzalandı
                (zincir kendi içinde `--pre`, `--post`, `--final` yapar)

    b2) TAG'DEN ÖNCE zorunlu final-artifact fiziksel kabulü
        GİRİŞ  : b)'nin ürettiği TAM installer dosyaları
        ÇIKIŞ  : ana paket ve add-on için install -> upgrade -> uninstall
                 zinciri, interaktif ve silent yollar ayrı ayrı geçti
        KORUMA :
        - Gerçek kurulu Player, Restart Manager ile nazikçe kapanır; kapanış
          marker'ı/exit durumu doğrulanır ve yardımcı süreç sızmaz.
        - Başka klasörde çalışan aynı adlı `MLC Player.exe` hayatta kalır.
        - Kapanmayı reddeden/asılı süreçte kurulum DURUR; kurulu program
          ağacında tek bir byte bile değişmemeli.
        - Test medyası ile `%APPDATA%\MLCPlayer` ayar/log ağacı önce/sonra
          dosya listesi, metadata ve SHA-256 hash ile aynı kalır.
        - Add-on, boş/relative/root/UNC/eski/wrong-product InstallLocation
          kayıtlarını dosya yazmadan reddeder; aktif Player, yt-dlp ve deno
          süreçleriyle gerçek upgrade ayrıca ölçülür.
        - İki kaldırma sırası da denenir; yalnız boş kurulum dizinleri silinir.
        Bu kabul yeni artifact'in ad/boyut/SHA-256 değeriyle kaydedilir. Eski
        bir build'in fiziksel kabulü yeni artifact için kanıt SAYILMAZ.

    c) python packaging/fetch_sources.py
       GİRİŞ  : corresponding_sources.json `ready`, engel listesi boş
       ÇIKIŞ  : source_mirror içinde sözleşmedeki gerçek kaynak arşivleri,
                boyut + SHA-256 ile doğrulanmış

    d) Build BAŞARIYLA bittikten SONRA, test edilen HEAD üzerinde
       YEREL ANNOTATED tag:
           git tag -a vX.Y -m "MLC Player vX.Y"
       GİRİŞ  : build, final-artifact kabulü ve fetch bitti; ağaç temiz
       ÇIKIŞ  : yerel annotated tag HEAD'de

    e) python packaging/prepublish.py --tag vX.Y
       GİRİŞ  : yerel tag mevcut
       ÇIKIŞ  : exit 0 — installer ve dinamik kaynak listesi doğrulanmış

    f) Commit eşliği doğrulanır ve tag AÇIKÇA push edilir:
           git rev-parse HEAD
           git rev-parse origin/master
           git push origin vX.Y
       GİRİŞ  : kapı exit 0 verdi
       ÇIKIŞ  : iki commit AYNI ve uzakta annotated tag var

       PR kapısı etkin değilse eski direct-push akışında `git push origin
       master` ayrı açık push onayıyla bu adımdan önce yapılır. PR kapısı
       etkinse master commit'i zaten onaylı PR merge'iyle uzaktadır; burada
       master'a ikinci kez push yapılmaz.

    g) Uzak annotated tag'in PEELED commit'i yerel HEAD ile aynı mı:
           git ls-remote origin "refs/tags/vX.Y^{}"
           git rev-parse HEAD
       GİRİŞ  : push bitti
       ÇIKIŞ  : iki değer AYNI. Değilse yayın DURUR.

    h) Draft release (PowerShell). Ters bölü satır devamı Windows'ta
       ÇALIŞMAZ; varlıklar bir diziye konup splat edilir.
       GİRİŞ  : g) geçti
       ÇIKIŞ  : DRAFT release, bütün beklenen varlıklar yüklü

    i) Uzak varlık ad / boyut / SHA-256 eşliği:
           gh release view vX.Y --json assets
       Yerel dosyaların adı, byte boyutu ve SHA-256 değeri uzaktakiyle
       BİREBİR aynı olmalı.
       GİRİŞ  : draft hazır
       ÇIKIŞ  : bütün varlıkların üçlüsü de eşleşti

    j) Draft yayımlanır:
           gh release edit vX.Y --draft=false --latest
       GİRİŞ  : i) geçti
       ÇIKIŞ  : sürüm yayında

Adım (h) komutu — Windows PowerShell'de kopyalanıp çalıştırılabilir:

```powershell
$assets = @(
  "installer_output/MLCPlayer_Setup_vX.Y.exe"
  "installer_output/MLCPlayer_Setup_vX.Y.exe.sig"
  "installer_output/MLCPlayer_InternetVideo_vX.Y.exe"
  "installer_output/MLCPlayer_InternetVideo_vX.Y.exe.sig"
)
$sourceAssets = python -c "import sys; sys.path.insert(0, 'packaging'); import fetch_sources; [print('source_mirror/' + x.name) for x in fetch_sources.plan()]"
if ($LASTEXITCODE -ne 0) { throw "kaynak listesi okunamadi" }
$assets += @($sourceAssets)

gh release create vX.Y --verify-tag --draft --title "MLC Player vX.Y" --notes-file notlar.md @assets
```

Kaynak adları `packaging/corresponding_sources.json` sözleşmesinden türer.
`status` değeri `ready` değilse, engel varsa veya kaynak listesi boşsa yayın
kapısı kapanır. `bin/RUNTIME_MANIFEST.txt` yalnız binary köken kaydıdır.

### Uzun libmpv build'ini tekrarlamama kuralı

`libmpv-corresponding-source-20260821-g49418246f.tar.zst` varlığı run
`32488810460` içindeki doğrulanmış kaynak parçasıdır. Yeni libmpv girdisi veya
build tarifi değişmedikçe iki saatlik kaynak build'i tekrarlanmaz. İndirilen
parça bir kez şu komutla kalıcı v0.38 varlık adına hazırlanır:

```powershell
python packaging/stage_libmpv_source.py --source "<artifact-root>\source\parts\libmpv-corresponding-source.tar.zst.part-00"
```

Araç ağ, build, Git, tag veya release işlemi yapmaz. Kaynağı sözleşmedeki
`557940716` bayt ve SHA-256 değeriyle doğrular, geçici dosyaya yazar ve yalnız
tam eşleşmede `source_mirror/` hedefine atomik geçirir. Doğrulanmış hedef zaten
varsa kaynak dosyası veya yeni build gerektirmeden başarıyla döner. Kalıcı URL
v0.38 release yayımlandığında canlı olur; draft aşamasında aynı dosyanın uzak
ad/boyut/SHA-256 eşliği doğrulanmadan yayın yapılmaz.

### Cryptography/OpenSSL/Rust kaynak tekrar-kullanım kuralı

Kilitli `cryptography 50.0.0` Windows wheel'i kendi CycloneDX SBOM'larında
OpenSSL `4.0.1` kaynağını ve 32 dış Rust crate'ini ad/sürüm/SHA-256 ile taşır.
`packaging/stage_cryptography_sources.py`, bu envanteri sdist içindeki
`Cargo.lock` ile çapraz doğrular. Mevcut kaynakların ağsız kontrolü:

```powershell
python packaging/stage_cryptography_sources.py
```

Yalnız kaynaklar eksikse ve ağ indirmesi ayrıca amaçlanıyorsa:

```powershell
python packaging/stage_cryptography_sources.py --download
```

Araç yalnız resmi crates.io sürüm endpoint'ini ve yönlendirildiği
`static.crates.io` alanını kabul eder; geçici dosyanın SBOM hash'i tutmadan
mevcut hedefin üzerine yazmaz. Cryptography wheel sürümü değişmedikçe crate
envanteri yeniden araştırılmaz; aynı 32 doğrulanmış kaynak tekrar kullanılır.

### yt-dlp kaynak tekrar-kullanım kuralı

Kilitli resmî `yt-dlp.exe` yalnız `2026.08.19` sürümü, release commit'i
`594bd50c2c78ac432f81600d309fdc4e0a92d82c` ve SHA-256 değeri
`66674953...1dd3e7a` için doğrulandı. EXE'nin runtime raporu, resmî build
kilitleri, CPython `3.10.11` Windows kaynak pinleri ve `curl_cffi 0.16.0`
native CMake pinleri birlikte denetlenir. Mevcut 33 kaynağın ağsız kontrolü:

```powershell
python packaging/stage_ytdlp_sources.py
```

Yalnız kaynaklar eksikse ve ağ indirmesi ayrıca amaçlanıyorsa:

```powershell
python packaging/stage_ytdlp_sources.py --download
```

Araç build veya kurulum yapmaz; yalnız güvenilen resmî alanlardan geçici
dosyaya indirir ve SHA-256 eşleşmeden hedefi değiştirmez. yt-dlp EXE'si,
release commit'i veya kilitli paket sürümleri değişirse sözleşme yeniden
eşleştirilmeden yayın kapısı açılamaz.

### Değişmez kurallar

- **Tag ve push build'den ÖNCE yapılmaz.** Tag, test edilmiş ve build
  edilmiş HEAD'i işaretler; build'den önce atılırsa build'in ürettiği şey
  doğrulanmamış olur.
- **`--target master` KULLANILMAZ.** Uzaktaki dalın o anki hâlini
  etiketler; yereldeki test edilmiş HEAD'i değil.
- **`--verify-tag` ve `--draft` ZORUNLUDUR.** İlki var olmayan bir
  etiketle release açılmasını engeller, ikincisi yayımı son denetimden
  sonraya bırakır.
- **`^{}` peel şarttır.** Annotated tag önce bir TAG NESNESİNE çözülür;
  peel olmadan commit karşılaştırması sessizce yanlış sonuç verir.

## Yerel prepublish kapısı

`python packaging/prepublish.py --tag vX.Y` — adım (e).

Denetledikleri:

1. `verify_release_ref` : tag ↔ kaynak sürümü ↔ HEAD bütünlüğü
2. Git çalışma ağacı TAMAMEN temiz (staged / tracked / untracked)
3. Dört installer artifact'i mevcut
4. İki `.sig` **kriptografik** olarak doğru (Ed25519, EXE'nin SHA-256'sı
   üzerinden) — yalnız varlık denetimi değil
5. Kaynak sözleşmesi hazır ve engelsiz
6. Sözleşmedeki bütün kaynakların boyut + SHA-256 değerleri aynı

**Ağ kullanmaz. Hiçbir Git yazma komutu çalıştırmaz.** Tag oluşturmaz,
push etmez, release açmaz.

## Dinamik varlık sözleşmesi

| # | varlık | kaynak |
|---|---|---|
| 1 | `MLCPlayer_Setup_vX.Y.exe` | build (b) |
| 2 | `MLCPlayer_Setup_vX.Y.exe.sig` | build (b) |
| 3 | `MLCPlayer_InternetVideo_vX.Y.exe` | build (b) |
| 4 | `MLCPlayer_InternetVideo_vX.Y.exe.sig` | build (b) |
| 5+ | `source_mirror/` gerçek kaynak arşivleri | fetch (c) |

Kaynak varlıkları `packaging/corresponding_sources.json` dosyasından türer.
EXE, binary ZIP veya yalnız header/DLL taşıyan geliştirme paketi bu listeye
konamaz. GPLv3 §6 "karşılık gelen kaynak" yükümlülüğü içindir, süs değildir.

## Yerel/uzak eşlik

Adım (i)'de her varlık için üç değer karşılaştırılır: **ad**, **boyut**
(byte) ve **SHA-256**. Üçü de eşleşmeden draft yayımlanmaz.

## Hata olursa yayın nerede durur

| durum | duran adım | gerekçe |
|---|---|---|
| Çalışma ağacı kirli | (e) kapı | yayımlanan şey commit'lenmemiş olabilir |
| Tag eksik | (e) kapı | doğrulanacak nesne yok |
| Tag eski commit'te | (e) kapı | tarihsel kusurun tam kendisi |
| Sürüm alanları ayrışmış | (e) kapı | kullanıcı yanlış sürüm görür |
| Artifact veya `.sig` eksik | (e) kapı | eksik release |
| İmza geçersiz / başka EXE'ye ait | (e) kapı | güncelleyici fail-closed reddeder |
| Ayna boyut/SHA-256 tutmuyor | (e) kapı | GPLv3 §6 yükümlülüğü |
| Sürüm yerel veya uzak tag olarak zaten var | (b) build | `check_publishable.py`, kabul edilmiş aynı sürüm çıktılarının temizlenip ezilmesini önler |
| Ağ yok — **(b) build sırasında** | **koşullu** | aynı sürümün yerel tag'i varsa DURUR; tag yoksa `check_publishable` uyarır ve build devam edebilir |
| Ağ yok — **(g) / (h) / (i) sırasında** | **DURUR** | uzak tag ve varlık eşliği KANITLANAMAZ; doğrulanmamış yayın açılmaz |
| Uzak tag ≠ HEAD | (g) | asıl koruma; draft açılmaz |
| Uzak varlık eşleşmiyor | (i) | draft yayımlanmaz |

"Ağ yok" iki ayrı durumdur ve tek bir kuralla yönetilmez. Build
aşamasında uzak sorgu yalnız **bilgi** verir; fakat checkout'ta aynı
sürümün yerel tag'i bulunursa bu ayrıca kanıttır ve temizlikten önce build
durur. Yerel tag de yoksa ağ yokluğu uyarıyla geçilir. Yayın aşamasında ağ
**kanıt** kaynağıdır; yokluğunda uzak tag'in peeled commit'i ve varlık
özetleri doğrulanamayacağı için yayın durur.

## Tarihsel tag kusuru (v0.35 / v0.36)

**Ölçülen olgu (salt-okunur, 17 Ağustos 2026):**

    v0.35 -> 2804c2f = 45de83c^   snapshot'ında APP_VERSION v0.34
    v0.36 -> 5b987d1 = 8284771^   snapshot'ında APP_VERSION v0.35

Her iki tag da sürüm yükseltme commit'inin **ebeveynindedir** ve tag
snapshot'ı bir önceki `APP_VERSION` değerini taşır. Release'ler
`targetCommitish: master` ile oluşturulmuştur.

**Çıkarım (kanıt değil):** bu, bump commit'i uzağa ulaşmadan release
oluşturulduğunda beklenen sonuçtur.

**Ölçülmeyen:** release EXE'lerinin iç sürümü bu incelemede
denetlenmedi. Paketlerin içeriği hakkında bir iddia yoktur.

### Geçmiş tag'ler taşınmaz

`v0.35` ve `v0.36` **değiştirilmez, taşınmaz, silinmez**. Yayımlanmış bir
etiketi oynatmak indirilmiş kopyalarla imzaları ayrıştırır. Bu süreç
yalnız **gelecek** yayınlar içindir.

## Kalan manuel adımlar

- (g) ve (i) elle çalıştırılır; otomatik değildir çünkü ağ gerektirir ve
  `prepublish` kapısı bilerek ağsızdır.
- (j) yayımlama kararı kullanıcınındır.
- Kapı zincire bağlı değildir; atlanabilir olması disipline bağlıdır.
  Bağlanamaz, çünkü build sırasında tag henüz yoktur.
