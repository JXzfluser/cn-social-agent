"""Automations API (S3)."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.api.prefs import merge_prefs
from cn_social_agent.content.automations import (
    apply_automation_patch,
    list_recipes,
    normalize_automation_prefs,
    run_recipe,
)


@require_user
async def list_automations(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    try:
        prefs = await state.store.get_user_prefs(user["id"])
    except Exception:  # noqa: BLE001
        prefs = {}
    if not isinstance(prefs, dict):
        prefs = {}
    recipes = list_recipes(prefs)
    norm = normalize_automation_prefs(prefs)
    return web.json_response(
        {
            "recipes": recipes,
            "runs": norm["automation_runs"][:10],
            "count": len(recipes),
        }
    )


@require_user
async def patch_automation(request: web.Request) -> web.Response:
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

    fragment = apply_automation_patch(
        prefs,
        recipe_id=str(body.get("id") or body.get("recipe_id") or "").strip(),
        enabled=body.get("enabled") if "enabled" in body else None,
    )
    if isinstance(body.get("automations_enabled"), dict):
        fragment["automations_enabled"] = {
            **fragment["automations_enabled"],
            **{str(k): bool(v) for k, v in body["automations_enabled"].items()},
        }
    merged = merge_prefs(prefs, fragment)
    await state.store.upsert_user_prefs(user["id"], merged)
    return web.json_response(
        {"ok": True, "recipes": list_recipes(merged), "prefs": fragment}
    )


@require_user
async def run_automation(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}
    recipe_id = str(
        body.get("id") or body.get("recipe_id") or request.match_info.get("id") or ""
    ).strip()
    dry_run = bool(body.get("dry_run"))
    try:
        per_page = int(body.get("per_page") or 5)
    except (TypeError, ValueError):
        per_page = 5

    try:
        prefs = await state.store.get_user_prefs(user["id"])
    except Exception:  # noqa: BLE001
        prefs = {}
    if not isinstance(prefs, dict):
        prefs = {}

    out = await run_recipe(
        recipe_id,
        user_id=user["id"],
        email=str(user.get("email") or ""),
        prefs=prefs,
        dry_run=dry_run,
        per_page=per_page,
    )
    patch = out.pop("prefs_patch", None)
    if isinstance(patch, dict):
        merged = merge_prefs(prefs, patch)
        await state.store.upsert_user_prefs(user["id"], merged)
        out["last_run_at"] = (patch.get("automation_last_run") or {}).get(recipe_id)
        out["runs"] = (patch.get("automation_runs") or [])[:5]
    status = 200 if out.get("ok") else 400
    return web.json_response(out, status=status)


def setup_automation_routes(app: web.Application) -> None:
    app.router.add_get("/api/automations", list_automations)
    app.router.add_patch("/api/automations", patch_automation)
    app.router.add_post("/api/automations/run", run_automation)
    app.router.add_post("/api/automations/{id}/run", run_automation)
