# InsForge Agent Workbench Design

> Date: 2026-07-26  
> Status: Approved — initial implementation landed (2026-07-26)  
> Approach: New slim kernel; quarantine legacy modules (`_legacy/`)

## 1. Goal

Rebuild cn-social-agent as an **InsForge-first Agent workbench**:

- InsForge owns Auth, DB, Storage, and AI Gateway.
- Product surface is a **single efficient web page** (chat + skills/tools + settings).
- **No** Chinese IM/social platform adapters in v1 (DingTalk / Feishu / WeCom / WeChat).
- Remove (or quarantine) features that are not on the InsForge path.

North star user flow:

**Login → multi-turn streaming chat via InsForge LLM → sessions/messages in InsForge DB → enable skills / call tools → upload media via InsForge Storage.**

## 2. Product decisions (locked)

| Decision | Choice |
|----------|--------|
| Product shape | E1 — InsForge Agent workbench + efficient UI |
| Delivery approach | Approach 2 — new slim kernel; move old ops modules to `_legacy/` |
| Platforms in v1 | None (Web chat + API only) |
| Admin / ops SaaS | Out of scope for v1 |
| Local SQLite as primary store | Forbidden for product paths |

## 3. Scope

### 3.1 Keep in v1

| Capability | InsForge dependency | Notes |
|------------|---------------------|-------|
| Login / session | Auth | Sole identity source; no `users.db` primary path |
| Chat agent | AI Gateway | Streaming, system prompt, multi-turn |
| Session memory | DB (PostgREST) | `sessions` + `messages` |
| Skills | DB (+ optional Storage) | `SKILL.md` load; list / enable / hot reload |
| Tools / function calling | App layer | Built-in tools + registry extension point |
| Attachments | Storage | Upload then reference in chat |
| Minimal API | — | Auth, chat, sessions, skills, tools, media, health |
| Workbench UI | — | Three-pane single page |

### 3.2 Remove or quarantine (not mounted)

- Ops admin SPA and its business nav (radar, sentiment, monetization, marketplace, kanban-as-product, etc.)
- Platform adapters (`platforms/`, social publishers, OAuth-for-platforms)
- SCRM, A2A/MCP, local vector store, APScheduler publish pipeline
- Seventeen business SQLite databases as product storage
- Stub routes (e.g. publish 501 presented as features)

### 3.3 Explicit Phase 2 (documented only, not built in v1)

- InsForge Schedules (scheduled agent runs)
- Platform webhooks
- Multi-agent collaboration
- Marketplace
- Deep Email / Secrets / Analytics usage

## 4. Architecture

```
┌─────────────────────────────────────────┐
│  Workbench UI (single page)             │
│  sessions | chat stream | skills/tools  │
└─────────────────┬───────────────────────┘
                  │ HTTP + Bearer
                  ▼
┌─────────────────────────────────────────┐
│  Slim Python API                        │
│  auth · chat · sessions · skills ·      │
│  tools · media                          │
└─────────────────┬───────────────────────┘
                  │ InsForge SDK
                  ▼
┌─────────────────────────────────────────┐
│  InsForge BaaS                          │
│  Auth · DB · Storage · AI Gateway       │
└─────────────────────────────────────────┘
```

### 4.1 Principles

1. Agent loop and tool/skill orchestration stay in Python.
2. Identity, persistence, files, and model calls go through InsForge only.
3. UI never talks to model vendors directly; API never talks to vendors when InsForge gateway is configured.
4. Startup imports a **whitelist** only; `_legacy` is never imported by the default entrypoint.

### 4.2 Target directory layout

```
src/cn_social_agent/
  insforge/       # existing SDK — single integration entry
  agent/          # chat loop, memory, tool calling (refined from current agent)
  skills/         # SKILL.md loader + registry
  tools/          # builtin tools + registry
  api/            # new app (replaces monolithic server.py as entry)
  workbench/      # static single-page UI assets
_legacy/          # quarantine for old modules during migration
run_workbench.py  # default entrypoint
```

Reusable from current tree: InsForge SDK, agent core, skills loader patterns.  
Everything else ops/platform-related moves under `_legacy/` until deleted.

