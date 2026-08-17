# Web Presentation + Douyin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Spec: `docs/superpowers/specs/2026-08-11-web-presentation-douyin-design.md`  
> Note: workspace may lack `.git` — skip commit steps if `git` is unavailable.
>
> **Status:** v1 landed in code (2026-08-11) — verify in UI

**Goal:** Add a presentation video track (Vite/React stage + Harness checkpoints + OBS import) and Douyin publish with half-auto fallback, without breaking the existing口播 L0/L1 path.

**Architecture:** Presentation projects store state in `video_projects.script` wbmeta (`video_type=presentation`). Scaffold copies `templates/web-presentation/` → `data/presentations/{id}/`, builds to `dist/`, serves via API. Douyin uses a separate `VideoPublisher` protocol so card image publishers stay untouched.

**Tech Stack:** Python/aiohttp workbench, Vite+React+TS template, edge-tts, existing InsForge `video_projects`, Douyin Open Platform OAuth (optional).

---

## File map

| Path | Responsibility |
|------|----------------|
| `src/cn_social_agent/video/presentation.py` | Paths, aspect sizes, checkpoint helpers, scaffold/copy, OBS checklist |
| `src/cn_social_agent/video/plan.py` | Branch presentation vs口播 plan steps |
| `templates/web-presentation/**` | Read-only Vite scaffold (stage, themes, demo chapter) |
| `src/cn_social_agent/api/video_routes.py` | Create type + presentation endpoints |
| `src/cn_social_agent/video/store.py` | Allow `video_type` on create/update |
| `skills/web-video-presentation/SKILL.md` | Agent contract |
| `src/cn_social_agent/skills/loader.py` | Triggers for presentation skill |
| `src/cn_social_agent/tools/builtin.py` | New presentation tools |
| `src/cn_social_agent/platforms/video_base.py` | `VideoPublisher` protocol |
| `src/cn_social_agent/platforms/douyin/publisher.py` | OAuth + upload or skipped half-auto |
| `src/cn_social_agent/api/oauth_routes.py` | Register `douyin` config platform |
| `src/cn_social_agent/workbench/index.html` | Presentation UI pane |
| `tests/workbench/test_presentation_*.py` | Unit/smoke |

---

### Task 1: Presentation meta + production plan

**Files:**
- Create: `src/cn_social_agent/video/presentation.py`
- Modify: `src/cn_social_agent/video/plan.py`
- Test: `tests/workbench/test_presentation_plan.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/workbench/test_presentation_plan.py
from cn_social_agent.video.plan import build_production_plan
from cn_social_agent.video.pipeline import encode_script_bundle
from cn_social_agent.video.presentation import (
    STAGE_SIZES,
    is_presentation,
    obs_checklist,
)


def test_stage_sizes():
    assert STAGE_SIZES["16:9"] == (1920, 1080)
    assert STAGE_SIZES["9:16"] == (1080, 1920)


def test_presentation_plan_topic_active():
    script = encode_script_bundle(
        {"full_script": "", "video_type": "presentation", "aspect": "16:9"}
    )
    plan = build_production_plan(
        {"topic": "", "script": script, "status": "draft", "video_type": "presentation"},
        [],
    )
    assert plan["track"] == "presentation"
    assert plan["total"] == 6
    by = {s["id"]: s for s in plan["steps"]}
    assert list(by) == ["topic", "outline", "build", "audio", "record", "publish"]
    assert by["topic"]["status"] == "active"


def test_presentation_plan_after_a1():
    script = encode_script_bundle(
        {
            "full_script": "口播",
            "video_type": "presentation",
            "aspect": "9:16",
            "theme": "desk",
            "outline": "ch1...",
            "checkpoints": {"a1": {"confirmed": True}},
        }
    )
    plan = build_production_plan(
        {
            "topic": "Harness 实践",
            "script": script,
            "status": "draft",
            "video_type": "presentation",
        },
        [],
    )
    by = {s["id"]: s for s in plan["steps"]}
    assert by["topic"]["status"] == "done"
    assert by["outline"]["status"] == "done"
    assert by["build"]["status"] == "active"


def test_obs_checklist_aspect():
    c = obs_checklist(aspect="9:16", preview_url="http://x/?auto=1")
    assert c["width"] == 1080 and c["height"] == 1920
    assert "?auto=1" in c["preview_url"]
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
PYTHONPATH=src .venv/bin/pytest tests/workbench/test_presentation_plan.py -v
```

- [ ] **Step 3: Implement `presentation.py` + plan branch**

`presentation.py` exports: `STAGE_SIZES`, `PRESENTATION_ROOT`, `TEMPLATE_ROOT`, `is_presentation(project|meta)`, `normalize_aspect`, `presentation_dir(project_id)`, `obs_checklist(...)`, `get_checkpoints(meta)`, `require_checkpoint(meta, name)`.

In `plan.py`: if `is_presentation(project)`, use `PRESENTATION_STEP_DEFS` and derive done flags from topic / (outline+a1) / (scaffolded+built) / (audio optional or skipped) / (output_path) / (publish status).

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit** (skip if no git)

