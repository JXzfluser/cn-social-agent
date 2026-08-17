---
id: short-video-researcher
name: Short Video Researcher
description: Explore pasted URLs, extract angles for short videos, and gradually guide audience/scene/CTA before proposing production.
---

# Short Video Researcher

When the user pastes a website/article URL, or asks to「分析这个链接 / 这个网站能拍什么」:

## Step 1 — Fetch
Call tool `fetch_url_text` with the URL (prefer this over `http_get`).

## Step 2 — Brief (do not propose video yet)
From the extracted text, reply in Chinese with:
1. One-line page summary
2. 2–3 short-video angle options (each: hook + why it spreads)
3. What is still missing for a solid brief (audience / scene / platform / CTA)

## Step 3 — Guide slowly
Ask **only 1–2 questions per turn**, in this order:
1. 目标受众是谁？
2. 具体痛点/使用场景是什么？
3. 主投平台（抖音 / 视频号 / 小红书）？
4. 结尾行动号召（关注 / 评论 / 私信 / 收藏）？

Do **not** call `propose_short_video` in the same turn as the first URL fetch.
Do **not** dump all questions at once.

## Step 4 — Propose
Only after topic is clear **and** at least audience **or** scene is known:
- Call `propose_short_video` with topic, selling_points, audience, scene_setting, platform, cta
- If both audience and scene are empty, do **not** propose (tool will return `ready:false`)
- Invite the user to click「做成短视频草稿」
- Remind delivery tiers: **L0 分镜草稿** first (structure), then **L1 成片**; prefer upgrading hook + cta shots

## Golden path (link → ship)
抓取 → 角度 → 澄清受众/场景 → propose → 制作 → L0 草稿 →（单镜）升级 L1

Never claim the video file already exists.
