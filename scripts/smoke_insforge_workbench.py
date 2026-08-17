#!/usr/bin/env python3
"""End-to-end smoke against a running workbench + InsForge."""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import httpx

BASE = os.getenv("WORKBENCH_URL", "http://127.0.0.1:18081")


async def main() -> int:
    email = f"wb-{uuid.uuid4().hex[:8]}@example.com"
    password = "test123456"
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0, trust_env=False) as c:
        health = (await c.get("/health")).json()
        print("health:", health)
        if health.get("store") != "insforge":
            print("FAIL: expected store=insforge")
            return 1

        reg = await c.post("/api/auth/register", json={"email": email, "password": password})
        print("register", reg.status_code, reg.text[:200])
        if reg.status_code >= 400:
            login = await c.post("/api/auth/login", json={"email": email, "password": password})
            data = login.json()
        else:
            data = reg.json()
            if not data.get("accessToken"):
                login = await c.post("/api/auth/login", json={"email": email, "password": password})
                data = login.json()

        token = data.get("accessToken") or data.get("access_token")
        if not token:
            print("FAIL: no token", data)
            return 1
        headers = {"Authorization": f"Bearer {token}"}

        me = await c.get("/api/auth/me", headers=headers)
        print("me", me.status_code, me.json())

        sess = await c.post("/api/sessions", headers=headers, json={"title": "e2e"})
        print("session", sess.status_code, sess.text[:300])
        sess.raise_for_status()
        sid = sess.json()["id"]

        chat = await c.post(
            "/api/chat",
            headers=headers,
            json={"session_id": sid, "content": "hello from e2e"},
        )
        print("chat", chat.status_code, chat.text[:300])
        chat.raise_for_status()

        detail = await c.get(f"/api/sessions/{sid}", headers=headers)
        msgs = detail.json().get("messages") or []
        print("messages", len(msgs))
        assert len(msgs) >= 2
        print("OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
