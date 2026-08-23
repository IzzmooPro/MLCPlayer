# MLC Player mimari ve gerçek Windows kalite planı

**Durum:** AKTİF

**Başlangıç tabanı:** `78518dd67e882e35da69ea7bb6bfc74e3cafc1c7`

**Başlangıç tarihi:** 23 Ağustos 2026

Bu plan iki gerçek riski kontrollü biçimde azaltır:

1. büyük UI/oynatma modüllerinin bakım ve yan etki riski;
2. deterministik/hosted testlerle gerçek Windows davranışı arasındaki boşluk.

Amaç daha fazla dosya veya test sayısı üretmek değil; her değişikliğin nedenini,
kanıtını, sınırını ve sıradaki adımını başka bir geliştiricinin yeniden araştırma
yapmadan bulabilmesini sağlamaktır.

## Değişmez sınırlar

- Büyük patlama biçiminde toplu refactor yapılmaz.
- Satır sayısı tek başına bölme gerekçesi değildir.
- Mimari çalışma sırasında kullanıcıya görünen davranış değişikliği yapılmaz.
- Önce mevcut davranış ve sahiplik ölçülür, sonra tek sorumluluk seçilir.
- Aynı turda hem geniş refactor hem yeni özellik yapılmaz.
- Otomatik, native ve kurulu-artifact sonuçları birbirinin yerine kullanılmaz.
- Gerçek cihaz koşumu, build ve kurulum her zamanki ayrı açık onaylara tabidir.
- Başarısız sonuç nedeni incelenmeden otomatik tekrarlanmaz.

## Tek kaynak ve güncellik düzeni

