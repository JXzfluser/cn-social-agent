#!/usr/bin/env python3
"""Smoke: fetch_url_text tool + skill is loaded."""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

from cn_social_agent.skills.loader import SkillLoader
from cn_social_agent.tools import ToolRegistry, register_builtin_tools
from cn_social_agent.tools.builtin import tool_fetch_url_text

BASE = os.getenv("WORKBENCH_URL", "http://127.0.0.1:18081").rstrip("/")
SAMPLE_URL = os.getenv(
    "SMOKE_FETCH_URL",
    "https://example.com/",
)


async def main() -> int:
    # Unit: tool
    data = await tool_fetch_url_text(SAMPLE_URL, max_chars=2000)
    print("fetch_ok", data.get("ok"), "title", (data.get("title") or "")[:60])
    print("chars", data.get("chars"), "snippet", (data.get("text") or "")[:120].replace("\n", " "))
    if not data.get("ok"):
        print("fetch failed", data)
        return 1
    if "example.com" in SAMPLE_URL and "Example Domain" not in (data.get("title") or ""):
        print("warn: expected title 'Example Domain', got", data.get("title"))

    # Unit: registry + skill scan
    reg = ToolRegistry()
    register_builtin_tools(reg)
    names = {t["name"] for t in reg.list_tools()}
    assert "fetch_url_text" in names, names
    root = os.path.join(os.path.dirname(__file__), "..", "skills")
    skills = SkillLoader(root).scan()
    ids = {s.id for s in skills}
    print("skills", sorted(ids))
    assert "short-video-researcher" in ids
    researcher = next(s for s in skills if s.id == "short-video-researcher")
    assert researcher.enabled, "short-video-researcher should default enabled"
    assert "propose_short_video" in researcher.body
    assert "fetch_url_text" in researcher.body

    # Optional live workbench: tools list + skill visible
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=15, trust_env=False) as c:
            h = await c.get("/health")
            print("health", h.status_code, h.json().get("tools"), h.json().get("skills"))
            # Login demo user and confirm tools/skills APIs expose fetch + researcher
            login = await c.post(
                "/api/auth/login",
                json={"email": "demo@local.test", "password": "demo123456"},
            )
            if login.status_code < 400:
                token = login.json().get("accessToken") or login.json().get("access_token")
                headers = {"Authorization": f"Bearer {token}"}
                tools = (await c.get("/api/tools", headers=headers)).json()
                tnames = {t["name"] for t in (tools.get("tools") or [])}
                assert "fetch_url_text" in tnames, tnames
                sk = (await c.get("/api/skills", headers=headers)).json()
                sids = {s["id"] for s in (sk.get("skills") or [])}
                assert "short-video-researcher" in sids, sids
                print("api_ok tools+skills")
            else:
                print("login_skip", login.status_code)
    except Exception as exc:  # noqa: BLE001
        print("health_skip", exc)

    print("ok")
    return 0


if __name__ == "__main__":
    # Ensure src on path when run as script
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    sys.exit(asyncio.run(main()))
