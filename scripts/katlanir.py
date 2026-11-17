#!/usr/bin/env python3
"""Katlanır telefon (iPhone Duo simülatörü) tanıtım videosu — gerçek ekran kaydı + 3B katlanan gövde, dikey/yatay 4K.

  ornek   çalışma dizinine örnek video.json yazar
  kes     simülatör kaydından klip keser (iç ekran: tam + sol/sağ yarı; dış ekran: tek klip), kaydın kendi çözünürlüğünde
  durum   iç ekranın görüntüsünden sağ sütundaki saat + durum simgesini saydam PNG olarak keser
  uret    video.json'dan Hyperframes kompozisyonlarını yazar (katlanir-dikey/, katlanir-yatay/) ve denetler
  kare    anahtar anların karelerini alır (temas sayfası)
  render  4K render → poster ilk kareye → son kodlama → 1080p kopya

Çalışma dizini = video.json'un dizini. Kayıtlar `kayit/` altına, çıktılar `<ad>-<biçim>.mp4` olarak yazılır.
Gerekenler: ffmpeg/ffprobe, Node (npx), Python 3 + Pillow. Kullanım: python3 katlanir.py <komut> -h
"""
import argparse, json, math, os, re, shutil, subprocess, sys
from string import Template

BECERI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HF = ["npx", "--yes", "hyperframes@0.8.60"]
COZ = {"dikey": "portrait-4k", "yatay": "landscape-4k"}
KUCUK = {"dikey": "1080:1920", "yatay": "1920:1080"}
VIDEO_UZ = (".mp4", ".mov", ".webm", ".m4v")

# ── Cihaz geometrisi (cihaz pikseli; iPhone Duo simülatörünün ekran oranlarına göre) ──
WP, HP, RD = 1012, 1440, 118                  # kapalı gövde; açık gövde 2·WP
IC_X, IC_Y, IC_W, IC_H = 22, 25, 1980, 1390   # iç ekran (gerçek 2852×2006, yatay)
IC_YARIM = IC_W // 2
SOL_W = IC_YARIM + 20                          # sol yarının videosu menteşeden taşar: birleşimde çizgi kalmaz
DS_X, DS_Y, DS_W, DS_H = 34, 24, 956, 1391     # dış ekran (gerçek 1398×2034)
IC_PIK, DS_PIK = (2852, 2006), (1398, 2034)
IC_PT = IC_W / (IC_PIK[0] / 3)                 # simülatör noktası → cihaz pikseli
DS_PT = DS_W / (DS_PIK[0] / 3)
AY, PERSP = 24, 8500                           # yarı açık: her yarı ±24°; kamera ≈ 8.4 yarım genişlik
DURUM_KESIT = (2620, 90, 2800, 305)            # gerçek iç ekranda saat + durum bloğu
DURUM_DIS = (1164, 249)                        # gerçek dış ekranda aynı bloğun sol üst köşesi
KATLA_SURE = 0.7

BICIM = {
    "dikey": dict(W=1080, H=1920, CX=540, CY_K=1166, SK=0.9, CY_Y=1040, SY=0.52, CY_A=1040, SA=0.505,
                  BASLIK="left: 70px; right: 70px; top: 250px; font-size: 84px; line-height: 1.1; text-wrap: balance;",
                  LOGO=240, LOGO_K=176, MARKA=124, SATIR1=116, SATIR=60,
                  ZEMIN=("left: 65px; top: 115px; width: 1080px; height: 1920px;",
                         "width: 1150px; height: 1150px; left: -470px; top: -380px;",
                         "width: 1050px; height: 1050px; right: -470px; top: 640px;",
                         "width: 1250px; height: 1250px; left: -420px; bottom: -520px;")),
    "yatay": dict(W=1920, H=1080, CX=960, CY_K=652, SK=0.55, CY_Y=652, SY=0.54, CY_A=660, SA=0.56,
                  BASLIK="left: 0; right: 0; top: 112px; font-size: 64px; line-height: 1.15;",
                  LOGO=184, LOGO_K=132, MARKA=96, SATIR1=104, SATIR=56,
                  ZEMIN=("left: 115px; top: 65px; width: 1920px; height: 1080px;",
                         "width: 1229px; height: 1229px; left: -422px; top: -499px;",
                         "width: 1114px; height: 1114px; right: -384px; top: 173px;",
                         "width: 1344px; height: 1344px; left: -307px; bottom: -653px;")),
}

ORNEK = {
    "ad": "tanitim",
    "bicimler": ["dikey", "yatay"],
    "zemin": "#fbfaf7",
    "vurgu": ["#2e4bc6", "#d96a7a", "#e8963c"],
    "yazi": {"renk": "#1b1a24"},
    "acilis": {"sure": 3.6, "logo": "logo.svg", "metin": "MARKA"},
    "kapali": {
        "ekran": [{"dosya": "kayit/dis-1.mp4"}, {"dosya": "kayit/dis-2.png", "sure": 4}],
        "dokunuslar": [{"an": 2.0, "x": 233, "y": 520}],
    },
    "ic": {
        "klip": "kayit/ic.mp4",
        "duzles": 1.5,
        "ek": 0,
        "dokunuslar": [{"an": 3.4, "x": 300, "y": 640}, {"an": 5.45, "x": 715, "y": 234}],
        "ust": [],
    },
    "katlanma": {"dis_ekran": "kayit/dis-son.png", "bekle": 1.0},
    "basliklar": [
        {"metin": "İlk başlık.", "bas": "giris+1", "bit": "acilma-0.4"},
        {"metin": "Açınca daha fazlası.", "bas": "tam+0.8", "bit": "katlanma"},
    ],
    "kapanis": {"sure": 4.5, "logo": "logo.svg", "satirlar": ["ornek.app", "Kısa bir slogan."]},
    "poster": "tam+2",
    "ses": True,
}


# ══════════════════════════ yardımcılar ══════════════════════════
def kos(cmd, cwd=None, yakala=False):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=yakala)
    if r.returncode != 0:
        if yakala:
            print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(f"başarısız (çıkış {r.returncode}): {cmd[0]}")
    return r.stdout if yakala else ""


def olc(yol):
    o = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,width,height,bit_rate:format=duration,size", "-of", "json", yol],
                                  capture_output=True, text=True).stdout or "{}")
    v = next((s for s in o.get("streams", []) if s.get("codec_type") == "video"), {})
    f = o.get("format", {})
    return dict(w=v.get("width"), h=v.get("height"), sure=round(float(f.get("duration", 0) or 0), 3),
                mbps=round(int(v.get("bit_rate", 0) or 0) / 1e6, 1), mib=round(int(f.get("size", 0) or 0) / 2**20, 1))


def cift(n):
    return n - (n % 2)


