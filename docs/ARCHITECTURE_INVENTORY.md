# MLC Player mimari envanteri

**Durum:** ÖN ÖLÇÜM TAMAM, SORUMLULUK ANALİZİ ÇALIŞTIRILMADI

**Ölçüm tabanı:** `78518dd67e882e35da69ea7bb6bfc74e3cafc1c7`

**Ölçüm tarihi:** 23 Ağustos 2026

Bu dosya refactor kararı değil, ölçüm ve sahiplik kaydıdır. Satır sayısı tek
başına kusur veya bölme gerekçesi değildir. Kullanıcı davranışı, state
sahipliği, yaşam döngüsü, bağımlılık ve test sınırı birlikte incelenmeden ürün
kodunda davranış değişikliği yapılmaz.

## Ön ölçüm

| Modül | Fiziksel satır | Analiz durumu |
| --- | ---: | --- |
| `app/video_frame.py` | 2623 | ÇALIŞTIRILMADI |
| `app/media_controls.py` | 1288 | ÇALIŞTIRILMADI |
| `app/player.py` | 1209 | ÇALIŞTIRILMADI |
| `app/playlist_panel.py` | 1102 | ÇALIŞTIRILMADI |
| `app/menu_actions.py` | 1082 | ÇALIŞTIRILMADI |
| `app/updater.py` | 1028 | ÇALIŞTIRILMADI |

Bu değerler yalnız başlangıç kapsamını görünür kılar. İlk ayrıştırma adayı henüz
seçilmemiştir.

## Her modül için zorunlu analiz alanları

| Alan | Kaydedilecek ölçüm |
| --- | --- |
| Görünür davranış | Kullanıcının gördüğü/etkilediği işlevler |
| State sahipliği | Değişkenin sahibi, yazan/okuyan bileşenler |
| Yaşam döngüsü | Oluşturma, bağlama, durdurma ve temizleme sırası |
| Eşzamanlılık | Timer, worker, thread, process ve callback sınırları |
| Native sınır | libmpv, Win32, Qt ve dosya sistemi etkileşimleri |
| Bağımlılık yönü | Import, sinyal, callback ve doğrudan ebeveyn erişimi |
| Test kapsaması | Deterministik test ve gerçek native runner ayrımı |
| Kusur geçmişi | Ledger/continuity içindeki ilgili başarısızlıklar |
| Aday dikiş | Davranış değiştirmeden ayrılabilecek tek sorumluluk |
| Ters gerekçe | Neden şu anda ayrılmaması gerektiği |

## Risk sıralaması

Her modül 0–3 arasında ayrı ayrı değerlendirilir:

- state sahibi sayısı;
- thread/timer/native yaşam döngüsü yoğunluğu;
- ters veya döngüsel bağımlılık;
- bir değişikliğin etkilediği görünür davranış sayısı;
- geçmiş gerçek kusur sayısı;
- native/kurulu davranış kapsamasındaki boşluk.

Toplam puan otomatik refactor kararı değildir. Önce düşük riskli, davranışı
koruyan ve ölçülebilir kazanımı olan dikiş tercih edilir. Büyük patlama refactor
yasaktır.

## İlk sıradaki çalışma

Altı modülün sınıf/fonksiyon/import/state ve mevcut test eşlemesini salt okunur
çıkar. Sonuçları bu dosyaya ekle; ürün kodunu değiştirme ve henüz ayrıştırma
önerisini uygulama.
