# Phase B — Single-scene control

> **Status:** Landed in code (2026-07-26) — **restart workbench** to load API routes

**Goal:** Re-render one scene + remux final; edit on_screen; director hints; quality suggestions.

## Done

- [x] Preserve scene meta (`poster_path`, `scene_render_mode`) after render
- [x] `render_one_scene` + `remux_project_final`
- [x] `POST /api/video/projects/{id}/scenes/{scene_id}/render`
- [x] PATCH scene `on_screen` / visual / mood / role
- [x] UI: 重渲草稿 / 此镜升级成片 / 只重配音 + tips
- [x] Agent coach + propose hints (L0/L1, hook/cta)
- [x] `suggest_scene_rerenders` on get/status
- [x] Researcher skill golden path

## Verify

1. Restart process on :18081 (new route was 404 on old process)
2. Open project with existing clips → edit 旁白 →「只重配音」
3. Hook 镜 →「此镜升级成片」→ final remux
4. Agent URL flow mentions L0→L1
