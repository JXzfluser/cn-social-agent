#!/usr/bin/env python3
"""Produce a 3-part GitHub hotspot short-video series (intro / idea / compare) as L0 drafts."""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

BASE = os.getenv("WORKBENCH_URL", "http://127.0.0.1:18081").rstrip("/")
EMAIL = os.getenv("WB_EMAIL", "demo@local.test")
PASSWORD = os.getenv("WB_PASSWORD", "demo123456")
REPO = os.getenv("GH_REPO", "openclaw/openclaw")

SERIES = [
    {
        "content_angle": "intro",
        "target_seconds": 120,
        "topic": f"{REPO} 入门：个人 AI 助手怎么跑起来",
        "brief": "Star 暴涨的开源个人 AI 助手；一句话是什么；谁适合；三步上手；验证；一个常见坑；约2分钟有价值口播",
        "audience": "想自己跑本地/个人 AI 助手的独立开发者",
        "scene_setting": "刷到满屏 OpenClaw，想装但怕踩坑",
        "cta": "评论区扣「入门」，发最小安装清单",
    },
    {
        "content_angle": "idea",
        "target_seconds": 90,
        "topic": f"{REPO} 核心思想：为什么个人 AI 要 Own Your Data",
        "brief": "爆火不只是功能多；核心是自己的助手、自己的设备、自己的数据；误区；记住一句话；约90秒",
        "audience": "关心隐私与工作流的程序员",
        "scene_setting": "所有聊天都在别人云上，想要一只『自己的龙虾』",
        "cta": "收藏这篇，下期对比它和常见聊天助手",
    },
    {
        "content_angle": "compare",
        "target_seconds": 120,
        "topic": f"{REPO} 对比：和个人向 Chat AI / Agent IDE 差在哪",
        "brief": "别跟风装错；对比云端聊天助手与 IDE Agent：谁适合日常个人助理、谁适合写代码；选型结论；约2分钟",
        "audience": "已经在用 ChatGPT/Cursor 的开发者",
        "scene_setting": "工具装了一堆，不知道 OpenClaw 该不该再占一个坑",
        "cta": "你现在主力是哪类工具？评论区告诉我",
    },
]


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=300.0, trust_env=False) as c:
        health = (await c.get("/health")).json()
        print("health", health)
        login = await c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code >= 400:
            await c.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
            login = await c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login.json().get("accessToken") or login.json().get("access_token")
        if not token:
            print("login failed", login.text)
            return 1
        headers = {"Authorization": f"Bearer {token}"}

        created = []
        for spec in SERIES:
            print("\n==>", spec["content_angle"], spec["topic"])
            p = await c.post(
                "/api/video/projects",
                headers=headers,
                json={
                    "topic": spec["topic"],
                    "title": spec["topic"][:40],
                    "target_seconds": spec["target_seconds"],
                    "tone": "硬核但不装",
                    "voice": "zh-CN-YunxiNeural",
                },
            )
            if p.status_code >= 400:
                print("create fail", p.status_code, p.text[:300])
                return 1
            pid = p.json()["id"]
            g = await c.post(
                f"/api/video/projects/{pid}/generate",
                headers=headers,
                json={
                    "target_seconds": spec["target_seconds"],
                    "tone": "硬核但不装",
                    "audience": spec["audience"],
                    "scene_setting": spec["scene_setting"],
                    "platform": "抖音",
                    "cta": spec["cta"],
                    "brief": spec["brief"],
                    "content_angle": spec["content_angle"],
                    "bg_theme": "neon",
                    "motion": "kenburns",
                },
            )
            if g.status_code >= 400:
                print("generate fail", g.status_code, g.text[:400])
                return 1
            title = (g.json().get("project") or {}).get("title")
            print("generated", pid, title)
            conf = await c.post(
                f"/api/video/projects/{pid}/confirm-storyboard",
                headers=headers,
                json={},
            )
            if conf.status_code >= 400:
                print("confirm fail", conf.status_code, conf.text[:200])
                return 1
            r = await c.post(
                f"/api/video/projects/{pid}/render",
                headers=headers,
                json={"delivery_level": "l0"},
            )
            print("render accepted", r.status_code, r.json().get("message"))
            # poll
            for _ in range(120):
                await asyncio.sleep(2)
                st = await c.get(f"/api/video/projects/{pid}/status", headers=headers)
                job = (st.json() or {}).get("job") or {}
                if job.get("status") in ("done", "failed"):
                    print("job", job.get("status"), job.get("message"), job.get("output_path"))
                    created.append(
                        {
                            "id": pid,
                            "angle": spec["content_angle"],
                            "title": title,
                            "status": job.get("status"),
                            "path": job.get("output_path"),
                        }
                    )
                    break
            else:
                print("timeout", pid)
                created.append({"id": pid, "angle": spec["content_angle"], "status": "timeout"})

        print("\n=== SERIES READY ===")
        for row in created:
            print(row)
        return 0 if all(x.get("status") == "done" for x in created) else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
