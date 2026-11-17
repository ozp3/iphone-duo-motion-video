---
name: katlanir-video
description: >-
  Katlanır telefon (iPhone Duo simülatörü) tanıtım videosu üretir: herhangi bir iOS uygulamasının simülatördeki GERÇEK
  ekran kaydı, 3B menteşeyle katlanıp açılan gövdede oynar. Cihaz kapalı girer (dış ekran), yarı açılır, bekler, tam
  açılır; sonda o anki ekranla doğrudan kapanır. Logo açılışı ve kapanışı, başlıklar, dokunuş izleri, tek ses paleti;
  Hyperframes ile dikey + yatay 4K ve 1080p kopya. Kullanıcı "katlanır telefon videosu", "iPhone Duo videosu", "duo ile
  tanıtım videosu", "fold/unfold animasyonlu uygulama videosu", "foldable phone promo / launch video", "uygulamamı
  katlanır telefonda göster", "duo videosunu güncelle / yeniden render et / 4K al" dediğinde MUTLAKA kullan. Düz
  (katlanmayan) telefon ya da web sitesi videosu için değil.
---

# Katlanır telefon tanıtım videosu

Video iki kaynaktan kurulur: **ekranlar simülatörün gerçek kaydı**, **gövde CSS 3B** (simülatör kaydı yalnız ekran
pikselini içerir, gövde hareketini değil). Her şey tek bir yapılandırma dosyasından (`video.json`) üretilir; elle
kompozisyon yazmak gerekmez.

Hat betiği — her adım tek komut, ayrıntı `-h`:

```
python3 ~/.claude/skills/katlanir-video/scripts/katlanir.py ornek|kes|durum|uret|kare|render
```

