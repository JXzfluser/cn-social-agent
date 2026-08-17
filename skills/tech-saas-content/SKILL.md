---
id: tech-saas-content
name: Tech SaaS Content Pack
description: FDE vertical pack — weekly tech content OS for SaaS/devtools (hotspots → 口播/卡片 → publish SOP).
---

# Tech SaaS Content Pack

面向 **技术 SaaS / 开发者工具** 团队的内容流水线技能。FDE 驻场时可改本文件的默认参数与话术，稳定后再回灌主仓。

## 何时启用

用户提到：产品更新、Changelog、开发者内容、技术口播、每周发片、内容操作系统、FDE 试点、SaaS 品牌内容。

## 默认参数（可按客户覆盖）

| 键 | 默认 | 说明 |
|----|------|------|
| 平台优先 | 抖音 → 公众号 | 小红书半自动可选 |
| 口播时长 | 90–120s | 深度分析 180s |
| 背景 | `studio` / `desk` | 深度用 desk |
| 渲染 | 先 L0，再 L1 | 禁止把 L0 叫成成片 |
| 周产能 | 2 条口播或 1 口播+1 卡片组 | 签约成功标准为准 |

客户覆盖写在实例备忘或本 skill 末尾「客户覆盖」一节，勿改坏通用段。

## 周节奏（对 Agent 的硬流程）

1. **选题** — `scan_hotspot_board` 或客户 Changelog / GitHub Release / 招聘 JD  
2. **定角度** — `intro` | `idea` | `compare` | `deep_analysis` | 产品更新口播  
3. **制作** — `propose_short_video` → 确认分镜 → **L0** →（可选）**L1**  
4. **卡片并行** — 需要图文时走知识卡（产品科普 / 招聘洞察）  
5. **发布** — 按客户 SOP；提醒半自动步骤；记录链接  
6. **复盘** — 问本周卡点；建议是否改模板

找开源热点时配合 `github-star-growth-video`；纯链接分析用 `short-video-researcher`；导演参数用 `short-video-director`。

## 三条常驻内容线

### A. 产品更新（Changelog → 口播）

钩子：这周上了什么 → 谁该关心 → 3 个变化 → 怎么试 → 一个坑 → CTA（文档/试用）

### B. 技术观点（热点 / 竞品）

钩子：行业信号 → 我们的判断一句 → 证据 2 点 → 误区 → CTA

### C. 招聘 / 团队品牌（可选）

转 `hiring-insight-cards`：能力图谱卡 → 配一条 60–90s 口播讲「我们要什么样的人」。

## 交付话术

- L0：「分镜草稿，看结构与节奏，不是成片。」  
- L1：「可发成片；按镜计费/耗时，失败可解释。」  
- 发布：「先发一条验证账号与 SOP，再谈矩阵。」

## Do not

- 不要承诺无人值守全平台群发  
- 不要跳过 L0 直接宣称「已成片」  
- 不要把客户密钥写进 skill 正文（放 env / Secrets）

## 客户覆盖（FDE 填写）

```text
customer_id:
brand_voice:
forbidden_claims:
preferred_cta:
weekly_quota:
```
