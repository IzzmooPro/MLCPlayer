# MLC Player değişiklik ve PR iş akışı

Bu dosya, `master` için PR + zorunlu GitHub Actions kontrolü etkin olduğunda
kullanılacak **tek değişiklik-akışı sözleşmesidir**. Yayın artifact sırası
yalnız `docs/RELEASE_PROCESS.md` içindedir.

## Etkinlik kapısı

Bu belge tek başına GitHub ayarını etkinleştirmez. PR kapısı yalnız canlı
GitHub protection read-back sonucunda şu iki koşul birlikte görülürse aktiftir:

- `master` değişikliği pull request gerektiriyor;
- GitHub Actions uygulamasından gelen tam **`test`** check'i zorunlu.

Güncel etkinlik durumu `docs/CONTINUITY.md` içindedir. Kaynak belge ile canlı
GitHub ayarı çelişirse değişiklik yapılmaz; önce salt-okunur read-back sonucu
kanıt defterine kaydedilir.

## Normal değişiklik sırası

1. Temiz ve eşit başlangıcı doğrula:

   ```powershell
   git status --short --branch
   git rev-list --left-right --count HEAD...origin/master
   ```

2. `master` üzerinden görev dalı aç: `codex/<kısa-konu>`. Kirli ağaç veya
   origin farkı varsa dal değiştirme; kullanıcı dosyalarını koru.
3. Yalnız görev kapsamını değiştir, etki alanına uygun dar testleri çalıştır ve
   karar kanıtını ledger/continuity sözleşmesine göre kaydet.
4. Commit için ayrı, görev dalını push etmek için ayrı açık kullanıcı onayı al.
5. PR oluşturmak için ayrıca açık onay al. PR hedefi `master`, kaynak dalı
   `codex/<kısa-konu>` olmalı; başlık ve açıklama gerçek değişiklik, test ve
   kanıt sınırını belirtmeli.
6. GitHub Actions **`test`** check'ini bekle:

   - `success`: birleşme adayıdır;
   - `failure`: otomatik tekrar yok; ilk gerçek hata incelenir, düzeltme aynı
     görev dalına ayrı commit olarak gider;
   - `queued` / `in_progress`: PASS değildir;
   - GitHub kesintisi veya eksik check: koruma bypass edilmez.

7. Birleştirme için ayrı açık kullanıcı onayı al. **Merge commit** kullan;
   squash/rebase kullanma. Böylece ledger içindeki doğrulanmış commit kimlikleri
   korunur.
8. Birleşme sonrası yerel `master` yalnız temiz ağaçta fast-forward edilir ve
   origin eşliği yeniden ölçülür. Görev dalı ancak sonuç kaydı tamamlandıktan
   sonra silinebilir.

## Neden sıfır inceleme onayı

Proje tek yöneticiyle yürütülüyor. İlk PR kapısı kod inceleme sayısını değil,
izlenebilir PR kaydını ve zorunlu `test` sonucunu hedefler. Bu nedenle planlanan
ayar **PR gerekli, approving review sayısı 0** biçimindedir. İkinci bir düzenli
bakımcı oluşursa review sayısı ayrıca kararlaştırılır.

## Yetkilendirme sınırları

Branch oluşturma yerel ve geri alınabilirdir; fakat commit, görev dalı push'u,
PR oluşturma, PR birleştirme, tag ve release birbirinden ayrı açık kullanıcı
onayı ister. Bir onay diğerine aktarılmaz. Force-push ve protection bypass
yapılmaz.

## Yayınla birleşimi

Sürüm alanı değişikliği de önce bu PR kapısından geçer. PR merge commit'i
origin/master üzerinde ve hosted `test` yeşil olduktan sonra yerel `master`
aynı commit'e fast-forward edilir. Build, fiziksel kabul, kaynak staging ve
yerel annotated tag bu **exact merge commit** üzerinde yürür.

Bu durumda yayın sürecindeki `git push origin master` bir değişiklik taşımaz;
yalnız yerel HEAD ile origin/master eşliğini doğrular. Tag push'u ve release
yine `docs/RELEASE_PROCESS.md` sırasına ve ayrı onaylara tabidir.

## Planlanan GitHub koruması

Etkinleştirme ayrıca açık GitHub-ayar onayı ister. Hedef yapı:

- administrators enforced;
- pull request required, approving reviews `0`;
- required check: **`test`**, kaynak GitHub Actions;
- branch must be up to date before merging;
- force push kapalı, branch deletion kapalı;
- bypass actor yok.

Etkinleştirmeden sonra canlı API read-back ve küçük bir deneme PR'ı ayrı kabul
kanıtıdır. Ayar var diye PR davranışı ölçülmeden PASS yazılmaz.
