# video.json ve üretici

## İçindekiler
1. Alanlar
2. Anlar ve zaman tabanları
3. Üst katman ve dokunuşlar
4. Üreticinin yapısı (gövde, DOM, katlanma devri)
5. Tuzaklar

## 1. Alanlar

`katlanir.py ornek` tam bir örnek yazar. Yollar video.json'a göre görelidir.

| Alan | Anlamı |
|---|---|
| `ad` | çıktı adı: `<ad>-dikey.mp4`, `<ad>-yatay.mp4` |
| `bicimler` | `["dikey", "yatay"]` ya da biri |
| `zemin`, `vurgu` | arka plan rengi; zemindeki üç yumuşak renk kütlesi (hex ×3) |
| `yazi` | `renk`, `aile` (varsayılan sistem yazısı), `css` (isteğe bağlı: @font-face içeren dosya, satır içine alınır) |
| `acilis` | `sure` (cihaz girene kadar), `logo` (SVG/PNG), `metin` (marka adı). Yoksa video cihazla başlar |
| `kapali.ekran` | kapalıyken dış ekranda sırayla oynayanlar: `{"dosya", "sure"?, "durum"?}` — video kendi süresi kadar, görsel `sure` (vars. 3) |
| `kapali.sure` | kapalı bölümün toplam süresi (vars. öğelerin toplamı) |
| `kapali.dokunuslar` | dış ekranda dokunuş izleri (bkz. 3) |
| `ic.klip` | iç ekran klibi (`kes --ekran ic` çıktısı; `-sol`/`-sag` yarıları yanında olmalı) |
| `ic.duzles` | klip içinde düzleşmenin başladığı saniye (yarı açık netleşme + ~0.5 sn bekleme; vars. 1.5) |
| `ic.ek` | klip bittikten sonra katlanmadan önce açık kalma süresi (son kare ve üst katmanlar durur; vars. 0) |
| `ic.dokunuslar`, `ic.ust` | bkz. 3 |
| `katlanma` | `dis_ekran` (kapanınca dış ekran: gerçek dış ekran görüntüsü/videosu; yoksa kapalı bölümün son karesi), `bekle` (kapalı bekleme, vars. 1.0), `durum` |
| `basliklar` | `{"metin", "bas", "bit"?}` — cihazın üstünde; 0.7 sn'de belirir, 0.45 sn'de söner |
| `kapanis` | `sure` (vars. 4.5), `logo`, `satirlar` (ilki büyük — alan adı; sonrakiler slogan) |
| `poster` | poster anı (vars. `"tam+2"`); `render --poster` ezer |
| `durum` | durum görüntüsü yolu (vars. `kayit/durum.png`) |
| `ses` | `false` → sessiz |

## 2. Anlar ve zaman tabanları

`uret` anları hesaplar, basar ve `katlanir-<biçim>/anlar.json`'a yazar (video saniyesi):

`giris` cihaz girer · `acilma` kapalı → yarı açık (0.6 sn) · `klip` iç ekran kaydı başlar (acilma + 0.2) ·
`duzles` yarı açık → tam açık (0.55 sn) · `tam` düz açık · `klip_son` · `katlanma` tam açık → kapalı (0.7 sn) ·
`kapali` · `cikis` cihaz iner · `kapanis` · `son`.

Zaman yazan her alan sayı ya da `"ad±sn"` alır (`"tam+0.8"`, `"katlanma-0.4"`). Sayının tabanı alana göre:

| Alan | Sayı neye göre |
|---|---|
| `basliklar`, `poster`, `kare --at` | videonun başı (mutlak saniye) |
| `ic.dokunuslar`, `ic.ust` | klibin başı (`klip`) — kesim içindeki saniye |
| `kapali.dokunuslar` | `giris` |

Toplam süre kendiliğinden çıkar: açılış + kapalı bölüm + klip + `ek` + katlanma + bekleme + kapanış. Daha uzun ya da
kısa video için klibi, `kapali` öğelerini ya da `ek`'i değiştir.

## 3. Üst katman ve dokunuşlar

