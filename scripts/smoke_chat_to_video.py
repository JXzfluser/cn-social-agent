#!/usr/bin/env python3
"""Smoke: chat session → from-session → video project card payload."""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

BASE = os.getenv("WORKBENCH_URL", "http://127.0.0.1:18081").rstrip("/")
EMAIL = os.getenv("WB_EMAIL", "demo@local.test")
PASSWORD = os.getenv("WB_PASSWORD", "demo123456")


async def main() -> int:
    async with httpx.AsyncClient(
        base_url=BASE, timeout=180.0, trust_env=False
    ) as c:
        health = await c.get("/health")
        print("health", health.status_code, health.json())
        login = await c.post(
            "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        if login.status_code >= 400:
            reg = await c.post(
                "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
            )
            print("register", reg.status_code)
            login = await c.post(
                "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
            )
        login.raise_for_status()
        token = login.json().get("accessToken") or login.json().get("access_token")
        h = {"Authorization": f"Bearer {token}"}

        sess = await c.post("/api/sessions", headers=h, json={})
        sess.raise_for_status()
        sid = sess.json()["id"]
        print("session", sid)

        chat = await c.post(
            "/api/chat",
            headers=h,
            json={
                "session_id": sid,
                "content": (
                    "我想做一条口播短视频：三分钟讲清什么是 AI Agent，"
                    "卖点是普通人也能用 Agent 省时间写周报。语气活泼。"
                ),
                "stream": False,
            },
        )
        print("chat", chat.status_code)
        if chat.status_code >= 400:
            print(chat.text[:400])
            return 1

        fs = await c.post(
            "/api/video/from-session",
            headers=h,
            json={"session_id": sid, "target_seconds": 30},
        )
        print("from-session", fs.status_code, fs.text[:500])
        if fs.status_code not in (200, 201):
            return 1
        data = fs.json()
        pid = data["project"]["id"]
        assert data.get("scenes"), "expected scenes"
        assert data.get("message", {}).get("tool_calls"), "expected card message"
        print("project", pid, "scenes", len(data["scenes"]))
        print("ok")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
