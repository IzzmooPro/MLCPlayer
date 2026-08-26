# MLC Player güncel devam noktası

Bu dosya projenin tek canlı devir noktasıdır. Tarihsel continuity kronolojisi
`CONTINUITY_HISTORY.md`, makinece doğrulanmış olaylar
`VERIFICATION_LEDGER.json`, diğer tarihsel anlatı `PROJECT_STATUS.md`,
`ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 26 Ağustos 2026
- Kayıt hazırlanırken doğrulanan HEAD: `98c9511a81943fcc84a6e6652a2ca24f3a9ba74e`
- Güncel HEAD/origin farkı her oturumda `git rev-list --left-right --count` ile ölçülür; bu belge kendi commit hash'ini tahmin etmez.
- Dal: `codex/v040-installed-acceptance` (exact `origin/master` tabanı; yalnız ledger/continuity kayıt değişikliği kirli)
- Son kanıt: `EV-20260826-079`
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

- Windows P0 matrisi: `WIN-P0-01`, `WIN-P0-02`, `WIN-P0-04` ve `WIN-P0-05`
  PASSED; track değiştirme, drag/drop, playlist sınırları ve IPC için
  `P0-03`, `P0-06`, `P0-07`, `P0-08` NOT_RUN.
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
- C ekran-sözleşmesinin commit/push provenance'ı `EV-20260826-023`–`025`
  kayıtlarında korunur; continuity meta-kayıt döngüsü başlatmaz.
- Installer C kaynağı `6fe453f`, kayıt commit'i `5c04c2d`dir
  (`EV-20260826-028`, `-029`). İki syntax hatası regression-first kapandı (`-030`);
  build exit 0, 56,344,277 byte, `c65a5fbc...3c3bb39`, NotSigned (`-031`). Pre-install
  görseli reddedildi; `Kur` çalışmadı ve süreç sızıntısı yoktu (`-032`).
- C v2 `326f9be`ye bağlı; ilk build durdu, fix `f96482a`, rebuild `7dcf8e0`/
  `30ce2986...f9a69c` oldu (`-033`–`-038`). Kullanıcı v2'yi görmeden iptal etti;
  önceki ekran beş compiler fix'iyle exact `d1dc658`e bağlandı, **58 passed**
  (`-039`, `-040`). Eski `c65...` EXE yoktur; v2 EXE restore kaynağını temsil etmez.
- Restore build'inde Welcome döndü, ilk Summary reddedildi (`-041`, `-042`); `ReadyMemo` düzeltmesi
  `5611c0c`e bağlandı (`-043`, `-044`), exact `da6c21e` build'i `cc1021...a274d` verdi (`-045`).
- Dist PASS'ti; reinstall yeni EXE'yi kopyaladı ama eski 47 root DLL'yi bırakarak FAILED oldu.
  Fix `83a0fef`; full gate **5023/19**; `89e2395` build'i setup `90e8ccd1...0698ffb`, Player `9a5fc567...a037d60` verdi (`-059`–`-066`).
  Exact 49 cleanup `ddeac9c`/setup `c480...`; residual/missing/mismatch `0`, Progress ve installed Launch geçti (`-067`–`-074`).
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

Exact v0.40 Internet Video add-on için tam main/add-on sahiplik ve aktif-ayar
baseline'ından kullanıcı kontrollü interaktif aynı-sürüm maintenance senaryosunu
çalıştır; bunu upgrade diye adlandırma ve henüz uninstall/rollback başlatma.

## Sonraki sıra

1. Dist launch geçerse mevcut 47-DLL bozuk kurulumu elle temizlemeden exact
   setup ile kullanıcı kontrollü reinstall ve ekran görüntüsü kabuline geç.
2. Kalan `P0-03`, `P0-06`, `P0-07`, `P0-08` boşlukları için mevcut runner'ı
   yeniden kullanarak dar kabul sırasını belirle.
3. Thumbnail timeline genişlemesinden önce kalıcı cache boyut/yaş temizleme
   politikasını ürün kararı olarak ele al.
4. Internet Video add-on güven ve eş-sürüm zincirini fail-closed tasarla;
   uygulama, build ve kurulum için ayrı onay al.

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
