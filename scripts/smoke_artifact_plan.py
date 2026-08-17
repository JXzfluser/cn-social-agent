#!/usr/bin/env python3
"""Golden path: create → generate → production_plan script=done → L0 → l0=done.

Requires a running workbench with WORKBENCH_STORE=insforge.

  WORKBENCH_URL=http://127.0.0.1:18081 .venv/bin/python scripts/smoke_artifact_plan.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

import httpx

BASE = os.getenv("WORKBENCH_URL", "http://127.0.0.1:18081")
EMAIL = os.getenv("SMOKE_EMAIL", "")
PASSWORD = os.getenv("SMOKE_PASSWORD", "demo123456")


def _step_status(plan: dict, step_id: str) -> str:
    for s in plan.get("steps") or []:
        if s.get("id") == step_id:
            return s.get("status") or ""
    return ""


async def main() -> int:
    email = EMAIL or f"plan-{uuid.uuid4().hex[:8]}@example.com"
    async with httpx.AsyncClient(base_url=BASE, timeout=240.0, trust_env=False) as c:
        health = (await c.get("/health")).json()
        print("health", health)
        if health.get("store") != "insforge":
            print("FAIL: need insforge store")
            return 1

        token = None
        if EMAIL:
            login = await c.post(
                "/api/auth/login", json={"email": email, "password": PASSWORD}
            )
            token = (login.json() or {}).get("accessToken")
        if not token:
            reg = await c.post(
                "/api/auth/register", json={"email": email, "password": PASSWORD}
            )
            data = reg.json() if reg.status_code < 400 else {}
            token = data.get("accessToken")
            if not token:
                login = await c.post(
                    "/api/auth/login", json={"email": email, "password": PASSWORD}
                )
                token = (login.json() or {}).get("accessToken")
        if not token:
            print("FAIL: no token")
            return 1
        h = {"Authorization": f"Bearer {token}"}

        proj = await c.post(
            "/api/video/projects",
            headers=h,
            json={
                "topic": "Artifact Plan 冒烟：三分钟讲清 Agent",
                "target_seconds": 30,
                "content_angle": "intro",
            },
        )
        print("create", proj.status_code, proj.text[:240])
        proj.raise_for_status()
        body = proj.json()
        pid = body["id"]
        if not body.get("t_created") and not (body.get("funnel") or {}).get("t_created"):
            print("WARN: t_created missing on create (continuing)")

        gen = await c.post(
            f"/api/video/projects/{pid}/generate",
            headers=h,
            json={
                "content_angle": "intro",
                "audience": "独立开发者",
                "scene_setting": "想装 Agent 又怕踩坑",
                "target_seconds": 30,
            },
        )
        print("generate", gen.status_code, gen.text[:400])
        gen.raise_for_status()
        g = gen.json()
        plan = g.get("production_plan") or {}
        print("plan_after_generate", plan.get("progress_label"), _step_status(plan, "script"))
        if _step_status(plan, "script") != "active":
            print("FAIL: expected script step active (awaiting confirm)", plan)
            return 1
        if g.get("storyboard_confirmed"):
            print("FAIL: storyboard should not be confirmed yet")
            return 1
        funnel = g.get("funnel") or {}
        if not funnel.get("t_script_ready"):
            print("WARN: t_script_ready missing", funnel)

        conf = await c.post(
            f"/api/video/projects/{pid}/confirm-storyboard",
            headers=h,
            json={},
        )
        print("confirm", conf.status_code, conf.text[:240])
        conf.raise_for_status()
        plan = conf.json().get("production_plan") or {}
        if _step_status(plan, "script") != "done":
            print("FAIL: expected script done after confirm", plan)
            return 1

        rend = await c.post(
            f"/api/video/projects/{pid}/render",
            headers=h,
            json={"delivery_level": "l0"},
        )
        print("render", rend.status_code, rend.text[:200])
        rend.raise_for_status()

        for i in range(120):
            st = await c.get(f"/api/video/projects/{pid}/status", headers=h)
            data = st.json()
            job = data.get("job") or {}
            plan = data.get("production_plan") or {}
            print(
                "status",
                i,
                job.get("status"),
                job.get("progress"),
                plan.get("progress_label"),
                _step_status(plan, "l0"),
                (job.get("message") or "")[:40],
            )
            if job.get("status") == "done":
                if _step_status(plan, "l0") != "done":
                    print("FAIL: L0 job done but plan l0 not done", plan)
                    return 1
                funnel = data.get("funnel") or {}
                if not funnel.get("t_l0_ready"):
                    print("WARN: t_l0_ready missing", funnel)
                print("OK artifact plan golden path", pid)
                return 0
            if job.get("status") == "failed":
                print("FAIL render", job.get("fail_reason") or job)
                return 1
            await asyncio.sleep(2)

        print("FAIL timeout waiting L0")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
