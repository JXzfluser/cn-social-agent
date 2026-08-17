# 讲解演示轨 + OBS 成片 + 发抖音

> Date: 2026-08-11  
> Status: Implementing  
> Plan: `docs/superpowers/plans/2026-08-11-web-presentation-douyin.md`  
> Approach: **方案 1** — 自研演示脚手架 + `web-video-presentation` Skill  
> Source notes: `docs/Harness视频制作资料.md`（ConardLi garden-skills / web-video-presentation 工作流）

## 1. Goal

在短视频工坊增加 **讲解演示（presentation）** 产品轨：用 Skill 纪律驱动

**主题/文章 → 口播稿 + 大纲 → 可点击网页演示（16:9 / 9:16）→ 本机 OBS + `?auto=1` 录屏 → 导入成片预览 → 发抖音**。

Locked decisions:

| Item | Choice |
|------|--------|
| Pipeline | B — 完整网页演示轨（非仅口播 L0/L1 文案 Skill） |
| Capture | B — 本机 OBS 一镜到底（非 Playwright 无头录屏） |
| Aspect | C — 双画幅，建项时选 `16:9` 或 `9:16` |
| Douyin | C — 开放平台 OAuth + 上传；无凭证降级半自动 |
| Skill source | 自研脚手架 + 仓库内 Skill（不 vendoring garden-skills 全文） |
| Relation to L0/L1 | 并存；新 `video_type=presentation`，不替换口播轨 |

## 2. Non-goals (v1)

- Playwright / 无头浏览器自动录屏成片
- 原样拷贝 ConardLi `garden-skills` 全部主题与资产
- 改造或下线现有口播 L0/L1 流水线
- 抖音矩阵多账号运营后台、定时发布日历
- 非官方 Cookie 爬虫发抖音

## 3. User flow

```text
新建「讲解演示」项目（选题 + 画幅 16:9|9:16 + 主题 token）
  → Phase 1：Agent/工坊生成 口播稿 + 开发大纲
  → Checkpoint A1（硬停）：确认稿子 / 大纲 / 主题 / 素材来源 / 串行|并行
  → Phase 2：脚手架落盘；按章写 React 章节（第一章先验视觉）
  → 工坊 iframe 步进预览（手动）
  → Checkpoint B（硬停）：网页 OK？是否合成 TTS？
  → Phase 3（可选）：按 narration 段合成音频，挂到演示资源
  → Phase 4：一键打开 ?auto=1 + OBS 操作清单
  → 用户 OBS 录完 →「导入成片」→ final.mp4 → HTML5 预览
  →「发抖音」：已授权则 API 上传；否则复制标题/话题并打开创作者中心
```

Agent 侧：触发 Skill 后可 `propose_presentation` 交接进工坊同一项目。

## 4. Architecture

```text
Agent (Skill: web-video-presentation)
        │ tools: propose / checkpoint / scaffold / chapter / tts / preview
        ▼
Workbench ?mode=video&type=presentation
        │
        ▼
/api/video/*  (+ presentation-specific routes)
        │
        ├── InsForge video_projects (video_type=presentation + meta)
        ├── data/presentations/{project_id}/   ← Vite scaffold + chapters + audio + final.mp4
        ├── templates/web-presentation/       ← 只读模板
        └── platforms/douyin/                 ← OAuth + video upload
```

Existing L0/L1 path (`data/videos/{id}/`, Agnes, storyboard confirm) remains unchanged for `video_type` 口播 / default.

## 5. Data model

Extend project script meta (`<!--wbmeta:…-->` or equivalent JSON fields already used by workshop):

| Field | Meaning |
|-------|---------|
| `video_type` | `presentation` \| existing 口播 values |
| `aspect` | `16:9` \| `9:16` |
| `theme` | e.g. `paper-press` \| `terminal-green` \| `desk` |
| `phase` | `content` \| `build` \| `audio` \| `record` \| `publish` |
| `checkpoints.a1` | `{ confirmed: bool, at, notes }` |
| `checkpoints.b` | `{ confirmed: bool, synthesize_audio: bool, at }` |
| `presentation_path` | relative dir under `data/presentations/{id}` |
| `dev_mode` | `serial` \| `parallel` |
| `publish` | last Douyin attempt result (mirrors cards history shape) |

Production plan steps for presentation track:

`选题 → 大纲 → 构建 → 音频 → 录屏 → 发布`

（口播轨仍用现有 `选题 → 类型 → 要素 → 分镜 → 草稿 → 成片`。）

## 6. Presentation scaffold

Path: `templates/web-presentation/`

Stack: Vite + React + TypeScript.

Hard constraints (from Harness notes):

1. Fixed stage: `1920×1080` or `1080×1920` + `transform: scale` to viewport — no responsive reflow of content
2. Global `(chapter, step)` cursor; chapters are pure functions of step — no independent timers driving narrative
3. One beat = one full-screen step; no bullet dump on a single step
4. Narration beat maps 1:1 to step
5. Chrome hidden until hover (progress only)
6. No header/footer/page chrome on stage
7. Prefer content-driven motion; entrance animation only as fallback
8. Multi-item reveals: 1 item = 1 step (no staggered dump of N)
9. One theme token set for the whole piece
10. Dual source: script sets pacing; outline/article sets visual density

Play modes:

| Mode | Query | Behavior |
|------|-------|----------|
| Manual | (none) | Click/keyboard advance; no forced audio |
| Audio | `?audio=1` | Manual advance; play step audio on enter |
| Auto | `?auto=1` | After first Space (unlock autoplay), advance by audio duration |

