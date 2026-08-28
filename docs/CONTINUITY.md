# MLC Player güncel devam noktası

Bu dosya projenin tek canlı devir noktasıdır. Tarihsel continuity kronolojisi
`CONTINUITY_HISTORY.md`, makinece doğrulanmış olaylar
`VERIFICATION_LEDGER.json`, diğer tarihsel anlatı `PROJECT_STATUS.md`,
`ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 28 Ağustos 2026
- Kayıt hazırlanırken doğrulanan HEAD: `e35ee2a5ea1dc1961220a2f80a32be6e2a6fe7a4`
- Güncel HEAD/origin farkı her oturumda `git rev-list --left-right --count` ile ölçülür; bu belge kendi commit hash'ini tahmin etmez.
- Dal: `codex/v040-b2-process-contract` (`origin/master` ile `7/0`; EV011 iki-belge PASS kaydı uncommitted)
- Son kanıt: `EV-20260828-011`
- Yayın kararı: **v0.39 canlı/latest; 87 varlık eş, public indirme/kurulum/açılış/medya kabulü geçti.**

## Canlı ürün ve yayın durumu

- Belge/yönetişim paketi ve semantik sahiplik düzeltmesi PR #48 üzerinden
  iki ebeveynli exact `5a94d4e` merge commit'iyle master'a alındı. Yerel ve
  uzak master, PR #49 kayıt merge'i sonrasında exact `b7e7cdd` üzerinde temiz,
  `0/0` ve aynıdır; iki görev dalı da korundu (`EV-20260826-006`).
- PR #48'in exact head'inde ilk zorunlu hosted run `32899094320`, **4965
  passed / 30 skipped / 1 failed** verdi (`EV-20260826-002`). Tek hata
  `PACKAGING_PLAN.md` için stale bütün-belge-tarihsel testiydi; otomatik retry
  yapılmadı.
- Semantik sahiplik düzeltmesi `EV-20260826-003` ile dar grupta **13 passed**
  ve bağımsız karşıt incelemede bloklayıcı bulgusuzdu. Repaired exact head
  `8558b73` üzerindeki yeni run `32934932893`, **4966 passed / 30 skipped /
  0 failed** ve `LEDGER_APPEND_ONLY_OK` verdi; PR merge öncesi MERGEABLE ve
  required `test=SUCCESS` olarak geri okundu (`EV-20260826-005`).
- `master` için PR ve GitHub Actions `test` kapısı aktiftir. GitHub approving
  review sayısı `0` olsa da bağımsız çift-süzgeç süreci uygulanır; force-push,
  protection bypass ve doğrudan master değişikliği yapılmaz.
- v0.39 zinciri kaynak build `EV-20260822-023`, tag/prepublish
  `EV-20260822-027`, uzak tag eşliği `EV-20260822-028`, draft asset eşliği
  `EV-20260822-029`, public latest/updater metadata `EV-20260822-032` ve
  public indirme/kurulum/açılış/gerçek medya kullanıcı kabulü
  `EV-20260822-033` kayıtlarına dayanır. Yeni build veya farklı artifact bu
  kabulü devralmaz.
- Kurulu v0.37 veya başka eski artifact için alınan sonuçlar v0.39'a ya da
  gelecekteki build'e taşınmaz.

## Kalite kabul özeti

- Windows P0 matrisi: `WIN-P0-01`–`WIN-P0-05` PASSED; drag/drop, playlist
  sınırları ve IPC için `P0-06`, `P0-07`, `P0-08` NOT_RUN.
- Video biçimi matrisi: SDR ekranda `VF-CORE-01` ve HDR ekranda SDR-on-HDR
  `VF-CORE-02` exact native ve kontrollü insan ramp kabulüyle PASSED. Kalan
  14 biçim satırı ve genel `WIN-P2-01` BLOCKED; bu iki PASS genel HDR/format
  desteği değildir.
- `VF-CORE-02` kanıtı exact fixture/runtime ve G2084/P2020 ekranda BT.709/
  BT.1886 giriş, BT.2020/PQ `rgba16hf` hedef, sıfır drop, exit 0,
  `MARK_DONE`, `stop -> terminate` ve sıfır süreç sızıntısıyla sınırlıdır.
- Hosted CI sonucu native Windows, kurulu paket, kullanıcı gözlemi veya
  skipped senaryoları PASS yapmaz.

## Açık çalışma ve korunan kapılar

- Installer UX kararları `PACKAGING_PLAN.md` içinde tutulur. Üç private bitmap
  yönü karşılaştırıldı; kullanıcı **C — Dengeli Hibrit** yönünü açıkça seçti
  ve seçim kayıt paketi exact `f432c73` commit'iyle bağlandı
  (`EV-20260826-008`). A ve B yalnız karşılaştırma referansıdır. Bitmap'ler
  Git'e alınmaz ve seçim gerçek Inno Setup davranışı sayılmaz.
- v0.40/Inno, reentry ve Türkçe Ready düzeltme zinciri PR #53–#55 üzerinden
  protected master'a alındı; exact hosted koşumlar yeşil, insan kontrollü
  ana/add-on ekran ve payload sınırları kabul edildi. Tam tarih ve ara kusurlar
  append-only `EV-20260826-077`–`083` kayıtlarındadır.
- İlk resmî v0.40 artifact zinciri hosted **5058 passed / 30 skipped** ve geçerli
  Ed25519 verdi; Authenticode `NotSigned`. Active add-on kapanış ve ürün URL
  önkoşulları fail-closed durdu (`EV-20260827-011`–`013`).
- Internet Video fallback ve geçici `QMenu` test ömrü regression-first kapatıldı;
  protected PR #64 head'i **5059 passed / 30 skipped / 0 failed** verdi. Ara
  hosted başarısızlıklar retry edilmedi; kaynak/test/provenance ayrıntıları
  `EV-20260827-014`–`023` içindedir.
- PR #64 build kanıtı ve PR #65 path-contract düzeltmesi protected master'a
  exact `ebc628b` olarak ulaştı; başarısız run retry edilmedi
  (`EV-20260827-024`–`027`).
  Exact-master dispatch **5061 passed / 30 skipped / 0 failed** verdi (`EV-20260827-028`);
  EV029 exact ebc build'i ana/add-on `07118348...cf6c5` / `d4a4d799...f9e675` üretti.
  Son B2 farklı `B8001DAA...fe2fc` ana artifact ile yürüdü fakat çağdaş source-build
  transcript'i yoktu. Provenance preflight'ı shared output'taki iki installer EXE'yi
  kaldırdı; imzalar ve kurulu v0.40 kaldı, ölçülen ürün/kullanıcı/kayıt durumu exact
  aynı ve süreç 0 (`EV-20260827-038`, imza sınırı düzeltmesi `EV-20260828-001`). Final cycle NOT_RUN; tag/release blokludur.
- Exact `994f0e2` artifact'larıyla yürütülen B2 zincirinde silent/interaktif
  kurulumlar, gerçek v0.39 yükseltmeleri, iki kaldırma sırası, altı geçersiz
  add-on hedefi, payload/ayar/süreç okumaları geçti. Gerçek Blender URL'si
  Player-owned exact `yt-dlp` ile 00:01→00:02 / 10:35 ilerledi; çıkarım Deno
  gerektirmedi. Bağımsız birlikte çalıştırılan finite `yt-dlp`/Deno engelleyici
  denemesi Restart Manager'da fail-closed durdu; kullanıcı Abort seçti, exit 5,
  rollback sonrası 103 kurulu ve iki kullanıcı dosyasında fark sıfır, süreç
  sızıntısı sıfırdı (`EV-20260827-030`). Karşıt inceleme bunun installer kusuru
  değil güvenli negatif davranış olduğunu doğruladı; `force` eklenmedi.
- EV031'deki o tarihteki B2 sözleşmesi regression-first olarak gerçek ürün URL başarısını
  yapay engelleyicilerden ayırdı. Product-success yalnız Player'ın başlattığı
  exact `yt-dlp`, PID/ebeveyn/komut ve ilerleyen position/duration ile geçer;
  Deno yalnız gerçek çıkarım kullanırsa gerekir. Refusing `yt-dlp` ve Deno
  diğer hedefler kapalıyken ayrı tek-engelleyici senaryolarında ölçülür; Ignore
  ve force yasak, Abort/rollback/hash/AppData/süreç sınırları fail-closed kalır.
  Hedef kırmızıdan sonra belge ailesi **206 passed**, karşıt P0/P1/P2=0 verdi;
  ürün ve Inno kaynakları değişmedi (`EV-20260827-031`); bu Deno refusal şartı
  daha sonra EV035 ile ölçülen cooperative-Deno kuralıyla değiştirildi.
- Exact kurulu v0.39 `yt-dlp` root+child diğer hedefler kapalı tek engelleyici
  olarak sınandı. Restart Manager yalnız iki `yt-dlp` sürecini buldu, kapanışın
  tamamlanamadığını kaydetti; kullanıcı Ignore/Retry yerine Abort seçti. Setup
  exit 5, kopya/başarı marker'ı yok, rollback sonrası 103 kurulu dosya, iki
  kullanıcı dosyası, kayıtlar ve hashler exact aynı, hedef süreç sızıntısı
  sıfırdı. İlk evaluator şema-kesişimini yanlış yorumlayarak güvenli BLOCKED
  verdi; fiziksel retry yapılmadan ayrı düzeltilmiş verdict **16/16 PASS** oldu
  (`EV-20260827-032`). Bu PASS yalnız yt-dlp fail-closed negatif kapısına aittir.
- Restart Manager exact Deno'yu kooperatif kapattı; v0.39→v0.40 add-on upgrade
  sızıntısız PASS (`EV-20260827-033`), normal fixture refusal BLOCKED (`EV-20260827-034`).
  Sözleşme graceful Deno + exact yt-dlp fail-closed oldu; belge **206 passed**, P0/P1/P2=0 (`EV-20260827-035`).
- Askıya alınmış tek exact v0.40 Player kapanmayınca ana setup kopya öncesi durdu;
  kullanıcı Retry/Ignore yerine Abort seçti, exit 5 ve rollback başarılıydı. Tüm
  ölçülen 103+2 dosya ile ayar/uninstall/OpenWith/kısayol yüzeyleri exact korundu; resume 0, normal kapanış, watchdog
  ateşlenmedi, sızıntı 0; evaluator **23/23 PASS**, karşıt P0/P1=0 (`EV-20260827-036`); app-level semantik/normal maintenance/silent/add-on'a aktarılmaz, belge kapanışı P0/P1/P2=0 (`EV-20260827-037`).
- Ayrı onaylı izole build exact `1dafe1f` üzerinde tek çalıştırmada exit 0 ve `DONE` verdi; fast-fail ana setup `ABBB01C3...DC34` / 55.945.176 bayt, değişmeyen add-on `D4A4D799...F9E675` / 48.909.126 bayt, iki detached Ed25519 geçerli, iki EXE Authenticode `NotSigned` ve süreç sızıntısı 0. Bu yalnız `source_build` PASS'tir; 5–10 saniye fiziksel davranış daha sonra EV011 ile geçti fakat tam B2 hâlâ tamamlanmadı (`EV-20260828-009`).
- Exact B7/D4 normal fiziksel döngüsü gerçek v0.39 yükseltmesi, iki kaldırma sırası, clean install, maintenance, payload/ayar koruması ve final restore ile geçti. Askıya alınmış Player yolu kopya öncesi Abort/exit 5, tam rollback ve sıfır sızıntıyla güvenliydi; fakat Restart Manager **66,715 saniye** bekledi. Kullanıcının 5–10 saniye UX sınırı nedeniyle tam B2 **FAILED** (`EV-20260828-006`).
- Regression-first installer-only düzeltme maintenance/upgrade sırasında süreç-ömürlü `MLCPlayer-Running` mutex'ini `PrepareToInstall` içinde önce denetler ve çalışan Player varsa kopya/RM bekleyişinden önce sekiz dilde hızlı fail-closed durur. `CloseApplications` fallback'i korunur; force/taskkill/ürün kodu yoktur. Dil sözleşmesi ve yanlış aynı-sihirbaz talimatı kapatıldı; dar paket **60 passed** (`EV-20260828-007`).
- Onaylı beş-dosya fast-fail/kayıt paketi exact `315e83a`, EV008 iki-belge evidence-commit kaydı exact `1dafe1f` olarak bağlandı; dosya sınırları ve post-commit dar paket **266 passed** (`EV-20260828-008`).
- Exact ABBB tek fiziksel denemesi setup başlamadan runner izolasyon kapısında **BLOCKED** oldu: başlangıç hedef süreç 0 ve başlatılan Player kimliği doğruydu, fakat üç saniye sonra hedef küme tek değildi. UAC/setup/suspend/kopya yok; Player normal kapandı, force/watchdog/sızıntı 0, 103+2 final durum korundu. Eski runner geçici hedef kimliğini kaydetmediğinden guard gevşetilmedi; prepared fresh runner sonraki ayrı onaylı denemede tam kümeyi kaydedecek (`EV-20260828-010`).
- Ayrı onaylı tek fresh-runner denemesinde exact ABBB setup askıya alınmış tek exact Player ve doğrulanmış mutex karşısında **6,983 saniyede** exit 7 ile hızlı fail-closed durdu; setup içi süre yaklaşık 0,131 saniyeydi. Restart Manager, kopya ve başarı marker'ı yok; 103 kurulu dosya, iki kullanıcı dosyası, ayarlar, kayıtlar, OpenWith ve üç kısayol exact korundu. Suspend/resume 0/0, normal kapanış, force/watchdog yok ve süreç sızıntısı 0; karşıt P0/P1=0 (`EV-20260828-011`). Bu PASS yalnız fast-fail senaryosudur; exact ABBB normal install/upgrade/uninstall B2 zincirinin yerine geçmez.
- `WIN-P0-03` ilk native koşumu exact `06cebc4` üzerinde fixture kapısını
  geçtikten sonra QMenu sınırında TIMEOUT oldu; exit 1 ve eksik final marker
  nedeniyle **FAILED** kaydedildi, seçim/ürün bug'ı iddia edilmedi
  (`EV-20260827-005`). Test-only nested-loop watchdog paketi 222 dar test ve
  karşıt P0/P1=0 sonrası PR #61 exact head `8b1471d` üzerinde **5058 passed /
  30 skipped / 0 failed** verdi ve exact `18a88b8` olarak merge edildi. Ayrı
  onaylı tek retry 35.6 saniyede **5 PASS / 0 FAIL / 0 BLOCKED**, exit 0, tam
  marker zinciri, ses 1→2, altyazı 1→2→1, checked read-back,
  `stop→terminate`, child/parent cursor restore ve ölçülen süreç=0 ile geçti
  (`EV-20260827-009`). `WIN-P0-03` artık **PASSED**.
- C yönü seçim, continuity ve protected-master kayıt zinciri PR #50–#52 ile
  merge edildi; exact commit/run/parent ayrıntıları append-only
  `EV-20260826-009`–`017` ve `EV-20260826-028` kayıtlarındadır.
- Beş ekranlı C sözleşmesi tek kanonik sahibi `PACKAGING_PLAN.md` içinde
  hazırlandı. Güncelleme kutusu mevcut ürün ayarına bağlı olmadığı için
  çıkarıldı; Internet Video yalnız ayrı paket bilgisi olarak kaldı. İki private
  test görseli gösterildi; gerçek Inno, build ve kurulum kabulü değildir.
- Kullanıcı finish seçeneklerinin gerçekten çalışmasını zorunlu tuttu.
  Regression-first kırmızıdan sonra exact EXE, Default Apps ve GitHub hedefi,
  optional-action sıra/hata/readback'i sözleşmeye bağlandı (`EV-20260826-018`).
  Son çift-süzgeç UAC sahipliği, install/reinstall/upgrade metni, downgrade
  engeli ve per-screen test boşluklarını buldu; ara test hataları incelenip
  sözleşme/test daraltıldı. Son karşıt incelemede finish testinin belge-geneli
  araması da fail-open bulundu; test finish ve fiziksel kabul bloklarına ayrı
  bağlandı ve nihai paket `EV-20260826-021` ile doğrulandı.
- Kullanıcı gösterilen iki private C akış görselini hedef kompozisyon ve metin
  olarak açıkça kabul etti (`EV-20260826-022`). Bu, compiled Inno pikseli,
  handler, build, kurulum veya Windows action/readback kabulü değildir.
- C ekran-sözleşmesinin commit/build/reddedilen ara artifact/restore ve exact
  cleanup zinciri append-only `EV-20260826-023`–`074` kayıtlarında korunur;
  canlı kararlar yukarıdaki v0.40 kabul özetindedir ve meta-kayıt döngüsü
  başlatılmaz.
- `SUBTITLE_SEARCH_UI_ENABLED=False` korunur. OpenSubtitles masaüstü dağıtım
  şartları ve güvenli dosya-çakışma davranışı doğrulanmadan çevrimiçi altyazı
  arayüzü açılmaz.
- SignPath yanıtı beklenir. Ayrı açık onay olmadan GitHub App kurulmaz,
  imzalama veya yayın işlemi yapılmaz; private iletişim bilgisi yayımlanmaz.
- `app/media_targets.py` ayrıştırması, ilgili P0 başlangıç çizgisi
  kaydedilmeden uygulanmaz.
- README'deki yerel altyazının otomatik görünürlüğü ile mevcut kaynak/test
  davranışı arasındaki çelişki ürün kararı bekler; bu belge düzenlemesi o
  davranışı değiştirmez.

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

EV011 iki-belge fast-fail PASS kaydını ayrı onayla commit et; sonra exact ABBB artifact'ı için kalan normal B2 install/upgrade/uninstall zinciri ayrıca onaylanmadan çalıştırılmaz. `P0-06`–`08` yayın sonrası; thumbnail cache politikası ürün kararıdır.

## Dokunulmayacaklar ve ayrı onaylar

- Private görsel/native artifact yolları Git'e eklenmez.
- Ledger append-only kalır; eski kayıt silinmez, yeniden sıralanmaz veya yerinde
  düzeltilmez.
- Ürün kodu, build, kurulum/kaldırma, commit, push, PR, merge, tag ve release
  birbirinden ayrı açık kullanıcı onayı ister.
- Başarısız native/hosted çalışma neden incelenmeden otomatik tekrarlanmaz.

## Kanonik kayıt kaynakları

- Canlı durum: `CONTINUITY.md`; kronoloji: `CONTINUITY_HISTORY.md`; kanıt: `VERIFICATION_LEDGER.json`; tarihçe: `PROJECT_STATUS.md`, `ROADMAP.md`, `ENGINEERING_AUDIT.md`.
- Paketleme/akış/yayın: `PACKAGING_PLAN.md`, `CHANGE_WORKFLOW.md`, `RELEASE_PROCESS.md`.
- Kalite/mimari/Windows: `docs/QUALITY_EVOLUTION_PLAN.md`, `docs/ARCHITECTURE_INVENTORY.md`, `docs/ARCHITECTURE_INVENTORY.json`, `docs/WINDOWS_ACCEPTANCE_MATRIX.md` ve video formatı kabul dosyaları.
