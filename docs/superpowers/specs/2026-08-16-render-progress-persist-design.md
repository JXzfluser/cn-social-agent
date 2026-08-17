# Render Progress Persist (Realtime 进度 / 异步升 L1)

**Date:** 2026-08-16  
**Status:** approved (Option B lite)

## Problem

L0/L1 render already runs in `asyncio.create_task` and the UI polls `GET /status` every 1.5s. Progress (`%` / message) lives only in `AppState.video_jobs`. Refresh or process restart drops mid-render feedback even though the project row is still `rendering`.

## Decision

Persist render progress into script wbmeta; keep polling. Do **not** wire InsForge Realtime or Schedules in this round.

## Design

1. On job start / each `on_progress` (throttled ≈ per scene or ≥2s): write  
   `render_progress`, `render_message`, `render_scene_i`, `render_scene_n`, `render_started_at`.
2. `GET /status`: if memory job missing and `status==rendering`, rebuild job from wbmeta.
3. On `done` / `failed`: clear progress keys from wbmeta.
4. UX: L1 CTA / job copy uses「后台升级成片中…」— same 202 + poll path.

## Out of scope

- InsForge Realtime channel / SQL trigger  
- SSE for video  
- Schedules / Edge for deferred L1  
- Redis / external job queue  

## Success

Refresh mid-L1 still shows non-zero progress + message from `/status` without an in-memory job.
