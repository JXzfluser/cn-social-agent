"""Connector settings API (ingest / publish toggles + user-defined connectors)."""

from __future__ import annotations

import uuid

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.api.prefs import merge_prefs
from cn_social_agent.content.connectors import (
    apply_connector_patch,
    enrich_catalog,
)

IDEA_CONNECTORS = [
    {
        "id": "github_trending",
        "label": "GitHub Trending",
        "direction": "ingest",
        "description": "GitHub 热门项目与开发者动态",
        "kind": "idea_source",
        "category": "idea",
    },
    {
        "id": "hackernews",
        "label": "Hacker News",
        "direction": "ingest",
        "description": "技术社区热门话题",
        "kind": "idea_source",
        "category": "idea",
    },
    {
        "id": "v2ex",
        "label": "V2EX",
        "direction": "ingest",
        "description": "中文技术社区讨论",
        "kind": "idea_source",
        "category": "idea",
    },
    {
        "id": "sspai",
        "label": "少数派",
        "direction": "ingest",
        "description": "效率工具与数字生活",
        "kind": "idea_source",
        "category": "idea",
    },
    {
        "id": "zhihu",
        "label": "知乎热榜",
        "direction": "ingest",
        "description": "知识分享与深度讨论",
        "kind": "idea_source",
        "category": "idea",
    },
    {
        "id": "competitor",
        "label": "竞品监控",
        "direction": "ingest",
        "description": "竞品内容与动态追踪",
        "kind": "idea_source",
        "category": "idea",
    },
    {
        "id": "pain_point",
        "label": "用户痛点",
        "direction": "ingest",
        "description": "用户问题与需求挖掘",
        "kind": "idea_source",
        "category": "idea",
    },
    {
        "id": "knowledge_base",
        "label": "知识库",
        "direction": "ingest",
        "description": "本地知识积累与管理",
        "kind": "idea_source",
        "category": "idea",
    },
]


async def _oauth_map(request: web.Request) -> dict:
    """Best-effort platform auth status without failing the catalog."""
    out: dict = {}
    user = request["user"]
    try:
        from cn_social_agent.platforms.tokens import load_platform_config

        for plat in ("weixin", "toutiao", "douyin", "xiaohongshu"):
            try:
                cfg = await load_platform_config(plat)
                connected = False
                if isinstance(cfg, dict):
                    for k in ("access_token", "app_id", "appId", "cookie", "refresh_token"):
                        if str(cfg.get(k) or "").strip():
                            connected = True
                            break
                out[plat] = {"ok": connected, "connected": connected}
            except Exception:  # noqa: BLE001
                out[plat] = {"ok": False}
    except Exception:  # noqa: BLE001
        pass
    return out


async def _idea_connector_status(request: web.Request) -> dict:
    out: dict = {}
    try:
        from cn_social_agent.idea_engine.connectors import manager
        types = manager.list_connector_types()
        for t in types:
            out[t["id"]] = {
                "status": t.get("status", "ready"),
                "status_label": "可用" if t.get("status") == "ready" else t.get("status", "未知"),
                "enabled": True,
            }
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(f"Failed to load Idea connectors: {e}")
    return out


