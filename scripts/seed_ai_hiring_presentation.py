#!/usr/bin/env python3
"""Create AI招聘能力图谱 presentation via API (meta track; DB column stays 口播)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = os.getenv("WB_BASE", "http://127.0.0.1:18081").rstrip("/")
EMAIL = os.getenv("WB_EMAIL", "demo@local.test")
PASSWORD = os.getenv("WB_PASSWORD", "demo123456")


def req(method: str, path: str, token: str = "", body: dict | None = None, timeout: int = 300) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail[:500]}") from e


def main() -> int:
    login = req("POST", "/api/auth/login", body={"email": EMAIL, "password": PASSWORD})
    token = login.get("accessToken") or login.get("access_token") or ""
    if not token:
        raise SystemExit(f"login failed: {login}")
    p = req(
        "POST",
        "/api/video/projects",
        token,
        {
            "topic": "AI 招聘能力图谱",
            "title": "AI 招聘能力图谱",
            "video_type": "presentation",
            "aspect": "9:16",
            "theme": "talent-map",
        },
    )
    pid = p["id"]
    print("project", pid)
    script = (
        "今天不讲空泛的会用 AI，讲招聘真正要看的：AI 岗位能力图谱。"
        "市场更看重可验证的交付物。三条轴：编排、检索、交付。招人三问：机制、易错、检验。"
    )
    outline = "1 开场\n2 三条能力轴\n3 智能体编排\n4 检索增强\n5 模型原生交付\n6 面试检验\n7 CTA"
    req(
        "POST",
        f"/api/video/projects/{pid}/checkpoints/a1",
        token,
        {"full_script": script, "outline": outline, "aspect": "9:16", "theme": "talent-map"},
    )
    print("A1 ok")
    req("POST", f"/api/video/projects/{pid}/presentation/scaffold", token, {})
    print("scaffold ok")
    out = req(
        "POST",
        f"/api/video/projects/{pid}/presentation/apply-pack",
        token,
        {"pack_id": "ai-hiring-map"},
    )
    print("apply-pack ok=", out.get("ok"))
    if not out.get("ok"):
        print(out.get("log", "")[-1500:])
        return 1
    req(
        "POST",
        f"/api/video/projects/{pid}/checkpoints/b",
        token,
        {"synthesize_audio": False},
    )
    print("B ok")
    print("preview:", f"{BASE}/api/video/projects/{pid}/presentation/?auto=1")
    print("workshop:", f"{BASE}/?mode=video")
    print("PROJECT_ID=", pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
