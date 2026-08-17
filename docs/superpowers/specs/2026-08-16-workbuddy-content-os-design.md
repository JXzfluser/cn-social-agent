# WorkBuddy-Inspired Content OS Design

> Date: 2026-08-16  
> Status: Approved — **S1 Content Project implementing / landed** (2026-08-16)  
> Approach: Path 2 — **Project → Connectors → Automations**  
> Scope: Fuse WorkBuddy concepts (connectors / projects / automation) into cn-social-agent as a **content production OS**, not an office-work clone.
>
> Plan: [`docs/superpowers/plans/2026-08-16-content-project-s1.md`](../plans/2026-08-16-content-project-s1.md)

## 1. Goal

Borrow WorkBuddy’s three-layer skeleton and translate it for Chinese short-content production:

| WorkBuddy | This product |
|-----------|--------------|
| Connectors to office SaaS | **Content sources + distribution endpoints** |
| Project as work container | **Content Project** (one topic / one edition) |
| Scheduled / triggered automation | **Content pipelines** on that project |

North-star flow:

**选题进入 Content Project → 连接器供料 → Agent/工坊在同一项目里深采·成刊·做片 → 自动化跑重复步骤 → 质检通过后导出/发布。**

## 2. Product decisions (locked)

| Decision | Choice |
|----------|--------|
| Sequencing | S1 Project → S2 Connectors → S3 Automations |
| Do not build now | MCP marketplace, Experts persona store, generic Slack/Notion office connectors |
| Project is first-class | Agent / 知识卡片 / 口播 / 讲解演示 share one `content_project_id` |
| Existing video `project` | Becomes one **artifact** of a Content Project (not the only “project”) |
| Seed-evidence handoff (already landed) | Becomes the default “enter project” behavior; later an automation action |
| InsForge | Auth + store for Content Projects / connector creds / automation runs |

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Workbench UI                                           │
│  Agent │ Content Projects │ Connectors │ Automations    │
│  + track workshops (card / video / presentation)        │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│  Content Project (一等公民)                             │
│  topic · short_topic · category · research_notes        │
│  evidence_pack · quality · artifacts[]                  │
│  connectors_used · automation_runs                      │
└──────┬──────────────────────────────┬───────────────────┘
       ▼                              ▼
