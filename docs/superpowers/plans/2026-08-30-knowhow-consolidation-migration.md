# Know-How 收敛整合 · 移除"项目"实体 · 统一 UI 规划 · 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 取消"内容项目 (Content Project)"这一独立实体，由 Know-How 作为 Agent 唯一知识库承载所有沉淀（话题 / 笔记 / 工作流记录 / 内容资产 / 学习 / 选题素材 / Skill 管理 + 提取）。同步重写工作台 UI 为"两区四视图"结构，清理冗余代码与文档，推动按新结构全量实施。

**Background:** 2026-08-30 评估结论：
1. Know-How 容器已就绪（17 个 `/api/knowhow/*` 路由 + 前端 `viewKnowhow`，旧 `assets`/`learn` mode 已重定向到 `knowhow`），但"项目"作为并行实体仍在后端挂载、前端散落 33 处 `content_project_id` 耦合，两套知识载体并存。
2. Skill 当前是 `skills/` 目录下的 10 个 SKILL.md 文件，loader 按消息文本匹配触发器注入 prompt；用户不能从创作经验中提取新 skill。Know-How 不承载 skill 管理，违反"唯一知识库"定位。
3. UI 顶栏 6 个 mode 按钮 + section 实际 9 个（含隐藏的 viewBoard/viewLearn/viewAtlas），结构臃肿、入口分散，没有体现"制作区 + 知识区"的二分。

**核心原则:**
1. 唯一知识轴心是 `topic_key`，不是 `content_project_id` — 所有制作流程上下文挂载点从项目改为话题。
2. Know-How 是 Agent 唯一知识库 — 承载 Notes / Workflow Records / Assets / KB / Skills，所有沉淀进 Know-How。
3. Skill 分两层 — 预置 skill（文件即真相，只读展示 + 开关）+ 经验 skill（从 workflow records 抽象，可编辑，可被 Agent 注入）。
4. 创作过程自动写入沉淀 — 不依赖用户手动录入；复利来自内部经验抽象。
5. UI 二分结构 — 制作区（Agent / 短视频 / 卡片 / 画布）+ 知识区（Know-How），顶栏只两组入口。
6. 先归档文档降低噪音，再解耦后端，再重写 UI，最后接 skill 承载 — 风险递增。

---

## 目标架构

```
                    ┌──────────────────────────────────────┐
                    │      topic_key · 唯一知识轴心         │
                    └──────────────┬───────────────────────┘
                                   ▼
              ┌────────────────────────────────────────────┐
              │            Know-How 知识库                │
              ├────────────────────────────────────────────┤
              │  Topics(话题) · 唯一索引键 topic_key      │
              │  ├ Notes 原子笔记                          │
              │  │   source_type:                         │
              │  │     research  ← 制作研究副产品         │
              │  │     feed      ← Idea 选题层素材        │
              │  │     learning  ← 学习模块同步           │
              │  │     manual    ← 用户手动灵感           │
              │  ├ Workflow Records 工作流记录            │
              │  │   ← 创作完成自动写入                   │
              │  ├ Skills 技能库（新增）                  │
              │  │   ├ 预置：从 skills/ 文件读，只读+开关  │
              │  │   └ 经验：从 ≥3 条 workflow 抽象       │
              │  │     字段：when_to_use / body /         │
              │  │           source_workflows[]           │
              │  ├ Assets 内容资产                        │
              │  │   卡片/短视频/期刊 按 topic_key 聚合   │
              │  └ KB 知识库（向量检索 / quiz / tutor）  │
              └────────────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
   选题(Idea层)              制作(L0→L1)                   质检→发布
   feed素材汇聚              带 topic_key 上下文           成品回写 Assets
   → propose 到 topic       research→Know-How Notes      workflow→自动记录
                                                      经验→Skills 抽象
```

**闭环点：** 制作过程副产品自动写入 Know-How（Notes / Workflow Records）；同 topic 攒够 3 条 workflow 后 Agent 提议抽象经验 skill；下次同主题创作时 Agent 从 Know-How 读取历史 Notes + Skills 注入 prompt。复利来自内部沉淀，不依赖外部平台数据回流。

---

## UI 整体规划（目标态）

### 设计原则

Know-How 现有结构（话题列表 + 6 个 Tab：话题/笔记/工作流/技能/资产/KB）太复杂——用户要"先选话题再切 Tab 再看内容"，每多一层切换就多一层认知负担。重新设计遵循四条原则：

1. **默认不切 Tab** — 进 Know-How 就是一个可读的内容流，不是空架子
2. **话题是上下文不是导航** — 话题列表收缩为侧边筛选器，不强制点击
3. **搜索是主入口** — 知识库的核心动作是"找"，不是"分层浏览"
4. **主侧栏随 mode 自适应** — 侧栏下半部根据当前 mode 显示该 mode 真正需要的辅助内容（会话/话题/项目/编辑参数），不是死导航

### 整体布局：主侧栏 + 主内容区

参考 ChatGPT/Claude/Cursor 的左侧栏范式，把当前顶栏的 mode 按钮 + 各视图内独立的 `<aside class="rail">` 合并为一个统一主侧栏。整体严格左右结构，侧栏内部各区域职责清晰、不混淆堆叠。

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ┌──────────────┐  ┌─────────────────────────────────────────────┐  │
│  │  主侧栏      │  │  主内容区                                   │  │
│  │  240px       │  │  （当前 mode 的核心工作区，无内部左栏）     │  │
│  │              │  │                                             │  │
│  └──────────────┘  └─────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**为何不用顶栏：** 顶栏占垂直空间 56px、按钮数量受限、不能显示当前上下文（话题/会话）。左侧栏解决三个问题：(1) 不占垂直空间；(2) 可列表化显示历史/筛选；(3) **解决 Know-How 还要内部左栏的双栏问题**——Know-How 的话题筛选合并进主侧栏上下文区，主区域只剩内容流。

**折叠/展开：** 默认 240px 展开；可折叠为 56px 图标栏（hover 显示文字 tooltip）。移动端 < 768px 折叠为抽屉，hamburger 唤出。

### 功能性质分类与组织（★核心设计）

当前问题：连接器/自动化/LLM/发布账号/主题/图鉴/InsForge 七项功能散落在顶栏 4 按钮 + 账号菜单 6 项，重复且无分类。按性质重新归类：

| 性质 | 功能 | 频次 | 归属 |
|------|------|------|------|
| 导航 | 5 个 mode | 高频 | 主侧栏导航区 |
| 上下文 | 会话/项目/话题/编辑参数 | 高频 | 主侧栏上下文区（随 mode 自适应） |
| 配置 | 模型与路由 / 发布账号 / 连接器 | 低频一次性 | 统一「设置」弹窗分 Tab |
| 运行管理 | 自动化配方与运行 | 中频 | 统一「设置」弹窗「自动化」Tab |
| 内容 | 人口图鉴 | 按需 | Know-How 内容流 asset 卡片 |
| 偏好 | 主题切换 | 极低频 | 统一「设置」弹窗「外观」Tab |
| 外部 | InsForge 控制台 | 极低频 | 统一「设置」弹窗「关于」Tab |

**关键原则：**
1. **侧栏纯粹** — 只放导航 + 上下文区 + 底部两个入口图标（账号/设置）。不堆配置功能。
2. **配置统一** — 模型/发布账号/连接器/自动化/主题/InsForge 全部进「设置」弹窗，分 Tab 组织。不再散落顶栏按钮 + 账号菜单重复项。
3. **内容回归内容区** — 人口图鉴是内容不是配置，作为 Know-How 内容流的 asset 卡片嵌入。
4. **运行 vs 配置** — 自动化的"配方管理"是配置进设置 Tab；"运行"也在同一 Tab 内（运行面板），因为运行频率不高，不值得独立占侧栏位。

### 主侧栏结构（从上到下，左右结构的左侧）