def yukle(yol):
    yol = os.path.abspath(yol or "video.json")
    if not os.path.isfile(yol):
        sys.exit(f"{yol} yok — önce `katlanir.py ornek` ile bir örnek yaz ve düzenle.")
    return json.load(open(yol, encoding="utf-8")), os.path.dirname(yol)


def kok_al(a):
    if getattr(a, "config", None):
        return os.path.dirname(os.path.abspath(a.config))
    return os.getcwd()


def mutlak(kok, yol):
    yol = os.path.expanduser(yol)
    return yol if os.path.isabs(yol) else os.path.join(kok, yol)


def video_mu(yol):
    return os.path.splitext(yol)[1].lower() in VIDEO_UZ


def son_kare(video, hedef):
    kos(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", video, "-frames:v", "1", "-update", "1", hedef])
    return hedef


def rgb(hexrenk):
    h = hexrenk.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


# ══════════════════════════ kes / durum / ornek ══════════════════════════
def ornek(a):
    yol = os.path.abspath(a.cikti or "video.json")
    if os.path.exists(yol) and not a.ustune:
        sys.exit(f"{yol} zaten var (üstüne yazmak için --ustune)")
    json.dump(ORNEK, open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("yazıldı:", yol)


def kes(a):
    kok = kok_al(a)
    kayit = os.path.abspath(a.kayit)
    parcalar = [tuple(float(x) for x in p.split("-")) for p in a.parcalar.split(",")] if a.parcalar else []
    o = olc(kayit)
    # iç ekranın çerçeve tamponu dikey kaydedilir (2006×2852) → yataya döndür; dış ekran zaten dikey
    dondur = "transpose=1," if (a.ekran == "ic" and o["h"] > o["w"]) else ""
    hedef = os.path.join(kok, "kayit")
    os.makedirs(hedef, exist_ok=True)
    ad = a.ad or a.ekran
    kod = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "10", "-preset", "slow", "-an", "-movflags", "+faststart"]
    cikti = os.path.join(hedef, f"{ad}.mp4")
    if parcalar:
        n = len(parcalar)
        f = f"[0:v]fps=30,{dondur}setsar=1,split={n}" + "".join(f"[p{i}]" for i in range(n)) + ";"
        f += ";".join(f"[p{i}]trim=start={b}:end={e},setpts=PTS-STARTPTS[q{i}]" for i, (b, e) in enumerate(parcalar)) + ";"
        f += "".join(f"[q{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[o]"
        kos(["ffmpeg", "-v", "error", "-y", "-i", kayit, "-filter_complex", f, "-map", "[o]"] + kod + [cikti])
    else:
        kos(["ffmpeg", "-v", "error", "-y", "-i", kayit, "-vf", f"fps=30,{dondur}setsar=1"] + kod + [cikti])
    t = olc(cikti)
    if a.ekran == "ic":
        W, H = t["w"], t["h"]
        kos(["ffmpeg", "-v", "error", "-y", "-i", cikti, "-vf", f"crop={cift(round(W * SOL_W / IC_W))}:{H}:0:0"] + kod
            + [os.path.join(hedef, f"{ad}-sol.mp4")])
        kos(["ffmpeg", "-v", "error", "-y", "-i", cikti, "-vf", f"crop={cift(W - W // 2)}:{H}:{W // 2}:0"] + kod
            + [os.path.join(hedef, f"{ad}-sag.mp4")])
        print(f"{ad}.mp4 + {ad}-sol.mp4 + {ad}-sag.mp4: {W}×{H}, {t['sure']} sn → {hedef}")
    else:
        print(f"{ad}.mp4: {t['w']}×{t['h']}, {t['sure']} sn → {hedef}")


def durum(a):
    from PIL import Image
    kok = kok_al(a)
    im = Image.open(a.ekran).convert("RGB")
    w, h = im.size
    if h > w:
        sys.exit(f"görüntü dikey ({w}×{h}); iç ekranın YATAY görüntüsünü ver (~2853×2007)")
    k = tuple(int(x) for x in a.kesit.split(",")) if a.kesit else tuple(round(v * w / 2853) for v in DURUM_KESIT)
    c = im.crop(k).convert("L")
    cw, ch = c.size
    kenar = sorted([c.getpixel((x, y)) for y in range(ch) for x in (0, 1, cw - 2, cw - 1)] + [c.getpixel((x, 0)) for x in range(cw)])
    zemin, en_koyu = kenar[len(kenar) // 2], min(c.getpixel((x, y)) for y in range(ch) for x in range(cw))
    renk = tuple(int((a.renk or "#1b1a24").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    out = Image.new("RGBA", (cw, ch))
    px = []
    for y in range(ch):
        for x in range(cw):
            al = max(0.0, min(1.0, (zemin - c.getpixel((x, y))) / max(1, zemin - en_koyu)))
            px.append(renk + (0 if al < 0.03 else round(al * 255),))
    out.putdata(px)
    hedef = os.path.join(kok, "kayit")
    os.makedirs(hedef, exist_ok=True)
    out.save(os.path.join(hedef, "durum.png"))
    on = Image.new("RGBA", (cw, ch), (251, 250, 247, 255))
    on.alpha_composite(out)
    on.resize((cw * 2, ch * 2)).save(os.path.join(hedef, "durum-onizleme.png"))
    print(f"durum.png {cw}×{ch} (kesit {k}) → {hedef}; önizleme durum-onizleme.png")


# ══════════════════════════ zaman çizelgesi ══════════════════════════
def zamanla(cfg, kok):
    ac = cfg.get("acilis")
    giris = float(ac.get("sure", 3.6)) if ac else 0.0
    ogeler, t = [], giris
    for o in cfg["kapali"]["ekran"]:
        yol = mutlak(kok, o["dosya"])
        s = float(o.get("sure") or (olc(yol)["sure"] if video_mu(yol) else 3.0))
        ogeler.append(dict(o, yol=yol, bas=t, sure=s))
        t += s
    acilma = giris + float(cfg["kapali"].get("sure") or (t - giris))
    ic = cfg["ic"]
    klip_yol = mutlak(kok, ic["klip"])
    klip_sure = olc(klip_yol)["sure"]
    klip = acilma + 0.2                                   # menteşe açılırken iç ekran yanar (kayıtta kararmış yanar)
    duzles = klip + float(ic.get("duzles", 1.5))          # kayıtta ekran oturduktan ~0.5 sn sonra düzleşir
    katlanma = klip + klip_sure + float(ic.get("ek", 0))
    kapali = katlanma + KATLA_SURE
    cikis = kapali + float(cfg.get("katlanma", {}).get("bekle", 1.0))
    kp = cfg.get("kapanis")
    kapanis = cikis + 0.45
    son = kapanis + float(kp.get("sure", 4.5)) if kp else cikis + 0.8
    anlar = dict(bas=0.0, giris=giris, acilma=acilma, klip=klip, duzles=duzles, tam=duzles + 0.55,
                 klip_son=klip + klip_sure, katlanma=katlanma, kapali=kapali, cikis=cikis, kapanis=kapanis, son=son)
    return {k: round(v, 3) for k, v in anlar.items()}, ogeler, klip_yol, klip_sure


def an_coz(x, anlar, taban):
    """Sayı → taban anı + sayı; metin → 'ad', 'ad+1.5', 'ad-0.4' (ad: anlar sözlüğünden)."""
    if isinstance(x, (int, float)):
        return round(anlar[taban] + float(x), 3)
    m = re.fullmatch(r"\s*([a-z_]+)\s*(?:([+-])\s*([\d.]+))?\s*", str(x))
    if not m or m.group(1) not in anlar:
        sys.exit(f"anlaşılmayan an: {x!r} (geçerli adlar: {', '.join(anlar)})")
    t = anlar[m.group(1)] + (float(m.group(3)) * (1 if m.group(2) == "+" else -1) if m.group(2) else 0)
    return round(t, 3)


# ══════════════════════════ şablonlar ══════════════════════════
CSS = Template("""
      $yazi_css
      :root { --zemin: $zemin; --ink: $ink; --font: $font; }
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: ${W}px; height: ${H}px; overflow: hidden; background: var(--zemin); }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; font-family: var(--font); color: var(--ink); background: var(--zemin); }
      .clip { position: absolute; inset: 0; }
      .gizli { opacity: 0; visibility: hidden; }

      /* Zemin: üç yumuşak renk kütlesi, yavaş gezinir ve renk değiştirir */
      .zemin { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
      .zemin__ortu { position: absolute; inset: -6%; filter: blur(34px); }
      .zemin__alan { position: absolute; $z0 }
      .sekil { position: absolute; mix-blend-mode: multiply; isolation: isolate; will-change: transform; }
      .sekil > i { position: absolute; inset: 0; display: block; border-radius: inherit; }
      .sekil--1 { $z1 border-radius: 58% 42% 38% 62% / 66% 44% 56% 34%; }
      .sekil--2 { $z2 border-radius: 40% 60% 66% 34% / 40% 34% 66% 60%; }
      .sekil--3 { $z3 border-radius: 62% 38% 34% 66% / 68% 42% 58% 32%; }
      .k1 { --renk: $r1; } .k2 { --renk: $r2; } .k3 { --renk: $r3; }
      .sekil--1 > i { background: radial-gradient(circle at 38% 34%, rgba(var(--renk), 0.4), rgba(var(--renk), 0.22) 62%, rgba(var(--renk), 0.1) 100%); }
      .sekil--2 > i { background: radial-gradient(circle at 62% 44%, rgba(var(--renk), 0.36), rgba(var(--renk), 0.2) 62%, rgba(var(--renk), 0.09) 100%); }
      .sekil--3 > i { background: radial-gradient(circle at 46% 58%, rgba(var(--renk), 0.34), rgba(var(--renk), 0.18) 62%, rgba(var(--renk), 0.09) 100%); }
      .sekil--1 > .k2, .sekil--1 > .k3, .sekil--2 > .k1, .sekil--2 > .k3, .sekil--3 > .k1, .sekil--3 > .k2 { opacity: 0; }

      /* Açılış / kapanış */
      .orta { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; padding-bottom: 40px; }
      .logo { display: block; width: ${LOGO}px; height: ${LOGO}px; object-fit: contain; margin-bottom: ${LOGO_ARA}px; }
      .logo--kucuk { width: ${LOGO_K}px; height: ${LOGO_K}px; margin-bottom: ${LOGO_K_ARA}px; }
      .marka { font-weight: 300; font-size: ${MARKA}px; line-height: 1.1; letter-spacing: 0.14em; padding-left: 0.14em; }
      .satir1 { font-weight: 300; font-size: ${SATIR1}px; line-height: 1.1; letter-spacing: 0.04em; padding-left: 0.04em; }
      .satir { font-weight: 400; font-size: ${SATIR}px; line-height: 1.2; letter-spacing: -0.01em; margin-top: ${SATIR_ARA}px; }
      .baslik { position: absolute; $BASLIK text-align: center; font-weight: 400; letter-spacing: -0.015em; }

      /* ══ Katlanır gövde: sol yarı menteşe (sağ kenarı) çevresinde döner, sağ yarının üstüne katlanır; kapalıyken
         menteşe omurgası solda, dış ekran sol yarının arka yüzünde. Ölçek CSS zoom (transform ölçeği yazıyı bulanıklaştırır). ══ */
      .sahne-yer { position: absolute; left: ${CX}px; top: ${CY_K}px; width: 0; height: 0; }
      .sahne3d { position: absolute; left: 0; top: 0; width: 0; height: 0; perspective: ${PERSP}px; perspective-origin: 0 0; zoom: $SK; }
      .duo { position: absolute; left: -${WP}px; top: -${HP2}px; width: ${WP2}px; height: ${HP}px; transform-style: preserve-3d; }
      .yarim { position: absolute; top: 0; width: ${WP}px; height: ${HP}px; transform-style: preserve-3d; }
      .yarim--sol { left: 0; transform-origin: 100% 50%; }
      .yarim--sag { left: ${WP}px; transform-origin: 0% 50%; }
      .govde { position: absolute; inset: 0; background: #060607; box-shadow: inset 0 0 0 9px #48484c, inset 0 0 0 11px #26262a; }
      .govde--sag { border-radius: 16px ${RD}px ${RD}px 16px; box-shadow: inset 0 0 0 9px #48484c, inset 0 0 0 11px #26262a, 0 40px 100px rgba(27, 26, 36, 0.24), 0 10px 26px rgba(27, 26, 36, 0.14); }
      .govde--sol { border-radius: ${RD}px 16px 16px ${RD}px; }
      .yuz { position: absolute; inset: 0; backface-visibility: hidden; -webkit-backface-visibility: hidden; }
      .yuz--arka { transform: rotateY(180deg); border-radius: 16px ${RD}px ${RD}px 16px; }
      .tus { position: absolute; border-radius: 5px; background: linear-gradient(#636367, #3c3c40); }
      .tus--ust1 { top: -8px; height: 12px; left: ${T1}px; width: ${T1W}px; }
      .tus--ust2 { top: -8px; height: 12px; left: ${T2}px; width: ${T2W}px; }
      .tus--yan { right: -8px; width: 12px; top: ${TY}px; height: ${TYH}px; }
      /* Menteşe omurgası: gövdenin ARKASINDA düz koyu şerit, üstten/alttan içeride (parlak kapsül değil) */
      .omurga { position: absolute; left: -29px; top: 19px; bottom: 19px; width: 29px; border-radius: 12px 0 0 12px; background: #444446; }
      .ic-pencere { position: absolute; top: ${IC_Y}px; width: ${IC_YARIM}px; height: ${IC_H}px; overflow: hidden; background: #000; }
      .ic-pencere--sol { left: ${IC_X}px; width: ${IC_YARIM6}px; border-radius: 96px 0 0 96px; background: transparent; }
      .ic-pencere--sol .ic-video { width: ${SOL_W}px; }
      .ic-pencere--sag { left: 0; border-radius: 0 96px 96px 0; }
      .ic-video { position: absolute; left: 0; top: 0; width: ${IC_YARIM}px; height: ${IC_H}px; display: block; object-fit: fill; }
      .tam { position: absolute; left: 0; top: 0; width: ${IC_W}px; height: ${IC_H}px; display: block; object-fit: fill; }
      .ic-kopya { position: absolute; top: 0; width: ${IC_W}px; height: ${IC_H}px; }
      .duo-ust { position: absolute; left: ${IC_X}px; top: ${IC_Y}px; width: ${IC_W}px; height: ${IC_H}px; border-radius: 96px; overflow: hidden; transform: translateZ(6px); }
      .ust { position: absolute; inset: 0; }
      .ust > .medya { position: absolute; display: block; object-fit: cover; }
      .dis-ekran { position: absolute; left: ${DS_X}px; top: ${DS_Y}px; width: ${DS_W}px; height: ${DS_H}px; border-radius: 40px 96px 96px 40px; overflow: hidden; background: #000; }
      .dis-oge { position: absolute; inset: 0; }
      .dis-oge > .medya { position: absolute; inset: 0; width: 100%; height: 100%; display: block; object-fit: cover; }
      .durum { position: absolute; display: block; }
      .karart { position: absolute; inset: 0; background: #000; }
      .kamera { position: absolute; left: 819px; top: 59px; width: 77px; height: 77px; border-radius: 50%; background: #050507; box-shadow: inset 0 0 0 3px #15151a; }
      .dokunus { position: absolute; left: 0; top: 0; width: 84px; height: 84px; border-radius: 50%; background: rgba(27, 26, 36, 0.22); border: 3px solid rgba(255, 255, 255, 0.85); box-shadow: 0 8px 22px rgba(27, 26, 36, 0.22); }
      .dalga { position: absolute; width: 120px; height: 120px; border-radius: 50%; background: rgba(43, 63, 158, 0.3); }
      .dokunus--ic { width: 112px; height: 112px; border-width: 4px; }
      .dalga--ic { width: 160px; height: 160px; }
""")


def html_yaz(cfg, kok, b, comp):
    P = BICIM[b]
    W, H = P["W"], P["H"]
    anlar, ogeler, klip_yol, klip_sure = zamanla(cfg, kok)
    A = lambda x, taban="bas": an_coz(x, anlar, taban)
    varliklar = os.path.join(comp, "assets")
    os.makedirs(varliklar, exist_ok=True)
    kopyalanan = {}

    def varlik(yol, ad=None):
        yol = os.path.abspath(yol)
        if yol not in kopyalanan:
            if not os.path.isfile(yol):
                sys.exit(f"dosya yok: {yol}")
            hedef_ad = ad or f"{len(kopyalanan):02d}-{os.path.basename(yol)}"
            shutil.copy2(yol, os.path.join(varliklar, hedef_ad))
            kopyalanan[yol] = "assets/" + hedef_ad
        return kopyalanan[yol]

    def medya(yol, sinif, stil="", baslangic=None, sure=None, iz=[100]):
        src = varlik(yol)
        if video_mu(yol):
            iz[0] += 1
            return (f'<video class="{sinif}" src="{src}" style="{stil}" data-start="{baslangic}" data-duration="{sure}" '
                    f'data-track-index="{iz[0]}" muted playsinline></video>')
        return f'<img class="{sinif}" src="{src}" style="{stil}" alt="" />'

    durum_yol = mutlak(kok, cfg.get("durum", "kayit/durum.png"))
    def durum_img(ic=True):
        if not os.path.isfile(durum_yol):
            sys.exit(f"'durum: true' isteniyor ama {durum_yol} yok — önce `katlanir.py durum <ekran.png>`")
        if ic:
            o, x, y = IC_W / IC_PIK[0], DURUM_KESIT[0], DURUM_KESIT[1]
        else:
            o, x, y = DS_W / DS_PIK[0], DURUM_DIS[0], DURUM_DIS[1]
        return (f'<img class="durum" src="{varlik(durum_yol, "durum.png")}" alt="" data-layout-ignore style="left: {x * o:.1f}px; '
                f'top: {y * o:.1f}px; width: {180 * o:.1f}px; height: {215 * o:.1f}px;" />')

    js, ses = [], []
    def J(s):
        js.append(s)
    def cal(t, *dosyalar):
        for i, (d, vol) in enumerate(dosyalar):
            ses.append((round(t + 0.04 * i, 3), d, vol))
    S_LOGO = (("logo-1.ogg", 0.45), ("logo-2.ogg", 0.28))
    S_KATLA, S_TIK, S_GECIS, S_GIRIS = (("katla.ogg", 0.24),), (("tikla-1.ogg", 0.55), ("tikla-2.ogg", 0.23)), (("gecis.ogg", 0.22),), (("giris.ogg", 0.16),)

    # ── dış ekran (kapalı bölüm) ──
    dis_html = []
    for i, o in enumerate(ogeler):
        ic = medya(o["yol"], "medya", baslangic=o["bas"], sure=round(o["sure"] + 0.5, 3))   # +0.5: geçişte üst üste
        dis_html.append(f'<div class="dis-oge{"" if i == 0 else " gizli"}" id="dis{i}">{ic}{durum_img(False) if o.get("durum") else ""}</div>')
        if i:
            J(f'gecis("#dis{i - 1}", "#dis{i}", {o["bas"]}, 0.3);')
            cal(o["bas"], *S_GECIS)
    kd = cfg.get("katlanma", {}).get("dis_ekran")
    son_yol = mutlak(kok, kd) if kd else None
    if not son_yol:   # verilmediyse kapalı bölümün son öğesinin son karesi
        son_yol = ogeler[-1]["yol"]
    if video_mu(son_yol) and not kd:
        son_yol = son_kare(son_yol, os.path.join(varliklar, "dis-son-kare.png"))
    dis_html.append(f'<div class="dis-oge gizli" id="disSon">{medya(son_yol, "medya", baslangic=anlar["katlanma"], sure=round(anlar["son"] - anlar["katlanma"], 3))}'
                    f'{durum_img(False) if cfg.get("katlanma", {}).get("durum") else ""}</div>')

    # ── iç ekran: klip (yarılar + düzken tam), üst katmanlar, katlanırken donmuş son hâl ──
    kok_ad = os.path.splitext(klip_yol)[0]
    sol_yol, sag_yol = kok_ad + "-sol.mp4", kok_ad + "-sag.mp4"
    for y in (sol_yol, sag_yol):
        if not os.path.isfile(y):
            sys.exit(f"{y} yok — iç ekran klibini `katlanir.py kes --ekran ic` ile kes (yarıları o üretir)")
    ks = round(klip_sure, 3)
    ic_son = son_kare(klip_yol, os.path.join(varliklar, "ic-son-kare.png"))
    ust_html, kopya_ic = [], [f'<img class="tam" src="{varlik(ic_son)}" alt="" />']
    for i, u in enumerate(cfg["ic"].get("ust", [])):
        yol = mutlak(kok, u["dosya"])
        bas = A(u["bas"], "klip")
        bit = A(u["bit"], "klip") if u.get("bit") is not None else None
        x, y, w, h = [v * IC_PT for v in u["kutu"]] if u.get("kutu") else (0, 0, IC_W, IC_H)
        stil = f"left: {x:.1f}px; top: {y:.1f}px; width: {w:.1f}px; height: {h:.1f}px;"
        if bas < anlar["tam"]:
            print(f"⚠ üst katman {i} cihaz düzleşmeden ({anlar['tam']}) başlıyor; düz açıkken görünür")
        sure = round((bit if bit else anlar["katlanma"]) - bas, 3)
        ust_html.append(f'<div class="ust gizli" id="ust{i}">{medya(yol, "medya", stil, bas, sure)}{durum_img() if u.get("durum") else ""}</div>')
        J(f'ft("#ust{i}", {{ autoAlpha: 0, scale: 0.88 }}, {{ autoAlpha: 1, scale: 1, duration: 0.42, ease: "power3.out" }}, {bas});')
        cal(bas, *S_GECIS)
        if bit is not None and bit < anlar["katlanma"] - 0.05:
            J(f'ft("#ust{i}", {{ autoAlpha: 1, scale: 1 }}, {{ autoAlpha: 0, scale: 0.88, duration: 0.38, ease: "power2.in" }}, {bit});')
            cal(bit, *S_GECIS)
        else:   # katlanma anında ekranda: yarıların donmuş kopyasına girer ("o anki ekran kalır")
            kare_yol = son_kare(yol, os.path.join(varliklar, f"ust{i}-son-kare.png")) if video_mu(yol) else yol
            kopya_ic.append(f'<img class="medya" src="{varlik(kare_yol)}" alt="" style="position: absolute; object-fit: cover; {stil}" />'
                            + (durum_img() if u.get("durum") else ""))
    kopya = "".join(kopya_ic)

    # ── dokunuş izleri (simülatör dokunuşları kayda girmez; nokta = simülatör noktası) ──
    dokunus_html = {"ic": [], "dis": []}
    def dokunuslar(liste, yuzey, taban):
        if not liste:
            return
        pt, r, rd, kap = (IC_PT, 56, 80, "ic") if yuzey == "ic" else (DS_PT, 42, 60, "dis")
        noktalar = sorted(({"t": A(d["an"], taban), "x": round(d["x"] * pt), "y": round(d["y"] * pt)} for d in liste), key=lambda d: d["t"])
        gruplar, g = [], [noktalar[0]]
        for n in noktalar[1:]:
            if n["t"] - g[-1]["t"] <= 2.5:
                g.append(n)
            else:
                gruplar.append(g); g = [n]
        gruplar.append(g)
        for gi, g in enumerate(gruplar):
            did = f"{kap}dokun{gi}"
            ek = " dokunus--ic" if kap == "ic" else ""
            dokunus_html[kap].append(f'<div class="dokunus{ek} gizli" id="{did}"></div>')
            bas = {"x": g[0]["x"] + 170, "y": g[0]["y"] + 150}
            J(f'tl.set("#{did}", {{ x: {bas["x"] - r}, y: {bas["y"] - r}, scale: 1 }}, 0);')
            J(f'ft("#{did}", {{ autoAlpha: 0 }}, {{ autoAlpha: 1, duration: 0.22, ease: "power1.out" }}, {round(g[0]["t"] - 0.5, 3)});')
            J(f'ft("#{did}", {{ x: {bas["x"] - r}, y: {bas["y"] - r} }}, {{ x: {g[0]["x"] - r}, y: {g[0]["y"] - r}, duration: 0.42, ease: "power3.out" }}, {round(g[0]["t"] - 0.5, 3)});')
            for ni, n in enumerate(g):
                dal = f"{did}d{ni}"
                ek2 = " dalga--ic" if kap == "ic" else ""
                dokunus_html[kap].append(f'<div class="dalga{ek2} gizli" id="{dal}" style="left: {n["x"] - rd}px; top: {n["y"] - rd}px;"></div>')
                if ni:
                    p = g[ni - 1]
                    J(f'ft("#{did}", {{ x: {p["x"] - r}, y: {p["y"] - r} }}, {{ x: {n["x"] - r}, y: {n["y"] - r}, duration: {round(max(0.1, min(1.0, n["t"] - p["t"] - 0.2)), 3)}, ease: "power3.inOut" }}, {round(p["t"] + 0.15, 3)});')
                J(f'ft("#{did}", {{ scale: 1 }}, {{ scale: 0.82, duration: 0.08, yoyo: true, repeat: 1, ease: "power1.inOut" }}, {n["t"]});')
                J(f'ft("#{dal}", {{ autoAlpha: 0.55, scale: 0.2 }}, {{ autoAlpha: 0, scale: 1.8, duration: 0.5, ease: "power2.out" }}, {n["t"]});')
                cal(n["t"], *S_TIK)
            J(f'ft("#{did}", {{ autoAlpha: 1 }}, {{ autoAlpha: 0, duration: 0.3, ease: "power1.inOut" }}, {round(g[-1]["t"] + 0.2, 3)});')
    dokunuslar(cfg["kapali"].get("dokunuslar"), "dis", "giris")
    dokunuslar(cfg["ic"].get("dokunuslar"), "ic", "klip")

    # ── başlıklar ──
    baslik_html = []
    for i, bs in enumerate(cfg.get("basliklar", [])):
        baslik_html.append(f'<h2 class="baslik gizli" id="baslik{i}" data-layout-allow-overlap>{bs["metin"]}</h2>')
        J(f'belir("#baslik{i}", {A(bs["bas"])}, 0.7, 20);')
        if bs.get("bit") is not None:
            J(f'sol("#baslik{i}", {A(bs["bit"])}, 0.45);')

    # ── açılış / kapanış ──
    ac, kp = cfg.get("acilis"), cfg.get("kapanis")
    acilis_html = kapanis_html = ""
    if ac:
        logo = f'<img class="logo gizli" id="aLogo" src="{varlik(mutlak(kok, ac["logo"]))}" alt="" />' if ac.get("logo") else ""
        metin = f'<div class="marka gizli" id="aMetin">{ac["metin"]}</div>' if ac.get("metin") else ""
        acilis_html = (f'<section id="s1" class="clip" data-start="0" data-duration="{anlar["giris"] + 0.4}" data-track-index="1">'
                       f'<div class="orta" id="s1ic">{logo}{metin}</div></section>')
        if logo:
            J('ft("#aLogo", { scale: 0.9, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "power3.out" }, 0.12);')
        if metin:
            J('belir("#aMetin", 0.5, 0.6, 16);')
        J(f'ft("#s1ic", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.45, ease: "power1.inOut" }}, {round(anlar["giris"] - 0.2, 3)});')
        cal(0.42, *S_LOGO)
    if kp:
        logo = f'<img class="logo logo--kucuk" id="kLogo" src="{varlik(mutlak(kok, kp["logo"]))}" alt="" />' if kp.get("logo") else ""
        satirlar = kp.get("satirlar", [])
        sat = "".join(f'<div class="{"satir1" if i == 0 else "satir"} gizli" id="kSatir{i}">{s}</div>' for i, s in enumerate(satirlar))
        kapanis_html = (f'<section id="s4" class="clip" data-start="{anlar["kapanis"]}" data-duration="{round(anlar["son"] - anlar["kapanis"], 3)}" '
                        f'data-track-index="4"><div class="orta" id="s4ic" style="opacity: 0">{logo}{sat}</div></section>')
        J(f'ft("#s4ic", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.7, ease: "power1.inOut" }}, {anlar["kapanis"] + 0.3});')
        if logo:
            J(f'ft("#kLogo", {{ scale: 0.94 }}, {{ scale: 1, duration: 0.8, ease: "power3.out" }}, {anlar["kapanis"] + 0.3});')
        for i in range(len(satirlar)):
            J(f'belir("#kSatir{i}", {round(anlar["kapanis"] + 0.45 + 0.65 * i, 3)}, 0.6, 12);')
        cal(anlar["kapanis"] + 0.38, *S_LOGO)

    # ── gövde hareketi ──
    XK = round(WP / 2 * P["SK"], 2)
    t = anlar
    cal(t["giris"] + 0.05, *S_GIRIS)
    cal(t["acilma"], *S_KATLA); cal(t["duzles"], *S_KATLA); cal(t["katlanma"], *S_KATLA)
    govde_js = Template("""
      tl.set("#duoSol", { rotationY: 180, z: 3 }, 0);
      tl.set("#duoSag", { rotationY: 0, z: -3 }, 0);
      tl.set("#sahne", { x: -$XK, y: $DIS }, 0);
      tl.set("#sahneZoom", { zoom: $SK }, 0);
      ft("#sahne", { y: $DIS }, { y: 0, duration: 0.95, ease: "power3.out" }, $giris);
      // Açılma: kapalı → yarı açık (dış ekran söner, iç ekran kayıtla yanar) → bekler → tam açık
      ft("#disKarart", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.15, ease: "none" }, $acilma);
      ft("#duoSol", { rotationY: 180 }, { rotationY: $AY, duration: 0.6, ease: "power2.inOut" }, $acilma);
      ft("#duoSag", { rotationY: 0 }, { rotationY: -$AY, duration: 0.6, ease: "power2.inOut" }, $acilma);
      ft("#sahne", { x: -$XK, y: 0 }, { x: 0, y: $DY, duration: 0.6, ease: "power2.inOut" }, $acilma);
      ft("#sahneZoom", { zoom: $SK }, { zoom: $SY, duration: 0.6, ease: "power2.inOut" }, $acilma);
      ft("#duoSol", { rotationY: $AY }, { rotationY: 0, duration: 0.55, ease: "power2.inOut" }, $duzles);
      ft("#duoSag", { rotationY: -$AY }, { rotationY: 0, duration: 0.55, ease: "power2.inOut" }, $duzles);
      ft("#sahne", { y: $DY }, { y: $DA, duration: 0.55, ease: "power2.inOut" }, $duzles);
      ft("#sahneZoom", { zoom: $SY }, { zoom: $SA, duration: 0.55, ease: "power2.inOut" }, $duzles);
      tl.set(["#icTam", "#icSon"], { autoAlpha: 1 }, $tam);
      // Katlanma: o anki ekran kalır (yarılardaki donmuş kopya), tam açıktan DOĞRUDAN kapalıya
      tl.set(".ic-kopya", { autoAlpha: 1 }, $katlanma);
      tl.set("#duoUst", { autoAlpha: 0 }, $katlanma);
      tl.set(".dis-oge", { autoAlpha: 0 }, $katlanma);
      tl.set("#disSon", { autoAlpha: 1 }, $katlanma);
      ft("#duoSol", { rotationY: 0 }, { rotationY: 180, duration: $KS, ease: "power2.inOut" }, $katlanma);
      ft("#sahne", { x: 0, y: $DA }, { x: -$XK, y: 0, duration: $KS, ease: "power2.inOut" }, $katlanma);
      ft("#sahneZoom", { zoom: $SA }, { zoom: $SK, duration: $KS, ease: "power2.inOut" }, $katlanma);
      ft(".ic-karart", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.2, ease: "none" }, $karart);
      ft("#disKarart", { autoAlpha: 1 }, { autoAlpha: 0, duration: 0.25, ease: "power1.out" }, $kapali);
      ft("#sahne", { y: 0 }, { y: $DIS, duration: 0.65, ease: "power2.in" }, $cikis);
""").substitute(XK=XK, DIS=H + 300, SK=P["SK"], SY=P["SY"], SA=P["SA"], AY=AY, DY=P["CY_Y"] - P["CY_K"], DA=P["CY_A"] - P["CY_K"],
                KS=KATLA_SURE, karart=round(t["katlanma"] + KATLA_SURE * 0.55, 3), **t)

    # ── zemin gezintisi ──
    n = math.ceil(t["son"] / 5) + 1
    zemin_js = Template("""
      ft("#sekil1", { x: 0, y: 0, scaleX: 1, scaleY: 1, rotation: 0 }, { x: 260, y: 320, scaleX: 1.28, scaleY: 0.82, rotation: 8, duration: $son, ease: "sine.inOut" }, 0);
      ft("#sekil2", { x: 0, y: 0, scaleX: 1.04, scaleY: 1, rotation: 0 }, { x: -250, y: -380, scaleX: 0.78, scaleY: 1.32, rotation: -10, duration: $son, ease: "sine.inOut" }, 0);
      ft("#sekil3", { x: 0, y: 0, scaleX: 1, scaleY: 1, rotation: 0 }, { x: 280, y: -340, scaleX: 1.22, scaleY: 0.86, rotation: 11, duration: $son, ease: "sine.inOut" }, 0);
      for (let i = 0; i < 3; i++) for (let s = 0; s < $n; s++) {
        const a = (i + s) % 3, b = (i + s + 1) % 3, t = s * 5 + 1.4;
        ft("#z" + (i + 1) + "k" + a, { opacity: 1 }, { opacity: 0, duration: 2.5, ease: "power1.inOut" }, t);
        ft("#z" + (i + 1) + "k" + b, { opacity: 0 }, { opacity: 1, duration: 2.5, ease: "power1.inOut" }, t);
      }
""").substitute(son=t["son"], n=n)

    # ── ses ──
    ses_html = ""
    if cfg.get("ses", True):
        ses.sort()
        ses_html = "\n".join(f'      <audio id="sfx{i:02d}" src="assets/sfx/{d}" data-start="{tt}" data-track-index="{300 + i}" data-volume="{vol}"></audio>'
                             for i, (tt, d, vol) in enumerate(ses))
        shutil.copytree(os.path.join(BECERI, "assets", "sfx"), os.path.join(varliklar, "sfx"), dirs_exist_ok=True)

    # ── CSS ──
    yazi = cfg.get("yazi", {})
    vurgu = cfg.get("vurgu", ["#2e4bc6", "#d96a7a", "#e8963c"])
    css = CSS.substitute(
        yazi_css=open(mutlak(kok, yazi["css"]), encoding="utf-8").read() if yazi.get("css") else "",
        zemin=cfg.get("zemin", "#fbfaf7"), ink=yazi.get("renk", "#1b1a24"),
        font=yazi.get("aile", "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif"),
        W=W, H=H, z0=P["ZEMIN"][0], z1=P["ZEMIN"][1], z2=P["ZEMIN"][2], z3=P["ZEMIN"][3],
        r1=rgb(vurgu[0]), r2=rgb(vurgu[1]), r3=rgb(vurgu[2]),
        LOGO=P["LOGO"], LOGO_ARA=round(P["LOGO"] * 0.18), LOGO_K=P["LOGO_K"], LOGO_K_ARA=round(P["LOGO_K"] * 0.21),
        MARKA=P["MARKA"], SATIR1=P["SATIR1"], SATIR=P["SATIR"], SATIR_ARA=round(P["SATIR"] * 0.66), BASLIK=P["BASLIK"],
        CX=P["CX"], CY_K=P["CY_K"], PERSP=PERSP, SK=P["SK"], WP=WP, HP=HP, HP2=HP // 2, WP2=2 * WP, RD=RD,
        T1=round(WP * 0.455), T1W=round(WP * 0.125), T2=round(WP * 0.61), T2W=round(WP * 0.128), TY=round(HP * 0.335), TYH=round(HP * 0.15),
        IC_X=IC_X, IC_Y=IC_Y, IC_W=IC_W, IC_H=IC_H, IC_YARIM=IC_YARIM, IC_YARIM6=IC_YARIM + 6, SOL_W=SOL_W,
        DS_X=DS_X, DS_Y=DS_Y, DS_W=DS_W, DS_H=DS_H)

    vid = lambda yol, sinif, iz: (f'<video class="{sinif}" id="{iz[0]}" src="{varlik(yol)}" data-start="{t["klip"]}" data-duration="{ks}" '
                                  f'data-track-index="{iz[1]}" muted playsinline></video>')
    n_ = "\n          "
    html = f'''<!doctype html>
<html lang="tr" data-resolution="{"portrait" if b == "dikey" else "landscape"}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{cfg.get("ad", "tanitim")} — katlanır ({b})</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>{css}    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{t["son"]}" data-width="{W}" data-height="{H}">
      <div class="zemin" data-layout-ignore aria-hidden="true"><div class="zemin__ortu"><div class="zemin__alan">
        <div class="sekil sekil--1" id="sekil1"><i class="k1" id="z1k0"></i><i class="k2" id="z1k1"></i><i class="k3" id="z1k2"></i></div>
        <div class="sekil sekil--2" id="sekil2"><i class="k1" id="z2k0"></i><i class="k2" id="z2k1"></i><i class="k3" id="z2k2"></i></div>
        <div class="sekil sekil--3" id="sekil3"><i class="k1" id="z3k0"></i><i class="k2" id="z3k1"></i><i class="k3" id="z3k2"></i></div>
      </div></div></div>
      {acilis_html}
      <!-- Zamansız kap: içindeki videolar kendi data-start'ıyla zamanlı (Hyperframes zamanlı öğe içinde video istemez) -->
      <section id="tel" class="clip">
        {n_.join(baslik_html)}
        <div class="sahne-yer" id="sahne" data-layout-ignore><div class="sahne3d" id="sahneZoom">
          <div class="duo" id="duo">
            <div class="yarim yarim--sag" id="duoSag">
              <span class="tus tus--ust1"></span><span class="tus tus--ust2"></span><span class="tus tus--yan"></span>
              <div class="govde govde--sag"><div class="ic-pencere ic-pencere--sag">
                {vid(sag_yol, "ic-video", ("icSag", 11))}
                <div class="ic-kopya gizli" style="left: -{IC_YARIM}px;">{kopya}</div>
                <div class="karart ic-karart gizli"></div>
              </div></div>
            </div>
            <div class="yarim yarim--sol" id="duoSol">
              <div class="yuz govde govde--sol"><div class="ic-pencere ic-pencere--sol">
                {vid(sol_yol, "ic-video", ("icSol", 10))}
                <div class="ic-kopya gizli" style="left: 0;">{kopya}</div>
                <div class="karart ic-karart gizli"></div>
              </div></div>
              <div class="yuz yuz--arka govde">
                <span class="omurga"></span>
                <div class="dis-ekran" id="ekran">
                  {n_.join(dis_html)}
                  <div class="kamera"></div>
                  {n_.join(dokunus_html["dis"])}
                  <div class="karart gizli" id="disKarart"></div>
                </div>
              </div>
            </div>
            <div class="duo-ust" id="duoUst">
              <img class="tam gizli" id="icSon" src="{varlik(ic_son)}" alt="" />
              {vid(klip_yol, "tam gizli", ("icTam", 12))}
              {n_.join(ust_html)}
              {n_.join(dokunus_html["ic"])}
            </div>
          </div>
        </div></div>
      </section>
      {kapanis_html}
{ses_html}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      function ft(h, a, b, t) {{ b.immediateRender = false; tl.fromTo(h, a, b, t); }}
      function belir(h, t, d, y) {{ ft(h, {{ autoAlpha: 0, y: y }}, {{ autoAlpha: 1, y: 0, duration: d, ease: "power3.out" }}, t); }}
      function sol(h, t, d) {{ ft(h, {{ autoAlpha: 1 }}, {{ autoAlpha: 0, duration: d, ease: "power1.inOut" }}, t); }}
      function gecis(a, b, t, d) {{ sol(a, t, d); ft(b, {{ autoAlpha: 0 }}, {{ autoAlpha: 1, duration: d, ease: "power1.inOut" }}, t); }}
{zemin_js}{govde_js}
      {(chr(10) + "      ").join(js)}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
'''
    os.makedirs(comp, exist_ok=True)
    open(os.path.join(comp, "index.html"), "w", encoding="utf-8").write(html)
    json.dump(anlar, open(os.path.join(comp, "anlar.json"), "w"), indent=1)
    ad = re.sub(r"[^a-z0-9-]+", "-", str(cfg.get("ad", "tanitim")).lower())
    json.dump({"id": f"{ad}-katlanir-{b}", "name": f"{ad}-katlanir-{b}"}, open(os.path.join(comp, "meta.json"), "w"), indent=2)
    json.dump({"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
               "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
               "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
               "media": {"autoProxy": True}}, open(os.path.join(comp, "hyperframes.json"), "w"), indent=2)
    json.dump({"name": "composition", "private": True, "type": "module"}, open(os.path.join(comp, "package.json"), "w"), indent=2)
    return anlar


def bicimler(a, cfg):
    return [a.bicim] if getattr(a, "bicim", None) and a.bicim != "ikisi" else cfg.get("bicimler", ["dikey", "yatay"])


def uret(a):
    cfg, kok = yukle(a.config)
    for b in bicimler(a, cfg):
        comp = os.path.join(kok, f"katlanir-{b}")
        anlar = html_yaz(cfg, kok, b, comp)
        print(f"yazıldı: {comp}/index.html · süre {anlar['son']} sn")
        print("anlar:", " · ".join(f"{k} {v}" for k, v in anlar.items() if k != "bas"))
        sonuc = kos(HF + ["check", comp], cwd=kok, yakala=True)
        print("\n".join(s for s in sonuc.splitlines()[-3:] if s.strip()))


def kare(a):
    cfg, kok = yukle(a.config)
    for b in bicimler(a, cfg):
        comp = os.path.join(kok, f"katlanir-{b}")
        anlar = json.load(open(os.path.join(comp, "anlar.json")))
        at = a.at or ",".join(str(round(x, 2)) for x in (
            anlar["giris"] + 2, anlar["klip"] + 0.9, anlar["tam"] + 1, anlar["klip_son"] - 0.5,
            anlar["katlanma"] + 0.35, anlar["kapali"] + 0.6, anlar["kapanis"] + 1.5))
        at = ",".join(str(an_coz(x if re.search(r"[a-z]", x) else float(x), anlar, "bas")) for x in at.split(","))
        out = os.path.join(kok, "renders", f"kare-{b}")
        shutil.rmtree(out, ignore_errors=True)
        kos(HF + ["snapshot", comp, "--at", at, "--describe", "false", "--no-end", "--timeout", "15000", "-o", out], cwd=kok, yakala=True)
        print(f"{b}: {at} → {out}/contact-sheet.jpg")


def render(a):
    cfg, kok = yukle(a.config)
    os.makedirs(os.path.join(kok, "renders"), exist_ok=True)
    ad = cfg.get("ad", "tanitim")
    for b in bicimler(a, cfg):
        comp = os.path.join(kok, f"katlanir-{b}")
        anlar = json.load(open(os.path.join(comp, "anlar.json")))
        p = a.poster or cfg.get("poster", "tam+2")
        poster_t = an_coz(p if re.search(r"[a-z]", str(p)) else float(p), anlar, "bas")
        ham = os.path.join(kok, "renders", f"{ad}-{b}-4k-ham.mp4")
        kos(HF + ["render", comp, "--resolution", COZ[b], "--crf", "10", "--video-frame-format", "png", "--quiet", "--output", ham],
            cwd=kok, yakala=True)
        cikti = os.path.join(kok, f"{ad}-{b}")
        poster = os.path.join(kok, "renders", f"{ad}-{b}-poster.png")
        kos(["ffmpeg", "-v", "error", "-y", "-ss", str(poster_t), "-i", ham, "-frames:v", "1", poster])
        kos(["ffmpeg", "-v", "error", "-y", "-i", poster, "-q:v", "2", cikti + ".jpg"])
        ses_akisi = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", ham],
                                   capture_output=True, text=True).stdout.strip()
        ses = ["-map", "0:a", "-c:a", "copy"] if ses_akisi else []
        kos(["ffmpeg", "-v", "error", "-y", "-i", ham, "-i", poster, "-filter_complex", "[0:v][1:v]overlay=0:0:enable='eq(n\\,0)'[o]",
             "-map", "[o]"] + ses + ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
             "-profile:v", "high", "-level", "5.1", "-movflags", "+faststart", cikti + ".mp4"])
        kos(["ffmpeg", "-v", "error", "-y", "-i", cikti + ".mp4", "-vf", f"scale={KUCUK[b]}:flags=lanczos", "-c:v", "libx264",
             "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", cikti + "-1080p.mp4"])
        for y in (cikti + ".mp4", cikti + "-1080p.mp4"):
            o = olc(y)
            print(f"{os.path.basename(y)}: {o['w']}×{o['h']}, {o['sure']} sn, {o['mbps']} Mbps, {o['mib']} MiB")
        print(f"poster: {cikti}.jpg ({poster_t} sn)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    alt = p.add_subparsers(dest="komut", required=True)
    o = alt.add_parser("ornek", help="örnek video.json yaz")
    o.add_argument("--cikti"); o.add_argument("--ustune", action="store_true")
    o.set_defaults(f=ornek)
    k = alt.add_parser("kes", help="simülatör kaydından klip kes")
    k.add_argument("kayit", help="simctl recordVideo çıktısı")
    k.add_argument("--ekran", choices=["ic", "dis"], default="ic")
    k.add_argument("--parcalar", help="a-b,c-d,... saniye aralıkları, sırayla birleştirilir (verilmezse tamamı)")
    k.add_argument("--ad", help="çıktı adı (varsayılan ekran adı: ic / dis)")
    k.add_argument("--config", help="video.json (kayit/ onun dizinine yazılır; yoksa çalışma dizini)")
    k.set_defaults(f=kes)
    d = alt.add_parser("durum", help="saat + durum simgesini kes")
    d.add_argument("ekran", help="iç ekranın yatay görüntüsü (~2853×2007)")
    d.add_argument("--kesit", help="x0,y0,x1,y1 (varsayılan: ölçülmüş kesit, genişliğe oranlanır)")
    d.add_argument("--renk", help="simge rengi (varsayılan #1b1a24)")
    d.add_argument("--config")
    d.set_defaults(f=durum)
    for ad, f, yardim in (("uret", uret, "kompozisyonları yaz + denetle"), ("kare", kare, "anahtar anların kareleri"),
                          ("render", render, "4K render + poster + 1080p")):
        s = alt.add_parser(ad, help=yardim)
        s.add_argument("--config", default="video.json")
        s.add_argument("--bicim", choices=["dikey", "yatay", "ikisi"])
        if ad == "kare":
            s.add_argument("--at", help="virgüllü anlar: saniye ya da 'tam+1' gibi ad±sn")
        if ad == "render":
            s.add_argument("--poster", help="poster anı: saniye ya da 'tam+2' (ilk kareye de işlenir)")
            s.add_argument("--crf", type=int, default=14)
        s.set_defaults(f=f)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
