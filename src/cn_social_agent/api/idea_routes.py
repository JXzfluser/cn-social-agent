"""Idea Engine API routes."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.deps import require_user
from cn_social_agent.idea_engine.engine import engine
from cn_social_agent.idea_engine.fragments import Fragment, fragment_store
from cn_social_agent.idea_engine.integrator import integrator
from cn_social_agent.idea_engine.library import LibraryItem, library_store


routes = web.RouteTableDef()


@routes.get("/api/idea/materials")
@require_user
async def list_materials(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    page = int(request.query.get("page", 1))
    page_size = int(request.query.get("page_size", 20))

    await engine.ensure_loaded(user_id)
    result = engine.get_materials(user_id, page, page_size)
    return web.json_response(result)


@routes.get("/api/idea/cards")
@require_user
async def list_cards(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    status = request.query.get("status")
    page = int(request.query.get("page", 1))
    page_size = int(request.query.get("page_size", 20))

    await engine.ensure_loaded(user_id)
    result = engine.get_cards(user_id, status, page, page_size)
    return web.json_response(result)


@routes.post("/api/idea/sync")
@require_user
async def sync_materials(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    data = await request.json()
    connector_ids = data.get("connector_ids")

    materials = await engine.sync_materials(user_id, connector_ids)

    return web.json_response({
        "synced": len(materials),
        "materials": [engine._material_to_dict(m) for m in materials],
    })


@routes.post("/api/idea/sync/{connector_id}")
@require_user
async def sync_single_connector(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    connector_id = request.match_info["connector_id"]

    materials = await engine.fetch_single_connector(user_id, connector_id)

    return web.json_response({
        "synced": len(materials),
        "materials": [engine._material_to_dict(m) for m in materials],
    })


@routes.post("/api/idea/generate")
@require_user
async def generate_cards(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    data = await request.json()
    material_ids = data.get("material_ids")

    cards = await engine.generate_cards(user_id, material_ids)

    return web.json_response({
        "generated": len(cards),
        "cards": [engine._card_to_dict(c) for c in cards],
    })


@routes.post("/api/idea/cards/{card_id}/select")
@require_user
async def select_card(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    email = str(request["user"].get("email") or "")
    card_id = request.match_info["card_id"]
    data = await request.json() if request.content_length else {}
    create_project = data.get("create_project", True)

    result = await engine.select_card(user_id, card_id)
    if not result:
        return web.json_response({"error": "Card not found"}, status=404)

    if create_project:
        material_id = result.get("material_id")
        material = None
        if material_id:
            for m in engine.materials.get(user_id, []):
                if m.id == material_id:
                    material = engine._material_to_dict(m)
                    break

        integration_result = await integrator.handle_card_selected(
            user_id, result, material, email=email
        )
        result.update(integration_result)
        project_id = str(result.get("project_id") or "")
        if project_id:
            await engine.set_card_project(user_id, card_id, project_id)

    return web.json_response(result)


@routes.post("/api/idea/cards/{card_id}/reject")
@require_user
async def reject_card(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    card_id = request.match_info["card_id"]

    success = await engine.reject_card(user_id, card_id)
    if not success:
        return web.json_response({"error": "Card not found"}, status=404)

    return web.json_response({"ok": True})


@routes.post("/api/idea/cards/{card_id}/feedback")
@require_user
async def feedback_card(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    card_id = request.match_info["card_id"]
    data = await request.json()
    feedback = data.get("feedback", "")

    if feedback not in ("good", "bad", ""):
        return web.json_response({"error": "Invalid feedback"}, status=400)

    success = await engine.feedback_card(user_id, card_id, feedback)
    if not success:
        return web.json_response({"error": "Card not found"}, status=404)

    return web.json_response({"ok": True})


@routes.get("/api/idea/connectors")
@require_user
async def list_connectors(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    status = engine.get_connector_status(user_id)
    return web.json_response({"connectors": status})


@routes.get("/api/idea/connectors/types")
@require_user
async def list_connector_types(request: web.Request) -> web.Response:
    from cn_social_agent.idea_engine.connectors import manager

    types = manager.list_connector_types()
    return web.json_response({"types": types})


@routes.get("/api/idea/fragments")
@require_user
async def list_fragments(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    page = int(request.query.get("page", 1))
    page_size = int(request.query.get("page_size", 20))

    result = fragment_store.list(user_id, page, page_size)
    return web.json_response(result)


@routes.post("/api/idea/fragments")
@require_user
async def create_fragment(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    data = await request.json()
    content = data.get("content", "").strip()

    if not content:
        return web.json_response({"error": "Content required"}, status=400)

    fragment = Fragment.create(user_id, content)
    fragment_store.add(fragment)

    return web.json_response(fragment.to_dict(), status=201)


@routes.delete("/api/idea/fragments/{fragment_id}")
@require_user
async def delete_fragment(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    fragment_id = request.match_info["fragment_id"]

    success = fragment_store.delete(user_id, fragment_id)
    if not success:
        return web.json_response({"error": "Fragment not found"}, status=404)

    return web.json_response({"ok": True})


@routes.get("/api/idea/library")
@require_user
async def list_library(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    page = int(request.query.get("page", 1))
    page_size = int(request.query.get("page_size", 20))

    result = library_store.list(user_id, page, page_size)
    return web.json_response(result)


@routes.post("/api/idea/library")
@require_user
async def add_to_library(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    data = await request.json()
    card_id = data.get("card_id", "")
    title = data.get("title", "")
    hook = data.get("hook", "")
    tags = data.get("tags", [])
    notes = data.get("notes", "")

    if not card_id or not title:
        return web.json_response({"error": "card_id and title required"}, status=400)

    item = LibraryItem(
        id=f"lib:{user_id}:{card_id}",
        user_id=user_id,
        card_id=card_id,
        title=title,
        hook=hook,
        tags=tags,
        notes=notes,
    )
    library_store.add(item)

    return web.json_response(item.to_dict(), status=201)


@routes.delete("/api/idea/library/{item_id}")
@require_user
async def remove_from_library(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    item_id = request.match_info["item_id"]

    success = library_store.delete(user_id, item_id)
    if not success:
        return web.json_response({"error": "Item not found"}, status=404)

    return web.json_response({"ok": True})


@routes.put("/api/idea/library/{item_id}")
@require_user
async def update_library_item(request: web.Request) -> web.Response:
    user_id = request["user"]["id"]
    item_id = request.match_info["item_id"]
    data = await request.json()

    tags = data.get("tags")
    notes = data.get("notes")

    success = library_store.update(user_id, item_id, tags, notes)
    if not success:
        return web.json_response({"error": "Item not found"}, status=404)

    item = library_store.get(user_id, item_id)
    return web.json_response(item.to_dict() if item else {})
