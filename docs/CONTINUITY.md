# MLC Player güncel devam noktası

Bu dosya projenin **tek güncel devir noktasıdır**. Tarihsel ayrıntı burada
büyütülmez; doğrulanmış sonuçlar `VERIFICATION_LEDGER.json`, eski kapsamlı
notlar `PROJECT_STATUS.md`, `ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 21 Ağustos 2026
- Son push edilmiş taban: `786f388f05ee10833bbd14fa0c55fc5a487e9f86`
- Dal: `master` (yerel çalışma dalı farklı ad taşıyabilir)
- Son kanıt: `EV-20260821-023`
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
18. `packaging/corresponding_sources.json` hâlâ `blocked` durumundadır.
   Yalnız yt-dlp transitif kaynakları ve kurulu lisans/notice/Qt relinking
   paketi açık kalır. libmpv ve cryptography kaynak build/envanter açıkları
   kapandı.
19. `SUBTITLE_SEARCH_UI_ENABLED=False` korunur. Yerel altyazı etkilenmez;
   OpenSubtitles masaüstü dağıtım şartı doğrulanmadan çevrimiçi arama açılmaz.
20. v0.38 build, kurulum, tag veya release yapılmadı. Kurulu v0.37 güncel
   kaynak ya da yeni DLL için kabul kanıtı değildir.

## Sıradaki tek adım

Kilitli resmi `yt-dlp 2026.08.19` executable'ının tam transitif kaynak
envanterini dağıtılan üçüncü taraf bildirimi ve resmi build metadata'sıyla
eşleştir; yalnız doğrulanan kaynakları sözleşmeye ekle.

## Sonraki sıra

1. yt-dlp transitif kaynak açığını kapat.
2. Kurulu lisans/notice ve Qt relinking paketini doğrula.
3. `corresponding_sources.json` gerçekten `ready` ve blockers boş olmadan
   sürüm değerlendirmesine geçme.
4. v0.38 draft aşamasında hazırlanmış libmpv kaynağının uzak
   ad/boyut/SHA-256 eşliğini doğrula; yeniden libmpv build etme.
5. Yalnız bundan sonra `docs/RELEASE_PROCESS.md` sırasını ayrı onaylarla uygula.

## Kayıt düzeni

- Başlangıç ve güncel sıra: bu dosya.
- Makinece doğrulanan sonuçlar: `docs/VERIFICATION_LEDGER.json`.
- Yayın sırası: `docs/RELEASE_PROCESS.md`.
- Güncel kaynak/lisans engelleri: `packaging/corresponding_sources.json`.
- Tarihsel uzun kayıt: `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`,
  `docs/ENGINEERING_AUDIT.md`.
- Agent kuralları: kökte `AGENTS.md`; Claude uyumluluğu için `CLAUDE.md`.
