"""Content automations — recipes, prefs, and run handlers (S3)."""

from __future__ import annotations

import time
from typing import Any, Optional

RECIPES: tuple[dict[str, Any], ...] = (
    {
        "id": "daily_hotspot_candidates",
        "label": "每日热点候选",
        "description": "按已开启连接器扫热点，把 Top N 写成草稿内容项目（不自动发布）",
        "trigger": "manual|daily",
        "actions": ["scan_hotspot", "create_content_projects"],
        "default_enabled": False,
    },
    {
        "id": "handoff_seed_research",
        "label": "交接自动种子证据",
        "description": "热点/Agent 交接进知识卡片时，自动用原文生成种子证据",
        "trigger": "handoff",
        "actions": ["seed_research"],
        "default_enabled": True,
    },
    {
        "id": "quality_pass_mark_export",
        "label": "成刊达标标记可导出",
        "description": "知识卡片质检通过后，在项目上标记「可导出」（不自动发到公号）",
        "trigger": "quality_pass",
        "actions": ["mark_export_ready"],
        "default_enabled": True,
    },
)


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def default_automation_prefs() -> dict[str, Any]:
    return {
        "automations_enabled": {r["id"]: bool(r["default_enabled"]) for r in RECIPES},
        "automation_last_run": {},
        "automation_runs": [],
    }


