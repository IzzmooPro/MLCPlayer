# MLC Player çalışma kuralları

Bu dosya yalnız kalıcı kuralları içerir. Güncel durum ve sıradaki iş için
`docs/PROJECT_STATUS.md` dosyasını oku.

Aşağıdaki kuralların üçü `.claude/settings.json` içindeki hook'larla
mekanik olarak da uygulanır: `git stash/reset/checkout/restore` engellenir,
her Python düzenlemesinden sonra `compileall` çalışır ve oturum başında
git durumu ile sıradaki adım okunur. Hook'lar kuralın yerine geçmez;
unutulma ihtimalini kapatır.

## Başlangıç

1. `CLAUDE.md` ve `docs/PROJECT_STATUS.md` dosyalarını oku.
2. `git status --short --branch` çalıştır (oturum hook'u bunu zaten sunar).
3. Yalnız görevle ilgili kaynak, test ve diff bölümlerini incele. Tüm depoyu veya eski raporları baştan okuma.
4. Kaynak ile rapor çelişirse kaynak ve yeniden üretilen davranış esas alınır.

## Çalışma yöntemi

- Kullanıcıyla Türkçe ve açık konuş.
- Hata düzeltmesinde önce gerçek davranışı ölçen başarısız test yaz; sonra minimum ürün değişikliğini yap.
- Tek turda tek bağımsız sorunu çöz. İlgisiz refaktör veya görsel değişiklik yapma.
- Kirli çalışma ağacını koru; `stash`, `reset`, `checkout` veya kullanıcı değişikliklerini geri alan komutlar kullanma.
- Kullanıcı açıkça istemedikçe commit, push, remote, tag, release, EXE/setup veya kalıcı Git config değişikliği yapma.
- Ekran görüntüsü, cache, log, kullanıcı ayarı ve büyük binary dosyalarını Git'e ekleme.

## Token tasarrufu

- Aramada önce `rg`; dosya okumada yalnız ilgili satır aralığını kullan.
- Geliştirme sırasında hedef testi çalıştır. Kapsam için `## Çeviri kuralları (kullanıcı kararı, 17 Ağustos 2026)

- **Yalnız kullanıcının GÖRDÜĞÜ metin çevrilir.** `safe_console` çıktıları,
  günlük satırları, mpv özellik değerleri ve geliştirici tanıları Türkçe
  KALIR. Ölçüm: kaynakta 615+ sarmalanmamış Türkçe metin var ve çoğu bu
  sınıftandır; toplu sarmalama YANLIŞ olur.
- **Bir dil TAMAMEN bitmeden diğerine geçilmez.** Önce o dilin bütün
  eksikleri bulunur ve kapatılır; parça parça ilerlemek yarım kalmış altı
  dil üretir. Sıra: İngilizce (bitti) → sonraki dil → sonraki.
- **Terminoloji uydurulmaz, DOĞRULANIR.** Yerleşmiş oynatıcıların
  (VLC, mpv, MPC-HC) yayımlanmış çevirilerine bakılır; kullanıcı o
  terimleri bekler. Dosyaları BİREBİR KOPYALAMA: VLC çevirileri GPLv2+
  lisanslıdır, terminoloji referans alınır, metin kopyalanmaz.
- **Sarmalama toplu regex ile YAPILMAZ.** Bu yöntem 17 Ağustos 2026'da iki
  çok satırlı metin birleştirmesini bölüp programı açılamaz hâle getirdi.
  Dosya dosya ilerlenir ve HER dosyadan sonra AST ile ayrıştırma
  doğrulanır (`python -m compileall` yetmez, sözdizimi geçerli ama anlam
  bozuk kalabilir).
- Metin eklendikten sonra `python packaging/extract_translations.py`
  çalıştırılır; `--check` ile CI benzeri doğrulama yapılır. Çevrilemeyen
  (`tr(değişken)`) çağrılar RAPOR EDİLİR, sessizce atlanmaz.

## Test stratejisi` bölümüne uy.
- Aynı başarısız komutu yeni hipotez olmadan tekrarlama.
- Terminal çıktısının tamamını rapora kopyalama; komut, sonuç, önemli hata ve exit code yeterlidir.
- Önceki raporları tekrar etme. Yalnız bu turdaki farkı ve devam eden riski yaz.
- Yeni handoff dosyaları üretme. Güncel durumu yalnız
  `docs/PROJECT_STATUS.md` içinde kısa tut.

## Ürün değişmezleri

- Sinematik arayüz tek kullanıcı arayüzüdür; klasik arayüzü geri getirme.
- MPV native `wid`, fullscreen, overlay, OSD, auto-hide, fade, timeline, ses ve CC davranışlarını ilgili test olmadan değiştirme.
- Playlist paneli ana pencerenin gömülü child yüzeyidir; video ile kesişmemeli ve başka uygulamaların üzerinde yüzmemelidir.
- Resume/watch-later kalıcılığını yeniden açma.
- Altyazı Merkezi worker'larını zorla `terminate()` etme; kooperatif kapanış ve tek sahiplik korunmalıdır.
- Yeni timer, always-on-top bayrağı veya geniş süreç temizliği ekleme.

## Yayın kuralları (imza zinciri — BOZULURSA KULLANICI GÜNCELLEME ALAMAZ)

Güncelleme, kurulum dosyasının SHA-256 özetinin yayıncı anahtarıyla
imzalanmasına dayanır (`app/release_signature.py`). Doğrulama fail-closed'dur:
imzası olmayan release REDDEDİLİR. Bu yüzden:

- **Her release'e İKİ dosya yüklenir:** `MLCPlayer_Setup_vX.exe` ve
  `MLCPlayer_Setup_vX.exe.sig`. İmza `packaging/build_release.bat` içinde
  otomatik üretilir (ADIM 5/6); zincir dışında elle derleme yapıldıysa
  `python packaging/sign_release.py <kurulum.exe>` çalıştırılır.
- **Özel anahtar depoya GİRMEZ.** Konum: `%USERPROFILE%\.mlcplayer\release_ed25519.key`
  (veya `MLC_SIGNING_KEY`). `.gitignore` ve
  `tests/test_release_signature_regressions.py` bunu korur.
- **Anahtar YENİDEN ÜRETİLMEZ.** Yeni anahtar, kurulu bütün kopyalar için
  güncellemeyi keser; kullanıcılar geçiş sürümünü ELLE kurmak zorunda kalır.
  Zorunluysa bu bedel kullanıcıya açıkça söylenir.
- **İmza denetimi devre dışı bırakılarak "düzeltme" yapılmaz.**
  `RELEASE_PUBLIC_KEY` boşaltmak veya doğrulama hatasını yutmak fail-open
  demektir; güncelleme kırıksa önce imzanın yüklenip yüklenmediğine bakılır.
- **Sürüm numarası:** `v0.3 → v0.31 → v0.32`. Karşılaştırma sayısaldır;
  `v0.31` varken `v0.4` yayımlanamaz (`31 > 4`, istemciler göremez); büyük
  adım için `v0.40`. `packaging/check_publishable.py` bunu zincirde durdurur.

## Çeviri kuralları (kullanıcı kararı, 17 Ağustos 2026)

- **Yalnız kullanıcının GÖRDÜĞÜ metin çevrilir.** `safe_console` çıktıları,
  günlük satırları, mpv özellik değerleri ve geliştirici tanıları Türkçe
  KALIR. Ölçüm: kaynakta 615+ sarmalanmamış Türkçe metin var ve çoğu bu
  sınıftandır; toplu sarmalama YANLIŞ olur.
- **Bir dil TAMAMEN bitmeden diğerine geçilmez.** Önce o dilin bütün
  eksikleri bulunur ve kapatılır; parça parça ilerlemek yarım kalmış altı
  dil üretir. Sıra: İngilizce (bitti) → sonraki dil → sonraki.
- **Terminoloji uydurulmaz, DOĞRULANIR.** Yerleşmiş oynatıcıların
  (VLC, mpv, MPC-HC) yayımlanmış çevirilerine bakılır; kullanıcı o
  terimleri bekler. Dosyaları BİREBİR KOPYALAMA: VLC çevirileri GPLv2+
  lisanslıdır, terminoloji referans alınır, metin kopyalanmaz.
- **Sarmalama toplu regex ile YAPILMAZ.** Bu yöntem 17 Ağustos 2026'da iki
  çok satırlı metin birleştirmesini bölüp programı açılamaz hâle getirdi.
  Dosya dosya ilerlenir ve HER dosyadan sonra AST ile ayrıştırma
  doğrulanır (`python -m compileall` yetmez, sözdizimi geçerli ama anlam
  bozuk kalabilir).
- Metin eklendikten sonra `python packaging/extract_translations.py`
  çalıştırılır; `--check` ile CI benzeri doğrulama yapılır. Çevrilemeyen
  (`tr(değişken)`) çağrılar RAPOR EDİLİR, sessizce atlanmaz.

## Test stratejisi

Test kapsamı etki alanına göre nokta atışıdır.

- Çözülmüş bir davranışı, ilgili kod yolu değişmedikçe yeniden native/fiziksel teste sokma. Yeni düzeltmenin o davranışa zarar verme ihtimali varsa yalnız ilgili regresyon testini çalıştır.
- Her sorun için sıra: (1) tek ve deterministik kırmızı test, (2) minimum düzeltme, (3) aynı testin yeşil sonucu, (4) değişen fonksiyonun doğrudan tüketicilerini kapsayan dar regresyon paketi, (5) görsel/native kanıt zorunluysa en fazla bir hedef child koşumu.
- Tam `pytest -q tests` yalnız ortak altyapı değiştiğinde veya turun sonunda gerçekten gerekliyse çalışır.
- Tam fiziksel matris yalnız release/setup öncesinde ve kullanıcı açıkça onaylarsa çalışır.
- Yeni FAIL görülürse otomatik tekrar koşma; önce mevcut log ve kaynağı incele.
- Kullanıcıdan izin almadan background GUI testi başlatma.
- Test öncesinde tahmini süreyi ve açılacak pencere/child sayısını bildir.

## Test ve güvenlik

- Qt/QSettings testleri benzersiz geçici dizin kullanmalı; gerçek kullanıcı ayarlarını kirletmemeli.
- Native testler yalnız kendi başlattığı kesin PID'i `try/finally` ile temizlemeli; Notepad/Explorer veya kullanıcının Python/Qt süreçlerini hedeflememeli.
- Native crash assertion geçse bile yok sayılmaz; son marker ve gerçek exit code raporlanır.
- Görsel değişiklik yalnız offscreen testle kabul edilmez; gerçek Windows penceresi ve mümkünse gerçek video gerekir.
- **Kayıt defteri ölçümü ve düzeltmesi yalnız `python -c "import winreg..."` ile yapılır.** `Get-ItemProperty`, `Set-ItemProperty` ve `reg.exe` bu ortamda GÜVENİLİR DEĞİLDİR: ajanın PowerShell'inden yapılan yazmalar sanal katmanda kalır, gerçek hive'a ulaşmaz. Çapraz test: `reg.exe`'nin yazdığını python GÖREMEZ, python'un yazdığını `reg.exe` GÖRÜR. Bu yüzden "düzelttim" raporları üç tur boyunca yanlıştı (bkz. docs/PROJECT_STATUS.md, ölçüm aracı tuzağı).
- Windows kabuk davranışı (ör. "Birlikte aç" adı) yalnız dosya meta verisiyle doğrulanmaz; Explorer adı çıkarımla bulup ÖNBELLEĞE alır. Kabul, kullanıcının gerçek menüsünde görülmesidir.

## Tur sonu

İlgili testlerden sonra çalıştır:

```powershell
python -m compileall -q main.py app tests
git diff --check
```

Ortak altyapı veya tamamlanmış ürün turunda ayrıca:

```powershell
pytest -q tests
```

Rapor yalnız şunları içersin: ilk kırmızı kanıt, değişen dosyalar, kullanıcı etkisi, test/compile/diff sonucu, kalan risk ve Git durumu.