```
┌──────────────────┐
│ [内容工作台]     │  ← Logo（折叠时只图标）
├──────────────────┤
│ 🔍 搜索          │  ← 全局搜索入口（Ctrl+K）
│                  │     跨 Know-How 全库 + Agent 历史会话
├──────────────────┤
│ 导航区（mode）   │  ← 5 个 mode 图标+文字
│  ◆ Agent         │     当前 mode 高亮
│  ▶ 短视频        │
│  ◇ 卡片          │
│  ▦ 画布          │
│  📚 Know-How     │
├──────────────────┤
│ 上下文区         │  ← ★关键：随 mode 自适应内容
│                  │     （占侧栏剩余高度，可滚动）
│  [agent 模式]    │
│   最近会话       │
│   · 产品更新     │
│   · 增长曲线     │
│   + 新对话       │
│                  │
│  [knowhow 模式]  │
│   话题筛选(多选) │
│   ▸ 全部         │
│   ▸ 产品         │
│   ▸ AI           │
│   + 新话题       │
│   ─              │
│   类型筛选(多选) │
│   ▸ 笔记/工作流  │
│   ▸ Skill/资产  │
│                  │
│  [video 模式]    │
│   最近项目       │
│   + 新建         │
│                  │
│  [card 模式]     │
│   分类选择       │
│   主题输入       │
│   期号输入       │
│   ← 编辑参数！   │
│                  │
│  [canvas 模式]   │
│   画布列表       │
│   + 新建画布     │
├──────────────────┤
│  👤 ⚙           │  ← 底部两个图标入口
│  账号 设置       │     账号：用户信息 + 登出
└──────────────────┘               设置：打开统一设置弹窗
```

**侧栏底部只两个图标（不是堆叠菜单）：**
- `👤 账号` — 点开小弹层：用户信息 + 登出。不含任何配置功能。
- `⚙ 设置` — 点开「设置」弹窗（见下）。

### 设置弹窗（统一配置中心）

点侧栏底部 `⚙ 设置` 图标唤出，全屏弹窗分左侧 Tab + 右侧内容：

```
┌──────────────────────────────────────────────────────────┐
│ 设置                                              [×]    │
├──────────────┬───────────────────────────────────────────┤
│              │                                           │
│  模型与路由  │  ← 当前 Tab 内容区                        │
│  发布账号    │                                           │
│  连接器      │  复用现有 openAccountSettings /           │
│  自动化      │  openConnectorsPanel /                   │
│  外观        │  openAutomationsPanel /                  │
│  关于        │  openPlatformAccounts 的渲染逻辑，        │
│              │  从独立弹窗改为嵌入此 Tab 内容区          │
│              │                                           │
└──────────────┴───────────────────────────────────────────┘
```

**Tab 划分（对应现有功能，不丢功能只重组织）：**

| Tab | 承载功能 | 实现来源 |
|-----|---------|---------|
| 模型与路由 | LLM 模型选择 + 路由策略（不含登录表单，登录在账号 popover） | 复用 `openAccountSettings()` 渲染逻辑，剥离登录表单部分 |
| 发布账号 | 微信/头条/抖音/小红书 OAuth | 复用 `accountOpenPlat` 面板逻辑 |
| 连接器 | 内容源（GitHub/HN/V2EX）+ 发布连接器配置 | 复用 `openConnectorsPanel()` 渲染逻辑 |
| 自动化 | 配方管理 + 运行面板 | 复用 `openAutomationsPanel()` 渲染逻辑 |
| 外观 | 主题切换（亮/暗） | 复用 `#themeToggle` handler |
| 关于 | InsForge 控制台链接 + 版本信息 | 复用 `#insforgeLink` |

**实现策略：** 现有 `openXxxPanel()` 函数渲染的是独立弹窗 DOM。重构时把这些渲染逻辑提取为 `renderXxxTab(container)` 函数，在设置弹窗的 Tab 内容区调用。不重写业务逻辑，只改容器。

### 顶栏处理

顶栏**完全删除**（不留极简顶栏）。原因：
- mode 导航在侧栏
- 配置在设置弹窗
- 主题在设置弹窗
- 移动端 hamburger 直接放侧栏顶部（侧栏折叠为抽屉时，顶部一个 hamburger 唤出）

移动端：`< 768px` 时侧栏默认隐藏为抽屉，侧栏顶部显示 hamburger 图标唤出。

### 主内容区各视图布局

主内容区始终是当前 mode 的工作区，**无内部左栏**（左栏职责全归主侧栏上下文区）。各视图保留各自右侧 `.side` 面板（编辑器属性面板，性质不同）：

| Mode | 主内容区结构 | 右侧 .side 保留 |
|------|------------|---------------|
| Agent | messages + composer（无左 rail） | idea-sidebar 抽屉保留（Idea 引擎，右侧浮动） |
| 短视频 | L0→L1 工作台（无左 rail） | 参数面板 .side 保留 |
| 卡片 | 编辑器（无左 rail） | 预览/导出 .side 保留 |
| 画布 | 自由排版（无左 rail） | — |
| Know-How | 单层内容流 + 顶部搜索（无 Tab 无左栏） | — |

### Know-How 视图在侧栏下的最终形态

主侧栏已承载话题筛选 + 类型筛选，Know-How 主区域**只剩内容流 + 顶部搜索框**：

```
┌────────────────────────────────────────────────────────────────────┐
│ Know-How · 知识库              [🔍 搜索全库]      [+ 新笔记]      │  ← 顶部 toolbar
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  内容流（话题/类型筛选已在左侧栏完成，按时间倒序）              │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 📝 笔记 · 话题「产品更新」 · 2 天前                          │  │
│  │   正文片段…                                                  │  │
│  │   [#标签] [[相关话题]]  [编辑]                              │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ 📋 工作流 · 话题「增长」 · 3 天前                            │  │
│  │   用了「钩子→痛点→价值」模板 · 质检通过                      │  │
│  │   [📎 成品视频]  [⚙ 提取为 Skill]                           │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ 🎯 Skill · 话题「AI」 · 5 天前                               │  │
│  │   when_to_use: 用户问"AI 工具对比"时                       │  │
│  │   body 摘要…   [开关]  [编辑]                               │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ 📊 人口图鉴 · 话题「人口」 · 1 周前                          │  │
│  │   [展开 iframe ↓]                                          │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ 🤖 KB 回答 · 搜索"xxx" · 刚刚                               │  │
│  │   检索结果摘要…                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**核心简化：**
- **Know-How 主区域无 Tab、无内部左栏**——话题/类型筛选在主侧栏上下文区
- **所有类型混在同一流**——笔记/工作流/Skill/资产/图鉴/KB 回答，按类型筛选器收窄
- **图鉴是内容项之一**——人口图鉴作为特殊 asset 类型嵌入流
- **Skill 是内容项之一**——预置 + 经验 skill 混在流里，开关和提取操作在卡上 inline
- **搜索全局可用**——顶部搜索框跨所有类型，回车后追加 KB 检索结果带 🤖 标记

**内容项卡片（按类型自适应）：**
- 笔记卡：标题 + 正文片段 + 标签 + 双链 + 编辑按钮
- 工作流卡：method + 质检状态 + 耗时 + 成品链接 + 「⚙ 提取为 Skill」（workflow ≥3 时高亮）
- Skill 卡：when_to_use + body 摘要 + 启停开关 + 编辑按钮；预置 skill 加 🔒
- 资产卡：缩略图/标题 + 打开/下载按钮
- 图鉴卡：标题 + 嵌入 iframe + 全屏按钮（懒加载）
- KB 回答卡：检索摘要 + 来源笔记链接 + 🤖 标记

### 删除的视图

| 旧 section | 处理 | 理由 |
|---|---|---|
| `viewBoard` | 删除 | 项目实体取消 |
| `viewLearn` | 删除 section | 学习功能（笔记/收藏）并入 Know-How 内容流，source_type=learning |
| `viewAtlas` | 删除 section | 图鉴作为 asset 类型嵌入 Know-How 流；账号菜单"高级"入口保留全屏 |
| `viewWorkflow` | 删除 section + mode 按钮 | 工作流编排并入账号菜单"自动化"项；配方和运行仍在 |

最终顶栏只 logo + hamburger，主侧栏 5 个 mode。右侧 0 个独立按钮，全在账号 chip 下拉。

---

## 冗余清单

### 代码冗余（src/）

| 文件 / 符号 | 处理 | Step |
|---|---|---|
| `api/content_project_routes.py` | 移除挂载 → 物理删 | 2 / 3 |
| `content/board.py` | 删除 | 2 |
| `content/service.py` 项目函数 | 删项目函数，保 topic_key 相关 | 2 |
| `content/models.py` Project 模型 | 删除 | 2 |
| `workbench/project_board.js` | 删除 | 3 |
| `index.html` `#viewBoard` section | 删除 | 4 |
| `index.html` `.board-*` CSS | 删除 | 4 |
| `index.html` `board-card` JS | 删除 | 4 |
| `index.html` `#viewLearn` section | 删除（功能并入 Know-How） | 4 |
| `index.html` `#viewAtlas` section | 删除 | 4 |
| `index.html` `content_project_id`（33 处） | 改为 `topic_key` | 3 |
| `learn.js` | 删除文件（学习功能并入 Know-How） | 4 |
| `population-atlas.html` | 归档不删 | 4 |

