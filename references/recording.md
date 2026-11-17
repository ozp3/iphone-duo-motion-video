# Recording in the simulator

Re-record only when the app's screens changed. If only copy, timing or the body changes, don't touch the recording —
re-cutting it with `cut` is enough.

## Find the device and its screens

```bash
xcrun simctl list devices | grep -i "iphone duo"          # UDID; if missing, create an iPhone Duo simulator in Xcode
xcrun simctl io <UDID> enumerate                           # display ports
```

There are two screens: **inner** (default size ~2007×2853, a portrait framebuffer) and **outer** (~1398×2034).
`simctl io recordVideo` records ONE screen at a time; take a separate recording if you need the outer screen.

- Hinge: the iOS Simulator tool's `duo_pose` action — `closed`, `half_open` (`angle: 100`), `open`; `duo_hinge`
  reports the state. Without that tool, change the pose by hand in the Simulator app; the recording order is the
  same. The body's motion is not in the recording; the video draws it in CSS 3D.
- Install and open the app in the simulator (the iOS Simulator tool's `build` / `launch`, or the project's own
  command).
- Make the data look real: empty lists or "test" text weaken a promo. If you need a local test server, use the
  project's own development script and sign in with a test account.
- The simulator uses the Mac's system proxy: if `localhost` goes to a proxy (connection errors, 502), serve the local
  backend on the Mac's network address and give the backend's own requests `no_proxy`. Don't change system settings.

## Recording order

Device closed, app on the first screen you want to show:

```bash
nohup xcrun simctl io <UDID> recordVideo --codec=h264 --display=<INNER SCREEN UUID> --force rec-inner.mov > rec.log 2>&1 &
echo $! > rec.pid
```

Record the hinge moves you plan to show, in the order you plan to show them — the screen's reaction to each pose is
part of the recording. Some behaviours worth knowing:

- From closed to `half_open`, the OS lights the inner screen dim and sharpens it in ~0.9 s. If you want a sharp
  half-open moment, **hold 3 s** there; a short hold only gives the dim state.
- From half-open to `open` the screen doesn't change.
- Folding back to half-open dims the folded side again; closing turns the inner screen off.

A typical session:

1. Wait ~2 s → pose changes you need (e.g. `duo_pose half_open angle 100`, hold 3 s, `duo_pose open`).
2. Do the flow you want to show in the app: note each tap's point (simulator points) and its second in the recording
   — simulator taps don't appear in the picture; the video draws touch indicators from these notes (`tap` events).
3. When done: `kill -INT $(cat rec.pid)` and wait for the file to close (until `ffprobe` reports a duration).

For the outer screen do the same with the device closed and the outer screen's UUID (`--screen outer` doesn't rotate).

## Choosing the cut ranges

Measure, don't eyeball:

```bash
# Brightness curve: when the inner screen lights up and sharpens
ffmpeg -i rec-inner.mov -vf "fps=4,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-" -f null - 2>/dev/null \
  | grep -o "YAVG=[0-9.]*"
# Contact sheet: taps and screen changes
ffmpeg -i rec-inner.mov -vf "fps=4,transpose=1,scale=300:-1,tile=6x6" -frames:v 1 sheet.png
```

Join only the stretches you need with `--parts "a-b,c-d,…"` (in order) — e.g. the light-up and sharpen around a
hinge move, then the app flow. Then place the clip and the pose events in `video.json` so that the hinge motion in
the video lines up with the screen's reaction in the clip, and set each tap's time from the cut (see `recipes.md`).

## Status column screenshot

With the device open, take a screenshot of the inner screen (the iOS Simulator tool's `screenshot`, full
resolution, landscape ~2853×2007). The wallpaper/background must be light (the icon comes out dark).
`duo.py status <png>` turns the clock + ring + dots into a transparent PNG; the default crop is for the iPhone Duo,
use `--crop x0,y0,x1,y1` for another layout.
