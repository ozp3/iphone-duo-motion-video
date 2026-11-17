#!/usr/bin/env python3
"""iPhone Duo motion video — real simulator screen recordings on a 3D folding body, any choreography, 4K.

The video is a timeline of events in video.json: hinge poses (any angle), enter/exit, media on the inner or outer
screen, overlays, taps, headlines, logo cards, screen power, camera moves and sounds. Nothing is fixed: you decide
when it folds, how often, how far, and what each screen shows.

  init    write a sample video.json (one example choreography) into the current directory
  cut     cut a clip from a simulator recording at the recording's own resolution (inner screen is rotated to landscape)
  status  cut the clock + status icon block from a screenshot of the inner screen, as a transparent PNG
  build   write the Hyperframes compositions (foldable-portrait/, foldable-landscape/) and check them
  frames  snapshot moments (default: around every pose change) into a contact sheet
  render  4K render -> poster burned into frame 0 -> final encode -> 1080p copy

The project directory is the directory of video.json. Needs ffmpeg/ffprobe, Node (npx), Python 3 + Pillow.
Usage: python3 duo.py <command> -h
"""
import argparse, json, math, os, re, shutil, subprocess, sys
from string import Template

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HF = ["npx", "--yes", "hyperframes@0.8.60"]
RES = {"portrait": "portrait-4k", "landscape": "landscape-4k"}
SMALL = {"portrait": "1080:1920", "landscape": "1920:1080"}
VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")

# ── Device geometry (device pixels; proportions of the iPhone Duo simulator screens) ──
WP, HP, RD = 1012, 1440, 118                  # one half of the body; open body is 2·WP
IN_X, IN_Y, IN_W, IN_H = 22, 25, 1980, 1390   # inner screen (real 2852×2006, landscape)
IN_HALF = IN_W // 2
OUT_X, OUT_Y, OUT_W, OUT_H = 34, 24, 956, 1391 # outer screen (real 1398×2034)
IN_PX, OUT_PX = (2852, 2006), (1398, 2034)
IN_PT = IN_W / (IN_PX[0] / 3)                  # simulator point -> device pixel
OUT_PT = OUT_W / (OUT_PX[0] / 3)
PERSP = 8500                                   # camera ≈ 8.4 half-widths away (measured from a reference photo)
THICK = 72                                     # each half's body depth (~5.5 mm at this scale): side walls, not a flat card
STATUS_CROP = (2620, 90, 2800, 305)            # clock + status block on the real inner screen
STATUS_OUTER = (1164, 249)                     # top-left of the same block on the real outer screen
POSES = {"closed": 0, "half": 132, "open": 180}   # opening angle between the halves; "half" = each half ±24°

FORMAT = {
    "portrait": dict(W=1080, H=1920, CX=540, CY_C=1166, SC=0.9, CY_O=1040, SO=0.505,
                     TITLE="left: 70px; right: 70px; top: 250px; font-size: 84px; line-height: 1.1; text-wrap: balance;",
                     LOGO=240, BRAND=124, LINE1=116, LINE=60,
                     BG=("left: 65px; top: 115px; width: 1080px; height: 1920px;",
                         "width: 1150px; height: 1150px; left: -470px; top: -380px;",
                         "width: 1050px; height: 1050px; right: -470px; top: 640px;",
                         "width: 1250px; height: 1250px; left: -420px; bottom: -520px;")),
    "landscape": dict(W=1920, H=1080, CX=960, CY_C=652, SC=0.55, CY_O=660, SO=0.56,
                      TITLE="left: 0; right: 0; top: 112px; font-size: 64px; line-height: 1.15;",
                      LOGO=184, BRAND=96, LINE1=104, LINE=56,
                      BG=("left: 115px; top: 65px; width: 1920px; height: 1080px;",
                          "width: 1229px; height: 1229px; left: -422px; top: -499px;",
                          "width: 1114px; height: 1114px; right: -384px; top: 173px;",
                          "width: 1344px; height: 1344px; left: -307px; bottom: -653px;")),
}

SAMPLE = {
    "name": "promo",
    "formats": ["portrait", "landscape"],
    "background": "#fbfaf7",
    "accents": ["#2e4bc6", "#d96a7a", "#e8963c"],
    "text": {"color": "#1b1a24"},
    "device": {"pose": "closed"},
    "timeline": [
        {"at": 0, "until": 3.4, "card": {"logo": "logo.svg", "title": "BRAND"}},
        {"id": "in", "at": 3.6, "enter": "bottom"},
        {"at": "in", "screen": "outer", "file": "rec/outer.mp4"},
        {"at": "in+1", "until": "unfold-0.4", "title": "Your first headline."},
        {"id": "unfold", "at": "in+6", "pose": "half", "duration": 0.6},
        {"id": "clip", "at": "unfold+0.2", "screen": "inner", "file": "rec/inner.mp4"},
        {"id": "flat", "at": "clip+1.5", "pose": "open", "duration": 0.55},
        {"at": "flat.end+0.5", "until": "fold", "title": "Open it for more."},
        {"at": "clip+3.4", "tap": [300, 640], "screen": "inner"},
        {"id": "fold", "at": "clip+10", "pose": "closed", "duration": 0.7},
        {"at": "fold.end+1", "exit": "bottom"},
        {"at": "fold.end+1.5", "card": {"logo": "logo.svg", "lines": ["example.app", "A short tagline."]}},
    ],
    "duration": "fold.end+6",
    "poster": "flat.end+2",
    "sound": True,
}


# ══════════════════════════ helpers ══════════════════════════
def run(cmd, cwd=None, capture=False):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=capture)
    if r.returncode != 0:
        if capture:
            print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(f"failed (exit {r.returncode}): {cmd[0]}")
    return r.stdout if capture else ""


def probe(path):
    o = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,width,height,bit_rate:format=duration,size", "-of", "json", path],
                                  capture_output=True, text=True).stdout or "{}")
    v = next((s for s in o.get("streams", []) if s.get("codec_type") == "video"), {})
    f = o.get("format", {})
    return dict(w=v.get("width"), h=v.get("height"), dur=round(float(f.get("duration", 0) or 0), 3),
                mbps=round(int(v.get("bit_rate", 0) or 0) / 1e6, 1), mib=round(int(f.get("size", 0) or 0) / 2**20, 1),
                audio=any(s.get("codec_type") == "audio" for s in o.get("streams", [])))


def load(path):
    path = os.path.abspath(path or "video.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} not found — run `duo.py init` and edit the sample first.")
    return json.load(open(path, encoding="utf-8")), os.path.dirname(path)


def project_dir(a):
    return os.path.dirname(os.path.abspath(a.config)) if getattr(a, "config", None) else os.getcwd()


def resolve(root, path):
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.join(root, path)


def is_video(path):
    return os.path.splitext(path)[1].lower() in VIDEO_EXT


def last_frame(video, dest):
    run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", video, "-frames:v", "1", "-update", "1", dest])
    return dest


def rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def r3(x):
    return round(float(x), 3)


