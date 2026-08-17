"""Douyin OAuth + video publish (real upload when creds present; else half-auto)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from cn_social_agent.platforms.base import PublishResult
from cn_social_agent.platforms.tokens import load_platform_config, load_token, save_token
from cn_social_agent.platforms.video_base import VideoPublishResult
from cn_social_agent.video.presentation import CREATOR_UPLOAD_URL, half_auto_douyin_payload


class DouyinPublisher:
    """Card-compatible publisher registered for OAuth config UI."""

    name = "douyin"

    async def _creds(self) -> tuple[str, str]:
        cfg = await load_platform_config("douyin")
        key = str(
            cfg.get("client_key")
            or cfg.get("app_id")
            or os.getenv("DOUYIN_CLIENT_KEY")
            or ""
        ).strip()
        secret = str(
            cfg.get("client_secret")
            or cfg.get("app_secret")
            or os.getenv("DOUYIN_CLIENT_SECRET")
            or ""
        ).strip()
        return key, secret

    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str:
        client_key = (os.getenv("DOUYIN_CLIENT_KEY") or "").strip()
        redirect = (os.getenv("DOUYIN_REDIRECT_URI") or redirect_uri).strip() or redirect_uri
        if not client_key:
            sep = "&" if "?" in redirect_uri else "?"
            return f"{redirect_uri}{sep}code=pending&state={state}&error=not_configured"
        return (
            "https://open.douyin.com/platform/oauth/connect/"
            f"?client_key={quote(client_key)}"
            f"&response_type=code&scope=user_info,video.create"
            f"&redirect_uri={quote(redirect)}"
            f"&state={quote(state or user_id)}"
        )

    async def handle_callback(
        self, *, user_id: str, query: dict[str, str]
    ) -> dict[str, Any]:
        code = (query.get("code") or "").strip()
        if not code or code in ("pending", "not_configured"):
            return {"ok": False, "message": "抖音 OAuth 未配置或用户取消"}
        # Token exchange — if secret missing, store code only
        key, secret = await self._creds()
        token_payload: dict[str, Any] = {
            "authorized": True,
            "code": code,
            "account": "douyin",
            "ts": int(time.time()),
        }
        if key and secret:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://open.douyin.com/oauth/access_token/",
                        data={
                            "client_key": key,
                            "client_secret": secret,
                            "code": code,
                            "grant_type": "authorization_code",
                        },
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        data = await resp.json(content_type=None)
                inner = data.get("data") if isinstance(data, dict) else None
                if isinstance(inner, dict) and inner.get("access_token"):
                    token_payload.update(
                        {
                            "access_token": inner.get("access_token"),
                            "refresh_token": inner.get("refresh_token"),
                            "open_id": inner.get("open_id"),
                            "expires_in": inner.get("expires_in"),
                        }
                    )
                else:
                    token_payload["note"] = f"token exchange incomplete: {data}"
            except Exception as e:  # noqa: BLE001
                token_payload["note"] = f"token exchange failed: {e}"
        else:
            token_payload["note"] = "missing client secret — code stored only"
        await save_token("douyin", user_id, token_payload)
        return {"ok": True, "account": "douyin", "message": "抖音授权已保存"}

    async def status(self, *, user_id: str) -> dict[str, Any]:
        key, secret = await self._creds()
        has_cred = bool(key and secret)
        tok = await load_token("douyin", user_id)
        authorized = bool(tok and (tok.get("access_token") or tok.get("authorized")))
        ready = has_cred  # config present; upload may still degrade
        return {
            "platform": "douyin",
            "ready": ready,
            "authorized": authorized,
            "account": (tok or {}).get("open_id") or (tok or {}).get("account") or "",
            "message": (
                "已配置 Client Key；授权后可尝试上传，否则半自动发抖音"
                if has_cred
                else "请填写 DOUYIN_CLIENT_KEY / SECRET（或平台面板）；未配置时发抖音走半自动"
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
            "platform": "douyin",
            "status": "skipped",
            "external_id": "",
            "url": CREATOR_UPLOAD_URL,
            "message": "抖音卡片图发布未启用；请用短视频工坊「发抖音」上传视频",
        }


class DouyinVideoPublisher:
    name = "douyin"

    def __init__(self) -> None:
        self._oauth = DouyinPublisher()

    async def status(self, *, user_id: str) -> dict[str, Any]:
        return await self._oauth.status(user_id=user_id)

    async def publish_video(
        self,
        *,
        user_id: str,
        title: str,
        video_path: Path,
        hashtags: list[str],
        description: str,
        meta: dict[str, Any],
    ) -> VideoPublishResult:
        st = await self.status(user_id=user_id)
        tok = await load_token("douyin", user_id)
        access = (tok or {}).get("access_token") or ""
        open_id = (tok or {}).get("open_id") or ""
        if not st.get("ready") or not access or not open_id:
            return half_auto_douyin_payload(
                title=title, hashtags=hashtags, description=description
            )

        # Attempt Douyin video upload init + upload. API shapes evolve — fail clearly.
        try:
            import aiohttp

            size = video_path.stat().st_size
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://open.douyin.com/api/douyin/v1/video/upload_video/",
                    params={"open_id": open_id},
                    headers={"access-token": str(access)},
                    data={"video": video_path.read_bytes()},
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    status = resp.status
                    raw = await resp.text()
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:  # noqa: BLE001
                        data = {"raw": raw[:500]}
            if status >= 400:
                out = half_auto_douyin_payload(
                    title=title, hashtags=hashtags, description=description
                )
                out["status"] = "failed"
                out["message"] = f"抖音上传失败 HTTP {status}，已附半自动文案：{raw[:200]}"
                return out
            # Success path varies; treat presence of data as published/draft
            video_id = ""
            if isinstance(data, dict):
                inner = data.get("data") if isinstance(data.get("data"), dict) else data
                if isinstance(inner, dict):
                    video_id = str(
                        inner.get("video_id")
                        or inner.get("item_id")
                        or inner.get("id")
                        or ""
                    )
            if not video_id:
                out = half_auto_douyin_payload(
                    title=title, hashtags=hashtags, description=description
                )
                out["message"] = (
                    f"抖音接口已响应但未返回 video_id，请半自动上传。响应：{str(data)[:240]}"
                )
                return out
            return {
                "platform": "douyin",
                "status": "published",
                "external_id": video_id,
                "url": "",
                "message": f"已提交抖音上传（{size} bytes）",
            }
        except Exception as e:  # noqa: BLE001
            out = half_auto_douyin_payload(
                title=title, hashtags=hashtags, description=description
            )
            out["status"] = "failed"
            out["message"] = f"上传异常，已降级半自动：{type(e).__name__}: {e}"
            return out
