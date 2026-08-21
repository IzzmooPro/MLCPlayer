# MLC Player güncel devam noktası

Bu dosya projenin **tek güncel devir noktasıdır**. Tarihsel ayrıntı burada
büyütülmez; doğrulanmış sonuçlar `VERIFICATION_LEDGER.json`, eski kapsamlı
notlar `PROJECT_STATUS.md`, `ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 21 Ağustos 2026
- Son push edilmiş taban: `8c7506e95740e7a40a9bd7845271771f566f5fcf`
- Dal: `master` (yerel çalışma dalı farklı ad taşıyabilir)
- Son kanıt: `EV-20260821-006`
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
   yapılmadı ve sonuç `EV-20260821-006` olarak kaydedildi. Onaylı yerel
   düzeltme hazırdır; ilgili imza, devam ve yayın-belgesi paketi **212 passed**
   verdi. Düzeltme mevcut HEAD'de commit edildi; henüz push edilmedi.
4. libmpv karşılık gelen kaynak derlemesi henüz başarılı değildir. Run
   `32414388160`, iki saat sonra build-time Git kimliği eksikliğiyle durdu;
   DLL ve kaynak paketi oluşmadı, yalnız log artifact'i oluştu.
5. Aynı hatanın tekrarlanmaması için geçici CI Git kimliği `8c7506e` ile
   eklendi ve hedef regresyon paketi **7 passed** verdi. Yeni libmpv kaynak
   derlemesi henüz çalıştırılmadı; bu nedenle düzeltme gerçek derleme kanıtı
   sayılmaz.
6. `packaging/corresponding_sources.json` hâlâ `blocked` durumundadır.
   libmpv dışında cryptography/OpenSSL/Rust, yt-dlp transitif kaynakları ve
   kurulu lisans/notice/Qt relinking paketi açık kalır.
7. `SUBTITLE_SEARCH_UI_ENABLED=False` korunur. Yerel altyazı etkilenmez;
   OpenSubtitles masaüstü dağıtım şartı doğrulanmadan çevrimiçi arama açılmaz.
8. v0.38 build, kurulum, tag veya release yapılmadı. Kurulu v0.37 güncel
   kaynak ya da yeni DLL için kabul kanıtı değildir.

## Sıradaki tek adım

Hazır, commit edilmiş ve **212 passed** veren `sign_release.py` belge
sözleşmesi düzeltmesini ayrı kullanıcı onayıyla push et. Yeni hosted CI
başarıyla bitmeden libmpv derlemesine geçme.

Ardından kullanıcı ayrı açık build onayı verirse, GitHub Actions içindeki
**libmpv source-captured build** iş akışını bir kez manuel başlat. Başlamadan
run commit'ini geri oku. Sonuç:

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
