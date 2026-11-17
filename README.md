# katlanir-video

iOS uygulamanız için **katlanır telefon tanıtım videosu** üreten bir [Claude Code](https://claude.com/claude-code)
becerisi. Ekranlarda simülatörün **gerçek kaydı** oynar, gövde 3B olarak gerçekten katlanır. Çıktı dikey ve yatay
**4K**.

Akış şöyle:

1. Cihaz kapalı girer; dış ekranda uygulamanız çalışır.
2. Menteşe yarı açılır, iç ekran yanar ve kısa bir an bekler.
3. Cihaz tam açılır; uygulama geniş ekranda sürer.
4. Sonda o anki ekranla doğrudan kapanır.
5. Logonuz ve sloganınızla biter.

## Neden gerçek kayıt?

Arayüzü yeniden çizmek her zaman küçük farklarla ele verir: bir simge, bir boşluk, bir yazı tipi. Bu beceride
ekranlar iPhone Duo simülatörünün kendi kaydıdır; yarı açıkta katlı yarının kararması ve açılınca netleşmesi
işletim sisteminin kendi animasyonudur. Yalnız gövde hareketi üretilir, çünkü ekran kaydı onu içermez. İki yarı
menteşe çevresinde döner, ekrandaki görüntü de onlarla birlikte kıvrılır.

## Kurulum

```bash
git clone https://github.com/ozp3/katlanir-video ~/.claude/skills/katlanir-video
pip3 install pillow
```

Gerekenler:

- macOS ve iPhone Duo simülatörü olan Xcode
- `ffmpeg`
- Node.js (`npx`; render için [Hyperframes](https://www.npmjs.com/package/hyperframes) kendiliğinden iner)
- Python 3

## Kullanım

Claude Code'a söylemeniz yeterli:

> uygulamamın katlanır telefon videosunu hazırla

Beceri kaydı alır, keser, videoyu kurar, kare kare kontrol eder ve render eder. Adımları elle de koşabilirsiniz:

```bash
K=~/.claude/skills/katlanir-video/scripts/katlanir.py
python3 $K ornek                                            # video.json taslağı
python3 $K kes kayit-ic.mov --ekran ic --parcalar "2.1-3.1,3.1-5.15,19.5-25.25"
python3 $K durum ekran.png                                  # saat + durum simgesi, gerçek ekrandan
python3 $K uret                                             # kompozisyonlar + denetim
python3 $K kare                                             # anahtar anların kareleri
python3 $K render                                           # 4K + poster + 1080p kopya
```

Her şey tek bir `video.json`'dan gelir:

- dış ekranda oynayacaklar,
- iç ekran kaydı ve dokunuş noktaları,
- üst katmanlar,
- başlıklar,
- açılış ve kapanış.

Alanların açıklaması `references/yapilandirma.md`'de, kaydın nasıl alınacağı `references/kayit.md`'de.

## English

A Claude Code skill that makes a **foldable-phone promo video** for your iOS app. The screens are the iPhone Duo
simulator's **real recording**, and the 3D body actually folds: it starts closed, opens half-way, holds, opens flat,
then closes straight from the open screen. You get 4K output in portrait and landscape, built with
[Hyperframes](https://www.npmjs.com/package/hyperframes).

Install with
`git clone https://github.com/ozp3/katlanir-video ~/.claude/skills/katlanir-video`, then ask Claude Code for a
foldable phone video of your app. The docs and the config keys are in Turkish.

## Lisans

[MIT](LICENSE). Ses efektleri [Kenney](https://kenney.nl) paketlerinden; lisansları CC0.
