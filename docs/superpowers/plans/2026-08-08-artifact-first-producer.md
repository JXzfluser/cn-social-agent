# Artifact-First Producer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把短视频项目做成「有 Plan、有交付物面板、失败可恢复」的长任务，提升产品档次到制片台，而不是聊天玩具。

**Architecture:** 以现有 `video project` + Chat 卡片为单一真相；新增轻量 `production_plan` 状态（由 project/scenes/job 推导，不必新表）；工坊主区改为交付物面板；Agent 侧按需注入 Skill + 澄清纪律。不引入 DeerFlow/LangGraph/沙箱。

**Tech Stack:** aiohttp workbench、`index.html` SPA、`video_routes` / `pipeline` / `agent/loop` / skills loader、InsForge 存项目（已有）。

**Spec:** [`docs/superpowers/specs/2026-08-08-artifact-first-producer-design.md`](../specs/2026-08-08-artifact-first-producer-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| [`src/cn_social_agent/video/plan.py`](../../src/cn_social_agent/video/plan.py) **(new)** | 从 project + scenes + job 推导 6 步 Plan |
| [`src/cn_social_agent/api/video_routes.py`](../../src/cn_social_agent/api/video_routes.py) | `GET/status` 与 project 详情附带 `production_plan`；失败动作文案 |
| [`src/cn_social_agent/workbench/index.html`](../../src/cn_social_agent/workbench/index.html) | Plan 条 UI、交付物面板、Chat 卡片同步 |
| [`src/cn_social_agent/agent/loop.py`](../../src/cn_social_agent/agent/loop.py) | Coach 缩短；Skill 按需拼装入口 |
| [`src/cn_social_agent/skills/loader.py`](../../src/cn_social_agent/skills/loader.py) | `select_skills_for_message(text) -> list[Skill]` |
| [`src/cn_social_agent/api/chat.py`](../../src/cn_social_agent/api/chat.py) | 调用按需 Skill，而不是全量 enabled body |
| [`config/default.yaml`](../../config/default.yaml) 或 env | `VIDEO_DEFAULT_ANGLE`、`L1_ENABLED` 等（可选本阶段） |
| [`scripts/smoke_artifact_plan.py`](../../scripts/smoke_artifact_plan.py) **(new)** | 黄金路径：创建→generate→plan steps→L0 status |
| [`tests/workbench/test_production_plan.py`](../../tests/workbench/test_production_plan.py) **(new)** | Plan 推导单测 |

---

## Phase P0 — Plan 条 + 交付物面板（3–5 天）

### Task 1: Plan 推导模块

**Files:**
- Create: `src/cn_social_agent/video/plan.py`
- Create: `tests/workbench/test_production_plan.py`

- [x] **Step 1:** 写失败测试：给定无 script 的 project → steps 1 pending；有 scenes → step 4 completed
- [x] **Step 2:** 实现 `build_production_plan(project, scenes, job=None) -> dict`：

```python
# steps ids: topic | angle | brief | script | l0 | l1
# each: {id, label, status: pending|active|done|failed, detail}
```

- [x] **Step 3:** 规则：`topic`←project.topic；`angle`←wbmeta.content_angle；`brief`←audience or scene_setting；`script`←len(scenes)>0；`l0`←status/delivery_level/output；`l1`←delivery_level==l1 and done
- [x] **Step 4:** 跑 pytest 该文件通过
- [ ] **Step 5:** Commit `feat(video): derive production plan from project state`

### Task 2: API 挂载 Plan

**Files:**
- Modify: `src/cn_social_agent/api/video_routes.py`（`get_project`、`status`、`from_session` 响应）

- [x] **Step 1:** 在 `get_project` / `status` JSON 增加 `production_plan`
- [x] **Step 2:** `from_session` 成功响应同样带上 plan（供 Chat 卡片）
- [x] **Step 3:** 手动 curl 一个已有项目，确认 6 步结构
- [ ] **Step 4:** Commit `feat(api): expose production_plan on video endpoints`

### Task 3: 工坊交付物面板 UI

**Files:**
- Modify: `src/cn_social_agent/workbench/index.html`

- [x] **Step 1:** 在 `#viewVideo` 主区（scriptCard 上方或替换杂乱 status）增加：
  - `#prodPlan`：横向 6 步（done/active/pending/failed）
  - `#artifactPanel`：三块——脚本 / 分镜草稿 / 成片（状态 + 主按钮）
- [x] **Step 2:** `openProject` / `pollStatus` 调用时 `renderProductionPlan(data.production_plan)` + `renderArtifacts(...)`
- [x] **Step 3:** 主按钮映射：无脚本→生成分镜；有脚本无 L0→生成分镜草稿；有 L0→升级成片 / 下载；失败→显示 fail_reason + 重试
- [x] **Step 4:** 保持右侧参数仅「类型 + 音色」（已简化，勿加回）
- [x] **Step 5:** 浏览器手测：新建→生成→Plan 步进→草稿按钮（API 验已有项目 `5/6`；新建遇 InsForge 超时，非 Plan 逻辑）
- [ ] **Step 6:** Commit `feat(ui): production plan bar and artifact panel`

### Task 4: Chat 卡片同步 Plan

**Files:**
- Modify: `src/cn_social_agent/workbench/index.html`（`appendVideoCard` / `pollVideoCard`）

- [x] **Step 1:** 视频卡片顶部显示精简 Plan（4 字标签或进度 `3/6`）
- [x] **Step 2:** 状态文案与交付物一致（草稿/成片/失败原因）
- [ ] **Step 3:** Commit `feat(ui): sync plan progress on chat video cards`

---

## Phase P1 — Skill 按需 + 澄清 + 失败恢复（3–5 天）

### Task 5: Skill 按需加载

**Files:**
- Modify: `src/cn_social_agent/skills/loader.py`
- Modify: `src/cn_social_agent/api/chat.py` 或 `agent/loop.py`（system prompt 组装处）

- [x] **Step 1:** 实现 `select_skills_for_message(skills, user_text) -> list[Skill]`：
  - URL → `short-video-researcher`
  - 热点|github|star → `github-star-growth-video`
  - 深度分析|规律|证据 → `deep-analysis-video`
  - 做片|短视频|口播 → `short-video-director`
  - 若无匹配：只注入 `short-video-director`（短）或不注入（二选一，默认注入 director）
- [x] **Step 2:** AgentLoop 拼 system 时用「选中 Skill」替代「全部 enabled Skill 全文」
- [x] **Step 3:** Skills 面板仍可开关；disabled 永不注入
- [x] **Step 4:** 手测：纯闲聊 system 更短；贴 URL 后含 researcher（单测覆盖）
- [ ] **Step 5:** Commit `feat(agent): load skills on demand by message triggers`

### Task 6: 澄清纪律（软闸门）

**Files:**
- Modify: `src/cn_social_agent/agent/loop.py`（VIDEO_COACH_PROMPT）
- Modify: `skills/short-video-researcher/SKILL.md`（已有则收紧）
- Optional: `tools/builtin.py` — `propose_short_video` 若缺 audience 且缺 scene_setting，返回 `ready:false` + hint（硬一点）

- [x] **Step 1:** Coach 写明：无受众且无场景时禁止 propose
- [x] **Step 2:** `propose_short_video` 增加校验：两者皆空 → `ok:true, ready:false, need:["audience|scene"]`（UI 不弹「可制作」或弹「还缺一项」）
- [x] **Step 3:** `appendSuggestCard`：仅 `ready!==false` 时显示主按钮
- [ ] **Step 4:** Commit `feat(agent): gate propose until audience or scene exists`

### Task 7: 失败恢复打磨

**Files:**
- Modify: `src/cn_social_agent/api/video_routes.py`（render job fail_reason 用 `_exc_text`）
- Modify: `src/cn_social_agent/workbench/index.html`（失败区三按钮）
- Verify: `src/cn_social_agent/video/agnes_client.py` URL 顶层读取（已修，加回归注释或小测）

- [x] **Step 1:** render/from-session 所有 `str(exc)` 改为 `_exc_text(exc)`
- [x] **Step 2:** 交付面板失败态：`重试草稿` / `重试成片` / `重试失败镜`（若有 scene 建议）
- [x] **Step 3:** 质检未过文案固定：「未通过成片质检，仍是草稿」+ reasons
- [ ] **Step 4:** Commit `fix(video): explainable failures and retry actions`

---

## Phase P2 — 埋点 + 黄金路径 CI（约 1 周）

### Task 8: 漏斗事件（最小）

**Files:**
- Modify: `video/store.py` 或 wbmeta：记录时间戳字段  
  `t_created` / `t_script_ready` / `t_l0_ready` / `t_l1_ready` / `t_downloaded`（能写进 meta 即可，不强求分析库）

- [x] **Step 1:** generate 成功写 `t_script_ready`
- [x] **Step 2:** L0 render done 写 `t_l0_ready`；L1 done 写 `t_l1_ready`
- [x] **Step 3:** download 接口写 `t_downloaded`（首次）
- [x] **Step 4:** `GET /api/video/projects` 列表可带这些字段（便于以后报表）
- [ ] **Step 5:** Commit `feat(video): funnel timestamps on project meta`（仓库无 `.git`）

### Task 9: Smoke / CI

**Files:**
- Create: `scripts/smoke_artifact_plan.py`
- Modify: `README.md`（一行如何跑）

- [x] **Step 1:** Smoke：login → create → generate → assert production_plan step script=done → render L0 → poll done → assert l0 step done
- [x] **Step 2:** README 增加命令
- [x] **Step 3:** 若有 CI workflow，加一步（无则注明手动）
- [ ] **Step 4:** Commit `test: smoke artifact-first golden path`（仓库无 `.git`）

---

## 验收清单（整规划出口）

- [x] 工坊打开任一项目：可见 Plan 6 步 + 脚本/草稿/成片三产物
- [x] Chat 做片卡片与项目 Plan 进度一致
- [x] 右侧参数仍只有类型 + 音色
- [x] 贴 URL：researcher 注入；缺受众/场景不能直接「可制作」
- [x] L1 失败：有可读原因 + 重试入口
- [x] `smoke_artifact_plan.py` 本地通过

---

## 建议执行顺序

1. P0 Task 1–4（先看得见制片台）  
2. P1 Task 6–7（信任）再 Task 5（按需 Skill）  
3. P2 埋点与 smoke  

**第一个可演示里程碑：** P0 完成即可对外说「从聊天玩具变成交片台」。