┌──────────────────┐        ┌─────────────────────────────┐
│  Connectors      │        │  Automations                │
│  ingest / publish│        │  trigger → actions on proj  │
└──────────────────┘        └─────────────────────────────┘
```

### 3.1 Content Project (S1)

Minimal schema (logical):

```json
{
  "id": "cp_…",
  "user_id": "…",
  "topic": "浏览器扩展合集：…",
  "short_topic": "浏览器扩展合集",
  "category": "product_explain",
  "source": { "kind": "hotspot|url|manual", "url": "", "title": "" },
  "research_notes": "…",
  "search_terms": ["浏览器扩展合集"],
  "evidence_pack": { "evidences": [], "count": 0 },
  "quality": { "items": [], "blockers": [] },
  "artifacts": {
    "journal_id": null,
    "video_id": null,
    "presentation_id": null
  },
  "status": "researching|composing|producing|done",
  "created_at": "…",
  "updated_at": "…"
}
```

Rules:

1. Hotspot / Agent handoff **creates or attaches** a Content Project (never drops `research_notes`).
2. Opening 知识卡片 / 口播 / 讲解 with a `content_project_id` preloads `short_topic`, notes, evidence.
3. Deep research / compose / video draft **write back** into the same project.
4. Topic assets view lists Content Projects (or links each topic_key → latest project).

### 3.2 Connectors (S2)

A connector is a named, switchable capability with auth + direction:

| id | direction | maps from today |
|----|-----------|-----------------|
| `hotspot_board` | ingest | hotspot engine (HN/GitHub/V2EX/…) |
| `web_fetch` | ingest | `fetch_url_text` / sogou scrape |
| `github` | ingest | `github_repo_insight` (optional OAuth later) |
| `weixin_publish` | publish | card platform publish |
| `toutiao_publish` | publish | card platform publish |
| `local_export` | publish | PNG / MP4 download |

UI: side panel “连接器” — enable/disable, show last sync / auth status.  
Every connector call records `{ connector_id, project_id, at, ok }` on the project.

### 3.3 Automations (S3)

Rule shape:

```json
{
  "id": "auto_…",
  "trigger": "cron|handoff|quality_pass",
  "actions": ["seed_research", "compose_journal", "export_images"],
  "scope": { "category": "product_explain", "connectors": ["hotspot_board"] },
  "enabled": true
}
```

v1 recipes (only after S1+S2):

1. **Daily hotspot candidates** → create draft Content Projects (no auto-publish).
2. **On handoff** → seed evidence (already mostly done) + open project.
3. **On journal quality_pass** → export images (optional notify later).

Hard gate: automations **must not** publish without explicit user confirmation in v1.

## 4. Phased delivery

### S1 — Content Project (first knife)

- Persist Content Projects (InsForge table or local+cloud mirror, same pattern as card history).
- API: create / get / list / patch / attach artifact.
- Wire: hotspot journal handoff, `propose_knowledge_cards`, card research/compose, video create — all accept/return `content_project_id`.
- UI: project rail or “当前项目” chip; workshops read/write project context.
- Success metric: Agent → 知识卡片 no longer feels like a blank workshop; notes + seeds land in one place.

### S2 — Connectors panel

- Registry + settings UI for ingest/publish connectors.
- Route existing tools through registry; project logs connector usage.
- Success metric: user can turn off a noisy source; publish channels show auth state clearly.

**Status (2026-08-16):** Landed — `content/connectors.py`, `/api/connectors`, header「连接器」面板；热点扫描尊重 `hotspot_sources_enabled`。

### S3 — Automations

- Cron + event triggers; run log; dry-run mode.
- Success metric: one daily “候选选题” list without manual hotspot scan; quality_pass can one-click export.

**Status (2026-08-16):** Landed — `content/automations.py`, `/api/automations` (+ run), header「自动化」面板；配方：每日热点候选 / 交接种子证据 / 成刊标记可导出。Hard gate：不自动发布。Cron 以「立即运行」+ last_run prefs 代替完整调度器。

### S3.5 — Knowledge Canvas（知识画布）

自由整理层：把「素材 → 结构」的思考过程留在项目里，而不是聊天记录里。

- 节点类型：便签 / 证据 / 钩子 / 结构 / 待验证 / 链接；拖拽、缩放、选中、配色、完成态。
- 两类画布：**独立画布**（`data/canvas_boards/` 本地落盘，可多份新建/重命名/删除）与**项目画布**（存在 Content Project 的 `canvas` 字段，跟随双写）。
- 连线：节点边界出发的三次曲线 + 可见箭头；双击线编辑标签或删除。
- 交互：应用内弹框（新建/重命名/删除/标签）、框选、⌘D 复制、⌘Z 撤销、适应内容、小地图导航、空白双击建便签、节点右键菜单。
- 模板：空白 / 选题漏斗 / 脚本结构 / SWOT；`GET /api/canvas/templates`、`POST /api/canvas/boards`（`template_id`）。
- AI 整理：`POST /api/canvas/organize`（选中节点；失败 422/503，不自动发布）。
- `导入素材` / `整理` / `导出 MD` / `交接到知识卡片` 保留。
- 硬闸不变：画布只产生素材与交接，不触碰发布。

**Status (2026-08-16):** Enhanced — 弹框、边界箭头、模板、小地图、AI 整理、撤销/缩放修复。

### S3.6 — Project Board（项目三栏看板）

主编台：把 Content Project 收成可视批次。

- 三栏：**候选 / 进行中 / 可导出**；已打回折叠区。
- 顶部搜索 / 分类 / 产物筛选 / 排序；卡片展示证据·画布·卡片·演示·视频进度点。
- 点击卡片打开右侧详情抽屉；可拖拽换栏（打回仍需理由弹框）。
- 「打开画布」进入对应项目画布。
- API：`GET /api/content-projects/board?q=&category=&artifact=&sort=`、`POST /api/content-projects/{id}/board`。

**Status (2026-08-16):** Enhanced — 筛选排序、进度标记、详情抽屉、拖拽换栏。

## 5. Out of scope (this design)

- MCP server marketplace / ToolSearch
- Experts / persona packages
- Generic office connectors (Slack, Notion, Gmail) as primary
- Multi-user team admin console
- Auto-publish to social platforms without human confirm

## 6. Relation to existing specs

- Builds on seed-evidence handoff (2026-08-16 cards topic work, not yet a separate spec file).
- Extends [insforge-agent-workbench](2026-07-26-insforge-agent-workbench-design.md) Phase 2 items (Schedules, webhooks) into **content-scoped** automations.
- Does not replace [knowledge-journal](2026-08-12-knowledge-journal-design.md) or [short-video-workshop](2026-07-26-short-video-workshop-design.md); those become artifact tracks under Content Project.
- Aligns with [hotspot-engine](2026-08-16-hotspot-engine-design.md) as the first ingest connector.

## 7. Open questions (resolve in S1 plan)

1. Persist Content Project in InsForge only vs dual-write local like card history?
2. Migrate existing video projects / journal history into Content Projects eagerly or lazily on open?
3. UI: new top-level mode “项目” vs persistent chip inside Agent / each workshop?