## 5. Workbench UI

One screen, three panes + top bar:

| Region | Content | Behavior |
|--------|---------|----------|
| Left | Session list | Create / search / delete; title + last activity |
| Center | Chat stream | SSE streaming; tool/skill call cards; attachment previews |
| Right | Context panel | Tabs: Skills (toggle) / Tools (read-only) / Settings (model, system prompt) |
| Top | Brand + user | Auth state, logout; **no** ops menu |

Out of UI scope: multi-module sidebar, dashboards, radar, boards.

Implementation preference for v1: lightweight static page + SSE (avoid heavy frontend stack unless later required).

## 6. API sketch

| Method | Path | Purpose | InsForge |
|--------|------|---------|----------|
| POST | `/api/auth/login` | Login | Auth |
| POST | `/api/auth/register` | Register (optional/disableable) | Auth |
| POST | `/api/auth/logout` | Logout | Auth |
| GET | `/api/auth/me` | Current user | Auth |
| GET/POST | `/api/sessions` | List / create | DB |
| GET/DELETE | `/api/sessions/{id}` | Detail / delete | DB |
| POST | `/api/chat` | Send message (SSE stream) | AI + DB |
| GET | `/api/skills` | List skills | DB / filesystem scan |
| PATCH | `/api/skills/{id}` | Enable / disable | DB |
| GET | `/api/tools` | Registered tools | In-process registry |
| POST | `/api/media` | Upload attachment | Storage |
| GET | `/health` | Liveness + dependency status | — |

Auth: `Authorization: Bearer <access_token>` on all non-public routes.  
Use InsForge `client_type=server` patterns for refresh tokens where needed.

## 7. Data model (InsForge Postgres)

Minimal tables:

**sessions**  
`id`, `user_id`, `title`, `system_prompt`, `model`, `created_at`, `updated_at`

**messages**  
`id`, `session_id`, `role`, `content`, `tool_calls` (json), `created_at`

**skill_bindings**  
`user_id`, `skill_id`, `enabled`

**media_objects**  
`id`, `user_id`, `storage_path`, `mime`, `created_at`

Apply via InsForge table/migration workflow (not local SQLite). Row-level access scoped by `user_id` from Auth.

## 8. Migration plan

1. **Freeze** — deprecate old `server.py` as product entry; document `run_workbench.py` as default.
2. **Kernel** — stand up `api/` + agent loop; LLM only through `InsForgeLLM` / gateway provider.
3. **Schema** — create the four tables in InsForge.
4. **Auth** — InsForge-only auth path; remove SQLite users as primary.
5. **Workbench UI** — three-pane page as default `/`.
6. **Skills / Tools** — migrate loader; ship 2–3 demo tools (e.g. `http_get`, `now`).
7. **Media** — wire Storage upload into chat.
8. **Quarantine** — move ops/platform modules to `_legacy/`; ensure default boot does not import them.
9. **Cleanup** — delete `_legacy` in a later pass once zero references remain.

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Accidental import of legacy | Package exclude `_legacy`; whitelist imports in entrypoint |
| Auth middleware event-loop bugs | Rewrite middleware as pure async; no `run_until_complete` on request path |
| UI rebuild cost | Static + SSE for v1 |
| InsForge down locally | `/health` reports Auth/DB/AI/Storage; README documents start order |

## 10. Success criteria (v1 Done)

- [ ] Login to workbench with an InsForge account
- [ ] Multi-turn streaming chat; messages persisted in InsForge DB
- [ ] Toggle at least one skill; invoke at least one tool in a conversation
- [ ] Upload an attachment and reference it in a session
- [ ] Default process does **not** load platform/ops/sentiment/monetization modules
- [ ] No product-path dependency on local business SQLite files

## 11. Non-goals (v1)

- Multi-platform social publishing
- SCRM / sentiment / monetization / marketplace
- Replacing InsForge Dashboard
- Full parity with the current admin SPA

## 12. Next step

After user approves this spec, produce an implementation plan via the writing-plans skill (`docs/superpowers/plans/...`) and execute in ordered tasks.
