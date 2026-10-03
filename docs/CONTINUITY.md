# MLC Player güncel devam noktası

Bu dosya projenin tek canlı devir noktasıdır. Belge haritası `docs/README.md`,
makinece doğrulanmış olaylar `docs/VERIFICATION_LEDGER.json`, tarihsel
continuity kronolojisi `docs/history/CONTINUITY_HISTORY.md` içindedir. Diğer
tarihsel anlatı `docs/history/` altındadır ve güncel karar kaynağı değildir.

- Güncelleme: 3 Ekim 2026
- Kayıt hazırlanırken doğrulanan HEAD: `c5ca0ec56ee8f7045cf03477ca1fe981b4692c4d`
- Güncel HEAD/origin farkı her oturumda `git rev-list --left-right --count`
  ile ölçülür; bu belge kendi commit hash'ini tahmin etmez.
- `master`: PR #75 merge commit `c5ca0ec` (ürün düzeltmeleri, klasör/belge
  düzeni ve CI test-yarışı düzeltmesi; `EV-20261003-001`–`002`).
- Son kanıt: `EV-20261003-005` (exact `699C34C3` sessiz kaldırıldı, ürün
  artığı sıfır; kurulum `EV-20261003-004`, build `EV-20261003-003`)
- Yayın kararı: **v0.40 canlı/latest; 87 varlık eş, public ana/add-on indirme
  hashleri ve Ed25519 imzaları geçti.** v0.41 henüz yayımlanmadı.

## Canlı ürün ve yayın durumu

- `master` için PR ve GitHub Actions `test` kapısı aktiftir. GitHub approving
  review sayısı `0` olsa da bağımsız çift-süzgeç süreci uygulanır; force-push,
  protection bypass ve doğrudan master değişikliği yapılmaz.
- v0.40 PR #67 exact `0a4f34c` head'i required `test` ile geçti ve merge commit
  `e702dd8c` exact-master dispatch'te **5064 passed / 30 skipped** verdi
  (`EV-20260828-019`). Annotated `v0.40` aynı commit'e peel eder; prepublish
  87/87, draft ad/boyut/SHA eşliği ve public/latest readback geçti. Ürünün
  updater yolu exact ABBB ana paketi seçti; public ana/add-on dosyaları
  yeniden indirilip accepted hash ve Ed25519 imzalarıyla eşleşti
  (`EV-20260828-020`).
- Kurulu v0.37 veya başka eski artifact için alınan sonuçlar v0.39'a ya da
  gelecekteki build'e taşınmaz.
- Güncel v0.41 adayı exact `c5ca0ec` build'idir: ana setup `699C34C3...85FB1`
  / 64.318.343 bayt, add-on `15230011...0563E` / 48.810.649 bayt (değişmedi),
  iki Ed25519 imzası geçerli (`EV-20261003-003`). Önceki yerel adaylar
  (`447E2155` ve eskileri) kaynakla birebir değildir. Paket kuruldu; ağaç
  build ile birebir, kullanıcı kontrolleri geçti (`EV-20261003-004`).
  Sessiz kaldırma bütün ürün artıklarını (kullanıcı görevi, yardımcı ve
  kaydı dahil) müdahalesiz sildi; yalnız varsayılan gereği kullanıcı ayarı ve
  eski günlük kaldı (`EV-20261003-005`). Kanıtlanmayanlar: ekrandan büyük
  kayıtlı pencere, ilk açılıştaki arka plan kaydı ve görünür kaldırıcının
  veri silme seçenekleri.

## Kalite kabul özeti

- Windows P0 matrisi: `WIN-P0-01`–`WIN-P0-06` PASSED; tam kabul sözleşmesi
  için `P0-07`, `P0-08` NOT_RUN. Dar playlist taşıma logu 4/4 PASS olarak geri
  okundu; IPC devri başarılı raporlandı ancak ham koşum kanıtı bulunamadı
  (`EV-20260905-004`–`005`).
- `WIN-P0-06` exact `3451aef` kaynak ağacında manuel Explorer video+SRT
  bırakmayla doğru oynatma, ilerleyen süre ve görünür altyazı verdi; tek
  dış-SRT native ölçümünde `stop→terminate` yaklaşık 0,08 sn, exit 0, süreç
  sızıntısı 0 (`EV-20260829-011`).
- Playlist UX paketi ve B yerleşimi (tek tekrar düğmesi, ayrı karışık düğmesi)
  deterministik pakette geçti; ilk kullanıcı kabulü `loop` geri okuma
  hatasıyla FAILED oldu, düzeltme **324 passed** verdi ancak fiziksel olarak
  yeniden açılmadı (`EV-20260829-013`, `EV-20260830-001`–`003`). Formal
  `WIN-P0-07` sırası kaydedilmediği için `NOT_RUN` kalır.
- Görsel bütünlük paketi (tek turuncu vurgu, ortak font zinciri, focus
  durumları) ve ana pencere kabul runner'ı eklendi; ilk gerçek runner
  ölçümünde buttons **21/21**, window_resize **12/12** geçti, playlist açıkken
  `overlayFullscreen` `entered=False` ile başarısız oldu
  (`EV-20260830-004`–`008`). Taze Windows insan görsel kabulü yoktur.
- `WIN-P0-08` deterministik çok-süreç kapsamı genişletildi; gerçek pencere
  foreground ve hedef yükleme ölçülmediği için fiziksel satır `NOT_RUN`
  (`EV-20260829-002`–`009`).
