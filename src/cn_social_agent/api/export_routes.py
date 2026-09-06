"""任务产物落盘导出 —— 「交付的是文件，不是聊天记录」。

把任务产物真实写入 ``data/exports/{user_key}/{task}_{title}/``，
并提供带用户校验的下载路由（防目录穿越）。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from aiohttp import web

from cn_social_agent.api.deps import require_user
from cn_social_agent.core.db import RlsViolation
from cn_social_agent.api.nexus_routes import _engine, nexus_user
from cn_social_agent.tasks.engine import TaskError

EXPORT_ROOT = Path(__file__).resolve().parents[3] / "data" / "exports"

_SAFE_NAME = re.compile(r"[^\w\u4e00-\u9fff.-]+", re.UNICODE)


def _user_key(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def _safe_name(name: str, fallback: str) -> str:
    name = _SAFE_NAME.sub("_", (name or "").strip()).strip("._")
    return name[:60] or fallback


def _task_dir(user_id: str, task_id: str, title: str) -> Path:
    return EXPORT_ROOT / _user_key(user_id) / _safe_name(f"{task_id[:8]}_{title}", task_id[:8])


@nexus_user
async def export_task(request: web.Request) -> web.Response:
    """把指定任务的全部产物落盘，返回可下载的文件清单。"""
    user_id = request["user"]["id"]
    engine = _engine(request)
    task_id = request.match_info["id"]
    try:
        task = await engine.get_task(task_id, with_detail=True)
    except TaskError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except RlsViolation:
        return web.json_response({"error": "not found"}, status=404)

    arts = task.artifacts or []
    if not arts:
        return web.json_response({"error": "任务没有可导出的产物"}, status=400)

    out_dir = _task_dir(user_id, task_id, task.title)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for a in arts:
        name = _safe_name(a.name or f"artifact.{a.kind or 'md'}", "artifact.txt")
        path = out_dir / name
        path.write_text(a.content or "", encoding="utf-8")
        rel = str(path.relative_to(EXPORT_ROOT)).replace("\\", "/")
        files.append({"name": name, "size": len((a.content or "").encode("utf-8")), "path": rel})
    return web.json_response(
        {"ok": True, "dir": str(out_dir), "files": files,
         "urls": [f"/api/exports/{f['path']}" for f in files]},
    )


@require_user
async def download_export(request: web.Request) -> web.Response:
    """下载已导出的文件（仅允许本人导出目录内的路径）。"""
    user_id = request["user"]["id"]
    rel = request.match_info["path"]
    if ".." in rel or rel.startswith("/"):
        return web.json_response({"error": "bad path"}, status=400)
    base = (EXPORT_ROOT / _user_key(user_id)).resolve()
    target = (base / rel).resolve()
    if not str(target).startswith(str(base)):
        return web.json_response({"error": "forbidden"}, status=403)
    if not target.is_file():
        return web.json_response({"error": "not found"}, status=404)
    return web.FileResponse(target, headers={
        "Content-Disposition": (
            f'attachment; filename="{target.name.encode("ascii", "ignore").decode() or "export.bin"}"; '
            f"filename*=UTF-8''{target.name}"
        )
    })


def setup_export_routes(app: web.Application) -> None:
    app.router.add_post("/api/nexus/tasks/{id}/export", export_task)
    app.router.add_get("/api/exports/{path:.+}", download_export)
