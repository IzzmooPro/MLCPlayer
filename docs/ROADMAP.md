# MLC Player yol haritası

**Snapshot: 17 Ağustos 2026** — tam paket milestone koşumu ve TEST-002
turunun ardından güncellendi. Bu belge her kabul edilen turun sonunda
yenilenir; buradaki durumlar o tarihteki ölçümleri yansıtır, kalıcı
gerçek değildir.

Durum sözlüğü `docs/ENGINEERING_AUDIT.md` içindedir; aynı kelimeler
burada da kullanılır. Yayın sırası burada tekrarlanmaz:
`docs/RELEASE_PROCESS.md`.

Her maddede dört alan vardır: **Durum**, **Bagimlilik**, **Olcut**
(tamamlanma ölçütü) ve **kullanıcı onayı** gerekip gerekmediği.

## Su anki asama

Yayın altyapısı sertleştirme turunda beş kusur (REL-001…REL-005) hedef
testlerle kapatıldı ve üç mantıksal yerel commit'e ayrıldı. **Push
yapılmadı**; canlı bir build/yayın koşumu da yapılmadı. Sıradaki teknik
risk, tam paket koşumunda yeniden görülen `0xe24c4a02` istisnasıdır.

---

## Tamamlanan ve hedef testle dogrulanan isler

### Runtime bütünlüğü (REL-001)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI (`96a8f52`)
- **Bagimlilik:** yok
- **Olcut:** `--pre` üç runtime'ı boyut + SHA-256 ile doğruluyor → sağlandı (52 passed, canlı exit 0)
- **Kullanici onayi:** commit verildi ve uygulandı; push ayrı onay ister

### Tag ↔ kaynak bütünlüğü (REL-002)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI
- **Bagimlilik:** yok
- **Olcut:** tag adı, dört sürüm alanı ve HEAD doğrulanıyor → sağlandı (45 passed)
- **Kullanici onayi:** commit verildi ve uygulandı; push ayrı onay ister

### Kesin artifact seçimi (REL-003)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI (`85dda6d`), CANLI KABUL BEKLIYOR
- **Bagimlilik:** gerçek Windows build
- **Olcut:** zincir uçtan uca koşup doğru sürümü imzalamalı
- **Kullanici onayi:** commit uygulandı; canlı build ayrıca onay ister

### Yerel yayın kapısı (REL-004)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI, CANLI KABUL BEKLIYOR
- **Bagimlilik:** REL-002, REL-003
- **Olcut:** gerçek bir yayın adayında exit 0 vermeli
- **Kullanici onayi:** commit uygulandı; push/release ayrı onay ister

### build/dist temizliği doğrulaması (REL-005)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI (`85dda6d`), CANLI KABUL BEKLIYOR
- **Bagimlilik:** REL-003 (aynı betik), gerçek Windows build
- **Olcut:** `rmdir` başarısız olduğunda zincir gerçekten durmalı — kilitli klasörle canlı koşumda görülmeli
- **Kullanici onayi:** commit uygulandı; canlı build ayrıca onay ister

### Süreç belgesi tekilleştirmesi (DOC-001)
- **Durum:** HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI, TAMAMLANDI
- **Bagimlilik:** yok
- **Olcut:** a–j yalnız `RELEASE_PROCESS.md` içinde → sağlandı
- **Kullanici onayi:** commit verildi ve uygulandı

---

## Tam paket milestone kosumu (17 Agustos 2026)

- **Durum:** HEDEF TESTLERLE DOGRULANDI (hedef kapanış)
- **Bagimlilik:** REL-001…REL-005
- **Olcut:** tek failure kapatılmış olmalı → sağlandı
- **Kullanici onayi:** gerekmez (ölçüm)

Gerçek sonuç: **3931 passed / 17 skipped / 1 failed**, **100,01 sn**.
Taban 3716/17 idi; artış eklenen regresyon dosyalarındandır.

Tek failure ürün kusuru değildi: bayat `ADDON_TO_SIGN` test assertion'ı
(TEST-002). **Hedef testle kapatıldı** — bu bir *hedef kapanıştır*,
ürün davranışı değişmedi.

**Tam paket bu test-only düzeltmeden sonra BİLEREK yeniden
çalıştırılmadı.** 3931 yeşil testi tek bir test dosyası değişikliği için
yeniden koşturmak ölçüm değil, tekrardır. Bir sonraki tam koşum commit
öncesinde yapılacak.

## Commit checkpoint sonucu

- **Durum:** TAMAMLANDI (hedef kapanış kanıtıyla)
- **Bagimlilik:** yukarıdaki milestone
- **Olcut:** tam `pytest -q tests` yeşil (0 failed); milestone 3931/17/1 ile karşılaştırılıp fark açıklanmış; `compileall` ve `git diff --check` temiz
- **Kullanici onayi:** verildi; üç yerel commit oluşturuldu, push yapılmadı

---

## Uzak release dogrulama otomasyonu

- **Durum:** ERTELENDI
- **Bagimlilik:** REL-004
- **Olcut:** `refs/tags/vX.Y^{}` peeled commit'i ve uzak varlık ad/boyut/SHA-256 eşliği mekanik denetlenmeli (şu an elle: adım g ve i)
- **Kullanici onayi:** gerekmez (salt-okunur), ama ağ kullanır — `prepublish` kapısına eklenmez, ayrı araç olur

---

## Genel mimari / guvenilirlik denetimi

