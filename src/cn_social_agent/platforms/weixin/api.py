"""WeChat Official Account HTTP helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

BASE = "https://api.weixin.qq.com"


class WeixinApiError(RuntimeError):
    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"weixin {errcode}: {errmsg}")


def _check(data: dict[str, Any]) -> dict[str, Any]:
    code = int(data.get("errcode") or 0)
    if code:
        raise WeixinApiError(code, str(data.get("errmsg") or "error"))
    return data


async def get_access_token(app_id: str, app_secret: str) -> str:
    url = f"{BASE}/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    if data.get("errcode"):
        _check(data)
    token = str(data.get("access_token") or "")
    if not token:
        raise WeixinApiError(-1, "missing access_token")
    return token


async def upload_content_image(access_token: str, path: Path) -> str:
    """Upload image for article HTML; returns CDN url."""
    url = f"{BASE}/cgi-bin/media/uploadimg"
    params = {"access_token": access_token}
    async with httpx.AsyncClient(timeout=60.0) as client:
        with path.open("rb") as f:
            files = {"media": (path.name, f, "image/png")}
            r = await client.post(url, params=params, files=files)
        r.raise_for_status()
        data = r.json()
    if data.get("errcode"):
        _check(data)
    out = str(data.get("url") or "")
    if not out:
        raise WeixinApiError(-1, "uploadimg missing url")
    return out


async def upload_thumb(access_token: str, path: Path) -> str:
    """Upload permanent image material; returns media_id for thumb."""
    url = f"{BASE}/cgi-bin/material/add_material"
    params = {"access_token": access_token, "type": "image"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        with path.open("rb") as f:
            files = {"media": (path.name, f, "image/png")}
            r = await client.post(url, params=params, files=files)
        r.raise_for_status()
        data = r.json()
    if data.get("errcode"):
        _check(data)
    mid = str(data.get("media_id") or "")
    if not mid:
        raise WeixinApiError(-1, "add_material missing media_id")
    return mid


async def draft_add(
    access_token: str,
    *,
    title: str,
    author: str,
    content_html: str,
    thumb_media_id: str,
    digest: str = "",
) -> str:
    url = f"{BASE}/cgi-bin/draft/add"
    params = {"access_token": access_token}
    body = {
        "articles": [
            {
                "title": title[:64],
                "author": author[:16],
                "digest": (digest or title)[:120],
                "content": content_html,
                "content_source_url": "",
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            url,
            params=params,
            content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
    if data.get("errcode"):
        _check(data)
    mid = str(data.get("media_id") or "")
    if not mid:
        raise WeixinApiError(-1, "draft/add missing media_id")
    return mid


async def freepublish_submit(access_token: str, media_id: str) -> dict[str, Any]:
    url = f"{BASE}/cgi-bin/freepublish/submit"
    params = {"access_token": access_token}
    body = {"media_id": media_id}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, params=params, json=body)
        r.raise_for_status()
        data = r.json()
    if data.get("errcode"):
        _check(data)
    return data
