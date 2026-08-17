"""Connector settings API (ingest / publish toggles)."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.api.prefs import merge_prefs
from cn_social_agent.content.connectors import (
    apply_connector_patch,
    enrich_catalog,
)


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


@require_user
async def list_connectors(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    try:
        prefs = await state.store.get_user_prefs(user["id"])
    except Exception:  # noqa: BLE001
        prefs = {}
    oauth = await _oauth_map(request)
    rows = await enrich_catalog(prefs if isinstance(prefs, dict) else {}, oauth_status=oauth)
    return web.json_response({"connectors": rows, "count": len(rows)})


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