Workbench serves or proxies the project (e.g. `GET /api/video/projects/{id}/presentation/` static, or subprocess `vite preview` URL stored in meta). v1 preferred: **copy scaffold → write chapter modules → `npm install && npm run build` → serve `dist/`** so preview does not require a long-lived Vite process. Dev rebuild on chapter save can be a follow-up.

## 7. Skill & tools

### Skill

`skills/web-video-presentation/SKILL.md`

- Triggers: 讲解演示、知识讲解视频、web presentation、Harness 演示、文章转视频演示, etc.
- Embeds four phases + hard checkpoints A1/B as contracts (Agent must stop)
- Points at scaffold conventions and theme tokens
- Does **not** invent Remotion/HyperFrames; does **not** claim OBS finished without user import

### Tools (new or extended in `tools/builtin.py`)

| Tool | Role |
|------|------|
| `propose_presentation` | Create/link presentation project; hand off to workshop |
| `confirm_checkpoint` | Persist A1/B confirmation (server validates required fields) |
| `scaffold_presentation` | Copy template into `data/presentations/{id}` with aspect/theme |
| `upsert_presentation_content` | Write script + outline artifacts |
| `build_chapter` | Write/replace one chapter module; optionally trigger rebuild |
| `synthesize_narration_audio` | Batch TTS for narration segments (reuse edge-tts unless MiniMax configured later) |
| `presentation_preview_url` | Return URL + OBS checklist payload |

Middleware: block Phase 2 tools until A1 confirmed; block Phase 3/4 auto-advance claims until B confirmed.

## 8. API

Reuse `/api/video/projects` where possible; add:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/video/projects` | `video_type=presentation`, `aspect`, `theme` |
| POST | `/api/video/projects/{id}/presentation/scaffold` | Materialize scaffold |
| POST | `/api/video/projects/{id}/checkpoints/{a1\|b}` | Confirm checkpoint |
| POST | `/api/video/projects/{id}/presentation/build` | npm build (async job ok) |
| GET | `/api/video/projects/{id}/presentation/` | Serve built preview (or redirect) |
| POST | `/api/video/projects/{id}/presentation/import` | Upload/attach OBS `final.mp4` |
| POST | `/api/video/projects/{id}/publish` | `platform=douyin` (+ caption overrides) |
| GET | `/api/oauth/douyin/status\|authorize\|…` | Mirror weixin/toutiao oauth routes |

Import sets `output_path`, status `done`, plan step `录屏` → done. Existing `download?inline=1` previews the mp4.

## 9. Douyin publish

### Publisher

`platforms/douyin/publisher.py`

- OAuth via Douyin Open Platform (`client_key` / `client_secret` from env + secrets store)
- Extend publish capability beyond card images: accept `video_path: Path` + title/hashtags/cta from script meta
- Prefer extending `PlatformPublisher` with optional video args **or** a parallel `VideoPublisher` protocol used only by video routes — avoid breaking card image publish. Recommendation: **`VideoPublisher` protocol** + thin adapter so Weixin/Toutiao card publishers stay untouched.

### Behavior

1. If credentials missing or not authorized → `status=skipped`, message includes creator-center URL + clipboard payload (title, hashtags, description)
2. If authorized and `final.mp4` present → upload + create post (scopes as required by current Douyin video API); persist result on project meta `publish`
3. UI: workshop button「发抖音」+ global「平台」dialog tab for Douyin (same pattern as cards)

Env: `DOUYIN_CLIENT_KEY`, `DOUYIN_CLIENT_SECRET`, redirect URI registered to workbench oauth callback.

## 10. UI (短视频工坊)

When creating a project, choose type:

- **口播短视频** — existing UI
- **讲解演示** — presentation UI

Presentation main pane:

1. Phase / plan strip (6 steps above)
2. Checkpoint panel (A1 / B) with confirm CTAs
3. iframe preview of presentation URL + mode links (手动 / 音频 / 自动)
4. OBS checklist card (resolution, `?auto=1`, Space to start, import path hint)
5. Import final + HTML5 `<video>` preview
6. Publish Douyin button + status

Agent chat head / handoff: open workshop on the presentation project id.

## 11. Error handling

| Case | Behavior |
|------|----------|
| Scaffold without A1 | 409 + checkpoint required |
| Build failure | job `failed` + npm log tail in status |
| Preview before build | empty state +「先构建演示」 |
| Import non-mp4 / empty | 400 |
| Douyin API error | `failed` + platform message; keep local mp4 |
| No Douyin creds | `skipped` half-auto path (not an error) |

## 12. Testing

- Unit: checkpoint gate; aspect stage size; plan step derivation for presentation
- Unit: Douyin publisher skipped path without credentials
- Smoke: scaffold → fake chapter → build → static preview 200
- Smoke: import tiny mp4 → inline download
- Optional manual: OBS + real Douyin sandbox when keys present

## 13. Success criteria (v1)

- [ ] Topic → A1 confirm → ≥1 chapter step-preview in chosen aspect
- [ ] B confirm → optional TTS → `?auto=1` URL + OBS checklist in UI
- [ ] Import mp4 → in-page preview
- [ ] Douyin: upload when configured; half-auto when not
- [ ] Existing口播 L0/L1 smoke still passes

## 14. Implementation order

1. Spec + plan (this doc → writing-plans)
2. Template scaffold (minimal stage + 1 demo chapter, both aspects)
3. Skill + tools + checkpoint API
4. Workshop presentation UI (preview iframe + checkpoints + OBS + import)
5. Douyin oauth + publish API + UI (with skipped fallback)
6. Smoke tests + docs pointer from Harness notes

## 15. Open follow-ups (explicitly out of v1 commit scope)

- Live Vite HMR during chapter authoring
- MiniMax CLI instead of edge-tts
- Parallel chapter workers
- Rich theme pack parity with garden-skills
- Playwright capture as optional Phase 4 alternate
