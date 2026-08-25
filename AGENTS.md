# MLC Player agent başlangıç sözleşmesi

Bu dosya, projeyi devralan her agentın ilk giriş noktasıdır.

## Her oturumun başında

1. `git rev-parse --show-toplevel`, `git status --short --branch`,
   `git log -1 --oneline --decorate` ve `git rev-list --left-right --count
   HEAD...origin/master` ile doğru checkout'u ve farkı salt okunur doğrula.
2. Önce `docs/CONTINUITY.md` dosyasını oku. Güncel durum ve sıradaki tek
   adım yalnız oradadır.
3. İlgili kanıtı `docs/VERIFICATION_LEDGER.json` içinde kimliğiyle bul.
4. Yalnız görev gerektiriyorsa tarihsel ayrıntı için
   `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md` veya
   `docs/ENGINEERING_AUDIT.md` dosyasına git. Tarihçeden güncel durum çıkarma.
5. Kaynak, güncel durum ve eski rapor çelişirse yeniden ölçülen kaynak
   davranışı esas alınır; çelişki kayda geçirilir.
6. `docs/CHANGE_WORKFLOW.md` içindeki etkinlik kapısını kontrol et. PR kapısı
   aktifse doğrudan `master` değişikliği/push'u yapma; `codex/<kısa-konu>` dalı,
   zorunlu `test` check'i ve merge-commit sırasını kullan.
7. Mimari veya gerçek Windows kalite işi `docs/QUALITY_EVOLUTION_PLAN.md`
   üzerinden yürür. Güncel modül yorumu `docs/ARCHITECTURE_INVENTORY.md`,
   makinece güncellik kapısı `docs/ARCHITECTURE_INVENTORY.json`, gerçek cihaz
   senaryosu `docs/WINDOWS_ACCEPTANCE_MATRIX.md` içindedir; eksik/eskimiş
   satır sessizce PASS yapılmaz.

## Kanıt sınırları

- `deterministic`: kaynak/statik/hedef test kanıtıdır; gerçek DLL veya
  kullanıcı davranışını kanıtlamaz.
- `hosted_ci`: GitHub runner kanıtıdır; gerçek Windows masaüstü, native
  smoke veya kurulu paket kanıtı değildir.
- `source_build`: derleme ve karşılık gelen kaynak artifact'i kanıtıdır;
  ürün kabulü veya kurulum kanıtı değildir.
- `registry_artifact`: sabit OCI/container manifesti ve blob eşliği kanıtıdır;
  DLL derlemesi, native çalışma veya ürün kabulü değildir.
- `native_smoke`: gerçek native çalışma kanıtıdır; yalnız aynı commit,
  binary ve senaryoya aittir.
- `installed_artifact`: adı, boyutu ve SHA-256 değeri kaydedilmiş kurulum
  artifact'ına aittir; başka build'e taşınamaz.
- `external_submission`: üçüncü tarafın açık başarı/teslim ekranı kanıtıdır;
  uygunluk kararı, hesap, sertifika, imza veya ürün kabulü değildir.

Bir katmandaki PASS başka katmana aktarılmaz. `blocked`, `failed`, `skipped`
veya eksik marker hiçbir zaman PASS olarak yazılmaz.

## Sonuç kaydı zorunluluğu

Bir sonuç sonraki kararda kanıt olarak kullanılacaksa görev kapanmadan önce:

1. `docs/VERIFICATION_LEDGER.json` sonuna yeni ve benzersiz kayıt ekle.
2. Commit, tam komut veya GitHub run bağlantısı, sonuç özeti, kanıt sınırı
   ve sıradaki işlemi doldur.
3. `docs/CONTINUITY.md` içindeki güncel durum, son kanıt kimliği ve sıradaki
   tek adımı güncelle.
4. `python -m pytest -q tests/test_continuity_regressions.py` çalıştır.
5. Başarısız sonucu da kaydet; nedeni incelemeden otomatik tekrar yapma.

