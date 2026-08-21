# MLC Player çalışma kuralları

Bu dosya yalnız kalıcı kuralları içerir. Güncel durum ve sıradaki iş için
`docs/CONTINUITY.md`, doğrulanmış sonuç için
`docs/VERIFICATION_LEDGER.json` dosyasını oku. Ortak agent başlangıç
sözleşmesi kökteki `AGENTS.md` dosyasıdır.

Aşağıdaki kuralların üçü `.claude/settings.json` içindeki hook'larla
mekanik olarak da uygulanır: `git stash/reset/checkout/restore` engellenir,
her Python düzenlemesinden sonra `compileall` çalışır ve oturum başında
git durumu ile sıradaki adım okunur. Hook'lar kuralın yerine geçmez;
unutulma ihtimalini kapatır.

## Başlangıç

1. `AGENTS.md`, `CLAUDE.md`, `docs/CONTINUITY.md` ve ilgili ledger kaydını oku.
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
- Geliştirme sırasında hedef testi çalıştır. Kapsam için `## Test stratejisi` bölümüne uy.
- Aynı başarısız komutu yeni hipotez olmadan tekrarlama.
- Terminal çıktısının tamamını rapora kopyalama; komut, sonuç, önemli hata ve exit code yeterlidir.
- Önceki raporları tekrar etme. Yalnız bu turdaki farkı ve devam eden riski yaz.
- Yeni geçici handoff dosyaları üretme. Güncel durumu yalnız
  `docs/CONTINUITY.md`, kalıcı kanıtı yalnız
  `docs/VERIFICATION_LEDGER.json` içinde tut; tarihsel belgeleri büyütme.

## Ürün değişmezleri

- Sinematik arayüz tek kullanıcı arayüzüdür; klasik arayüzü geri getirme.
- MPV native `wid`, fullscreen, overlay, OSD, auto-hide, fade, timeline, ses ve CC davranışlarını ilgili test olmadan değiştirme.
- **Playlist ana pencerenin YANINDA duran BAĞIMSIZ penceredir** (kullanıcı
  kararı, 17 Ağustos 2026; önceki kural "gömülü child yüzeyi"ydi). Şu üçü
  değişmedi ve testle korunur: video ile KESİŞMEZ, başka uygulamaların
  üzerinde YÜZMEZ (`WindowStaysOnTopHint` yok) ve video alanından yer
  ALMAZ. Pencere ana pencereye SAHİPLİ `Qt.Window`dur; `Qt.Tool`
  KULLANILMAZ — `Tool` odak kaybında pencereyi gizler ve kullanıcının
  raporladığı "başka uygulama öne gelince playlist kayboluyor" hatası
  tam olarak bundandı. Sözleşme:
  `tests/test_playlist_window_regressions.py`.
- Resume/watch-later kalıcılığını yeniden açma.
- Altyazı Merkezi worker'larını zorla `terminate()` etme; kooperatif kapanış ve tek sahiplik korunmalıdır.
- Yeni timer, always-on-top bayrağı veya geniş süreç temizliği ekleme.

## Yayın kuralları (imza zinciri — BOZULURSA KULLANICI GÜNCELLEME ALAMAZ)

Güncelleme, kurulum dosyasının SHA-256 özetinin yayıncı anahtarıyla
imzalanmasına dayanır (`app/release_signature.py`). Doğrulama fail-closed'dur:
imzası olmayan release REDDEDİLİR. Bu yüzden:

- **Release varlık sayısı sabit değildir.** Dört installer/imza varlığına,
  `packaging/corresponding_sources.json` içindeki doğrulanmış gerçek kaynak
  arşivleri eklenir. Eski binary paketler karşılık gelen kaynak sayılamaz.
  Manifest `ready` değilse veya blocker listesi doluysa yayın kapısı kapalıdır.
  Dinamik listeyi `packaging/fetch_sources.py`, bütünlüğü
  `python packaging/prepublish.py --tag vX.Y` denetler. Kesin varlık ve komut
  sözleşmesi yalnız `docs/RELEASE_PROCESS.md` içindedir.
- Installer imzaları `packaging/sign_release.py` ve `.sig` zinciriyle
  üretilir; bu uygulama imzası Windows Authenticode yerine geçmez.
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