Proje dizini (video.json'un olduğu yer):

```
<proje>/
  video.json              yapılandırma (ornek yazar)
  kayit/                  kes ve durum çıktıları: ic.mp4, ic-sol.mp4, ic-sag.mp4, dis-*.mp4, durum.png
  katlanir-dikey/         üretilen Hyperframes kompozisyonu (index.html, assets/, anlar.json)
  katlanir-yatay/
  <ad>-dikey.mp4 …        4K çıktılar, -1080p kopyalar, .jpg posterler
  NOTLAR.md               her turun kısa notu (ne değişti, neden)
```

Gerekenler: Xcode + iPhone Duo simülatörü, ffmpeg/ffprobe, Node (`npx hyperframes@0.8.60`), Python 3 + Pillow.

## Kurallar

Her biri gerçek bir geri bildirimden çıktı; çiğnemek aynı itirazı geri getirir.

1. **Ekranlar gerçek kayıt.** Uygulama ekranını CSS/HTML ile yeniden çizme: göz bildiği arayüzün taklidini küçük
   farklardan hemen yakalar. Uygulamada olmayan bir şey gösterilecekse (ör. bir sohbet görünümü) ayrı bir görsel/video
   olarak üst katmana koy (`ic.ust`).
2. **Gövde gerçekten katlanır.** İki yarı menteşe çevresinde döner; sol yarı sağın üstüne kapanır. Yarıları yana
   kaydırmak/genişletmek katlanma gibi görünmez ("raylı kayma"). Yarıların ekranında kaydın sol/sağ yarısı oynar,
   böylece görüntü gövdeyle birlikte kıvrılır.
3. **Gövde gerçek cihaza benzer.** Kapalıyken menteşe solda, gövdenin arkasında düz koyu şerit (parlak kapsül sahte
   durur); tuşlar sağ yarıda; yarı açık her yarı ±24°. Kullanıcı referans görsel verirse ölç (en/boy, kıvrım oranı)
   ve ona uydur — göz kararı değil.
4. **Durum sütunu çizilmez, kesilir.** Saat ve kablosuz simgesi gerçek ekrandan alınır (`durum`); çizilen simge
   "bozuk" diye geri döndü. Kendi görselin tam ekranı kaplıyorsa `"durum": true` ile gerçek bloğu üstüne koy.
5. **Kalite.** Ölçek CSS `zoom` (transform ölçeği yazıyı tam boyda çizip küçültür, bulanıklaştırır); kesimler kaydın
   kendi çözünürlüğünde; çıktı 4K. 1080p'ye doğrudan render "kalite çok düşük" diye geri döndü.
6. **Akış.** Açılış: kapalı → yarı açık (iç ekran, kayıttaki gibi kararmış yanar ve ~1 sn'de netleşir) → 0.5 sn
   bekler → tam açık. Bitiş: **o anki ekran kalır** (başka ekrana dönmek hata gibi görünür), tam açıktan **doğrudan**
   kapanır (yarı açıkta durmaz), kapanınca dış ekranda aynı işin dar hâli (gerçek dış ekran görüntüsü).
7. **Dil ve ses.** Reklam dili: fayda anlatan kısa başlıklar; iç kod adı, sürüm/karar numarası, dosya adı yok. Aynı
   eylem her yerde aynı ses (paketteki tek palet: katlanma, dokunuş, geçiş, logo).
8. **Cihaz ve hesap.** Kayıt simülatörde, test hesaplarıyla. Kullanıcının gerçek telefonuna kurma, gerçek parola yazma.

## Akış

İstek neyi değiştiriyor, oradan başla; birden çok şey isteniyorsa en erken adımdan sırayla ilerle:

| İstek | Başla |
|---|---|
| Yeni video | 0 |
| Uygulama ekranı değişti, yeni kayıt | 1 |
| Saat / durum simgesi | 2 |
| Metin, başlık, süre, sıra, üst katman, dokunuş, logo | 3 |
| Yalnız yeniden render / farklı poster | 5 |

0. **Proje** — boş bir dizinde `katlanir.py ornek` → `video.json`. Logo (SVG/PNG), marka adı, başlıklar ve kapanış
   satırlarını kullanıcının ürününden al; bilinmiyorsa makul bir taslak yaz ve raporda söyle.
1. **Kayıt** — `references/kayit.md` (simülatörü ve ekran kimliklerini bulma, menteşe pozları, kayıt sırası, kesim
   aralığı seçme). Sonra `katlanir.py kes <kayit.mov> --ekran ic --parcalar "a-b,c-d"`; dış ekran için
   `--ekran dis --ad dis-1`.
2. **Durum** — iç ekranın yatay ekran görüntüsü → `katlanir.py durum <png>`; `kayit/durum-onizleme.png`'ye bak.
3. **Yapılandırma** — `references/yapilandirma.md` (alanlar, anlar ve zaman tabanları, üst katman, dokunuş). Sonra
   `katlanir.py uret`: iki biçimi yazar, `hyperframes check` koşar (temiz olmalı) ve anları basar.
4. **Kare kare bak** — `katlanir.py kare` (varsayılan: kapalı, yarı açık, açık, klip sonu, katlanma ortası, kapalı son
   hâl, kapanış; `--at "tam+1,katlanma+0.3"` ile özel anlar). Temas sayfasını OKU; şüpheli yeri yakınlaştır. Asıl
   itirazlar küçük ayrıntılardan gelir (simgenin içi, menteşe kalınlığı, bir anlık yanlış ekran) — "check geçti" yetmez.
5. **Render** — `katlanir.py render [--poster "tam+2"]` (biçim başına ~2 dk; arka planda koş). Poster ilk kareye de
   işlenir (paylaşım küçük resmi). Çıktı ölçümlerini oku (çözünürlük, Mbps, MiB).
6. **Gönder** — dosya gönderme aracı varsa: 4K dosyalar 30 MiB'ı aşar ve uzak görüntüleyicilere gitmez; `-1080p.mp4`
   kopyalarını da gönder ve bunu tek satırla söyle.
7. **Not** — `NOTLAR.md`'ye turun özeti: ne değişti, neden, hangi geri bildirimle. Sonraki tur oradan başlar.

Projede önceki turlardan elle yazılmış özel bir kompozisyon/üretici varsa onu sürdür (yeniden yazma); yukarıdaki
kurallar orada da geçerli.

## Rapor

Kısa: ne üretildi (dosyalar, süre, çözünürlük), bu turda ne değişti, kullanıcıdan beklenen karar varsa numaralı.
Kullanıcının kendi rapor biçimi varsa ona uy.
