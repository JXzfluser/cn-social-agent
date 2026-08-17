# Canvas and Project Workspace Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver polished canvas creation/relations/navigation/templates/AI organization and a searchable, draggable project board with progress and detail views.

**Architecture:** Add pure Python helpers for geometry, templates, project query/progress, and AI payload validation. Keep existing persistence and routes, while moving new browser behavior into focused static JavaScript modules loaded by the workbench.

**Tech Stack:** Python 3, aiohttp, vanilla JavaScript/CSS/HTML, pytest.

---

### Task 1: Canvas geometry and templates

**Files:**
- Create: `src/cn_social_agent/content/canvas_geometry.py`
- Modify: `src/cn_social_agent/content/canvas.py`
- Test: `tests/workbench/test_canvas_enhancements.py`

- [ ] **Step 1: Write failing geometry and template tests**

Test that `edge_endpoints(a, b)` intersects the source and target rectangle boundaries, never their centers, and that `curve_path(a, b)` returns a cubic SVG path. Test `list_canvas_templates()` and `instantiate_canvas_template("topic_funnel")` for stable node IDs, valid edges, and no overlap.

- [ ] **Step 2: Verify the tests fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/workbench/test_canvas_enhancements.py -q`

Expected: import failure for `canvas_geometry`.

- [ ] **Step 3: Implement pure helpers**

Implement:

```python
def edge_endpoints(source: dict[str, Any], target: dict[str, Any]) -> tuple[float, float, float, float]: ...
def curve_path(source: dict[str, Any], target: dict[str, Any]) -> str: ...
def list_canvas_templates() -> list[dict[str, str]]: ...
def instantiate_canvas_template(template_id: str) -> dict[str, Any]: ...
```

Use rectangle-ray intersection for endpoints and deterministic templates for `blank`, `topic_funnel`, `script_structure`, and `swot`.

- [ ] **Step 4: Verify tests pass**

Run the focused test file and existing `tests/workbench/test_canvas.py`.

### Task 2: Canvas routes and AI organization guard

**Files:**
- Modify: `src/cn_social_agent/api/canvas_routes.py`
- Create: `src/cn_social_agent/content/canvas_ai.py`
- Test: `tests/workbench/test_canvas_enhancements.py`

- [ ] **Step 1: Write failing route/helper tests**

Test template listing/creation, AI request validation, selected-node filtering, invalid model output rejection, and preservation of existing node IDs.

- [ ] **Step 2: Verify RED**

Run the focused test and confirm missing functions/routes cause the failure.

- [ ] **Step 3: Implement endpoints**

Add:

```text
GET  /api/canvas/templates
POST /api/canvas/boards          {title, template_id}
POST /api/canvas/organize        {project_id|board_id, node_ids, instruction}
```

The organize route uses the configured workbench LLM, requests strict JSON, normalizes the result, and saves only after successful validation. It does not publish.

- [ ] **Step 4: Verify GREEN**

Run focused tests and all canvas tests.

### Task 3: Workbench dialog and canvas interaction module

**Files:**
- Create: `src/cn_social_agent/workbench/canvas_enhancements.js`
- Modify: `src/cn_social_agent/workbench/index.html`
- Test: `tests/workbench/test_workbench_static.py`

- [ ] **Step 1: Write failing static-contract tests**

Assert the workbench contains one reusable dialog, loads `canvas_enhancements.js`, contains no canvas `window.prompt`/`window.confirm`, and exposes buttons for fit, templates, minimap, and AI organize.

- [ ] **Step 2: Verify RED**

Run the static-contract test and confirm the missing module/dialog assertions fail.

- [ ] **Step 3: Implement dialog and interactions**

The module exports/attaches:

```javascript
window.CanvasEnhancements = {
  openDialog,
  edgeGeometry,
  renderMinimap,
  fitContent,
  openContextMenu,
  openTemplatePicker,
  organizeSelection,
};
```

Replace create/rename/delete/edge-label prompts with the reusable dialog. Render cubic edge paths with boundary endpoints and visible arrows. Add double-click-to-create, context menu, fit, minimap navigation, template picker, and AI organize.

- [ ] **Step 4: Verify GREEN**

Run static tests, then use browser smoke testing for keyboard focus, Escape, Enter, arrow visibility, and minimap navigation.

### Task 4: Project query and progress model

**Files:**
- Modify: `src/cn_social_agent/content/board.py`
- Modify: `src/cn_social_agent/api/content_project_routes.py`
- Test: `tests/workbench/test_board.py`

- [ ] **Step 1: Write failing tests**

Test:

```python
filter_projects(cards, query="agent", category="AI", artifact="canvas")
sort_projects(cards, "evidence_desc")
project_progress(project)
```

Progress must report evidence, canvas, journal, presentation, video, and quality states.

- [ ] **Step 2: Verify RED**

Run `tests/workbench/test_board.py` and confirm missing helper failures.

- [ ] **Step 3: Implement helpers and board query parameters**

Support `q`, `category`, `artifact`, and `sort` on `/api/content-projects/board`. Include categories and progress in the response. Keep lane mapping unchanged.

- [ ] **Step 4: Verify GREEN**

Run board and content-project tests.

### Task 5: Project board module, drawer, and drag/drop

**Files:**
- Create: `src/cn_social_agent/workbench/project_board.js`
- Modify: `src/cn_social_agent/workbench/index.html`
- Test: `tests/workbench/test_workbench_static.py`

- [ ] **Step 1: Write failing static-contract tests**

Assert search/filter/sort controls, detail drawer, artifact progress markers, draggable cards, lane drop zones, and project canvas actions exist.

- [ ] **Step 2: Verify RED**

Run the focused static test.

- [ ] **Step 3: Implement board behavior**

The module owns filtering, fetch cancellation, drawer rendering, drag state, optimistic lane movement, rollback on failure, and “open project canvas”. Reject continues to use the workbench dialog because it requires a reason.

- [ ] **Step 4: Verify GREEN**

Run static tests and browser-smoke filters, drawer, drag between non-rejected lanes, reject dialog, and canvas handoff.

### Task 6: Integration verification and documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-08-16-workbuddy-content-os-design.md`

- [ ] **Step 1: Run all workbench tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/workbench -q --tb=short
```

Expected: all tests pass.

- [ ] **Step 2: Restart and smoke the app**

Restart on port `18081`, verify HTTP 200, then browser-test:

1. Create and rename a board through the in-app dialog.
2. Create two nodes, connect them, verify visible arrow, edit edge label.
3. Fit content and navigate with minimap.
4. Create each template and run AI organize error/success paths.
5. Search/filter/sort projects, open detail drawer, drag lanes.
6. Open a project canvas and hand selected nodes to cards.
7. Hard refresh and verify persistence.

- [ ] **Step 3: Update docs**

Document new canvas routes, board query parameters, keyboard shortcuts, and the no-auto-publish guard.