| Bilgi | Tek resmî kaynak | Ne zaman güncellenir |
| --- | --- | --- |
| Güncel durum ve sıradaki tek adım | `docs/CONTINUITY.md` | Her karar/kanıt turunun sonunda |
| Makinece okunabilir sonuç | `docs/VERIFICATION_LEDGER.json` | Sonraki kararda kullanılacak her sonuçta |
| Bu programın faz ve kapıları | `docs/QUALITY_EVOLUTION_PLAN.md` | Faz başlarken veya kapanırken |
| Modül sahipliği ve ayrıştırma adayları | `docs/ARCHITECTURE_INVENTORY.md` | Ölçüm veya sahiplik değiştiğinde |
| Altı büyük modülün hash/yapı güncellik kapısı | `docs/ARCHITECTURE_INVENTORY.json` | Bu altı kaynaktan biri değiştiğinde |
| Gerçek Windows senaryoları | `docs/WINDOWS_ACCEPTANCE_MATRIX.md` | Senaryo/ortam/artifact sonucu değiştiğinde |
| Yayın sırası | `docs/RELEASE_PROCESS.md` | Yalnız yayın sözleşmesi değiştiğinde |
| Tarihsel anlatı | `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, `docs/ENGINEERING_AUDIT.md` | Tarihsel checkpoint gerektiğinde |

Tarihsel belgeler güncel karar kaynağı değildir. Güncel kaynakla çelişen eski
yorum sessizce düzeltilmez veya karar olarak kullanılmaz; yeni ölçüm ve gerekirse
yeni ledger kaydı eklenir.

Bir faz tamamlandığında plan durumu, ilgili envanter/matris, ledger kaydı ve
`CONTINUITY.md` içindeki sıradaki tek adım **tek güncelleme işlemi** olarak ele
alınır. Ardından etki alanına uygun dar test ve continuity testi çalıştırılır.
Başarısız sonuç da gerçek sonucu ve incelenen nedeni ile kaydedilir.

## Faz 0 — Kalıcı sözleşme

**Durum:** TAMAMLANDI

- Bu planı, ilk mimari envanteri ve Windows kabul matrisini oluştur.
- Agent başlangıç sözleşmesini üç dosyaya bağla.
- Belgelerin varlığını, kanıt sınırlarını ve güncellik işlemini regresyonla
  koru.

Çıkış kapısı: dar belge testleri yeşil, ledger geçerli, continuity yeni tek
adıma işaret ediyor ve ürün kodunda değişiklik yok.

## Faz 1 — Salt okunur mimari envanter

**Durum:** TAMAMLANDI

Önce `docs/ARCHITECTURE_INVENTORY.md` tamamlanır. Her büyük modül için:

- kullanıcıya görünen sorumluluklar;
- state, timer, thread, process ve native kaynak sahipliği;
- doğrudan bağımlılıklar ve geri çağrı yönleri;
- mevcut deterministik ve native test kapsaması;
- geçmiş kusur yoğunluğu;
- güvenli ayrıştırma dikişleri ve ayrıştırmama gerekçeleri

kaydedilir. Bu faz ürün kodunu değiştirmez.

Çıkış kapısı: en az altı büyük modül aynı ölçütlerle değerlendirilmiş, ilk
refactor adayı yalnız satır sayısına değil ölçülen sahiplik/bağımlılık riskine
göre seçilmiş ve kapsam kullanıcıya sunulmuş olmalıdır.

## Faz 2 — Gerçek Windows başlangıç kabulü

**Durum:** AKTİF — P0 EŞLEMESİ TAMAM, ÇEKİRDEKTE 1 PASS / 1 FAIL

`docs/WINDOWS_ACCEPTANCE_MATRIX.md` içindeki P0 senaryoları exact commit,
runtime ve mümkünse artifact SHA-256 kimliğiyle çalıştırılır. Var olan native
runner'lar yeniden kullanılır; aynı davranış için ikinci bir test sistemi
yazılmaz. Donanım yoksa sonuç `BLOCKED` kalır, PASS yapılmaz.

Sekiz P0 satırının deterministik sınırı, mevcut native ölçümü, exact girdisi
ve açık boşluğu matriste kayıtlıdır. Bu eşleme hiçbir satırı PASS yapmaz.
Gerçek koşumlar kısa otomatik çekirdek, fiziksel etkileşim ve eksik kabul
paketleri olarak ayrı onaylarla ilerler.

Exact `69af424` kaynak-native çekirdeğinde kanonik açılış/kapanış geçti;
tek-videolu overlay runner'ı gerçek oynatma kanıtından sonra kendi eski
teardown sırası nedeniyle `0xC0000005` ile başarısız oldu. Otomatik tekrar
yapılmaz; `EV-20260823-019/020` ve Windows matrisi güncel karar kaynağıdır.
Test-only harness kapanışı `EV-20260823-021` ile deterministik olarak
düzeltildi; gerçek retry yapılmadan P0-02 durumu yükseltilmez.
Exact `98f4440` retry'sı geç UI hatalarını temizledi fakat child normal
Python/libmpv finalizasyonunda `MARK_DONE` sonrasında yine başarısız oldu
(`EV-20260823-022`). Finalizasyon sözleşmesi düzeltilmeden P0-02 yükseltilmez.
Test-only finalizasyon yolu `EV-20260823-023` ile flush + `os._exit`
sözleşmesine alındı; deterministik etki grubu **103 passed / 2 skipped**
verdi. Native retry yapılmadığı için P0-02 hâlâ **FAILED** durumundadır.

Çıkış kapısı: P0 satırlarının her biri PASSED, FAILED veya gerekçeli BLOCKED;
çocuk süreç exit kodu, final marker, stderr ve süreç sızıntısı sınırları açık;
kanıt yalnız kullanılan commit/runtime/artifact'a bağlıdır.

## Faz 3 — İlk küçük mimari ayrıştırma

**Durum:** PLANLANDI

Faz 1 ve Faz 2 tamamlanmadan başlamaz. Tek tur sırası:

1. ayrılacak sorumluluğu ve kullanıcı davranışını yaz;
2. mevcut davranışı dar regresyonla kilitle;
3. yalnız bir sorumluluğu taşı;
4. hedef testleri çalıştır;
5. ilgili P0 native senaryosunu ayrı onayla çalıştır;
6. karmaşıklık azalmadıysa değişikliği genişletme.

İlk dosya otomatik olarak `video_frame.py` seçilmez. Envanter sonucu başka bir
modül daha güvenli ve daha yüksek kazanımlıysa önce o ele alınır.

## Faz 4 — Kontrollü tekrar

**Durum:** PLANLANDI

Her başarılı ayrıştırmadan sonra envanter ve matris güncellenir. Bir sonraki
adım ancak önceki değişikliğin hosted ve gerekli gerçek davranış kanıtı kendi
sınırları içinde tamamlandığında seçilir. Tam paket, build veya kurulum yalnız
ortak altyapı/yayın etkisi varsa ve ayrı onayla çalıştırılır.

## Başarı ölçütü

Başarı, dosya veya satır sayısının azalması değildir. Aşağıdaki sonuçların
birlikte görülmesidir:

- bir kullanıcı davranışının tek ve açık sahibi vardır;
- state/thread/native yaşam döngüsü sınırı daha nettir;
- aynı davranışın testi daha dar ve anlaşılırdır;
- sonraki geliştirici güncel durumu resmî dosyalardan çıkarabilir;
- gerçek Windows kanıtı exact commit/runtime/artifact dışına taşınmaz.