**Üst katman (`ic.ust`)** — iç ekranın üstünde, düz açıkken: `{"dosya", "bas", "bit"?, "kutu"?, "durum"?}`.
Görsel ya da video; `kutu` = `[x, y, gen, yük]` simülatör noktası (iç ekran ~951×669 nokta; yoksa tam ekran);
`durum: true` gerçek durum bloğunu üstüne koyar. Uygulama açılır gibi gelir (ölçek 0.88 → 1), `bit`'te küçülerek
gider. `bit` yoksa ya da katlanmaya kadar sürüyorsa **katlanırken ekranda kalır**: son hâli (videoysa son karesi)
yarıların donmuş kopyasına girer. `tam`'dan önce başlayan katman düzleşene kadar görünmez (uyarı basılır).

**Dokunuşlar** — `{"an", "x", "y"}`, nokta = simülatör noktası (kayıtta dokunduğun yer). 2.5 sn'den yakın dokunuşlar
tek bir iz olarak birinden ötekine kayar; iz 0.5 sn önce belirir, basışta küçülür + dalga, son dokunuştan 0.2 sn
sonra söner. Her dokunuşta aynı tık sesi.

## 4. Üreticinin yapısı

Geometri (cihaz pikseli, iPhone Duo oranları): kapalı gövde 1012×1440 (açık 2×), iç ekran 1980×1390 (gerçek
2852×2006), dış ekran 956×1391 (gerçek 1398×2034). Başka katlanır cihaz için `katlanir.py` başındaki sabitler
(`WP, HP, IC_*, DS_*, *_PIK, DURUM_*`) ve `BICIM` kadrajları değişir.

```
#sahne (konum x/y) > #sahneZoom (zoom + perspektif 8500, köken menteşede) > #duo
  #duoSag   tuşlar · gövde · iç ekranın sağ yarısı (klip-sag · .ic-kopya · .ic-karart)
  #duoSol   ön yüz: iç ekranın sol yarısı (klip-sol, menteşeden 6 px taşar · .ic-kopya · .ic-karart)
            arka yüz: .omurga · #ekran = dış ekran (kapali öğeleri · #disSon · dokunuşlar · #disKarart)
  #duoUst   düz açıkken üst katman (translateZ 6px): tam genişlik klip · son kare · ic.ust · iç dokunuşlar
```

- Sol yarı menteşe (sağ kenarı) çevresinde döner: kapalı `rotationY 180`, yarı açık `24`, açık `0`; sağ yarı yarı
  açıkta `-24`. Sol `z: 3` (önde), sağ `z: -3`. Dış gölge yalnız sağ gövdede (sol yarının gölgesi menteşede şerit yapar).
- Düz açıkken birleşim çizgisi görünmesin diye üstte tam genişlik klip oynar; yarılar yalnız katlanırken görünür.
- **Katlanma devri:** `katlanma`'da `#duoUst` gizlenir, yarılardaki `.ic-kopya` (son kare + kalan üst katmanlar)
  görünür; sol yarı 0 → 180 döner, iç ekran kapanmanın son kısmında kararır, `#disKarart` kapanınca söner ve
  `#disSon` görünür.

## 5. Tuzaklar

- `data-start`'lı `<video>` zamanlı bir öğenin içine konmaz (Hyperframes); bu yüzden cihaz bölümü zamansız.
- Her tween `fromTo` + `immediateRender: false` (`ft()` sarmalayıcısı): Hyperframes zaman çizelgesini rastgele
  noktalara sarar.
- GSAP 3.14 `scaleZ` tanımaz. Kimlikler tekil: ikinci kopya kimliksiz üretilir.
- Ölçek `transform: scale` değil `zoom` — bu kuralı bozan her değişiklik yazıyı bulanıklaştırır.
- `hyperframes check` kontrast ve yerleşim denetler; başlık zeminle yeterli kontrastta olmalı.
- Simülatör noktası ↔ piksel: iç ekranda 1 nokta = 3 gerçek piksel; kayıt yataya döndürülmüş hâliyle ölçülür.