### 文档冗余（docs/）

**直接归档**（移至 `docs/archive/legacy/`）：
- `docs/PRD.md`、`docs/PRD_v2.md`
- `docs/MODULE_DEEP_DIVE.md`、`docs/MODULE_EVALUATION.md`
- `docs/PRODUCT_ANALYSIS.md`、`docs/PRODUCT_ITERATION_2026-08-17.md`
- `docs/CONTENT_GENERATION_OPTIMIZATION.md`、`docs/UX_IMPROVEMENTS.md`
- `docs/Harness视频制作资料.md`、`docs/fde/`、`docs/content/`
- `docs/superpowers/plans/2026-08-30-compound-loop-ui-polish.md`（被本计划取代）

**保留但标注状态**（加头部 `> Status: 已被 Know-How 收敛取代，仅作历史参考`）：
- `docs/superpowers/specs/2026-08-16-workbuddy-content-os-design.md`
- `docs/superpowers/specs/2026-08-16-canvas-project-enhancement-design.md`
- `docs/superpowers/specs/2026-08-25-kb-architecture-redesign.md`
- `docs/superpowers/specs/2026-08-29-idea-engine-design.md`
- `docs/superpowers/plans/2026-08-16-content-project-s1.md`
- `docs/superpowers/plans/2026-08-16-canvas-project-enhancement.md`

**保留主线**：产品定位、Know-How 设计、短视频/卡片/质检/发布相关 specs/plans。

---

## File map

| File | Responsibility | Step |
|------|----------------|------|
| Create: `docs/archive/legacy/README.md` | 归档说明 | 1 |
| Move: 12 文件/目录 → `docs/archive/legacy/` | 降噪音 | 1 |
| Edit: 6 个 specs/plans 加状态标注 | 防误导 | 1 |
| Edit: `src/cn_social_agent/api/app.py` | 移除 `setup_content_project_routes` 挂载 | 2 |
| Delete: `src/cn_social_agent/content/board.py` | 死代码 | 2 |
| Edit: `src/cn_social_agent/content/service.py` | 删项目函数 | 2 |
| Edit: `src/cn_social_agent/content/models.py` | 删 Project 模型 | 2 |
| Delete: `src/cn_social_agent/api/content_project_routes.py` | 物理删 | 3 |
| Delete: `src/cn_social_agent/workbench/project_board.js` | 死前端 | 3 |
| Edit: `src/cn_social_agent/workbench/index.html` | 33 处 `content_project_id`→`topic_key` | 3 |
| Edit: `src/cn_social_agent/workbench/video_workshop.js` | `setContentProjectId`→`setTopicKey` | 3 |
| Edit: `src/cn_social_agent/workbench/cards_workshop.js` | 同上耦合点修复 | 3 |
| Edit: `src/cn_social_agent/workbench/index.html` | 删 viewBoard/viewLearn/viewAtlas/viewWorkflow section + board CSS/JS | 4b |
| Edit: `src/cn_social_agent/workbench/index.html` | 顶栏完全删除 + 新增 `<aside id="appRail">` 主侧栏骨架（含底部账号/设置两图标）+ CSS + setRailContext JS | 4a |
| Edit: `src/cn_social_agent/workbench/index.html` | 新增设置弹窗 `<div id="settingsModal">` + 6 Tab + renderSettingsTab JS（复用现有 openXxxPanel 渲染逻辑） | 4a |
| Edit: `src/cn_social_agent/workbench/index.html` | body 改 flex 布局，各 section.view 包入 `<main id="appMain">` | 4a |
| Edit: `src/cn_social_agent/workbench/index.html` | 各视图内部 `<aside class="rail">` 内容平移到 setRailContext + 删内部 rail | 4b |
| Edit: `src/cn_social_agent/workbench/index.html` | `viewKnowhow` 重写为单层内容流（去 Tab，搜索 + 流） | 4b |
| Delete: `src/cn_social_agent/workbench/learn.js` | 学习并入 Know-How | 4b |
| Edit: `src/cn_social_agent/api/topic_hub_routes.py` | 新增 `/api/knowhow/stream` + `/api/knowhow/search` + `/api/knowhow/{key}/skills` CRUD + `/extract-skills`（A 组后端前置） | 4b |
| Edit: `src/cn_social_agent/api/sessions.py` | 新增 `/api/sessions/search` 会话标题搜索 | 4b |
| Create: `src/cn_social_agent/knowledge/skills.py` | Skill 服务（读文件 + 读写经验 skill + LLM 提取） | 4b |
| Edit: `src/cn_social_agent/agent/mode.py` | prompt 注入 topic 下的经验 skill（F 组） | 4b |
| Edit: `src/cn_social_agent/schema/workbench.sql` 增表 | `wb_topic_skills` 表（A 组） | 4b |
| Edit: `src/cn_social_agent/workbench/index.html` | 新增 `<dialog id="globalSearchModal">` 搜索弹窗 + CSS + 键盘 handler + 跳转逻辑（E 组） | 4b |

---

## Step 1: 文档归档（最低风险）

**目标：** 把已放弃方向文档移出顶层视线，给保留但过时文档加状态声明，防止 Agent / 协作者读到被误导。

### 任务

- [x] 1.1 创建 `docs/archive/legacy/` 目录
- [x] 1.2 写 `docs/archive/legacy/README.md`：说明本目录文档描述的方向（多平台 SCRM SaaS / Content Project 枢纽 / 遗产模块）已放弃，仅作历史参考，**勿据此开发或建议**。当前主线见 `docs/superpowers/specs/2026-08-29-knowhow-system-design.md`
- [x] 1.3 移动以下到 `docs/archive/legacy/`：
  - `docs/PRD.md`、`docs/PRD_v2.md`
  - `docs/MODULE_DEEP_DIVE.md`、`docs/MODULE_EVALUATION.md`
  - `docs/PRODUCT_ANALYSIS.md`、`docs/PRODUCT_ITERATION_2026-08-17.md`
  - `docs/CONTENT_GENERATION_OPTIMIZATION.md`、`docs/UX_IMPROVEMENTS.md`
  - `docs/Harness视频制作资料.md`、`docs/fde/`（整目录）、`docs/content/`（整目录）
  - `docs/superpowers/plans/2026-08-30-compound-loop-ui-polish.md`
- [x] 1.4 给以下文件头部加状态声明：
  - `docs/superpowers/specs/2026-08-16-workbuddy-content-os-design.md`
  - `docs/superpowers/specs/2026-08-16-canvas-project-enhancement-design.md`
  - `docs/superpowers/specs/2026-08-25-kb-architecture-redesign.md`
  - `docs/superpowers/specs/2026-08-29-idea-engine-design.md`
  - `docs/superpowers/plans/2026-08-16-content-project-s1.md`
  - `docs/superpowers/plans/2026-08-16-canvas-project-enhancement.md`
- [x] 1.5 更新 `README.md` 文档索引段落，移除已归档引用，补指向 Know-How 主线设计

### 验收
- [x] `docs/` 顶层只剩 `archive/`、`superpowers/` 两个目录
- [x] 被标注的 6 个文件头部有声明
- [x] `README.md` 无死链

### 风险
- 低。纯文件移动 + 文本编辑。注意移动后 grep 文档交叉引用是否断链。

---

## Step 2: 后端解耦 content_project（中风险）

**目标：** 移除项目路由挂载，删除项目死代码，保留函数参数 `content_project_id` 改为 `topic_key`。content_project 表暂保留只读过渡。

### 任务

