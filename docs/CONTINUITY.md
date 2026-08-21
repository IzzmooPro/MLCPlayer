# MLC Player güncel devam noktası

Bu dosya projenin **tek güncel devir noktasıdır**. Tarihsel ayrıntı burada
büyütülmez; doğrulanmış sonuçlar `VERIFICATION_LEDGER.json`, eski kapsamlı
notlar `PROJECT_STATUS.md`, `ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 22 Ağustos 2026
- Son push edilmiş taban: `50b230ef0962950f0d55dbd141bb289ded6f3b30`
- Dal: `master` (yerel çalışma dalı farklı ad taşıyabilir)
- Son kanıt: `EV-20260821-041`
- Yayın kararı: **ENGELLİ — yeni sürüm çıkarılmaz**

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

## Sıradaki tek adım

Kaldırma kabulü geçti. `EV-20260821-039`–`041` build/kurulum/kaldırma kanıt
kayıtlarını commit etmek için kullanıcıdan ayrıca açık onay al. Push bu onayın
kapsamında değildir.

## Sonraki sıra

1. v0.38 draft aşamasında hazırlanmış libmpv kaynağının uzak
   ad/boyut/SHA-256 eşliğini doğrula; yeniden libmpv build etme.
2. Yalnız bundan sonra `docs/RELEASE_PROCESS.md` sırasını ayrı onaylarla uygula.

## Kayıt düzeni

- Başlangıç ve güncel sıra: bu dosya.
- Makinece doğrulanan sonuçlar: `docs/VERIFICATION_LEDGER.json`.
- Yayın sırası: `docs/RELEASE_PROCESS.md`.
- Güncel kaynak/lisans engelleri: `packaging/corresponding_sources.json`.
- Tarihsel uzun kayıt: `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`,
  `docs/ENGINEERING_AUDIT.md`.
- Agent kuralları: kökte `AGENTS.md`; Claude uyumluluğu için `CLAUDE.md`.
