# Topic Assets + Content Memory Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Give the workbench durable topic memory: aggregate journals/videos under normalized topics, reuse evidence packs, and thin recipe + visual-align fixes.

**Architecture:** Read-only aggregator over existing card history + video_projects (no new KG DB). Canonical `topic_key` groups assets. Later compose/propose prefer local packs. Parallel thin fix for storyboard visual lock.

**Tech Stack:** aiohttp API, workbench `index.html` mode, pytest

---

## File map

| File | Responsibility |
|------|----------------|
| `src/cn_social_agent/knowledge/topic_key.py` | Normalize topic → key + display |
| `src/cn_social_agent/knowledge/assets.py` | Aggregate journals + video projects by topic |
| `src/cn_social_agent/api/assets_routes.py` | `GET /api/topic-assets`, `GET /api/topic-assets/{key}` |
| `src/cn_social_agent/workbench/index.html` | New `assets` mode + list/detail UI |
| `src/cn_social_agent/cards/service.py` / compose UI | A2: compose from existing packId |
| `src/cn_social_agent/video/pipeline.py` | B5: lock theme hop; require shot half |
| `src/cn_social_agent/api/prefs.py` | A4: recent recipes thin |

## Order

1. A1 topic_key + assets API + UI + tests — **done**
2. A2 pack reuse via assets「用此证据成刊」+ existing compose packId — **done (thin)**
3. B5 visual theme lock + ensure_visual_board_shot — **done**
4. A4 recipe prefs (`recent_recipes` / `push_recipe`) — **done**
5. A3 Agent `lookup_topic_assets` tool — **done**
   - tools/context.py contextvars
   - gather/lookup in knowledge/assets.py
   - coach local-first; propose_* attaches local_assets
   - UI appendTopicAssetsCard


### Shipped in this pass

- `knowledge/topic_key.py`, `knowledge/assets.py`
- `GET /api/topic-assets`, `GET /api/topic-assets/{key}`
- Workbench mode `assets`
- Theme hop removed; script normalize fills `板式｜镜头`
- prefs `recent_recipes` + clarify `push_recipe`
