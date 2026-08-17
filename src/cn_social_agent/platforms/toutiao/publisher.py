"""Toutiao (Jinri Toutiao) publisher skeleton — skipped until API ready."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from cn_social_agent.platforms.base import PublishResult
from cn_social_agent.platforms.tokens import load_platform_config, load_token, save_token


class ToutiaoPublisher:
    name = "toutiao"

    async def _creds(self) -> tuple[str, str]:
        cfg = await load_platform_config("toutiao")
        app_id = str(cfg.get("app_id") or os.getenv("TOUTIAO_APP_ID") or "").strip()
        app_secret = str(
            cfg.get("app_secret") or os.getenv("TOUTIAO_APP_SECRET") or ""
        ).strip()
        return app_id, app_secret

    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str:
        app_id = (os.getenv("TOUTIAO_APP_ID") or "").strip()
        redirect = (
            os.getenv("TOUTIAO_REDIRECT_URI") or redirect_uri
        ).strip() or redirect_uri
        if not app_id:
            sep = "&" if "?" in redirect_uri else "?"
            return f"{redirect_uri}{sep}code=pending&state={state}&error=not_configured"
        # Placeholder OAuth URL shape — real endpoint TBD when API opens
        from urllib.parse import quote

        return (
            "https://open.douyin.com/platform/oauth/connect/"
            f"?client_key={quote(app_id)}"
            f"&response_type=code&scope=user_info"
            f"&redirect_uri={quote(redirect)}"
            f"&state={quote(state or user_id)}"
        )

    async def handle_callback(
        self, *, user_id: str, query: dict[str, str]
    ) -> dict[str, Any]:
        code = (query.get("code") or "").strip()
        if not code or code in ("pending", "not_configured"):
            return {"ok": False, "message": "头条 OAuth 未开通或未配置"}
        await save_token(
            "toutiao",
            user_id,
            {
                "authorized": True,
                "code": code,
                "account": "toutiao",
                "ts": int(time.time()),
                "note": "placeholder — token exchange TBD",
            },
        )
        return {"ok": True, "account": "toutiao", "message": "已记录授权码（发帖 API 待开通）"}

    async def status(self, *, user_id: str) -> dict[str, Any]:
        app_id, app_secret = await self._creds()
        has_cred = bool(app_id and app_secret)
        tok = await load_token("toutiao", user_id)
        return {
            "platform": "toutiao",
            "ready": False,
            "authorized": bool(tok),
            "account": (tok or {}).get("account") or "",
            "message": (
                "头条发帖 API 待开通（可先保存 AppID）"
                if has_cred
                else "请先填写 AppID / AppSecret（发布面板内可配置）"
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
        return {
            "platform": "toutiao",
            "status": "skipped",
            "external_id": "",
            "url": "",
            "message": f"头条发帖 API 待开通，已跳过（{len(image_paths)} 图 · {title}）",
        }
