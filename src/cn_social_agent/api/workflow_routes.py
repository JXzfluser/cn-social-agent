from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _gen_id() -> str:
    return str(uuid.uuid4())


@require_user
async def list_workflows(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"workflows": [], "templates": []})

    try:
        rows = await db.query(
            "wb_workflows",
            filters={"user_id": f"eq.{user['id']}"},
            order="created_at.desc",
        )
    except Exception:
        rows = []

    workflows = []
    for r in (rows or []):
        workflows.append({
            "id": r.get("id"),
            "name": r.get("name", ""),
            "description": r.get("description", ""),
            "nodes": r.get("nodes", []),
            "edges": r.get("edges", []),
            "trigger": r.get("trigger_config", {}),
            "enabled": bool(r.get("enabled", True)),
            "createdAt": r.get("created_at", ""),
            "updatedAt": r.get("updated_at", ""),
        })

    try:
        tpl_rows = await db.query("wb_workflow_templates", limit=50)
    except Exception:
        tpl_rows = []

    templates = []
    for t in tpl_rows or []:
        templates.append({
            "id": t.get("id"),
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "category": t.get("category", "content"),
            "nodes": t.get("nodes", []),
            "edges": t.get("edges", []),
            "thumbnail": t.get("thumbnail"),
        })

    return web.json_response({"workflows": workflows, "templates": templates})


@require_user
async def get_workflow(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    workflow_id = request.match_info["id"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}", "user_id": f"eq.{user['id']}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "not found"}, status=404)

    r = rows[0]
    return web.json_response({
        "id": r.get("id"),
        "name": r.get("name", ""),
        "description": r.get("description", ""),
        "nodes": r.get("nodes", []),
        "edges": r.get("edges", []),
        "trigger": r.get("trigger_config", {}),
        "enabled": bool(r.get("enabled", True)),
        "createdAt": r.get("created_at", ""),
        "updatedAt": r.get("updated_at", ""),
    })


@require_user
async def create_workflow(request: web.Request) -> web.Response:
    """POST /api/workflows — create a new workflow."""
    state = get_state(request)
    user = request["user"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}

    name = (body.get("name") or "Untitled Workflow").strip()
    description = (body.get("description") or "").strip()
    nodes = body.get("nodes") or []
    edges = body.get("edges") or []
    trigger = body.get("trigger") or {"type": "manual", "config": {}}

    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []

    workflow_id = _gen_id()
    now = _iso_now()

    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        await db.create("wb_workflows", {
            "id": workflow_id,
            "user_id": user["id"],
            "name": name,
            "description": description,
            "nodes": nodes,
            "edges": edges,
            "trigger_config": trigger,
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({
        "id": workflow_id,
        "name": name,
        "description": description,
        "nodes": nodes,
        "edges": edges,
        "trigger": trigger,
        "enabled": True,
        "createdAt": now,
        "updatedAt": now,
    }, status=201)


@require_user
async def update_workflow(request: web.Request) -> web.Response:
    """PUT /api/workflows/:id — update workflow."""
    state = get_state(request)
    user = request["user"]
    workflow_id = request.match_info["id"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}

    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}", "user_id": f"eq.{user['id']}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "not found"}, status=404)

    updates: dict[str, Any] = {"updated_at": _iso_now()}
    for field in ("name", "description", "nodes", "edges", "enabled"):
        if field in body:
            if field == "nodes" or field == "edges":
                updates[field] = body[field] if isinstance(body[field], list) else []
            elif field == "enabled":
                updates[field] = bool(body[field])
            else:
                updates[field] = str(body[field])[:500]

    if "trigger" in body:
        updates["trigger_config"] = body["trigger"] if isinstance(body["trigger"], dict) else {}

    try:
        await db.update(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}"},
            data=updates,
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    try:
        rows = await db.query(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "not found after update"}, status=500)

    r = rows[0]
    return web.json_response({
        "id": r.get("id"),
        "name": r.get("name", ""),
        "description": r.get("description", ""),
        "nodes": r.get("nodes", []),
        "edges": r.get("edges", []),
        "trigger": r.get("trigger_config", {}),
        "enabled": bool(r.get("enabled", True)),
        "createdAt": r.get("created_at", ""),
        "updatedAt": r.get("updated_at", ""),
    })


@require_user
async def delete_workflow(request: web.Request) -> web.Response:
    """DELETE /api/workflows/:id — delete workflow."""
    state = get_state(request)
    user = request["user"]
    workflow_id = request.match_info["id"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}", "user_id": f"eq.{user['id']}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "not found"}, status=404)

    try:
        await db.delete(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}"},
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"ok": True})


