---
id: deep-analysis-video
name: Deep Analysis Video
description: Produce thesis-driven mid-length口播（约3分钟）inspired by finance deep-dive YouTube — evidence, pattern, clear verdict.
---

# Deep Analysis → 短视频

对标财经「深度分析」片的叙事密度，做成竖屏中长口播（默认 **180 秒**）：
悬念标题 → 论点 → 证据 → 规律 → **清晰结论/行动点**。

## 何时启用

用户说：深度分析、财报风格、讲规律、讲买点/结论、对标某条 YouTube 深度片、要有证据链、不要鸡汤。

## 流程

1. 素材 — `fetch_url_text` / `github_repo_insight` / 用户口述数据（不编造数字）
2. 定角度 — 工坊选 `content_angle=deep_analysis`，时长 **180**，背景优先 `desk`
3. 结构硬性  
   `hook → pain → thesis → evidence ×2 → pattern → verdict → pitfall → cta`
4. 标题公式 — `标的 + 惊人规律？ + 悬念 + 但结论已清晰`
5. `propose_short_video` — selling_points 写清论点与两条证据摘要
6. 交付 — L0 看分镜板式（论点条/数据条/趋势/结论条）是否差异化，再升 L1

## 画面提示（给 visual 字段）

| role | 板式 |
|------|------|
| thesis | 左侧色条 + 大字论点 |
| evidence | 柱状/数据条 + 关键数字 |
| pattern | 折线趋势 + 规律句 |
| verdict | 绿色结论条 + 行动点按钮 |

## 注意

- 证据必须像「可核对」，不要空形容词。
- 没有真实数据时，明确说「用公开指标占位，上线前替换」，禁止瞎编 star/涨跌幅。
