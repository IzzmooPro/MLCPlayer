# MLC Player belge haritası

Bu dosya hangi bilginin hangi belgede tutulduğunu gösteren tek haritadır.
Bir bilgi yalnız bir belgede yaşar; başka belgeler onu tekrar etmez, buraya
veya sahibine bağlanır. `tests/test_docs_index_regressions.py` bu haritadaki
her belgenin var olduğunu ve `docs/` altındaki her belgenin burada
listelendiğini denetler.

## Önce okunacaklar

1. `docs/process/AGENTS.md` — agent başlangıç sözleşmesi ve kanıt sınırları.
2. `docs/CONTINUITY.md` — güncel durum ve sıradaki tek adım.
3. `docs/VERIFICATION_LEDGER.json` — makinece doğrulanmış sonuçlar.

Claude'a özgü kurallar `.claude/CLAUDE.md` içindedir ve `AGENTS.md`'yi
otomatik yükler. Kullanıcıya dönük tanıtım `.github/README.md` (İngilizce,
GitHub ana sayfası) ve `.github/README.tr.md` dosyalarındadır.

## Canlı belgeler

| Belge | Tek sorumluluğu | Ne zaman güncellenir |
| --- | --- | --- |
| `docs/CONTINUITY.md` | Güncel durum, korunan kapılar, sıradaki tek adım | Her karar/kanıt turunun sonunda |
| `docs/VERIFICATION_LEDGER.json` | Append-only kanıt kaydı | Sonraki kararda kullanılacak her sonuçta |
| `docs/process/AGENTS.md` | Agent başlangıcı, kanıt katmanları, çift-süzgeç | Çalışma sözleşmesi değiştiğinde |
| `docs/process/CHANGE_WORKFLOW.md` | PR, CI ve birleştirme akışı | Dal/PR kuralı değiştiğinde |
| `docs/release/RELEASE_PROCESS.md` | Yayın sırasının tek resmî kaynağı | Yalnız yayın sözleşmesi değiştiğinde |
| `docs/release/PACKAGING_PLAN.md` | Installer UX sözleşmesi, paketleme kararları, açık uyumluluk maddeleri | Installer veya paketleme kararı değiştiğinde |
| `docs/release/SIGNPATH.md` | SignPath başvurusu ve imzalama hazırlığı | Başvuru durumu değiştiğinde |
| `docs/policies/PRIVACY.md` | Kamuya açık gizlilik politikası | Ağ veya yerel veri davranışı değiştiğinde |
| `docs/policies/CODE_SIGNING_POLICY.md` | Kamuya açık kod imzalama politikası | İmzalama durumu değiştiğinde |
| `docs/quality/QUALITY_EVOLUTION_PLAN.md` | Mimari ve gerçek Windows kalite programı | Faz başlarken veya kapanırken |
| `docs/quality/ARCHITECTURE_INVENTORY.md` | Modül sahipliği ve ayrıştırma adayları | Ölçüm veya sahiplik değiştiğinde |
| `docs/quality/ARCHITECTURE_INVENTORY.json` | Altı büyük modülün hash/yapı güncellik kapısı | Bu modüllerden biri değiştiğinde |
| `docs/quality/WINDOWS_ACCEPTANCE_MATRIX.md` | Gerçek Windows kabul senaryoları | Senaryo veya sonuç değiştiğinde |
| `docs/video-format/VIDEO_FORMAT_ACCEPTANCE_PLAN.md` | SDR/HDR/codec kabul planı ve ölçülmüş yetenek envanteri | Format kararı veya ölçüm değiştiğinde |
| `docs/video-format/VIDEO_FORMAT_ACCEPTANCE_MATRIX.json` | Format satırlarının makinece kaynağı | Satır sonucu değiştiğinde |
| `docs/video-format/VIDEO_FORMAT_MEDIA_MANIFEST.json` | Test medyasının kimlik ve köken sözleşmesi | Medya adayı değiştiğinde |

## Tarihsel arşiv (`docs/history/`)

Bu dosyalar güncel karar kaynağı değildir; her biri açılışında bunu söyler.
Kapanan iş canlı belgeden silinmez, kelimesi kelimesine buraya taşınır.

| Belge | İçerik |
| --- | --- |
| `docs/history/CONTINUITY_HISTORY.md` | Eski devir notlarının kronolojisi (özeti testle sabit) |
| `docs/history/PROJECT_STATUS.md` | 20 Ağustos 2026'ya kadarki proje anlatısı |
| `docs/history/ROADMAP.md` | 20 Ağustos 2026 yol haritası snapshot'ı |
| `docs/history/ENGINEERING_AUDIT.md` | Denetim bulguları ve AUD-20260905 devir raporu |
| `docs/history/PACKAGING_HISTORY.md` | Paketleme kayıtları, eski uyumluluk listesi, ilk ikon notları |

## Depo düzeni

Kökte yalnız `Start.bat` ve `LICENSE` bulunur (Git'in zorunlu `.gitignore`
ve `.gitattributes` dosyaları dışında). `LICENSE` GitHub'ın lisansı
tanıması için köktedir.

| Klasör | İçerik |
| --- | --- |
| `app/` | Ürün kaynağı; giriş noktaları `app/main.py` ve `app/user_cleanup_main.py` |
| `assets/` | İkon ve görsel kimlik dosyaları |
| `bin/` | libmpv ve yardımcı çalışma zamanı ikilileri (büyükleri Git'e girmez) |
| `docs/` | Bu harita ve yukarıdaki belgeler |
| `licenses/` | Üçüncü taraf lisans metinleri |
| `packaging/` | PyInstaller spec, Inno Setup ve yayın betikleri |
| `requirements/` | Bağımlılık listeleri ve hash kilidi |
| `scripts/` | Başlatıcı ve bakım betikleri |
| `tests/` | Otomatik testler ve native ölçüm child'ları |
| `translations/` | `.ts` çeviri kaynakları |
| `.github/` | README dosyaları ve GitHub Actions iş akışları |
| `.claude/` | Claude kuralları, ayarları ve hook'ları |
| `output/` | Git'e girmeyen bütün üretim çıktıları (build, dist, installer, kaynak aynası) |

## Yeni belge kuralları

- Önce bu haritaya bak: bilginin bir sahibi varsa oraya yaz, yeni dosya açma.
- Yeni belge gerçekten gerekiyorsa uygun alt klasöre koy ve bu tabloya ekle;
  test, listelenmemiş belgeyi kabul etmez.
- Canlı belgede kapanan iş birikirse kelimesi kelimesine `docs/history/`
  altına taşı ve canlı belgede yalnız kanıt kimliğiyle an.
- Satırlar sarılı yazılır; tek satıra yığılmış paragraf yazılmaz.
- Yerel kullanıcı yolu, kişisel ad veya özel artifact yolu yazılmaz.
