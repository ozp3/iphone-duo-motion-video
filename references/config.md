# video.json reference and how the generator works

## Contents
1. Top-level fields
2. Times and ids
3. Event reference
4. How it's built (body, screens, DOM)
5. Pitfalls

## 1. Top-level fields

| Field | Meaning |
|---|---|
| `name` | output name: `<name>-portrait.mp4`, `<name>-landscape.mp4` |
| `formats` | `["portrait", "landscape"]` or one of them |
| `background`, `accents` | background colour; the three soft colour masses drifting on it (hex ×3) |
| `text` | `color`, `font` (default: system font), `css` (optional file with @font-face, inlined) |
| `device` | `{"pose": ...}` — start pose (default `closed`) |
| `timeline` | the events (section 3), in any order |
| `duration` | total length (number or reference; default: 0.8 s after the last event) |
| `poster` | poster time (default 40% of the length); `render --poster` overrides |
| `status_image` | path of the status block (default `rec/status.png`) |
| `sound` | `false` turns the automatic sounds off |
| `auto_power` | `false` turns the automatic screen power off |

## 2. Times and ids

`at` and `until` take seconds or a reference: give any event an `"id"` and refer to its start (`"fold"`) or end
(`"fold.end"`), with an offset (`"fold.end+0.5"`, `"in-0.2"`). An event's end is `at + duration` for timed events
(pose, enter, exit, camera, power), `until` when given, or the clip's own end for a video. References may point forward.
`build` prints every id with its resolved time.

## 3. Event reference

| Type (key) | Fields | Default duration |
|---|---|---|
| `pose` | `pose`: closed / half / open / 0–180 · `duration` · `ease` · `camera` | 0.6 |
| `enter` | `enter`: bottom / top / left / right / fade · `duration` · `ease` | 0.95 |
| `exit` | `exit`: bottom / top / left / right / fade · `duration` · `ease` | 0.65 |
| `camera` | `camera`: `{zoom, x, y}` (zoom multiplier, pixel offsets) · `duration` · `ease` | 0.8 |
| media (`file`) | `file` · `screen`: inner / outer · `layer`: base / overlay · `in` / `out`: cut / fade / pop · `until` · `box` · `status` | clip length |
| `tap` | `tap`: `[x, y]` simulator points · `screen` | — |
| `title` | `title`: text · `until` | — |
| `card` | `card`: `{logo, title, lines}` · `until` | — |
| `power` | `power`: inner / outer · `state`: on / off · `duration` | 0.2 |
| `sound` | `sound`: file · `volume` | — |

## 4. How it's built

Geometry (device pixels, iPhone Duo proportions): one half of the body is 1012×1440, the inner screen 1980×1390 (real
2852×2006), the outer screen 956×1391 (real 1398×2034). For another foldable, change the constants at the top of
`duo.py` (`WP, HP, IN_*, OUT_*, *_PX, STATUS_*`) and the `FORMAT` framing.

```
#stage (x/y) > #stageZoom (zoom + perspective 8500, origin at the hinge) > #device
  #halfRight  buttons · body · window onto the right half of the inner stack
  #halfLeft   front: window onto the left half of the inner stack (runs 6 px past the hinge)
              back: .spine · #outer = outer screen (outer media · outer taps · #outerDim)
  .top-layer  the inner stack again, flat, shown only while fully open (translateZ 6px — no seam at the hinge)
```

- **Pose → rotation.** Opening angle φ: φ ≥ 90 → halves at ±(180−φ)/2; φ < 90 → the right half turns back towards
  the camera (−45·φ/90) and the left closes over it. Left `z: 3` (in front), right `z: -3`. Only the right body casts
  an outer shadow (the left one's shadow would fall on the hinge as a stripe).
- **Framing follows the pose**: closed is centred on the visible half at the closed zoom; from the half pose up it's
  centred on the whole body at the open zoom; in between it interpolates. Camera events multiply / offset on top.
- **Inner stack**: all inner media, overlays, taps and the power dim, drawn three times (left window, right window,
  flat top layer). Tweens target classes, so all three move together. Each video copy has its own id and file (the
  renderer finds media by id and could collapse identical copies).
- **Scale** is CSS `zoom`, never `transform: scale` (text would be drawn full size and shrunk — blurry).

## 5. Pitfalls

- A `<video>` with `data-start` can't sit inside a timed element (Hyperframes) — the device section is untimed.
- Every tween is `fromTo` + `immediateRender: false` (the `ft()` wrapper), with a resting state set at 0 for anything
  tweened more than once: Hyperframes seeks the timeline to arbitrary points.
- Full-frame layers (the power dims) must start hidden in CSS; `hyperframes check` fails otherwise.
- GSAP 3.14 doesn't know `scaleZ`.
- `hyperframes check` tests contrast and layout; headlines need enough contrast with the background.
- Simulator point ↔ pixel: 1 point = 3 real pixels; measure on the recording after it's rotated to landscape.
