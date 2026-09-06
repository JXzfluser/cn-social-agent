# 功能闭环复利 + UI 极致化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 不加新功能。接通现有 8 条功能闭环中 7 条已断裂的数据链路（复利飞轮），并把 UI 从"功能堆叠"打磨到"极致体验"（统一交互语言 + 长任务过程可视化）。

**Background:** 2026-08-30 全面评估结论：系统骨架（令牌系统、画布、质量面板、内容项目枢纽）已是 4.5 分水准，但 (a) 7 条复利链路在关键节点断裂（KB 只写不读、idea 死胡同、口播不吃研究笔记、视频不回写枢纽等），(b) 工作流/idea/knowhow 三个视图存在功能性崩溃与设计系统脱节。

**核心原则:**
1. 只接通链路，不造新轮子 — 每个修复都复用已有服务（`cps.create_project`、`generate_script`、`run_research`）。
2. 服务端闭环优先 — 凡数据流依赖 UI 行为才能闭合的，改为服务端主动闭合。
3. 先修崩溃，再谈体验 — Phase 0 全是体验性硬伤。

---

## 复利链路全景（目标态）

```
                    ┌──────────────────────────────────────┐
                    │         topic_key 知识轴心            │
                    └──────────┬───────────────────────────┘
       ┌──────────┬───────────┼───────────┬──────────┐
       ▼          ▼           ▼           ▼          ▼
  ┌─────────┐ ┌────────┐ ┌────────┐ ┌─────────┐ ┌────────┐
  │ 热点发现 │ │ Idea   │ │ Agent  │ │ KnowHow│ │ Learn  │
  │ 引擎    │ │ Engine │ │ 研究   │ │ 笔记   │ │ 洞察   │
  └────┬────┘ └───┬────┘ └───┬────┘ └────┬────┘ └───┬────┘
       └──────────┴───────────┼───────────┴──────────┘
                              ▼
   ┌─────────────────────────────────────────────────────┐
   │              内容项目 (Content Project)               │
   │  topic_key · research_notes · evidence_pack          │
   │  artifacts: { journal_id, video_id, presentation_id }│
   └──────────────────────┬──────────────────────────────┘
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │ 知识期刊  │   │ 口播视频  │   │ 讲解演示视频  │
    └──────────┘   └──────────┘   └──────────────┘
```

已闭合（保留）：热点→内容项目→期刊证据回写→export_ready；期刊证据→讲解演示脚本注入；topic_assets 每次 propose 前聚合；生产计划→agent todos 反向同步。

断裂（本计划接通）：①KB 只写不读 ②口播不吃研究笔记 ③agent handoff 不建项目 ④视频不回写项目 ⑤idea 引擎未接线 ⑥knowhow 洞察零消费 ⑦工作流 Handler 空壳。

---

## File map

| File | Responsibility |
|------|----------------|
| Modify: `src/cn_social_agent/api/app.py` | 解决合并冲突（P0-1） |
| Modify: `src/cn_social_agent/workflow/index.js` | TemplateMarket/ScheduleManager 崩溃修复（P0-2） |
| Modify: `src/cn_social_agent/workflow/schedule-manager.js` | listTemplates→真实日程（P0-2） |
| Modify: `src/cn_social_agent/workbench/learn.js` | SM-2 ease bug + exportToCanvas schema（P0-3） |
| Modify: `src/cn_social_agent/workbench/idea-engine.js` | 双重实例化 + XSS + 事件委托（P0-4） |
| Modify: `src/cn_social_agent/agent/mode.py` | query_knowledge_base 入工具集（P1-1） |
| Modify: `src/cn_social_agent/video/pipeline.py` | generate_script 接受 research_notes（P1-2） |
| Modify: `src/cn_social_agent/api/video_routes.py` | 组装研究笔记；渲染成功回写内容项目（P1-2/P1-4） |
| Modify: `src/cn_social_agent/tools/builtin.py` | handoff_hotspot 共享路由逻辑建项目（P1-3） |
| Create: `src/cn_social_agent/tools/handoff_service.py` | handoff 共享服务函数（P1-3） |
| Modify: `src/cn_social_agent/api/hotspots_routes.py` | 改调共享服务（P1-3） |
| Modify: `src/cn_social_agent/idea_engine/integrator.py` | 项目 store 适配器接线（P1-5） |
| Modify: `src/cn_social_agent/api/deps.py` | 启动时注入 stores（P1-5） |
| Modify: `src/cn_social_agent/workbench/index.html` | Phase 2 UI 三件套（P2） |
| Create: `tests/workbench/test_compound_loops.py` | 链路回归测试（P1） |

