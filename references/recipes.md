# Recipes

Each recipe is one or a few timeline events in `video.json`. Combine them in any order; nothing here is a required
sequence. Times are seconds or references like `"fold.end+0.5"` (see `config.md`).

## Contents
- Device: start pose · fold / unfold · any angle · hold · fold several times · enter / exit · camera
- Screens: app on the outer screen · app on the inner screen · sync a clip with the hinge · switch screens ·
  overlay (pop in) · keep the screen while folding · screen power · real status bar on your own image
- Story: taps and swipes · headlines · logo card (intro / outro) · sound · poster · length

---

## Device

**Start pose** — where the device is at t=0:

```json
"device": {"pose": "closed"}
```

`closed`, `half`, `open`, or an opening angle from 0 (closed) to 180 (flat).

**Fold / unfold** — a `pose` event animates the hinge from the current angle to a new one:

```json
{"id": "unfold", "at": 6, "pose": "open", "duration": 0.6}
{"id": "fold",   "at": 14, "pose": "closed", "duration": 0.7}
```

Optional `ease` (any GSAP ease, default `power2.inOut`).

**Any angle** — `"pose": "half"` (132°) is a shallow V, `"pose": 90` a deeper one, `"pose": 60` a narrow V. From 60° up
the halves open symmetrically towards the camera; below 60° the right half turns back to face the camera and the left
closes over it, so a closed device shows its outer screen. The framing zooms with the pose (a narrow V is shown larger).

**Hold** — nothing to write: the device keeps its pose until the next `pose` event. For example, open half-way, hold
0.5 s, then open fully:

```json
{"id": "a", "at": 6, "pose": "half", "duration": 0.6},
{"at": "a.end+0.5", "pose": "open", "duration": 0.55}
```

**Fold several times** — add more `pose` events; each starts from wherever the previous one ended.

**Enter / exit** — slide in or out from `bottom`, `top`, `left`, `right`, or `fade`:

```json
{"id": "in", "at": 0.3, "enter": "bottom", "duration": 0.95},
{"at": 18, "exit": "fade", "duration": 0.6}
```

If the first motion event is an `enter`, the device starts off-screen. Without an `enter` it's on screen from the start.

**Camera** — push in, pull back or shift the framing (multiplies the zoom, offsets in output pixels):

```json
{"at": 9, "camera": {"zoom": 1.2, "y": 80}, "duration": 0.8}
```

A `pose` event can carry a `camera` too, so the camera move rides on the fold. Return with `{"zoom": 1, "x": 0, "y": 0}`.
The framing already follows the pose: the zoom keeps the body's on-screen width, a closed device is centred on its
visible half, an open one on the hinge. Keep camera pushes modest at narrow angles — the body is already large there.

## Screens

A media event puts an image or a video on a screen:

```json
{"at": 0, "screen": "outer", "file": "rec/outer.mp4"}
```

**App on the outer screen** — record the outer screen (see `recording.md`), cut it, add it with `"screen": "outer"`.

**App on the inner screen** — the same with `"screen": "inner"`. The inner content is drawn on both halves, so it
bends with the body during any fold.

**Sync a clip with the hinge** — the simulator lights the inner screen dim when it's half-open and sharpens it about a
second later. If your clip starts from that moment, start it just after the unfold begins:

```json
{"id": "unfold", "at": 6, "pose": "half"},
{"id": "clip", "at": "unfold+0.2", "screen": "inner", "file": "rec/inner.mp4"},
{"at": "clip+1.5", "pose": "open"}
```

**Switch screens** — another `base` media event on the same screen replaces the previous one. `in`: `cut`, `fade`
(default after the first), `pop`. `until` ends it explicitly (`out`: `cut`, `fade`, `pop`). A video holds its last
frame after it ends.

**Overlay (pop in)** — `"layer": "overlay"` stacks it above the base; `box` places it in simulator points
`[x, y, w, h]` (the inner screen is ~951×669 points, the outer ~466×678):

```json
{"at": "clip+7", "until": "clip+10", "screen": "inner", "file": "chat.png", "layer": "overlay", "box": [120, 80, 700, 480]}
```

Default in/out is `pop` (scales like an app opening and closing).

**Keep the screen while folding** — that's the default: whatever is on the inner screen at the moment of a fold stays
there and bends with the halves. Don't end an overlay or switch the base right at the fold unless you want that.

**Screen power** — by default the screens behave like the real device: opening from closed turns the outer screen off
and the inner on; closing turns the inner off near the end and the outer on once closed. Override or add moments:

```json
{"at": 12, "power": "outer", "state": "off", "duration": 0.2}
```

Set `"auto_power": false` at the top level to control power only by hand.

**Real status bar on your own image** — if your image covers the whole screen, add `"status": true` to the media event
to put the simulator's real clock + status icon on top (made by `duo.py status`).

## Story

**Taps and swipes** — the simulator doesn't draw touches, so add them where you touched in the recording
(simulator points). A tap presses with a ripple; a swipe presses, slides along its path and lifts — start it a moment
before the content moves in the recording:

```json
{"at": "clip+3.4", "tap": [300, 640], "screen": "inner"},
{"at": "clip+5.1", "swipe": [[760, 330], [200, 330]], "duration": 0.3, "screen": "inner"}
```

Gestures less than 2.5 s apart are one finger: it glides from the end of one to the start of the next, taking the
time available, so it never jumps.

**Headlines** — above the device; rise in over 0.7 s, fade over 0.45 s at `until`:

```json
{"at": "in+1", "until": "unfold-0.4", "title": "Your headline."}
```

**Logo card (intro / outro)** — a full-frame card: logo, a spaced-out brand title, and lines (the first large, the
rest smaller):

```json
{"at": 0, "until": 3.4, "card": {"logo": "logo.svg", "title": "BRAND"}},
{"at": 18, "card": {"logo": "logo.svg", "lines": ["example.app", "A short tagline."]}}
```

Move the device out (`exit`) before a card, or let the card cover it.

**Sound** — on by default: one sound per kind of action (hinge, tap, screen change, device entering, logo). Add your
own with `{"at": 5, "sound": "whoosh.ogg", "volume": 0.3}`; `"sound": false` turns the automatic ones off.

**Poster** — `"poster": "flat.end+2"` (or `render --poster`); it's also burned into frame 0 as the share thumbnail.

**Length** — `"duration": "fold.end+6"`; without it the video ends 0.8 s after the last event.