# ══════════════════════════ init / cut / status ══════════════════════════
def init(a):
    path = os.path.abspath(a.output or "video.json")
    if os.path.exists(path) and not a.force:
        sys.exit(f"{path} already exists (use --force to overwrite)")
    json.dump(SAMPLE, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("wrote:", path, "— one example choreography; see references/recipes.md to make your own")


def cut(a):
    root = project_dir(a)
    src = os.path.abspath(a.recording)
    parts = [tuple(float(x) for x in p.split("-")) for p in a.parts.split(",")] if a.parts else []
    o = probe(src)
    # the inner screen's framebuffer is recorded portrait (2006×2852) -> rotate to landscape; the outer one is already portrait
    rotate = "transpose=1," if (a.screen == "inner" and o["h"] > o["w"]) else ""
    dest = os.path.join(root, "rec")
    os.makedirs(dest, exist_ok=True)
    out = os.path.join(dest, f"{a.name or a.screen}.mp4")
    enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "10", "-preset", "slow", "-an", "-movflags", "+faststart"]
    if parts:
        n = len(parts)
        f = f"[0:v]fps=30,{rotate}setsar=1,split={n}" + "".join(f"[p{i}]" for i in range(n)) + ";"
        f += ";".join(f"[p{i}]trim=start={b}:end={e},setpts=PTS-STARTPTS[q{i}]" for i, (b, e) in enumerate(parts)) + ";"
        f += "".join(f"[q{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[o]"
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", f, "-map", "[o]"] + enc + [out])
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"fps=30,{rotate}setsar=1"] + enc + [out])
    t = probe(out)
    print(f"{os.path.basename(out)}: {t['w']}×{t['h']}, {t['dur']} s -> {dest}")