---

# Phase 0 — 修基础（体验性硬伤）

### Task P0-1: 解决 api/app.py 合并冲突

- [ ] **Step 1: 确认冲突面** — 四处标记：imports、`on_startup`、`on_cleanup`、`create_app` 路由注册。
- [ ] **Step 2: 保留策略** — 上游侧为基线 + 保留真实存在的新路由（learn/topic_hub/workflow/idea）；丢弃对不存在的 `knowledge_routes` / `content.scheduler` 的引用。
- [ ] **Step 3: 验证** — `python -c "from cn_social_agent.api.app import create_app"` + `pytest tests/workbench/test_workbench_api.py -q` 通过。

### Task P0-2: 修工作流编辑器崩溃

- [ ] `workflow/index.js:191` `TemplateMarketPanel` → `TemplateMarket`
- [ ] `workflow/index.js:193` `ScheduleManagerPanel` → `ScheduleManager`
- [ ] `schedule-manager.js` 将 `listTemplates()` 改为真实日程列表读取（无则空态文案，不冒充）
- [ ] 验证：浏览器打开工作流 tab，点"更多→模板市场/定时任务"不再白屏。

### Task P0-3: 修 learn.js SM-2 与画布导出 schema

- [ ] SM-2 ease 更新：`s.q` undefined 导致 ease 永远 1.3 — 复习评分时记录 `q` 并参与 ease 计算。
- [ ] `exportToCanvas` 节点 `{type:"note", content}` → `{kind:"note", text}` 对齐画布 schema。
- [ ] 验证：单元测试（如 learn 逻辑有可测纯函数则补测）。

### Task P0-4: 修 Idea 面板双重实例化与 XSS

- [ ] 删除 `index.html:10349-10356` 的 lazy 第二实例化，或删除 idea-engine.js 的 DOMContentLoaded 自建（保留一处）。
- [ ] 所有 `innerHTML` 拼接点改用主应用 `escapeHtml`（标题/摘要/标签）。
- [ ] `onclick="ideaPanel.xxx(...)"` 内联 JSON 属性 → 事件委托。
- [ ] 验证：打开/关闭侧栏仅一次初始化；带引号标题不崩。

---

# Phase 1 — 接通复利链路（数据流）

### Task P1-1: KB 双向通道

- [ ] `agent/mode.py` 的 `RESEARCH_TOOLS` 与 `PRODUCE_TOOLS` 加入 `query_knowledge_base`。
- [ ] 测试：MockLLM 场景下工具不被过滤（tests 补一条断言）。

### Task P1-2: 口播脚本消费研究笔记

- [ ] `video/pipeline.py:generate_script` 增加 `research_notes: list[str] | None` 参数，注入 prompt 的"本地证据（必须吸收）"段（对齐 `presentation_content.py` 的做法）。
- [ ] `api/video_routes.py` 项目创建/from-session 时：按 `content_project_id` 或 `topic_key` 从内容项目取 `evidence_pack` + `research_notes` 组装传入。
- [ ] 测试：`tests/workbench/` 补 generate_script 带研究笔记的断言。

### Task P1-3: Agent handoff 统一建内容项目

- [ ] Create `tools/handoff_service.py`: 提取 `create_handoff(...)` = build payload + `cps.create_project`（从 `hotspots_routes.py:104-154` 提取）。
- [ ] `api/hotspots_routes.py` 改调共享函数。
- [ ] `tools/builtin.py:handoff_hotspot` 改调共享函数（返回 content_project_id 给 agent）。
- [ ] 测试：agent 工具路径 handoff 后 `content_project_id` 非空。