- [x] 2.1 在 [app.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/app.py) 移除 `from cn_social_agent.api.content_project_routes import setup_content_project_routes` 与 `setup_content_project_routes(app)` 调用
- [x] 2.2 删除 [content/board.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/content/board.py)（`git rm`）+ 删除 [content_project_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/content_project_routes.py)（孤儿，随 board 一起删）
- [x] 2.3 [content/service.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/content/service.py) 函数体改桩（返回 `{}`/`None`/`[]`），保留签名让 6 处调用方（canvas_routes/card_routes/idea_engine/project_bridge/handoff_service/research_link/automations）import 链不断、`.get()` 不崩
- [x] 2.4 [content/models.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/content/models.py) 的 `normalize_project` 改轻量桩：移除 `from content.board import BOARD_STATUSES, project_lane`、删除 `STATUSES = BOARD_STATUSES`、删除 `out["lane"] = project_lane(out)` 与 status 白名单校验；保留字段补全逻辑供 cloud/store_local 调用
- [x] 2.5 grep 全 `src/` 确认无 `content_project_routes` / `from cn_social_agent.content.board` / `import Project` 残留（清零）
- [x] 2.6 跑 `PYTHONPATH=src .venv/bin/python -m pytest tests/workbench -q` → 352 passed；启动 `run_workbench.py` → http://127.0.0.1:8080 正常监听。删除 4 个失效测试文件/函数：`test_board.py`、`test_content_project.py`、`test_canvas.py::test_canvas_persists_on_project`、`test_hotspot_handoff.py::test_agent_tool_creates_content_project`、`test_idea_persistence.py::test_project_bridge_creates_content_project`、`test_research_link.py` 的 3 个 service 集成测试

### 验收
- [x] `app.py` 不再挂载 content_project 路由
- [x] `content/board.py` 与 `content_project_routes.py` 不存在
- [x] `src/` 内无 `import Project` / `from content.board` 残留
- [x] pytest 通过（352 passed）；工作台能启动

### 执行调整记录（vs 原计划）
原计划设想「删 service.py 纯项目 CRUD + `content_project_id` 改 `topic_key`」「删 `Project` 模型」。实际代码核对发现偏差：
1. **无 `Project` 类**，只有 `normalize_project` 函数，被 cloud/store_local 调用 → 改桩而非删函数。
2. **service.py 被 6 处主线模块依赖**（canvas_routes/card_routes/idea_engine/project_bridge/handoff_service/research_link/automations），它们的改造在 Step 4b。若直接删 service 函数，这些模块立即崩，违反「期间主线不受影响」承诺 → 采用「激进删除 + 临时桩」方案：函数体改桩返回空结构，切断 project 数据流，调用方拿到空但不崩，功能短期降级。
3. **`content_project_id` 主要在前端**（33 处），后端用的是 `project_id`。后端参数语义迁移推迟到 Step 3 前端改耦合点时连带处理。
4. board.py 的看板函数（group/filter/sort/board_card/lane_move 等）只被 content_project_routes 引用，删 routes 后即孤儿，随 board.py 一起删；`BOARD_STATUSES`/`project_lane` 被 models.py 引用，通过 normalize_project 改桩内联消解。

### 风险
- 中。前端 33 处 `content_project_id` 在 Step 2 后会调用失败——预期，Step 3 集中修。期间项目相关功能不可用（service 桩返回空），Agent / 短视频 / 卡片 / Know-How 主线不受影响。Step 2-3 连续执行。Step 4b 改造 6 处调用方时彻底重写为 `topic_key` 枢纽。

---

## Step 3: 前端改耦合点（高风险，需逐处确认）

**目标：** 33 处 `content_project_id` 改为 `topic_key`，物理删除 content_project_routes 文件 + project_board.js。

### 任务

- [x] 3.1 grep [index.html](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html) 全部 `content_project_id`（实际 17 处，非文档原估 33 处），用 `replace_all` 批量改：`content_project_id` → `topic_key`、`setContentProjectId` → `setTopicKey`、`state.contentProjectId` → `state.topicKey`
- [x] 3.2 grep [cards_workshop.js](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/cards_workshop.js)（6 处），同样 `replace_all`：`content_project_id` → `topic_key`、`setContentProjectId` → `setTopicKey`、`getContentProjectId` → `getTopicKey`、`contentProjectId` → `topicKey`。`video_workshop.js` 无引用
- [x] 3.3 删除 [project_board.js](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/project_board.js)（`git rm`）
- [x] 3.4 删除 `<script src="/static/project_board.js?v=pj-board-1"></script>` 引用
- [x] 3.5 [content_project_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/content_project_routes.py) 已在 Step 2 删除；后端 API 层兼容改：[handoff_service.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/tools/handoff_service.py) `out["content_project_id"]` → `out["topic_key"]`；[video_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/video_routes.py) / [card_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/card_routes.py) 兼容读 `body.get("topic_key") or body.get("content_project_id")`；[canvas_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/canvas_routes.py) 响应字段改 `topic_key`；[research_link.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/content/research_link.py) 参数名 `content_project_id` → `topic_key`（import 别名 `derive_topic_key` 避免遮蔽）
- [x] 3.6 冒烟验证：`pytest tests/workbench` → 352 passed；启动 18082 端口 + curl 验证 `/api/auth/register` 200 + `/api/video/projects` 创建 200（完整冒烟脚本需调 LLM 耗时长，核心 API 已验证不 500）
- [ ] 3.7 人工验证黄金路径：选题 → Chat 制作 → L0 → L1 → 下载，全程无 content_project 报错（留给用户 UI 联调时验证）

### 验收
- [x] `index.html` grep `content_project_id` / `setContentProjectId` / `contentProjectId` 计数 = 0
- [x] `cards_workshop.js` 无 `setContentProjectId` / `getContentProjectId`
- [x] `project_board.js` 与 `content_project_routes.py` 已删
- [x] pytest 352 passed；核心 API curl 200
- [ ] 黄金路径人工走通（留 UI 联调）

### 执行调整记录（vs 原计划）
1. **实际 23 处非 33 处**：index.html 17 处 + cards_workshop.js 6 处 = 前端 23 处，后端另有 14 处。文档原估 33 偏高。
2. **后端一并改**：原计划只改前端，实际发现后端 API 层（video_routes/card_routes/canvas_routes/research_link/handoff_service）也读写字段名。为让前端发 `topic_key` 后端能读到，后端 API 层加兼容读 `body.get("topic_key") or body.get("content_project_id")`；handoff_service 输出字段和 canvas_routes 响应字段直接改名 `topic_key`。
3. **参数名遮蔽 bug**：research_link.py 参数改 `topic_key` 后遮蔽了 `from knowledge.topic_key import topic_key` 函数，报 `TypeError: 'str' object is not callable`。改 import 别名 `derive_topic_key` 解决。
4. **删 2 个失效测试**：`test_workbench_static.py::test_project_board_module_and_controls`（断言 project_board.js 存在）删除，其 canvas 断言保留为独立函数。
5. **冒烟脚本未完整跑**：smoke_video_workshop/chat_to_video/artifact_plan 需调 LLM 生成脚本，单次耗时超 3 分钟。改用 curl 快速验证核心 API（注册 200 + 创建视频项目 200），确认改名不引入 500。完整冒烟留 UI 联调时跑。

### 风险
- 高（已控制）。23 处前端改动用 `replace_all` 批量改 + grep 清零验证；后端 API 层兼容读两字段名避免破坏；`setTopicKey` 状态机入口改名后 cards_workshop 内部 `state.topicKey` 一致性已验证（pytest 352 passed）。`state.contentProject`（项目对象）保留不改，因它是对象非 id，不在 grep 范围，Step 4b 重写时再处理。

---

## Step 4a: 主侧栏骨架 + 设置弹窗 + 顶栏删除（结构层）

**目标：** 建立统一主侧栏替代顶栏 mode 按钮和各视图独立 `<aside class="rail">`。侧栏底部放账号+设置两图标。配置类功能统一进设置弹窗分 Tab。顶栏完全删除。此 step 只做结构骨架，上下文区先留空壳，逐 mode 填充在 Step 4b。

### 任务

**主侧栏骨架：**
- [x] 4a.1 在 [index.html](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html) `<body>` 顶部插入 `<aside id="appRail">`：brand + search + nav(5 mode) + context(占位) + footer(👤⚙) + collapse + account popover + drawer backdrop
- [x] 4a.2 新增 CSS：`.rail`/`.rail--expanded`(240px)/`.rail--collapsed`(56px，隐藏 logo/search/context，nav 只图标)/`.rail-nav`/`.rail-context`/`.rail-footer`/`.rail-icon-btn`/`.rail-collapse`/`.rail-account-popover`/`.rail-drawer-backdrop` + 暗色适配
- [x] 4a.3 `.rail-context` CSS `flex: 1; overflow-y: auto`，预留 mode 容器 hook
- [x] 4a.4 写 JS `setRailContext(mode)`：清空 `#railContext`，按 mode 渲染占位文案（agent/video/card/canvas/knowhow 各不同）
- [x] 4a.5 改 `setMode`：末尾调 `setRailContext(mode)`
- [x] 4a.6 `#railNav button` 点击 → `setMode(data-mode)`；active 高亮（DOMContentLoaded 内绑）
- [x] 4a.7 `#railCollapseBtn` 点击 → 切 expanded/collapsed，存 localStorage `wb_rail_collapsed`；恢复时读 localStorage
- [x] 4a.8 移动端：`< 767px` 时 `.rail` fixed 抽屉 transform translateX(-100%)，`body.rail-drawer-open` 时显示；`#mobileMenuFab`（桌面隐藏）点击唤出；`#railDrawerBackdrop` 点击关闭

