from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user


AGENT_LEARNING_DIR = Path(__file__).resolve().parents[3] / "agent-learning"
_VENV_PYTHON = AGENT_LEARNING_DIR / ".venv" / "bin" / "python"
BRIDGE = AGENT_LEARNING_DIR / "api_bridge.py"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# (fetched_at_epoch, hotspot_items) — 10 min TTL, shared across users
_HOTSPOT_CACHE: tuple[float, list[dict[str, Any]]] = (0.0, [])


def _bridge_learn(args: list[str], timeout: int = 30) -> dict:
    if not _VENV_PYTHON.exists():
        return {"error": f"未找到学习库 venv：{_VENV_PYTHON}"}
    if not BRIDGE.exists():
        return {"error": f"未找到 api_bridge：{BRIDGE}"}
    try:
        proc = subprocess.run(
            [str(_VENV_PYTHON), str(BRIDGE), *args],
            cwd=str(AGENT_LEARNING_DIR),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"执行超时（>{timeout}s）"}
    except OSError as exc:
        return {"error": f"无法启动 bridge 子进程：{exc}"}
    if proc.returncode != 0:
        return {"error": "bridge 执行失败", "stderr": proc.stderr[:2000]}
    start = proc.stdout.find("{")
    if start < 0:
        return {"error": "bridge 输出非 JSON", "stdout": proc.stdout[:2000]}
    try:
        return json.loads(proc.stdout[start:])
    except (ValueError, json.JSONDecodeError):
        return {"error": "bridge JSON 解析失败", "stdout": proc.stdout[:2000]}


