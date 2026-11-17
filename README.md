# iphone-duo-motion-video

A [Claude Code](https://claude.com/claude-code) skill for **motion videos of your iOS app on a foldable phone**. The
screens are the iPhone Duo simulator's **real recordings**; the 3D body really folds and the picture bends with it.
You choreograph everything, and it renders portrait and landscape in **4K**.

## What you can do

Every part is a building block you can place anywhere on the timeline and repeat:

- **Fold and unfold** to any angle (closed, a shallow V, an L, flat), as often as you like, with any easing.
- **Hold** a pose, **enter and exit** from any side or with a fade, **move the camera** (push in, pull back).
- **Show your app on either screen**: the outer screen while closed, the inner screen open, or both at different
  times. Switch screens with a cut, a fade or a pop.
- **Overlays** on top of the app (an image or a video, full screen or in a box), popping in like an app.
- **Touch indicators** for taps and swipes where you touched in the recording (the simulator doesn't draw touches);
  the finger slides along a swipe and glides smoothly between gestures.
- **Headlines**, **logo cards** for intros and outros, a soft animated background in your colours.
- **Screen power** that behaves like the real device, or under your control.
- **Sound**: one consistent sound per action, plus your own files.

## Why a real recording?

Redrawing an interface always gives itself away through small differences: an icon, a gap, a font. Here the screens
are the simulator's own recording, so the app looks exactly like the app. The operating system's own reactions are
part of it too, like the folded half dimming when half-open. Only the body's motion is generated, because a screen
recording doesn't contain it. The content is drawn on both halves, so it bends with every fold.

## Install

```bash
git clone https://github.com/ozp3/iphone-duo-motion-video ~/.claude/skills/iphone-duo-motion-video
pip3 install pillow
```

You need:

- macOS and Xcode with the iPhone Duo simulator
- `ffmpeg`
- Node.js (`npx`; [Hyperframes](https://www.npmjs.com/package/hyperframes) downloads itself for rendering)
- Python 3

## Usage

Tell Claude Code what you want to show:

> make a foldable phone video of my app: start closed on the login screen, unfold to the dashboard, fold it twice
> to show it standing up, end on our logo

The skill plans the timeline with you, records the simulator, cuts the clips, builds the video, checks it frame by
frame and renders it.

The timeline is a list of events in `video.json`:

```json
"device": {"pose": "closed"},
"timeline": [
  {"id": "in", "at": 0.3, "enter": "bottom"},
  {"at": "in", "screen": "outer", "file": "rec/outer.mp4"},
  {"id": "open", "at": 5, "pose": "open", "duration": 0.7},
  {"at": "open+0.2", "screen": "inner", "file": "rec/inner.mp4"},
  {"at": "open.end+1", "until": "open.end+4", "title": "Everything, side by side."},
  {"at": 12, "pose": 90, "camera": {"zoom": 1.15}},
  {"at": 15, "pose": "closed"},
  {"at": 16.5, "card": {"logo": "logo.svg", "lines": ["example.app"]}}
]
```

You can also run the steps by hand:

```bash
D=~/.claude/skills/iphone-duo-motion-video/scripts/duo.py
python3 $D init                                     # a starting video.json
python3 $D cut rec-inner.mov --screen inner --parts "2.1-3.1,19.5-25.25"
python3 $D build                                    # compositions + check
python3 $D frames                                   # snapshots around every fold
python3 $D render                                   # 4K + poster + 1080p copy
```

- [`references/recipes.md`](references/recipes.md) shows how to do each thing.
- [`references/config.md`](references/config.md) lists every field.
- [`references/recording.md`](references/recording.md) explains the simulator recording.

## License

[MIT](LICENSE). Sound effects are from [Kenney](https://kenney.nl) packs, released under CC0.