@require_user
async def run_workflow(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    workflow_id = request.match_info["id"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}

    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}", "user_id": f"eq.{user['id']}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "not found"}, status=404)

    workflow = rows[0]
    context = body.get("context", {})

    from cn_social_agent.workflow.engine import engine
    run = await engine.execute(workflow, context, trigger_type="manual")

    try:
        await db.create("wb_workflow_runs", {
            "id": run["id"],
            "workflow_id": workflow_id,
            "user_id": user["id"],
            "status": run["status"],
            "trigger_type": run["triggerType"],
            "node_states": run["nodeStates"],
            "context": run["context"],
            "error": run.get("error"),
            "started_at": run["startedAt"],
            "finished_at": run.get("finishedAt"),
        })
    except Exception as e:
        print(f"[workflow] Failed to save run: {e}")

    return web.json_response(run)


@require_user
async def list_workflow_runs(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    workflow_id = request.match_info["id"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"runs": [], "total": 0})

    try:
        rows = await db.query(
            "wb_workflow_runs",
            filters={"workflow_id": f"eq.{workflow_id}", "user_id": f"eq.{user['id']}"},
            order="started_at.desc",
            limit=100,
        )
    except Exception:
        rows = []

    runs = []
    for r in (rows or []):
        runs.append({
            "id": r.get("id"),
            "workflowId": r.get("workflow_id"),
            "status": r.get("status", "pending"),
            "triggerType": r.get("trigger_type", "manual"),
            "nodeStates": r.get("node_states", {}),
            "context": r.get("context", {}),
            "error": r.get("error"),
            "startedAt": r.get("started_at", ""),
            "finishedAt": r.get("finished_at"),
        })

    return web.json_response({"runs": runs, "total": len(runs)})