### Task P1-4: 视频完成回写内容项目

- [ ] `api/video_routes.py` L0/L1 渲染成功路径：有 `content_project_id` 或 `topic_key` 匹配时 `cps.attach_artifacts(project_id, video_id=...)`，状态 → `export_ready`（仅当质量门通过）。
- [ ] 测试：渲染成功后项目 artifacts.video_id 非空。

### Task P1-5: Idea Engine 接入持久化与项目

- [ ] `api/deps.py` 启动时 `integrator.set_project_store(cps 适配器)`。
- [ ] IdeaEngine materials/cards 持久化到 `wb_idea_*`（已有 ensure 脚本建表；失败降级内存模式并 warn）。
- [ ] 测试：选中 idea 卡（create_project=True）后内容项目存在。

---

# Phase 2 — UI 一致性（交互语言统一）

### Task P2-1: dialog/toast/骨架屏三件套
- [ ] 全站 `alert/confirm/prompt` → `openDialog()`（cards/knowhow/learn/workflow）。
- [ ] `workflowNotify` 提拔为全局 `wbToast()` 组件。
- [ ] 骨架屏套件 `.wb-skeleton` 覆盖：看板、会话列表、卡片历史、项目详情。

### Task P2-2: Agent 聊天体验
- [ ] 流式期间 tool trail（工具名 + spinner）。
- [ ] 消息 markdown 渲染（escape 后 mini-markdown）。
- [ ] 停止生成按钮（AbortController）。
- [ ] 复制/重发悬浮操作条。

### Task P2-3: 卡片编辑器性能
- [ ] `renderPreview()` 输入防抖 150ms。
- [ ] 预览翻页动效 + 配色一键轮换。

### Task P2-4: 工作流编辑器接入设计系统
- [ ] 内联样式 → 共享 CSS 类（复用 `.cv-*` 语言）。
- [ ] 节点状态色接入令牌（`--ok/--danger/--accent`）。
- [ ] 真实 undo/redo（拖拽/配置变更入栈 + 状态回滚）。

### Task P2-5: KnowHow + Learn 合并
- [ ] Learn 视图并入 KnowHow 详情 tab（学习/自测/导师）。
- [ ] 笔记改可编辑卡片；图谱用画布技术渲染。

### Task P2-6: 成本可视化接线
- [ ] 全局成本条（本周累计，悬浮明细）接 `/api/usage/summary`。
- [ ] L1 渲染按钮旁预估成本提示。

---

# Phase 3 — 极致体验（持续）

### Task P3-1: 长任务进度可视化全覆盖
- [ ] 视频渲染步骤条动画（脚本→TTS→画面→合成→质检）。
- [ ] 讲解轨收敛为向导式单列（高级按钮降级）。
- [ ] AI 画布整理 FLIP 动画。

### Task P3-2: 创作动线重构
- [ ] 模式切换收敛为"发现→研究→整理→创作→发布"叙事。
- [ ] Board/Atlas/Learn 入口进顶部导航。

### Task P3-3: 画布增强
- [ ] 拖拽式连线 + 磁性吸附。
- [ ] 缩放改内容变换避免模糊。

### Task P3-4: 知识复利深化
- [ ] 按 topic_key 归集成本（usage 事件带 topic）。
- [ ] KnowHow 洞察注入生成上下文（`query_topic_insights` 工具）。
- [ ] 工作流 Handler 接入真实服务（LLM/渲染/研究/发布）。

---

## Verification

- [ ] Phase 0: `pytest tests/workbench -q` 全绿 + 应用可启动（`run_workbench.py` smoke）。
- [ ] Phase 1: `tests/workbench/test_compound_loops.py` 七条链路断言全绿。
- [ ] Phase 2: 浏览器实测（browser-use MCP）走通 golden path，console 无报错。
- [ ] Phase 3: 每项交付配一次浏览器实测。

## Out of scope（本计划不做）

- 付费用户/定价相关工作（用户明确暂不考虑）。
- 新功能模块（Marketplace、多平台一键发布、真人拍摄）。
- pipeline.py / index.html 大拆分（另行计划）。