def normalize_automation_prefs(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw or {}
    en_raw = src.get("automations_enabled")
    if not isinstance(en_raw, dict):
        en_raw = {}
    enabled = {}
    for r in RECIPES:
        rid = r["id"]
        enabled[rid] = bool(en_raw[rid]) if rid in en_raw else bool(r["default_enabled"])
    last = src.get("automation_last_run")
    if not isinstance(last, dict):
        last = {}
    last_clean = {str(k): str(v)[:40] for k, v in last.items() if str(k)}
    runs = src.get("automation_runs")
    if not isinstance(runs, list):
        runs = []
    runs_clean = [x for x in runs if isinstance(x, dict)][:30]
    return {
        "automations_enabled": enabled,
        "automation_last_run": last_clean,
        "automation_runs": runs_clean,
    }


def is_automation_enabled(prefs: dict[str, Any] | None, recipe_id: str) -> bool:
    norm = normalize_automation_prefs(prefs)
    return bool(norm["automations_enabled"].get(recipe_id, False))


def list_recipes(prefs: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    norm = normalize_automation_prefs(prefs)
    out = []
    for r in RECIPES:
        rid = r["id"]
        out.append(
            {
                **r,
                "enabled": bool(norm["automations_enabled"].get(rid, r["default_enabled"])),
                "last_run_at": norm["automation_last_run"].get(rid) or "",
            }
        )
    return out


def apply_automation_patch(
    prefs: dict[str, Any],
    *,
    recipe_id: str = "",
    enabled: Optional[bool] = None,
) -> dict[str, Any]:
    norm = normalize_automation_prefs(prefs)
    en = dict(norm["automations_enabled"])
    rid = (recipe_id or "").strip()
    if rid and rid in en and enabled is not None:
        en[rid] = bool(enabled)
    return {
        "automations_enabled": en,
        "automation_last_run": norm["automation_last_run"],
        "automation_runs": norm["automation_runs"],
    }


def _append_run(
    prefs: dict[str, Any],
    *,
    recipe_id: str,
    ok: bool,
    summary: str,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    norm = normalize_automation_prefs(prefs)
    now = _iso_now()
    last = dict(norm["automation_last_run"])
    last[recipe_id] = now
    run = {
        "id": f"run_{int(time.time())}_{recipe_id[:12]}",
        "recipe_id": recipe_id,
        "at": now,
        "ok": bool(ok),
        "summary": (summary or "")[:240],
        "details": details or {},
    }
    runs = [run, *norm["automation_runs"]][:30]
    return {
        "automations_enabled": norm["automations_enabled"],
        "automation_last_run": last,
        "automation_runs": runs,
    }


async def run_daily_hotspot_candidates(
    *,
    user_id: str,
    email: str = "",
    prefs: Optional[dict[str, Any]] = None,
    per_page: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scan hotspot board → create draft Content Projects for top items."""
    from cn_social_agent.content.connectors import enabled_hotspot_sources
    from cn_social_agent.content import service as cps
    from cn_social_agent.tools.hotspots import tool_scan_hotspot_board

    allowed = enabled_hotspot_sources(prefs)
    if not allowed:
        return {
            "ok": False,
            "error": "热点看板连接器未开启或无启用源",
            "created": [],
            "count": 0,
        }

    scan = await tool_scan_hotspot_board(
        per_page=max(1, min(10, int(per_page or 5))),
        source="all",
        allowed_sources=allowed,
    )
    board = list(scan.get("board") or [])[: max(1, min(10, int(per_page or 5)))]
    if not board:
        return {
            "ok": True,
            "created": [],
            "count": 0,
            "hint": scan.get("hint") or "热点榜为空",
            "dry_run": dry_run,
        }

    created: list[dict[str, Any]] = []
    if dry_run:
        for item in board:
            created.append(
                {
                    "topic": str(item.get("title") or item.get("full_name") or "")[:120],
                    "url": str(item.get("url") or "")[:200],
                    "dry_run": True,
                }
            )
        return {"ok": True, "created": created, "count": len(created), "dry_run": True}

    for item in board:
        title = str(item.get("title") or item.get("full_name") or "").strip()
        if not title:
            continue
        why = str(item.get("why") or "")[:400]
        url = str(item.get("url") or "").strip()
        notes = "\n".join(
            p
            for p in (
                f"为何值得做：{why}" if why else "",
                f"来源：{item.get('source') or ''}",
                f"链接：{url}" if url else "",
                str(item.get("description") or "")[:800],
            )
            if p
        )
        proj = await cps.create_project(
            topic=title,
            user_id=user_id,
            email=email,
            category="product_explain",
            research_notes=notes,
            source={
                "kind": "hotspot",
                "url": url,
                "title": title,
                "name": str(item.get("source") or ""),
            },
            why=why,
            topic_key=str(item.get("topic_key") or "")[:120],
            url=url,
        )
        # mark as automation draft
        await cps.patch_project(
            proj["id"],
            {"status": "candidate"},
            user_id=user_id,
            email=email,
        )
        created.append(
            {
                "id": proj["id"],
                "short_topic": proj.get("short_topic"),
                "topic": proj.get("topic"),
                "url": url,
            }
        )
    return {"ok": True, "created": created, "count": len(created), "dry_run": False}


async def run_recipe(
    recipe_id: str,
    *,
    user_id: str,
    email: str = "",
    prefs: Optional[dict[str, Any]] = None,
    dry_run: bool = False,
    per_page: int = 5,
) -> dict[str, Any]:
    rid = (recipe_id or "").strip()
    known = {r["id"] for r in RECIPES}
    if rid not in known:
        return {"ok": False, "error": f"unknown recipe: {rid}"}

    if rid == "daily_hotspot_candidates":
        result = await run_daily_hotspot_candidates(
            user_id=user_id,
            email=email,
            prefs=prefs,
            per_page=per_page,
            dry_run=dry_run,
        )
    elif rid == "handoff_seed_research":
        result = {
            "ok": True,
            "hint": "交接种子证据由工坊打开时自动执行（可在此开关偏好）",
            "enabled": is_automation_enabled(prefs, rid),
        }
    elif rid == "quality_pass_mark_export":
        result = {
            "ok": True,
            "hint": "成刊质检通过后会自动在内容项目上标记 export_ready",
            "enabled": is_automation_enabled(prefs, rid),
        }
    else:
        result = {"ok": False, "error": "not implemented"}

    summary = ""
    if rid == "daily_hotspot_candidates":
        summary = f"创建 {result.get('count') or 0} 个候选项目"
        if result.get("error"):
            summary = str(result["error"])[:160]
    else:
        summary = str(result.get("hint") or "ok")[:160]

    prefs_patch = _append_run(
        prefs or {},
        recipe_id=rid,
        ok=bool(result.get("ok")),
        summary=summary,
        details={"count": result.get("count"), "dry_run": dry_run},
    )
    return {**result, "recipe_id": rid, "prefs_patch": prefs_patch}
