# MLC Player güncel devam noktası

Bu dosya projenin **tek güncel devir noktasıdır**. Tarihsel ayrıntı burada
büyütülmez; doğrulanmış sonuçlar `VERIFICATION_LEDGER.json`, eski kapsamlı
notlar `PROJECT_STATUS.md`, `ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 21 Ağustos 2026
- Son push edilmiş taban: `0035f7c37347a933544e2bfed9373a50f921de65`
- Dal: `master` (yerel çalışma dalı farklı ad taşıyabilir)
- Son kanıt: `EV-20260821-011`
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
   (`EV-20260821-011`). Mirror artifact'i sağlamdır; libmpv build başlamadı.
7. `packaging/corresponding_sources.json` hâlâ `blocked` durumundadır.
   libmpv dışında cryptography/OpenSSL/Rust, yt-dlp transitif kaynakları ve
   kurulu lisans/notice/Qt relinking paketi açık kalır.
8. `SUBTITLE_SEARCH_UI_ENABLED=False` korunur. Yerel altyazı etkilenmez;
   OpenSubtitles masaüstü dağıtım şartı doğrulanmadan çevrimiçi arama açılmaz.
9. v0.38 build, kurulum, tag veya release yapılmadı. Kurulu v0.37 güncel
   kaynak ya da yeni DLL için kabul kanıtı değildir.

## Sıradaki tek adım

Kaynak digest ile doğrulanmış owned hedef manifest digest'ini ayrı sabitleyen
ve **15 passed** veren düzeltme bu kayıt commit'iyle commit edildi. Push için
ayrı onay al. Mirror run sonucunu geriye dönük PASS sayma ve mirror'ı yeniden
çalıştırma; sağlam artifact bağımsız kayıtla korunur.

Mirror başarıyla doğrulandıktan sonra libmpv source-captured build için yeni
ve ayrı açık build onayı al. Sonuç:

- başarılıysa binary ve corresponding-source artifact adlarını, boyutlarını,
  SHA-256 değerlerini ve run bağlantısını yeni ledger kaydıyla kaydet;
- başarısızsa adımı, ilk gerçek hata satırını ve oluşan artifact'leri kaydet;
  nedeni incelemeden tekrar çalıştırma.

Bu adım ürün build'i, kurulum, tag veya release yetkisi vermez.

## Sonraki sıra

1. Başarılı libmpv kaynak build'ini bağımsız doğrula ve ancak sonra mevcut
   DLL'i değiştirme planı hazırla. DLL değiştirme/build ayrıca onay ister.
2. cryptography/OpenSSL/Rust ve yt-dlp transitif kaynak açıklarını kapat.
3. Kurulu lisans/notice ve Qt relinking paketini doğrula.
4. `corresponding_sources.json` gerçekten `ready` ve blockers boş olmadan
   sürüm değerlendirmesine geçme.
5. Yalnız bundan sonra `docs/RELEASE_PROCESS.md` sırasını ayrı onaylarla uygula.

## Kayıt düzeni

- Başlangıç ve güncel sıra: bu dosya.
- Makinece doğrulanan sonuçlar: `docs/VERIFICATION_LEDGER.json`.
- Yayın sırası: `docs/RELEASE_PROCESS.md`.
- Güncel kaynak/lisans engelleri: `packaging/corresponding_sources.json`.
- Tarihsel uzun kayıt: `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`,
  `docs/ENGINEERING_AUDIT.md`.
- Agent kuralları: kökte `AGENTS.md`; Claude uyumluluğu için `CLAUDE.md`.