**设置弹窗（统一配置中心）：**
- [x] 4a.9 在 `index.html` `</script>` 后、`</body>` 前插入 `<div class="settings-modal" id="settingsModal" hidden>`：backdrop + shell + head(设置+×) + body(tabs nav + tab-content)
- [x] 4a.10 新增 CSS：`.settings-modal`(fixed inset 0 flex center)/`.settings-modal-shell`(720px max 80vh)/`.settings-tabs`(左竖排 140px)/`.settings-tab-content`(flex 1 overflow-y auto) + 暗色适配
- [x] 4a.11 写 JS `openSettings(tab='llm')`：`modal.hidden=false` + `renderSettingsTab(tab)` + 绑 ESC 关闭
- [x] 4a.12 写 JS `renderSettingsTab(tab)`：切 active Tab + 调对应 `renderXxxTab(c)`，try-catch 容错
- [x] 4a.13 `renderLlmTab(c)`：把现有 `#accountDlg .plat-dlg-body` 整段 append 到容器（不克隆，保持 id 唯一）+ 调 `refreshLlmSettings()` + 保存按钮绑 `saveLlmSettingsFromTab`
- [x] 4a.14 `renderAccountsTab(c)`：渲染"打开发布账号面板"按钮，点击触发原 `accountOpenPlat` 面板（原 globalPlatDlg 保留）
- [x] 4a.15 `renderConnectorsTab(c)`：async 调 `/api/connectors`，用 `renderConnectorsInline(rows)` 生成 HTML（复用原 renderConnectorsPanel 逻辑）+ `wireConnectorsHandlers(c)` 绑 patch
- [x] 4a.16 `renderAutomationsTab(c)`：async 调 `/api/automations`，用 `renderAutomationsInline(recipes,runs)` + `wireAutomationsHandlers(c)` 绑 patch/run
- [x] 4a.17 `renderAppearanceTab(c)`：亮/暗单选，onchange 设 `data-theme` + localStorage `wb_theme`
- [x] 4a.18 `renderAboutTab(c)`：版本信息 + InsForge 控制台链接
- [x] 4a.19 `#settingsTabs button` 点击 → `renderSettingsTab(tab)`（DOMContentLoaded 内绑）
- [x] 4a.20 `#settingsCloseBtn`/`#settingsBackdrop` 点击 → `closeSettings()`（`modal.hidden=true` + 解绑 ESC）

**顶栏完全删除 + 账号入口：**
- [x] 4a.21 删除整个 `<header>` 元素（logo/modes/contentProjectChip/themeToggle/llmChipBtn/globalConnectorsBtn/globalAutomationsBtn/accountMenuBtn/accountMenu 全删）
- [x] 4a.22 同 4a.21（元素随 header 一起删）
- [x] 4a.23 `#railAccountBtn` 点击 → `#railAccountPopover` 显隐（含用户信息 `#rapUserMeta` + 登录/切换账号 `#rapLoginBtn` → `showLogin(true)` + 登出 `#logoutBtn2` → `doLogout()`）；`syncRailPopoverPos()` 按折叠态调 left；点外部关闭
- [x] 4a.24 `#railSettingsBtn` 点击 → `openSettings('llm')`
- [x] 4a.25 顶栏元素已删，原 handler 块（`if ($(id))` 守护）自然失效不崩；功能入口在 `#railSettingsBtn`（设置弹窗）和 `#railAccountBtn`（popover）

**布局调整：**
- [x] 4a.26 `body` CSS 改 `display: flex; flex-direction: row`；`#app` 改 `flex: 1; min-width: 0`；`#appRail` flex-shrink 0（CSS 已含）
- [x] 4a.27 各 `section.view` 显隐逻辑保持，未包 `<main id="appMain">`（`#app` 已是 flex column 容器，包一层冗余，省略）

### 验收
- [x] 无顶栏（curl `<header>` 计数=0），主侧栏可见，5 个 mode 按钮可点切换
- [x] 侧栏底部两图标（👤账号 / ⚙设置）可点
- [x] 账号 popover（用户信息 + 登录/切换账号 + 登出）
- [x] 设置弹窗 6 Tab 可切（JS 函数全嵌入验证）
- [x] 各 Tab 渲染函数已实现（llm/accounts/connectors/automations/appearance/about）
- [x] 原顶栏功能入口：模型→设置 llm Tab；连接器/自动化→设置对应 Tab；主题→设置 appearance Tab；InsForge→设置 about Tab；图鉴→knowhow mode（atlas 仍可通过 setMode('atlas') 进，Step 4b 整合为 asset）
- [x] 折叠/展开可用，状态持久化 localStorage
- [x] 移动端抽屉（`#mobileMenuFab` + `body.rail-drawer-open` + backdrop）
- [x] 切 mode 时 `#railContext` 占位文案变化（setRailContext 在 setMode 末尾调用）
- [x] pytest 352 passed；curl 确认 5 新元素在（appRail/settingsModal/railNav/railAccountBtn/railSettingsBtn）

### 执行调整记录（vs 原计划）
1. **不克隆 LLM 面板**：原设想克隆 `#accountDlg .plat-dlg-body` 到 Tab 容器，但克隆会导致 id 重复（`refreshLlmSettings` 按 id 查找）。改为直接 `appendChild(body)` 移动原节点，保持 id 唯一。代价：原 `#accountDlg` dialog 变空，但已无入口打开它（顶栏删），不影响。
2. **`#appMain` 容器省略**：原 4a.27 要求包 `<main id="appMain">`，但 `#app` 已是 flex column 容器承载所有 view，再包一层冗余。省略，view 显隐逻辑不变。
3. **`mobileMenuBtn` 改 `mobileMenuFab`**：顶栏删后原 `#mobileMenuBtn` 不存在，改用 `#mobileMenuFab`（body 顶部 FAB，< 768px 显示）唤出 rail 抽屉。原 agent 内 rail 的移动端覆盖逻辑保留（`mobileMenuBtn.id !== "mobileMenuFab"` 守护，不会重复绑）。
4. **图鉴入口**：原 `#accountOpenAtlas` 已删，atlas mode 仍可通过 `setMode('atlas')` 进（URL 参数 / Know-How 整合在 Step 4b）。
5. **登录入口**：原 `accountDlg` 含登录表单（`#loginEmail`/`#loginPassword` 在独立 `#login` div，不在 accountDlg 内），登录走 `#login` div + `showLogin(true)`。popover 的"登录/切换账号"调 `showLogin(true)` 复用，不重复表单。
6. **诊断告警**：IDE 报 Line 5531 等正则解析错误是 pre-existing（Step 3 已确认），非本次引入；HTML 结构诊断全绿。

### 风险
- 中（已控制）。结构改动大但 pytest 352 passed 证明未崩业务。关键风险在 `renderLlmTab` 移动原 `#accountDlg .plat-dlg-body` 节点——若用户先开设置 llm Tab 再点其他地方，节点可能丢失。当前 `renderLlmTab` 每次都 append 同一节点，重复调用安全（节点移动非克隆）。UI 联调时需验证：开设置 → 切 llm Tab → 改模型 → 保存 → 关设置 → 重开，模型配置是否持久。

---

## Step 4b: Know-How 重写 + Skill 承载 + 搜索弹窗 + rail 平移（合并原 4b+5）

**目标：** 一次性完整重写 Know-How 视图为单层内容流（含 skill 卡片 + workflow 提取），承载 skill 统一管理 + 经验提取新功能；各视图内部 rail 平移到主侧栏上下文区；新增全局搜索弹窗（跨 Know-How 全库 + Agent 会话）。合并原 Step 4b 和 Step 5，避免 Know-How UI 结构改动后 Step 5 找不到容器的契约断裂。

**执行策略：** 任务分 7 组（A-G），按组 commit。A 组后端前置是 C/D 组的硬依赖，必须先完成；B 组与其他组无耦合可并行；C/D 组都改 Know-How view 需连续做；E/F 独立可后做。

