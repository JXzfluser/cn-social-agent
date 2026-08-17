#!/usr/bin/env python3
"""Smoke: create video project → generate → render → download."""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = os.getenv("WORKBENCH_URL", "http://127.0.0.1:18081")


async def main() -> int:
    email = f"vid-{uuid.uuid4().hex[:8]}@example.com"
    password = "test123456"
    async with httpx.AsyncClient(base_url=BASE, timeout=180.0, trust_env=False) as c:
        health = (await c.get("/health")).json()
        print("health", health)
        if health.get("store") != "insforge":
            print("FAIL: need insforge store")
            return 1

        reg = await c.post("/api/auth/register", json={"email": email, "password": password})
        data = reg.json() if reg.status_code < 400 else {}
        token = data.get("accessToken")
        if not token:
            login = await c.post("/api/auth/login", json={"email": email, "password": password})
            token = login.json().get("accessToken")
        assert token, "no token"
        h = {"Authorization": f"Bearer {token}"}

        proj = await c.post(
            "/api/video/projects",
            headers=h,
            json={"topic": "三分钟讲清什么是 AI Agent", "target_seconds": 30},
        )
        print("create", proj.status_code, proj.text[:200])
        proj.raise_for_status()
        pid = proj.json()["id"]

        gen = await c.post(f"/api/video/projects/{pid}/generate", headers=h, json={})
        print("generate", gen.status_code, gen.text[:400])
        gen.raise_for_status()
        scenes = gen.json().get("scenes") or []
        print("scenes", len(scenes))
        assert scenes, "no scenes"

        conf = await c.post(
            f"/api/video/projects/{pid}/confirm-storyboard",
            headers=h,
            json={},
        )
        print("confirm", conf.status_code, conf.text[:200])
        conf.raise_for_status()

        rend = await c.post(f"/api/video/projects/{pid}/render", headers=h, json={})
        print("render", rend.status_code, rend.text[:200])
        rend.raise_for_status()

        for i in range(120):
            st = await c.get(f"/api/video/projects/{pid}/status", headers=h)
            job = st.json().get("job") or {}
            print("status", job.get("status"), job.get("progress"), job.get("message"))
            if job.get("status") == "done":
                break
            if job.get("status") == "failed":
                print("FAIL render", job)
                return 1
            await asyncio.sleep(2)
        else:
            print("FAIL timeout")
            return 1

        dl = await c.get(f"/api/video/projects/{pid}/download", headers=h)
        print("download", dl.status_code, "bytes", len(dl.content))
        if dl.status_code != 200 or len(dl.content) < 1000:
            print("FAIL download")
            return 1
        out = Path("data/videos/_smoke_final.mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(dl.content)
        print("OK wrote", out)
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
