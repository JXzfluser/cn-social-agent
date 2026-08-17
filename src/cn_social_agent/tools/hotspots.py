"""Multi-source hotspot board for Agent research (GitHub / HN / V2EX / Dev.to / 少数派)."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from cn_social_agent.tools.github import tool_github_rising_repos
from cn_social_agent.tools.hotspot_engine import (
    DOMAIN_OPTIONS,
    attach_local_assets,
    enrich_board,
    filter_by_domain,
)

SOURCES = (
    {"id": "github", "label": "GitHub"},
    {"id": "hn", "label": "Hacker News"},
    {"id": "lobsters", "label": "Lobsters"},
    {"id": "v2ex", "label": "V2EX"},
    {"id": "devto", "label": "Dev.to"},
    {"id": "sspai", "label": "少数派"},
)

DEFAULT_CN_RSS = "https://sspai.com/feed"


def parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        desc = (node.findtext("description") or "").strip()
        if title:
            items.append({"title": title, "url": link, "description": desc[:160]})
    return items


def list_hotspot_sources() -> list[dict[str, str]]:
    return [{"id": s["id"], "label": s["label"]} for s in SOURCES]


def _starters_for_topic(
    *,
    title: str,
    url: str,
    source: str,
    insight_hint: str,
) -> tuple[str, list[dict[str, Any]]]:
    label = title.strip() or url
    link = (url or "").strip()
    link_bit = f" 链接：{link}" if link else ""
    if source == "github":
        insight_msg = (
            f"帮我研究 {label}：先 github_repo_insight，再给 3 句洞察——"
            f"是什么、谁该关注、值不值得做成内容。先别做片，等我决定。"
        )
    else:
        insight_msg = (
            f"帮我研究这个{insight_hint}「{label}」{link_bit}："
            f"先用 fetch_url_text 抓要点，再给 3 句洞察——"
            f"是什么、谁该关注、值不值得做成内容。先别做片，等我决定。"
        )
    starters = [
        {
            "angle": "insight",
            "label": "洞察研究",
            "seconds": 0,
            "message": insight_msg,
        },
        {
            "angle": "intro",
            "label": "做成短视频 · 入门",
            "seconds": 120,
            "message": (
                f"做成短视频（入门讲解·约2分钟）：讲清「{label}」是什么、谁该关注、"
                f"一个可跟做的动作。先研究再 propose_short_video；制作去短视频工坊。"
            ),
        },
        {
            "angle": "cards",
            "label": "生成知识卡片",
            "seconds": 0,
            "message": (
                f"围绕「{label}」生成知识卡片：先提炼 3 个知识点，"
                f"再 propose_knowledge_cards；扫描到知识卡片工坊完成。"
            ),
        },
    ]
    return insight_msg, starters


def _board_item(
    *,
    rank: int,
    source: str,
    source_label: str,
    title: str,
    url: str,
    meta: str,
    description: str,
    score: int | None = None,
) -> dict[str, Any]:
    insight_msg, starters = _starters_for_topic(
        title=title,
        url=url,
        source=source,
        insight_hint=source_label,
    )
    score_bit = f" · {score}" if score is not None else ""
    return {
        "rank": rank,
        "source": source,
        "source_label": source_label,
        "full_name": title,
        "url": url,
        "stars": score or 0,
        "language": source_label,
        "description": (description or "")[:160],
        "topics": [],
        "headline": f"#{rank} [{source_label}] {title}{score_bit}",
        "starters": starters,
        "default_message": insight_msg,
    }


async def _scan_github(
    *, days: int, min_stars: int, language: str, per_page: int
) -> dict[str, Any]:
    raw = await tool_github_rising_repos(
        days=days,
        min_stars=min_stars,
        language=language,
        per_page=per_page,
    )
    if not raw.get("ok"):
        return {
            "ok": False,
            "source": "github",
            "error": raw.get("error") or "GitHub 扫描失败",
            "board": [],
        }
    board = []
    for i, repo in enumerate(raw.get("repos") or [], start=1):
        name = repo.get("full_name") or ""
        desc = (repo.get("description") or "暂无描述").strip()
        lang = repo.get("language") or "多语言"
        stars = int(repo.get("stars") or 0)
        item = _board_item(
            rank=i,
            source="github",
            source_label="GitHub",
            title=name,
            url=repo.get("url") or "",
            meta=lang,
            description=desc,
            score=stars,
        )
        # Prefer github_repo_insight starters already built for github source
        board.append(item)
    return {
        "ok": True,
        "source": "github",
        "title": "GitHub 近创高星",
        "query": raw.get("query"),
        "board": board,
    }


async def _scan_hn(*, per_page: int) -> dict[str, Any]:
    url = "https://hn.algolia.com/api/v1/search?tags=front_page"
    try:
        async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "source": "hn",
                    "error": f"HN API {resp.status_code}",
                    "board": [],
                }
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": "hn", "error": str(exc)[:200], "board": []}

    board = []
    for i, hit in enumerate((data.get("hits") or [])[:per_page], start=1):
        title = (hit.get("title") or hit.get("story_title") or "").strip()
        link = (hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}").strip()
        points = int(hit.get("points") or 0)
        if not title:
            continue
        board.append(
            _board_item(
                rank=i,
                source="hn",
                source_label="HN",
                title=title,
                url=link,
                meta="Hacker News",
                description=f"{points} points · {hit.get('author') or ''}",
                score=points,
            )
        )
    return {
        "ok": True,
        "source": "hn",
        "title": "Hacker News 首页",
        "board": board,
    }


async def _scan_v2ex(*, per_page: int) -> dict[str, Any]:
    url = "https://www.v2ex.com/api/topics/hot.json"
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            trust_env=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; cn-social-agent/1.0)"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "source": "v2ex",
                    "error": f"V2EX API {resp.status_code}",
                    "board": [],
                }
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": "v2ex", "error": str(exc)[:200], "board": []}

    if not isinstance(data, list):
        return {"ok": False, "source": "v2ex", "error": "unexpected payload", "board": []}

    board = []
    for i, row in enumerate(data[:per_page], start=1):
        title = (row.get("title") or "").strip()
        link = (row.get("url") or "").strip()
        node = ((row.get("node") or {}) if isinstance(row.get("node"), dict) else {}).get("title") or ""
        replies = int(row.get("replies") or 0)
        if not title:
            continue
        board.append(
            _board_item(
                rank=i,
                source="v2ex",
                source_label="V2EX",
                title=title,
                url=link,
                meta=node,
                description=f"{node} · {replies} 回复",
                score=replies,
            )
        )
    return {
        "ok": True,
        "source": "v2ex",
        "title": "V2EX 热议",
        "board": board,
    }


async def _scan_lobsters(*, per_page: int) -> dict[str, Any]:
    url = "https://lobste.rs/hottest.json"
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            trust_env=False,
            headers={"User-Agent": "cn-social-agent-workbench"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "source": "lobsters",
                    "error": f"Lobsters API {resp.status_code}",
                    "board": [],
                }
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": "lobsters", "error": str(exc)[:200], "board": []}

    if not isinstance(data, list):
        return {"ok": False, "source": "lobsters", "error": "unexpected payload", "board": []}

    board = []
    for i, row in enumerate(data[:per_page], start=1):
        title = (row.get("title") or "").strip()
        link = (row.get("url") or row.get("comments_url") or "").strip()
        score = int(row.get("score") or 0)
        tags = row.get("tags") or []
        if not title:
            continue
        board.append(
            _board_item(
                rank=i,
                source="lobsters",
                source_label="Lobsters",
                title=title,
                url=link,
                meta=", ".join(tags[:4]) if isinstance(tags, list) else "",
                description=(row.get("description") or "")[:160] or f"score {score}",
                score=score,
            )
        )
    return {
        "ok": True,
        "source": "lobsters",
        "title": "Lobsters 热门",
        "board": board,
    }


async def _scan_devto(*, per_page: int) -> dict[str, Any]:
    url = f"https://dev.to/api/articles?top=7&per_page={per_page}"
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            trust_env=False,
            headers={"User-Agent": "cn-social-agent-workbench"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "source": "devto",
                    "error": f"Dev.to API {resp.status_code}",
                    "board": [],
                }
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": "devto", "error": str(exc)[:200], "board": []}

    if not isinstance(data, list):
        return {"ok": False, "source": "devto", "error": "unexpected payload", "board": []}

    board = []
    for i, row in enumerate(data[:per_page], start=1):
        title = (row.get("title") or "").strip()
        link = (row.get("url") or "").strip()
        tags = row.get("tag_list") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        reactions = int(row.get("positive_reactions_count") or 0)
        if not title:
            continue
        board.append(
            _board_item(
                rank=i,
                source="devto",
                source_label="Dev.to",
                title=title,
                url=link,
                meta=", ".join(tags[:4]),
                description=(row.get("description") or "")[:160] or f"❤ {reactions}",
                score=reactions,
            )
        )
    return {
        "ok": True,
        "source": "devto",
        "title": "Dev.to 本周热门",
        "board": board,
    }


async def _scan_sspai(*, per_page: int) -> dict[str, Any]:
    url = (os.getenv("HOTSPOT_CN_RSS_URL") or DEFAULT_CN_RSS).strip()
    try:
        async with httpx.AsyncClient(
            timeout=12.0,
            trust_env=True,
            headers={"User-Agent": "cn-social-agent"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "source": "sspai",
                    "error": f"RSS {resp.status_code}",
                    "board": [],
                }
            rows = parse_rss_items(resp.text)[:per_page]
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": "sspai", "error": str(exc)[:200], "board": []}

    board = [
        _board_item(
            rank=i,
            source="sspai",
            source_label="少数派",
            title=r["title"],
            url=r["url"],
            meta="少数派",
            description=r.get("description") or "",
            score=max(1, 100 - i),
        )
        for i, r in enumerate(rows, start=1)
    ]
    return {
        "ok": True,
        "source": "sspai",
        "title": "少数派 RSS",
        "board": board,
    }


async def tool_scan_hotspot_board(
    days: int = 60,
    min_stars: int = 500,
    language: str = "",
    per_page: int = 8,
    source: str = "all",
    domain: str = "all",
    allowed_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Scan multi-source hotspots with research-first chat starters.

    ``allowed_sources`` restricts which engines run (connector prefs). When
    empty list, returns an empty board with ok=True and a hint.
    """
    per_page = max(1, min(15, int(per_page or 8)))
    src = (source or "all").strip().lower() or "all"
    if src not in ("all", "github", "hn", "v2ex", "devto", "lobsters", "sspai"):
        src = "all"
    domain = (domain or "all").strip().lower() or "all"

    allow: set[str] | None = None
    if allowed_sources is not None:
        allow = {str(s).strip().lower() for s in allowed_sources if str(s).strip()}
        if not allow:
            return {
                "ok": True,
                "title": "热点榜（无启用源）",
                "hint": "热点看板连接器已关闭，或所有源已被关掉。到「连接器」面板开启。",
                "sources": list_hotspot_sources(),
                "source": src,
                "domain": domain,
                "domains": DOMAIN_OPTIONS,
                "board": [],
                "count": 0,
                "scored": True,
                "skipped_sources": [s["id"] for s in SOURCES],
            }

    def want(sid: str) -> bool:
        if allow is not None and sid not in allow:
            return False
        return src in ("all", sid)

    results: list[dict[str, Any]] = []
    if want("github"):
        n = per_page if src == "github" else max(3, per_page // 2)
        results.append(
            await _scan_github(
                days=days, min_stars=min_stars, language=language, per_page=n
            )
        )
    if want("hn"):
        n = per_page if src == "hn" else max(3, per_page // 2)
        results.append(await _scan_hn(per_page=n))
    if want("lobsters"):
        n = per_page if src == "lobsters" else max(3, per_page // 2)
        results.append(await _scan_lobsters(per_page=n))
    if want("v2ex"):
        n = per_page if src == "v2ex" else max(3, per_page // 2)
        results.append(await _scan_v2ex(per_page=n))
    if want("devto"):
        n = per_page if src == "devto" else max(3, per_page // 2)
        results.append(await _scan_devto(per_page=n))
    if want("sspai"):
        n = per_page if src == "sspai" else max(3, per_page // 2)
        results.append(await _scan_sspai(per_page=n))

    board: list[dict[str, Any]] = []
    errors: list[str] = []
    titles: list[str] = []
    for r in results:
        if r.get("ok"):
            titles.append(str(r.get("title") or r.get("source") or ""))
            for item in r.get("board") or []:
                board.append(item)
        else:
            errors.append(f"{r.get('source')}: {r.get('error') or 'failed'}")

    board = enrich_board(board)
    board = filter_by_domain(board, domain)
    board = board[:per_page]

    # Enrich with local topic assets when request/agent tool context has a user.
    try:
        from cn_social_agent.tools.context import get_tool_context

        if str(get_tool_context().get("user_id") or "").strip():
            board = await attach_local_assets(board)
    except Exception:  # noqa: BLE001 — never fail the board for asset lookup
        pass

    if not board and errors:
        return {
            "ok": False,
            "error": "；".join(errors)[:400],
            "sources": list_hotspot_sources(),
            "source": src,
            "domain": domain,
            "domains": DOMAIN_OPTIONS,
            "board": [],
            "count": 0,
            "scored": True,
        }

    title = " · ".join([t for t in titles if t]) or "热点榜"
    if src == "all":
        title = "综合热点（GitHub / HN / Lobsters / V2EX / Dev.to / 少数派）"
    return {
        "ok": True,
        "title": title,
        "source": src,
        "domain": domain,
        "domains": DOMAIN_OPTIONS,
        "sources": list_hotspot_sources(),
        "count": len(board),
        "board": board,
        "scored": True,
        "errors": errors,
        "hint": (
            "多源热点：默认 insight 研究；用户选短视频/知识卡片意图后再交接工坊。"
            + (f" 部分源失败：{'；'.join(errors)}" if errors else "")
        ),
    }
