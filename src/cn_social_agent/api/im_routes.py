"""IM 远程指挥（通用 Webhook 通道，对标 OpenWorkBuddy「IM 远程指挥」）。

每个用户有一个入站 secret：外部系统（飞书机器人 relay、快捷指令、curl…）
POST ``{"secret": ..., "message": ...}`` 即可远程给 agent 下任务，
同步拿回回复。无需任何第三方凭据。
"""

from __future__ import annotations

import secrets

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user

KindError = web.HTTPBadRequest


def _im_prefs(prefs: dict) -> dict:
    im = prefs.get("im_webhook") if isinstance(prefs.get("im_webhook"), dict) else {}
    return {
        "enabled": bool(im.get("enabled", True)),
        "secret": str(im.get("secret") or ""),
    }


async def _ensure_secret(state, user_id: str) -> dict:
    prefs = await state.store.get_user_prefs(user_id)
    im = _im_prefs(prefs if isinstance(prefs, dict) else {})
    if not im["secret"]:
        im["secret"] = "im_" + secrets.token_hex(12)
        merged = dict(prefs if isinstance(prefs, dict) else {})
        merged["im_webhook"] = im
        await state.store.upsert_user_prefs(user_id, merged)
    return im


@require_user
async def get_im_config(request: web.Request) -> web.Response:
    state = get_state(request)
    user_id = request["user"]["id"]
    im = await _ensure_secret(state, user_id)
    return web.json_response({
        "enabled": im["enabled"],
        "secret": im["secret"],
        "inbound_path": "/api/im/inbound",
        "example": (
            f'curl -X POST <host>/api/im/inbound '
            f'-d \'{{"secret": "{im["secret"]}", "message": "写一句朋友圈文案"}}\''
        ),
    })


@require_user
async def put_im_config(request: web.Request) -> web.Response:
    state = get_state(request)
    user_id = request["user"]["id"]
    body = await request.json() if request.can_read_body else {}
    prefs = await state.store.get_user_prefs(user_id)
    im = await _ensure_secret(state, user_id)
    if "enabled" in body:
        im["enabled"] = bool(body.get("enabled"))
    if body.get("reset_secret"):
        im["secret"] = "im_" + secrets.token_hex(12)
    merged = dict(prefs if isinstance(prefs, dict) else {})
    merged["im_webhook"] = im
    await state.store.upsert_user_prefs(user_id, merged)
    return web.json_response({"ok": True, **im})


async def _all_users(state) -> list[dict]:
    """用户清单：协议方法优先，memory store 回退到内部 users 表。"""
    if hasattr(state.store, "list_users"):
        try:
            return list(await state.store.list_users())
        except Exception:  # noqa: BLE001
            pass
    users = getattr(state.store, "users", None)
    if isinstance(users, dict):
        return [{"id": v["id"], "email": k} for k, v in users.items()]
    return []


def _user_id_by_secret(secret: str) -> str | None:
    """按 secret 扫描本地 prefs extras 反查用户（InsForge 模式无 list_users API，
    而 im_webhook secret 恰好持久在每用户一个的 extras 文件里——文件名即 user_id）。"""
    import json
    from cn_social_agent.api.prefs_local import prefs_dir

    try:
        for path in prefs_dir().glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            im = data.get("im_webhook") or {}
            if isinstance(im, dict) and im.get("secret") and secrets.compare_digest(str(im["secret"]), secret):
                return path.stem
    except Exception:  # noqa: BLE001
        pass
    return None


async def inbound(request: web.Request) -> web.Response:
    """外部系统入口：secret 鉴权 → agent 处理 → 同步回复。"""
    state = get_state(request)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return web.json_response({"error": "invalid json"}, status=400)
    secret = str(body.get("secret") or "").strip()
    message = str(body.get("message") or "").strip()
    if not secret or not message:
        return web.json_response({"error": "secret and message required"}, status=400)

    # 按 secret 反查用户：先走用户清单比对，InsForge 等无清单存储回退到 extras 文件扫描
    target = None
    for u in await _all_users(state):
        prefs = await state.store.get_user_prefs(u["id"])
        im = _im_prefs(prefs if isinstance(prefs, dict) else {})
        if im["secret"] and secrets.compare_digest(im["secret"], secret):
            target = (u, im)
            break
    if target is None:
        uid = _user_id_by_secret(secret)
        if uid:
            try:
                prefs = await state.store.get_user_prefs(uid)
            except Exception:  # noqa: BLE001
                from cn_social_agent.api.prefs_local import read_extras
                prefs = read_extras(uid)
            target = ({"id": uid, "email": ""}, _im_prefs(prefs if isinstance(prefs, dict) else {}))
    if target is None:
        return web.json_response({"error": "invalid secret"}, status=401)
    user, im = target
    if not im["enabled"]:
        return web.json_response({"error": "im channel disabled"}, status=403)

    user_id = user["id"]
    # 会话：IM 远程统一进「IM 远程指挥」会话，历史可回看
    sessions = await state.store.list_sessions(user_id)
    session = next((s for s in sessions if s.get("title") == "IM 远程指挥"), None)
    if session is None:
        session = await state.store.create_session(user_id, title="IM 远程指挥")
    session_id = session["id"]

    assert state.agent is not None
    try:
        reply = await state.agent.run(
            [{"role": "user", "content": message}],
            user_id=user_id,
            email=str(user.get("email") or ""),
            store_mode=state.store_mode,
        )
    except Exception as exc:  # noqa: BLE001 — 对外只回错误摘要
        return web.json_response({"error": f"agent failed: {exc}"}, status=502)

    content = reply.content or ""
    await state.store.add_message(user_id, session_id, role="user", content=message)
    await state.store.add_message(
        user_id, session_id, role="assistant", content=content,
        tool_calls=reply.tool_calls or None,
    )
    return web.json_response({"ok": True, "reply": content, "session_id": session_id})


def setup_im_routes(app: web.Application) -> None:
    app.router.add_get("/api/im/config", get_im_config)
    app.router.add_put("/api/im/config", put_im_config)
    app.router.add_post("/api/im/inbound", inbound)
