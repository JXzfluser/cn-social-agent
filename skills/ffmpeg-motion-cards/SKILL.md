---
id: ffmpeg-motion-cards
name: FFmpeg Motion Cards
description: Reference for strong Ken Burns zoom+pan, HUD overlays, and vertical 1080x1920 still-to-video encoding used by the workbench renderer.
---

# FFmpeg Motion Cards

Workbench renders each scene as: textured PNG + edge-tts MP3 → MP4, then concat.

Cards must include high-contrast plates (terminal UI, diagonal bands, scanlines). Flat gradients alone make even strong zoom look static.

## Strong Ken Burns + pan

For duration `D` seconds at 30fps, frames `N = max(1, round(D*30))`, `n = N-1`:

```
ffmpeg -loop 1 -framerate 30 -i still.png -i audio.mp3 \
  -vf "scale=2160:3840,zoompan=z='1.0+(1.48-1.0)*on/n':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*(1-0.08-0.84*on/n)':d=N:s=1080x1920:fps=30,drawbox=...,fade=..." \
  -t D -c:v libx264 -pix_fmt yuv420p out.mp4
```

Rules of thumb:
- Zoom end ≥ **1.45** (old 1.12 was invisible on phones)
- Always pan (`up` / `right` / `diag`) — center-only zoom on dark panels looks frozen
- Scale source ~2× before zoompan so the crop has headroom
- Prefer `z='z0+(z1-z0)*on/n'` over fragile `zoom+step`

## HUD overlays (always on for local)

After zoompan:

```
drawbox=… top accent bar
drawbox=x='mod(t*280\,w+160)-160' … sweeping light
drawbox=… bottom progress fill = iw*t/D
```

## Motions

| id | feel |
|----|------|
| kenburns | auto role→motion; default up push ~1.48× |
| punch_in | fast center punch ~1.72× |
| drift | lateral slide at mild zoom |
| diagonal | corner-to-corner push |
| pull_back | zoom out reveal |
| static | fades only |

Role defaults when motion=`kenburns`: hook→punch_in, pain→diagonal, value→drift, proof→kenburns, cta→pull_back.

## Progressive plates (typing)

Local render writes 6–10 keyframes per scene (`scene_N_keys/k_XX.png`) with terminal `reveal` 0→1 and cursor blink, then:

```
ffmpeg -framerate KEYS/DUR -i k_%02d.png -i audio.mp3 \
  -vf "fps=30,scale=2160:3840,zoompan=...:d=1:...,drawbox=...,fade=..." \
  -t DUR out.mp4
```

Typing + strong zoom/pan + HUD scrub = readable motion even without Agnes T2V.

