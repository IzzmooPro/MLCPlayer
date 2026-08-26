# MLC Player güncel devam noktası

Bu dosya projenin tek canlı devir noktasıdır. Tarihsel continuity kronolojisi
`CONTINUITY_HISTORY.md`, makinece doğrulanmış olaylar
`VERIFICATION_LEDGER.json`, diğer tarihsel anlatı `PROJECT_STATUS.md`,
`ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 26 Ağustos 2026
- Kayıt hazırlanırken doğrulanan HEAD: `7dcf8e097ee7966c8326381ea0102d174e9adcbd`
- Güncel HEAD/origin farkı: her oturumda `git rev-list --left-right --count
  HEAD...origin/master` ile canlı ölçülür; bu belge kendi commit hash'ini
  önceden tahmin etmez.
- Dal: `codex/installer-experience` (`origin/master`dan 6 commit ileride)
- Son kanıt: `EV-20260826-038`
- Yayın kararı: **v0.39 canlı ve latest; 87 yayın varlığı eş, public indirme,
  kurulum, açılış ve gerçek medya oynatma kullanıcı kabulü geçti.**

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
- `codex/installer-ux-c-selection` görev dalı exact `ce8211b` head'iyle origin'e
  push edildi ve yerel/uzak görev dalı `0/0` eş okundu (`EV-20260826-009`). PR
  #50 daha sonra exact `e262c0c` head'iyle açıldı. Zorunlu hosted run
  `32937990279`, **4967 passed / 30 skipped / 0 failed** ve
  `LEDGER_APPEND_ONLY_OK` verdi (`EV-20260826-010`). Bu continuity yenilemesi
  yeni head oluşturacağından aynı eski run merge yetkisi vermez.
- Continuity yenilemesinin exact `acccb87` head'indeki yeni zorunlu run
  `32944386076`, **4967 passed / 30 skipped / 0 failed** ve
  `LEDGER_APPEND_ONLY_OK` verdi (`EV-20260826-011`). PR OPEN/MERGEABLE/CLEAN ve
  required `test=SUCCESS` okundu; aşağıdaki canlı kapı yenilemesi yeni head
  oluşturacağından bu run da yalnız `acccb87` için geçerlidir.
- Kalıcı canlı kapının exact `4ad4999` head'indeki zorunlu run `32945821716`,
  **4967 passed / 30 skipped / 0 failed** ve `LEDGER_APPEND_ONLY_OK` verdi. Ayrı
  onay sonrasında PR #50 iki ebeveynli exact `33680f4` merge commit'iyle
  protected master'a alındı; parent'lar `b7e7cdd` ve `4ad4999`, yerel/uzak
  master `0/0` ve görev dalı korundu (`EV-20260826-012`).
- Post-merge kayıt hazırlanırken continuity testi önce **9 passed / 1 failed**
  verdi: uzayan canlı adım, oturum hook'unun 12 satırlık sınırında kesiliyordu
  (`EV-20260826-013`). Terminal kuralı ayrı bölüme taşındı; hook veya limit
  değiştirilmeden aynı dar paket **10 passed** oldu (`EV-20260826-014`).
- PR #51 kayıt paketi protected master'a iki ebeveynli exact `db96ac5` merge
  commit'iyle alındı; parent'lar `33680f4` ve `e9be732`, exact hosted run
  `32949577656` **249 passed / 0 failed** ve `LEDGER_APPEND_ONLY_OK` verdi,
  yerel/uzak master `0/0` okundu. Bu provenance ilk gerçek C ekran-sözleşmesi
  kaydında bağlandı (`EV-20260826-017`).
- C ekran-sözleşmesi PR #52 ile exact `f0a91ad` merge commit'ine alındı
  (parent `db96ac5` + `12ac711`); hosted run/job `32953472410/98129903318`
  **4969 passed / 30 skipped**, ledger temiz ve master `0/0` (`EV-20260826-028`).
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
- Ayrı commit onayıyla C ekran-sözleşmesi paketi exact `9467db3` commit'ine
  bağlandı; parent `db96ac5`, kapsam dört beklenen belge/test dosyası ve dal
  temiz readback'te `origin/master`dan 1 commit ilerideydi (`EV-20260826-023`).
- Commit-readback kaydı exact `531127b` commit'iyle bağlandı ve ayrı push
  onayıyla yeni `origin/codex/installer-c-screen-contract` dalına gönderildi;
  yerel/uzak görev dalı exact `531127b`, `0/0` ve temiz okundu. PR açılmadı
  (`EV-20260826-024`).
- Push/readback kaydı exact `f794670` commit'iyle bağlandı ve ayrı onayla aynı
  uzak görev dalına gönderildi; yerel/uzak dal exact `f794670`, `0/0` ve temiz
  okundu (`EV-20260826-025`). Aşağıdaki dayanıklı kapı ilk karşılanmayan
  durumu seçer; sırf her push'u yeniden kaydetmek için meta-kayıt döngüsü kurmaz.
- Installer C kaynağı `6fe453f`, kayıt commit'i `5c04c2d`dir
  (`EV-20260826-028`, `-029`). İki syntax hatası regression-first kapandı (`-030`);
  build exit 0, 56,344,277 byte, `c65a5fbc...3c3bb39`, NotSigned (`-031`). Pre-install
  görseli reddedildi; `Kur` çalışmadı ve süreç sızıntısı yoktu (`-032`).
- C v2 `326f9be`ye bağlı (`-033`, `-034`); ilk build hexte durdu, setup/sızıntı yok (`-035`). Minimal
  fix regression-first **44 passed**, açık P0/P1 olmadan exact `f96482a`ya
  bağlandı (`-036`, `-037`). Exact `7dcf8e0` rebuild exit 0, setup 56,565,837
  byte/`30ce2986...f9a69c`, NotSigned (`-038`); henüz launch/görsel kabul değil.
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

Merge-kayıt PR'ı protected master'a ulaştığında sırf meta-merge'i yeniden
kaydetmek için yeni bir ledger/PR zinciri başlatma. Protected-master merge
commit/parent/run ve `0/0` readback'ini sonraki ilk gerçek C ekran-sözleşmesi
kaydında provenance olarak bağla; ardından ekran metni, odak ve akış işine geç.

## Sıradaki tek adım

Exact build kaydını commit etmek için ayrıca açık onay iste; setup launch,
`Kur`, kurulum ve finish action yetkisi bu onaydan çıkarılmaz.

## Sonraki sıra

1. Commit readback'inden sonra exact Inno 7.1.0 build için ayrıca onay al;
   ardından yeni setup'ın ileri/geri görsel incelemesini ve fiziksel kurulumu
   birbirinden ayrı onaylat.
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
