---
id: hiring-insight-cards
name: Hiring Insight Cards
description: Produce 招聘洞察 knowledge-card journals and companion口播 for tech employer branding.
---

# Hiring Insight Cards

把 **招聘 JD / 能力要求** 变成可发的知识卡片组，并可配一条短口播。服务技术团队雇主品牌与 FDE 试点中的「招聘内容线」。

## 何时启用

用户提到：招聘洞察、JD、雇主品牌、招人、能力图谱、岗位卡片、技术招聘内容。

## 流程

1. **定范畴** — 卡片 category = `hiring_insight`；主题 1–3 个岗位或能力方向  
2. **扫描** — 用卡片工具 / `scan`：岗位职责与技能信号（深度 shallow → deep）  
3. **编排** — `compose` 出期刊结构；检查证据是否空洞  
4. **导出** — PNG 导出；公众号可贴图草稿；小红书半自动轮播  
5. **可选口播** — 60–90s：钩子（市场缺什么人）→ 我们要的 3 能力 → 误区 → CTA（JD 链接）  
   - 口播走 `propose_short_video`，`content_angle=intro`，提醒先 L0  

## 质量门槛

- 卡片正文避免百科空话；每张至少 1 个可核对信号（技能 / 年限 / 场景）  
- 系列封面标题具体（如「AI 应用工程师 · 能力图谱」），忌「招聘干货」  
- 发布前让客户确认：是否可公开、是否脱敏薪资  

## 与 tech-saas-content 的分工

| 场景 | 主 skill |
|------|----------|
| 周更产品/技术口播 | `tech-saas-content` |
| 招聘专题卡 + 雇主内容 | **本 skill** |
| 纯 GitHub 涨星选题 | `github-star-growth-video` |

## Do not

- 不要编造公司未提供的薪资与 HC  
- 不要把竞品 JD 原文大段搬运当「洞察」  
- 不要跳过客户审核直接公开发布  

## 客户覆盖（FDE 填写）

```text
customer_id:
roles_focus:
tone: (严谨学术 / 活泼技术)
cta_url:
```
