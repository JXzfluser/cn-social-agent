"""学习模块 API：把 Workbench 前端请求转给 agent-learning 的 api_bridge（子进程）。

agent-learning 有独立的 .venv（numpy/langgraph/mcp…），主项目 .venv 不一定具备，
因此这里一律用 agent-learning/.venv/bin/python 起子进程执行 api_bridge.py，
复用学习库自身代码与离线 FakeLLM，避免跨 venv 依赖污染。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aiohttp import web

from cn_social_agent.api.deps import require_user

AGENT_LEARNING_DIR = Path(__file__).resolve().parents[3] / "agent-learning"
_VENV_PYTHON = AGENT_LEARNING_DIR / ".venv" / "bin" / "python"
BRIDGE = AGENT_LEARNING_DIR / "api_bridge.py"
PROGRESS_FILE = AGENT_LEARNING_DIR / "user_progress.json"


def _extract_json(text: str) -> dict:
    """从 stdout 提取 JSON：容忍杂散输出（警告/日志混入），取第一个 '{' 起解析。"""
    start = text.find("{")
    if start < 0:
        raise ValueError("stdout 中没有 JSON 对象")
    return json.loads(text[start:])


def _bridge(args: list[str], timeout: int = 60) -> dict:
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
        return {"error": f"执行超时（>{timeout}s），已终止"}
    except OSError as exc:
        return {"error": f"无法启动 bridge 子进程：{exc}"}
    if proc.returncode != 0:
        return {"error": "bridge 执行失败", "stderr": proc.stderr[:2000]}
    try:
        return _extract_json(proc.stdout)
    except (ValueError, json.JSONDecodeError):
        return {"error": "bridge 输出非 JSON", "stdout": proc.stdout[:2000]}


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"viewed": [], "completed": [], "quiz_scores": {}}


def _save_progress(data: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


@require_user
async def list_topics(request: web.Request) -> web.Response:
    return web.json_response(_bridge(["topics"]))


@require_user
async def get_topic(request: web.Request) -> web.Response:
    tid = request.match_info["tid"]
    return web.json_response(_bridge(["topic", tid]))


@require_user
async def run_demo(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    path = str(body.get("path") or "")
    if not path:
        return web.json_response({"error": "missing path"}, status=400)
    return web.json_response(_bridge(["run", path], timeout=40))


@require_user
async def kb_query(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    q = str(body.get("query") or "").strip()
    if not q:
        return web.json_response({"error": "query required"}, status=400)
    top_k = int(body.get("top_k") or 5)
    synthesize = bool(body.get("synthesize"))
    args = ["kb", q, "--top-k", str(top_k)]
    if synthesize:
        args.append("--synthesize")
    return web.json_response(_bridge(args, timeout=60))


@require_user
async def get_quiz(request: web.Request) -> web.Response:
    tid = request.match_info["tid"]
    return web.json_response(_bridge(["quiz", tid]))


@require_user
async def get_diagram(request: web.Request) -> web.Response:
    tid = request.match_info["tid"]
    return web.json_response(_bridge(["diagram", tid]))


@require_user
async def get_progress(request: web.Request) -> web.Response:
    user = request.get("user", {})
    uid = user.get("id", "default")
    progress = _load_progress()
    user_progress = progress.get(uid, {"viewed": [], "completed": [], "quiz_scores": {}})
    return web.json_response(user_progress)


@require_user
async def save_progress(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    user = request.get("user", {})
    uid = user.get("id", "default")
    progress = _load_progress()
    progress[uid] = {
        "viewed": body.get("viewed", progress.get(uid, {}).get("viewed", [])),
        "completed": body.get("completed", progress.get(uid, {}).get("completed", [])),
        "quiz_scores": body.get("quiz_scores", progress.get(uid, {}).get("quiz_scores", {})),
    }
    _save_progress(progress)
    return web.json_response({"ok": True})


@require_user
async def web_fetch(request: web.Request) -> web.Response:
    body = await request.json() if request.can_read_body else {}
    url = str(body.get("url") or "").strip()
    if not url:
        return web.json_response({"error": "url required"}, status=400)
    use_llm = bool(body.get("use_llm"))
    args = ["web", url]
    if use_llm:
        args.append("--use-llm")
    return web.json_response(_bridge(args, timeout=60))


def setup_learn_routes(app: web.Application) -> None:
    app.router.add_get("/api/learn/topics", list_topics)
    app.router.add_get("/api/learn/topic/{tid}", get_topic)
    app.router.add_post("/api/learn/run", run_demo)
    app.router.add_post("/api/learn/kb", kb_query)
    app.router.add_get("/api/learn/quiz/{tid}", get_quiz)
    app.router.add_get("/api/learn/diagram/{tid}", get_diagram)
    app.router.add_get("/api/learn/progress", get_progress)
    app.router.add_post("/api/learn/progress", save_progress)
    app.router.add_post("/api/learn/chat", chat)
    app.router.add_post("/api/learn/web", web_fetch)


def _chat(body):
    topic = str(body.get("topic") or "").strip()
    question = str(body.get("question") or "").strip()
    if not question:
        return {"error": "问题 required", "reply": "请输入你的问题"}
    # 简单的本地知识库检索（基于 topics/ 目录下的 markdown）
    # 优先返回本地知识点的简短回答，否则尝试调用 LLM
    import os, json
    topics_dir = Path(__file__).resolve().parents[3] / "agent-learning" / "topics"
    reply = None
    if topics_dir.exists():
        for fp in sorted(topics_dir.glob("*.md")):
            try:
                content = fp.read_text(encoding="utf-8")
                if question.lower() in content.lower():
                    # 提取简短回答（首段）
                    lines = content.split("\n")
                    short = ""
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith("#") and len(line) < 200:
                            short = line
                            break
                    if short:
                        reply = short
                        break
            except Exception:
                continue
    if reply is None:
        # 调用 LLM（受 InsForge/LLM 配置限制，此处占位）
        reply = f"关于「{question}」的知识点：见 topics/{topic or '01'}/readme.md 了解详情"
    return {"reply": reply}


async def chat(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    return web.json_response(_chat(body))