@require_user
async def list_connectors(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    try:
        prefs = await state.store.get_user_prefs(user["id"])
    except Exception:  # noqa: BLE001
        prefs = {}
    oauth = await _oauth_map(request)
    idea_status = await _idea_connector_status(request)
    
    global_rows = await enrich_catalog(prefs if isinstance(prefs, dict) else {}, oauth_status=oauth)
    
    idea_rows = []
    for ic in IDEA_CONNECTORS:
        status_info = idea_status.get(ic["id"], {})
        idea_rows.append({
            **ic,
            "enabled": status_info.get("enabled", True),
            "status": status_info.get("status", "ready"),
            "status_label": status_info.get("status_label", "可用"),
        })
    
    all_rows = global_rows + idea_rows

    # User-defined connectors (stored per user in prefs, isolated by auth).
    try:
        prefs_map = prefs if isinstance(prefs, dict) else {}
        customs = prefs_map.get("custom_connectors")
        enabled_map = prefs_map.get("connectors_enabled")
        enabled_map = enabled_map if isinstance(enabled_map, dict) else {}
        for row in customs if isinstance(customs, list) else []:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            all_rows.append({
                **row,
                "enabled": bool(enabled_map.get(str(row["id"]), True)),
                "status": "ready",
                "status_label": "可用",
            })
    except Exception:  # noqa: BLE001
        pass

    return web.json_response({"connectors": all_rows, "count": len(all_rows)})


@require_user
async def create_custom_connector(request: web.Request) -> web.Response:
    """Register a user-defined connector (ingest or publish)."""
    state = get_state(request)
    user = request["user"]
    body = await request.json() if request.can_read_body else {}
    label = str((body or {}).get("label") or "").strip()
    if not label:
        return web.json_response({"error": "label required"}, status=400)
    direction = str((body or {}).get("direction") or "ingest").strip().lower()
    if direction not in ("ingest", "publish"):
        direction = "ingest"
    description = str((body or {}).get("description") or "").strip()
    url = str((body or {}).get("url") or "").strip()

    try:
        prefs = await state.store.get_user_prefs(user["id"])
    except Exception:  # noqa: BLE001
        prefs = {}
    prefs = prefs if isinstance(prefs, dict) else {}
    customs = prefs.get("custom_connectors")
    customs = [r for r in customs if isinstance(r, dict)] if isinstance(customs, list) else []
    row = {
        "id": f"custom_{uuid.uuid4().hex[:10]}",
        "label": label[:80],
        "direction": direction,
        "description": description[:200],
        "url": url[:300],
        "kind": "custom",
        "category": "custom",
        "custom": True,
    }
    customs.append(row)
    merged = merge_prefs(prefs, {"custom_connectors": customs})
    await state.store.upsert_user_prefs(user["id"], merged)
    return web.json_response({"ok": True, "connector": row}, status=201)


@require_user
async def delete_custom_connector(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    cid = request.match_info["id"]
    try:
        prefs = await state.store.get_user_prefs(user["id"])
    except Exception:  # noqa: BLE001
        prefs = {}
    prefs = prefs if isinstance(prefs, dict) else {}
    customs = prefs.get("custom_connectors")
    customs = [r for r in customs if isinstance(r, dict)] if isinstance(customs, list) else []
    kept = [r for r in customs if str(r.get("id")) != cid]
    if len(kept) == len(customs):
        return web.json_response({"error": "not found"}, status=404)
    merged = merge_prefs(prefs, {"custom_connectors": kept})
    await state.store.upsert_user_prefs(user["id"], merged)
    return web.json_response({"ok": True})


@require_user
async def patch_connector(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}
    try:
        prefs = await state.store.get_user_prefs(user["id"])
    except Exception:  # noqa: BLE001
        prefs = {}
    if not isinstance(prefs, dict):
        prefs = {}

    fragment = apply_connector_patch(
        prefs,
        connector_id=str(body.get("id") or body.get("connector_id") or "").strip(),
        enabled=body.get("enabled") if "enabled" in body else None,
        hotspot_source_id=str(body.get("hotspot_source_id") or body.get("source_id") or "").strip(),
        hotspot_enabled=body.get("hotspot_enabled")
        if "hotspot_enabled" in body
        else (body.get("source_enabled") if "source_enabled" in body else None),
    )
    # Also accept bulk maps
    if isinstance(body.get("connectors_enabled"), dict):
        fragment["connectors_enabled"] = {
            **fragment["connectors_enabled"],
            **{str(k): bool(v) for k, v in body["connectors_enabled"].items()},
        }
    if isinstance(body.get("hotspot_sources_enabled"), dict):
        fragment["hotspot_sources_enabled"] = {
            **fragment["hotspot_sources_enabled"],
            **{str(k): bool(v) for k, v in body["hotspot_sources_enabled"].items()},
        }

    merged = merge_prefs(prefs, fragment)
    await state.store.upsert_user_prefs(user["id"], merged)
    oauth = await _oauth_map(request)
    rows = await enrich_catalog(merged, oauth_status=oauth)
    return web.json_response({"ok": True, "connectors": rows, "prefs": fragment})


def setup_connector_routes(app: web.Application) -> None:
    app.router.add_get("/api/connectors", list_connectors)
    app.router.add_patch("/api/connectors", patch_connector)
    app.router.add_post("/api/connectors/custom", create_custom_connector)
    app.router.add_delete("/api/connectors/custom/{id}", delete_custom_connector)
