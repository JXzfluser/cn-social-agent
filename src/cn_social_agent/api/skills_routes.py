from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user


@require_user
async def list_skills(request: web.Request) -> web.Response:
    state = get_state(request)
    state.skills.scan()
    pack = getattr(state, "pack", None)
    if pack is not None:
        from cn_social_agent.packs.loader import apply_pack_skills

        apply_pack_skills(state.skills, pack)
    bindings = await state.store.get_skill_bindings(request["user"]["id"])
    rows = []
    for skill in state.skills.list_skills():
        if skill["id"] in bindings:
            skill["enabled"] = bindings[skill["id"]]
        rows.append(skill)
    return web.json_response({"skills": rows})


@require_user
async def patch_skill(request: web.Request) -> web.Response:
    state = get_state(request)
    skill_id = request.match_info["id"]
    body = await request.json()
    enabled = bool(body.get("enabled", True))
    skill = state.skills.set_enabled(skill_id, enabled)
    if not skill:
        return web.json_response({"error": "not found"}, status=404)
    await state.store.set_skill_enabled(request["user"]["id"], skill_id, enabled)
    return web.json_response(skill.to_dict())


def setup_skills_routes(app: web.Application) -> None:
    app.router.add_get("/api/skills", list_skills)
    app.router.add_patch("/api/skills/{id}", patch_skill)
