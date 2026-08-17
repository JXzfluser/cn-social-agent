"""OAuth / platform auth routes for card publish."""

from __future__ import annotations

import os
from urllib.parse import quote

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.cards.history import history_owner_key
from cn_social_agent.platforms import get_publisher, list_platforms
from cn_social_agent.platforms.tokens import (
    clear_token,
    load_platform_config,
    mask_secret,
    save_platform_config,
    secrets_backend_status,
)

_CONFIG_PLATFORMS = frozenset({"weixin", "toutiao", "douyin"})


def _public_base(request: web.Request) -> str:
    base = (os.getenv("OAUTH_PUBLIC_BASE") or "").strip().rstrip("/")
    if base:
        return base
    return str(request.url.origin()).rstrip("/")


def _mock_allowed(request: web.Request) -> bool:
    if os.getenv("CARD_PUBLISH_ALLOW_MOCK", "").strip() in ("1", "true", "yes"):
        return True
    state = get_state(request)
    return state.llm_mode == "mock"


@require_user
async def oauth_status(request: web.Request) -> web.Response:
    platform = (request.match_info.get("platform") or "").strip().lower()
    if platform == "mock" and not _mock_allowed(request):
        return web.json_response({"error": "mock not allowed"}, status=403)
    user = request["user"]
    owner = history_owner_key(user_id=user["id"], email=user.get("email"))
    try:
        pub = get_publisher(platform)
    except KeyError:
        return web.json_response({"error": f"unknown platform: {platform}"}, status=404)
    st = await pub.status(user_id=owner)
    st["secrets"] = secrets_backend_status()
    return web.json_response(st)


@require_user
async def oauth_authorize(request: web.Request) -> web.Response:
    """Confirm / start auth. Weixin uses server credentials — no popup needed."""
    platform = (request.match_info.get("platform") or "").strip().lower()
    if platform == "mock" and not _mock_allowed(request):
        return web.json_response({"error": "mock not allowed"}, status=403)
    user = request["user"]
    owner = history_owner_key(user_id=user["id"], email=user.get("email"))
    try:
        pub = get_publisher(platform)
    except KeyError:
        return web.json_response({"error": f"unknown platform: {platform}"}, status=404)

    st = await pub.status(user_id=owner)
    if not st.get("ready"):
        msg = st.get("message") or "请先填写 AppID / AppSecret"
        return web.json_response(
            {
                "ok": False,
                "error": msg,
                "needs_config": True,
                "platform": platform,
                "message": msg,
                "secrets": secrets_backend_status(),
            },
            status=400,
        )

    # In-place confirm: weixin (server creds), mock, xiaohongshu (half-auto)
    if platform in ("weixin", "mock", "xiaohongshu"):
        code = "half_auto" if platform == "xiaohongshu" else "server_cred"
        result = await pub.handle_callback(
            user_id=owner, query={"code": code, "state": owner}
        )
        return web.json_response(
            {
                "ok": bool(result.get("ok")),
                "inline": True,
                "platform": platform,
                "account": result.get("account") or "",
                "message": result.get("message")
                or ("已确认授权" if result.get("ok") else "授权失败"),
                "half_auto": bool(st.get("half_auto")),
                "creator_url": st.get("creator_url") or "",
                "secrets": secrets_backend_status(),
            }
        )

    base = _public_base(request)
    redirect_uri = f"{base}/api/oauth/{platform}/callback"
    auth_url = pub.auth_url(user_id=owner, redirect_uri=redirect_uri, state=owner)
    return web.json_response(
        {
            "ok": True,
            "auth_url": auth_url,
            "platform": platform,
            "secrets": secrets_backend_status(),
        }
    )


async def oauth_callback(request: web.Request) -> web.Response:
    platform = (request.match_info.get("platform") or "").strip().lower()
    q = {k: str(v) for k, v in request.rel_url.query.items()}
    state = (q.get("state") or q.get("user_id") or "").strip()
    if not state:
        raise web.HTTPFound("/?mode=card&oauth=err&msg=" + quote("missing state"))
    try:
        pub = get_publisher(platform)
    except KeyError:
        raise web.HTTPFound("/?mode=card&oauth=err&msg=" + quote("unknown platform"))
    result = await pub.handle_callback(user_id=state, query=q)
    if result.get("ok"):
        raise web.HTTPFound(f"/?mode=card&oauth=ok&platform={quote(platform)}")
    msg = quote(str(result.get("message") or "auth failed"))
    raise web.HTTPFound(f"/?mode=card&oauth=err&platform={quote(platform)}&msg={msg}")


