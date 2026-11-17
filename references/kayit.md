# Simülatörde kayıt

Uygulama ekranı değiştiyse kayıt yeniden alınır. Yalnız metin, zamanlama ya da gövde değişiyorsa kayda dokunma —
var olan kayıttan `kes` ile yeniden kesmek yeter.

## Cihazı ve ekranları bul

```bash
xcrun simctl list devices | grep -i "iphone duo"          # UDID; yoksa Xcode'da iPhone Duo simülatörü oluştur
xcrun simctl io <UDID> enumerate                           # ekran (Display) portları
```

İki ekran vardır: **iç** (varsayılan boyutu ~2007×2853, dikey çerçeve tamponu) ve **dış** (~1398×2034).
`simctl io recordVideo` aynı anda TEK ekran kaydeder; dış ekran gerekiyorsa ayrı bir kayıt al.

- Menteşe: iOS Simülatör aracının `duo_pose` eylemi — `closed`, `half_open` (`angle: 100`), `open`; `duo_hinge`
  durumu söyler. Bu araç yoksa pozu Simulator uygulamasından elle değiştir; kayıt sırası aynıdır. Gövde hareketi
  kayda girmez; videoda CSS 3B çizilir.
- Uygulamayı simülatöre kur ve aç (iOS Simülatör aracı `build` / `launch`, ya da projenin kendi komutu).
- Veriyi gerçekçi kur: boş liste ya da "deneme" metinleri tanıtımı zayıflatır. Yerel bir test ortamı/sunucusu
  gerekiyorsa projenin kendi geliştirme betiğini kullan; test hesabıyla gir.
- Simülatör Mac'in sistem vekilini (proxy) kullanır: `localhost` bir vekile gidiyorsa (bağlantı hatası, 502) yerel
  sunucuyu Mac'in ağ adresinden yayınla ve backend'in kendi istekleri için `no_proxy` ver. Sistem ayarını değiştirme.

## Kayıt sırası

Cihaz kapalı, uygulama ilk gösterilecek ekranda:

```bash
nohup xcrun simctl io <UDID> recordVideo --codec=h264 --display=<İÇ EKRAN UUID> --force kayit-ic.mov > ic.log 2>&1 &
echo $! > ic.pid
```

1. ~2 sn bekle → `duo_pose half_open angle 100` → **3 sn bekle.** İşletim sistemi iç ekranı kararmış yakar, ~0.9 sn'de
   netleştirir. Videodaki yarı açık bekleme bu oturmuş net kareden kesilir; kısa beklersen yalnız kararmış hâl kalır.
2. `duo_pose open` → 1–2 sn (ekran değişmez).
3. Uygulamada göstereceğin akışı yap: her dokunuşun noktasını (simülatör noktası) ve kayıttaki saniyesini not et —
   simülatör dokunuşu görüntüye girmez, videoda dokunuş izi bu notlardan çizilir (`ic.dokunuslar`).
4. Bitince: `kill -INT $(cat ic.pid)` ve dosyanın kapanmasını bekle (`ffprobe` süre verene kadar).

Dış ekran için aynısını cihaz kapalıyken dış ekranın UUID'siyle yap (`--ekran dis` kesimi döndürmez).

## Kesim aralıklarını seçme

Göz kararı değil, ölçerek:

```bash
# Parlaklık eğrisi: iç ekranın yandığı ve netleştiği an
ffmpeg -i kayit-ic.mov -vf "fps=4,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-" -f null - 2>/dev/null \
  | grep -o "YAVG=[0-9.]*"
# Kare tablosu: dokunma ve ekran geçiş anları
ffmpeg -i kayit-ic.mov -vf "fps=4,transpose=1,scale=300:-1,tile=6x6" -frames:v 1 tablo.png
```

Tipik iç ekran kesimi üç parça: **yanma + netleşme** (~1 sn) · **net bekleme + düzleşme** (~2 sn) · **uygulama
akışı**. `--parcalar "2.1-3.1,3.1-5.15,19.5-25.25"` gibi; parçalar sırayla birleştirilir. Sonra `video.json`'da
`ic.duzles`'i (kesim içinde düzleşmenin başladığı saniye; netleşme + ~0.5) ve dokunuşların kesim içindeki saniyelerini
yeni kesime göre yaz.

## Durum sütunu görüntüsü

Açık pozda iç ekranın görüntüsünü al (iOS Simülatör aracı `screenshot`, tam çözünürlük, yatay ~2853×2007). Duvar
kâğıdı/arka plan açık renkli olmalı (simge koyu çıkar). `katlanir.py durum <png>` saat + halka + noktaları saydam
PNG'ye çevirir; kesit varsayılanı iPhone Duo içindir, başka yerleşimde `--kesit x0,y0,x1,y1`.
