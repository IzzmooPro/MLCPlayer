# MLC Player çalışma kuralları

Bu dosya yalnız kalıcı kuralları içerir. Güncel durum ve sıradaki iş için
`docs/PROJECT_STATUS.md` dosyasını oku.

## Başlangıç

1. `CLAUDE.md` ve `docs/PROJECT_STATUS.md` dosyalarını oku.
2. `git status --short --branch` çalıştır.
3. Yalnız görevle ilgili kaynak, test ve diff bölümlerini incele. Tüm depoyu veya eski raporları baştan okuma.
4. Kaynak ile rapor çelişirse kaynak ve yeniden üretilen davranış esas alınır.

## Çalışma yöntemi

- Kullanıcıyla Türkçe ve açık konuş.
- Hata düzeltmesinde önce gerçek davranışı ölçen başarısız test yaz; sonra minimum ürün değişikliğini yap.
- Tek turda tek bağımsız sorunu çöz. İlgisiz refaktör veya görsel değişiklik yapma.
- Kirli çalışma ağacını koru; `stash`, `reset`, `checkout` veya kullanıcı değişikliklerini geri alan komutlar kullanma.
- Kullanıcı açıkça istemedikçe commit, push, remote, tag, release, EXE/setup veya kalıcı Git config değişikliği yapma.
- Ekran görüntüsü, cache, log, kullanıcı ayarı ve büyük binary dosyalarını Git'e ekleme.

## Token tasarrufu

- Aramada önce `rg`; dosya okumada yalnız ilgili satır aralığını kullan.
- Geliştirme sırasında hedef testi çalıştır. Kapsam için `## Test stratejisi` bölümüne uy.
- Aynı başarısız komutu yeni hipotez olmadan tekrarlama.
- Terminal çıktısının tamamını rapora kopyalama; komut, sonuç, önemli hata ve exit code yeterlidir.
- Önceki raporları tekrar etme. Yalnız bu turdaki farkı ve devam eden riski yaz.
- Yeni handoff dosyaları üretme. Güncel durumu yalnız
  `docs/PROJECT_STATUS.md` içinde kısa tut.

## Ürün değişmezleri

- Sinematik arayüz tek kullanıcı arayüzüdür; klasik arayüzü geri getirme.
- MPV native `wid`, fullscreen, overlay, OSD, auto-hide, fade, timeline, ses ve CC davranışlarını ilgili test olmadan değiştirme.
- Playlist paneli ana pencerenin gömülü child yüzeyidir; video ile kesişmemeli ve başka uygulamaların üzerinde yüzmemelidir.
- Resume/watch-later kalıcılığını yeniden açma.
- Altyazı Merkezi worker'larını zorla `terminate()` etme; kooperatif kapanış ve tek sahiplik korunmalıdır.
- Yeni timer, always-on-top bayrağı veya geniş süreç temizliği ekleme.

## Test stratejisi

Test kapsamı etki alanına göre nokta atışıdır.

- Çözülmüş bir davranışı, ilgili kod yolu değişmedikçe yeniden native/fiziksel teste sokma. Yeni düzeltmenin o davranışa zarar verme ihtimali varsa yalnız ilgili regresyon testini çalıştır.
- Her sorun için sıra: (1) tek ve deterministik kırmızı test, (2) minimum düzeltme, (3) aynı testin yeşil sonucu, (4) değişen fonksiyonun doğrudan tüketicilerini kapsayan dar regresyon paketi, (5) görsel/native kanıt zorunluysa en fazla bir hedef child koşumu.
- Tam `pytest -q tests` yalnız ortak altyapı değiştiğinde veya turun sonunda gerçekten gerekliyse çalışır.
- Tam fiziksel matris yalnız release/setup öncesinde ve kullanıcı açıkça onaylarsa çalışır.
- Yeni FAIL görülürse otomatik tekrar koşma; önce mevcut log ve kaynağı incele.
- Kullanıcıdan izin almadan background GUI testi başlatma.
- Test öncesinde tahmini süreyi ve açılacak pencere/child sayısını bildir.

## Test ve güvenlik

- Qt/QSettings testleri benzersiz geçici dizin kullanmalı; gerçek kullanıcı ayarlarını kirletmemeli.
- Native testler yalnız kendi başlattığı kesin PID'i `try/finally` ile temizlemeli; Notepad/Explorer veya kullanıcının Python/Qt süreçlerini hedeflememeli.
- Native crash assertion geçse bile yok sayılmaz; son marker ve gerçek exit code raporlanır.
- Görsel değişiklik yalnız offscreen testle kabul edilmez; gerçek Windows penceresi ve mümkünse gerçek video gerekir.

## Tur sonu

İlgili testlerden sonra çalıştır:

```powershell
python -m compileall -q main.py app tests
git diff --check
```

Ortak altyapı veya tamamlanmış ürün turunda ayrıca:

```powershell
pytest -q tests
```

Rapor yalnız şunları içersin: ilk kırmızı kanıt, değişen dosyalar, kullanıcı etkisi, test/compile/diff sonucu, kalan risk ve Git durumu.