### 任务

**A. 后端前置（Know-How 内容流 + 搜索 + Skill 承载的 API 依赖）：**
- [x] 4b.A1 在 [topic_hub_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/topic_hub_routes.py) 新增 `GET /api/knowhow/stream?topics=&types=&q=&limit=50`：跨表聚合 wb_topic_notes + wb_workflow_records + wb_topic_assets，按 updated_at 倒序，支持 topics/types 多选过滤 + q 全文过滤。这是 C 组内容流渲染的硬依赖
- [x] 4b.A2 在 [topic_hub_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/topic_hub_routes.py) 新增 `GET /api/knowhow/search?q=&limit=20`：跨 notes+workflows+assets LIKE 搜索，返回 {type, id, title, topic_key, updated_at} 列表。供 E 组搜索弹窗调用
- [x] 4b.A3 在 [sessions.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/sessions.py) 新增 `GET /api/sessions/search?q=&limit=10`：搜 wb_sessions.title 字段（一期只搜标题，消息内容搜索留二期），返回 {id, title, updated_at} 列表
- [x] 4b.A4 在 [schema/workbench.sql](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/schema/workbench.sql) 新增表：
  ```sql
  CREATE TABLE wb_topic_skills (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic_key TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    when_to_use TEXT,
    body TEXT NOT NULL,
    source_workflows JSONB DEFAULT '[]',
    skill_type TEXT DEFAULT 'experience',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
  );
  ```
- [x] 4b.A5 创建 [knowledge/skills.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/knowledge/skills.py)：
  - `list_preset_skills()` → 复用 `SkillLoader` 从 `skills/` 目录读
  - `list_experience_skills(topic_key, user_id)` → 从 `wb_topic_skills` 读
  - `create_experience_skill(...)` → 写入 `wb_topic_skills`
  - `extract_skills_from_workflows(topic_key)` → 取 ≥3 条 workflow records，调 LLM 抽象 `when_to_use + body`，**返回建议不直接写库**
  - `confirm_extracted_skill(...)` → 用户确认后写库
- [x] 4b.A6 在 [topic_hub_routes.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/topic_hub_routes.py) 新增 skills 路由：
  - `GET /api/knowhow/{key}/skills` → 合并返回预置 + 经验 skill
  - `POST /api/knowhow/{key}/skills` → 创建经验 skill
  - `PATCH /api/knowhow/skills/{id}` → 编辑/启停
  - `DELETE /api/knowhow/skills/{id}`
  - `POST /api/knowhow/{key}/extract-skills` → 触发提取，返回建议
  - `POST /api/knowhow/skills/{id}/confirm` → 确认建议写入

**B. Agent/短视频/卡片/画布 上下文区平移（各视图内部 rail → 主侧栏上下文区）：**

