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

## Kanıt sınırları

- `deterministic`: kaynak/statik/hedef test kanıtıdır; gerçek DLL veya
  kullanıcı davranışını kanıtlamaz.
- `hosted_ci`: GitHub runner kanıtıdır; gerçek Windows masaüstü, native
  smoke veya kurulu paket kanıtı değildir.
- `source_build`: derleme ve karşılık gelen kaynak artifact'i kanıtıdır;
  ürün kabulü veya kurulum kanıtı değildir.
- `native_smoke`: gerçek native çalışma kanıtıdır; yalnız aynı commit,
  binary ve senaryoya aittir.
- `installed_artifact`: adı, boyutu ve SHA-256 değeri kaydedilmiş kurulum
  artifact'ına aittir; başka build'e taşınamaz.

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
eklenir. Kayıt değişikliği de normal kod gibi kullanıcıya gösterilir ve
commit için ayrıca onay alınır.

## Kalıcı çalışma kuralları

- Kullanıcıyla Türkçe, kısa ve karar odaklı konuş.
- Kirli çalışma ağacını ve kullanıcı dosyalarını koru.
- Etki alanına uygun dar test kullan; aynı tam paketi gereksiz tekrarlama.
- Ürün kodu, hosted/deterministik kanıt, native smoke ve kurulu artifact
  kanıtını ayrı raporla.
- Build, kurulum/kaldırma, commit, push, tag ve release ayrı ayrı açık
  kullanıcı onayı ister.
- Yayın sırasının tek resmî kaynağı `docs/RELEASE_PROCESS.md` dosyasıdır.

