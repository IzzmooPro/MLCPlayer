# MLC Player güncel devam noktası

Bu dosya projenin tek canlı devir noktasıdır. Tarihsel continuity kronolojisi
`CONTINUITY_HISTORY.md`, makinece doğrulanmış olaylar
`VERIFICATION_LEDGER.json`, diğer tarihsel anlatı `PROJECT_STATUS.md`,
`ROADMAP.md` ve `ENGINEERING_AUDIT.md` içindedir.

- Güncelleme: 26 Ağustos 2026
- Kayıt hazırlanırken doğrulanan HEAD: `6428af94125514876f6e8b15d07ea1d02111dccf`
- Güncel HEAD/origin farkı: her oturumda `git rev-list --left-right --count
  HEAD...origin/master` ile canlı ölçülür; bu belge kendi commit hash'ini
  önceden tahmin etmez.
- Dal: `master` (yerel çalışma dalı farklı ad taşıyabilir)
- Son kanıt: `EV-20260826-004`
- Yayın kararı: **v0.39 canlı ve latest; 87 yayın varlığı eş, public indirme,
  kurulum, açılış ve gerçek medya oynatma kullanıcı kabulü geçti.**

## Canlı ürün ve yayın durumu

- Belge/yönetişim paketi exact `6308d55` commit'indedir. Yerel görev dalı
  `origin/master`dan iki commit ileridedir ve remote görev dalıyla exact
  `567328f` üzerinde eşittir. PR #48 açıktır; merge yapılmadı.
- PR #48'in exact head'inde ilk zorunlu hosted run `32899094320`, **4965
  passed / 30 skipped / 1 failed** verdi (`EV-20260826-002`). Tek hata
  `PACKAGING_PLAN.md` için stale bütün-belge-tarihsel testiydi; otomatik retry
  yapılmadı.
- Semantik sahiplik düzeltmesi `EV-20260826-003` ile kanıtlandı: güncel UX,
  kalıcı paketleme kararları ve tarihsel snapshot ayrımı dar grupta
  **13 passed** ve bağımsız karşıt incelemede bloklayıcı bulgusuzdur. Düzeltme
  exact `6428af9` commit'indedir; yerel görev dalı remote görev dalından bir
  commit ileridedir. `EV-20260826-004` bağlantı kaydı henüz çalışma ağacındadır.
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
  yönü hazırdır: A Sinematik Gece, B Windows ile Uyumlu, C Dengeli Hibrit.
  Kullanıcı henüz A/B/C seçimi yapmadı; bitmap'ler Git'e alınmaz ve gerçek
  Inno Setup davranışı sayılmaz.
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

## Sıradaki tek adım

Üç installer önizlemesi arasından kullanıcının açık A, B veya C görsel yön
seçimini al. Seçimden önce installer kodu, build veya kurulum yapma.

## Sonraki sıra

1. Seçilen installer yönünün metin, odak ve ekran akışını kesinleştir;
   uygulama değişikliği için ayrıca açık onay al.
2. Installer uygulamasını ayrı `codex/installer-experience` dalında
   regresyon-first yürüt; build ve fiziksel kurulumu ayrı ayrı onaylat.
3. Kalan `P0-03`, `P0-06`, `P0-07`, `P0-08` boşlukları için mevcut runner'ı
   yeniden kullanarak dar kabul sırasını belirle.
4. Thumbnail timeline genişlemesinden önce kalıcı cache boyut/yaş temizleme
   politikasını ürün kararı olarak ele al.
5. Internet Video add-on güven ve eş-sürüm zincirini fail-closed tasarla;
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
