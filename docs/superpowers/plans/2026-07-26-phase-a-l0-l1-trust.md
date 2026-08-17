# Phase A — L0/L1 Trust Contract Implementation Plan

> **Status:** Phase A landed in code (2026-07-26) — verify in UI  
> Spec: `docs/superpowers/specs/2026-07-26-product-positioning-90d-roadmap.md`

**Goal:** Local = 「分镜草稿」L0; Agnes = 「成片」L1; default L0→upgrade L1; fail reasons; L1 quality gate; chat/workshop sync.

## Done

- [x] wbmeta: `delivery_level` / `fail_reason` / `quality_gate_pass` + helpers
- [x] `video/quality.py` P0 gate (brightness / motion / A-V)
- [x] API: generate pins local; render accepts `delivery_level`; status returns delivery
- [x] UI: 生成分镜草稿 / 升级成片; retry; auto L0 after from-session; project list tags; card sync

## Verify manually

1. Open http://127.0.0.1:18081/ → 短视频：创建分镜 → 「生成分镜草稿」→ 文案应为草稿非成片  
2. Agent：做短视频 → 自动 L0 → 「升级成片」走 Agnes + 质检  
3. 失败时卡片显示原因 + 重试；工坊列表显示「分镜草稿/成片」