```bash
git add src/cn_social_agent/video/presentation.py src/cn_social_agent/video/plan.py tests/workbench/test_presentation_plan.py
git commit -m "feat(presentation): meta helpers and production plan track"
```

---

### Task 2: Vite web-presentation template

**Files:**
- Create: `templates/web-presentation/package.json`
- Create: `templates/web-presentation/vite.config.ts`
- Create: `templates/web-presentation/index.html`
- Create: `templates/web-presentation/tsconfig.json`
- Create: `templates/web-presentation/src/main.tsx`
- Create: `templates/web-presentation/src/App.tsx`
- Create: `templates/web-presentation/src/stage.css`
- Create: `templates/web-presentation/src/themes.ts`
- Create: `templates/web-presentation/src/config.ts` (aspect/theme injected at scaffold)
- Create: `templates/web-presentation/src/chapters/index.ts`
- Create: `templates/web-presentation/src/chapters/ch01-demo.tsx`
- Create: `templates/web-presentation/src/narrations.ts`
- Test: `tests/workbench/test_presentation_template.py` (files exist + package.json name)

Constraints in App:
- Read `config.aspect` → stage size
- `(chapter, step)` cursor; Arrow/Space/click advance
- `?audio=1` / `?auto=1` modes per spec
- Hover-only progress chrome

- [ ] **Step 1–4:** Add template files; test asserts required paths exist; optional `npm install && npm run build` in template dir when node available.

---

### Task 3: Scaffold / checkpoint / build / serve / import API

**Files:**
- Modify: `src/cn_social_agent/video/store.py` — allow `video_type` create/update
- Modify: `src/cn_social_agent/api/video_routes.py` — create accepts presentation fields; new routes
- Extend: `src/cn_social_agent/video/presentation.py` — `scaffold_project`, `write_content`, `run_build`, `import_final`
- Test: `tests/workbench/test_presentation_scaffold.py` (tmpdir, no InsForge)

API:
- `POST .../presentation/scaffold` — 409 if A1 missing
- `POST .../checkpoints/{a1|b}`
- `POST .../presentation/build`
- `GET .../presentation/` or `/presentation/{path:.*}` — static from `dist/`
- `POST .../presentation/import` — multipart mp4 → `final.mp4` + `output_path`

Create project: `video_type=presentation`, seed wbmeta with aspect/theme/phase.

---

### Task 4: Skill + triggers + agent tools

**Files:**
- Create: `skills/web-video-presentation/SKILL.md`
- Modify: `src/cn_social_agent/skills/loader.py` — add triggers **before** short-video-director
- Modify: `src/cn_social_agent/tools/builtin.py` — register tools listed in spec
- Test: `tests/workbench/test_skill_select.py` — assert presentation triggers

---

### Task 5: Douyin VideoPublisher + publish route

**Files:**
- Create: `src/cn_social_agent/platforms/video_base.py`
- Create: `src/cn_social_agent/platforms/douyin/__init__.py`
- Create: `src/cn_social_agent/platforms/douyin/publisher.py`
- Modify: `src/cn_social_agent/platforms/__init__.py` — register douyin (card oauth) + video registry
- Modify: `src/cn_social_agent/api/oauth_routes.py` — `_CONFIG_PLATFORMS` include `douyin`
- Modify: `src/cn_social_agent/api/video_routes.py` — `POST .../publish`
- Test: `tests/workbench/test_douyin_publish.py` — skipped path returns clipboard payload

`publish_video` without creds:

```python
{
  "platform": "douyin",
  "status": "skipped",
  "external_id": "",
  "url": "https://creator.douyin.com/creator-micro/content/upload",
  "message": "...",
  "clipboard": {"title": "...", "hashtags": [...], "description": "..."},
}
```

With creds: attempt real upload; on API gap still return clear `failed`/`skipped` message (no fake success).

---

### Task 6: Workshop UI

**Files:**
- Modify: `src/cn_social_agent/workbench/index.html` (and/or small `presentation_workshop.js` if splitting)
- Platform dialog: add Douyin tab (mirror weixin/toutiao)

UI:
- New project type toggle: 口播 | 讲解演示
- Presentation pane: plan strip, A1/B panels, iframe, OBS checklist, import, preview, 发抖音
- Hide L0/L1 controls when `video_type=presentation`

---

### Task 7: Smoke + docs pointer

**Files:**
- Create: `scripts/smoke_presentation.py` (scaffold in tmp, build if node, or skip)
- Modify: `docs/Harness视频制作资料.md` — link to spec at top
- Modify: spec status → Implementing
- Run: existing `tests/workbench/test_production_plan.py` still pass

---

## Spec coverage check

| Spec section | Task |
|--------------|------|
| Dual aspect + stage | 1, 2 |
| Checkpoints A1/B | 1, 3, 4, 6 |
| Scaffold build serve | 2, 3 |
| OBS + import + preview | 3, 6 |
| Skill + tools | 4 |
| Douyin API + half-auto | 5, 6 |
|口播 L0/L1 untouched | 1 branch + 7 regression |

## Execution

User requested start immediately → **Inline Execution** in this session (executing-plans style), beginning Task 1.
