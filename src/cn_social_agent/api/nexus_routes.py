"""Nexus expert workbench — HTTP API.

Every handler that touches tenant data is wrapped by :func:`nexus_user`, which:

1. validates the bearer token (reusing :func:`deps.require_user`),
2. binds a :class:`TenantContext` carrying the **end-user** JWT and locale, and
3. tears the context down afterwards.

Because :class:`cn_social_agent.core.db.TenantDB` and
:class:`cn_social_agent.core.ai.TenantAI` both read that context, the routes
never pass a user id around by hand — isolation is a property of the ambient
context, exactly as it is in the database. The routes are thin: all the real
logic (lifecycle, review, isolation) lives in
:mod:`cn_social_agent.tasks.engine` and :mod:`cn_social_agent.core`.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.core.db import RlsViolation, TenantDB
from cn_social_agent.core.events import bus, task_stream
from cn_social_agent.core.i18n import available_locales, dictionary
from cn_social_agent.core.tenant import (
    DEFAULT_LOCALE,
    TenantContext,
    bind,
    clear,
    require,
)
from cn_social_agent.experts.models import Expert
from cn_social_agent.tasks.engine import TaskEngine, TaskError

logger = logging.getLogger(__name__)


# ── tenant binding ──────────────────────────────────────────────────


def _engine(request: web.Request) -> TaskEngine:
    state = get_state(request)
    return TaskEngine(client=state.nexus_client, registry=state.nexus_registry)


async def _profile_locale(request: web.Request, user_id: str) -> Optional[str]:
    state = get_state(request)
    try:
        db = TenantDB(state.nexus_client)
        row = await db.get_by_id("wb_user_profiles", user_id, id_column="user_id")
        if row and row.get("locale"):
            return str(row["locale"])
    except Exception:  # noqa: BLE001
        pass
    return None


def nexus_user(handler):
    """Authenticate, bind the tenant (with locale), run, then clear context."""

    @require_user
    async def wrapped(request: web.Request) -> web.Response:
        state = get_state(request)
        user = request["user"]
        token = request["access_token"]
        # Header/query first, then stored profile, then default.
        explicit = (
            request.query.get("locale")
            or request.headers.get("X-Locale")
            or request.headers.get("x-locale")
        )
        bind(TenantContext(user_id=user["id"], email=user.get("email", ""), token=token, locale=DEFAULT_LOCALE))
        try:
            if not explicit:
                explicit = await _profile_locale(request, user["id"])
            locale = explicit or DEFAULT_LOCALE
            bind(TenantContext(user_id=user["id"], email=user.get("email", ""), token=token, locale=locale))
            return await handler(request)
        finally:
            clear()

    return wrapped


# ── error mapping ──────────────────────────────────────────────────


def _error(exc: Exception, status: int = 400) -> web.Response:
    msg = str(exc)
    return web.json_response({"error": msg}, status=status)


# ── experts ─────────────────────────────────────────────────────────


@nexus_user
async def list_experts(request: web.Request) -> web.Response:
    state = get_state(request)
    locale = require().locale
    experts = state.nexus_registry.summary(locale) if state.nexus_registry else []
    return web.json_response({"experts": experts, "locale": locale})


@nexus_user
async def get_expert(request: web.Request) -> web.Response:
    state = get_state(request)
    locale = require().locale
    expert_id = request.match_info["id"]
    expert: Optional[Expert] = state.nexus_registry.get(expert_id) if state.nexus_registry else None
    if expert is None:
        return web.json_response({"error": "unknown expert"}, status=404)
    return web.json_response({"expert": expert.to_dict(locale), "locale": locale})


# ── tasks ────────────────────────────────────────────────────────────


@nexus_user
async def create_task(request: web.Request) -> web.Response:
    body = await request.json()
    expert_id = (body.get("expert_id") or "").strip()
    title = (body.get("title") or "").strip()
    brief = (body.get("brief") or "").strip()
    locale = body.get("locale") or require().locale
    if not expert_id:
        return web.json_response({"error": "expert_id required"}, status=400)
    engine = _engine(request)
    try:
        task = await engine.create_task(expert_id, title, brief, locale=locale)
    except TaskError as exc:
        return _error(exc, 400)
    except KeyError as exc:
        return web.json_response({"error": f"unknown expert: {expert_id}"}, status=404)
    return web.json_response({"task": task.to_dict()}, status=201)


@nexus_user
async def list_tasks(request: web.Request) -> web.Response:
    engine = _engine(request)
    status = request.query.get("status")
    try:
        tasks = await engine.list_tasks(status=status or None, limit=100, offset=0)
    except RlsViolation as exc:
        return _error(exc, 403)
    return web.json_response({"tasks": [t.to_dict() for t in tasks]})


@nexus_user
async def get_task(request: web.Request) -> web.Response:
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        task = await engine.get_task(task_id, with_detail=True)
    except TaskError as exc:
        return _error(exc, 404)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"task": task.to_dict(with_detail=True)})


@nexus_user
async def run_task(request: web.Request) -> web.Response:
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        task = await engine.run_task(task_id)
    except TaskError as exc:
        return _error(exc, 400)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"task": task.to_dict(with_detail=True)})


@nexus_user
async def review_task(request: web.Request) -> web.Response:
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        task = await engine.review_task(task_id)
    except TaskError as exc:
        return _error(exc, 400)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"task": task.to_dict(with_detail=True)})


@nexus_user
async def decide_task(request: web.Request) -> web.Response:
    body = await request.json()
    decision = (body.get("decision") or "").strip().lower()
    note = (body.get("note") or "").strip()
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        task = await engine.decide(task_id, decision, note)
    except TaskError as exc:
        return _error(exc, 400)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"task": task.to_dict(with_detail=True)})


@nexus_user
async def add_task_message(request: web.Request) -> web.Response:
    """Task follow-up: the user adds a message to a live task (WorkBuddy-style)."""
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        return web.json_response({"error": "content required"}, status=400)
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        await engine.add_user_message(task_id, content)
    except TaskError as exc:
        return _error(exc, 404)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"success": True})


@nexus_user
async def rename_task(request: web.Request) -> web.Response:
    """Rename a task (WorkBuddy-style list management)."""
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return web.json_response({"error": "title required"}, status=400)
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        task = await engine.get_task(task_id, with_detail=False)  # ownership check
        from cn_social_agent.tasks.engine import TASKS_TABLE, utcnow
        await engine.db.update_by_id(
            TASKS_TABLE, task.id, {"title": title[:300], "updated_at": utcnow()}
        )
    except TaskError as exc:
        return _error(exc, 404)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"success": True, "title": title[:300]})


@nexus_user
async def archive_task(request: web.Request) -> web.Response:
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        task = await engine.archive(task_id)
    except TaskError as exc:
        return _error(exc, 400)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"task": task.to_dict(with_detail=True)})


@nexus_user
async def delete_task(request: web.Request) -> web.Response:
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        await engine.delete_task(task_id)
    except TaskError as exc:
        return _error(exc, 404)
    except RlsViolation as exc:
        return _error(exc, 404)
    return web.json_response({"success": True})


# ── live trace (SSE) ────────────────────────────────────────────────


@nexus_user
async def stream_task(request: web.Request) -> web.StreamResponse:
    tenant_id = require().user_id
    task_id = request.match_info["id"]
    stream = task_stream(tenant_id, task_id)
    resp = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
    await resp.prepare(request)

    async def _pump():
        async for event in bus().stream(stream):
            try:
                await resp.write(f"data: {event.to_json()}\n\n".encode("utf-8"))
            except Exception:  # noqa: BLE001
                break

    try:
        await _pump()
    except (aiohttp.ClientDisconnectedError, ConnectionResetError):  # pragma: no cover
        pass
    finally:
        try:
            await resp.write_eof()
        except Exception:  # noqa: BLE001
            pass
    return resp


# ── profile / locale / i18n ─────────────────────────────────────────


@nexus_user
async def update_profile(request: web.Request) -> web.Response:
    body = await request.json()
    state = get_state(request)
    user_id = require().user_id
    fields: dict[str, Any] = {}
    if "locale" in body and body["locale"]:
        fields["locale"] = str(body["locale"])
    if "display_name" in body:
        fields["display_name"] = str(body["display_name"])
    if "settings" in body and isinstance(body["settings"], dict):
        fields["settings"] = body["settings"]
    if not fields:
        return web.json_response({"success": True, "profile": {"locale": require().locale}})
    db = TenantDB(state.nexus_client)
    try:
        await db.upsert("wb_user_profiles", {"user_id": user_id, **fields}, on_conflict="user_id")
    except RlsViolation as exc:
        return _error(exc, 403)
    return web.json_response({"success": True, "profile": {"locale": fields.get("locale", require().locale)}})


@nexus_user
async def list_locales(request: web.Request) -> web.Response:
    return web.json_response({"locales": available_locales(), "current": require().locale})


@nexus_user
async def i18n_dict(request: web.Request) -> web.Response:
    locale = request.match_info.get("locale") or require().locale
    return web.json_response({"locale": locale, "messages": dictionary(locale)})


@nexus_user
async def nexus_health(request: web.Request) -> web.Response:
    state = get_state(request)
    backend = "insforge" if getattr(state.insforge, "enabled", False) else (
        "memory" if state.nexus_client.__class__.__name__ == "MemoryInsForgeClient" else "insforge"
    )
    return web.json_response({
        "ok": True,
        "backend": backend,
        "experts": len(state.nexus_registry or []),
        "user": require().user_id,
        "isolation": "rls",
    })


# ── wiring ──────────────────────────────────────────────────────────


def setup_nexus_routes(app: web.Application) -> None:
    app.router.add_get("/api/nexus/experts", list_experts)
    app.router.add_get("/api/nexus/experts/{id}", get_expert)
    app.router.add_post("/api/nexus/tasks", create_task)
    app.router.add_get("/api/nexus/tasks", list_tasks)
    app.router.add_get("/api/nexus/tasks/{id}", get_task)
    app.router.add_patch("/api/nexus/tasks/{id}", rename_task)
    app.router.add_post("/api/nexus/tasks/{id}/run", run_task)
    app.router.add_post("/api/nexus/tasks/{id}/messages", add_task_message)
    app.router.add_post("/api/nexus/tasks/{id}/review", review_task)
    app.router.add_post("/api/nexus/tasks/{id}/decide", decide_task)
    app.router.add_post("/api/nexus/tasks/{id}/archive", archive_task)
    app.router.add_delete("/api/nexus/tasks/{id}", delete_task)
    app.router.add_get("/api/nexus/stream/{id}", stream_task)
    app.router.add_put("/api/nexus/profile", update_profile)
    app.router.add_get("/api/nexus/locales", list_locales)
    app.router.add_get("/api/i18n/{locale}", i18n_dict)
    app.router.add_get("/api/nexus/health", nexus_health)
