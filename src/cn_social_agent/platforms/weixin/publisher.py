"""WeChat Official Account publisher (P1)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from cn_social_agent.platforms.base import PublishResult
from cn_social_agent.platforms.tokens import load_platform_config, load_token, save_token
from cn_social_agent.platforms.weixin import api as wxapi

# Process-local access_token cache: app_id -> (token, expires_at)
_token_cache: dict[str, tuple[str, float]] = {}


class WeixinPublisher:
    name = "weixin"

    async def _creds(self) -> tuple[str, str]:
        cfg = await load_platform_config("weixin")
        app_id = str(cfg.get("app_id") or os.getenv("WEIXIN_APP_ID") or "").strip()
        app_secret = str(cfg.get("app_secret") or os.getenv("WEIXIN_APP_SECRET") or "").strip()
        return app_id, app_secret

    async def _access_token(self, app_id: str, app_secret: str) -> str:
        now = time.time()
        cached = _token_cache.get(app_id)
        if cached and cached[1] > now + 60:
            return cached[0]
        token = await wxapi.get_access_token(app_id, app_secret)
        _token_cache[app_id] = (token, now + 7000)
        return token

    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str:
        # P1: server credentials — authorize is a no-op confirm redirect
        sep = "&" if "?" in redirect_uri else "?"
        return f"{redirect_uri}{sep}code=server_cred&state={state}&user_id={user_id}"

    async def handle_callback(
        self, *, user_id: str, query: dict[str, str]
    ) -> dict[str, Any]:
        app_id, app_secret = await self._creds()
        if not app_id or not app_secret:
            return {
                "ok": False,
                "message": "未配置 WEIXIN_APP_ID / WEIXIN_APP_SECRET（或 InsForge 平台配置）",
            }
        await save_token(
            "weixin",
            user_id,
            {
                "authorized": True,
                "account": app_id,
                "mode": "server_cred",
                "ts": int(time.time()),
            },
        )
        return {"ok": True, "account": app_id}

    async def status(self, *, user_id: str) -> dict[str, Any]:
        app_id, app_secret = await self._creds()
        ready = bool(app_id and app_secret)
        tok = await load_token("weixin", user_id)
        # Server cred mode: configured ⇒ treated as authorized
        authorized = ready and (bool(tok) or ready)
        return {
            "platform": "weixin",
            "ready": ready,
            "authorized": authorized,
            "account": (tok or {}).get("account") or (app_id[:8] + "…" if app_id else ""),
            "message": (
                "公众号凭证已配置，可直接发布"
                if ready
                else "请先在顶栏「平台」填写 AppID / AppSecret"
            ),
        }

    async def publish(
        self,
        *,
        user_id: str,
        title: str,
        image_paths: list[Path],
        direct: bool,
        meta: dict[str, Any],
    ) -> PublishResult:
        app_id, app_secret = await self._creds()
        if not app_id or not app_secret:
            return {
                "platform": "weixin",
                "status": "skipped",
                "external_id": "",
                "url": "",
                "message": "未配置微信公众号凭证，已跳过",
            }
        if not image_paths:
            return {
                "platform": "weixin",
                "status": "failed",
                "external_id": "",
                "url": "",
                "message": "无图片可发布",
            }
        try:
            access = await self._access_token(app_id, app_secret)
            urls: list[str] = []
            for p in image_paths:
                urls.append(await wxapi.upload_content_image(access, p))
            thumb_id = await wxapi.upload_thumb(access, image_paths[0])
            html = "".join(f'<p style="text-align:center;"><img src="{u}"/></p>' for u in urls)
            author = (
                str(meta.get("author") or "").strip()
                or os.getenv("WEIXIN_DRAFT_AUTHOR", "知识卡片")
            )
            media_id = await wxapi.draft_add(
                access,
                title=title,
                author=author,
                content_html=html,
                thumb_media_id=thumb_id,
                digest=title,
            )
            if direct:
                try:
                    pub = await wxapi.freepublish_submit(access, media_id)
                    return {
                        "platform": "weixin",
                        "status": "published",
                        "external_id": str(pub.get("publish_id") or media_id),
                        "url": "",
                        "message": f"已提交发表 · {title}",
                    }
                except Exception as exc:  # noqa: BLE001
                    return {
                        "platform": "weixin",
                        "status": "draft",
                        "external_id": media_id,
                        "url": "",
                        "message": f"发表失败已保留草稿：{exc}",
                    }
            return {
                "platform": "weixin",
                "status": "draft",
                "external_id": media_id,
                "url": "",
                "message": f"已写入公众号草稿 · {title}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "platform": "weixin",
                "status": "failed",
                "external_id": "",
                "url": "",
                "message": f"微信发布失败：{exc}",
            }
