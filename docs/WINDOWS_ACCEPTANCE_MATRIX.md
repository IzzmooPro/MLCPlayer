# MLC Player gerçek Windows kabul matrisi

**Durum:** SÖZLEŞME HAZIR, SENARYOLAR NOT_RUN

**Plan tabanı:** `78518dd67e882e35da69ea7bb6bfc74e3cafc1c7`

**Hazırlanma tarihi:** 23 Ağustos 2026

Bu matris gerçek Windows davranışını kaydeder. Deterministik veya hosted CI
sonucu buradaki satırları PASS yapmaz. Bir sürümdeki PASS başka sürüme taşınmaz.
`BLOCKED, PASS değildir`; donanım veya exact artifact yoksa açıkça BLOCKED
yazılır.

## Sonuç sözlüğü

- `NOT_RUN`: henüz çalıştırılmadı.
- `PASSED`: beklenen davranış aynı exact commit/runtime/artifact üzerinde
  ölçüldü.
- `FAILED`: beklenen davranış sağlanmadı; otomatik tekrar yapılmaz.
- `BLOCKED`: gerekli donanım, medya, izin veya artifact yok.

## Her koşumda zorunlu kimlik

- exact commit;
- kaynak koşumunda runtime manifest ve DLL SHA-256;
- kurulu koşumda installer adı, boyutu ve artifact SHA-256;
- uygulama ve installer sürümü;
- Windows sürümü, ekran ölçeği, monitör/GPU ve ses çıkışı (mahrem veri yok);
- kullanılan medyanın türü/codec'i ve gerekiyorsa güvenli kimliği;
- komut veya manuel adımlar;
- child exit code, final marker, stderr özeti ve süreç sızıntısı sonucu;
- ölçüm zamanı ve sonucu kaydeden ledger kimliği.

## P0 — Her mimari değişiklik öncesi başlangıç çizgisi

| Kimlik | Senaryo | Beklenen kanıt | Durum |
| --- | --- | --- | --- |
| WIN-P0-01 | Uygulama açılışı ve normal kapanış | Exit 0, final marker, stderr sınıflaması, süreç sızıntısı yok | NOT_RUN |
| WIN-P0-02 | Gerçek yerel video oynatma | Süre ilerler, kare/oynatma kanıtı vardır, medya değişmez | NOT_RUN |
| WIN-P0-03 | Ses ve yerel altyazı parçası değiştirme | Seçim libmpv read-back ile doğrulanır | NOT_RUN |
| WIN-P0-04 | Seek, duraklatma ve devam | Zaman/state read-back beklenen aralıkta | NOT_RUN |
| WIN-P0-05 | Tam ekran, native resize ve geri dönüş | Boyut/state doğru, donma ve kontrol kaybı yok | NOT_RUN |
| WIN-P0-06 | Dosya/altyazı sürükle-bırak | Doğru medya veya altyazı uygulanır | NOT_RUN |
| WIN-P0-07 | Oynatma listesi ekleme, taşıma ve sınırlar | Sıra ve seçim korunur, son satır hedeflenebilir | NOT_RUN |
| WIN-P0-08 | İkinci uygulama örneği/IPC | Dosya veya URL ilk örneğe geçer, artık süreç yok | NOT_RUN |

## P1 — Ortam ve dayanıklılık

| Kimlik | Senaryo | Beklenen kanıt | Durum |
| --- | --- | --- | --- |
| WIN-P1-01 | Çoklu monitör arasında taşıma | Pencere/overlay doğru ekranda ve erişilebilir | NOT_RUN |
| WIN-P1-02 | Farklı DPI/ölçek | Kontroller taşmaz, hit alanları görselle eşleşir | NOT_RUN |
| WIN-P1-03 | Ses cihazı değiştirme | Donma/çökme yok; sonuç açıkça kaydedilir | NOT_RUN |
| WIN-P1-04 | Ağ videosunda bağlantı kesilmesi | Sır temiz hata, gizli veri yok, UI geri döner | NOT_RUN |
| WIN-P1-05 | Uzun oynatma listesi | Etkileşim ve kapanış kabul edilebilir, sızıntı yok | NOT_RUN |
| WIN-P1-06 | Uyku/uyanma veya ekran kilidi | Oynatma ve pencere durumu açık sonuçla kaydedilir | NOT_RUN |

## P2 — Donanıma bağlı kapsam

| Kimlik | Senaryo | Beklenen kanıt | Durum |
| --- | --- | --- | --- |
| WIN-P2-01 | HDR ekran ve HDR medya | Gerçek HDR donanımı/Windows ayarıyla görüntü yolu | BLOCKED |
| WIN-P2-02 | Bluetooth ses gecikmesi/değişimi | Gerçek Bluetooth cihazıyla davranış ölçümü | BLOCKED |
| WIN-P2-03 | Birden fazla GPU/driver yolu | Kullanılan GPU/driver açık, oynatma sonucu ölçülü | BLOCKED |

P2 satırları uygun donanım doğrulanmadan çalıştırılmaz ve PASSED yazılmaz.

## Var olan araçların yeniden kullanımı

- `tests/run_physical_acceptance.py`
- `tests/run_native_overlay_matrix.py`
- `tests/run_subtitle_visual_acceptance.py`
- `tests/native_feature_acceptance.py`
- `tests/native_shutdown_acceptance.py`

Yeni runner ancak mevcut araç kesin olarak senaryoyu ölçemiyorsa ve önce bu
boşluk belgelenirse eklenir.

## İlk sıradaki çalışma

P0 satırlarını mevcut runner ve testlerle eşleştir. Eksik ölçümleri yaz; hiçbir
native koşumu veya kurulum açık kullanıcı onayı olmadan başlatma.
