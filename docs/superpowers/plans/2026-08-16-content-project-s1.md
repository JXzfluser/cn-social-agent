# Content Project (S1) Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Content Project first-class so Agent / hotspot / 知识卡片 / 口播 share one `content_project_id` with notes + evidence that never get dropped on jump.

**Architecture:** Dual-write store (local JSON + InsForge `wb_content_projects`), thin HTTP CRUD, handoff/workshop wire-through. UI: persistent “当前项目” chip (no new top-level mode in S1).

**Tech Stack:** Python aiohttp, existing InsForge db helpers, workbench `index.html` / `cards_workshop.js`

**Open questions resolved for S1:**
1. Persist = dual-write like card history  
2. Migrate old journals/videos = lazy (only when opened with an id, optional later)  
3. UI = chip + list drawer, not a new mode

---

### Task 1: Domain model + local store

**Files:**
- Create: `src/cn_social_agent/content/__init__.py`
- Create: `src/cn_social_agent/content/models.py`
- Create: `src/cn_social_agent/content/store_local.py`
- Test: `tests/workbench/test_content_project.py`

- [ ] **Step 1: Write failing tests for normalize + local save/get/list**

```python
# tests/workbench/test_content_project.py
from cn_social_agent.content.models import normalize_project, new_project_id
from cn_social_agent.content.store_local import save_project, get_project, list_projects

def test_normalize_distills_short_topic():
    p = normalize_project({
        "topic": "浏览器扩展合集：我们为你找到了这 6 款实用、有趣的「新玩意」",
        "user_id": "u1",
    })
    assert p["short_topic"] == "浏览器扩展合集"
    assert p["id"].startswith("cp_")
    assert p["status"] == "researching"

def test_local_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_PROJECT_DIR", str(tmp_path))
    p = normalize_project({"topic": "Grok Build", "user_id": "u1", "email": "a@b.c"})
    saved = save_project(p, user_id="u1", email="a@b.c")
    got = get_project(saved["id"], user_id="u1", email="a@b.c")
    assert got["short_topic"] == "Grok Build"
    assert any(x["id"] == saved["id"] for x in list_projects(user_id="u1", email="a@b.c"))
```

- [ ] **Step 2: Implement models + local store (mirror `cards/history.py` owner_key pattern)**
- [ ] **Step 3: Tests pass**

---

### Task 2: InsForge cloud mirror + schema

**Files:**
- Create: `src/cn_social_agent/content/cloud.py`
- Modify: `scripts/ensure_workbench_tables.py` (add `wb_content_projects`)
- Modify: `src/cn_social_agent/schema/workbench.sql` if present
- Modify: `src/cn_social_agent/api/deps.py` (set_content_db on boot)

- [ ] **Step 1: Table** `wb_content_projects` with `user_id`, `email`, `owner_key`, `project_id`, `topic`, `short_topic`, `category`, `status`, `payload` (jsonb/text)
- [ ] **Step 2: upsert / get / list / delete** like `cards/cloud.py`
- [ ] **Step 3: Dual-write helper** `content/service.py`: `upsert_project` → local then cloud

---

### Task 3: HTTP API

**Files:**
- Create: `src/cn_social_agent/api/content_project_routes.py`
- Modify: `src/cn_social_agent/api/app.py` — `setup_content_project_routes(app)`

Routes:
- `POST /api/content-projects` — create from topic/notes/source
- `GET /api/content-projects` — list
- `GET /api/content-projects/{id}` — get
- `PATCH /api/content-projects/{id}` — patch fields / evidence / artifacts
- `POST /api/content-projects/{id}/attach` — body `{ journal_id?, video_id?, presentation_id? }`

- [ ] **Step 1: Tests with TestClient** (mock store or memory)
- [ ] **Step 2: Implement routes + register**

---

### Task 4: Handoff creates/attaches project

**Files:**
- Modify: `src/cn_social_agent/tools/hotspot_handoff.py`
- Modify: `src/cn_social_agent/api/hotspots_routes.py`
- Modify: `src/cn_social_agent/tools/builtin.py` (`propose_knowledge_cards` return `content_project_id` when notes present — optional create via service)
- Test: extend `tests/workbench/test_hotspot_handoff.py`

- [ ] Journal handoff response includes `content_project_id`, `short_topic`, `research_notes`
- [ ] Creating handoff persists a Content Project with notes

---

### Task 5: Workshops read/write project

**Files:**
- Modify: `src/cn_social_agent/api/card_routes.py` — research/compose accept `content_project_id`, write back evidence/journal_id
- Modify: `src/cn_social_agent/workbench/cards_workshop.js` — state.contentProjectId, setHandoff/setProject, research body
- Modify: `src/cn_social_agent/workbench/index.html` — openCardWorkshop + handoffHotspot pass id; “当前项目” chip
- Bump `cards_workshop.js?v=`

- [ ] Open workshop with project id → preload roles/notes → research writes evidence back to project
- [ ] Chip shows `short_topic`; click opens card workshop for that project

---

### Task 6: Smoke + suite

- [ ] `pytest tests/workbench/test_content_project.py tests/workbench/test_hotspot_handoff.py tests/workbench/test_knowledge_journal.py -q`
- [ ] Manual: hotspot → journal handoff → chip shows topic → evidence seeds on-topic
- [ ] Restart workbench; hard-refresh UI

---

## Spec coverage

| Spec S1 item | Task |
|--------------|------|
| Persist Content Projects | 1–2 |
| API CRUD + attach | 3 |
| Wire hotspot / propose / research | 4–5 |
| UI chip | 5 |
| Success: Agent jump not blank | 4–5 |
