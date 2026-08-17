---
id: web-video-presentation
name: Web Video Presentation
description: Harness-style 实测讲解 — 深度口播+大纲+图示舞台 → OBS ?auto=1 → 导入成片 → 发抖音。
---

# Web Video Presentation

将文章/主题做成 **可点击驱动的网页演示**（16:9 或 9:16），再用本机 OBS 录屏成片。不要走口播 L0/L1 卡片流水线。

对标形态：**产品实测讲解片**（Hook → 差异 → 概念 → 安装 → 真实验证 → 意外发现 → 进阶 → 收束+CTA），不是空洞图示课。

## Agent 内容纪律（先于一切脚手架）

讲解演示的价值在「打磨后的内容」，不是空舞台。Agent 必须：

1. **调研**：对仓库/文章先 `github_repo_insight` 或 `fetch_url_text`；若主题资产有期刊证据包，优先 `lookup_topic_assets` / 传入 `pack_id`，把事实写入 research_notes
2. **深度起草**：调用 `draft_presentation_content`（传入 research_notes / audience / angle；有证据则带 pack_id）
3. **交接**：`propose_presentation` 带上 thesis、outline、full_script（及草稿章节若已有）
4. **硬停 A1**：用户确认前不得 scaffold/build

工坊亦可从「主题资产」点「用此证据做讲解」——自动建讲解项目并深度起草（注入证据）。

### 实测讲解质量条（不达标禁止宣称「稿件完成」）

| 项 | 最低标准 |
|----|----------|
| thesis | 一句可反驳、可检验的差异主张 |
| 口播 | ≥350 汉字，分段对应章节；结尾有本周行动/CTA |
| 大纲 | 6–8 章，时间戳式节拍，覆盖实测弧线 |
| 章节 role | 必含：hook / differentiate / concept / setup / demo / wrap；建议 discovery / advanced |
| 演示步 | ≥18 slides |
| 图示 | ≥8 页含 diagram；至少 1 页 `compare` |
| demo 类章 | slides 须有 `outcome`（观众应看到的可观察结果） |
| demo 验证 | demo（及在场的 discovery/advanced）须声明 `verify.command` + `verify.expected`；「沙箱验证」须全部 pass，否则内容门禁不过 |
| 每轴/论点 | 机制 + 易错 + 检验（或追问） |

禁止：赋能/干货/一文读懂/今天简单讲一下；禁止每页只有口号无细节；禁止只有概念没有「怎么跑起来」和「第一次真实验证」。

### 叙事弧线（录制时按此节拍）

1. **hook** — 为何值得看（爆点/痛点，尽快立住好奇）
2. **differentiate** — 与旧做法差异（对比图）
3. **concept** — 核心机制命名并说清
4. **setup** — 安装/前置（清单或流水线）
5. **demo** — 第一次真实验证：操作 → 可观察结果
6. **discovery** — 意外发现/反直觉（可信度）
7. **advanced** — 进阶（并行/长期/多 Agent）
8. **wrap** — 记住一句话 + 可执行 CTA

## 四阶段（必须遵守硬检查点）

1. **Phase 1 内容** — 调研 → draft → 口播稿 + 大纲 + 图示结构
2. **Checkpoint A1（硬停）** — 用户确认：稿子 / 大纲 / 主题 / 素材 / 串行|并行。未确认不得 scaffold。
3. **Phase 2 构建** — `scaffold_presentation`；工坊应用草稿 content.json / 内容包；第一章先验视觉
4. **Checkpoint B（硬停）** — 网页是否 OK；是否合成 TTS
5. **Phase 3 音频** — 按 slide.`narration`（否则 body/title）合成 TTS；写出带 `duration_ms` / `start_ms` 的时间轴；质检覆盖率与缺音频
6. **Phase 4 录屏** — 打开 `?auto=1`，按旁白时间轴推进；给 OBS 清单；**不要声称已录完**，等用户「导入成片」
7. **发抖音** — 导入成片后跑双质检（内容门禁 + 成片门禁）；未过质检禁止发抖音。有凭证走上传；否则半自动复制文案 + 创作者中心

## 双质检

| 门 | 检查 |
|----|------|
| 内容 | depth 弧线、demo 沙箱验证通过、A1、舞台已构建、旁白时间轴（若已合成） |
| 成片 | 音轨/画面、黑场、静帧、时长 vs 旁白时间轴 |

工坊 Phase 1「沙箱验证」会跑 demo 的 `verify.command`（Docker 沙箱）；Phase 4「双质检」可随时重跑；导入成片会自动跑成片门禁。

## Tools

- `draft_presentation_content` — 带调研笔记的深度文稿起草（工坊/API 会跑 LLM 打磨）
- `propose_presentation` — 交接讲解演示项目（须带 outline + full_script）
- `confirm_checkpoint` — 写入 A1 / B
- `scaffold_presentation` / `build_chapter` — 脚手架与章节
- `synthesize_narration_audio` — TTS（可选）
- `presentation_preview_url` — 预览 URL + OBS 清单

## 视觉纪律

- 固定舞台尺寸 + scale；每步独占整屏；口播节拍 = step
- 舞台无 chrome（进度条 hover 才显示）
- 主题 token 整片一致；默认 `talent-map` / `paper-press`，避免空洞纯黑
- 内容可含图示：`diagram.type` = `axes3` | `pipeline` | `state` | `cards` | `compare` | `checklist`；亦可用 `points` / `flow`
- demo 步可把 `outcome` 当作字幕/验收提示，录屏时对准该结果

## Do not

- 不要 invent Remotion/HyperFrames
- 不要在 A1 前 scaffold/build
- 不要在用户导入 mp4 前声称成片完成
- 不要默认走 Agnes L1 口播轨
- 不要用空洞口号冒充实内容；不达标就继续 draft
- 不要做成「只有概念图、没有安装与实测结果」的伪讲解