- **Durum:** ERTELENDI
- **Bagimlilik:** yok
- **Olcut:** kapanış yaşam döngüsü, thread sahipliği ve hata sınırları tek tek ölçülmüş; bilinen aralıklı child takılmasının kök nedeni bulunmuş
- **Kullanici onayi:** gerekmez (inceleme)

---

## Performans ve gecikme denetimi

- **Durum:** ERTELENDI
- **Bagimlilik:** yok
- **Olcut:** açılış süresi, ilk kare gecikmesi ve seek gecikmesi gerçek 4K medyayla ölçülmüş; resize donması turundaki gibi öncesi/sonrası tablosu çıkarılmış
- **Kullanici onayi:** GUI/native koşum için **gerekir**

---

## Test / CI / bagimlilik denetimi

- **Durum:** ERTELENDI
- **Bagimlilik:** "Commit öncesi yapılacaklar"
- **Olcut:** tam paket süresi ve kararlılığı kayıtlı; bağımlılık sürümleri sabitlenmiş
- **Kullanici onayi:** gerekmez

## SIRADAKI TEKNIK RISK: `0xe24c4a02` (NATIVE-001)

- **Durum:** GORUNURLUK KUSURU KAPATILDI (HEDEF TESTLERLE DOGRULANDI, COMMIT EDILDI); **kök neden ERTELENDI**
- **Bagimlilik:** yok — commit'i beklemez
- **Olcut:** (a) native istisna artık sessizce geçemez → **sağlandı**; (b) kök neden bulunmuş ya da bilinçli kabul edilmiş → **sağlanmadı**
- **Kullanici onayi:** gerçek-mpv/native koşum için **gerekir**

Ayrıntılı kayıt: `docs/ENGINEERING_AUDIT.md` → **NATIVE-001**.

Kapatılan: native senaryolar ayrı sürece taşındı ve üst test `exit 0` olsa
bile stderr'deki native istisnayı **FAIL** sayıyor.

**İlk düzeltme bağımsız denetimde REDDEDİLDİ**; o turdaki *23 passed*
sonucu nihai kabul DEĞİLDİR. Üç kusur giderildi: (1) sıraya bağımlı
`assert "mpv" not in sys.modules` iddiası — `app.player` zaten `mpv`
import ettiği için başka bir test önce koşunca düşüyordu; yerine bu
modülün import ETKİSİ ölçülüyor, (2) iki MPV instance'ına karşılık tek
kapanış marker çifti — artık senaryo başına ayrı marker ve ayrı
`stop < terminate` denetimi var, (3) aklanan `MARK_*_ERROR` — artık kesin
FAIL.

Dördüncü kusur (18 Ağustos 2026): `evaluate_child` marker BİÇİMİNİ
denetlemiyordu; `MARK_COVER_TRACKS abc`, değersiz `MARK_THREADS_AFTER` ve
`MARK_DONE junk` içeren çıktı TAMAM sayılıyordu. Artık `MARKER_GRAMMAR`
her zorunlu marker'ın token sayısını ve değerini zorluyor.

Güncel gerçek sonuç: **deterministik 61 passed**. Native kabul, child
üretim kodu değişmediği için tekrarlanmadı; geçerli canlı sonuç önceki
turun **39 passed / exit 0 / stderr BOŞ** koşumudur. Raporlanan iki-test
sıra regresyonu **iki yönde de yeşil**.

**Kapatılmayan:** istisnayı doğuran native modül belirlenmedi ve ürün
üzerindeki etki ölçülmedi. **Tek yeşil native koşum, aralıklı olgunun
bittiğini ispatlamaz.** Yayına hazırlık ölçütlerinden biri olmaya devam
ediyor (bkz. madde 8).

---

## Gercek Windows build ve kabul matrisi

- **Durum:** CANLI KABUL BEKLIYOR
- **Bagimlilik:** REL-001, REL-003
- **Olcut:** `build_release.bat` uçtan uca exit 0; dört artifact üretilmiş ve imzalanmış; fiziksel kabul matrisi koşulmuş
- **Kullanici onayi:** **gerekir** — build ayrı bir onaydır

---

## Release rehearsal

- **Durum:** ERTELENDI
- **Bagimlilik:** yukarıdakilerin tamamı
- **Olcut:** a–j sırası **draft'a kadar** prova edilmiş; adım (j) yayımlama yapılmadan durdurulmuş; kapı exit 0 vermiş
- **Kullanici onayi:** **gerekir** — tag, push ve release ayrı ayrı onay ister

---

## Nihai release-ready kriterleri

Bir sürüm ancak şunların **hepsi** sağlandığında yayına hazır sayılır:

1. Tam paket yeşil ve taban farkı açıklanmış
2. REL-001…REL-005 commit edilmiş
3. `build_release.bat` gerçek koşumda exit 0
4. `prepublish.py --tag vX.Y` exit 0
5. Uzak peeled tag commit'i == yerel HEAD
6. Sekiz varlığın ad/boyut/SHA-256 eşliği doğrulanmış
7. Fiziksel kabul matrisi koşulmuş
8. `0xe24c4a02` riski ya kapatılmış ya bilinçli olarak kabul edilmiş

- **Durum:** ERTELENDI
- **Bagimlilik:** 1–8
- **Olcut:** sekiz maddenin tamamı işaretli
- **Kullanici onayi:** her dış adım için ayrı ayrı gerekir
