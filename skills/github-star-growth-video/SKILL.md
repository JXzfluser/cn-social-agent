---
id: github-star-growth-video
name: GitHub Star Growth Video
description: Research fast-growing GitHub repos and produce intro / core-idea / comparison mid-length口播（1–3 分钟）for developers.
---

# GitHub Star Growth → 短视频

面向程序员受众，围绕 **Star 增长很快的开源项目** 做有价值的中长口播（默认 90–120 秒，深度可达 180 秒）。

## 何时启用

用户说：GitHub 热点、热点榜、Star 暴涨、最近很火的开源、某个 github.com 链接、要做开源测评/入门。

## 流程

1. **扫热点榜** — `scan_hotspot_board`（优先；可调 days / min_stars / language）
   - 把榜单条目与开聊话术列给用户，方便点选开聊
2. **深挖一个** — `github_repo_insight(repo)` 拿 stars_per_day、README、三条角度大纲
3. **定角度**（同一仓库可连做）
   - `intro` 入门上手 · 建议 **120s**
   - `idea` 核心思想 · 建议 **90–120s**
   - `compare` 横向对比 · 建议 **120s**
   - `deep_analysis` 深度分析 · 建议 **180s**（论点→证据→规律→结论）
4. **澄清** — 一次问 1–2 个：受众（独立开发者/后端/前端）· 对比对象 · 平台
5. **propose_short_video** — topic 含仓库名；selling_points 写清角度；提醒工坊选对应 `content_angle` 与时长（勿再默认 45s）
6. **交付** — 先 L0 草稿，再 L1；hook/cta 优先成片

## 三条内容线模板（信息密度）

结构参考：hook → pain → context → steps/value（≥3 点）→ proof/compare → pitfall → cta

### 入门 (intro · ~120s)
钩子：星数/涨速 → 它是什么一句话 → 谁该装 → 三步跑通 → 验证 → 一个坑 → CTA

### 核心思想 (idea · ~90–120s)
钩子：为什么突然到处都是 → 核心观念一句 → 解决什么旧痛 → 误区 → 记住一点 → CTA

### 对比 (compare · ~120s)
钩子：别跟风装错 → 和 A/B 差在哪（2–3 点）→ 什么人选它 → 什么人别选 → 选型结论 → CTA

## 注意

- 没有 `GITHUB_TOKEN` 时仍可用公开 API，但可能触发限流；有 token 更稳。
- 不要编造 star 数；以工具返回为准。
- 不要首轮 insight 后立刻整片渲染承诺。
- 画面 / visual 必须按 role 换板式，避免每镜同一终端框。
