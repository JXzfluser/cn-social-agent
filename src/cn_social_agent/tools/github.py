"""GitHub research tools — rising stars / repo insight for short-video topics."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx


def _gh_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cn-social-agent-workbench",
    }
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_repo(repo: str) -> tuple[str, str]:
    text = (repo or "").strip()
    text = text.replace("https://github.com/", "").replace("http://github.com/", "")
    text = text.strip("/")
    if text.endswith(".git"):
        text = text[:-4]
    parts = text.split("/")
    if len(parts) < 2:
        raise ValueError("repo must be owner/name or github.com/owner/name")
    return parts[0], parts[1]


async def tool_github_rising_repos(
    days: int = 60,
    min_stars: int = 500,
    language: str = "",
    per_page: int = 8,
) -> dict[str, Any]:
    """Search recently created repos with high star counts (proxy for hot growth)."""
    days = max(7, min(365, int(days or 60)))
    min_stars = max(50, min(100000, int(min_stars or 500)))
    per_page = max(1, min(15, int(per_page or 8)))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    q = f"stars:>={min_stars} created:>={since}"
    if (language or "").strip():
        q += f" language:{language.strip()}"
    url = (
        "https://api.github.com/search/repositories"
        f"?q={quote(q)}&sort=stars&order=desc&per_page={per_page}"
    )
    async with httpx.AsyncClient(timeout=25.0, trust_env=False) as client:
        resp = await client.get(url, headers=_gh_headers())
        if resp.status_code >= 400:
            return {
                "ok": False,
                "error": f"GitHub API {resp.status_code}",
                "body": resp.text[:400],
            }
        data = resp.json()
    items = []
    for it in data.get("items") or []:
        created = it.get("created_at") or ""
        stars = int(it.get("stargazers_count") or 0)
        items.append(
            {
                "full_name": it.get("full_name"),
                "url": it.get("html_url"),
                "description": (it.get("description") or "")[:200],
                "stars": stars,
                "forks": it.get("forks_count"),
                "language": it.get("language"),
                "created_at": created,
                "topics": (it.get("topics") or [])[:8],
                "angle_seeds": [
                    f"入门：{it.get('full_name')} 是什么、怎么跑起来",
                    f"核心思想：为什么 {it.get('full_name')} Star 涨这么快",
                    f"对比：{it.get('full_name')} 和常见替代方案差在哪",
                ],
            }
        )
    return {
        "ok": True,
        "query": q,
        "count": len(items),
        "repos": items,
        "hint": "挑一个 repo 后调用 github_repo_insight，再按 intro/idea/compare 做短视频。",
    }


async def tool_github_repo_insight(repo: str, include_readme: bool = True) -> dict[str, Any]:
    """Fetch repo metadata (+ optional README excerpt) for short-video briefing."""
    owner, name = _parse_repo(repo)
    base = f"https://api.github.com/repos/{owner}/{name}"
    async with httpx.AsyncClient(timeout=25.0, trust_env=False) as client:
        r = await client.get(base, headers=_gh_headers())
        if r.status_code >= 400:
            return {"ok": False, "error": f"repo {r.status_code}", "body": r.text[:300]}
        meta = r.json()
        readme = ""
        if include_readme:
            rr = await client.get(
                f"{base}/readme",
                headers={**_gh_headers(), "Accept": "application/vnd.github.raw"},
            )
            if rr.status_code < 400:
                readme = rr.text[:5000]
    stars = int(meta.get("stargazers_count") or 0)
    created = meta.get("created_at") or ""
    # rough growth signal: stars / days since create
    growth = None
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        days = max(1, (datetime.now(timezone.utc) - created_dt).days)
        growth = round(stars / days, 1)
    except Exception:  # noqa: BLE001
        days = None
    # strip markdown noise lightly
    readme_plain = re.sub(r"```[\s\S]*?```", " ", readme)
    readme_plain = re.sub(r"[#>*`\[\]()]", " ", readme_plain)
    readme_plain = re.sub(r"\s+", " ", readme_plain).strip()[:1800]
    return {
        "ok": True,
        "full_name": meta.get("full_name"),
        "url": meta.get("html_url"),
        "description": meta.get("description") or "",
        "stars": stars,
        "forks": meta.get("forks_count"),
        "watchers": meta.get("subscribers_count") or meta.get("watchers_count"),
        "language": meta.get("language"),
        "license": (meta.get("license") or {}).get("spdx_id"),
        "topics": meta.get("topics") or [],
        "created_at": created,
        "pushed_at": meta.get("pushed_at"),
        "days_since_create": days,
        "stars_per_day": growth,
        "homepage": meta.get("homepage") or "",
        "readme_excerpt": readme_plain,
        "content_angles": {
            "intro": {
                "label": "入门上手",
                "suggested_seconds": 120,
                "outline": ["它是什么", "适合谁", "三步跑通", "验证", "常见坑", "CTA"],
            },
            "idea": {
                "label": "核心思想",
                "suggested_seconds": 90,
                "outline": ["为什么爆火", "核心一句话", "解决什么痛", "误区", "记住一点", "CTA"],
            },
            "compare": {
                "label": "横向对比",
                "suggested_seconds": 120,
                "outline": ["和谁比", "差异表", "什么人该选它", "什么人别选", "选型结论", "CTA"],
            },
            "deep_analysis": {
                "label": "深度分析",
                "suggested_seconds": 180,
                "outline": [
                    "悬念标题",
                    "现象/痛点",
                    "核心论点 thesis",
                    "证据1",
                    "证据2",
                    "规律 pattern",
                    "结论+行动点 verdict",
                    "避坑",
                    "CTA",
                ],
            },
        },
    }


async def tool_scan_hotspot_board(
    days: int = 60,
    min_stars: int = 500,
    language: str = "",
    per_page: int = 10,
    source: str = "all",
) -> dict[str, Any]:
    """Backward-compatible wrapper — multi-source board lives in tools.hotspots."""
    from cn_social_agent.tools.hotspots import tool_scan_hotspot_board as _scan

    return await _scan(
        days=days,
        min_stars=min_stars,
        language=language,
        per_page=per_page,
        source=source,
    )

