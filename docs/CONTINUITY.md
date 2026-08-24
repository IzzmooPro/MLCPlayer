# MLC Player güncel devam noktası

Bu dosya projenin **tek güncel devir noktasıdır**. Tarihsel ayrıntı burada
büyütülmez; doğrulanmış sonuçlar `VERIFICATION_LEDGER.json`, eski kapsamlı
notlar `PROJECT_STATUS.md`, `ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 24 Ağustos 2026
- Kayıt hazırlanırken doğrulanan HEAD: `227550d3cbefe62756a8fd764a1b4bc2b03f5237`
- Güncel HEAD/origin farkı: her oturumda `git rev-list --left-right --count
  HEAD...origin/master` ile canlı ölçülür; bu belge kendi commit hash'ini
  önceden tahmin etmez.
- Dal: `master` (yerel çalışma dalı farklı ad taşıyabilir)
- Son kanıt: `EV-20260824-006`
- Yayın kararı: **v0.39 canlı ve latest; 87 varlık eş, public indirme/kurulum/
  açılış/gerçek medya oynatma kullanıcı kabulü geçti; CI bootstrap gürültüsü
  gerçek hosted run ile temizlendi**

## Şu anda doğrulanmış durum

1. Ürün ve tek-instance IPC düzeltmeleri `15d2e24` tabanında tamamlandı.
   Gerçek uygulamada ikinci açılış, dosya ve YouTube bağlantısı aktarımı
   kullanıcı tarafından doğrulandı. Bu manuel kabul, yeni bir build veya
   kurulu v0.37 kanıtı değildir.
2. GitHub CI, `8c7506e` üzerinde geçti: run `32465911298`, **4712 passed / 26
   skipped / 0 failed**. Bu hosted kanıttır; skip edilen native/kurulu paket
   yollarını yeşile çevirmez.
3. Devam sistemi commit'i `50641a4` için run `32467900184`, **4719 passed /
   26 skipped / 1 failed** verdi. Eksik `sign_release.py` belge sözleşmesi
   gerçek hatadır; ürün çalışma zamanı hatası değildir. Otomatik tekrar
   yapılmadı ve sonuç `EV-20260821-006` olarak kaydedildi. Düzeltme
   `add2533` ile push edildi; run `32468470119` ilk denemede **4720 passed /
   26 skipped / 0 failed** verdi (`EV-20260821-007`).
4. libmpv karşılık gelen kaynak derlemesi henüz başarılı değildir. İlk run
   `32414388160`, iki saat sonra build-time Git kimliği eksikliğiyle durdu;
   DLL ve kaynak paketi oluşmadı, yalnız log artifact'i oluştu.
5. Git kimliği düzeltmesinden sonraki run `32469172739`, dış upstream imajın
   sabit digest'i registry'den silindiği için `Initialize containers` adımında
   13 saniyede durdu (`manifest unknown`). Kod, kaynak indirme ve derleme hiç
   başlamadı; artifact yoktur (`EV-20260821-008`). Aynı çalışma otomatik
   tekrarlanmadı.
6. İmajın kaynak deposu `shinchiro/archlinux-docker`, GPL-3.0 lisanslıdır.
   Güncel immutable digest doğrulandı. Kendi GHCR alanımıza yalnız bu digest'i
   ve kaynak etiketini doğrulayarak taşıyan manuel mirror iş akışı yerelde
   hazırlandı; kaynak repo commit'i ve GPL-3.0 lisansı da kayda bağlandı.
   İlgili workflow/devam paketi **15 passed** verdi. Çözüm `0035f7c` ile
   push edildi; hosted run `32470025995` ilk denemede **4721 passed / 26
   skipped / 0 failed** verdi (`EV-20260821-009`). Mirror run `32470615045`
   kaynak doğrulamasını ve katman push'unu tamamladı; owned hedef digest
   `b71001…` oldu. İş akışı kaynak OCI digest'inin hedefte aynen kalacağını
   yanlış varsaydığı için final readback kırmızı oldu (`EV-20260821-010`).
   Otomatik tekrar yapılmadı. Bağımsız registry readback, kaynak ve hedefin
   aynı config ile aynı iki katman digest/boyutunu taşıdığını doğruladı
   (`EV-20260821-011`). Digest düzeltmesi `ab6255e` ile push edildi; hosted
   run `32472613516` ilk denemede **4721 passed / 26 skipped / 0 failed**
   verdi (`EV-20260821-012`). Mirror artifact'i sağlamdır; libmpv build
   başlamadı.
7. Owned imajla libmpv run `32473206459`, araç zinciri ve bağımlılıkları
   tamamladıktan sonra `mpv.exe` ve `libmpv-2.dll` bağlama aşamasında durdu.
   Rust nightly LLVM 23 ThinLTO bitcode üretirken sabit tarif LLVM 22.1.8
   kullandı. Yalnız `libmpv-build-logs` artifact'i oluştu; DLL ve karşılık
   gelen kaynak paketi oluşmadı (`EV-20260821-013`). Otomatik tekrar yapılmadı.
8. Package ThinLTO kapatıldı ve CMake cache değeri kaynak indirmeden önce
   zorunlu doğrulamaya bağlandı. Dar iş akışı testleri **9 passed**, devam
   testleri **7 passed** ve `git diff --check` temizdir (`EV-20260821-014`).
   Bu deterministic kanıttır; gerçek DLL üretildiğini göstermez.
9. Düzeltme `4b94867` ile push edildi. Hosted run `32488320851` ilk denemede
   **4722 passed / 26 skipped / 0 failed** verdi (`EV-20260821-015`). Bu
   hosted kanıttır; libmpv kaynak build'i veya DLL kanıtı değildir.
10. `libmpv source-captured build` run `32488810460` başarıyla tamamlandı.
   Üç artifact'in GitHub boyut/SHA-256 değerleri, iç checksum listeleri, iki
   7z arşivi, 112.772.608 baytlık `libmpv-2.dll`, 98.736 girdilik kaynak
   arşivi, 113 kaynak dizini ve 1.126 log dosyası bağımsız doğrulandı
   (`EV-20260821-016`). Bu source_build kanıtıdır; DLL henüz projeye veya
   kurulu uygulamaya alınmadı ve MLC Player native smoke yapılmadı.
11. Kayıt commit'i `df7b0d9` için hosted run `32488993182` ilk denemede
   **4722 passed / 26 skipped / 0 failed** verdi (`EV-20260821-017`). Bu
   sonuç kaynak build'i veya native davranış kanıtına dönüştürülmez.
12. Player artifact'inden çıkarılan `mpv.com --version` Windows'ta exit 0
   verdi: mpv `v0.41.0-930-g49418246f`, FFmpeg `N-126239-g88ae625e6`
   (`EV-20260821-018`). Bu yalnız player artifact native probudur; MLC Player
   henüz yeni `libmpv-2.dll` dosyasını yüklemedi ve medya oynatmadı.
13. Yeni `libmpv-2.dll` yerel proje runtime'ına alındı. Gerçek MLC Player
   açılış/kapanış smoke'u **1 passed** verdi; geçici dizinde üretilen 3
   saniyelik WAV açıldı, dış altyazı parçası uygulandı/seçildi, kanonik
   kapanış ve `MARK_DONE` ile süreç exit 0 döndü (`EV-20260821-019`). DLL
   `112.772.608` bayt ve SHA-256 değeri `de80329f...f684f4e` olarak manifest,
   checksum ve mpv notice dosyalarına işlendi. Bu görsel video, internet
   videosu, paket veya kurulu uygulama kabulü değildir.
14. Runtime metadata commit'i `fdaad7b` push edildi; hosted run `32514249686`
   ilk denemede **4722 passed / 26 skipped / 0 failed** verdi
   (`EV-20260821-020`). İki saatlik libmpv build'i tekrar çalıştırılmadı.
15. Doğrulanmış libmpv kaynak parçası yeniden build edilmeden
   `source_mirror/libmpv-corresponding-source-20260821-g49418246f.tar.zst`
   adına hazırlandı: `557.940.716` bayt, SHA-256 `5ce4be...efc0`. Aynı dosya
   kaynak argümanı olmadan yeniden doğrulandı; kalıcı v0.38 URL'si sözleşmeye
   bağlandı ve ilgili **238 test geçti** (`EV-20260821-021`). URL ancak v0.38
   release yayımlandığında canlı olur; tag/release yapılmadı.
16. Kaynak staging commit'i `786f388` push edildi; hosted run `32515193214`
   ilk denemede **4728 passed / 26 skipped / 0 failed** verdi
   (`EV-20260821-022`). Uzun libmpv build'i çalışmadı.
17. Kilitli `cryptography 50.0.0` wheel'inin CycloneDX SBOM'ları OpenSSL
   `4.0.1` ve 32 dış Rust crate'ini bildirdi. OpenSSL kaynak hash'i, sdist
   `Cargo.lock` envanteri ve indirilen 32 `.crate` dosyası wheel SBOM'uyla
   birebir eşleşti; 32 crate toplam `4.121.466` bayttır. Ağsız yeniden kontrol
   ve ilgili **31 test geçti** (`EV-20260821-023`). Cryptography sürümü
   değişmedikçe bu kaynaklar yeniden araştırılmaz veya indirilmez.
18. Resmî `yt-dlp.exe` (`2026.08.19`, commit `594bd50c...`) içindeki Python
   `3.10.11`, 14 kilitli runtime paketi, PyInstaller `6.22.0`, CPython Windows
   bağımlılıkları ve `curl_cffi` native zinciri toplam 33 kaynak arşiviyle
   eşleştirildi. Ağsız doğrulama ve ilgili **243 test geçti**
   (`EV-20260821-024`). yt-dlp sürümü değişmedikçe bu kaynaklar yeniden
   araştırılmaz veya indirilmez.
19. Kurulu lisans paketi kaynakta tamamlandı: Python/PyQt6/Qt ve paketlenen
   Python runtime bağımlılıklarının bildirimleri, tam Qt LGPLv3 metni ve
   `_internal\\PyQt6\\Qt6` dinamik değiştirme talimatı ana pakete bağlandı.
   İlgili **132 test** ve release ön-kontrolü geçti (`EV-20260821-025`).
   `corresponding_sources.json` yalnız taze build ve kurulu-artifact kabulü
   bu yerleşimi henüz kanıtlamadığı için `blocked` kalır.
20. Ürün ve installer sürüm kaynakları `v0.38` / `0.38.0.0` olarak birlikte
   yükseltildi; sürüm, paketleme ve devamlılık kapsamındaki **254 test** ile
   release ön-kontrolü geçti (`EV-20260821-026`). Build henüz yapılmadı.
21. `SUBTITLE_SEARCH_UI_ENABLED=False` korunur. Yerel altyazı etkilenmez;
   OpenSubtitles masaüstü dağıtım şartı doğrulanmadan çevrimiçi arama açılmaz.
22. Temiz `f64188f` üzerinde v0.38 kaynak build'i **DONE / exit 0** verdi.
   Ana installer `56.293.597` bayt ve SHA-256 `cb9d047b...d8b85`; add-on
   `48.896.317` bayt ve SHA-256 `16416b7c...9d28`. İki Ed25519 imzası
   doğrulandı; ana `dist` içindeki 12 lisans/notice dosyası kaynakla bayt bayt
   aynı ve installer sürümü `0.38.0.0` (`EV-20260821-027`). Kurulum, tag,
   push veya release yapılmadı; Kurulu v0.37 bu artifact için kanıt değildir.
23. Exact ana installer kullanıcı onayıyla v0.37 üzerine kuruldu; exit 0,
   restart yok. Kayıt ve EXE sürümü v0.38, kurulu 12 lisans/notice dosyası
   kaynakla bayt bayt aynı, Qt DLL/plugin değiştirme yolu mevcut. Kullanıcı
   ayarı ve log SHA-256 değerleri kurulum öncesi/sonrası aynı kaldı
   (`EV-20260821-028`). `corresponding_sources.json` artık `ready` ve blocker
   listesi boştur. Bu installed-artifact kanıtıdır; native oynatma veya
   kaldırma kabulü değildir.
24. Hazır sözleşme tam modda ağsız doğrulandı: **83/83** kaynak arşivi mevcut
   boyut ve SHA-256 değerleriyle geçti; indirme veya build yapılmadı
   (`EV-20260821-029`). Ready/blocked test sözleşmeleri ayrıldı ve ilgili
   **24 test** geçti.
25. İlk installed native smoke gözlemcisi GUI `safe_console` metnini dosya
   logunda aradığı için geçersiz kaldı ve süreç zorla kapatıldı
   (`EV-20260821-030`, PASS değildir). Neden incelendikten sonra ürünün gerçek
   başlık sözleşmesiyle yapılan koşum geçti: kurulu v0.38 geçici WAV'ı açtı,
   başlık dosya adına döndü, süreç 4 saniye canlı kaldı, normal `WM_CLOSE`
   sonrası exit 0 verdi ve süreç sızmadı (`EV-20260821-031`). Kullanıcı INI
   hash'i değişmedi; çalışma logu beklenen safe-band kaydıyla 66 bayt büyüdü.
26. Kullanıcının açık bıraktığını doğruladığı kurulu v0.38 üzerinde ana paket
   kaldırıcı exit 0 verdi ve kayıt/kısayolları sildi; buna rağmen **36 ürün
   dosyası / 183.272.347 bayt** kurulum dizininde kaldı. Log, çok sayıda
   silme hatası 5 ve `Removed all? No` kaydetti. Ayar, log ve yerel önbellekteki
   68 dosyanın yol/boyut/zaman/SHA-256 değerleri değişmedi; add-on'a
   dokunulmadı (`EV-20260821-032`, **FAILED**). Otomatik tekrar yapılmadı.
27. Ana ürün süreç ömrü boyunca `MLCPlayer-Running` mutex'ini artık açık
   tutuyor; ana kaldırıcı aynı mutex mevcutsa hiçbir kayıt, kısayol veya dosya
   silmeden fail-closed duruyor. Kurulumun Restart Manager davranışı ve add-on
   değiştirilmedi. Regresyon önce kırmızıydı; düzeltme sonrası ilgili **29 test
   geçti** (`EV-20260821-033`). Bu deterministic kanıttır; yeni installer veya
   fiziksel kaldırma PASS'i değildir.
28. Temiz ve push edilmiş `9f294c2` üzerinde v0.38 build ilk koşumda **DONE /
   exit 0** verdi. Yeni ana installer `56.318.464` bayt ve SHA-256
   `5eab7e...ec01`; add-on `48.896.317` bayt ve SHA-256 `16416b...9d28`.
   İki Ed25519 imzası doğrulandı (`EV-20260821-034`). Bu source_build
   kanıtıdır; installer çalıştırılmadı ve fiziksel kaldırma henüz kanıtlanmadı.
29. Eski başarısız kaldırmadan kalan doğrulanmış 36 ürün dosyası / 183.272.347
   bayt, sıfır süreç-modül kullanımı ölçüldükten sonra yalnız
   `C:\Program Files\MLC Player` hedefinden temizlendi. Hedef artık yok; AppData
   altındaki 68 kullanıcı dosyasının yol/boyut/zaman/SHA-256 değerleri aynı
   kaldı (`EV-20260821-035`). Bu manuel kurtarmadır; uninstaller PASS'i değildir.
30. Exact yeni ana installer temiz hedefe exit 0 ile kuruldu. Kurulu EXE
   `3.118.308` bayt, SHA-256 `a851c2...6ee2` ve FileVersion `v0.38`; tek
   uninstall kaydı mevcut. AppData altındaki 68 kullanıcı dosyası aynı kaldı,
   add-on ikilileri kurulmadı (`EV-20260821-036`). Uygulama henüz açılmadı ve
   yeni kaldırıcı davranışı fiziksel olarak ölçülmedi.
31. Açık Player varken yeni mutex kapısı doğru çalıştı: kaldırıcı exit 1 ile
   hiçbir dosya/kayıt/kısayol veya kullanıcı verisini değiştirmeden durdu.
   Player normal kapatıldıktan sonra kaldırıcı exit 0 / `Removed all? Yes`
   verdi; ürün dizini, uninstall kaydı, HKLM kaydı ve kısayollar gitti, 68
   AppData dosyası aynı kaldı. Ancak eski sürümden kalmış kullanıcı düzeyi
   `HKCU\Software\Classes\Applications\MLC Player.exe` ağacı silinmiş EXE'ye
   işaret ederek kaldı (`EV-20260821-037`, **FAILED**). Otomatik tekrar veya
   kayıt temizliği yapılmadı.
32. Installer'a yalnız tam ürün anahtarını hedefleyen
   `HKCU\Software\Classes\Applications\MLC Player.exe` kaldırma kuralı eklendi.
   `dontcreatekey` kurulumda kullanıcı anahtarı oluşturmuyor/değiştirmiyor;
   `uninsdeletekey` yalnız uninstall sırasında ürüne özel ağacı temizliyor.
   Paylaşılan `Applications` üst ağacı testle yasaklandı. Regresyon önce
   kırmızıydı; düzeltmeden sonra ilgili **21 test geçti**
   (`EV-20260821-038`). Build veya fiziksel retest yapılmadı.
33. Temiz ve push edilmiş `50b230e` üzerinde build ilk koşumda **DONE / exit
   0** verdi. Yeni ana installer `56.308.623` bayt ve SHA-256
   `bfac5d...bc3a2`; add-on kimliği değişmedi. İki Ed25519 imzası doğrulandı.
   Eski HKCU anahtarı mevcut, ürün dizini yok; fiziksel retest başlangıç koşulu
   korunuyor (`EV-20260821-039`). Installer henüz çalıştırılmadı.
34. Exact yeni installer exit 0 ile kuruldu. Eski HKCU ağacının `reg.exe /s`
   temsili kurulum öncesi/sonrası aynı SHA-256 değerini (`9cb332...ebcd`)
   taşıdı; `dontcreatekey` fiziksel olarak doğrulandı. Kurulu EXE
   `3.118.308` bayt ve SHA-256 `870307...ca64`; tek uninstall kaydı mevcut.
   AppData altındaki 68 dosya aynı kaldı, add-on kurulmadı
   (`EV-20260821-040`). Uninstall temizliği henüz ölçülmedi.
35. Aynı exact ana artifact'ın kaldırıcısı exit 0 verdi; log
   `Uninstallation process succeeded`, `Removed all? Yes` ve yeniden başlatma
   gerekmediğini kaydetti. Ürün dizini, uninstall kaydı, HKLM/HKCR ürün
   kayıtları ve kısayollar tamamen gitti. Önceden mevcut eski ürüne özel HKCU
   ağacı silindi; komşu 3 `Applications` anahtarı aynı kaldı. AppData altındaki
   68 dosya yol/boyut/zaman/SHA-256 olarak değişmedi, süreç sızıntısı olmadı ve
   add-on'a dokunulmadı (`EV-20260821-041`). Fiziksel kayıt temizliği kabulü
   geçti.
36. Kalıcı libmpv kaynak dosyası yerelde yeniden build edilmeden doğrulandı:
   `libmpv-corresponding-source-20260821-g49418246f.tar.zst`, `557.940.716`
   bayt, SHA-256 `5ce4be...efc0`. GitHub API yalnız v0.33–v0.37 yayınlarını
   döndürdü; `gh release view v0.38` `release not found` / exit 1 verdi ve
   uzak v0.38 tag'i de yok. Bu nedenle uzak asset eşliği **BLOCKED**;
   doğrulanacak uzak dosya henüz oluşturulmamış (`EV-20260821-042`). Uzun
   libmpv build'i tekrarlanmadı ve GitHub'da değişiklik yapılmadı.
37. `v0.38` annotated tag'i `b1b6c4d` commit'ine oluşturulup push edildi;
   uzak peeled commit yerel HEAD ile aynıydı. `prepublish.py --tag v0.38`
   dört kapının tamamını geçti ve 87 varlığı hazır buldu. Draft release
   `374689765` oluşturuldu; 87/87 uzak varlıkta ad, byte boyutu, SHA-256 digest
   ve `uploaded` durumu yerel dosyalarla birebir eşleşti
   (`EV-20260821-043`). Draft henüz yayınlanmadı; libmpv build'i tekrarlanmadı.
38. Ayrı açık yayın onayıyla draft canlıya alındı. Kimlik doğrulamalı ve anonim
   GitHub API okumaları `v0.38`, `draft=false`, `prerelease=false`, 87 varlık
   ve latest tag `v0.38` döndürdü; herkese açık release sayfası HTTP 200 verdi.
   Ana installer `56.308.623` bayt / SHA-256 `bfac5d...bc3a2`, kalıcı libmpv
   kaynağı `557.940.716` bayt / SHA-256 `5ce4be...efc0` olarak public metadata'da
   doğrulandı (`EV-20260821-044`). Yeni build, kurulum veya native smoke
   çalıştırılmadı.
39. Canlı v0.38 açıklamasının en üstüne ana installer ve isteğe bağlı İnternet
   Video installer'ı için doğrudan indirme bağlantıları eklendi. Kalan
   varlıkların imza ve açık kaynak karşılık-gelen-kaynak dosyaları olduğu,
   normal kullanıcıların bunları indirmemesi gerektiği açıklandı. Geri okuma
   iki bağlantıyı ve uyarıyı doğruladı; release canlı kaldı ve 87 varlığın
   hiçbiri değiştirilmedi (`EV-20260821-045`).
40. `fa78529` için hosted CI run `32531352457`, **4752 passed / 26 skipped /
   5 failed** verdi. Bir hata Windows checkout'taki lisans CRLF dönüşümü,
   dört hata ise normal CI checkout'unda bulunmayan ignored `source_mirror`
   arşivlerinin koşulsuz açılmasıydı. Ürün, native smoke veya v0.38 yayın
   artifact'i yeniden ölçülmedi; otomatik tekrar yapılmadı
   (`EV-20260822-001`).
41. Lisans metinleri bütün checkout'larda LF'e sabitlendi. Dört derin arşiv
   testi yalnız staged corresponding-source artifact'i mevcutsa çalışıyor;
   staging komutu aynı dört doğrulamayı zorunlu tutmaya devam ediyor. Önce
   kırmızı yerel koşum **5 failed / 9 passed**, düzeltme sonrası dar koşum
   **18 passed / 4 artifact-skip** verdi. Kaynak indirilmedi, build veya release
   yapılmadı (`EV-20260822-002`).
42. Güncelleme installer'ı indirme sonrasında ve ürün kapanmadan hemen önce
   boyut/SHA-256 ile yeniden doğrulanıyor; normal dosya ve reparse kontrolleri
   yapılıyor. Windows'ta launcher çağrısı dönene kadar dosya yazma ve silmeye
   kapalı tutuluyor. Regresyon önce **2 failed**, düzeltme sonrasında güncelleyici
   hedef grubu **69 passed** verdi. Bu deterministic/Windows kilit kanıtıdır;
   gerçek UAC veya kurulu artifact testi değildir (`EV-20260822-003`).
43. GHSA düzeltme sınırlarına göre yalnız geliştirici/test/build kilitleri
   Pillow `12.3.0`, pytest `9.0.3` ve setuptools `83.0.0` sürümlerine taşındı.
   Resmî PyPI metadata'sı Python 3.13/3.14 uyumunu doğruladı; ürün runtime
   gereksinimleri değişmedi ve bu paketler PyInstaller dışlama sözleşmesine
   bağlandı. Bağımlılık hedef grubu **17 passed** verdi. Paket kurulmadı ve
   build yapılmadı (`EV-20260822-004`).
44. Eski placeholder QLabel'ı URL yükleme için metin ve mantıksal durum
   taşımaya devam ediyor ancak fiziksel olarak daima gizli; yalnız onaylı
   `EmptyStateOverlay` görünür ve erişilebilir ağaçta kalıyor. Regresyon önce
   fiziksel görünürlüğü **1 failed** ile ölçtü; boş ekran, URL yükleme ve başlık
   yaşam döngüsü grubu düzeltme sonrasında **66 passed** verdi
   (`EV-20260822-005`).
45. Değişiklik etkisine göre birleştirilmiş son paket **306 passed / 4 staged
   source artifact skip / 0 failed** verdi. Extractor **453** çevrilebilir metni
   güncel buldu; çeviri/devamlılık ek grubu **35 passed**, ledger JSON ve
   `git diff --check` temiz, staged alan boştu. Bu deterministic kanıttır;
   hosted CI, native smoke, build veya kurulu artifact kanıtı değildir
   (`EV-20260822-006`).
46. `6fb5e5d` için hosted CI run `32570125468`, **4728 passed / 30 skipped /
   40 failed** verdi. Kurulum, bağımlılık doğrulama, compile, çeviri ve
   whitespace adımları geçti; yalnız pytest kırmızıydı. Hataların 38'i yeni
   boş ekran davranışına rağmen medya yokken playback overlay bekleyen eski
   fixture'lardan, biri eski 48 px başlık beklentisinden, biri de dar Frame
   double'ında opsiyonel boş-ekran widget'ına doğrudan erişimden kaynaklandı.
   Otomatik tekrar yapılmadı (`EV-20260822-007`).
47. Playback-overlay testleri medya-var durumuna, varsayılan açılış testleri
   ise önce boş ekran sonra medya geçişine ayrıldı. Başlık sözleşmesi 32 px'e
   getirildi ve dar Frame double'ı için opsiyonel widget erişimi güvenli
   yapıldı. Etkilenen dokuz modül **214 passed / 0 failed** verdi; extractor
   **453** çevrilebilir metni ve yedi kataloğu güncel buldu
   (`EV-20260822-008`). Bu henüz yalnız uncommitted deterministic kanıttır.
48. Son dar kapıda devamlılık, boş-ekran bilgi penceresi ve başlık yaşam
   döngüsü **35 passed / 0 failed** verdi. Ledger JSON, `git diff --check`,
   çeviri güncelliği ve boş staged alan doğrulandı (`EV-20260822-009`).
49. Bu CI düzeltme paketi kullanıcı onayıyla tek commit'e alındı. Commit
   kimliği her oturumda canlı Git komutuyla doğrulanır; push henüz yapılmadı.
50. Düzeltme commit'i `05ee170` push edildi. Hosted CI run `32574293662` ilk
   denemede **4768 passed / 30 skipped / 0 failed** verdi; bağımlılık,
   compile, çeviri ve whitespace adımlarının tamamı geçti
   (`EV-20260822-010`). Bu hosted kanıttır; native oynatma, build veya kurulu
   artifact kanıtı değildir.
51. Hosted CI başarı kaydının belge paketi `e4f9114` olarak commit ve push
   edildi. Yalnız iki belge değişmesine rağmen run `32575563284` yine tüm
   bağımlılıkları kurup **4768 passed / 30 skipped / 0 failed** verdi
   (`EV-20260822-011`). Sonuç yeşildir ancak belge-only değişiklik için tam
   test maliyetinin gereksiz olduğunu somut olarak gösterir.
52. Mevcut `test` kontrol adı korunarak değişen dosya sınıflandırması eklendi.
   Yalnız `docs/` veya Markdown değişiklikleri altı tam sabitlenmiş küçük
   bağımlılıkla devamlılık, ledger JSON ve whitespace kapılarını çalıştırır;
   karışık, boş veya belirsiz aralıklar fail-safe tam CI'a gider. Regresyon
   önce **3 failed / 7 passed**, düzeltme sonrası birleşik dar kapı
   **17 passed / 0 failed** verdi (`EV-20260822-012`). GitHub workflow kabulü
   bu aşamada henüz yapılmamıştı.
53. Kısa CI workflow paketi `86f2a65` olarak commit ve push edildi. Run
   `32576426906` sınıflandırmayı başarıyla tamamladı; workflow/test dosyaları
   değiştiği için beklenen tam yolu seçti. Belge-only adımlar atlandı, tam
   bağımlılık ve test yolu **4771 passed / 30 skipped / 0 failed** verdi
   (`EV-20260822-013`). Workflow sözdizimi ve güvenli tam yol hosted olarak
   kabul edildi; kısa yol henüz gerçek belge-only push ile ölçülmedi.
54. Tam-yol hosted kabul kaydının iki belgeli paketi kullanıcı onayıyla yerel
   commit'e alındı. Commit kimliği her oturumda canlı Git komutuyla
   doğrulanır; bu belge-only commit henüz push edilmedi.
55. Belge-only commit `a58e73f` olarak push edildi. Run `32576705122`
   sınıflandırmayı doğru yaptı, tam bağımlılık ve 4771-test yolunu atladı,
   küçük bağımlılıkları yaklaşık sekiz saniyede kurdu; ancak belge pytest'i
   ürün `tests/conftest.py` dosyasını yüklediği için test toplamadan
   `python-mpv is missing` ile durdu (`EV-20260822-014`, **FAILED**).
   Otomatik tekrar yapılmadı; bu ürün çalışma zamanı hatası değildir.
56. Belge adımları `MLC_CI=0`, boş `PYTHONPATH` ve pytest `--noconftest` ile
   ürün/native başlangıcından ayrıldı. Koruma testi küçük kilide python-mpv,
   PyQt, PySide veya shiboken eklenmesini yasaklıyor. Workflow sözleşmesi
   **11 passed**, gerçek izole devamlılık komutu **7 passed** verdi
   (`EV-20260822-015`). Düzeltme henüz hosted olarak kabul edilmedi.
57. Kısa-yol izolasyon ve regresyon paketi kullanıcı onayıyla yerel commit'e
   alındı. Commit kimliği her oturumda canlı Git komutuyla doğrulanır; commit
   henüz push edilmedi.
58. İzolasyon paketi `f16cbbd` olarak commit ve push edildi. Run `32577216957`
   workflow/test değişiklikleri nedeniyle beklenen tam yolu seçti ve
   **4772 passed / 30 skipped / 0 failed** verdi (`EV-20260822-016`). Düzeltme
   GitHub'da kabul edildi; yalnız düzeltilmiş kısa yolun bir belge-only push
   ile son kabulü kaldı.
59. Tam-yol hosted kabul kaydının iki belgeli paketi kullanıcı onayıyla yerel
   commit'e alındı. Commit kimliği her oturumda canlı Git komutuyla
   doğrulanır; bu son belge-only tetik henüz push edilmedi.
60. Belge-only commit `770101f` olarak push edildi. Run `32577815302` kısa
   yolu seçti; yedi devamlılık testi `0.19` saniyede geçti ve tam bağımlılık /
   ürün-test yolu atlandı. İş akışı toplamda yaklaşık 25 saniyede başarıyla
   bitti; bu final meta-test için döngü oluşturan yeni kayıt commit'i
   yapılmadı.
61. v0.39 sürüm kaynakları yerelde birlikte yükseltildi ve hedef sürüm grubu
   **383 passed** verdi; ancak ilk release ön-kontrolü yerel `mpv-2.dll` ile
   `yt-dlp.exe` manifestten farklı olduğu için doğru biçimde durdu. Sonuç
   `EV-20260822-017` olarak FAILED kaydedildi ve neden incelenmeden tekrar
   yapılmadı.
62. Kullanıcı onayıyla yalnız iki runtime girdisi doğrulanmış kaynaklardan
   yedekli olarak geri alındı. `mpv-2.dll` `112.772.608` bayt / `de80329f...`,
   `yt-dlp.exe` `17.840.399` bayt / `66674953...`; yt-dlp `2026.08.19`
   döndürdü ve release ön-kontrolü geçti. Dar son grup **285 passed / 4 staged
   source skip / 0 failed** verdi (`EV-20260822-018`). Bu yerel deterministic
   kanıttır; build veya yayın değildir.
63. İlk zorunlu devamlılık koşumu **6 passed / 1 failed** verdi. Tek hata,
   sıradaki adım metninin eski oturumlardan otomatik commit talimatı taşınmasını
   önleyen ifade sözleşmesine aykırı olmasıydı. Ürün veya runtime hatası
   değildir; sonuç `EV-20260822-019` olarak kaydedildi ve assertion
   incelenmeden tekrar yapılmadı.
64. İfade nedeni düzeltildikten sonra zorunlu devamlılık testi **7 passed / 0
   failed** verdi (`EV-20260822-020`). Güncel devir noktası hiçbir commit,
   build, push, tag veya release işlemini otomatik başlatmıyor.
65. v0.39 hazırlık commit'i `a2d87a6` push edildi. Hosted run `32578719607`
   tam yolu seçti; kilitli bağımlılıklar, ortam doğrulaması, compile, çeviri
   ve whitespace adımları geçti. Test sonucu **4772 passed / 30 skipped / 0
   failed** oldu (`EV-20260822-021`). Bağımlılık kurulumu başlamadan önce
   `sitecustomize` kaynaklı `python-mpv is missing` mesajı çıktı; pip devam
   etti, sonraki kilitli-ortam kapısı ve bütün testler geçti. Bu nedenle sonuç
   yeşildir; mesaj ayrıca temizlenmesi gereken, engelleyici olmayan CI log
   gürültüsüdür.
66. Temiz ve origin ile eşit `7a5f70d` üzerinde ayrı onayla v0.39 aday build'i
   başlatıldı. Bağımlılık kapısı yerel Pillow `12.2.0`, pytest `9.0.2` ve
   setuptools `82.0.1` sürümlerini kilitli `12.3.0`, `9.0.3`, `83.0.0`
   değerlerinden eski bulduğu için zincir çıktı silmeden/üretmeden durdu
   (`EV-20260822-022`, **FAILED**). Otomatik tekrar veya paket kurulumu
   yapılmadı; `installer_output` içindeki eski v0.37 dosyaları korundu.
67. Ayrı kurulum onayıyla yalnız Pillow `12.3.0`, pytest `9.0.3` ve setuptools
   `83.0.0` yüklendi; bütün `requirements-lock.txt` kapısı geçti. Ayrı build
   tekrarı onayıyla temiz ve origin ile eşit `b796040` üzerinde zincir tek kez
   çalıştı ve **DONE** verdi. Ana v0.39 installer `56.329.783` bayt / SHA-256
   `00ed3e...4915`; add-on `48.896.196` bayt / SHA-256 `07f691...a491`.
   İkisi de `0.39.0.0`; iki 88 baytlık Ed25519 imzası bağımsız doğrulandı ve
   post/final kapıları exit 0 verdi (`EV-20260822-023`). Bu source-build
   kanıtıdır; kurulum, tag veya release kanıtı değildir.
68. Exact v0.39 ana/add-on installer'ları görünür ve sessiz yollarda; gerçek
   v0.38 yükseltmesi, açık Player'da fail-closed kaldırma, Player/Deno Restart
   Manager yükseltmesi ve iki kaldırma sırasında sınandı. Ana açık-Player
   kaldırması `exit 1` verdi ve 144 dosya / 314.635.287 baytlık ağaç özeti
   değişmedi. İki kaldırma sırası da exit 0 / klasör-kayıt-süreç artığı 0 ile
   bitti; `MLCPlayer.ini` hash/zamanı değişmedi. Kullanıcı görünür yükseltme
   sonrası uygulamanın sorunsuz açıldığını doğruladı. Ancak aktif yt-dlp
   hazırlığı güvenlik politikası tarafından başlamadan engellendi; başka
   klasörde aynı adlı süreç, asılı Player ve bozuk InstallLocation fault
   senaryoları çalıştırılmadı. Sonuç `EV-20260822-024` olarak **BLOCKED**;
   sistemde v0.39 kurulu değildir ve AppData korunur.
69. Ayrı fault-injection onayıyla eksik kapılar exact artifact'larda
   tamamlandı. Geçici klasördeki aynı adlı dış süreç ana yükseltmeden sağ
   çıktı. Boş/relative/root/UNC/stale/wrong-product InstallLocation durumları
   dosya yazmadan reddedildi ve kayıtlar `finally` ile geri yüklendi. Asılı
   Player'da ana installer `exit 7`, 137 dosya / 194.656.960 baytlık ağaç
   özeti değişmeden kaldı; Player uyandırılıp normal `exit 0` ile kapandı.
   Normal çalışan, ağsız stdin bekleyen yt-dlp'de add-on installer güvenli
   rollback/`exit 5` yaptı ve hash değişmedi; süreç kapatılınca aynı yükseltme
   `exit 0` verdi. Cleanup iki kaldırıcıda exit 0; final klasör/kayıt/süreç 0,
   INI hash/zamanı aynı (`EV-20260822-025`, **PASS**). Yalnız testte kullanılan
   344.064 baytlık dış-süreç kopyası `%TEMP%` altında kaldı; silme komutu
   politika tarafından reddedildi, repo/ürün/AppData veya release içeriği
   değildir.
70. `e9da1fb` temiz ve origin ile eşit durumdayken ayrı indirme onayıyla
   `packaging/fetch_sources.py` çalıştı. Sözleşmedeki **83/83** kaynak arşivi
   toplam **914.482.463 bayt** olarak indirildi ve yerleşik boyut/SHA-256
   doğrulamasından geçti. Ayrı ağsız döngü `BAD_COUNT=0`; kaynak aynası,
   libmpv/cryptography/yt-dlp staging, prepublish ve artifact seçim grubu
   **94 passed / 0 failed** verdi (`EV-20260822-026`). Libmpv veya ürün build'i
   tekrarlanmadı; tag/release oluşturulmadı.
71. `551a685` için GitHub belge CI run `32593979351` **7 passed / 0 failed**
   verdi; tam ürün yolu belge-only değişiklik nedeniyle bilinçli atlandı. Ayrı
   tag onayıyla yerel annotated `v0.39` tag nesnesi oluşturuldu; peel sonucu
   `551a685` HEAD ile aynıydı. Ağsız `prepublish.py --tag v0.39` exit 0 verdi:
   sürüm/tag eşliği, temiz ağaç, iki kriptografik installer imzası ve **87/87**
   yayın varlığı geçti (`EV-20260822-027`). Uzak tag/release hâlâ yoktur.
72. Ayrı tag-push onayıyla yalnız `v0.39` tag'i origin'e gönderildi. Uzak tag
   nesnesi `36ba120c`; zorunlu `refs/tags/v0.39^{}` sorgusu tam
   `551a685a68ffc171e0340780a371d0b99edda540` döndürdü ve yerel HEAD/kabul
   edilmiş build commit'iyle birebir eşleşti (`EV-20260822-028`). Dal commit'i,
   draft veya canlı release gönderilmedi.
73. Ayrı taslak-release onayıyla `--verify-tag --draft` kullanılarak v0.39
   taslağı oluşturuldu. Yerel **87** benzersiz varlık toplam
   **1.019.708.618 bayt** idi. GitHub taslağı `isDraft=true`,
   `isPrerelease=false`, **87** uploaded varlık ve aynı toplam bayt değerini
   verdi; her uzak varlık yerel dosyayla ad/boyut/SHA-256 olarak karşılaştırıldı,
   `MISMATCH_COUNT=0` (`EV-20260822-029`). Canlı yayın yapılmadı.
74. EV-027..029 kanıt commit'i `750e770` origin/master'a push edildi. GitHub
   run `32594538584` belge-only yolu seçerek **7 passed / 0 failed** verdi;
   tam ürün paketi doğru biçimde atlandı (`EV-20260822-030`). Uzak v0.39
   release hâlâ `isDraft=true`, `isPrerelease=false` ve 87 varlıklıdır.
75. Ayrı canlı-yayın onayıyla doğrulanmış v0.39 taslağı `--draft=false
   --latest` ile yayımlandı. İlk salt-okunur public kontrol betiği kaynakta
   olmayan `is_allowed_final_download_url` adını çağırdığı için hata verdi;
   ürün/release değişmedi, kaynak incelenmeden tekrar yapılmadı
   (`EV-20260822-031`, **failed harness**). Doğru
   `is_allowed_download_host` ile çalıştırılan kontrol ürünün gerçek
   `fetch_latest_release` ve `select_update_asset` yolunda `latest=v0.39`, 87
   varlık ve doğru ana installer seçimini verdi. Ana/isteğe bağlı installer
   metadata boyut+SHA-256 değerleri exact kabul artifact'larıyla aynı, iki
   signature GET ve Ed25519 doğrulaması PASS, iki installer HEAD/redirect/izinli
   host/Content-Length kontrolü PASS (`EV-20260822-032`).
76. Kullanıcı, yönlendirildiği public v0.39 GitHub release sayfasından ana
   sürümü indirip kurduğunu, uygulamanın açıldığını ve gerçek medya oynattığını;
   kabul sırasında hiçbir sorun görmediğini bildirdi (`EV-20260822-033`). Exact
   public ana artifact kimliği **MLCPlayer_Setup_v0.39.exe / 56.329.783 bayt /
   SHA-256 00ed3ef67da44adf1f4d997426636ba7642413098c66bf08fade54dd44584915**;
   kullanıcının indirdiği dosya ayrıca yeniden hash'lenmedi.
77. Engelleyici olmayan erken `python-mpv is missing` CI mesajının nedeni,
   `MLC_CI=1` ve `PYTHONPATH=scripts` değişkenlerinin kilitli bağımlılık
   kurulumundan önce job genelinde etkin olmasıydı. İki değişken yalnız
   `Run CI-safe test suite` adımına taşındı; pip/verify/compile/çeviri mpv test
   kancasını görmüyor, pytest ve çocukları aynı stub sözleşmesini koruyor.
   Workflow + stub dar grubu **15 passed / 0 failed** verdi
   (`EV-20260822-034`). Gerçek GitHub log kabulü push sonrasını bekliyor.
78. Düzeltme `ae02819` ile push edildi. Tam hosted run `32595637824`; kilitli
   kurulum, ortam doğrulama, compile, çeviri ve whitespace adımlarını geçti,
   **4772 passed / 30 skipped / 0 failed** verdi ve 2 dakika 57 saniyede bitti.
   Tam logda eski `python-mpv is missing from the locked CI environment` metni
   **0 kez** bulundu (`EV-20260822-035`).
79. Salt-okunur GitHub denetiminde public reponun varsayılan `master` dalı için
   branch protection sorgusu `404 Branch not protected`, repository rulesets
   sorgusu boş liste verdi. Hesap admin yetkili; son başarılı tam run'ın doğru
   required-check kimliği GitHub Actions uygulamasından **`test`** adıdır
   (`EV-20260822-036`). Hiçbir GitHub ayarı değiştirilmedi.
80. Ayrı GitHub-ayar onayıyla temel `master` protection uygulandı. Canlı
   read-back: `protected=true`, `enforce_admins=true`,
   `allow_force_pushes=false`, `allow_deletions=false`. Required status check,
   PR review ve actor restriction yok; linear history, branch lock ve creation
   block kapalıdır (`EV-20260822-037`). Böylece admin dahil geçmişi bozma/silme
   engellendi; normal doğrudan push sözleşmesi kural tarafından kapatılmadı.
81. Koruma açıkken ordinary `git push origin master`, `583605c` belge
   commit'ini force/bypass olmadan kabul etti; fetch sonrası yerel/uzak eşit,
   koruma ayarları aynı kaldı. Kısa hosted run `32598954194` **7 passed / 0
   failed** verdi (`EV-20260822-038`). Böylece doğrudan normal push yolunun
   bozulmadığı davranışsal olarak kanıtlandı.
82. PR + zorunlu `test` hazırlığı yerel `codex/pr-gate-workflow` dalına alındı.
   Yeni tek kaynak `docs/CHANGE_WORKFLOW.md`; agent onay sınırları, merge-commit
   kimliği, release merge-commit eşliği, iki README bağlantısı ve yedi dar
   sözleşme testi eklendi. İlk hedef koşum satır sonuna duyarlı yeni assertion
   yüzünden **1 failed / 217 passed** verdi (`EV-20260822-039`); neden
   incelendikten sonra assertion whitespace-normalized yapıldı. Aynı grup
   **218 passed / 0 failed**, diff-check temiz verdi (`EV-20260822-040`).
83. Dal commit'i `98ae1a9` push edildi ve PR #1 açıldı. Aynı commit için dal
   push run `32599545727` **4780 passed / 30 skipped / 0 failed**, bağımsız PR
   run `32599574281` **4780 passed / 30 skipped / 0 failed** verdi. İki run
   tekrar değildir; farklı `push` ve `pull_request` olaylarıdır.
84. İlk katı protection isteği kişisel repoda organizasyona özel boş actor
   restriction alanları taşıdığı için HTTP 422 ile değişiklik yapmadan
   reddedildi (`EV-20260822-041`). Neden incelendikten sonra yalnız bu alanlar
   çıkarıldı. Canlı read-back artık PR zorunluluğu, approval `0`, GitHub Actions
   `test` (`app_id=15368`) ve `strict=true` gösteriyor; admin zorlaması açık,
   force-push ve silme kapalıdır.
85. PR #1 yeni kural altında `CLEAN` / `MERGEABLE` kaldı ve ayrı merge onayıyla
   merge-commit yöntemiyle birleştirildi. Uzak ve yerel `master` temiz/eşit
   `4d71f8132fb46d9f5f969f8efe292da898111894` commit'indedir; koruma geri
   okumada etkin kalmıştır (`EV-20260822-042`).
86. Kabul kaydı `ed9bd90` commit'iyle görev dalına push edildi; PR #2'nin dal
   push ve PR testleri geçti. Ayrı onayla merge commit `b547b9f` üzerinden
   `master`a alındı; yerel/uzak master temiz ve eşit, canlı PR + `test`
   koruması etkin kaldı.
87. Canlı run geçmişi ilk iki korumalı değişikliğin her birinde dal push'u, PR
   ve master merge'i için üç CI çalıştırdığını gösterdi. Yeni sözleşme testi
   eski tetikleyicide **2 failed / 9 passed** verdi (`EV-20260822-043`). Neden
   incelendikten sonra otomatik `push` kaldırıldı; otomatik yalnız
   `pull_request`, sürüm adayı/ortak CI teşhisi için elle `workflow_dispatch`
   bırakıldı. CI, PR ve release belge sözleşmeleri **223 passed / 0 failed**
   verdi (`EV-20260822-044`). Bu henüz hosted kabul değildir.
88. Değişiklik `6e293ef` olarak görev dalına push edildi; dal push'unda run
   oluşmadı. PR #3 exact aynı head için yalnız bir `pull_request` run'ı
   (`32601141966`) oluşturdu ve **4781 passed / 30 skipped / 0 failed** verdi.
   Ayrı onayla merge commit `b56df3f` üzerinden master'a alındı; merge
   commitinde ikinci push run'ı oluşmadı. Yerel/uzak master temiz/eşit ve canlı
   PR koruması etkin kaldı (`EV-20260822-045`). Tek otomatik CI hedefi hosted
   ortamda geçti.
89. Tek-CI kabul kaydı PR #4 ile merge commit `bb6da34` üzerinden master'a
   alındı. Ardından bağımlılık denetiminde 24 exact Python kilidi GitHub
   reviewed advisory veritabanında **0 eşleşme** verdi; mevcut bağımlılık
   regresyonu **9 passed / 0 failed** tamamlandı. Canlı GitHub'da Dependabot
   alerts kapalıydı. Ayrı ayar onayıyla vulnerability-alerts etkinleştirildi;
   PUT ve GET **HTTP 204**, dependency graph SBOM **30 paket**, açık alert
   listesi **0** verdi. Otomatik security-update PR'ları kapalı, secret scanning
   ve push protection açık kaldı (`EV-20260822-046`).
90. Ücretsiz SignPath Foundation yolu güncel `origin/master` tabanından ayrı
   temiz worktree'de incelendi. GPL-3.0, canlı sürüm, dokümantasyon ve açık
   kaynak bağımlılıklar başvuruyu makul kılıyor; fakat MFA durumu kaynakta
   kanıtlanamaz ve SignPath'in istediği GitHub-hosted doğrulanabilir unsigned
   installer build'i henüz yoktur. Gerçeği abartmayan `CODE_SIGNING_POLICY.md`,
   `PRIVACY.md` ve `docs/SIGNPATH_READINESS.md` hazırlandı. Sözleşme önce
   **4 failed**, uygulama sonrasında **4 passed**; ilgili belge paketi CI
   ortamında **540 passed / 0 failed** verdi (`EV-20260823-001`). Başvuru,
   hesap, sertifika, build veya yayın yapılmadı.
91. Kullanıcı GitHub MFA'nın açık olduğunu doğruladı; bu yalnız kullanıcı
   beyanıdır, kaynak kanıtı değildir. Geçici Actions artifact'indeki exact
   doğrulanmış libmpv DLL'ini tekrar iki saatlik build yapmadan proje GHCR
   alanına bir kez taşıyacak manuel workflow hazırlandı. Workflow kaynak run,
   commit, artifact son kullanma zamanı, arşiv ve DLL boyut/hash değerlerini
   zorunlu tutuyor; mevcut etiketi ezmiyor ve digest ile geri indirip bayt
   karşılaştırıyor. İş akışı henüz çalıştırılmadı; GHCR, build, SignPath ve
   yayın durumu değişmedi (`EV-20260823-002`).
92. Runtime mirror hazırlığı `32bda63` commit'iyle görev dalına push edildi;
   dal push'unda test oluşmadı. PR #7 exact aynı head için yalnız
   `pull_request` run `32604056103` oluşturdu ve **4791 passed / 30 skipped /
   0 failed** verdi. PR `CLEAN / MERGEABLE` durumundayken ayrı onayla gerçek
   iki ebeveynli merge commit `e9b5a96` üzerinden master'a alındı. Merge
   commitinde ikinci push run'ı oluşmadı. Workflow GitHub tarafından başarıyla
   ayrıştırıldı fakat manuel runtime mirror job'u henüz dispatch edilmedi;
   GHCR durumu değişmedi (`EV-20260823-003`).
93. Ayrı açık onayla exact master `81f881f` üzerindeki manuel runtime mirror
   workflow'u bir kez çalıştırıldı. Run `32620779433` tüm adımları **PASS**
   tamamladı; kaynak artifact/run/commit, arşiv ve DLL kimliği doğrulandı,
   push sonrası digest ile geri indirilip dört dosya bayt bayt karşılaştırıldı.
   Kalıcı OCI manifest digest'i `sha256:f33b793c...10518`; DLL katmanı
   `112.772.608` bayt ve `sha256:de80329f...f684f4e`. Anonim GHCR readback
   HTTP 200 ile aynı manifest, artifact type, dört katman ve DLL kimliğini
   doğruladı. Exact kilit `packaging/libmpv_runtime_lock.json` içinde kayda
   hazırlandı (`EV-20260823-004`). libmpv yeniden build edilmedi; SignPath,
   installer, tag veya release çalıştırılmadı.
94. Güncel master `a0f3a93` tabanında hosted imzasız ana installer sınırı
   hazırlandı. Manuel workflow yalnız GitHub-hosted Windows 2025 kullanıyor;
   action/Python/ORAS sabit, Inno Setup `6.7.1` fail-closed ve 24 Windows wheel
   exact SHA-256 kilitlidir. Runtime yalnız kalıcı OCI digest'iyle çekiliyor;
   main-only `--pre-main` yolu add-on ikililerini istemeden exact mpv hash'ini
   doğruluyor. Çıktı `NotSigned` olmak ve `.sig` taşımamak zorunda; installer
   ile provenance ayrı artifact olarak saklanıyor. Sözleşme önce **6 failed**,
   uygulama sonrası test-only kapsam hatası düzeltilince **6 passed** verdi.
   Etki grubu doğrulanmış DLL test PATH'iyle **88 passed / 1 skipped**;
   main-pre grubu **24 passed / 1 skipped** ve hash kilidi gerçek pip seçimiyle
   **24/24 wheel PASS** verdi (`EV-20260823-005`). Workflow/build/SignPath/tag/
   release çalıştırılmadı.
95. Ayrı açık onayla exact master `555b936` üzerinde ilk hosted unsigned-main
   koşumu `32624655897` başlatıldı. Python 3.13.15 ve ORAS adımları geçti;
   `ISCC.exe` bulundu ancak Windows dosya metadata'sı `0.0.0.0` döndürdüğü
   için araç zinciri kapısı 26 saniyede durdu. Bağımlılık kurulumu, OCI çekimi,
   build ve artifact yükleme adımlarının tamamı atlandı; otomatik tekrar
   yapılmadı (`EV-20260823-006`, **FAILED**).
96. Resmî Inno Setup `is-6_7_1` kaynağındaki davranışa göre yalnız sürüm probu
   düzeltildi. Workflow geçici ve çıktı üretmeyen minimal script ile gerçek
   compiler engine'i çalıştırıyor, motorun bildirdiği tam `6.7.1` değerini
   zorunlu tutuyor ve geçici dosyayı `finally` içinde siliyor. Regresyon eski
   yöntemi önce kırmızı yakaladı; dar sözleşme düzeltme sonrası **7 passed / 0
   failed** verdi (`EV-20260823-007`). Bu deterministic kanıttır; hosted
   düzeltme kabulü veya installer build PASS'i değildir.
97. Düzeltme `6f62ceb` olarak görev dalına push edildi; dal push'unda test
   oluşmadı. PR #11 exact aynı head için yalnız `pull_request` run
   `32625238272` oluşturdu ve **4802 passed / 30 skipped / 0 failed** verdi.
   Ayrı onayla iki ebeveynli merge commit `ffa8466` üzerinden master'a alındı;
   merge commitinde ikinci push run'ı oluşmadı (`EV-20260823-008`). Bu hosted
   CI kabulüdür; manuel unsigned-installer workflow'u henüz tekrar
   çalıştırılmadı ve artifact yoktur.
98. Kabul kaydı PR #12 ile iki ebeveynli merge commit `dffb91c` üzerinden
   master'a alındı. Ayrı açık onayla exact bu master üzerinde unsigned-main
   run `32632912597` başlatıldı. Düzeltilmiş Inno `6.7.1` motor probu ve 24 exact
   wheel kapısı geçti; immutable OCI manifesti ile doğru libmpv DLL'i indi.
   Kaynak/provenance kimliği de geçtikten sonra yalnız checkout'taki
   `RUNTIME_MANIFEST.txt` baytları OCI kopyasıyla uyuşmadı. Build ve artifact
   adımları atlandı; otomatik tekrar yapılmadı (`EV-20260823-009`, **FAILED**).
99. Anonim GHCR ve exact Git blob readback'i iki kanonik manifestin **2402
   bayt / SHA-256 `f76e62...b578`** olarak aynı olduğunu; başarısız committe bu
   dosyanın EOL kuralı olmadığını gösterdi. Regresyon eski durumda **1 failed /
   7 passed** verdi. Yalnız `bin/RUNTIME_MANIFEST.txt text eol=lf` kuralı
   eklendi; `git check-attr` LF'i doğruladı ve grup **8 passed / 0 failed**
   verdi (`EV-20260823-010`). Bu deterministic kanıttır; hosted build PASS'i
   veya installer artifact'i değildir.
100. LF düzeltmesi PR #13 run `32633527175` üzerinde **4803 passed / 30
   skipped / 0 failed** verdi ve iki ebeveynli merge commit `1f01633` ile
   master'a alındı. Ayrı açık onayla exact bu committe unsigned-main run
   `32634062651` çalıştı; bütün adımlar geçti. Installer
   `MLCPlayer_Setup_v0.39.exe`, **57.255.931 bayt**, SHA-256
   `cab8c89b...36066`, Authenticode `NotSigned`; provenance aynı commit/run,
   Python `3.13.15`, Inno `6.7.1`, wheel/runtime ve installer kimliklerini
   doğruluyor. İki Actions artifact arşivi bağımsız indirmede API boyut ve
   digest değerleriyle birebir eşleşti (`EV-20260823-011`). Bu hosted unsigned
   build kanıtıdır; kurulum, native smoke, imza veya yayın değildir.
101. SignPath Foundation için halka açık başvuru taslağı exact hosted build,
   proje, lisans, roller, politika ve ilk imza kapsamını doğru biçimde bir
   araya getiriyor. Aktif workflow'a SignPath action/token eklenmedi; isteğe
   bağlı İnternet Video eklentisi kapsam dışında kaldı. Sözleşme önce **2
   failed / 3 passed**, belge uygulaması sonrasında test yolu hatası nedeniyle
   **1 failed / 4 passed**, beklenti düzeltildikten sonra **5 passed / 0
   failed** verdi. Son etki grubu **222 passed / 0 failed** ve ledger JSON
   kontrolü geçti (`EV-20260823-012`). Paket **gönderilmedi**; hesap,
   sertifika, imza, build, tag veya release oluşturulmadı.
102. Başvuru paketi commit'i `f25a687` exact head olarak PR #15 run
   `32636105104` üzerinde **4804 passed / 30 skipped / 0 failed** verdi. PR
   yeşil ve mergeable iken ayrı onayla iki ebeveynli merge commit `5929267`
   üzerinden master'a alındı; merge commitinde ikinci push run'ı oluşmadı
   (`EV-20260823-013`). Bu hosted CI kabulüdür; gerçek başvuru, hesap,
   GitHub App, sertifika, imza, build, tag veya release değildir.
103. Kabul kaydı PR #16 belge CI'sında **7 passed / 0 failed** verdi ve iki
   ebeveynli `e5390da` merge commit'iyle master'a alındı. Ayrı açık onaylarla
   resmî SignPath formuna yalnız doğrulanmış kamu bilgileri ve özel iletişim
   alanları girildi; pazarlama onayı kapalı kaldı. İlk CAPTCHA zaman aşımı
   başarı üretmedi; neden incelendikten sonra tek kontrollü yeniden tetikleme
   yapıldı ve sayfa **Form submitted / Thank you, we'll be in touch soon**
   mesajını gösterdi (`EV-20260823-014`). Bu yalnız external_submission
   kanıtıdır; kabul, hesap, GitHub App, sertifika veya imza değildir. Yeni
   teslim-durumu sözleşmesi önce **4 failed / 8 passed**, uygulama sonrasında
   test satır-bölme beklentisiyle **2 failed / 10 passed**, düzeltme sonrası
   **12 passed / 0 failed** verdi; son etki grubu **222 passed / 0 failed**
   tamamlandı.
104. Mimari karmaşıklık ve gerçek Windows davranış boşluğu için kalıcı kalite
   programı oluşturuldu. `QUALITY_EVOLUTION_PLAN.md` fazları ve tek-kaynak
   güncellik işlemini; `ARCHITECTURE_INVENTORY.md` altı büyük modülün ölçüm
   tabanını; `WINDOWS_ACCEPTANCE_MATRIX.md` exact commit/runtime/artifact'a
   bağlı P0/P1/P2 senaryolarını tanımlar. Sözleşme önce belgeler yokken **4
   failed**, uygulama sonrasında yalnız testin büyük-küçük harf duyarlılığıyla
   **1 passed / 3 failed**, beklenti düzeltildikten sonra **4 passed / 0
   failed** verdi. Yeni plan sözleşmesi ile continuity grubu son kontrolde
   **11 passed / 0 failed** tamamlandı (`EV-20260823-015`). Ürün kodu, build,
   kurulum ve native koşum değişmedi.
105. Altı büyük modülün satır/yapı/state, owner bağımlılığı, yaşam döngüsü,
   test yüzeyi ve geçmiş kusur riski salt okunur ölçüldü. En yüksek risk
   `video_frame.py` ve `player.py` olsa da ilk düşük-riskli aday, MPV/Qt state'i
   taşımayan `app/media_targets.py` yaprağı olarak seçildi. Kaynağın sessizce
   eskimesini önlemek için altı dosyanın normalize SHA-256 ve yapı sayıları
   `ARCHITECTURE_INVENTORY.json` ile fail-closed sözleşmeye bağlandı. İnsan
   envanteri öncesi test **1 failed / 3 passed**, uygulama sonrası **4 passed**;
   makine envanteri kapısı önce dosya yokken **2 failed / 3 passed**, uygulama
   sonrası **5 passed / 0 failed** verdi. Kalite ve continuity son grubu **12
   passed / 0 failed** tamamlandı (`EV-20260823-016`). Ürün kodu, native
   davranış, build ve kurulum değişmedi.
106. Sekiz P0 Windows senaryosu mevcut deterministik sınır, native runner,
   exact girdi ve açık kanıt boşluğuyla eşlendi. Kapanış, gerçek video
   ilerlemesi, pause/seek, native resize ve tam ekran için yeniden
   kullanılabilir yollar bulundu. Gerçek ses/altyazı parçası değiştirme,
   Explorer video/altyazı bırakma, playlist son sınıra fiziksel taşıma ve
   ikinci örnek dosya/URL IPC için tam fail-closed kabul bulunmadığı açıkça
   kaydedildi. Eşleme regresyonu önce **1 failed / 5 passed**, belge
   tamamlandıktan sonra **6 passed / 0 failed** verdi
   (`EV-20260823-017`). Sekiz satır da `NOT_RUN`; ürün kodu ve gerçek native
   davranış değişmedi.
107. Kalite programı PR #18'in exact head'i `c9e2458` üzerinde zorunlu hosted
   test **4811 passed / 30 skipped / 0 failed** verdi; koşum 2 dakika 59
   saniyede ilk denemede tamamlandı. PR merge öncesi `MERGEABLE/CLEAN` ve
   zorunlu `test` check'i `COMPLETED/SUCCESS` olarak geri okundu. Ayrı onayla
   iki ebeveynli `7e93ed8` merge commit'i origin/master'a alındı
   (`EV-20260823-018`). Kabul kaydı PR #19'da belge kapısı **7 passed / 0
   failed** verdikten sonra iki ebeveynli `69af424` merge commit'iyle
   master'a alındı. Bu hosted kanıt tek başına P0 satırlarını PASS yapmadı.
108. Exact `69af424` kaynak commit'i, manifestle eş `112772608` baytlık
   `mpv-2.dll` ve gerçek MP4 ile özel kapanış kapısı ilk koşumda exit 0 /
   **1 passed in 2.62s** verdi. Medya ve DLL SHA-256 değerleri koşum öncesi/
   sonrası aynı, süreç sızıntısı sıfırdı; `WIN-P0-01` **PASSED** oldu
   (`EV-20260823-019`). Bu kurulu v0.39 artifact kanıtı değildir.
109. Aynı exact girdilerle tek videolu overlay senaryosu duration `5071.726`
   ve position `4.6` üretti; `RESULTS`, `MARK_DONE`, boş behavior failure ve
   sıfır child sızıntısı vardı. Ancak eski child, ürünün güvenli kapanışından
   önce MPV'yi elle sonlandırdığı için üç geç UI timer hatasından sonra
   `0xC0000005` döndürdü. Fail-closed runner exit 1 verdi; `WIN-P0-02`
   **FAILED** kaldı ve otomatik tekrar yapılmadı (`EV-20260823-020`). Kaynak
   incelemesi ürün oynatma yolundan değil harness teardown sırasından başlayan
   nedeni gösterdi; henüz düzeltme uygulanmadı.
110. Native sonuç kaydı PR #20'de zorunlu hosted test **4811 passed / 30
   skipped / 0 failed** verdikten sonra iki ebeveynli `2d4e4c3` merge
   commit'iyle master'a alındı. Overlay child kapanış kusuru regresyon-first
   ele alındı: yeni test önce **1 failed**, child'ın doğrudan MPV
   stop/terminate çağrıları kaldırılıp kanonik `player.close()` yoluna
   geçirildikten sonra **1 passed** verdi. İlgili deterministik etki grubu
   **102 passed / 2 skipped / 0 failed** tamamlandı (`EV-20260823-021`). Ürün
   kodu değişmedi ve native retry yapılmadı; `WIN-P0-02` hâlâ **FAILED**.
111. Test-only kapanış düzeltmesi PR #21'de hosted **4812 passed / 30 skipped
   / 0 failed** verdikten sonra iki ebeveynli `98f4440` merge commit'iyle
   master'a alındı. Ayrı onaylı tek native retry aynı medya/runtime ile gerçek
   duration `5071.726`, position `4.633`, tam `RESULTS` ve `MARK_DONE` üretti;
   önceki üç geç UI timer hatası tamamen kayboldu. Buna rağmen child
   `MARK_DONE` sonrasında normal Python/libmpv finalizasyonunda yine
   `0xC0000005` döndürdü; fail-closed sonuç **FAILED** ve otomatik ek retry
   yapılmadı (`EV-20260823-022`). Kalan neden ürünün kanonik kapanışından
   sonra yalnız child'ın `raise SystemExit` yolunda; `main.py` ve güvenli
   native child'lar bu bilinen Windows/libmpv sınırında flush + `os._exit`
   kullanıyor.
112. Overlay child finalizasyon sözleşmesi regresyon-first düzeltildi. Yeni
   hedef test önce `os._exit(exit_code)` bulunmadığı için **1 failed**, sonra
   child focus sürecini temizleyip stdout/stderr akışlarını boşalttıktan sonra
   normal Python/libmpv finalizasyonuna girmeden sert çıkış kullanınca **1
   passed** verdi. İlgili deterministik etki grubu **103 passed / 2 skipped /
   0 failed** tamamlandı (`EV-20260823-023`). Ürün kodu ve native durum
   değişmedi; `WIN-P0-02` hâlâ **FAILED** ve otomatik retry yapılmadı.
113. PR #23 zorunlu `test` kontrolü başarıyla tamamlandı ve düzeltme iki
   ebeveynli `9ef4935` merge commit'iyle master'a alındı. Ayrı onaylı tek
   native retry aynı MP4 ve DLL parmak izleriyle gerçek duration `5071.726`,
   position `4.633`, tam `RESULTS` ve `MARK_DONE` üretti; child exit `0`,
   matrix exit `0`, davranış hatası/süreç sızıntısı yoktu. Koşum sonrası
   hash'ler aynı ve ağaç temiz kaldı (`EV-20260823-024`). `WIN-P0-02` artık
   **PASSED**; bu yalnız exact kaynak commit/runtime/medya/Windows senaryosuna
   ait native_smoke kanıtıdır.
114. EV-20260823-024 kayıt paketi PR #24'ün exact `bd14c98` head'inde zorunlu
   `test` kontrolünden **4813 passed / 30 skipped / 0 failed** ile geçti. PR
   `CLEAN/MERGEABLE` durumundayken ayrı onayla iki ebeveynli `36f418e` merge
   commit'i üzerinden master'a alındı (`EV-20260824-001`). Bu hosted kanıt
   fiziksel Windows davranışını PASS yapmaz.
115. Ayrı onaylı fiziksel `buttons,timeline,window_resize,fullscreen` paketi
   exact `36f418e`, aynı özel MP4 ve aynı DLL ile başlatıldı. `buttons` child'ı
   altı PASS satırı yanında `cc_on[closed]` için bir FAIL üretti; ardından
   oynatma-listesi sonu modalı kendiliğinden kapanmadı ve grup 600 saniyelik
   timeout içinde bekledi. Kullanıcı bu aşırı beklemeyi durdurdu; modal elle
   onaylanmadı, exact runner/child süreçleri doğrulanıp sonlandırıldı ve artık
   süreç kalmadı. `MARK_DONE`/özet oluşmadı; `timeline`, `window_resize` ve
   `fullscreen` başlamadı. Medya/DLL hash'leri ve temiz kaynak durumu korundu
   (`EV-20260824-002`, **FAILED**). Otomatik tekrar yapılmadı; `WIN-P0-04` ve
   `WIN-P0-05` hâlâ `NOT_RUN`.
116. Başarısız fiziksel sonuç kaydı PR #25'in exact `12a5570` head'inde
   zorunlu `test` kontrolünden **4813 passed / 30 skipped / 0 failed** ile
   geçti. PR `CLEAN/MERGEABLE` durumundayken ayrı onayla iki ebeveynli
   `947a4ce` merge commit'i üzerinden master'a alındı (`EV-20260824-003`).
   Bu hosted kanıt fiziksel sonucu yükseltmez.
117. Fiziksel harness regresyon-first düzeltildi. İlk yeni kapı saf sözleşme
   modülü yokken bir koleksiyon hatası, ikinci kapı kalan timeout sabitleri
   yokken bir koleksiyon hatası verdi. Uygulama sonrasında dar testler **7
   passed**, fiziksel harness ailesi **131 passed / 0 failed** tamamlandı.
   Altyazı track'i ve lineer önceki/sonraki playlist hedefi artık tıklamadan
   önce fail-closed `BLOCKED` kaydıdır; gerçek playlist tıklamasında beklenmedik
   modal 900 ms sonra gerçek Esc ile bounded kapatılır. Seçili grup üst sınırı
   sırasıyla **180/300/180/120 saniye** oldu (`EV-20260824-004`). Ürün kodu ve
   native durum değişmedi; fiziksel retry yapılmadı.
118. Harness düzeltmesi PR #26'nın exact `5742563` head'inde zorunlu hosted
   testten **4822 passed / 30 skipped / 0 failed** ile geçti. Ayrı onayla iki
   ebeveynli `227550d` merge commit'i üzerinden master'a alındı
   (`EV-20260824-005`). Bu hosted kanıt fiziksel Windows davranışını PASS
   yapmaz.
119. Ayrı onaylı `buttons` koşumu exact `227550d`, aynı doğrulanmış MP4/DLL,
   iki ayrı hardlink playlist yolu ve otomatik SRT etkinleştirmesine girmeyen
   gerçek dış ASS iziyle ilk denemede **44,4 saniye / exit 0 / 21 PASS / 0
   FAIL / 0 BLOCKED / MARK_DONE** verdi. Kapalı ve açık playlist panelinde CC,
   oynat/duraklat, sessiz, ses kaydırıcısı, ayarlar, sonraki/önceki ve tam
   ekran düğmeleri geçti; kapanış `stop -> terminate`, imleç geri dönüşü ve
   süreç temizliği doğrulandı (`EV-20260824-006`). İki playlist yolu aynı
   medya baytlarına aittir; timeline, native resize/fullscreen grupları ve
   P0-03/P0-07'nin daha geniş kabulü tamamlanmış sayılmaz. Ürün kodu değişmedi.

## Sıradaki tek adım

`EV-20260824-005` ve `EV-20260824-006` kayıt paketini commit etmek için ayrı
açık onay al. Native testi tekrar çalıştırma.

## Sonraki sıra

1. Commit sonrasında push, PR ve merge işlemlerini ayrı ayrı onaylat.
2. Kayıt merge edildikten sonra yalnız `timeline` grubu için ayrı native onay
   al; `window_resize` ve `fullscreen` aynı onaya dahil değildir.
3. Kalan açık boşluklar için dar runner veya kayıtlı manuel kabul kararını ver.
4. P0 başlangıç çizgisi kaydedilmeden `app/media_targets.py` ayrıştırmasını
   uygulama.
5. SignPath yanıtını paralel olarak bekle; özel iletişim bilgisini yayımlama ve
   GitHub App, imzalama veya yayın işlemini ayrı açık karar olmadan yapma.

## Kayıt düzeni

- Başlangıç ve güncel sıra: bu dosya.
- Makinece doğrulanan sonuçlar: `docs/VERIFICATION_LEDGER.json`.
- Yayın sırası: `docs/RELEASE_PROCESS.md`.
- Güncel kaynak/lisans engelleri: `packaging/corresponding_sources.json`.
- Tarihsel uzun kayıt: `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`,
  `docs/ENGINEERING_AUDIT.md`.
- Agent kuralları: kökte `AGENTS.md`; Claude uyumluluğu için `CLAUDE.md`.
- Mimari/gerçek Windows programı: `docs/QUALITY_EVOLUTION_PLAN.md`.
- Güncel modül ölçümü: `docs/ARCHITECTURE_INVENTORY.md`.
- Makinece modül güncellik kapısı: `docs/ARCHITECTURE_INVENTORY.json`.
- Gerçek cihaz senaryoları: `docs/WINDOWS_ACCEPTANCE_MATRIX.md`.