@require_user
async def get_workflow_run(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    run_id = request.match_info["runId"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflow_runs",
            filters={"id": f"eq.{run_id}", "user_id": f"eq.{user['id']}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "not found"}, status=404)

    r = rows[0]
    return web.json_response({
        "id": r.get("id"),
        "workflowId": r.get("workflow_id"),
        "status": r.get("status", "pending"),
        "triggerType": r.get("trigger_type", "manual"),
        "nodeStates": r.get("node_states", {}),
        "context": r.get("context", {}),
        "error": r.get("error"),
        "startedAt": r.get("started_at", ""),
        "finishedAt": r.get("finished_at"),
    })


@require_user
async def cleanup_workflow_runs(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    workflow_id = request.match_info["id"]
    keep = int(request.query.get("keep", "100"))
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflow_runs",
            filters={"workflow_id": f"eq.{workflow_id}", "user_id": f"eq.{user['id']}"},
            order="started_at.desc",
            limit=keep + 50,
        )
    except Exception:
        rows = []

    if not rows or len(rows) <= keep:
        return web.json_response({"deleted": 0})

    to_delete = rows[keep:]
    deleted = 0
    for r in to_delete:
        try:
            await db.delete(
                "wb_workflow_runs",
                filters={"id": f"eq.{r['id']}"},
            )
            deleted += 1
        except Exception:
            pass

    return web.json_response({"deleted": deleted})


@require_user
async def get_run_logs(request: web.Request) -> web.Response:
    state = get_state(request)
    run_id = request.match_info["runId"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"logs": []})

    try:
        rows = await db.query(
            "wb_workflow_run_logs",
            filters={"run_id": f"eq.{run_id}"},
            order="created_at.asc",
            limit=500,
        )
    except Exception:
        rows = []

    logs = []
    for r in (rows or []):
        logs.append({
            "id": r.get("id"),
            "nodeId": r.get("node_id"),
            "level": r.get("level", "info"),
            "message": r.get("message", ""),
            "data": r.get("data"),
            "createdAt": r.get("created_at"),
        })

    return web.json_response({"logs": logs})


@require_user
async def add_run_log(request: web.Request) -> web.Response:
    state = get_state(request)
    run_id = request.match_info["runId"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}

    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    log_id = _gen_id()
    try:
        await db.create("wb_workflow_run_logs", {
            "id": log_id,
            "run_id": run_id,
            "node_id": body.get("nodeId", ""),
            "level": body.get("level", "info"),
            "message": body.get("message", ""),
            "data": body.get("data"),
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"id": log_id})


@require_user
async def retry_run(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    run_id = request.match_info["runId"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflow_runs",
            filters={"id": f"eq.{run_id}", "user_id": f"eq.{user['id']}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "run not found"}, status=404)

    old_run = rows[0]
    workflow_id = old_run.get("workflow_id")

    try:
        wf_rows = await db.query(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}"},
            limit=1,
        )
    except Exception:
        wf_rows = []

    if not wf_rows:
        return web.json_response({"error": "workflow not found"}, status=404)

    workflow = wf_rows[0]
    from cn_social_agent.workflow.engine import engine
    new_run = await engine.execute(workflow, old_run.get("context", {}), trigger_type="retry")

    try:
        await db.create("wb_workflow_runs", {
            "id": new_run["id"],
            "workflow_id": workflow_id,
            "user_id": user["id"],
            "status": new_run["status"],
            "trigger_type": "retry",
            "node_states": new_run["nodeStates"],
            "context": new_run["context"],
            "error": new_run.get("error"),
            "started_at": new_run["startedAt"],
            "finished_at": new_run.get("finishedAt"),
        })
    except Exception as e:
        print(f"[workflow] Failed to save retry run: {e}")

    return web.json_response(new_run)


@require_user
async def export_workflow(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    workflow_id = request.match_info["id"]
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflows",
            filters={"id": f"eq.{workflow_id}", "user_id": f"eq.{user['id']}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "not found"}, status=404)

    wf = rows[0]
    return web.json_response({
        "name": wf.get("name"),
        "description": wf.get("description", ""),
        "nodes": wf.get("nodes", []),
        "edges": wf.get("edges", []),
        "triggerConfig": wf.get("trigger_config", {}),
    })


@require_user
async def import_workflow(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}

    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    name = (body.get("name") or "导入的工作流").strip()
    workflow_id = _gen_id()
    now = _iso_now()

    try:
        await db.create("wb_workflows", {
            "id": workflow_id,
            "user_id": user["id"],
            "name": name,
            "description": body.get("description", ""),
            "nodes": body.get("nodes", []),
            "edges": body.get("edges", []),
            "trigger_config": body.get("triggerConfig", {"type": "manual", "config": {}}),
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"id": workflow_id, "name": name})


@require_user
async def list_templates(request: web.Request) -> web.Response:
    state = get_state(request)
    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"templates": []})

    try:
        rows = await db.query("wb_workflow_templates", limit=50)
    except Exception:
        rows = []

    templates = []
    for t in (rows or []):
        templates.append({
            "id": t.get("id"),
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "category": t.get("category", "content"),
            "nodes": t.get("nodes", []),
            "edges": t.get("edges", []),
            "thumbnail": t.get("thumbnail"),
        })

    return web.json_response({"templates": templates})


@require_user
async def create_from_template(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    template_id = request.match_info["templateId"]
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        body = {}

    db = getattr(state.insforge, "db", None) if state.insforge else None
    if db is None:
        return web.json_response({"error": "database not available"}, status=503)

    try:
        rows = await db.query(
            "wb_workflow_templates",
            filters={"id": f"eq.{template_id}"},
            limit=1,
        )
    except Exception:
        rows = []

    if not rows:
        return web.json_response({"error": "template not found"}, status=404)

    tpl = rows[0]
    name = (body.get("name") or tpl.get("name", "Untitled")).strip()

    workflow_id = _gen_id()
    now = _iso_now()

    try:
        await db.create("wb_workflows", {
            "id": workflow_id,
            "user_id": user["id"],
            "name": name,
            "description": tpl.get("description", ""),
            "nodes": tpl.get("nodes", []),
            "edges": tpl.get("edges", []),
            "trigger_config": {"type": "manual", "config": {}},
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({
        "id": workflow_id,
        "name": name,
        "description": tpl.get("description", ""),
        "nodes": tpl.get("nodes", []),
        "edges": tpl.get("edges", []),
        "trigger": {"type": "manual", "config": {}},
        "enabled": True,
        "createdAt": now,
        "updatedAt": now,
    }, status=201)


def setup_workflow_routes(app: web.Application) -> None:
    app.router.add_get("/api/workflows", list_workflows)
    app.router.add_get("/api/workflows/{id}", get_workflow)
    app.router.add_post("/api/workflows", create_workflow)
    app.router.add_put("/api/workflows/{id}", update_workflow)
    app.router.add_delete("/api/workflows/{id}", delete_workflow)
    app.router.add_post("/api/workflows/{id}/run", run_workflow)
    app.router.add_get("/api/workflows/{id}/export", export_workflow)
    app.router.add_post("/api/workflows/import", import_workflow)
    app.router.add_get("/api/workflows/{id}/runs", list_workflow_runs)
    app.router.add_delete("/api/workflows/{id}/runs", cleanup_workflow_runs)
    app.router.add_get("/api/workflows/runs/{runId}", get_workflow_run)
    app.router.add_get("/api/workflows/runs/{runId}/logs", get_run_logs)
    app.router.add_post("/api/workflows/runs/{runId}/logs", add_run_log)
    app.router.add_post("/api/workflows/runs/{runId}/retry", retry_run)
    app.router.add_get("/api/workflows/templates", list_templates)
    app.router.add_post("/api/workflows/from-template/{templateId}", create_from_template)
