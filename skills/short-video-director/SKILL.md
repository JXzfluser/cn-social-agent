---
id: short-video-director
name: Short Video Director
description: Direct richer mid-length口播 — duration 1–3min, render engine, background, motion, and pacing.
---

# Short Video Director

When helping users make or improve口播短视频, enrich **duration / render engine / background / motion / content**, not only the script.
目标是「看完有收获」的口播。**优先让用户从模板开拍**（产品更新 15s / 技术吐槽 15s / 教程 90s），再自由加长或升深度分析。

## Templates first

If the user has not chosen a style, propose one of:

1. `product_update` — 15s 停滑，changelog / 本周上线
2. `tech_rant` — 15s 观点，`content_angle=idea`
3. `tutorial` — ~90s 入门，`content_angle=intro`

Pass `template_id` + `target_seconds` into create/generate tools when available. Do not default every piece to 120s.

## Before generate / render

Ask or infer (1–2 at a time if missing):

1. **时长** — 30 / 45 / 60 / 90 / **120（默认）** / **180（深度分析）** 秒
2. **内容角度** — `intro` / `idea` / `compare` / **`deep_analysis`** / `general`
3. **渲染引擎** — `local`（L0 草稿）| `agnes-video`（L1 成片）
4. **背景主题** — `night` | `dawn` | `studio` | `neon` | `paper` | `forest` | **`desk`（深度分析）**
5. **动画** — `kenburns` | `static` | `punch_in` 等

Call tool `list_video_styles` if you need the exact allowed values.
找选题优先 `scan_hotspot_board`；深挖用 `github_repo_insight`，再按四条角度 propose（含 deep_analysis）。

## When generating

Pass: `target_seconds`（deep_analysis 用 180）, `content_angle`, `render_mode`, `bg_theme`（desk）, `motion`, plus audience/scene/platform/cta.
深度分析结构：hook→pain→thesis→evidence×2→pattern→verdict→pitfall→cta；每镜 visual 板式不同。

Remind the user they can set the same controls in **短视频工坊** 右侧参数。

## Render engines

- `local` — L0 分镜草稿：按 role 差异化卡片 + ffmpeg 运镜
- `agnes-video` — L1 成片：每镜 Agnes 文生视频，再与 edge-tts 口播合成

## Do not

- Do not invent Remotion/HyperFrames pipelines in this workbench.
- Do not claim Agnes finished instantly — generation is asynchronous and may take minutes per scene.
- Do not ship 30s slogan cards when the user wants valuable 1–3 min content.
