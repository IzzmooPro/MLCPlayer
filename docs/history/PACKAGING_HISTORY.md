# MLC Player paketleme tarihçesi

> **TARİHSEL ARŞİV:** Bu dosya `docs/release/PACKAGING_PLAN.md` içinden
> 3 Ekim 2026'da değiştirilmeden ayrılan tarihsel paketleme kayıtlarını,
> eski yayın öncesi uyumluluk kontrol listesini ve ilk ikon notlarını
> korur. Güncel durum buradan çıkarılmaz: güncel devir için
> `docs/CONTINUITY.md`, canlı installer sözleşmesi ve açık uyumluluk
> maddeleri için `docs/release/PACKAGING_PLAN.md` kullanılır.

## Tarihsel paketleme kayıtları

Aşağıdaki tarihli libmpv engel ve kapanış ölçümleri dondurulmuş tarihsel
snapshot'tır. Güncel dağıtım durumu bu bölümden çıkarılmaz; `CONTINUITY.md` ve
`VERIFICATION_LEDGER.json` üzerinden okunur.

### YAYIN ENGELI: mpv-2.dll DAGITILAMAZ -> COZULDU (16 Agustos 2026)

**DURUM: kapatildi.** Asagidaki teshis kayit olarak korunuyor; en altta
degisim ve dogrulama sonuclari var.

**Tahmin degil, ikilinin KENDI icinden okundu.**

`bin/mpv-2.dll` (99.390.990 bayt, 25 Kasim 2024) icine gomulu FFmpeg
`configure` dizesi:

    --prefix=/__w/mpv-winbuild-cmake/mpv-winbuild-cmake/build64/install/mingw
    ... --enable-gpl --enable-version3 --enable-nonfree ...
    --enable-libx264 --enable-libx265 --enable-libxvid
    --enable-cuda --enable-cuvid --enable-nvdec --enable-nvenc ...

FFmpeg'in kendi `configure` yardim metni `--enable-nonfree` icin sunu der:
*"allow use of nonfree code, the resulting libs and binaries will be
unredistributable"*. Yani bu DLL kisisel kullanim icin derlenebilir ama
**hicbir bicimde ucuncu kisilere dagitilamaz** — ne setup icinde, ne yaninda.

- `--enable-lgpl` YOK; `--enable-gpl` + `--enable-version3` VAR. Yani LGPL
  degil, GPLv3 tarafindadir. MLC Player da GPLv3 oldugu icin bu KISIM sorun
  degildir; sorun yalniz `nonfree`dir.
- nonfree'yi tetikleyen bilesen `fdk-aac` DEGIL: ikilide `libfdk` izi yok,
  buna karsilik `nvenc`, `cuda`, `cuvid` var. Kaynak CUDA/NVENC tarafidir.
- `bin/SHA256SUMS.txt` bu dosya icin kaynagi bilerek bos birakiyor
  ("source/version is intentionally unspecified"). 99 MB'lik bir ikili
  kaynagi kayitli olmadan dagitilamaz; `yt-dlp`/`deno` icin uygulanan
  provenance disiplini buna da uygulanmalidir.

**Cozum basit ve dogrulandi:** ayni yukari-akis projenin (`mpv-winbuild-cmake`)
GUNCEL yapilandirmasi `--enable-nonfree` KULLANMIYOR; yalniz `--enable-gpl`
ve `--enable-version3` geciyor. Elimizdeki DLL eski/varyant bir yapidir.

Yapilacaklar (release turunda, sirasiyla):

1. `mpv-2.dll` guncel ve `nonfree` ICERMEYEN bir yapiyla degistir.
2. Degistirdikten SONRA ayni olcumu tekrarla: gomulu `configure` dizesinde
   `--enable-nonfree` OLMADIGINI dogrula. Bu, kabul kriteridir.
3. Surum, kaynak URL, boyut ve SHA-256'yi `bin/RUNTIME_MANIFEST.txt` icine
   yaz; `SHA256SUMS.txt`teki "intentionally unspecified" notunu kaldir.
4. mpv/FFmpeg icin GPLv3 lisans metnini ve karsilik gelen kaynak erisimini
   pakete ekle.
5. Codec/patent tarafi ayrica degerlendirilmeli: `libx264`, `libx265`,
   `libxvid` GPL'dir (lisans tarafi GPLv3 ile uyumludur) ancak H.264/H.265
   PATENT yukumlulukleri lisanstan AYRI bir konudur ve ticari dagitimda
   avukata sorulmalidir.

### YAPILDI: degisim ve dogrulama (16 Agustos 2026)