@require_user
async def list_research_notes(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db is None:
            return web.json_response({"notes": [], "count": 0})
        
        rows = await db.query(
            "wb_topic_research_notes",
            filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"},
            order="created_at.desc",
            limit=100,
        )
        return web.json_response({"notes": rows or [], "count": len(rows or [])})
    except Exception as e:
        return web.json_response({"notes": [], "count": 0, "error": str(e)})


@require_user
async def create_research_note(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    body = await request.json() if request.can_read_body else {}
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    content = str(body.get("content") or "").strip()
    if not content:
        return web.json_response({"error": "content required"}, status=400)
    
    note = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "topic_key": topic_key,
        "content": content,
        "note_type": body.get("note_type", "general"),
        "source": body.get("source", ""),
        "tags": body.get("tags", []),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.create("wb_topic_research_notes", note)
        return web.json_response(note)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def delete_research_note(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    note_id = (request.match_info.get("note_id") or "").strip()
    
    if not note_id:
        return web.json_response({"error": "note_id required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.delete("wb_topic_research_notes", filters={"id": f"eq.{note_id}", "user_id": f"eq.{user['id']}"})
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def list_workflow_records(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db is None:
            return web.json_response({"records": [], "count": 0})
        
        rows = await db.query(
            "wb_topic_workflow_records",
            filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"},
            order="created_at.desc",
            limit=50,
        )
        return web.json_response({"records": rows or [], "count": len(rows or [])})
    except Exception as e:
        return web.json_response({"records": [], "count": 0, "error": str(e)})


@require_user
async def create_workflow_record(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    body = await request.json() if request.can_read_body else {}
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "topic_key": topic_key,
        "workflow_type": body.get("workflow_type", "content_creation"),
        "method": body.get("method", ""),
        "what_worked": body.get("what_worked", ""),
        "what_didnt_work": body.get("what_didnt_work", ""),
        "duration_minutes": body.get("duration_minutes", 0),
        "content_type": body.get("content_type", ""),
        "quality_rating": body.get("quality_rating", 0),
        "engagement_data": body.get("engagement_data", {}),
        "notes": body.get("notes", ""),
        "created_at": _now_iso(),
    }
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.create("wb_topic_workflow_records", record)
        return web.json_response(record)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def list_learning_insights(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db is None:
            return web.json_response({"insights": [], "count": 0})
        
        rows = await db.query(
            "wb_topic_learning_insights",
            filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"},
            order="created_at.desc",
            limit=50,
        )
        return web.json_response({"insights": rows or [], "count": len(rows or [])})
    except Exception as e:
        return web.json_response({"insights": [], "count": 0, "error": str(e)})


@require_user
async def create_learning_insight(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    body = await request.json() if request.can_read_body else {}
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    insight = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "topic_key": topic_key,
        "insight_type": body.get("insight_type", "general"),
        "content": body.get("content", ""),
        "audience_signal": body.get("audience_signal", ""),
        "content_angle": body.get("content_angle", ""),
        "confidence": body.get("confidence", 0.5),
        "source_data": body.get("source_data", {}),
        "created_at": _now_iso(),
    }
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.create("wb_topic_learning_insights", insight)
        return web.json_response(insight)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def delete_learning_insight(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    insight_id = (request.match_info.get("insight_id") or "").strip()
    
    if not insight_id:
        return web.json_response({"error": "insight_id required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.delete("wb_topic_learning_insights", filters={"id": f"eq.{insight_id}", "user_id": f"eq.{user['id']}"})
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def get_learning_topics(request: web.Request) -> web.Response:
    try:
        data = _bridge_learn(["topics"])
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def get_learning_topic_detail(request: web.Request) -> web.Response:
    tid = request.match_info.get("tid", "")
    try:
        data = _bridge_learn(["topic", tid])
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def list_knowhow_topics(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    try:
        db = state.insforge.db if state.insforge else None
        if not db:
            return web.json_response({"topics": []})
        rows = await db.query(TABLE_HUBS, filters={"user_id": f"eq.{user['id']}"}, order="topic.desc", limit=100)
        topics = []
        for r in (rows or []):
            notes = await db.query(TABLE_NOTES, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{r['topic_key']}"}, limit=1000)
            wfs = await db.query("wb_topic_workflow_records", filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{r['topic_key']}"}, limit=1000)
            sks = await db.query("wb_topic_skills", filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{r['topic_key']}"}, limit=1000)
            nc = len(notes or [])
            wc = len(wfs or [])
            sc = len(sks or [])
            topics.append({
                "topic_key": r["topic_key"],
                "topic": r["topic"],
                "summary": r.get("summary", ""),
                "note_count": nc,
                "workflow_count": wc,
                "skill_count": sc,
                "total_count": nc + wc + sc,
            })
        return web.json_response({"topics": topics})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


TABLE_HUBS = "wb_topic_hubs"
TABLE_LINKS = "wb_topic_links"
TABLE_NOTES = "wb_topic_notes"


@require_user
async def get_topic_hub(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if not db:
            return web.json_response({"hub": None, "notes": [], "workflows": [], "links": []})
        
        hub_rows = await db.query(TABLE_HUBS, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"}, limit=1)
        hub = hub_rows[0] if hub_rows else None
        
        notes = await db.query(TABLE_NOTES, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"}, order="created_at.desc", limit=100)
        workflows = await db.query("wb_topic_workflow_records", filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"}, order="created_at.desc", limit=50)
        link_rows = await db.query(TABLE_LINKS, filters={"user_id": f"eq.{user['id']}", "source_key": f"eq.{topic_key}"}, limit=100)
        
        return web.json_response({
            "hub": hub,
            "notes": notes or [],
            "workflows": workflows or [],
            "links": [r.get("target_key") for r in (link_rows or [])],
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def create_topic_hub(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    body = await request.json() if request.can_read_body else {}
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    hub = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "topic_key": topic_key,
        "topic": body.get("topic", topic_key),
        "summary": body.get("summary", ""),
        "linked_topics": body.get("linked_topics", []),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            existing = await db.query(TABLE_HUBS, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"}, limit=1)
            if existing:
                await db.update(TABLE_HUBS, filters={"id": f"eq.{existing[0]['id']}"}, data={"topic": hub["topic"], "summary": hub["summary"], "updated_at": hub["updated_at"]})
                hub["id"] = existing[0]["id"]
            else:
                await db.create(TABLE_HUBS, hub)
        return web.json_response(hub)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def delete_topic_hub(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.delete(TABLE_HUBS, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"})
            await db.delete(TABLE_NOTES, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"})
            await db.delete(TABLE_LINKS, filters={"user_id": f"eq.{user['id']}", "source_key": f"eq.{topic_key}"})
            await db.delete(TABLE_LINKS, filters={"user_id": f"eq.{user['id']}", "target_key": f"eq.{topic_key}"})
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def create_topic_note(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    body = await request.json() if request.can_read_body else {}
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    content = str(body.get("content") or "").strip()
    if not content:
        return web.json_response({"error": "content required"}, status=400)
    
    note = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "topic_key": topic_key,
        "content": content,
        "source_type": body.get("source_type", "manual"),
        "tags": body.get("tags", []),
        "linked_notes": body.get("linked_notes", []),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.create(TABLE_NOTES, note)
        return web.json_response(note)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def delete_topic_note(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    note_id = (request.match_info.get("note_id") or "").strip()
    
    if not note_id:
        return web.json_response({"error": "note_id required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.delete(TABLE_NOTES, filters={"id": f"eq.{note_id}", "user_id": f"eq.{user['id']}"})
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def update_topic_note(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    note_id = (request.match_info.get("note_id") or "").strip()
    body = await request.json() if request.can_read_body else {}
    
    if not note_id:
        return web.json_response({"error": "note_id required"}, status=400)
    
    update_data = {}
    if "content" in body:
        update_data["content"] = body["content"]
    if "tags" in body:
        update_data["tags"] = body["tags"]
    update_data["updated_at"] = _now_iso()
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.update(TABLE_NOTES, filters={"id": f"eq.{note_id}", "user_id": f"eq.{user['id']}"}, data=update_data)
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def create_topic_link(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    body = await request.json() if request.can_read_body else {}
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    target_key = body.get("target_key", "").strip()
    if not target_key:
        return web.json_response({"error": "target_key required"}, status=400)
    
    link = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "source_key": topic_key,
        "target_key": target_key,
        "link_type": body.get("link_type", "related"),
        "created_at": _now_iso(),
    }
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            existing = await db.query(TABLE_LINKS, filters={"user_id": f"eq.{user['id']}", "source_key": f"eq.{topic_key}", "target_key": f"eq.{target_key}"}, limit=1)
            if not existing:
                await db.create(TABLE_LINKS, link)
        return web.json_response(link)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def delete_topic_link(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    target_key = (request.match_info.get("target") or "").strip()
    
    if not topic_key or not target_key:
        return web.json_response({"error": "topic key and target required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if db:
            await db.delete(TABLE_LINKS, filters={"user_id": f"eq.{user['id']}", "source_key": f"eq.{topic_key}", "target_key": f"eq.{target_key}"})
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def get_related_topics(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if not db:
            return web.json_response({"related": []})
        
        current_notes = await db.query(TABLE_NOTES, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"}, limit=50)
        current_tags = set()
        for note in (current_notes or []):
            for tag in (note.get("tags") or []):
                current_tags.add(tag)
        
        all_topics = await db.query(TABLE_HUBS, filters={"user_id": f"eq.{user['id']}"}, limit=100)
        
        linked_rows = await db.query(TABLE_LINKS, filters={"user_id": f"eq.{user['id']}", "source_key": f"eq.{topic_key}"}, limit=100)
        linked_keys = set(r.get("target_key") for r in (linked_rows or []))
        
        recommendations = []
        for t in (all_topics or []):
            if t["topic_key"] == topic_key or t["topic_key"] in linked_keys:
                continue
            
            other_notes = await db.query(TABLE_NOTES, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{t['topic_key']}"}, limit=50)
            other_tags = set()
            for note in (other_notes or []):
                for tag in (note.get("tags") or []):
                    other_tags.add(tag)
            
            intersection = len(current_tags & other_tags)
            union = len(current_tags | other_tags)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > 0:
                recommendations.append({
                    "topic_key": t["topic_key"],
                    "topic": t["topic"],
                    "similarity": round(similarity, 2),
                    "shared_tags": list(current_tags & other_tags),
                })
        
        recommendations.sort(key=lambda x: x["similarity"], reverse=True)
        
        return web.json_response({"related": recommendations[:10]})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def sync_learning_to_topic(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    
    try:
        db = state.insforge.db if state.insforge else None
        if not db:
            return web.json_response({"synced": 0})
        
        insights = await db.query("wb_topic_learning_insights", filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"}, limit=50)
        
        existing_notes = await db.query(TABLE_NOTES, filters={"user_id": f"eq.{user['id']}", "topic_key": f"eq.{topic_key}"}, limit=100)
        existing_contents = set(n.get("content", "") for n in (existing_notes or []))
        
        synced = 0
        for insight in (insights or []):
            content = insight.get("content", "")
            if content and content not in existing_contents:
                note = {
                    "id": str(uuid.uuid4()),
                    "user_id": user["id"],
                    "topic_key": topic_key,
                    "content": content,
                    "source_type": "learning",
                    "tags": ["学习洞察"],
                    "linked_notes": [],
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
                await db.create(TABLE_NOTES, note)
                existing_contents.add(content)
                synced += 1
        
        return web.json_response({"synced": synced})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def run_demo(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    code = body.get("code", "")
    topic_key = body.get("topic_key", "")
    if not code:
        return web.json_response({"error": "code required"}, status=400)
    try:
        result = _bridge_learn(["demo", topic_key, code], timeout=60)
        return web.json_response({"output": result.get("output", "无输出")})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def query_kb(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    question = body.get("question", "")
    topic_key = body.get("topic_key", "")
    if not question:
        return web.json_response({"error": "question required"}, status=400)
    try:
        result = _bridge_learn(["kb", topic_key, question], timeout=30)
        return web.json_response({"answer": result.get("answer", "未找到答案")})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def generate_quiz(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    topic_key = body.get("topic_key", "")
    if not topic_key:
        return web.json_response({"error": "topic_key required"}, status=400)
    try:
        result = _bridge_learn(["quiz", topic_key], timeout=30)
        return web.json_response({"quiz": result.get("quiz", "未生成题目")})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def send_tutor_message(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    message = body.get("message", "")
    topic_key = body.get("topic_key", "")
    if not message:
        return web.json_response({"error": "message required"}, status=400)
    try:
        result = _bridge_learn(["tutor", topic_key, message], timeout=30)
        return web.json_response({"reply": result.get("reply", "未收到回复")})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ----- Know-How content stream + search (Step 4b A1/A2) -----

def _stream_item(item_type: str, row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a row into a stream item."""
    return {
        "type": item_type,
        "id": row.get("id"),
        "topic_key": row.get("topic_key"),
        "title": _stream_title(item_type, row),
        "preview": _stream_preview(item_type, row),
        "updated_at": row.get("updated_at") or row.get("created_at"),
        "raw": row,
    }


def _stream_title(item_type: str, row: dict[str, Any]) -> str:
    if item_type == "note":
        c = (row.get("content") or "").strip()
        return c[:48] + ("…" if len(c) > 48 else "") or "未命名笔记"
    if item_type == "workflow":
        method = row.get("method") or ""
        wf_type = {"content_creation": "内容创作", "research": "调研", "editing": "剪辑"}.get(row.get("workflow_type"), row.get("workflow_type") or "")
        return method or wf_type or "未命名工作流"
    if item_type == "asset":
        return row.get("title") or row.get("topic") or "内容资产"
    if item_type == "skill":
        return row.get("skill_name") or "经验 skill"
    return row.get("title") or "未命名"


def _stream_preview(item_type: str, row: dict[str, Any]) -> str:
    if item_type == "note":
        c = (row.get("content") or "").strip()
        return c[:160] + ("…" if len(c) > 160 else "")
    if item_type == "workflow":
        parts = []
        if row.get("what_worked"):
            parts.append(f"有效: {str(row['what_worked'])[:80]}")
        if row.get("what_didnt_work"):
            parts.append(f"避免: {str(row['what_didnt_work'])[:80]}")
        return "\n".join(parts)
    if item_type == "asset":
        return row.get("summary") or ""
    if item_type == "skill":
        w = row.get("when_to_use") or ""
        b = (row.get("body") or "")[:120]
        return f"{w}\n{b}".strip()
    return ""


@require_user
async def knowhow_stream(request: web.Request) -> web.Response:
    """GET /api/knowhow/stream?topics=&types=&q=&limit=50 — cross-table aggregated feed."""
    state = get_state(request)
    user = request["user"]
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({"items": []})

    topics_param = (request.query.get("topics") or "").strip()
    types_param = (request.query.get("types") or "").strip()
    q = (request.query.get("q") or "").strip()
    try:
        limit = max(1, min(200, int(request.query.get("limit") or "50")))
    except ValueError:
        limit = 50

    topics = [t for t in topics_param.split(",") if t] if topics_param else []
    types = [t for t in types_param.split(",") if t] if types_param else []
    valid_types = {"note", "workflow", "skill"}
    types = [t for t in types if t in valid_types] or list(valid_types)

    items: list[dict[str, Any]] = []

    async def _fetch_notes() -> None:
        if "note" not in types:
            return
        filters = {"user_id": f"eq.{user['id']}"}
        rows = await db.query(TABLE_NOTES, filters=filters, order="updated_at.desc", limit=limit * 2)
        for r in (rows or []):
            if topics and r.get("topic_key") not in topics:
                continue
            if q and q.lower() not in (r.get("content") or "").lower():
                continue
            items.append(_stream_item("note", r))

    async def _fetch_workflows() -> None:
        if "workflow" not in types:
            return
        filters = {"user_id": f"eq.{user['id']}"}
        rows = await db.query(
            "wb_topic_workflow_records", filters=filters, order="updated_at.desc", limit=limit * 2
        )
        for r in (rows or []):
            if topics and r.get("topic_key") not in topics:
                continue
            if q:
                hay = " ".join(
                    str(r.get(k) or "") for k in ("method", "what_worked", "what_didnt_work", "notes", "workflow_type")
                ).lower()
                if q.lower() not in hay:
                    continue
            items.append(_stream_item("workflow", r))

    async def _fetch_skills() -> None:
        if "skill" not in types:
            return
        filters = {"user_id": f"eq.{user['id']}"}
        rows = await db.query("wb_topic_skills", filters=filters, order="updated_at.desc", limit=limit * 2)
        for r in (rows or []):
            if topics and r.get("topic_key") not in topics:
                continue
            if q:
                hay = " ".join(
                    str(r.get(k) or "") for k in ("skill_name", "when_to_use", "body")
                ).lower()
                if q.lower() not in hay:
                    continue
            items.append(_stream_item("skill", r))

    try:
        import asyncio as _asyncio

        await _asyncio.gather(_fetch_notes(), _fetch_workflows(), _fetch_skills())
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return web.json_response({"items": items[:limit]})


@require_user
async def knowhow_stats(request: web.Request) -> web.Response:
    """GET /api/knowhow/stats — aggregated counts for the overview banner."""
    state = get_state(request)
    user = request["user"]
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({
            "total_notes": 0, "total_workflows": 0, "total_skills": 0,
            "total_topics": 0, "total_items": 0, "recent_items": 0,
            "topic_coverage": [],
        })
    uid = user["id"]
    try:
        import asyncio as _asyncio
        notes, workflows, skills, topics = await _asyncio.gather(
            db.query(TABLE_NOTES, filters={"user_id": f"eq.{uid}"}, limit=5000),
            db.query("wb_topic_workflow_records", filters={"user_id": f"eq.{uid}"}, limit=5000),
            db.query("wb_topic_skills", filters={"user_id": f"eq.{uid}"}, limit=5000),
            db.query(TABLE_HUBS, filters={"user_id": f"eq.{uid}"}, limit=200),
        )
        notes = notes or []
        workflows = workflows or []
        skills = skills or []
        topics = topics or []

        import time as _time
        cutoff = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_time.time() - 7 * 86400))
        recent = sum(
            1 for items in (notes, workflows, skills)
            for r in items
            if (r.get("updated_at") or r.get("created_at") or "") >= cutoff
        )

        topic_keys = {t["topic_key"] for t in topics}
        coverage: dict[str, dict] = {}
        for tk in topic_keys:
            coverage[tk] = {"notes": 0, "workflows": 0, "skills": 0}
        for r in notes:
            tk = r.get("topic_key")
            if tk in coverage:
                coverage[tk]["notes"] += 1
        for r in workflows:
            tk = r.get("topic_key")
            if tk in coverage:
                coverage[tk]["workflows"] += 1
        for r in skills:
            tk = r.get("topic_key")
            if tk in coverage:
                coverage[tk]["skills"] += 1

        topic_coverage = [
            {
                "topic_key": tk,
                "topic": next((t["topic"] for t in topics if t["topic_key"] == tk), tk),
                "total": c["notes"] + c["workflows"] + c["skills"],
                **c,
            }
            for tk, c in sorted(coverage.items(), key=lambda x: x[1]["notes"] + x[1]["workflows"] + x[1]["skills"])
        ]

        return web.json_response({
            "total_notes": len(notes),
            "total_workflows": len(workflows),
            "total_skills": len(skills),
            "total_topics": len(topics),
            "total_items": len(notes) + len(workflows) + len(skills),
            "recent_items": recent,
            "topic_coverage": topic_coverage,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def daily_briefing(request: web.Request) -> web.Response:
    """GET /api/daily-briefing — resurfaced knowledge + pending projects + hotspots."""
    state = get_state(request)
    user = request["user"]
    uid = user["id"]
    email = str(user.get("email") or "")
    db = state.insforge.db if state.insforge else None

    out: dict[str, Any] = {
        "date": _now_iso()[:10],
        "review_items": [],
        "pending_projects": [],
        "hotspots": [],
    }

    def _age_days(ts: str) -> int:
        try:
            from datetime import datetime

            t = datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
            return max(0, int((time.time() - t) // 86400))
        except Exception:  # noqa: BLE001
            return 0

    # 1) Resurfaced knowledge: notes + skills at least 7 days old, random sample
    if db:
        try:
            import asyncio as _asyncio
            import random as _random

            notes, skills = await _asyncio.gather(
                db.query(TABLE_NOTES, filters={"user_id": f"eq.{uid}"}, limit=5000),
                db.query("wb_topic_skills", filters={"user_id": f"eq.{uid}"}, limit=5000),
            )
            pool: list[dict[str, Any]] = []
            for n in notes or []:
                pool.append(
                    {
                        "type": "note",
                        "id": n.get("id"),
                        "title": (n.get("content") or "")[:60],
                        "topic_key": n.get("topic_key"),
                        "created_at": n.get("created_at") or n.get("updated_at") or "",
                    }
                )
            for s in skills or []:
                pool.append(
                    {
                        "type": "skill",
                        "id": s.get("id"),
                        "title": s.get("skill_name") or "",
                        "topic_key": s.get("topic_key"),
                        "created_at": s.get("created_at") or s.get("updated_at") or "",
                    }
                )
            old = [p for p in pool if _age_days(p.get("created_at") or "") >= 7]
            _random.shuffle(old)
            for p in old[:5]:
                p["days_ago"] = _age_days(p.get("created_at") or "")
                out["review_items"].append(p)
        except Exception:  # noqa: BLE001
            pass

    # 2) Pending content projects (active statuses)
    try:
        from cn_social_agent.content import service as cps

        projects = await cps.list_projects(user_id=uid, email=email, limit=100)
        active = ("candidate", "researching", "draft", "in_progress")
        out["pending_projects"] = [
            {
                "id": p.get("id"),
                "topic": p.get("short_topic") or p.get("topic"),
                "status": p.get("status"),
                "updated_at": p.get("updated_at"),
            }
            for p in projects
            if str(p.get("status") or "") in active
        ][:5]
    except Exception:  # noqa: BLE001
        pass

    # 3) Hotspots (read-only board scan, no project creation).
    # Cached 10 min + 8s timeout: a cold multi-source scan takes ~15s.
    try:
        import asyncio as _asyncio

        from cn_social_agent.content.connectors import enabled_hotspot_sources
        from cn_social_agent.tools.hotspots import tool_scan_hotspot_board

        prefs = await state.store.get_user_prefs(uid) if state.store else {}
        allowed = enabled_hotspot_sources(prefs if isinstance(prefs, dict) else {})

        global _HOTSPOT_CACHE
        cached_ts, cached_items = _HOTSPOT_CACHE
        if cached_items and (time.time() - cached_ts) < 600:
            out["hotspots"] = cached_items
        else:
            scan = await _asyncio.wait_for(
                tool_scan_hotspot_board(per_page=5, source="all", allowed_sources=allowed),
                timeout=8,
            )
            items = [
                {
                    "title": str(b.get("title") or b.get("full_name") or "")[:80],
                    "source": b.get("source") or "",
                    "url": str(b.get("url") or "")[:200],
                }
                for b in (scan.get("board") or [])[:5]
            ]
            if items:
                _HOTSPOT_CACHE = (time.time(), items)
            out["hotspots"] = items or cached_items
    except Exception:  # noqa: BLE001
        try:
            out["hotspots"] = _HOTSPOT_CACHE[1]
        except Exception:  # noqa: BLE001
            pass

    return web.json_response(out)


@require_user
async def analyze_topic(request: web.Request) -> web.Response:
    """GET /api/knowhow/{key}/analyze — completeness analysis and gap detection for a topic."""
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)

    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({
            "topic": topic_key,
            "distribution": {"concepts": 0, "practices": 0, "pitfalls": 0, "insights": 0},
            "gaps": [],
            "completeness_score": 0.0,
        })

    uid = user["id"]
    try:
        import asyncio as _asyncio
        import time as _time

        # Fetch all assets for this topic
        notes, workflows, skills = await _asyncio.gather(
            db.query(TABLE_NOTES, filters={"user_id": f"eq.{uid}", "topic_key": f"eq.{topic_key}"}, limit=5000),
            db.query("wb_topic_workflow_records", filters={"user_id": f"eq.{uid}", "topic_key": f"eq.{topic_key}"}, limit=5000),
            db.query("wb_topic_skills", filters={"user_id": f"eq.{uid}", "topic_key": f"eq.{topic_key}"}, limit=5000),
        )
        notes = notes or []
        workflows = workflows or []
        skills = skills or []

        # Classify by knowledge type based on note_type field or infer from content
        concepts = 0
        practices = 0
        pitfalls = 0
        insights = 0

        for n in notes:
            note_type = (n.get("note_type") or "").lower()
            if note_type in ("concept", "idea", "definition"):
                concepts += 1
            elif note_type in ("practice", "workflow", "tutorial"):
                practices += 1
            elif note_type in ("pitfall", "mistake", "trap"):
                pitfalls += 1
            elif note_type in ("insight", "lesson", "reflection"):
                insights += 1
            else:
                # Default classification if no type specified
                concepts += 1

        # Workflows count as practices
        practices += len(workflows)

        # Skills can be insights or practices depending on type
        for s in skills:
            skill_type = (s.get("skill_type") or "").lower()
            if skill_type == "experience":
                insights += 1
            else:
                practices += 1

        distribution = {
            "concepts": concepts,
            "practices": practices,
            "pitfalls": pitfalls,
            "insights": insights,
        }

        # Calculate completeness score
        score = 0.0
        # Base score: 0.25 per category that has at least 1 item
        for count in distribution.values():
            if count > 0:
                score += 0.25

        # Bonus: workflows with both what_worked and what_didnt_work
        for w in workflows:
            ww = w.get("what_worked") or ""
            wd = w.get("what_didnt_work") or ""
            if ww.strip() and wd.strip():
                score += 0.1
                break  # Only once per topic

        # Penalty: no new notes in 30 days
        cutoff_30d = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_time.time() - 30 * 86400))
        has_recent = any(
            (n.get("updated_at") or n.get("created_at") or "") >= cutoff_30d
            for n in notes
        )
        if not has_recent and len(notes) > 0:
            score -= 0.1

        score = max(0.0, min(1.0, round(score, 2)))

        # Detect gaps
        gaps = []
        if pitfalls == 0:
            gaps.append({
                "area": "踩坑总结",
                "reason": "缺少 pitfalls 类型知识",
                "suggestion": "补充最近遇到的陷阱或常见错误",
            })
        if insights == 0 and len(notes) + len(workflows) > 2:
            gaps.append({
                "area": "经验沉淀",
                "reason": "有实践但缺少系统性总结",
                "suggestion": "将零散经验整理为可复用的技能卡片",
            })
        if concepts == 0 and (practices > 0 or insights > 0):
            gaps.append({
                "area": "概念梳理",
                "reason": "有实践/经验但缺少基础概念定义",
                "suggestion": "补充核心概念和术语解释，帮助理解上下文",
            })

        # Check for subtopic gaps based on common tech dimensions
        # Extract keywords from titles/content
        all_text = " ".join(
            [n.get("content") or "" for n in notes[:20]] +
            [w.get("method") or "" for w in workflows[:10]] +
            [s.get("skill_name") or "" for s in skills[:10]]
        ).lower()

        common_dimensions = {
            "性能优化": ["performance", "optimization", "speed", "latency", "缓存", "性能"],
            "架构设计": ["architecture", "design", "pattern", "结构", "架构", "分层"],
            "安全": ["security", "auth", "permission", "漏洞", "安全", "加密"],
            "运维部署": ["deploy", "docker", "ci/cd", "监控", "运维", "部署"],
            "测试": ["test", "unit test", "integration", "测试", "用例"],
            "文档": ["doc", "readme", "documentation", "文档", "说明"],
        }

        missing_dims = []
        for dim, keywords in common_dimensions.items():
            has_keyword = any(kw in all_text for kw in keywords)
            if not has_keyword:
                missing_dims.append(dim)

        # If we have significant activity but missing common dimensions, suggest them
        total_items = len(notes) + len(workflows) + len(skills)
        if total_items >= 5 and missing_dims:
            # Only suggest top 2 missing dimensions to avoid overwhelming
            for dim in missing_dims[:2]:
                gaps.append({
                    "area": dim,
                    "reason": f"未检测到与{dim}相关的内容",
                    "suggestion": f"补充关于{dim}的实践或笔记",
                })

        return web.json_response({
            "topic": topic_key,
            "distribution": distribution,
            "gaps": gaps,
            "completeness_score": score,
            "total_items": total_items,
        })

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_user
async def knowhow_search(request: web.Request) -> web.Response:
    """GET /api/knowhow/search?q=&limit=20 — LIKE search across notes+workflows+skills."""
    state = get_state(request)
    user = request["user"]
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({"results": []})
    q = (request.query.get("q") or "").strip()
    try:
        limit = max(1, min(50, int(request.query.get("limit") or "20")))
    except ValueError:
        limit = 20
    if not q:
        return web.json_response({"results": []})
    pattern = f"%{q}%"

    results: list[dict[str, Any]] = []

    async def _search_notes() -> None:
        rows = await db.query(
            TABLE_NOTES,
            filters={"user_id": f"eq.{user['id']}", "content": f"ilike.{pattern}"},
            order="updated_at.desc",
            limit=limit,
        )
        for r in (rows or []):
            results.append(
                {
                    "type": "note",
                    "id": r.get("id"),
                    "title": (r.get("content") or "")[:48],
                    "topic_key": r.get("topic_key"),
                    "updated_at": r.get("updated_at"),
                }
            )

    async def _search_workflows() -> None:
        rows = await db.query(
            "wb_topic_workflow_records",
            filters={"user_id": f"eq.{user['id']}", "title": f"ilike.{pattern}"},
            order="updated_at.desc",
            limit=limit,
        )
        for r in (rows or []):
            results.append(
                {
                    "type": "workflow",
                    "id": r.get("id"),
                    "title": r.get("title") or "",
                    "topic_key": r.get("topic_key"),
                    "updated_at": r.get("updated_at"),
                }
            )

    async def _search_skills() -> None:
        rows = await db.query(
            "wb_topic_skills",
            filters={"user_id": f"eq.{user['id']}", "skill_name": f"ilike.{pattern}"},
            order="updated_at.desc",
            limit=limit,
        )
        for r in (rows or []):
            results.append(
                {
                    "type": "skill",
                    "id": r.get("id"),
                    "title": r.get("skill_name") or "",
                    "topic_key": r.get("topic_key"),
                    "updated_at": r.get("updated_at"),
                }
            )

    try:
        import asyncio as _asyncio

        await _asyncio.gather(_search_notes(), _search_workflows(), _search_skills())
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    results.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return web.json_response({"results": results[:limit]})


# ----- Skill routes (Step 4b A6) -----

@require_user
async def list_topic_skills(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    db = state.insforge.db if state.insforge else None
    from cn_social_agent.knowledge.skills import list_experience_skills, list_preset_skills

    preset = list_preset_skills(getattr(state, "skills_loader", None))
    experience = await list_experience_skills(db, user_id=user["id"], topic_key=topic_key) if db else []
    return web.json_response({"preset": preset, "experience": experience})


@require_user
async def create_topic_skill(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    body = await request.json() if request.can_read_body else {}
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({"error": "db unavailable"}, status=500)
    from cn_social_agent.knowledge.skills import create_experience_skill

    row = await create_experience_skill(
        db,
        user_id=user["id"],
        topic_key=topic_key,
        skill_name=body.get("skill_name") or "",
        when_to_use=body.get("when_to_use") or "",
        body=body.get("body") or "",
        source_workflows=body.get("source_workflows") or [],
        skill_type=body.get("skill_type") or "experience",
        enabled=bool(body.get("enabled", True)),
    )
    if row.get("error"):
        return web.json_response(row, status=500)
    return web.json_response(row, status=201)


@require_user
async def patch_topic_skill(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    skill_id = (request.match_info.get("id") or "").strip()
    if not skill_id:
        return web.json_response({"error": "skill id required"}, status=400)
    body = await request.json() if request.can_read_body else {}
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({"error": "db unavailable"}, status=500)
    from cn_social_agent.knowledge.skills import patch_experience_skill

    row = await patch_experience_skill(db, skill_id=skill_id, user_id=user["id"], updates=body)
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(row)


@require_user
async def delete_topic_skill(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    skill_id = (request.match_info.get("id") or "").strip()
    if not skill_id:
        return web.json_response({"error": "skill id required"}, status=400)
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({"error": "db unavailable"}, status=500)
    from cn_social_agent.knowledge.skills import delete_experience_skill

    ok = await delete_experience_skill(db, skill_id=skill_id, user_id=user["id"])
    return web.json_response({"ok": ok})


@require_user
async def extract_topic_skills(request: web.Request) -> web.Response:
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("key") or "").strip()
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({"error": "db unavailable"}, status=500)
    from cn_social_agent.knowledge.skills import (
        extract_skills_from_workflows,
        fetch_workflow_records_for_extraction,
    )

    workflows = await fetch_workflow_records_for_extraction(
        db, user_id=user["id"], topic_key=topic_key
    )
    llm_client = getattr(state, "llm_client", None) or getattr(state, "llm", None)
    if not llm_client:
        return web.json_response(
            {"error": "LLM client unavailable", "workflow_count": len(workflows)}, status=500
        )
    suggestion = await extract_skills_from_workflows(
        workflows, topic_key=topic_key, llm_client=llm_client
    )
    return web.json_response(suggestion, status=200 if not suggestion.get("error") else 400)


@require_user
async def confirm_topic_skill(request: web.Request) -> web.Response:
    """POST /api/knowhow/skills/{id}/confirm — persist a confirmed suggestion ({id} is the topic_key; body carries suggestion)."""
    state = get_state(request)
    user = request["user"]
    topic_key = (request.match_info.get("id") or request.query.get("topic_key") or "").strip()
    if not topic_key:
        return web.json_response({"error": "topic key required"}, status=400)
    body = await request.json() if request.can_read_body else {}
    db = state.insforge.db if state.insforge else None
    if not db:
        return web.json_response({"error": "db unavailable"}, status=500)
    from cn_social_agent.knowledge.skills import confirm_extracted_skill

    row = await confirm_extracted_skill(
        db,
        user_id=user["id"],
        topic_key=topic_key,
        suggestion=body,
    )
    if row.get("error"):
        return web.json_response(row, status=500)
    return web.json_response(row, status=201)


def setup_topic_hub_routes(app: web.Application) -> None:
    app.router.add_get("/api/topic-hub/{key}/notes", list_research_notes)
    app.router.add_post("/api/topic-hub/{key}/notes", create_research_note)
    app.router.add_delete("/api/topic-hub/notes/{note_id}", delete_research_note)
    
    app.router.add_get("/api/topic-hub/{key}/workflows", list_workflow_records)
    app.router.add_post("/api/topic-hub/{key}/workflows", create_workflow_record)
    
    app.router.add_get("/api/topic-hub/{key}/insights", list_learning_insights)
    app.router.add_post("/api/topic-hub/{key}/insights", create_learning_insight)
    app.router.add_delete("/api/topic-hub/insights/{insight_id}", delete_learning_insight)
    
    app.router.add_get("/api/topic-hub/learning/topics", get_learning_topics)
    app.router.add_get("/api/topic-hub/learning/topic/{tid}", get_learning_topic_detail)
    
    app.router.add_get("/api/knowhow/topics", list_knowhow_topics)
    app.router.add_get("/api/knowhow/stats", knowhow_stats)
    app.router.add_get("/api/knowhow/stream", knowhow_stream)
    app.router.add_get("/api/knowhow/search", knowhow_search)
    app.router.add_get("/api/daily-briefing", daily_briefing)
    app.router.add_get("/api/knowhow/{key}/analyze", analyze_topic)
    app.router.add_get("/api/knowhow/{key}", get_topic_hub)
    app.router.add_post("/api/knowhow/{key}", create_topic_hub)
    app.router.add_delete("/api/knowhow/{key}", delete_topic_hub)
    app.router.add_post("/api/knowhow/{key}/notes", create_topic_note)
    app.router.add_patch("/api/knowhow/notes/{note_id}", update_topic_note)
    app.router.add_delete("/api/knowhow/notes/{note_id}", delete_topic_note)
    app.router.add_post("/api/knowhow/{key}/workflows", create_workflow_record)
    app.router.add_post("/api/knowhow/{key}/link", create_topic_link)
    app.router.add_delete("/api/knowhow/{key}/link/{target}", delete_topic_link)
    app.router.add_get("/api/knowhow/{key}/related", get_related_topics)
    app.router.add_post("/api/knowhow/{key}/sync-learning", sync_learning_to_topic)
    app.router.add_get("/api/knowhow/{key}/skills", list_topic_skills)
    app.router.add_post("/api/knowhow/{key}/skills", create_topic_skill)
    app.router.add_patch("/api/knowhow/skills/{id}", patch_topic_skill)
    app.router.add_delete("/api/knowhow/skills/{id}", delete_topic_skill)
    app.router.add_post("/api/knowhow/{key}/extract-skills", extract_topic_skills)
    app.router.add_post("/api/knowhow/skills/{id}/confirm", confirm_topic_skill)
    app.router.add_post("/api/knowhow/demo", run_demo)
    app.router.add_post("/api/knowhow/kb", query_kb)
    app.router.add_post("/api/knowhow/quiz", generate_quiz)
    app.router.add_post("/api/knowhow/tutor", send_tutor_message)
