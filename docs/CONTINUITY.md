# MLC Player güncel devam noktası

Bu dosya projenin tek canlı devir noktasıdır. Tarihsel continuity kronolojisi
`CONTINUITY_HISTORY.md`, makinece doğrulanmış olaylar
`VERIFICATION_LEDGER.json`, diğer tarihsel anlatı `PROJECT_STATUS.md`,
`ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 27 Ağustos 2026
- Kayıt hazırlanırken doğrulanan HEAD: `e64f8c2feea9300f621c8a74f4cf576c968eb71f`
- Güncel HEAD/origin farkı her oturumda `git rev-list --left-right --count` ile ölçülür; bu belge kendi commit hash'ini tahmin etmez.
- Dal: `codex/internet-video-format-fallback` (`origin/master`dan 2 ileride; preservation kaydı uncommitted)
- Son kanıt: `EV-20260827-016`
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
- v0.40/Inno paketi PR #53 ile `3dc9dde` master'a alındı; exact-master run tek flaky
  reentry testinde durdu, timer kök nedeni test-only kapatıldı (`EV-20260826-077/078`).
- Test-only reentry düzeltmesi PR #54 ile exact `98c9511` protected master'a
  alındı. PR run'ı ve yeni exact-master dispatch sırasıyla **5025 passed / 30
  skipped / 0 failed** verdi; eski başarısız run retry edilmedi.
- Exact `98c9511` kaynak build'inin 55,934,004 baytlık ana v0.40 setup'ı önce
  kurulu v0.39'u kullanıcı kontrollü interaktif akışta v0.40'a yükseltti;
  kurulu Player build EXE'siyle exact eş, 91 dist dosyasında eksik/uyuşmazlık
  sıfır ve normal kullanıcı kapanışı sonrasında süreç sızıntısı sıfırdı.
- Ayrı aynı-sürüm maintenance senaryosunda kurulu Player açık bırakıldı;
  Restart Manager uygulamayı listeledi ve kullanıcı close-applications yolunu
  seçti. Eski PID kopya başlamadan kapandı, kurulum logu başarı ve restart yok
  sonucu verdi, 91 dist dosyası yine exact eş kaldı ve üç Finish eylemi kapalıyken
  yeni Player/Settings/tarayıcı süreci açılmadı (`EV-20260826-079`). Setup launcher
  exit code'u tutulmadığından ve aktif ayar baseline'ı Player açılmadan önce
  alındığından genel exit-code veya kullanıcı-ayar-koruma PASS'i yazılmadı.
- Exact v0.40 add-on maintenance, Ready ekranı görünmeyen `Sonraki` eylemine
  yönlendirirken gerçek düğme `Kur` olduğu için kopya başlamadan iptal edildi;
  103 dosya, ayarlar, kayıtlar ve süreçler değişmeden kaldı (`EV-20260826-080`).
  Regression-first düzeltme yalnız Inno'nun iki hatalı Türkçe Ready mesajını
  override eder; hedef/aile **1/14 passed**, ilgili aile **33 passed**, gerçek
  main+add-on compile preflight PASS ve çift-süzgeç temizdir (`EV-20260826-081`).
- Düzeltme PR #55 ile iki ebeveynli exact `6dacfd5` merge commit'i olarak
  protected master'a ulaştı. PR koşumu `33013632094` ve zorunlu exact-master
  dispatch `33014038693` ayrı ayrı **5026 passed / 30 skipped / 0 failed** verdi.
  Yalnız add-on'u hedefleyen private build exact `6dacfd5`ten tek, unsigned
  48.909.130 baytlık `85b9b249...fcd3b51` artifact üretti; repo ve resmî
  çıktı konumu değişmedi (`EV-20260826-082`). Bu kaynak build sonucu henüz
  Türkçe Ready/Geri→İleri veya kurulu bakım kabulü değildir.
- Exact `85b9b249...fcd3b51` insan kontrollü Türkçe same-version akışında tüm
  ekranları ve beş exact payload'ı geçti; yalnız beklenen uninstaller/InstallDate
  metadata'sı değişti (`EV-20260826-083`). Log/exit, silent ve uninstall ölçülmedi.
- Exact `ca4999d` dispatch'i **5058 passed / 30 skipped / 0 failed** verdi ve
  resmî zincir iki v0.40 setup ile doğrulanmış Ed25519 imzalarını üretti; iki
  EXE Authenticode `NotSigned` (`EV-20260827-011`).
- Ana v0.40 maintenance/upgrade 91/91 eşlik verdi; active add-on yt-dlp
  kapanmayınca Abort/rollback ile v0.39 kaldı (`EV-20260827-012`). Corrected
  URL önkoşulu da setup başlamadan FAILED; release bloklu (`EV-20260827-013`).
- Regression-first düzeltme izole `web_safari,visionos,web` allowlist ve mpv
  kaçışı getirdi; hedef **2/2**, aile **42 passed / 2 skipped**, py_compile/diff
  ve bağımsız inceleme temiz (`EV-20260827-014`); paket `3abdf13`, provenance kaydı `e64f8c2` (`EV-20260827-015`), EV016 ayrı ve uncommitted bir koruma kaydıdır. Eski URL FAILED; yeni kaynak ağ/native NOT_RUN.
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

Exact iki belgeli `EV-20260827-016` preservation kaydını ayrıca açık onayla commit et; push, build, kurulum, tag veya release başlatma.

## Sonraki sıra

1. Protected merge sonrası build ve fiziksel kabulü ayrı onaylarla sıfırdan
   uygula; silent/ikinci uninstall/invalid-target bitmeden tag/release yapma.
2. Kalan `P0-06`, `P0-07`, `P0-08` boşluklarını yayın sonrasına bırak.
3. Thumbnail timeline genişlemesinden önce kalıcı cache boyut/yaş temizleme
   politikasını ürün kararı olarak ele al.

## Dokunulmayacaklar ve ayrı onaylar

- Private görsel/native artifact yolları Git'e eklenmez.
- Ledger append-only kalır; eski kayıt silinmez, yeniden sıralanmaz veya yerinde
  düzeltilmez.
- Ürün kodu, build, kurulum/kaldırma, commit, push, PR, merge, tag ve release
  birbirinden ayrı açık kullanıcı onayı ister.
- Başarısız native/hosted çalışma neden incelenmeden otomatik tekrarlanmaz.

## Kanonik kayıt kaynakları

- Canlı durum ve tek sonraki adım: `docs/CONTINUITY.md`.
- Ayrılmış continuity kronolojisi: `docs/CONTINUITY_HISTORY.md`.
- Makinece kanıt: `docs/VERIFICATION_LEDGER.json`.
- Tarihsel ayrıntı: `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`,
  `docs/ENGINEERING_AUDIT.md`.
- Paketleme ve installer kararları: `docs/PACKAGING_PLAN.md`.
- Değişiklik akışı: `docs/CHANGE_WORKFLOW.md`.
- Yayın sırası: `docs/RELEASE_PROCESS.md`.
- Mimari kalite programı: `docs/QUALITY_EVOLUTION_PLAN.md`.
- Güncel mimari envanter: `docs/ARCHITECTURE_INVENTORY.md` ve
  `docs/ARCHITECTURE_INVENTORY.json`.
- Gerçek Windows senaryoları: `docs/WINDOWS_ACCEPTANCE_MATRIX.md` ve video
  formatı kabul dosyaları.
