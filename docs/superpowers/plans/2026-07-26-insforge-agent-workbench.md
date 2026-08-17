# InsForge Agent Workbench Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 InsForge-first Agent 工作台：瘦内核 API + 单页 UI，并移除未接入 InsForge 的冗余模块。

**Architecture:** 新入口 `run_workbench.py` 只加载 `cn_social_agent.api`；身份/数据/文件/模型走 InsForge SDK；旧运营与平台代码移入 `_legacy/` 并不再被启动路径引用。

**Tech Stack:** Python 3.10+、aiohttp、现有 `cn_social_agent.insforge` SDK、静态 HTML/JS + SSE

**Spec:** `docs/superpowers/specs/2026-07-26-insforge-agent-workbench-design.md`

---

## File map

| Path | Responsibility |
|------|----------------|
| `src/cn_social_agent/tools/registry.py` | Tool 注册与执行 |
| `src/cn_social_agent/tools/builtin.py` | `now` / `http_get` |
| `src/cn_social_agent/skills/loader.py` | SKILL.md 扫描与启停绑定 |
| `src/cn_social_agent/agent/loop.py` | 对话循环 + tool calling |
| `src/cn_social_agent/api/app.py` | aiohttp 应用组装 |
| `src/cn_social_agent/api/auth.py` | 登录/注册/登出/me |
| `src/cn_social_agent/api/sessions.py` | 会话 CRUD |
| `src/cn_social_agent/api/chat.py` | 对话 + SSE |
| `src/cn_social_agent/api/skills.py` | Skills API |
| `src/cn_social_agent/api/tools.py` | Tools API |
| `src/cn_social_agent/api/media.py` | Storage 上传 |
| `src/cn_social_agent/api/health.py` | 探活 |
| `src/cn_social_agent/api/deps.py` | InsForge 实例与鉴权中间件 |
| `src/cn_social_agent/api/store.py` | sessions/messages DB 访问（InsForge PostgREST；测试可内存） |
| `src/cn_social_agent/workbench/index.html` | 三栏工作台 |
| `src/cn_social_agent/schema/workbench.sql` | 四张表 DDL |
| `run_workbench.py` | 唯一默认入口 |
| `_legacy/` | 旧模块隔离区 |

---

### Task 1: 瘦内核 — tools / skills / agent loop

**Files:**
- Create: `src/cn_social_agent/tools/__init__.py`, `registry.py`, `builtin.py`
- Create: `src/cn_social_agent/skills/__init__.py`, `loader.py`
- Create: `src/cn_social_agent/agent/__init__.py`, `loop.py`
- Create: `skills/demo-echo/SKILL.md`
- Test: `tests/workbench/test_tools.py`

- [x] 实现 ToolRegistry + builtin `now` / `http_get`
- [x] 实现 SkillLoader（扫描 `skills/**/SKILL.md`）
- [x] 实现 `AgentLoop.run()`：拼 messages → InsForgeLLM → 可选 tool 一轮 → 返回 assistant 文本
- [x] `pytest tests/workbench/test_tools.py -q` 通过

### Task 2: API 层 + store + schema

**Files:**
- Create: `src/cn_social_agent/schema/workbench.sql`
- Create: `src/cn_social_agent/api/*.py`（上表所列）
- Create: `run_workbench.py`
- Test: `tests/workbench/test_api_health.py`

- [x] DDL：sessions / messages / skill_bindings / media_objects
- [x] MemoryStore（无 InsForge 时供本地/测试）+ InsForgeStore
- [x] 挂载全部路由；Bearer 鉴权
- [x] `python run_workbench.py` 可启动；`GET /health` 返回 JSON

### Task 3: Workbench 单页

**Files:**
- Create: `src/cn_social_agent/workbench/index.html`（含内联 CSS/JS）

- [x] 登录表单 + 三栏布局
- [x] 会话列表 / 流式对话 / Skills 开关 / Tools 只读 / 设置
- [x] 默认 `/` 提供该页面

### Task 4: 移除冗余 — 移入 `_legacy/`

**Move into `_legacy/` (不再被 workbench 引用):**

`src/a2a`, `admin`, `analytics`, `auth_mod`, `auth_core.py`, `cli`, `content`, `crawler`, `data`, `inbox`, `kanban`, `llm`, `marketplace`, `mcp`, `media`, `messaging`, `monetization`, `oauth`, `observability`, `platforms`, `repurposer_v2`, `review`, `routes`, `scheduler`, `scrm`, `sentiment`, `social`, `team`, `trends`, `trends_v2`, `verify`, `webhook`, `workflow`, `vector_store`, `server.py`, `login.html`, `middleware.py`, `run_all.py`, `agent`（旧）, `tools`（旧顶层）, `config`（旧）, `utils`, 以及根目录 `run_server.py`

**Keep active:**
- `src/cn_social_agent/`（insforge + 新内核）
- `src/insforge` symlink → `cn_social_agent/insforge`
- `src/__init__.py` 精简
- `skills/`, `tests/workbench/`, `run_workbench.py`, design/plan docs

- [x] 执行 move
- [x] 确认 `run_workbench.py` 启动不 import `_legacy`
- [x] 更新根 `README.md` 为工作台说明
- [x] 旧 `tests/` 与运营相关的移入 `_legacy/tests_old` 或删除（保留 `tests/workbench`）

### Task 5: 冒烟验证

- [x] `pytest tests/workbench -q`
- [x] 手工：InsForge 可用时走登录+对话；不可用时 `/health` 标明依赖状态

---

## Spec coverage

| Spec 项 | Task |
|---------|------|
| Auth / chat / sessions / skills / tools / media / health | 2–3 |
| 三栏 UI | 3 |
| 四表 schema | 2 |
| 移除平台与运营模块 | 4 |
| 无 SQLite 主路径 | 2（InsForge 或测试内存） |
| 成功标准清单 | 5 |