Yeni ikili: `mpv v0.41.0-923-g7b8915bc1`, FFmpeg `N-126125-g1d7b14f61`,
libass `0x1705000`. Kaynak arsiv, boyut ve SHA-256 artik
`bin/RUNTIME_MANIFEST.txt` icinde; `SHA256SUMS.txt`teki "intentionally
unspecified" notu KALDIRILDI. Eski nonfree DLL silinmedi, `bin/_old/` altina
alindi ve `.gitignore` ile hem depodan hem pakete girmekten uzak tutuldu
(`MLCPlayer.spec` acik dosya listesi kullanir, `bin/` glob'u YOKTUR).

**Lisans dogrulamasi (kabul kriteri yeniden tanimlandi).** Ilk kriter
"ikilide `--enable-nonfree` dizesi aranir" idi; yeni yapida FFmpeg'in
`configure`/lisans SABITLERI hic bulunmuyor (linker kullanilmayanlari
atmis), bu yuzden o kriter bu yapi icin GECERSIZDIR — "bulamadim" ile "yok"
ayni sey degildir. Bunun yerine uc bagimsiz kanit kullanildi:

1. Nonfree'yi ZORUNLU kilan bilesenlerin hicbiri ikilide yok:
   `libfdk` / `fdk_aac` / `libnpp` / `nppi_` / `cuda-nvcc` / `decklink`.
2. Etiketin (`20260814`) RESMI build tarifi yalniz `--enable-gpl` ve
   `--enable-version3` geciyor; `--enable-nonfree`, `--enable-libnpp` ve
   `--enable-cuda-nvcc` YOK. CUDA serbest `--enable-cuda-llvm` yolundan.
3. Eski ikilide FFmpeg'in kendi lisans sabiti literal olarak
   `nonfree and unredistributable` yaziyordu; yeni ikilide boyle bir sabit
   YOK ve nonfree bilesen izi de yok.

Sonuc: yeni yapi GPL(v3) tarafindadir ve MLC Player'in GPLv3 lisansiyla
uyumludur; dagitilabilir.

**API uyumlulugu olculdu.** Urunun bagli oldugu 31 secenek/ozelligin TAMAMI
yeni surumde mevcut (eksik yok). Altyazi stil sozlesmesinin kritik DEGERLERI
de yazilip geri okundu: `sub-ass-override=force`, `sub-border-style=
background-box` ve `outline-and-shadow`, `#AARRGGBB` renkler
(`#FFF26A3D`, `#C80020A0`), `sub-shadow-offset`, `sub-use-margins`,
`sub-ass-force-margins`, `sub-margin-y`, `sub-pos`, `sub-scale`,
`sub-border-size` — 14/14 dogru geri okundu.

**Not (davranis DEGISTIRILMEDI):** `sub-margin-y-offset` v0.36'da YOKTU ve
mevcut `sub-margin-y` tasariminin gerekcesi buydu. v0.41'de bu ozellik ARTIK
VAR. Gerekce eskidi ama bu turda hicbir altyazi yolu degistirilmedi; olasi
sadelestirme ayri bir turun konusudur.

**Test:** `pytest -q tests` -> **3158 passed, 17 skipped** (degisimden onceki
sonucun birebir aynisi).

**ACIK KALAN — fiziksel dogrulama.** Offscreen paketin gecmesi, altyazi
guvenli bandinin PIKSEL duzeyinde korundugunu KANITLAMAZ. mpv 0.36 -> 0.41
ve FFmpeg 6 -> 8 atlamasindan sonra `o_band` / `p_ass_band` gercek video
kabulu yeniden kosulmalidir (gercek pencere + gercek MKV, kullanici onayiyla).
Bu kosum yapilana kadar guvenli bant "dogrulanmis" SAYILMAZ.

## Yayin oncesi uyumluluk kontrol listesi

Asagidakiler somut ve dogrulanabilir maddelerdir. Hicbiri hukuki gorus
degildir.

### Kapatilmasi zorunlu

- [ ] `mpv-2.dll` nonfree olmayan yapiyla degistirildi ve olcumle dogrulandi
      (yukaridaki bolum).
- [ ] GPLv3+ birlesik `yt-dlp.exe` ve GPLv3 mpv icin **karsilik gelen kaynak
      erisimi**: kullaniciya, kullandigi ikiliyle ayni surumun kaynagini
      sunma yukumlulugu. Pratik yol, her ikili icin surum + kaynak arsiv
      URL'sini ve bir yedek kopyayi saklamaktir.
- [ ] Kokteki `LICENSE` (GPLv3, 35.149 bayt) setup icine de girmeli;
      `licenses/` klasoru pakete kopyalanmali.
- [ ] GPLv3'un onerdigi dosya basi telif/lisans bildirimleri kaynak
      dosyalara eklenmeli.

### OpenSubtitles API (olculdu)

Resmi sartlar: her istekte `Api-Key` basligi, uygulama adi + surum tasiyan
benzersiz `User-Agent`, **saniyede 1 istek** sinirlamasi, indirme kotalari
kullanici rutbesine bagli.

- [x] `app/opensubtitles.py` `Api-Key` gonderiyor ve
      `USER_AGENT = "MLC Player Subtitle Center v1"` kullaniyor — sartlara
      uygun bicimde ad + surum tasiyor.
- [x] Mevcut kod API anahtarini kullanicidan alir; uygulamaya gomulu anahtar
      YOKTUR. **Bu teknik durum bir uyumluluk karari degildir.** Servis
      yoneticisinin uygulama basina tek anahtar yonlendirmesi nedeniyle
      cevrimici arama arayuzu kapali tutulur; acik sart veya yazili saglayici
      onayi olmadan ne gomulu anahtar ne de kullanici-basina-anahtar akisi
      yayinlanir.
- [x] **KAPANDI (16 Agustos 2026):** onleyici hiz sinirlamasi eklendi.
      `MIN_REQUEST_INTERVAL_S = 1.0` ve `_respect_rate_limit()`, butun
      isteklerin gectigi TEK bogaz noktasi olan `_call()` icinde. Bekleme
      QThread worker'indadir, GUI donmaz; kilit es zamanli worker'larin ayni
      pencerede iki istek gondermesini engeller; saat GERI giderse bekleme
      aralikla SINIRLANIR. `429/406` tepkisel yolu AYNEN korunur — onleyici
      sinir onu degil, servise gereksiz yuku engeller.
      Sozlesme: 4 test (arka arkaya istekler araliklanir, yavas istek
      araligi tuketir ve bosa beklenmez, saat geri giderse ust sinir,
      anahtar yoksa aga cikilmadan once beklenmez).
- [ ] Indirilen altyazilarin yeniden dagitimi ve saklanmasi konusundaki
      sartlar dogrulanmali (uygulama altyaziyi yalniz kullanicinin diskine
      yaziyor; baska yere kopyalamiyor).

### Kod imzalama ve SmartScreen

- [ ] Kod imzalama sertifikasi arastirilmali. **Imza, lisans ve telif
      yukumluluklerinin yerine GECMEZ**; yalnizca dagitim guvenini artirir.
      Imzasiz setup Windows SmartScreen uyarisi uretir.

### Avukata yoneltilecek acik sorular

1. GPLv3 bir uygulamayla ayni pakette dagitilan GPLv3+ `yt-dlp.exe` icin
   "karsilik gelen kaynak" yukumlulugunu, kaynak arsiv URL'si sunmak
   karsiliyor mu, yoksa kopyayi bizim mi barindirmamiz gerekir?
2. H.264/H.265 decode iceren bir masaustu oynaticinin Turkiye'den ucretsiz
   dagitiminda patent havuzu (MPEG-LA / Access Advance) yukumlulugu dogar mi?
3. Acik kaynak bir Windows masaustu istemcisinde "uygulama basina tek API
   anahtari" nasil dagitilmalidir? Anahtarin kaynakta/ikili icinde gorulebilir
   olmasi kabul ediliyor mu; kullanicinin kendi anahtarini girmesi yasak mi?
   OpenSubtitles'tan yazili cevap alinmadan arayuz yeniden acilmayacak.

### Boyut etkisi (olculdu)

`mpv-2.dll` ~99 MB + `deno.exe` ~97 MB + `yt-dlp.exe` ~18 MB; yalnizca bu uc
dosya ~214 MB'dir. Kurulum boyutu ve setup sikistirma karari bu gercege gore
verilmelidir.

## Uygulama ikonu (tek gorsel kimlik)

Kaynak asset `assets/mlc-player-icon.png` (1254x1254 RGBA, kullanici
tarafindan saglandi, degistirilmeden alindi). Windows ICO ondan LANCZOS ile
uretildi: `assets/mlc-player-icon.ico` (16, 20, 24, 32, 40, 48, 64, 128, 256
px; alfa korundu). Olcu ve SHA-256 degerleri `assets/ICON_MANIFEST.txt`
icindedir.

Paketleme:

    _internal\assets\mlc-player-icon.ico

`MLCPlayer.spec` icinde `EXE(..., icon='assets/mlc-player-icon.ico')`.

### Setup icin KESIN alanlar (ileride uygulanacak)

Inno `.iss` bu turda URETILMEDI. Uygulanacak alanlar:

- `SetupIconFile=assets\mlc-player-icon.ico`
- `UninstallDisplayIcon={app}\MLC Player.exe`
- Masaustu ve Baslat menusu kisayollari ana EXE ikonunu kullanir.
- Setup ve kaldiricinin gercek gorunumu Inno kabulunde AYRICA dogrulanir.