def status(a):
    from PIL import Image
    root = project_dir(a)
    im = Image.open(a.screenshot).convert("RGB")
    w, h = im.size
    if h > w:
        sys.exit(f"screenshot is portrait ({w}×{h}); give a LANDSCAPE screenshot of the inner screen (~2853×2007)")
    box = tuple(int(x) for x in a.crop.split(",")) if a.crop else tuple(round(v * w / 2853) for v in STATUS_CROP)
    c = im.crop(box).convert("L")
    cw, ch = c.size
    edge = sorted([c.getpixel((x, y)) for y in range(ch) for x in (0, 1, cw - 2, cw - 1)] + [c.getpixel((x, 0)) for x in range(cw)])
    bg, darkest = edge[len(edge) // 2], min(c.getpixel((x, y)) for y in range(ch) for x in range(cw))
    color = tuple(int((a.color or "#1b1a24").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    out = Image.new("RGBA", (cw, ch))
    px = []
    for y in range(ch):
        for x in range(cw):
            al = max(0.0, min(1.0, (bg - c.getpixel((x, y))) / max(1, bg - darkest)))
            px.append(color + (0 if al < 0.03 else round(al * 255),))
    out.putdata(px)
    dest = os.path.join(root, "rec")
    os.makedirs(dest, exist_ok=True)
    out.save(os.path.join(dest, "status.png"))
    pv = Image.new("RGBA", (cw, ch), (251, 250, 247, 255))
    pv.alpha_composite(out)
    pv.resize((cw * 2, ch * 2)).save(os.path.join(dest, "status-preview.png"))
    print(f"status.png {cw}×{ch} (crop {box}) -> {dest}; preview status-preview.png")


# ══════════════════════════ timeline ══════════════════════════
KINDS = ("pose", "enter", "exit", "file", "tap", "swipe", "title", "card", "power", "camera", "sound")
DEFAULT_DUR = {"pose": 0.6, "enter": 0.95, "exit": 0.65, "camera": 0.8, "power": 0.2, "swipe": 0.35}
TIME_RE = re.compile(r"\s*([A-Za-z_][\w-]*(?:\.end)?)\s*(?:([+-])\s*([\d.]+))?\s*")


def kind(e):
    k = next((k for k in KINDS if k in e), None)
    if not k:
        sys.exit(f"event without a type ({', '.join(KINDS)}): {e}")
    return "media" if k == "file" else k


def parse_time(x, ids):
    if isinstance(x, (int, float)):
        return float(x)
    m = TIME_RE.fullmatch(str(x))
    if not m:
        sys.exit(f"can't read time {x!r} — use seconds or 'id', 'id+1.5', 'id.end-0.4'")
    if m.group(1) not in ids:
        return None
    off = float(m.group(3)) * (1 if m.group(2) == "+" else -1) if m.group(2) else 0.0
    return ids[m.group(1)] + off


def resolve_timeline(cfg, root):
    events = [dict(e) for e in cfg.get("timeline", [])]
    ids = {}
    for e in events:
        e["kind"] = kind(e)
        if e["kind"] == "media":
            e["path"] = resolve(root, e["file"])
            if not os.path.isfile(e["path"]):
                sys.exit(f"missing file: {e['path']}")
            e["len"] = probe(e["path"])["dur"] if is_video(e["path"]) else None
    for _ in range(len(events) + 2):           # references may point forward: resolve until nothing changes
        progress = False
        for e in events:
            if "t" in e:
                continue
            t = parse_time(e["at"], ids)
            u = parse_time(e["until"], ids) if e.get("until") is not None else None
            if t is None or (e.get("until") is not None and u is None):
                continue
            e["t"] = r3(t)
            if e["kind"] in DEFAULT_DUR:
                e["d"] = float(e.get("duration", DEFAULT_DUR[e["kind"]]))
                e["end"] = r3(t + e["d"])
            else:
                e["end"] = r3(u) if u is not None else (r3(t + e["len"]) if e.get("len") else None)
            if u is not None:
                e["u"] = r3(u)
            if e.get("id"):
                ids[e["id"]] = e["t"]
                ids[e["id"] + ".end"] = e["end"] if e["end"] is not None else e["t"]
            progress = True
        if not progress:
            break
    left = [e for e in events if "t" not in e]
    if left:
        sys.exit(f"unresolved times (unknown id?): {[e.get('at') for e in left]} — known ids: {sorted(ids)}")
    events.sort(key=lambda e: e["t"])
    ends = [e.get("end") or e["t"] for e in events]
    dur = parse_time(cfg["duration"], ids) if cfg.get("duration") is not None else max(ends) + 0.8
    if dur is None:
        sys.exit(f"can't resolve duration {cfg['duration']!r}")
    return events, ids, r3(dur)


SYM = 60   # from this opening angle up, the halves open symmetrically (a V facing the camera)


def angles(phi):
    """Opening angle (0 closed … 180 flat) -> rotationY of the left and right halves.
    Down to SYM the halves form a symmetric V; below it the right half turns back to face the camera and the left
    one closes over it, so a closed device shows its outer screen."""
    phi = max(0.0, min(180.0, float(phi)))
    if phi >= SYM:
        a = (180 - phi) / 2
        return r3(a), r3(-a)
    right = -(180 - SYM) / 2 * phi / SYM
    return r3(180 - phi + right), r3(right)


def extent(phi):
    """On-screen size of the body at this pose: (width in half-body widths, height growth), perspective included.
    A half turned towards the camera grows (its outer edge comes closer); a half folded over the other adds no width."""
    left, right = angles(phi)
    w, grow = 0.0, 1.0
    for a, over in ((left, left > 90), (-right, False)):
        tilt = math.radians(180 - a if a > 90 else a)
        mag = PERSP / (PERSP - WP * math.sin(tilt))
        grow = max(grow, mag)
        if not over:
            w += math.cos(tilt) * mag
    return max(1.0, w), grow


def walls(radii, segs=8):
    """Side walls of one half: strips along its rounded outline (radii: top-left, top-right, bottom-right,
    bottom-left), each standing from the screen plane (z=0) back to the rear face (z=-THICK), shaded by facing."""
    tl, tr, br, bl = radii
    w, h = WP, HP
    pts = []
    def arc(cx, cy, rad, a0, a1):
        for i in range(segs + 1):
            a = math.radians(a0 + (a1 - a0) * i / segs)
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    arc(w - tr, tr, tr, -90, 0)
    arc(w - br, h - br, br, 0, 90)
    arc(bl, h - bl, bl, 90, 180)
    arc(tl, tl, tl, 180, 270)
    pts.append(pts[0])
    lx, ly = -0.42, -0.91                       # light from above, slightly left
    out = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy)
        if ln < 0.5:
            continue
        nx, ny = dy / ln, -dx / ln              # outward normal (clockwise outline, y down)
        lit = (nx * lx + ny * ly + 1) / 2
        g = round(46 + 92 * lit)
        col = f"rgb({g}, {g}, {g + 5})"
        L = ln + 1.5                            # slight overlap: no hairline gaps between strips
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ang = math.degrees(math.atan2(dy, dx))
        out.append(f'<i class="wall" style="left: {mx - L / 2:.1f}px; top: {my - THICK / 2:.1f}px; width: {L:.1f}px; '
                   f'background: {col}; transform: translateZ({-THICK / 2}px) rotateZ({ang:.2f}deg) rotateX(90deg);"></i>')
    return "".join(out)


def pose_angle(p):
    if isinstance(p, (int, float)):
        return float(p)
    if p not in POSES:
        sys.exit(f"unknown pose {p!r} — use closed / half / open or an opening angle 0–180")
    return float(POSES[p])


# ══════════════════════════ template ══════════════════════════
CSS = Template("""
      $font_css
      :root { --bg: $bg; --ink: $ink; --font: $font; }
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: ${W}px; height: ${H}px; overflow: hidden; background: var(--bg); }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; font-family: var(--font); color: var(--ink); background: var(--bg); }
      .clip { position: absolute; inset: 0; }
      .hidden { opacity: 0; visibility: hidden; }

      /* Background: three soft colour masses that drift and shift colour slowly */
      .bg { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
      .bg__blur { position: absolute; inset: -6%; filter: blur(34px); }
      .bg__area { position: absolute; $b0 }
      .blob { position: absolute; mix-blend-mode: multiply; isolation: isolate; will-change: transform; }
      .blob > i { position: absolute; inset: 0; display: block; border-radius: inherit; }
      .blob--1 { $b1 border-radius: 58% 42% 38% 62% / 66% 44% 56% 34%; }
      .blob--2 { $b2 border-radius: 40% 60% 66% 34% / 40% 34% 66% 60%; }
      .blob--3 { $b3 border-radius: 62% 38% 34% 66% / 68% 42% 58% 32%; }
      .c1 { --c: $r1; } .c2 { --c: $r2; } .c3 { --c: $r3; }
      .blob--1 > i { background: radial-gradient(circle at 38% 34%, rgba(var(--c), 0.4), rgba(var(--c), 0.22) 62%, rgba(var(--c), 0.1) 100%); }
      .blob--2 > i { background: radial-gradient(circle at 62% 44%, rgba(var(--c), 0.36), rgba(var(--c), 0.2) 62%, rgba(var(--c), 0.09) 100%); }
      .blob--3 > i { background: radial-gradient(circle at 46% 58%, rgba(var(--c), 0.34), rgba(var(--c), 0.18) 62%, rgba(var(--c), 0.09) 100%); }
      .blob--1 > .c2, .blob--1 > .c3, .blob--2 > .c1, .blob--2 > .c3, .blob--3 > .c1, .blob--3 > .c2 { opacity: 0; }

      /* Logo cards and headlines */
      .card { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; padding-bottom: 40px; }
      .logo { display: block; width: ${LOGO}px; height: ${LOGO}px; object-fit: contain; margin-bottom: ${LOGO_GAP}px; }
      .brand { font-weight: 300; font-size: ${BRAND}px; line-height: 1.1; letter-spacing: 0.14em; padding-left: 0.14em; }
      .line1 { font-weight: 300; font-size: ${LINE1}px; line-height: 1.1; letter-spacing: 0.04em; padding-left: 0.04em; }
      .line { font-weight: 400; font-size: ${LINE}px; line-height: 1.2; letter-spacing: -0.01em; margin-top: ${LINE_GAP}px; }
      .card > div { white-space: nowrap; }
      .title { position: absolute; $TITLE text-align: center; font-weight: 400; letter-spacing: -0.015em; }

      /* ══ Folding body: each half turns around the hinge; the left half closes over the right one. Closed, the hinge
         spine is on the left and the outer screen is on the left half's back. Scale is CSS zoom (a transform scale
         draws text full size and shrinks it, which blurs it). ══ */
      .stage-pos { position: absolute; left: ${CX}px; top: ${CY_C}px; width: 0; height: 0; }
      .stage3d { position: absolute; left: 0; top: 0; width: 0; height: 0; perspective: ${PERSP}px; perspective-origin: 0 0; zoom: $SC; }
      .device { position: absolute; left: -${WP}px; top: -${HP2}px; width: ${WP2}px; height: ${HP}px; transform-style: preserve-3d; }
      .half { position: absolute; top: 0; width: ${WP}px; height: ${HP}px; transform-style: preserve-3d; }
      .half--left { left: 0; transform-origin: 100% 50%; }
      .half--right { left: ${WP}px; transform-origin: 0% 50%; }
      .body { position: absolute; inset: 0; background: #060607; box-shadow: inset 0 0 0 9px #48484c, inset 0 0 0 11px #26262a; }
      .body--right { border-radius: 16px ${RD}px ${RD}px 16px; box-shadow: inset 0 0 0 9px #48484c, inset 0 0 0 11px #26262a, 0 40px 100px rgba(27, 26, 36, 0.24), 0 10px 26px rgba(27, 26, 36, 0.14); }
      .body--left { border-radius: ${RD}px 16px 16px ${RD}px; }
      .face { position: absolute; inset: 0; backface-visibility: hidden; -webkit-backface-visibility: hidden; }
      .face--back { transform: translateZ(-${THICK}px) rotateY(180deg); border-radius: 16px ${RD}px ${RD}px 16px; }
      /* Side walls: thin strips standing along the rounded outline, from the screen plane back to the rear face —
         this is what gives the body its thickness when it folds (otherwise the halves read as razor-thin cards). */
      .wall { position: absolute; height: ${THICK}px; }
      .btn { position: absolute; border-radius: 5px; background: linear-gradient(#636367, #3c3c40); }
      .btn--top1 { top: -8px; height: 12px; left: ${B1}px; width: ${B1W}px; }
      .btn--top2 { top: -8px; height: 12px; left: ${B2}px; width: ${B2W}px; }
      .btn--side { right: -8px; width: 12px; top: ${BS}px; height: ${BSH}px; }
      /* Hinge spine: a flat dark strip BEHIND the body, inset at top and bottom (not a shiny capsule) */
      .spine { position: absolute; left: -29px; top: 19px; bottom: 19px; width: 29px; border-radius: 12px 0 0 12px; background: #444446; }
      /* The inner screen's content is one stack, drawn three times: in each half's window (so it bends with the body)
         and on a flat top layer shown only while fully open (no seam at the hinge). */
      .inner-win { position: absolute; top: ${IN_Y}px; height: ${IN_H}px; overflow: hidden; background: #000; }
      .inner-win--left { left: ${IN_X}px; width: ${IN_HALF6}px; border-radius: 96px 0 0 96px; }
      .inner-win--right { left: 0; width: ${IN_HALF}px; border-radius: 0 96px 96px 0; }
      .top-layer { position: absolute; left: ${IN_X}px; top: ${IN_Y}px; width: ${IN_W}px; height: ${IN_H}px; border-radius: 96px; overflow: hidden; transform: translateZ(6px); background: #000; }
      .stack { position: absolute; top: 0; width: ${IN_W}px; height: ${IN_H}px; }
      .item { position: absolute; inset: 0; }
      .media { position: absolute; left: 0; top: 0; width: 100%; height: 100%; display: block; object-fit: cover; }
      .outer-screen { position: absolute; left: ${OUT_X}px; top: ${OUT_Y}px; width: ${OUT_W}px; height: ${OUT_H}px; border-radius: 40px 96px 96px 40px; overflow: hidden; background: #000; }
      .status { position: absolute; display: block; }
      .dim { position: absolute; inset: 0; background: #000; }
      .camera { position: absolute; left: 819px; top: 59px; width: 77px; height: 77px; border-radius: 50%; background: #050507; box-shadow: inset 0 0 0 3px #15151a; }
      .touch { position: absolute; left: 0; top: 0; width: 84px; height: 84px; border-radius: 50%; background: rgba(27, 26, 36, 0.22); border: 3px solid rgba(255, 255, 255, 0.85); box-shadow: 0 8px 22px rgba(27, 26, 36, 0.22); }
      .ripple { position: absolute; width: 120px; height: 120px; border-radius: 50%; background: rgba(43, 63, 158, 0.3); }
      .touch--inner { width: 112px; height: 112px; border-width: 4px; }
      .ripple--inner { width: 160px; height: 160px; }
""")


def write_html(cfg, root, fmt, comp):
    P = FORMAT[fmt]
    W, H = P["W"], P["H"]
    events, ids, total = resolve_timeline(cfg, root)
    assets = os.path.join(comp, "assets")
    os.makedirs(assets, exist_ok=True)
    copied = {}

    def asset(path, name=None):
        path = os.path.abspath(path)
        key = (path, name)
        if key not in copied:
            if not os.path.isfile(path):
                sys.exit(f"missing file: {path}")
            fname = name or f"{len(copied):02d}-{os.path.basename(path)}"
            shutil.copy2(path, os.path.join(assets, fname))
            copied[key] = "assets/" + fname
        return copied[key]

    status_path = resolve(root, cfg.get("status_image", "rec/status.png"))
    def status_img(screen):
        if not os.path.isfile(status_path):
            sys.exit(f"'status: true' needs {status_path} — run `duo.py status <screenshot.png>` first")
        s, (x, y) = (IN_W / IN_PX[0], STATUS_CROP[:2]) if screen == "inner" else (OUT_W / OUT_PX[0], STATUS_OUTER)
        return (f'<img class="status" src="{asset(status_path, "status.png")}" alt="" data-layout-ignore style="left: {x * s:.1f}px; '
                f'top: {y * s:.1f}px; width: {180 * s:.1f}px; height: {215 * s:.1f}px;" />')

    js, sfx = [], []
    J = js.append
    auto_sound = cfg.get("sound", True)
    def play(t, *files, force=False):
        if auto_sound or force:
            for i, (f, vol) in enumerate(files):
                sfx.append((r3(t + 0.04 * i), f, vol))
    S_LOGO = (("logo-1.ogg", 0.45), ("logo-2.ogg", 0.28))
    S_FOLD, S_TAP = (("fold.ogg", 0.24),), (("tap-1.ogg", 0.55), ("tap-2.ogg", 0.23))
    S_SWAP, S_ENTER = (("transition.ogg", 0.22),), (("enter.ogg", 0.16),)

    track = [100]
    def video_tag(path, start, dur, inst):
        # Each instance gets its own id and its own file copy: the renderer finds media by id, and identical
        # src/start/duration triples could be collapsed into one element (the other copies would freeze).
        track[0] += 1
        src = asset(path, f"{inst}-{track[0]}-{os.path.basename(path)}")
        return (f'<video class="media" id="v{track[0]}" src="{src}" data-start="{start}" data-duration="{dur}" '
                f'data-track-index="{track[0]}" muted playsinline></video>')

    # ── media on the screens: an item per event; "base" items replace each other, overlays stack on top ──
    stack_items = {"inner": [], "outer": []}      # (z, html-builder) — inner items are built once per instance
    medias = [e for e in events if e["kind"] == "media"]
    for scr in ("inner", "outer"):
        bases = [e for e in medias if e.get("screen", "inner") == scr and e.get("layer", "base") == "base"]
        for i, e in enumerate(bases):
            nxt = bases[i + 1] if i + 1 < len(bases) else None
            e["in_"] = e.get("in", "cut" if i == 0 else "fade")
            if e.get("u") is None and nxt:   # replaced by the next base: hide once the next one has come in
                e["out_at"], e["out_"] = r3(nxt["t"] + (0.42 if nxt.get("in") == "pop" else 0.3 if nxt.get("in", "fade") == "fade" else 0)), "cut"
            elif e.get("u") is not None:
                e["out_at"], e["out_"] = e["u"], e.get("out", "fade")
        for e in medias:
            if e.get("screen", "inner") == scr and e.get("layer", "base") == "overlay":
                e["in_"] = e.get("in", "pop")
                if e.get("u") is not None:
                    e["out_at"], e["out_"] = e["u"], e.get("out", "pop")
    for n, e in enumerate(medias):
        scr = e.get("screen", "inner")
        if scr not in ("inner", "outer"):
            sys.exit(f"screen must be inner or outer: {e}")
        cls = f"m{n}"
        end = e.get("out_at") or total
        pt = IN_PT if scr == "inner" else OUT_PT
        style = ""
        if e.get("box"):
            x, y, w, h = [v * pt for v in e["box"]]
            style = f' style="left: {x:.1f}px; top: {y:.1f}px; width: {w:.1f}px; height: {h:.1f}px;"'
        def build(inst, e=e, cls=cls, end=end, style=style, scr=scr):
            parts = []
            if is_video(e["path"]):
                lf = last_frame(e["path"], os.path.join(assets, f"{cls}-last.png")) if not os.path.exists(os.path.join(assets, f"{cls}-last.png")) else os.path.join(assets, f"{cls}-last.png")
                parts.append(f'<img class="media" src="{asset(lf)}" alt=""{style} />')   # holds after the video ends
                vstyle = style.replace('style="', 'style="z-index: 1; ') if style else ' style="z-index: 1;"'
                parts.append(video_tag(e["path"], e["t"], r3(min(e["len"], end - e["t"]) if end else e["len"]), inst).replace("<video", f"<video{vstyle}", 1))
            else:
                parts.append(f'<img class="media" src="{asset(e["path"])}" alt=""{style} />')
            if e.get("status"):
                parts.append(status_img(scr))
            return f'<div class="item {cls} hidden">{"".join(parts)}</div>'
        stack_items[scr].append((1 if e.get("layer", "base") == "overlay" else 0, n, build))
        sel = f".{cls}"
        J(f'tl.set("{sel}", {{ autoAlpha: 0, scale: 1 }}, 0);')   # resting state before any seek
        if e["in_"] == "cut":
            J(f'tl.set("{sel}", {{ autoAlpha: 1 }}, {e["t"]});')
        elif e["in_"] == "fade":
            J(f'ft("{sel}", {{ autoAlpha: 0 }}, {{ autoAlpha: 1, duration: 0.3, ease: "power1.inOut" }}, {e["t"]});')
            if e.get("layer") == "overlay" or n:
                play(e["t"], *S_SWAP)
        else:
            J(f'ft("{sel}", {{ autoAlpha: 0, scale: 0.88 }}, {{ autoAlpha: 1, scale: 1, duration: 0.42, ease: "power3.out" }}, {e["t"]});')
            play(e["t"], *S_SWAP)
        if e.get("out_at") is not None:
            o, t = e["out_"], e["out_at"]
            if o == "cut":
                J(f'tl.set("{sel}", {{ autoAlpha: 0 }}, {t});')
            elif o == "fade":
                J(f'ft("{sel}", {{ autoAlpha: 1 }}, {{ autoAlpha: 0, duration: 0.3, ease: "power1.inOut" }}, {t});')
            else:
                J(f'ft("{sel}", {{ autoAlpha: 1, scale: 1 }}, {{ autoAlpha: 0, scale: 0.88, duration: 0.38, ease: "power2.in" }}, {t});')
                play(t, *S_SWAP)

    # ── touches: taps and swipes (the simulator doesn't draw touches; point = simulator point) ──
    # One finger per burst of gestures: it fades in, glides to each touch, presses (tap: press + ripple; swipe: presses,
    # slides along the path, lifts) and fades out. Glides between gestures take the time available, so it never jumps.
    touch = {"inner": [], "outer": []}
    S_SWIPE = (("tap-2.ogg", 0.2),)
    for scr in ("inner", "outer"):
        pt, r, rr = (IN_PT, 56, 80) if scr == "inner" else (OUT_PT, 42, 60)
        gest = []
        for e in events:
            if e.get("screen", "inner") != scr or e["kind"] not in ("tap", "swipe"):
                continue
            if e["kind"] == "tap":
                p = (round(e["tap"][0] * pt), round(e["tap"][1] * pt))
                gest.append({"t": e["t"], "end": e["t"], "a": p, "b": p, "swipe": False})
            else:
                (x1, y1), (x2, y2) = e["swipe"]
                gest.append({"t": e["t"], "end": e["end"], "a": (round(x1 * pt), round(y1 * pt)),
                             "b": (round(x2 * pt), round(y2 * pt)), "swipe": True, "ease": e.get("ease", "power1.inOut")})
        if not gest:
            continue
        gest.sort(key=lambda g: g["t"])
        groups, cur = [], [gest[0]]
        for g in gest[1:]:
            if g["t"] - cur[-1]["end"] <= 2.5:
                cur.append(g)
            else:
                groups.append(cur); cur = [g]
        groups.append(cur)
        mod, rmod = (" touch--inner", " ripple--inner") if scr == "inner" else ("", "")
        for gi, grp in enumerate(groups):
            tc = f"t{scr[0]}{gi}"
            touch[scr].append(f'<div class="touch{mod} {tc} hidden"></div>')
            ax, ay = grp[0]["a"]
            sx, sy = ax + 170, ay + 150
            t0 = r3(grp[0]["t"] - 0.5)
            J(f'tl.set(".{tc}", {{ x: {sx - r}, y: {sy - r}, scale: 1, autoAlpha: 0 }}, 0);')
            J(f'ft(".{tc}", {{ autoAlpha: 0 }}, {{ autoAlpha: 1, duration: 0.22, ease: "power1.out" }}, {t0});')
            J(f'ft(".{tc}", {{ x: {sx - r}, y: {sy - r} }}, {{ x: {ax - r}, y: {ay - r}, duration: 0.42, ease: "power3.out" }}, {t0});')
            for ni, g in enumerate(grp):
                if ni:
                    q = grp[ni - 1]
                    d = max(0.12, min(0.8, g["t"] - q["end"] - 0.15))
                    start = max(q["end"] + 0.05, g["t"] - d - 0.05)
                    d = r3(max(0.05, min(d, g["t"] - start)))
                    J(f'ft(".{tc}", {{ x: {q["b"][0] - r}, y: {q["b"][1] - r} }}, {{ x: {g["a"][0] - r}, y: {g["a"][1] - r}, duration: {d}, ease: "power2.inOut" }}, {r3(start)});')
                if g["swipe"]:
                    J(f'ft(".{tc}", {{ scale: 1 }}, {{ scale: 0.84, duration: 0.08, ease: "power1.out" }}, {g["t"]});')
                    J(f'ft(".{tc}", {{ x: {g["a"][0] - r}, y: {g["a"][1] - r} }}, {{ x: {g["b"][0] - r}, y: {g["b"][1] - r}, duration: {r3(g["end"] - g["t"])}, ease: "{g["ease"]}" }}, {g["t"]});')
                    J(f'ft(".{tc}", {{ scale: 0.84 }}, {{ scale: 1, duration: 0.12, ease: "power1.out" }}, {g["end"]});')
                    play(g["t"], *S_SWIPE)
                else:
                    rc = f"{tc}r{ni}"
                    touch[scr].append(f'<div class="ripple{rmod} {rc} hidden" style="left: {g["a"][0] - rr}px; top: {g["a"][1] - rr}px;"></div>')
                    J(f'ft(".{tc}", {{ scale: 1 }}, {{ scale: 0.82, duration: 0.08, yoyo: true, repeat: 1, ease: "power1.inOut" }}, {g["t"]});')
                    J(f'ft(".{rc}", {{ autoAlpha: 0.55, scale: 0.2 }}, {{ autoAlpha: 0, scale: 1.8, duration: 0.5, ease: "power2.out" }}, {g["t"]});')
                    play(g["t"], *S_TAP)
            J(f'ft(".{tc}", {{ autoAlpha: 1 }}, {{ autoAlpha: 0, duration: 0.3, ease: "power1.inOut" }}, {r3(grp[-1]["end"] + 0.2)});')

    def stack(left, inst):
        items = sorted(stack_items["inner"], key=lambda it: (it[0], it[1]))
        body = "".join(b(inst) for _, _, b in items) + "".join(touch["inner"])
        return f'<div class="stack" style="left: {left}px;">{body}<div class="dim inner-dim hidden"></div></div>'

    # ── device motion: one state (pose angle, camera, off-screen offset) -> stage position, zoom, half rotations ──
    dev = cfg.get("device", {})
    phi = pose_angle(dev.get("pose", "closed"))
    XC = WP / 2 * P["SC"]
    def frame(ph, cam, off):
        # Framing follows the pose: the zoom keeps the body's on-screen width (open = 2 half-widths at SO) and its
        # height (closed zoom, shrunk by how much the nearer edges grow); closed it's centred on the visible half,
        # from the symmetric V up on the hinge.
        w, grow = extent(ph)
        zoom = min(P["SC"] / grow, P["SO"] * 2 / w) * cam["zoom"]
        x = -XC * max(0.0, 1 - ph / SYM) + cam["x"] + off[0]
        y = (P["CY_O"] - P["CY_C"]) * min(1.0, ph / POSES["half"]) + cam["y"] + off[1]
        return r3(x), r3(y), r3(zoom)
    OFF = {"bottom": (0, H + 300), "top": (0, -(H + 300)), "left": (-(W + 1400), 0), "right": (W + 1400, 0), "fade": (0, 0), None: (0, 0)}
    motion = [e for e in events if e["kind"] in ("pose", "enter", "exit", "camera")]
    first_enter = next((e for e in motion if e["kind"] == "enter"), None)
    starts_off = first_enter is not None and not any(e["kind"] == "exit" and e["t"] < first_enter["t"] for e in motion)
    off = OFF[first_enter["enter"]] if starts_off else (0, 0)
    cam = {"zoom": 1.0, "x": 0.0, "y": 0.0}
    x0, y0, z0 = frame(phi, cam, off)
    L, R = angles(phi)
    J(f'tl.set("#halfLeft", {{ rotationY: {L}, z: 3 }}, 0); tl.set("#halfRight", {{ rotationY: {R}, z: -3 }}, 0);')
    J(f'tl.set("#stage", {{ x: {x0}, y: {y0}, autoAlpha: {0 if (starts_off and first_enter["enter"] == "fade") else 1} }}, 0); tl.set("#stageZoom", {{ zoom: {z0} }}, 0);')
    flat_visible = phi >= 180
    J(f'tl.set(".top-layer", {{ autoAlpha: {1 if flat_visible else 0} }}, 0);')
    power = {"inner": phi > 0, "outer": phi == 0}
    J(f'tl.set(".inner-dim", {{ autoAlpha: {0 if power["inner"] else 1} }}, 0); tl.set("#outerDim", {{ autoAlpha: {0 if power["outer"] else 1} }}, 0);')
    auto_power = cfg.get("auto_power", True)
    power_ev = []                                  # (t, screen, state, duration)
    for e in motion:
        k, t, d = e["kind"], e["t"], e["d"]
        ease = e.get("ease", "power3.out" if k == "enter" else "power2.in" if k == "exit" else "power2.inOut")
        new_phi, new_cam, new_off = phi, dict(cam), off
        if k == "pose":
            new_phi = pose_angle(e["pose"])
            if isinstance(e.get("camera"), dict):
                new_cam.update(e["camera"])
        elif k == "camera":
            new_cam.update(e["camera"])
        elif k == "enter":
            off = OFF[e["enter"]] if e["enter"] != "fade" else (0, 0)
            new_off = (0, 0)
            if e["enter"] == "fade":
                J(f'ft("#stage", {{ autoAlpha: 0 }}, {{ autoAlpha: 1, duration: {d}, ease: "power1.inOut" }}, {t});')
            else:   # visible again (an earlier exit may have faded it out)
                J(f'tl.set("#stage", {{ autoAlpha: 1 }}, {t});')
            play(t + 0.05, *S_ENTER)
        elif k == "exit":
            new_off = OFF[e["exit"]] if e["exit"] != "fade" else off
            if e["exit"] == "fade":
                J(f'ft("#stage", {{ autoAlpha: 1 }}, {{ autoAlpha: 0, duration: {d}, ease: "power1.inOut" }}, {t});')
        a, b = frame(phi, cam, off), frame(new_phi, new_cam, new_off)
        if a[:2] != b[:2]:
            J(f'ft("#stage", {{ x: {a[0]}, y: {a[1]} }}, {{ x: {b[0]}, y: {b[1]}, duration: {d}, ease: "{ease}" }}, {t});')
        if a[2] != b[2]:
            J(f'ft("#stageZoom", {{ zoom: {a[2]} }}, {{ zoom: {b[2]}, duration: {d}, ease: "{ease}" }}, {t});')
        if new_phi != phi:
            (L0, R0), (L1, R1) = angles(phi), angles(new_phi)
            J(f'ft("#halfLeft", {{ rotationY: {L0} }}, {{ rotationY: {L1}, duration: {d}, ease: "{ease}" }}, {t});')
            J(f'ft("#halfRight", {{ rotationY: {R0} }}, {{ rotationY: {R1}, duration: {d}, ease: "{ease}" }}, {t});')
            if phi >= 180:
                J(f'tl.set(".top-layer", {{ autoAlpha: 0 }}, {t});')
            if new_phi >= 180:
                J(f'tl.set(".top-layer", {{ autoAlpha: 1 }}, {r3(t + d)});')
            play(t, *S_FOLD)
            if auto_power and phi == 0 and new_phi > 0:       # opening: outer screen off, inner on
                power_ev += [(t, "outer", "off", 0.15), (r3(t + 0.2), "inner", "on", 0.15)]
            if auto_power and phi > 0 and new_phi == 0:       # closing: inner off near the end, outer on once closed
                power_ev += [(r3(t + d * 0.55), "inner", "off", 0.2), (r3(t + d), "outer", "on", 0.25)]
        phi, cam, off = new_phi, new_cam, new_off
    for e in events:
        if e["kind"] == "power":
            power_ev.append((e["t"], e["power"], e.get("state", "on"), e["d"]))
    for t, scr, state, d in sorted(power_ev):
        sel = ".inner-dim" if scr == "inner" else "#outerDim"
        a, b = (1, 0) if state == "on" else (0, 1)
        J(f'ft("{sel}", {{ autoAlpha: {a} }}, {{ autoAlpha: {b}, duration: {d}, ease: "none" }}, {t});')

    # ── headlines and logo cards ──
    title_html, card_html = [], []
    for i, e in enumerate(x for x in events if x["kind"] == "title"):
        title_html.append(f'<h2 class="title hidden" id="title{i}" data-layout-allow-overlap>{e["title"]}</h2>')
        J(f'tl.set("#title{i}", {{ autoAlpha: 0, y: 0 }}, 0);')
        J(f'rise("#title{i}", {e["t"]}, 0.7, 20);')
        if e.get("u") is not None:
            J(f'fade("#title{i}", {e["u"]}, 0.45);')
    for i, e in enumerate(x for x in events if x["kind"] == "card"):
        c, t = e["card"], e["t"]
        parts = []
        if c.get("logo"):
            parts.append(f'<img class="logo" id="card{i}Logo" src="{asset(resolve(root, c["logo"]))}" alt="" />')
            J(f'ft("#card{i}Logo", {{ scale: 0.9 }}, {{ scale: 1, duration: 0.8, ease: "power3.out" }}, {r3(t + 0.12)});')
            play(t + 0.42, *S_LOGO)
        rows = ([("brand", c["title"])] if c.get("title") else []) + [("line1" if j == 0 else "line", s) for j, s in enumerate(c.get("lines", []))]
        for j, (k_, s) in enumerate(rows):
            parts.append(f'<div class="{k_} hidden" id="card{i}Row{j}">{s}</div>')
            J(f'rise("#card{i}Row{j}", {r3(t + 0.4 + 0.6 * j)}, 0.6, 14);')
        card_html.append(f'<div class="card hidden" id="card{i}">{"".join(parts)}</div>')
        J(f'tl.set("#card{i}", {{ autoAlpha: 0 }}, 0);')
        J(f'ft("#card{i}", {{ autoAlpha: 0 }}, {{ autoAlpha: 1, duration: 0.6, ease: "power1.inOut" }}, {t});')
        if e.get("u") is not None:
            J(f'fade("#card{i}", {r3(e["u"])}, 0.45);')
    for e in events:
        if e["kind"] == "sound":
            play(e["t"], (os.path.basename(asset(resolve(root, e["sound"]))), float(e.get("volume", 0.3))), force=True)

    # ── background drift ──
    n = math.ceil(total / 5) + 1
    bg_js = Template("""
      ft("#blob1", { x: 0, y: 0, scaleX: 1, scaleY: 1, rotation: 0 }, { x: 260, y: 320, scaleX: 1.28, scaleY: 0.82, rotation: 8, duration: $end, ease: "sine.inOut" }, 0);
      ft("#blob2", { x: 0, y: 0, scaleX: 1.04, scaleY: 1, rotation: 0 }, { x: -250, y: -380, scaleX: 0.78, scaleY: 1.32, rotation: -10, duration: $end, ease: "sine.inOut" }, 0);
      ft("#blob3", { x: 0, y: 0, scaleX: 1, scaleY: 1, rotation: 0 }, { x: 280, y: -340, scaleX: 1.22, scaleY: 0.86, rotation: 11, duration: $end, ease: "sine.inOut" }, 0);
      for (let i = 0; i < 3; i++) for (let s = 0; s < $n; s++) {
        const a = (i + s) % 3, b = (i + s + 1) % 3, t = s * 5 + 1.4;
        ft("#b" + (i + 1) + "c" + a, { opacity: 1 }, { opacity: 0, duration: 2.5, ease: "power1.inOut" }, t);
        ft("#b" + (i + 1) + "c" + b, { opacity: 0 }, { opacity: 1, duration: 2.5, ease: "power1.inOut" }, t);
      }
""").substitute(end=total, n=n)

    # ── sound files: bundled palette + any custom ones (custom ones were copied by asset()) ──
    sfx.sort()
    sfx_html = "\n".join(
        f'      <audio id="sfx{i:02d}" src="{("assets/sfx/" + f) if os.path.exists(os.path.join(SKILL, "assets", "sfx", f)) else ("assets/" + f)}" '
        f'data-start="{t}" data-track-index="{400 + i}" data-volume="{vol}"></audio>' for i, (t, f, vol) in enumerate(sfx))
    shutil.copytree(os.path.join(SKILL, "assets", "sfx"), os.path.join(assets, "sfx"), dirs_exist_ok=True)

    text = cfg.get("text", {})
    acc = cfg.get("accents", ["#2e4bc6", "#d96a7a", "#e8963c"])
    css = CSS.substitute(
        font_css=open(resolve(root, text["css"]), encoding="utf-8").read() if text.get("css") else "",
        bg=cfg.get("background", "#fbfaf7"), ink=text.get("color", "#1b1a24"),
        font=text.get("font", "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif"),
        W=W, H=H, b0=P["BG"][0], b1=P["BG"][1], b2=P["BG"][2], b3=P["BG"][3], r1=rgb(acc[0]), r2=rgb(acc[1]), r3=rgb(acc[2]),
        LOGO=P["LOGO"], LOGO_GAP=round(P["LOGO"] * 0.18), BRAND=P["BRAND"], LINE1=P["LINE1"], LINE=P["LINE"],
        LINE_GAP=round(P["LINE"] * 0.66), TITLE=P["TITLE"], CX=P["CX"], CY_C=P["CY_C"], PERSP=PERSP, SC=P["SC"],
        WP=WP, HP=HP, HP2=HP // 2, WP2=2 * WP, RD=RD,
        B1=round(WP * 0.455), B1W=round(WP * 0.125), B2=round(WP * 0.61), B2W=round(WP * 0.128), BS=round(HP * 0.335), BSH=round(HP * 0.15),
        IN_Y=IN_Y, IN_X=IN_X, THICK=THICK, IN_W=IN_W, IN_H=IN_H, IN_HALF=IN_HALF, IN_HALF6=IN_HALF + 6,
        OUT_X=OUT_X, OUT_Y=OUT_Y, OUT_W=OUT_W, OUT_H=OUT_H)

    outer_items = "".join(b("outer") for _, _, b in sorted(stack_items["outer"], key=lambda it: (it[0], it[1])))
    nl = "\n          "
    html = f'''<!doctype html>
<html lang="en" data-resolution="{fmt}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{cfg.get("name", "promo")} — foldable ({fmt})</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>{css}    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">
      <div class="bg" data-layout-ignore aria-hidden="true"><div class="bg__blur"><div class="bg__area">
        <div class="blob blob--1" id="blob1"><i class="c1" id="b1c0"></i><i class="c2" id="b1c1"></i><i class="c3" id="b1c2"></i></div>
        <div class="blob blob--2" id="blob2"><i class="c1" id="b2c0"></i><i class="c2" id="b2c1"></i><i class="c3" id="b2c2"></i></div>
        <div class="blob blob--3" id="blob3"><i class="c1" id="b3c0"></i><i class="c2" id="b3c1"></i><i class="c3" id="b3c2"></i></div>
      </div></div></div>
      <!-- Untimed container: the videos inside carry their own data-start (Hyperframes won't nest video in a timed element) -->
      <section id="phone" class="clip">
        {nl.join(title_html)}
        <div class="stage-pos" id="stage" data-layout-ignore><div class="stage3d" id="stageZoom">
          <div class="device" id="device">
            <div class="half half--right" id="halfRight">
              {walls((16, RD, RD, 16))}
              <span class="btn btn--top1"></span><span class="btn btn--top2"></span><span class="btn btn--side"></span>
              <div class="body body--right"><div class="inner-win inner-win--right">{stack(-IN_HALF, "right")}</div></div>
            </div>
            <div class="half half--left" id="halfLeft">
              {walls((RD, 16, 16, RD))}
              <div class="face body body--left"><div class="inner-win inner-win--left">{stack(0, "left")}</div></div>
              <div class="face face--back body">
                <span class="spine"></span>
                <div class="outer-screen" id="outer">
                  {outer_items}
                  <div class="camera"></div>
                  {nl.join(touch["outer"])}
                  <div class="dim hidden" id="outerDim"></div>
                </div>
              </div>
            </div>
            <div class="top-layer">{stack(0, "flat")}</div>
          </div>
        </div></div>
      </section>
      {nl.join(card_html)}
{sfx_html}
    </div>
    <script>
      // Card rows never overflow: a long line (a repo name, a URL) shrinks until it fits 88% of the frame width
      document.querySelectorAll(".card > div").forEach((el) => {{
        let fs = parseFloat(getComputedStyle(el).fontSize);
        while (el.offsetWidth > {W} * 0.88 && fs > 18) {{ fs -= 2; el.style.fontSize = fs + "px"; }}
      }});
      const tl = gsap.timeline({{ paused: true }});
      function ft(h, a, b, t) {{ b.immediateRender = false; tl.fromTo(h, a, b, t); }}
      function rise(h, t, d, y) {{ ft(h, {{ autoAlpha: 0, y: y }}, {{ autoAlpha: 1, y: 0, duration: d, ease: "power3.out" }}, t); }}
      function fade(h, t, d) {{ ft(h, {{ autoAlpha: 1 }}, {{ autoAlpha: 0, duration: d, ease: "power1.inOut" }}, t); }}
{bg_js}
      {(chr(10) + "      ").join(js)}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
'''
    os.makedirs(comp, exist_ok=True)
    open(os.path.join(comp, "index.html"), "w", encoding="utf-8").write(html)
    poses = [e for e in events if e["kind"] == "pose"]
    moments = sorted({r3(x) for e in poses for x in (e["t"] + e["d"] / 2, e["end"] + 0.4)} | {r3(min(total - 0.1, 1.2))})
    meta = dict(duration=total, ids=ids, moments=moments[:12])
    json.dump(meta, open(os.path.join(comp, "marks.json"), "w"), indent=1)
    slug = re.sub(r"[^a-z0-9-]+", "-", str(cfg.get("name", "promo")).lower())
    json.dump({"id": f"{slug}-foldable-{fmt}", "name": f"{slug}-foldable-{fmt}"}, open(os.path.join(comp, "meta.json"), "w"), indent=2)
    json.dump({"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
               "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
               "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
               "media": {"autoProxy": True}}, open(os.path.join(comp, "hyperframes.json"), "w"), indent=2)
    json.dump({"name": "composition", "private": True, "type": "module"}, open(os.path.join(comp, "package.json"), "w"), indent=2)
    return meta


def formats(a, cfg):
    return [a.format] if getattr(a, "format", None) and a.format != "both" else cfg.get("formats", ["portrait", "landscape"])


def time_arg(x, meta):
    t = parse_time(x if re.search(r"[A-Za-z]", str(x)) else float(x), meta["ids"])
    if t is None:
        sys.exit(f"unknown id in {x!r} — known: {sorted(meta['ids'])}")
    return r3(t)


def build(a):
    cfg, root = load(a.config)
    for fmt in formats(a, cfg):
        comp = os.path.join(root, f"foldable-{fmt}")
        meta = write_html(cfg, root, fmt, comp)
        print(f"wrote: {comp}/index.html · {meta['duration']} s")
        print("ids:", " · ".join(f"{k} {v}" for k, v in sorted(meta["ids"].items(), key=lambda kv: kv[1])) or "(none)")
        out = run(HF + ["check", comp], cwd=root, capture=True)
        print("\n".join(s for s in out.splitlines()[-3:] if s.strip()))


def frames(a):
    cfg, root = load(a.config)
    for fmt in formats(a, cfg):
        comp = os.path.join(root, f"foldable-{fmt}")
        meta = json.load(open(os.path.join(comp, "marks.json")))
        times = ",".join(str(time_arg(x, meta)) for x in a.at.split(",")) if a.at else ",".join(str(x) for x in meta["moments"])
        out = os.path.join(root, "renders", f"frames-{fmt}")
        shutil.rmtree(out, ignore_errors=True)
        run(HF + ["snapshot", comp, "--at", times, "--describe", "false", "--no-end", "--timeout", "15000", "-o", out], cwd=root, capture=True)
        sheets = sorted(f for f in os.listdir(out) if f.startswith("contact-sheet"))
        print(f"{fmt}: {times} -> " + ", ".join(os.path.join(out, f) for f in sheets))


def render(a):
    cfg, root = load(a.config)
    os.makedirs(os.path.join(root, "renders"), exist_ok=True)
    name = cfg.get("name", "promo")
    for fmt in formats(a, cfg):
        comp = os.path.join(root, f"foldable-{fmt}")
        meta = json.load(open(os.path.join(comp, "marks.json")))
        p = a.poster or cfg.get("poster")
        poster_t = time_arg(p, meta) if p is not None else r3(meta["duration"] * 0.4)
        raw = os.path.join(root, "renders", f"{name}-{fmt}-4k-raw.mp4")
        run(HF + ["render", comp, "--resolution", RES[fmt], "--crf", "10", "--video-frame-format", "png", "--quiet", "--output", raw],
            cwd=root, capture=True)
        out = os.path.join(root, f"{name}-{fmt}")
        poster = os.path.join(root, "renders", f"{name}-{fmt}-poster.png")
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(poster_t), "-i", raw, "-frames:v", "1", poster])
        run(["ffmpeg", "-v", "error", "-y", "-i", poster, "-q:v", "2", out + ".jpg"])
        audio = ["-map", "0:a", "-c:a", "copy"] if probe(raw)["audio"] else []
        # The poster is burned into frame 0: share previews show that frame (1/30 s, unnoticeable when playing)
        run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", poster, "-filter_complex", "[0:v][1:v]overlay=0:0:enable='eq(n\\,0)'[o]",
             "-map", "[o]"] + audio + ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
             "-profile:v", "high", "-level", "5.1", "-movflags", "+faststart", out + ".mp4"])
        # The 1080p copy is downscaled from 4K (2× supersampling: sharper than rendering 1080p directly)
        run(["ffmpeg", "-v", "error", "-y", "-i", out + ".mp4", "-vf", f"scale={SMALL[fmt]}:flags=lanczos", "-c:v", "libx264",
             "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p"] + (["-c:a", "copy"] if audio else []) + ["-movflags", "+faststart", out + "-1080p.mp4"])
        for f in (out + ".mp4", out + "-1080p.mp4"):
            o = probe(f)
            print(f"{os.path.basename(f)}: {o['w']}×{o['h']}, {o['dur']} s, {o['mbps']} Mbps, {o['mib']} MiB")
        print(f"poster: {out}.jpg ({poster_t} s)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("init", help="write a sample video.json")
    s.add_argument("--output"); s.add_argument("--force", action="store_true")
    s.set_defaults(f=init)
    s = sub.add_parser("cut", help="cut a clip from a simulator recording")
    s.add_argument("recording", help="output of simctl recordVideo")
    s.add_argument("--screen", choices=["inner", "outer"], default="inner")
    s.add_argument("--parts", help="a-b,c-d,... second ranges, joined in order (default: the whole recording)")
    s.add_argument("--name", help="output name in rec/ (default: the screen name)")
    s.add_argument("--config", help="video.json (rec/ goes next to it; default: current directory)")
    s.set_defaults(f=cut)
    s = sub.add_parser("status", help="cut the clock + status icon block")
    s.add_argument("screenshot", help="landscape screenshot of the inner screen (~2853×2007)")
    s.add_argument("--crop", help="x0,y0,x1,y1 (default: the measured crop, scaled to the width)")
    s.add_argument("--color", help="icon colour (default #1b1a24)")
    s.add_argument("--config")
    s.set_defaults(f=status)
    for name, fn, hlp in (("build", build, "write the compositions + check"), ("frames", frames, "snapshot moments"),
                          ("render", render, "4K render + poster + 1080p")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("--config", default="video.json")
        s.add_argument("--format", choices=["portrait", "landscape", "both"])
        if name == "frames":
            s.add_argument("--at", help="comma-separated times: seconds or id±seconds like 'flat.end+1'")
        if name == "render":
            s.add_argument("--poster", help="poster time: seconds or 'id+2' (also burned into frame 0)")
            s.add_argument("--crf", type=int, default=14)
        s.set_defaults(f=fn)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