- Video biçimi matrisi: SDR ekranda `VF-CORE-01` ve HDR ekranda SDR-on-HDR
  `VF-CORE-02` exact native ve kontrollü insan ramp kabulüyle PASSED. Kalan
  14 biçim satırı ve genel `WIN-P2-01` BLOCKED; bu iki PASS genel HDR/format
  desteği değildir.
- `VF-CORE-02` kanıtı exact fixture/runtime ve G2084/P2020 ekranda BT.709/
  BT.1886 giriş, BT.2020/PQ `rgba16hf` hedef, sıfır drop, exit 0,
  `MARK_DONE`, `stop -> terminate` ve sıfır süreç sızıntısıyla sınırlıdır.
- Hosted CI sonucu native Windows, kurulu paket, kullanıcı gözlemi veya
  skipped senaryoları PASS yapmaz.
- Kapanmış v0.40 installer/B2 zincirleri, PR #48/#49 meta kayıtları ve
  yayın sonrası UX denetimi kelimesi kelimesine `CONTINUITY_HISTORY.md`
  içindeki 3 Ekim 2026 arşiv bölümündedir.

## Açık çalışma ve korunan kapılar

- Installer UX kararlarının tek kanonik sahibi
  `docs/release/PACKAGING_PLAN.md` belgesidir; kullanıcı C — Dengeli Hibrit
  yönünü seçti (`EV-20260826-008`).
- `SUBTITLE_SEARCH_UI_ENABLED=False` korunur. OpenSubtitles masaüstü dağıtım
  şartları ve güvenli dosya-çakışma davranışı doğrulanmadan çevrimiçi altyazı
  arayüzü açılmaz.
- SignPath Foundation başvurusu 2 Eylül 2026'da yeterli kamu görünürlüğü/güven
  sinyali olmadığı gerekçesiyle onaylanmadı; bu teknik kalite reddi, sertifika
  veya ücretli plan onayı değildir. Ayrı açık onay olmadan GitHub App
  kurulmaz, imzalama veya yayın yapılmaz (`docs/release/SIGNPATH.md`).
- `app/media_targets.py` ayrıştırması, ilgili P0 başlangıç çizgisi
  kaydedilmeden uygulanmaz.
- Kullanıcı eşleşen yerel `.srt` dosyaları için otomatik seçme ve görünür
  açma davranışını ürün sözleşmesi olarak seçti (`EV-20260905-019`).
- Kalite/mimari/Windows işi: `docs/quality/QUALITY_EVOLUTION_PLAN.md`,
  `docs/quality/ARCHITECTURE_INVENTORY.md`,
  `docs/quality/ARCHITECTURE_INVENTORY.json`,
  `docs/quality/WINDOWS_ACCEPTANCE_MATRIX.md` ve `docs/video-format/`.
- Ertelenen öneriler (ayrı karar ister): EOF tespitinin 100 ms yoklama yerine
  `eof-reached`/`idle-active` gözlemiyle yapılması gerçek libmpv ve native
  ölçüm gerektirir; birden çok dosyayla açma tek kopya protokol sürümünü
  yükseltir; CI'a ruff eklemek kilitli bağımlılık dosyasını değiştirir;
  kaynak-metin (`"x" in source`) testlerinin davranış testine çevrilmesi
  kademeli yapılmalıdır.
- Gizlilik: `docs/VERIFICATION_LEDGER.json` içinde 24 kayıt yerel kullanıcı
  yolunu taşır; ledger append-only olduğu için yerinde değiştirilmedi
  (kullanıcı kararı, 3 Ekim 2026). Yeni kayıtlara kullanıcı yolu yazılmaz.

## Kanıt sınırları

- `deterministic`: kaynak, statik veya hedef test kanıtı.
- `hosted_ci`: GitHub runner kanıtı.
- `source_build`: derleme ve karşılık gelen kaynak artifact'i kanıtı.
- `registry_artifact`: sabit container manifest/blob eşliği kanıtı.
- `native_smoke`: exact commit, binary ve gerçek native senaryo kanıtı.
- `installed_artifact`: adı, boyutu ve SHA-256 değeri kayıtlı artifact kanıtı.
- `external_submission`: üçüncü tarafın açık teslim/başarı ekranı kanıtı.

Bir katmandaki PASS başka katmana aktarılmaz. `blocked`, `failed`, `skipped`
veya eksik marker PASS değildir.

## Meta-kayıt terminal kuralı

Merge-kayıt PR'ı protected master'a ulaştığında yeni meta-PR zinciri başlatma;
merge/parent/run/`0/0` readback'ini sonraki gerçek kayıt provenance'ına bağla.

## Sıradaki tek adım

Kayıt dalı `codex/v041-build-record`'u ayrı onaylarla commit, push ve PR
olarak göndermek. Ardından v0.41 tag ve yayını yalnız
`docs/release/RELEASE_PROCESS.md` sırasıyla, exact `c5ca0ec` artifact'ları
(`699C34C3` ana setup, `15230011` add-on ve `.sig` dosyaları) ile ve her adım
için ayrı onayla yapılır.

## Dokunulmayacaklar ve ayrı onaylar

- Private görsel/native artifact yolları Git'e eklenmez.
- Ledger append-only kalır; eski kayıt silinmez, yeniden sıralanmaz veya yerinde
  düzeltilmez.
- Ürün kodu, build, kurulum/kaldırma, commit, push, PR, merge, tag ve release
  birbirinden ayrı açık kullanıcı onayı ister.
- Başarısız native/hosted çalışma neden incelenmeden otomatik tekrarlanmaz.
