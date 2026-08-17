# Chat → Short Video Implementation Plan

> **For agentic workers:** implement task-by-task. Steps use checkbox syntax.

**Goal:** Wire Agent chat to short-video creation via propose tool + from-session API + in-chat cards.

**Architecture:** Tool signals readiness; `from-session` extracts topic via LLM then reuses existing generate pipeline; UI stays on Agent view with video cards; workshop lists same projects.

**Tech Stack:** aiohttp, existing VideoStore/pipeline, workbench `index.html`

---

### Task 1: Tool + coach prompt
- [x] Add `propose_short_video` in `tools/builtin.py`
- [x] Append video coach system fragment in `agent/loop.py`

### Task 2: from-session API
- [x] Add `extract_topic_from_transcript` in `video/pipeline.py`
- [x] `POST /api/video/from-session` in `video_routes.py` + register route
- [x] Persist assistant message with tool_calls `short_video_project`

### Task 3: UI
- [x] Action bar, suggest card, video card in `index.html`
- [x] Wire render/status/preview/download; optional jump to video mode

### Task 4: Verify
- [x] Smoke: `scripts/smoke_chat_to_video.py`