**Agent 上下文区：**
- [x] 4b.1 `setRailContext('agent')` 渲染：会话列表 + 新对话按钮（从原 `aside.rail` 的 sessionList + newSessionBtn 平移）
- [x] 4b.2 删除 `<section id="viewAgent">` 内的 `<aside class="rail">`（2190 行起）
- [x] 4b.3 保留 `<aside class="idea-sidebar" id="ideaSidebar">`（2257 行）——这是 Agent 的右侧抽屉（Idea 引擎），不是左 rail，性质不同，保留。**已核实 CSS**（[index.html:622-626](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html#L622-L626)）`position: fixed; right: 0` 相对视口浮动，删 viewAgent 内部 rail 不影响其定位
- [x] 4b.4 调整 `#viewAgent .agent-layout` CSS：从 `grid-template-columns: var(--rail-w) 1fr` 改为 `1fr`（无左 rail），idea-sidebar 仍是右侧抽屉浮动

**短视频上下文区：**
- [x] 4b.5 `setRailContext('video')` 渲染：项目列表 + 新建按钮（从原 `aside.rail` 的 projectList + newVideoBtn 平移）
- [x] 4b.6 删除 `<section id="viewVideo">` 内的 `<aside class="rail">`（2320 行起）
- [x] 4b.7 保留短视频工坊内部的 `.side` 右侧面板（参数面板性质不同，保留）

**卡片上下文区：**
- [x] 4b.8 `setRailContext('card')` 渲染：分类选择 + 主题输入 + 期号输入 + 操作按钮（从原 `aside.rail` 的 kc-section 表单**完整平移**，这是编辑参数不是导航）。**state 持久化**：定义全局 `railContextState = { card: {category, topic, issue}, video: {lastProjectId}, agent: {lastSessionId}, canvas: {lastBoardId} }`，`setRailContext('card')` 渲染时从 `railContextState.card` 回填 input 值；input `change` 事件写入 `railContextState.card`，避免切 mode 再切回要重填
- [x] 4b.9 删除 `<section id="viewCard">` 内的 `<aside class="rail">`（2601 行起）
- [x] 4b.10 卡片编辑器的右侧 `.side`（预览/导出）保留

**画布上下文区：**
- [x] 4b.11 `setRailContext('canvas')` 渲染：画布列表 + 新建画布（从原 `aside.canvas-rail` 的 canvasBoardList 平移）
- [x] 4b.12 删除 `<section id="viewCanvas">` 内的 `<aside class="rail canvas-rail">`（2782 行起）

**C. Know-How 上下文区 + 主区域单层重写：**
- [x] 4b.13 `setRailContext('knowhow')` 渲染：话题筛选（多选）+ 类型筛选（多选）+ 新话题按钮（从原 `aside.knowhow-rail` 平移话题列表，类型筛选新增）
- [x] 4b.14 删除 `<section id="viewKnowhow">` 内的 `<aside class="knowhow-rail">`（2875 行起）和 `.kh-tabs`（原 Tab 栏，8 个 Tab：笔记/工作流/内容资产/Demo/问答KB/自测/知识图谱/AI导师）。**5 个边缘 Tab 按下方 4b.40-4b.44 处理去向，不可直接删功能逻辑**
- [x] 4b.15 重写 `viewKnowhow` 主区域结构为：顶部 toolbar（标题 + 搜索框 + 新笔记按钮）+ 内容流容器 `<div class="kh-stream" id="khStream">`
- [x] 4b.16 新增 CSS：`.kh-stream` / `.kh-card` / `.kh-card--note|workflow|skill|asset|atlas|kb` 各类型变体
- [x] 4b.17 写 JS `renderKnowhowStream(topicFilter, typeFilter, query)`：调 A 组已建的 `/api/knowhow/stream` 返回混合内容列表（types 含 note/workflow/asset/skill/atlas/kb_result），按时间倒序渲染卡片
- [x] 4b.18 主侧栏话题/类型筛选变化 → debounce 200ms → 重渲染 `#khStream`
- [x] 4b.19 顶部搜索框 `input` debounce 300ms → 重渲染流（用 `/stream?q=`）；回车追加 KB 检索（调现有 `/api/knowhow/kb`，[index.html:714](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/api/topic_hub_routes.py#L714)），结果带 🤖 标记作为 `kb_result` 类型卡片插入流顶。**原"问答KB"Tab 功能并入此处，不再作为独立 Tab**
- [x] 4b.20 人口图鉴卡：渲染特殊 asset 卡片，点击展开内嵌 iframe（懒加载，展开时才设 src）
- [x] 4b.21 Skill 卡占位：预置 skill 🔒 + 启停开关（D 组接真数据）；经验 skill + 编辑按钮（D 组接真数据，先 hidden）
- [x] 4b.22 工作流卡：「⚙ 提取为 Skill」按钮（D 组接真数据，先 hidden，workflow ≥3 时高亮显示）

**C2. 5 个边缘 Tab 去向处理（接 4b.14，按"知识 vs 操作"分类决策）：**
- [x] 4b.40 **Demo Tab → 删除**：[index.html:4198-4205](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html#L4198-L4205) 的 `runKhDemo()` 代码运行功能与知识库定位不符，删除 data-khtab="demos" 按钮 + `runKhDemo` 函数 + 相关 DOM
- [x] 4b.41 **问答KB Tab → 并入流顶搜索框**：已在 4b.19 处理。回车触发 KB 检索，结果作为 `kb_result` 卡片插入流顶（带 🤖 标记）。删除 data-khtab="kb" 按钮 + `queryKhKb` 函数原 Tab 渲染，改造为流顶搜索框回车 handler
- [x] 4b.42 **自测 Tab → 删除**：[index.html:4216-4224](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html#L4216-L4224) 的 `generateKhQuiz()` 是低频学习工具，非知识本身。删除 data-khtab="quiz" 按钮 + `generateKhQuiz` 函数
- [x] 4b.43 **知识图谱 Tab → 改为 asset 卡片**：[index.html:4225-4236](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html#L4225-L4236) 的 `renderKhGraph()` 保留为内容流中的特殊 asset 卡片（点击展开画布），不作为独立 Tab。改造 `renderKhGraph` 接受容器参数，在 asset 卡片展开时调用
- [x] 4b.44 **AI导师 Tab → 删除，Agent mode 替代**：[index.html:4237-4247](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html#L4237-L4247) 的 `sendKhTutorMessage()` 与 Agent mode 功能重复。删除 data-khtab="tutor" 按钮 + `sendKhTutorMessage` 函数。替代路径：Agent mode 对话时若设置 topic_key 上下文，自动加载该 topic 的笔记作为 prompt 上下文（与 F 组 4b.38 经验 skill 注入同机制）

**D. Skill 承载 UI（接 C 组的 skill 卡占位，连真数据 + 提取流程）：**
- [x] 4b.28 在 viewKnowhow 内容流中渲染 skill 卡片真实数据：预置 skill 从 `/api/knowhow/{key}/skills` 取 `skill_type=preset_ref`，复用 `panelSkills` 开关逻辑；经验 skill 列表 + 编辑/删除按钮
- [x] 4b.29 skill 卡内联编辑：点 skill 卡 → 展开编辑表单（when_to_use / body 字段），调 `PATCH /api/knowhow/skills/{id}` 保存
- [x] 4b.30 「⚙ 提取 Skill」按钮接真：调 `POST /api/knowhow/{key}/extract-skills` → 弹窗展示建议（when_to_use + body）→ 用户确认 → 调 `POST /api/knowhow/skills/{id}/confirm` 写入
- [x] 4b.31 workflow 类型卡片流顶部加提示横幅：当某 topic 下 workflow ≥3 条时显示"已有 N 条工作流记录，可提取经验 Skill"，高亮提取按钮

**E. 全局搜索弹窗（跨 Know-How 全库 + Agent 会话）：**
- [x] 4b.32 在 `index.html` 末尾插入搜索弹窗骨架：
  ```html
  <dialog id="globalSearchModal" class="search-modal">
    <div class="search-modal-shell">
      <input type="text" id="globalSearchInput" placeholder="搜索 Know-How 与会话…" autocomplete="off">
      <div class="search-results" id="globalSearchResults">
        <!-- 空查询显示最近话题 + 最近笔记 -->
      </div>
    </div>
  </dialog>
  ```
- [x] 4b.33 新增 CSS：`.search-modal`/`.search-modal-shell`/`.search-results`/`.search-result-item`。dialog 居中 max-width 640px，结果项左侧 icon + 标题 + topic 标签 + 时间
- [x] 4b.34 写 JS `openGlobalSearch()`：显示 dialog + autofocus 输入框 + 渲染空查询快捷入口（最近话题 + 最近笔记）。**数据来源用 localStorage**：键 `kh:recent` 存最近 5 条 `{type, id, title, topic_key, ts}`，点击搜索结果或浏览笔记/话题时写入（更新 ts 排序），无需后端接口
- [x] 4b.35 写 JS `runGlobalSearch(q)`：debounce 250ms，并发调 `/api/knowhow/search?q=` + `/api/sessions/search?q=`，合并结果按相关度排序渲染
- [x] 4b.36 键盘导航：↑↓ 选择结果项，Enter 跳转，Esc 关闭；全局 `Cmd/Ctrl+K` 唤出（已核实 [index.html:10508](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/workbench/index.html#L10508) 的 meta handler 未占用 K）
- [x] 4b.37 跳转逻辑：点笔记/工作流/资产 → 切 Know-How mode + 应用 topic 筛选 + 滚动到该卡片；点会话 → 切 Agent mode + load 该会话。**异步顺序**：先 `setMode('knowhow')` + `setRailContext('knowhow')` 应用 topic 筛选，等 `renderKnowhowStream` 渲染完（await fetch 完成 + DOM 写入），再 `scrollIntoView` 到目标卡片（用 `data-item-id` 定位）。会话跳转同理 await session load 完

**F. Agent prompt 注入经验 skill：**
- [x] 4b.38 在 [agent/mode.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/agent/mode.py) 修改 prompt 组装：现有 `select_skills_for_message` 只匹配预置 skill；新增若当前对话有 `topic_key` 上下文，从 `wb_topic_skills` 取该 topic 下 enabled 的经验 skill，与预置 skill 合并注入 `prompt_block_for_skills`（走现有长度截断逻辑）

**G. 清理死代码 + setMode 清理：**
- [x] 4b.23 删除 `#viewBoard` section（2723 行起）+ `.board-*` CSS + `board-card` JS + `project_board.js` 文件 + script 标签
- [x] 4b.24 删除 `#viewLearn` section（3342 行起）+ `learn.js` 文件 + script 标签
- [x] 4b.25 删除 `#viewAtlas` section（2858 行起）+ `.atlas-toolbar` CSS（Know-How 早期占位拷贝，重写时换成自有样式）
- [x] 4b.26 删除 `#viewWorkflow` section（2777 行起）
- [x] 4b.27 在 `setMode` 删除 `board`/`learn`/`atlas`/`workflow` 分支；更新 `labels`/`modeMark` 映射；grep `switchMode('board'/'learn'/'atlas'/'workflow')` 调用点清理

### 验收
- [ ] 切到 Agent，侧栏下半显示最近会话，主区域是对话流（无内部左 rail）
- [ ] 切到 短视频，侧栏显示项目列表，主区域是工坊（无内部左 rail，右侧参数面板仍在）
- [ ] 切到 卡片，侧栏显示分类/主题/期号表单，主区域是编辑器（无内部左 rail，右侧预览仍在）
- [ ] 切到 画布，侧栏显示画布列表，主区域是画布（无内部左 rail）
- [ ] 切到 Know-How，侧栏显示话题/类型筛选，主区域是单层内容流（无 Tab，无内部左栏）
- [x] grep `viewBoard`/`viewLearn`/`viewAtlas`/`viewWorkflow` 在 index.html 计数 = 0
- [x] `learn.js`/`project_board.js` 文件已删
- [ ] 5 个 mode 切换均正常，无 JS 报错
- [x] `wb_topic_skills` 表存在
- [x] `/api/knowhow/stream` + `/api/knowhow/search` + `/api/sessions/search` + 6 个 skills 路由可调
- [ ] Know-How 内容流显示 skill 卡片（预置 + 经验）
- [ ] 提取流程跑通（≥3 条 workflow → 建议 → 确认 → 写库）
- [ ] Agent 对话 prompt 含该 topic 下的经验 skill（用日志或 debug 验证）
- [ ] Cmd/Ctrl+K 唤出搜索弹窗，输入关键词返回 Know-How + 会话结果
- [ ] 搜索结果点击可跳转到对应 view + 滚动/加载

### 执行调整记录（vs 原计划）
- **rail 平移改 DOM 物理移动**：4b.1/4b.5/4b.8/4b.11 未按"删除视图内 aside.rail + 在 setRailContext 重新渲染"实现，改为 `setRailContext(mode)` 把各视图内部 rail 元素**物理 appendChild 到 `#railContext`**，切 mode 时归还原视图。保留原 DOM id 与事件绑定，避免重写 sessionList/projectList/canvasBoardList 渲染逻辑。4b.2/4b.6/4b.9/4b.12 的"删除视图内 aside.rail"改为"运行时借走"，CSS 加 `.rail-in-context` 适配。功能等价：切到某 mode 时 rail 出现在主侧栏上下文区，视图内无内部左 rail。
- **knowhow rail 未平移**：4b.13 改为在 `#railContext` 内直接渲染筛选器占位（话题/类型/搜索 toolbar 留在 viewKnowhow 主区域顶部，未拆到 rail），简化实现。
- **经验 skill 注入位置**：4b.38 计划写 `agent/mode.py`，实际落在 [agent/loop.py](file:///Users/zfl/projects/cn-social-agent/src/cn_social_agent/agent/loop.py) 的 `_experience_skills_block()`，在 prompt 组装阶段注入，效果等价。
- **wb_topic_skills 表 defaultValue 修正**：建表脚本中 `enabled` 列 `defaultValue` 原写 Python `True`（布尔），InsForge Tables API 要求字符串，改为 `"true"` 后建表成功（表已物理创建）。
- **learn 死代码延展清理**：4b.24 计划删 learn.js + script 标签，实际还清理了 index.html 中 3 处守护式调用（`__learnActivate`/`__learnSelectTopic`）、`detectLearnTopics()` 改为返回 null（停用 agent 话题气泡）、canvas「关联知识点」徽章删除、`.bubble-learn-*`/`.cv-learn-badge`/`.cv-learn-icon` 孤立 CSS 删除。
- **运行时验收延后**：验收中 mode 切换显示（645-649）/ 无 JS 报错（652）/ skill 卡片渲染（655）/ 提取流程跑通（656）/ prompt 含经验 skill（657）/ 搜索弹窗与跳转（658-659）均需运行时 UI 联调，与 Step 3.7 黄金路径同批留待用户 UI 联调时验证。静态可验项（grep=0、文件已删、表存在、路由已注册）已勾选。

### 风险
- 高（合并后任务量 39 项）。按 A→B→C→D→E→F→G 组顺序执行，每组独立 commit 降低风险。
- 各视图内部 rail 删除后，相关 JS（如 sessionList render、projectList render）的事件绑定要迁移到 setRailContext 渲染时重新绑定。务必 grep 每个被删 rail 内的 DOM id，确认其 JS handler 仍能找到新位置的元素。
- 卡片 rail 表单 state 持久化方案已定义（4b.8 全局 `railContextState` 对象），实现时务必让 input `change` 事件正确写入对应字段。
- A 组 `/api/knowhow/stream` 是 C 组内容流渲染的硬依赖，必须先完成；`/api/knowhow/search` + `/api/sessions/search` 是 E 组搜索弹窗硬依赖。
- 提取的 LLM prompt 设计是关键——建议质量决定 skill 可用性。先做最简版（让 LLM 总结 3 条 workflow 的共性 + 给出 when_to_use），跑几次真实数据后再迭代 prompt。经验 skill 注入 prompt 后可能过长，需做长度截断（与预置 skill 同走 `prompt_block_for_skills` 的现有逻辑）。
- 搜索弹窗的会话搜索一期只搜 title，若用户反馈需要消息内容搜索，二期补全文检索。

---

## 关键决策记录

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D1 | 唯一知识载体 | Know-How（取消 Content Project） | 避免两套载体并存导致上下文干扰 |
| D2 | Idea 引擎归属 | 合并为 Know-How 选题层 | 选题素材是知识库一部分，对外只一个入口 |
| D3 | 制作上下文挂载点 | `topic_key` | Know-How 唯一索引键 |
| D4 | 沉淀写入方式 | 创作过程自动写入 | 防止 Know-How 空置 |
| D5 | content_project 表 | Step 3 前保留只读过渡 | 避免前端引用悬空崩溃 |
| D6 | 文档处理 | 归档不删除 | 保留历史可追溯，仅移出顶层视线 |
| D7 | Skill 双层 | 预置(文件) + 经验(库) | 预置即真相不可改，经验可抽象可编辑 |
| D8 | 经验 skill 提取 | 需用户确认，不自动生效 | 防止噪音污染 prompt |
| D9 | UI 极简 | 主侧栏 + 单内容区 | 顶栏占垂直空间且不能显示上下文；左侧栏解决双栏问题，符合 AI 应用范式 |
| D10 | viewWorkflow 删除 | section + mode 按钮都删，工作流编排并入设置弹窗「自动化」Tab | 工作流编排非主线，不该占顶栏位 |
| D11 | viewAtlas 删除 section | 改为 Know-How 流里的 asset 卡片项；全屏入口放设置弹窗「关于」Tab | 图鉴是知识内容，不该是独立视图 |
| D12 | Know-How 去Tab化 | 单层内容流，话题/类型筛选合并到主侧栏上下文区 | 默认可读、降低切换成本、搜索为主入口 |
| D13 | 上下文区随 mode 自适应 | setRailContext(mode) 切换时整体替换侧栏下半内容 | 各 mode 的辅助内容性质不同（导航/参数），强统一会破坏体验 |
| D14 | 卡片 mode 上下文保留表单 | 分类/主题/期号作为输入表平平移，不强行改列表 | 表单是编辑参数不是选择项，统一要服从功能 |
| D15 | 各视图右侧面板保留 | 短视频/卡片/Canvas 的 `.side` 不并入主侧栏 | 右侧是编辑器属性面板，性质与左侧导航不同，混淆会破坏编辑流 |
| D16 | 配置统一进设置弹窗 | 模型/发布账号/连接器/自动化/主题/InsForge 全部进设置弹窗分 Tab，不再散落顶栏按钮 + 账号菜单重复项 | 按性质分类组织；配置低频不该占侧栏位；避免当前顶栏 4 按钮 + 账号 6 项的重复混乱 |
| D17 | 顶栏完全删除 | 不留极简顶栏，mode 在侧栏、配置在设置弹窗、hamburger 在侧栏顶部 | 顶栏只放 logo+ham 已无存在价值，留空顶栏占垂直空间反而割裂左右结构 |
| D18 | 侧栏底部只两图标 | 账号 + 设置两个图标，不是下拉菜单堆叠 | 账号只承载用户信息+登出，配置全在设置弹窗，避免在侧栏底部再堆一个 7 项下拉 |
| D19 | 设置弹窗复用而非重写 | 提取现有 openXxxPanel() 渲染逻辑为 renderXxxTab(container)，不重写业务 | 降风险保功能，只改容器不改逻辑 |
| D20 | 人口图鉴是内容非配置 | 作为 Know-How 内容流 asset 卡片，不进设置弹窗 | 图鉴是查看类内容，与模型/连接器等配置性质不同，进设置会混淆 |
| D21 | 合并 Step 4b+5 | 一次性完整重写 Know-How（含 skill 承载 + 搜索），不分两 Step | 避免 4b 改 Know-How 结构后 5 找不到 Tab 容器的契约断裂；任务分 A-G 组 commit 降低风险 |
| D22 | 搜索弹窗跨 Know-How + 会话 | 一期就纳入 Agent 会话搜索（搜 wb_sessions.title） | 搜索是全局入口，只搜知识库会割裂体验；会话标题搜索复杂度低先做，消息全文留二期 |
| D23 | `/stream` + `/search` 接口前置 | 作为 4b A 组后端前置任务，不延到独立 Step | `/stream` 是内容流硬依赖，`/search` 是搜索弹窗硬依赖，前置避免 mock 数据返工 |
| D24 | Know-How 5 个边缘 Tab 去向 | Demo/自测/AI导师删除；问答KB 并入流顶搜索框回车；知识图谱改 asset 卡片 | Know-How 是知识库不是工具箱；操作类功能（Demo 运行代码/Quiz 生成题目/Tutor 对话）非知识本身；Tutor 与 Agent mode 功能重复由 Agent + topic 上下文替代；KB 检索是搜索增强不独立成 Tab；图谱关联可视化是内容回归卡片 |
| D25 | 登录入口在账号 popover | 登录/切换账号放侧栏底部账号 popover，不放设置弹窗"模型与路由"Tab | 现有 accountDlg 含登录表单，提取为设置 Tab 时登录跑进"模型"Tab 会怪异；登录是账号操作不是配置，与登出并列在 popover |
| D26 | 搜索空查询用 localStorage | 键 `kh:recent` 存最近 5 条 {type, id, title, topic_key, ts}，点击时写入 | 避免新增后端"最近"接口；前端本地记录用户行为足够，无服务端状态 |

---

## 后续（本计划外，待数据驱动）

本计划只做"收敛 + 清理 + UI 重构 + Skill 承载"，不新增以下能力。等 Know-How 跑起来有真实使用数据后再决定：
- 制作过程 → Know-How 自动写入 research_notes / workflow records 的具体触发点（依赖各 workshop 的完成事件钩子）
- Know-How → 创作复用的更深 Agent 注入逻辑（当前只注入 skill，未来可注入历史 workflow 全量）
- Know-How Phase 2-4（双向链接 / 智能关联 / 相关话题推荐，原设计文档已规划）
- 经验 skill 跨 topic 复用机制（当前 skill 绑 topic，未来可做全局 skill 库）

**一句话：** 把容器唯一化、把噪音清干净、把 UI 二分收敛、把 skill 承载接通——四件事做完，Know-How 真正成为 Agent 的知识库；之后的能力扩展等真实数据驱动。
