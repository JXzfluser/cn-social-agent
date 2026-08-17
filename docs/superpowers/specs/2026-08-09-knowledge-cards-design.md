# 知识卡片工作台 · 设计（不含公众号）

> Date: 2026-08-09  
> Source: Workbuddy `card-gen-web`  
> Status: Integrated into main workbench (2026-08-09)

## 目标

把「AI 招聘知识卡片」完整接入 CN Workbench：扫描岗位 → 生成封面+知识卡 → 编辑预览 → 导出 PNG。

## 非目标

- ~~公众号草稿发布（后续可加）~~ → 见 [2026-08-09-card-platform-publish-design.md](./2026-08-09-card-platform-publish-design.md)（公众号 / 头条贴图发布）
- 引入 React/Vite/Tailwind 构建链

## 形态

- 入口：主工作台第三模式 `/?mode=card`（与 Agent / 短视频共用登录与顶栏）
- 旧链接 `/cards` → 302 到 `/?mode=card`
- API：`/api/cards/scan`、`/api/cards/history`（历史按 user 隔离）
- AI：**默认使用工作台已配置 LLM**（Agent 设置里切换）；无独立 DeepSeek 面板
- Agent 工具：`propose_knowledge_cards` / `scan_knowledge_cards` / `present_knowledge_card`
- 卡片画布：1080×1440 深色成片样式（导出外观保留）

## 功能清单

- 岗位扫描（live / cached / ai via workbench LLM）
- 历史存档与回载（按用户）
- 封面/知识卡编辑（2–5 张）
- Scaled 预览 + html-to-image PNG 导出
- 装饰图上传（dataURL）
- Agent 对话内建议卡 / 产物卡 → 打开卡片工坊
- **分类**：招聘洞察 / 产品科普 / 技能路线 / 行业速览（可扩展）
- **布局**：左（分类+主题+历史）· 中预览 · 右编辑；顶栏显示当前 LLM，InsForge 已配置时可一键切换
- InsForge：卡片生成走工作台 LLM；选 InsForge 提供商即用 InsForge/OpenRouter