@require_user
async def oauth_unbind(request: web.Request) -> web.Response:
    platform = (request.match_info.get("platform") or "").strip().lower()
    user = request["user"]
    owner = history_owner_key(user_id=user["id"], email=user.get("email"))
    ok = await clear_token(platform, owner)
    return web.json_response({"ok": ok, "platform": platform})


@require_user
async def oauth_platforms(_request: web.Request) -> web.Response:
    return web.json_response(
        {"platforms": list_platforms(), "secrets": secrets_backend_status()}
    )


@require_user
async def get_platform_config(request: web.Request) -> web.Response:
    platform = (request.match_info.get("platform") or "").strip().lower()
    if platform == "xiaohongshu":
        return web.json_response(
            {
                "platform": "xiaohongshu",
                "app_id": "",
                "app_secret_masked": "",
                "has_secret": False,
                "author": "",
                "configured": True,
                "half_auto": True,
                "creator_url": "https://creator.xiaohongshu.com/publish/publish",
                "message": "小红书为半自动：导出图集 → 复制文案 → 创作者中心粘贴",
                "secrets": secrets_backend_status(),
            }
        )
    if platform not in _CONFIG_PLATFORMS:
        return web.json_response({"error": f"unsupported: {platform}"}, status=404)
    cfg = await load_platform_config(platform)
    if platform == "weixin":
        app_id = str(cfg.get("app_id") or os.getenv("WEIXIN_APP_ID") or "")
        app_secret = str(cfg.get("app_secret") or os.getenv("WEIXIN_APP_SECRET") or "")
        author = str(cfg.get("author") or os.getenv("WEIXIN_DRAFT_AUTHOR") or "")
    elif platform == "douyin":
        app_id = str(
            cfg.get("client_key")
            or cfg.get("app_id")
            or os.getenv("DOUYIN_CLIENT_KEY")
            or ""
        )
        app_secret = str(
            cfg.get("client_secret")
            or cfg.get("app_secret")
            or os.getenv("DOUYIN_CLIENT_SECRET")
            or ""
        )
        author = ""
    else:
        app_id = str(cfg.get("app_id") or os.getenv("TOUTIAO_APP_ID") or "")
        app_secret = str(cfg.get("app_secret") or os.getenv("TOUTIAO_APP_SECRET") or "")
        author = ""
    return web.json_response(
        {
            "platform": platform,
            "app_id": app_id,
            "app_secret_masked": mask_secret(app_secret),
            "has_secret": bool(app_secret),
            "author": author,
            "configured": bool(app_id and app_secret),
            "secrets": secrets_backend_status(),
        }
    )


@require_user
async def put_platform_config(request: web.Request) -> web.Response:
    platform = (request.match_info.get("platform") or "").strip().lower()
    if platform not in _CONFIG_PLATFORMS:
        return web.json_response({"error": f"unsupported: {platform}"}, status=404)
    body = await request.json() if request.can_read_body else {}
    app_id = str(body.get("app_id") or "").strip()
    app_secret = str(body.get("app_secret") or "").strip()
    author = str(body.get("author") or "").strip()
    existing = await load_platform_config(platform)
    if not app_secret and existing.get("app_secret"):
        app_secret = str(existing.get("app_secret") or "")
    if not app_id or not app_secret:
        return web.json_response(
            {"error": "app_id 与 app_secret 均必填（密钥可留空表示不改）"},
            status=400,
        )
    data = {
        "app_id": app_id,
        "app_secret": app_secret,
        "source": "ui",
    }
    if platform == "douyin":
        data["client_key"] = app_id
        data["client_secret"] = app_secret
    if platform == "weixin" and author:
        data["author"] = author
    if platform == "toutiao":
        redir = str(
            body.get("redirect_uri") or os.getenv("TOUTIAO_REDIRECT_URI") or ""
        ).strip()
        if redir:
            data["redirect_uri"] = redir
    ok = await save_platform_config(platform, data)
    return web.json_response(
        {
            "ok": True,
            "platform": platform,
            "configured": True,
            "saved_to_insforge": ok,
            "secrets": secrets_backend_status(),
            "message": (
                "已保存到 InsForge Secrets"
                if ok
                else "InsForge 写入失败，已保存到本地 data/oauth/config"
            ),
        }
    )


def setup_oauth_routes(app: web.Application) -> None:
    app.router.add_get("/api/oauth/platforms", oauth_platforms)
    app.router.add_get("/api/oauth/{platform}/status", oauth_status)
    app.router.add_get("/api/oauth/{platform}/authorize", oauth_authorize)
    app.router.add_get("/api/oauth/{platform}/callback", oauth_callback)
    app.router.add_get("/api/oauth/{platform}/config", get_platform_config)
    app.router.add_put("/api/oauth/{platform}/config", put_platform_config)
    app.router.add_delete("/api/oauth/{platform}", oauth_unbind)