Eski kayıt değiştirilmez veya silinmez; yanlışsa yeni bir düzeltme kaydı
eklenir. Alan düzeltmesi yeni kaydın `corrects` listesinde hedef kayıt kimliği,
alan adı, yanlış değer ve doğrulanmış doğru değerle makinece belirtilir. CI,
PR tabanındaki ledger girdilerinin mevcut dosyanın birebir başlangıç bölümü
olduğunu doğrular; eski kayıt silme, yeniden sıralama veya yerinde yazma
fail-closed durur. Kayıt değişikliği de normal kod gibi kullanıcıya gösterilir
ve commit için ayrıca onay alınır.

Commit öncesi çalışma-ağacı kanıtında zorunlu `commit` alanı, ölçümün başladığı
exact committed tabanı gösterir; değişikliğin o commit'in içinde olduğunu
iddia etmez. Böyle bir kayıtta `baseline_commit`, `working_tree_state`,
`changed_files` ve çalıştırılan `commands` ayrıca yazılır. Private artifact
varsa yalnız güvenli adı ve SHA-256 değeri `private_artifact_digests` altında
tutulur; private yol depoya yazılmaz. Değişikliği içeren commit ancak
oluşturulup geri okunduktan sonra yeni bir kayıtla `evidence_commit` olarak
bağlanır. Eski kayıt yerinde değiştirilmez.

## Bağımsız çift-süzgeç

Birden fazla bağımsız konu veya doğrulama yüzeyi varsa uygun alt işler farklı
agentlara verilir. Gereksiz agent, aynı testin tekrarı veya aynı dosyaya paralel
yazma yapılmaz.

1. Uygulayan exact tabanı doğrular; mümkünse önce kırmızı regresyonu üretir,
   minimal değişikliği yapar ve yalnız hedef testi çalıştırır.
2. Karşıt inceleyen salt okunur başlar ve sonucu doğrulamaya değil çürütmeye
   çalışır. Maddi kod veya yönetişim değişikliğinde uygulayan ve karşıt
   inceleyen farklı agentlar olmalıdır; aynı agent kendi değişikliğinin tek
   nihai PASS kaynağı olamaz.
3. Entegratör ham diff ve kanıtı kaynak üzerinden değerlendirir; her bulguyu
   `fixed`, `accepted risk` veya `rejected with evidence` olarak kapatır.
4. Aynı checkout'ta tek yazma sahibi vardır. Ledger ve continuity yalnız
   entegrasyon sahibi tarafından güncellenir. Bağımsız yazarlık gerekiyorsa
   ayrı worktree, aynı exact base ve açık diff kimliği kullanılır.
5. Test basamakları etkiyle sınırlıdır: hedef kırmızı/yeşil, bir etki ailesi,
   karşıt inceleyenin yeni sınır testi ve PR'de tek tam hosted paket. Native,
   build ve kurulum yalnız ayrı onaylı exact senaryoda çalışır.
6. Kaynak ağacı özeti, ortam, komut, fixture/runtime/artifact kimliği
   değişmediyse mevcut kanıt yeniden kullanılır; aynı pahalı koşum sırf ikinci
   agent için tekrarlanmaz.

## Kalıcı çalışma kuralları

- Kullanıcıyla Türkçe, kısa ve karar odaklı konuş.
- Kirli çalışma ağacını ve kullanıcı dosyalarını koru.
- Etki alanına uygun dar test kullan; aynı tam paketi gereksiz tekrarlama.
- Ürün kodu, hosted/deterministik kanıt, native smoke ve kurulu artifact
  kanıtını ayrı raporla.
- Build, kurulum/kaldırma, commit, push, PR oluşturma, PR birleştirme, tag ve
  release ayrı ayrı açık kullanıcı onayı ister.
- Force-push ve GitHub protection bypass yapılmaz.
- Yayın sırasının tek resmî kaynağı `docs/RELEASE_PROCESS.md` dosyasıdır.