- **YAYIN SÜRECİNİN TEK RESMÎ KAYNAĞI `docs/RELEASE_PROCESS.md`'DİR.**
  Kesin sıra, her adımın giriş/çıkış şartı, sekiz varlık sözleşmesi ve
  hata hâlinde nerede durulacağı ORADADIR; burada tekrarlanmaz.

  Buradan çıkmayan değişmezler:

  - **Tag ve push build'den ÖNCE yapılmaz.** Tag, test edilmiş ve build
    edilmiş HEAD'i işaretler.
  - **`--target master` KULLANILMAZ**; uzaktaki dalın o anki hâlini
    etiketler, yereldeki test edilmiş HEAD'i değil.
  - **`--verify-tag --draft` ZORUNLUDUR.**
  - **Build, commit, push, tag ve release AYRI AYRI kullanıcı onayı
    ister.** Biri için verilen onay diğerine geçmez.
  - Yayın öncesi kapı: `python packaging/prepublish.py --tag vX.Y`.

  Ölçülen olgu (salt-okunur, 17 Ağustos 2026): `v0.35` ve `v0.36`
  etiketleri sürüm yükseltme commit'inin EBEVEYNİNDEDİR
  (`2804c2f = 45de83c^`, `5b987d1 = 8284771^`) ve tag snapshot'ları bir
  önceki `APP_VERSION` değerini taşır. Ayrıntı ve çıkarım sınırları
  resmî belgededir. **Geçmiş tag'ler taşınmaz.**

## Çeviri kuralları (kullanıcı kararı, 17 Ağustos 2026)

- **Yalnız kullanıcının GÖRDÜĞÜ metin çevrilir.** `safe_console` çıktıları,
  günlük satırları, mpv özellik değerleri ve geliştirici tanıları Türkçe
  KALIR. Ölçüm: kaynakta 615+ sarmalanmamış Türkçe metin var ve çoğu bu
  sınıftandır; toplu sarmalama YANLIŞ olur.
- **Bir dil TAMAMEN bitmeden diğerine geçilmez.** Önce o dilin bütün
  eksikleri bulunur ve kapatılır; parça parça ilerlemek yarım kalmış altı
  dil üretir. Sıra: İngilizce (bitti) → sonraki dil → sonraki.
- **Terminoloji uydurulmaz, DOĞRULANIR.** Yerleşmiş oynatıcıların
  yayımlanmış çevirilerine bakılır; kullanıcı o terimleri bekler.
  KAYNAK (kullanıcı verdi): `https://github.com/videolan/vlc` → `po/`
  dizini; her dil kendi `.po` dosyasındadır (`de.po`, `fr.po`, `ru.po`…).
  "Playback speed", "Subtitle track", "Audio device" gibi terimlerin o
  dildeki YERLEŞİK karşılığı oradan doğrulanır.
  Dosyaları BİREBİR KOPYALAMA: VLC çevirileri GPLv2+ lisanslıdır;
  terminoloji referans alınır, metin kopyalanmaz.
- **Sarmalama toplu regex ile YAPILMAZ.** Bu yöntem 17 Ağustos 2026'da iki
  çok satırlı metin birleştirmesini bölüp programı açılamaz hâle getirdi.
  Dosya dosya ilerlenir ve HER dosyadan sonra AST ile ayrıştırma
  doğrulanır (`python -m compileall` yetmez, sözdizimi geçerli ama anlam
  bozuk kalabilir).
- **Modül düzeyi sabitler `tr()` ile SARMALANMAZ.** Import anında çevirmen
  henüz yoktur; sabit kaynak dile donar. `tr_mark()` ile işaretlenir,
  kullanım yerinde `translate_marked()` ile çevrilir (VLC'nin `N_()` +
  `vlc_gettext()` deyimi).
- **GÖRÜNEN METİN KİMLİK OLARAK KULLANILMAZ.** Bir menüyü, listedeki bir
  öğeyi veya kayıtlı bir tercihi `action.text()` / `currentText()` ile
  geri aramak, metin çevrildiği anda SESSİZCE başarısız olur. Kimlik
  nesnenin kendisidir ya da `QAction.data()` / `QComboBox` öğesinin
  `data()` alanıdır. Bu kusur 17 Ağustos 2026'da iki kez bulundu (menü
  sekme sırası, altyazı arama dili).
- **Sarmalanmamış metin taraması Türkçe harf aramakla BİTMEZ.** `Sessiz`,
  `Ses`, `Oynat` gibi ASCII-only metinler kaçar. Dosya bitmeden arayüz
  çağrılarının (`show_osd`, `setText`, `warning`, `QPushButton`…) sabit
  argümanları da AST ile taranır.
- Metin eklendikten sonra `python packaging/extract_translations.py`
  çalıştırılır; `--check` ile CI benzeri doğrulama yapılır. Çevrilemeyen
  (`tr(değişken)`) çağrılar RAPOR EDİLİR, sessizce atlanmaz.
- **Çıkarıcı YENİ METİN EKLENMESE DE gerekir.** `.ts` dosyaları her
  `tr()` çağrısının SATIR NUMARASINI tutar; `tr()` içeren bir dosyaya
  satır ekleyip çıkarmak kaydı bayatlatır ve
  `test_the_translation_files_are_up_to_date` KIRMIZI olur. Bu, 17
  Ağustos 2026'da tam paketi ÜÇ kez düşürdü. Kural: `tr()` taşıyan bir
  ürün dosyasına dokunulduysa, tur kapanmadan çıkarıcı çalıştırılır
  (metin sayısı değişmese bile — ölçüm: 442 → 442).

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
