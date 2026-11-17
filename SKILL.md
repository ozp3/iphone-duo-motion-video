---
name: iphone-duo-motion-video
description: >-
  Makes motion videos of any iOS app on a foldable phone (iPhone Duo simulator): the app's REAL simulator screen
  recordings play on a 3D body that genuinely folds, and you choreograph everything on a timeline — hinge poses at any
  angle, how often it folds, enter/exit moves, camera, what each screen (inner/outer) shows, overlays, touch
  indicators, headlines, logo cards, screen power and sound. Built with Hyperframes as portrait + landscape 4K plus
  1080p copies. Use this skill whenever the user wants a "foldable phone video", "iPhone Duo video", "Duo promo /
  launch / demo video", "fold / unfold animation of my app", "show my app on a foldable", or to change, re-render or
  re-record such a video — even if they don't say "skill". Not for flat (non-folding) phone or website videos.
---

# iPhone Duo motion video

Two sources make the video: **the screens are the simulator's real recordings**, **the body is CSS 3D** (a simulator
recording holds only screen pixels, not the device's motion). The choreography is entirely the user's: a `video.json`
timeline of events, each a building block you can place anywhere and repeat. `references/recipes.md` shows how to do
each thing (fold, hold, any angle, switch screens, overlay, taps, cards, camera…).

Pipeline script — one command per step, details with `-h`:

```
python3 ~/.claude/skills/iphone-duo-motion-video/scripts/duo.py init|cut|status|build|frames|render
```

Project directory (where video.json lives):

```
<project>/
  video.json              the timeline (init writes one example — replace it with the user's story)
  rec/                    cut clips and the status image
  foldable-portrait/      generated Hyperframes composition (index.html, assets/, marks.json)
  foldable-landscape/
  <name>-portrait.mp4 …   4K outputs, -1080p copies, .jpg posters
  NOTES.md                a short note per round (what changed, why)
```

Needs: Xcode with the iPhone Duo simulator, ffmpeg/ffprobe, Node (`npx hyperframes@0.8.60`), Python 3 + Pillow.

## Rules

These are about craft, not about any particular sequence. Each came from real feedback; breaking one brings the same
objection back.

1. **Screens are real recordings.** Don't redraw the app's UI in CSS/HTML: viewers spot an imitation of an interface
   they know from tiny differences. Something the app doesn't have (say, a chat view) goes on top as a separate image
   or video overlay.
2. **The body really folds.** The halves turn around the hinge and the screen content bends with them. Sliding or
   stretching halves sideways doesn't read as folding ("it slides on rails").
3. **The body looks like the real device.** Closed, the hinge is on the left: a flat dark strip behind the body (a
   shiny capsule looks fake); buttons on the right half. If the user gives reference images, measure them (aspect
   ratio, crease) and match — don't eyeball.
4. **The status column is cut, never drawn.** The clock and Wi-Fi icon come from the real screen (`status`); a drawn
   icon came back as "broken".
5. **Quality.** Scale with CSS `zoom` (a transform scale blurs text); cut at the recording's own resolution; render 4K.
   Rendering straight at 1080p came back as "quality is too low".
6. **Behave like the device.** What's on screen when a fold starts stays and bends with the halves — switching to
   another screen mid-fold looks like a bug. Screens power like the real thing (closed: outer on, inner off; the
   folded half dims when half-open — that dimming is in the recording, keep it). Line pose events up with the
   screen's reaction in the clip.
7. **Copy and sound.** Ad language: short headlines about the benefit; no internal code names, ticket numbers or file
   names. The same action always makes the same sound (the bundled palette does this).
8. **Device and accounts.** Record in the simulator with test accounts. Never install on the user's real phone or type
   a real password.

## Workflow

Start from whatever the request changes; with several changes, start at the earliest step:

| Request | Start at |
|---|---|
| New video | 0 |
| The app's screens changed, new recording | 1 |
| Clock / status icon | 2 |
| Story, timing, poses, copy, overlays, taps, cards | 3 |
| Re-render only / different poster | 5 |

0. **Story** — agree on the choreography with the user (or propose one): what each screen shows, when and how far it
   folds, headlines, logo cards. Then `duo.py init` for a starting file and rewrite its timeline. Take the logo, brand
   name and copy from the user's product; if unknown, draft sensible ones and say so.
1. **Record** — `references/recording.md`: finding the simulator and its screens, hinge poses and what the OS does on
   each, recording, choosing cut ranges. Then `duo.py cut <rec.mov> --screen inner|outer --parts "a-b,c-d" --name …`.
2. **Status** — only if an image of yours covers a whole screen: a landscape screenshot of the inner screen →
   `duo.py status <png>`; look at `rec/status-preview.png`.
3. **Timeline** — `references/recipes.md` (how to do each thing) and `references/config.md` (every field, times and
   ids). Then `duo.py build`: writes both formats, runs `hyperframes check` (must be clean) and prints each id's time.
4. **Look frame by frame** — `duo.py frames` (default: around every pose change; `--at "fold+0.3,flat.end+1"` for
   your own moments). READ the contact sheets and zoom into anything doubtful. The real objections come from small
   details (inside of an icon, hinge thickness, one wrong frame mid-fold) — "check passed" is not enough.
5. **Render** — `duo.py render [--poster "id+2"]` (~2 min per format; run it in the background). The poster is also
   burned into frame 0 (the share thumbnail). Read the output measurements (resolution, Mbps, MiB).
6. **Send** — if you have a file-sending tool: 4K files go over 30 MiB and don't reach remote viewers; send the
   `-1080p.mp4` copies too and say so in one line.
7. **Note** — add a short summary of the round to `NOTES.md`: what changed, why, after which feedback.

If the project already has a hand-written composition from earlier rounds, keep using it (don't rewrite it); the
rules above still apply there.

## Report

Short: what was produced (files, length, resolution), what changed this round, and any decision needed from the user,
numbered. If the user has their own report format, follow it.
