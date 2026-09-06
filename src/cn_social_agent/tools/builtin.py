"""Built-in tools for the workbench agent."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from .registry import Tool, ToolRegistry
from .github import (
    tool_github_rising_repos,
    tool_github_repo_insight,
)
from .hotspot_handoff import build_handoff_payload
from .hotspots import tool_scan_hotspot_board
from .population import tool_open_population_atlas, tool_population_census_lookup


async def tool_now() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "iso": now.isoformat(),
        "unix": str(int(now.timestamp())),
    }


async def tool_library_list() -> dict[str, Any]:
    from .context import tool_user_id
    from .reference_library import reference_library

    items = reference_library.list(tool_user_id())
    return {"count": len(items), "items": items}


async def tool_library_read(id: str = "", query: str = "") -> dict[str, Any]:
    from .context import tool_user_id
    from .reference_library import reference_library

    user_id = tool_user_id()
    item = reference_library.get(user_id, id) if id else reference_library.search(user_id, query)
    if item is None:
        listing = reference_library.list(user_id)
        return {
            "found": False,
            "hint": "未找到匹配资料。可用 library_list 查看全部文件名后重试。",
            "available": [i["name"] for i in listing],
        }
    return {
        "found": True,
        "id": item["id"],
        "name": item["name"],
        "kind": item["kind"],
        "content": item["content"],
    }


async def tool_http_get(url: str, max_chars: int = 4000) -> dict[str, str]:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url)
        text = resp.text[: max(0, int(max_chars))]
        return {
            "status_code": str(resp.status_code),
            "url": str(resp.url),
            "body": text,
        }


class _TextExtractor(HTMLParser):
    """Lightweight HTML → visible text (stdlib, no BeautifulSoup required)."""

    # Do not skip <head>: we need <title>. Skip noisy tags only.
    _SKIP = {"script", "style", "noscript", "svg", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks: list[str] = []
        self.title = ""
        self._in_title = False
        self._in_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "title":
            self._in_title = True
            return
        if t == "body":
            self._in_body = True
        if t in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth or not self._in_body:
            return
        if t in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "title":
            self._in_title = False
            return
        if t in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
            return

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
            return
        if self._skip_depth or not self._in_body:
            return
        self._chunks.append(text + " ")


def _html_to_text(html: str) -> tuple[str, str]:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        stripped = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
        return "", re.sub(r"\s+", " ", stripped).strip()
    title = parser.title.strip()
    raw = "".join(parser._chunks)
    # Some pages omit <body>; fall back to all non-skip text excluding title-only
    if not raw.strip():
        loose = _TextExtractor()
        loose._in_body = True
        try:
            loose.feed(html)
            loose.close()
        except Exception:  # noqa: BLE001
            loose = None
        if loose:
            title = title or loose.title.strip()
            raw = "".join(loose._chunks)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return title, raw.strip()


def _looks_like_url(url: str) -> bool:
    try:
        p = urlparse(url.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:  # noqa: BLE001
        return False


async def tool_fetch_url_text(url: str, max_chars: int = 8000) -> dict[str, Any]:
    """Fetch a URL and return readable plain text for research / short-video briefing."""
    url = (url or "").strip()
    if not _looks_like_url(url):
        return {
            "ok": False,
            "error": "url must be absolute http(s)",
            "url": url,
            "title": "",
            "text": "",
            "chars": 0,
        }
    max_chars = max(500, min(int(max_chars or 8000), 20000))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; CNWorkbench/1.0; +https://localhost) "
            "AppleWebKit/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    async with httpx.AsyncClient(
        timeout=20.0, follow_redirects=True, trust_env=False, headers=headers
    ) as client:
        resp = await client.get(url)
    final_url = str(resp.url)
    if resp.status_code >= 400:
        return {
            "ok": False,
            "error": f"HTTP {resp.status_code}",
            "url": final_url,
            "title": "",
            "text": "",
            "chars": 0,
            "status_code": str(resp.status_code),
        }
    ctype = (resp.headers.get("content-type") or "").lower()
    body = resp.text or ""
    if "html" in ctype or body.lstrip().startswith("<"):
        title, text = _html_to_text(body)
    else:
        title, text = "", body
    text = text[:max_chars]
    if not title:
        title = urlparse(final_url).path.rsplit("/", 1)[-1] or final_url
    result = {
        "ok": True,
        "url": final_url,
        "title": title[:200],
        "text": text,
        "chars": str(len(text)),
        "status_code": str(resp.status_code),
        "truncated": "true" if len(text) >= max_chars else "false",
    }
    try:
        from cn_social_agent.tools.kb_enrich import enrich_kb_from_url
        note_path = enrich_kb_from_url(final_url, title, text)
        if note_path:
            result["kb_note"] = str(note_path)
    except Exception:  # noqa: BLE001
        pass
    return result


async def tool_query_knowledge_base(question: str, top_k: int = 5) -> dict[str, Any]:
    """Query the agent-learning RAG knowledge base for related notes and web-fetched content."""
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "question required", "results": []}
    try:
        import sys
        al_dir = str(
            __import__("pathlib").Path(__file__).resolve().parents[3] / "agent-learning"
        )
        if al_dir not in sys.path:
            sys.path.insert(0, al_dir)
        from knowledge_base.kb import KnowledgeBase

        kb = KnowledgeBase()
        kb.build()
        results = kb.query(question, top_k=max(1, min(top_k, 10)))
        return {
            "ok": True,
            "question": question,
            "results": [
                {
                    "score": round(float(s), 4),
                    "source": c.source,
                    "topic": c.topic,
                    "text": c.text[:600],
                }
                for c, s in results
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300], "results": []}


async def tool_handoff_hotspot(
    title: str,
    url: str = "",
    source: str = "",
    why: str = "",
    topic_key: str = "",
    track: str = "koubo",
    research_notes: str = "",
) -> dict[str, Any]:
    """Hand a hotspot item to a workshop track with research notes attached."""
    return await build_handoff_payload(
        title=title,
        url=url,
        source=source,
        why=why,
        topic_key=topic_key,
        track=track,
        research_notes=research_notes,
    )


from cn_social_agent.video.pipeline import list_video_styles


async def tool_list_video_styles() -> dict[str, Any]:
    """Return allowed durations, background themes, and motion styles for short videos."""
    data = list_video_styles()
    data["ok"] = True
    return data


async def tool_propose_short_video(
    topic: str,
    selling_points: str = "",
    ready: bool = True,
    audience: str = "",
    scene_setting: str = "",
    platform: str = "",
    cta: str = "",
) -> dict[str, str | bool | list[str]]:
    """Signal that the chat idea is ready for short-video production (UI suggestion card)."""
    topic_s = (topic or "").strip()
    audience_s = (audience or "").strip()
    scene_s = (scene_setting or "").strip()
    ready_flag = bool(ready)
    need: list[str] = []
    if not audience_s and not scene_s:
        ready_flag = False
        need.append("audience|scene")
    from cn_social_agent.knowledge.assets import lookup_local_assets

    local = await lookup_local_assets(topic_s, limit=3)
    hits = local.get("hits") or []
    hint = (
        "还缺受众或使用场景，先补一项再提议做片。"
        if need
        else "先出 L0 分镜草稿确认结构，再升级 L1 成片；优先把 hook/cta 镜升级成片。"
    )
    if hits:
        hint = f"{hint}；{local.get('hint')}"
    return {
        "ok": True,
        "ready": ready_flag,
        "need": need,
        "topic": topic_s,
        "selling_points": (selling_points or "").strip(),
        "audience": audience_s,
        "scene_setting": scene_s,
        "platform": (platform or "").strip(),
        "cta": (cta or "").strip(),
        "video_track": "koubo",
        "workshop_mode": "koubo",
        "hint": hint,
        "local_assets": hits,
        "present_topic_assets": bool(hits),
        "l1_priority_roles": ["hook", "cta"],
        "delivery": {
            "l0": "分镜草稿（本地卡片）",
            "l1": "成片（Agnes 真画面）",
        },
    }


async def tool_clarify_brief(
    question: str,
    need: str | list[str] = "audience|scene",
    topic: str = "",
    audience: str = "",
    scene_setting: str = "",
    platform: str = "",
    video_track: str = "",
    aspect: str = "",
    theme: str = "",
) -> dict[str, str | bool | list[str]]:
    """Ask the user for missing brief fields before proposing production."""
    from cn_social_agent.api.prefs import normalize_video_track

    if isinstance(need, list):
        need_list = [str(x).strip() for x in need if str(x).strip()]
    else:
        need_list = [x.strip() for x in str(need or "audience|scene").split("|") if x.strip()]
    if not need_list:
        need_list = ["audience|scene"]
    track = normalize_video_track(video_track)
    return {
        "ok": True,
        "clarify": True,
        "ready": False,
        "question": (question or "还缺一项关键信息：先选口播还是讲解演示？目标受众或使用场景？").strip(),
        "need": need_list,
        "topic": (topic or "").strip(),
        "audience": (audience or "").strip(),
        "scene_setting": (scene_setting or "").strip(),
        "platform": (platform or "").strip(),
        "video_track": track,
        "aspect": (aspect or "").strip() or "9:16",
        "theme": (theme or "").strip() or "talent-map",
        "hint": "先选口播或讲解，再补受众/场景；填好后即可提议做片",
    }



async def tool_propose_presentation(
    topic: str,
    aspect: str = "9:16",
    theme: str = "talent-map",
    outline: str = "",
    full_script: str = "",
    thesis: str = "",
    audience: str = "",
    research_notes: str = "",
) -> dict[str, str | bool]:
    """Signal UI to open/create a presentation-track project with polished copy."""
    from cn_social_agent.video.presentation import normalize_aspect

    topic_s = (topic or "").strip()
    if not topic_s:
        return {"ok": False, "error": "topic required", "present": False}
    outline_s = (outline or "").strip()
    script_s = (full_script or "").strip()
    thin = len(re.sub(r"\s+", "", script_s)) < 200 or outline_s.count("\n") < 3
    return {
        "ok": True,
        "present": True,
        "presentation": True,
        "propose_presentation": True,
        "topic": topic_s,
        "aspect": normalize_aspect(aspect),
        "theme": (theme or "talent-map").strip() or "talent-map",
        "outline": outline_s,
        "full_script": script_s,
        "thesis": (thesis or "").strip(),
        "audience": (audience or "").strip(),
        "research_notes": (research_notes or "").strip(),
        "needs_deep_draft": thin,
        "hint": (
            "内容偏薄：请先 draft_presentation_content 再交接"
            if thin
            else "请在短视频工坊打开讲解演示，确认 A1 前可点「Agent 深度起草」打磨"
        ),
        "workshop_mode": "presentation",
        "video_track": "presentation",
    }


async def tool_draft_presentation_content(
    topic: str,
    research_notes: str = "",
    audience: str = "",
    angle: str = "",
    aspect: str = "9:16",
    theme: str = "talent-map",
    project_id: str = "",
) -> dict[str, object]:
    """Hand off a deep-draft request; workshop/API runs LLM with depth bars."""
    topic_s = (topic or "").strip()
    if not topic_s:
        return {"ok": False, "error": "topic required"}
    notes = (research_notes or "").strip()
    return {
        "ok": True,
        "draft_presentation": True,
        "topic": topic_s,
        "research_notes": notes,
        "audience": (audience or "").strip(),
        "angle": (angle or "").strip(),
        "aspect": (aspect or "9:16").strip() or "9:16",
        "theme": (theme or "talent-map").strip() or "talent-map",
        "project_id": (project_id or "").strip(),
        "video_track": "presentation",
        "workshop_mode": "presentation",
        "hint": (
            "已提交深度起草请求：工坊将按实测弧线生成 thesis/大纲/口播/≥18 步图示稿。"
            "若尚无项目，请先 propose_presentation。"
        ),
        "quality_bar": {
            "thesis": True,
            "script_chars": 350,
            "chapters": 6,
            "slides": 18,
            "diagrams": 8,
        },
    }


async def tool_confirm_checkpoint(
    checkpoint: str,
    synthesize_audio: bool = False,
    notes: str = "",
) -> dict[str, str | bool]:
    """Remind agent/UI to persist checkpoint via API (Agent cannot invent confirmation)."""
    name = (checkpoint or "").strip().lower()
    if name not in ("a1", "b"):
        return {"ok": False, "error": "checkpoint must be a1 or b"}
    return {
        "ok": True,
        "checkpoint": name,
        "synthesize_audio": bool(synthesize_audio) if name == "b" else False,
        "notes": (notes or "").strip(),
        "hint": f"请用户在工坊点击确认检查点 {name.upper()}，或调用 POST /checkpoints/{name}",
    }


async def tool_scaffold_presentation(project_id: str = "") -> dict[str, str | bool]:
    pid = (project_id or "").strip()
    return {
        "ok": True,
        "project_id": pid,
        "hint": "调用 POST /api/video/projects/{id}/presentation/scaffold（需 A1 已确认）",
        "requires_checkpoint": "a1",
    }


async def tool_build_chapter(
    project_id: str,
    chapter_id: str,
    note: str = "",
) -> dict[str, str | bool]:
    return {
        "ok": True,
        "project_id": (project_id or "").strip(),
        "chapter_id": (chapter_id or "").strip(),
        "note": (note or "").strip(),
        "hint": "在 data/presentations/{id}/src/chapters/ 写入章节后执行 presentation/build",
    }


async def tool_synthesize_narration_audio(project_id: str = "") -> dict[str, str | bool]:
    return {
        "ok": True,
        "project_id": (project_id or "").strip(),
        "hint": "检查点 B 选择合成音频后，按 narrations.ts 用 edge-tts 生成 public/audio/*.mp3",
        "requires_checkpoint": "b",
    }


async def tool_presentation_preview_url(
    project_id: str,
    aspect: str = "16:9",
) -> dict[str, object]:
    from cn_social_agent.video.presentation import normalize_aspect, obs_checklist

    pid = (project_id or "").strip()
    preview = f"/api/video/projects/{pid}/presentation/" if pid else ""
    return {
        "ok": True,
        "project_id": pid,
        "preview_url": preview,
        "auto_url": (preview + "?auto=1") if preview else "",
        "obs": obs_checklist(aspect=normalize_aspect(aspect), preview_url=preview + "?auto=1" if preview else ""),
    }


async def tool_present_video_artifact(
    project_id: str,
    note: str = "",
    topic: str = "",
    title: str = "",
) -> dict[str, str | bool]:
    """Present an existing video project card in the chat (delivery artifact)."""
    pid = (project_id or "").strip()
    if not pid:
        return {"ok": False, "error": "project_id required", "present": False}
    return {
        "ok": True,
        "present": True,
        "project_id": pid,
        "topic": (topic or "").strip(),
        "title": (title or topic or "").strip(),
        "note": (note or "分镜已就绪，可在卡片上生成草稿或升级成片").strip(),
    }


def _parse_roles_arg(
    roles: str | list | None,
    *,
    topic: str = "",
    category: str = "",
) -> list[str]:
    """Parse roles/topics for card handoff.

    Prefer explicit roles → topic → category defaults. Never force hiring
    job titles when the subject is clearly a product/topic string.
    """
    import re

    if isinstance(roles, list):
        out = [str(s).strip() for s in roles if str(s).strip()]
        if out:
            return out
    else:
        text = str(roles or "").strip()
        if text:
            return [s.strip() for s in re.split(r"[、,，]", text) if s.strip()]
    topic_s = str(topic or "").strip()
    if topic_s:
        return [topic_s]
    from cn_social_agent.cards.categories import DEFAULT_TOPICS, get_category

    return list(
        DEFAULT_TOPICS.get(get_category(category)["id"])
        or DEFAULT_TOPICS["hiring_insight"]
    )


async def tool_propose_knowledge_cards(
    roles: str = "",
    note: str = "",
    topic: str = "",
    category: str = "",
    research_notes: str = "",
) -> dict[str, object]:
    """Signal UI to suggest generating knowledge cards (does not scan yet)."""
    from cn_social_agent.cards.categories import CATEGORIES, infer_category
    from cn_social_agent.cards.topic import build_search_terms, extract_short_topic
    from cn_social_agent.knowledge.assets import lookup_local_assets

    topic_s = (topic or "").strip()
    notes_s = (research_notes or "").strip()
    # Distill a searchable subject so long titles don't poison the search.
    if topic_s:
        topic_s = extract_short_topic(topic_s, notes_s) or topic_s
    cat = (category or "").strip()
    # Infer category before filling default roles, so product topics don't
    # get hiring job-title seeds.
    if cat not in CATEGORIES:
        cat = infer_category(topic_s, roles, note) or ""
    if cat not in CATEGORIES:
        cat = ""
    role_list = _parse_roles_arg(roles, topic=topic_s, category=cat)
    if cat not in CATEGORIES:
        cat = infer_category(topic_s, "、".join(role_list), note) or ""
    if cat not in CATEGORIES:
        cat = ""
    query = topic_s or (role_list[0] if role_list else "")
    local = await lookup_local_assets(query, limit=3)
    hits = local.get("hits") or []
    default_note = (
        "已带原文素材，工坊会先生成种子证据（不足可「补搜」），勾选后「成刊」"
        if notes_s
        else "主题清楚后可到知识卡片工坊「深采」，勾选素材后「成刊」"
    )
    note_s = (note or default_note).strip()
    if hits:
        note_s = f"{note_s}；{local.get('hint')}"
    return {
        "ok": True,
        "propose_cards": True,
        "roles": role_list,
        "topic": topic_s,
        "category": cat,
        "note": note_s,
        "research_notes": notes_s,
        "search_terms": build_search_terms(topic_s, notes_s) if topic_s else [],
        "local_assets": hits,
        "hint": local.get("hint") or note_s,
        "present_topic_assets": bool(hits),
    }


async def tool_lookup_topic_assets(topic: str = "", limit: int = 5) -> dict[str, Any]:
    """Search local journals + videos before deep research / new produce."""
    from cn_social_agent.knowledge.assets import lookup_local_assets

    lim = max(1, min(10, int(limit or 5)))
    data = await lookup_local_assets((topic or "").strip(), limit=lim)
    data["ok"] = True
    return data


async def tool_scan_knowledge_cards(
    roles: str = "",
    note: str = "",
    topic: str = "",
    category: str = "",
    research_notes: str = "",
) -> dict[str, object]:
    """Signal UI to open knowledge-card workshop (does NOT run scan automatically)."""
    from cn_social_agent.cards.categories import CATEGORIES, infer_category
    from cn_social_agent.cards.topic import build_search_terms, extract_short_topic

    topic_s = (topic or "").strip()
    notes_s = (research_notes or "").strip()
    if topic_s:
        topic_s = extract_short_topic(topic_s, notes_s) or topic_s
    cat = (category or "").strip()
    if cat not in CATEGORIES:
        cat = infer_category(topic_s, roles, note) or ""
    if cat not in CATEGORIES:
        cat = ""
    role_list = _parse_roles_arg(roles, topic=topic_s, category=cat)
    if cat not in CATEGORIES:
        cat = infer_category(topic_s, "、".join(role_list), note) or ""
    if cat not in CATEGORIES:
        cat = ""
    default_note = (
        "已带原文素材，工坊会先生成种子证据（不足可「补搜」），勾选后「成刊」"
        if notes_s
        else "请到知识卡片工坊「深采」，勾选素材后点「成刊」"
    )
    return {
        "ok": True,
        "scan_cards": True,
        "roles": role_list,
        "topic": topic_s,
        "category": cat,
        "note": (note or default_note).strip(),
        "research_notes": notes_s,
        "search_terms": build_search_terms(topic_s, notes_s) if topic_s else [],
    }


async def tool_present_knowledge_card(
    card_id: str,
    note: str = "",
    title: str = "",
    roles: str = "",
) -> dict[str, object]:
    """Present an existing knowledge-card history item in chat."""
    cid = (card_id or "").strip()
    if not cid:
        return {"ok": False, "error": "card_id required", "present": False}
    role_list = _parse_roles_arg(roles) if roles else []
    return {
        "ok": True,
        "present": True,
        "present_cards": True,
        "card_id": cid,
        "title": (title or "").strip(),
        "roles": role_list,
        "note": (note or "知识卡片已就绪，可在卡片工坊编辑并导出 PNG").strip(),
    }


async def tool_write_todos(
    todos: list | None = None,
    active_project_id: str = "",
    note: str = "",
) -> dict[str, object]:
    """Update the session produce plan (topic→…→l1). UI reads agent_state."""
    clean: list[dict[str, str]] = []
    for item in todos or []:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id") or "").strip()
        if not sid:
            continue
        st = str(item.get("status") or "pending")
        if st not in ("pending", "active", "done", "blocked", "failed"):
            st = "pending"
        clean.append(
            {
                "id": sid,
                "label": str(item.get("label") or sid)[:40],
                "status": st,
                "detail": str(item.get("detail") or "")[:80],
            }
        )
    return {
        "ok": True,
        "todos": clean,
        "active_project_id": (active_project_id or "").strip(),
        "note": (note or "").strip(),
    }


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(
        Tool(
            name="now",
            description="Return the current UTC time.",
            parameters={"properties": {}, "required": []},
            handler=tool_now,
        )
    )
    registry.register(
        Tool(
            name="http_get",
            description=(
                "Raw HTTP GET (may return HTML). Prefer fetch_url_text when you need "
                "readable article/page content for research."
            ),
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "Absolute URL to fetch"},
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters of body to return",
                        "default": 4000,
                    },
                },
                "required": ["url"],
            },
            handler=tool_http_get,
        )
    )
    registry.register(
        Tool(
            name="fetch_url_text",
            description=(
                "Fetch a public http(s) URL and extract readable plain text (title + body). "
                "Use when the user pastes a website/article link and you need to explore "
                "content for short-video research. Do NOT use for login-walled pages."
            ),
            parameters={
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Absolute http(s) URL",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters of extracted text (default 8000)",
                        "default": 8000,
                    },
                },
                "required": ["url"],
            },
            handler=tool_fetch_url_text,
        )
    )
    registry.register(
        Tool(
            name="query_knowledge_base",
            description=(
                "Query the agent-learning RAG knowledge base for related notes and web-fetched content. "
                "Use when the user asks about a topic that might be covered in the learning notes or "
                "previously fetched articles. Returns scored text chunks with source info."
            ),
            parameters={
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Search query in natural language",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["question"],
            },
            handler=tool_query_knowledge_base,
        )
    )
    registry.register(
        Tool(
            name="scan_hotspot_board",
            description=(
                "Scan a multi-source hotspot board (GitHub / HN / Lobsters / V2EX / Dev.to) "
                "for research. Returns scored/ranked items with why + insight-first starters. "
                "Prefer when the user wants 热点榜 / 扫选题 / 研究洞察. "
                "Use source=github|hn|lobsters|v2ex|devto|all and "
                "domain=all|ai|devtools|product|hiring. For GitHub repos then call "
                "github_repo_insight; for articles use fetch_url_text. "
                "Do not propose video/cards until the user asks."
            ),
            parameters={
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "GitHub look-back days (default 60)",
                        "default": 60,
                    },
                    "min_stars": {
                        "type": "integer",
                        "description": "GitHub minimum stars (default 500)",
                        "default": 500,
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional GitHub language filter e.g. TypeScript",
                        "default": "",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Items per source (max 15)",
                        "default": 10,
                    },
                    "source": {
                        "type": "string",
                        "description": "all | github | hn | lobsters | v2ex | devto",
                        "default": "all",
                    },
                    "domain": {
                        "type": "string",
                        "description": "all | ai | devtools | product | hiring",
                        "default": "all",
                    },
                },
                "required": [],
            },
            handler=tool_scan_hotspot_board,
        )
    )
    registry.register(
        Tool(
            name="handoff_hotspot",
            description=(
                "Hand a chosen hotspot item to a production track with research notes. "
                "track=koubo (口播短视频) | presentation (讲解演示) | journal (知识卡片). "
                "Pass research_notes if you already researched the link; otherwise the "
                "server fetches a short excerpt from url. Returns the same payload the "
                "UI 「研究并交接」 button uses (propose_short_video / propose_presentation / "
                "propose_cards)."
            ),
            parameters={
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Hotspot title / topic seed",
                    },
                    "url": {
                        "type": "string",
                        "description": "Original article or repo URL",
                        "default": "",
                    },
                    "source": {
                        "type": "string",
                        "description": "Source id e.g. github | hn | v2ex | sspai",
                        "default": "",
                    },
                    "why": {
                        "type": "string",
                        "description": "Why this topic is worth producing",
                        "default": "",
                    },
                    "topic_key": {
                        "type": "string",
                        "description": "Normalized topic key from the board item",
                        "default": "",
                    },
                    "track": {
                        "type": "string",
                        "description": "koubo | presentation | journal",
                        "default": "koubo",
                    },
                    "research_notes": {
                        "type": "string",
                        "description": "Existing research notes; skips server-side fetch",
                        "default": "",
                    },
                },
                "required": ["title"],
            },
            handler=tool_handoff_hotspot,
        )
    )
    registry.register(
        Tool(
            name="github_rising_repos",
            description=(
                "Find recently created GitHub repos with high star counts "
                "(proxy for fast star growth / hot open-source topics). "
                "Prefer scan_hotspot_board when the user wants a ranked 热点榜 for research. "
                "Then call github_repo_insight on a chosen repo."
            ),
            parameters={
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Look back N days for repo creation (default 60)",
                        "default": 60,
                    },
                    "min_stars": {
                        "type": "integer",
                        "description": "Minimum stars (default 500)",
                        "default": 500,
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional language filter e.g. TypeScript",
                        "default": "",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "How many repos to return (max 15)",
                        "default": 8,
                    },
                },
                "required": [],
            },
            handler=tool_github_rising_repos,
        )
    )
    registry.register(
        Tool(
            name="github_repo_insight",
            description=(
                "Fetch a GitHub repo's stars/forks/topics/README excerpt and "
                "ready-made content angles: intro(入门), idea(核心思想), compare(对比). "
                "Pass owner/name or github.com URL."
            ),
            parameters={
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "owner/name or https://github.com/owner/name",
                    },
                    "include_readme": {
                        "type": "boolean",
                        "description": "Include README excerpt (default true)",
                        "default": True,
                    },
                },
                "required": ["repo"],
            },
            handler=tool_github_repo_insight,
        )
    )
    registry.register(
        Tool(
            name="population_census_lookup",
            description=(
                "查询中国第七次全国人口普查（2020）结构化数据：全国概览、省份详情、"
                "城市常住人口、或按人口/老龄化/城镇化/性别比/密度/增长率排序。 "
                "用户问人口结构、老龄化、城镇化、某省某市人口时优先调用。"
            ),
            parameters={
                "properties": {
                    "province": {
                        "type": "string",
                        "description": "省/自治区/直辖市名，如 广东、浙江、上海",
                        "default": "",
                    },
                    "city": {
                        "type": "string",
                        "description": "地级市名，如 深圳、成都；可与 province 联用",
                        "default": "",
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "排行榜字段：pop|growth|urban|aging|gender|density",
                        "default": "pop",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "排行返回条数（默认 8，最大 31）",
                        "default": 8,
                    },
                    "national": {
                        "type": "boolean",
                        "description": "仅返回全国汇总时设为 true",
                        "default": False,
                    },
                },
                "required": [],
            },
            handler=tool_population_census_lookup,
        )
    )
    registry.register(
        Tool(
            name="open_population_atlas",
            description=(
                "在工作台打开「中国人口结构图鉴」可视化页面（第七次普查）。"
                "可传入 province / city 深链到对应详情。用户要看图、对比省份结构时调用。"
            ),
            parameters={
                "properties": {
                    "province": {"type": "string", "default": ""},
                    "city": {"type": "string", "default": ""},
                    "note": {"type": "string", "default": ""},
                },
                "required": [],
            },
            handler=tool_open_population_atlas,
        )
    )
    registry.register(
        Tool(
            name="list_video_styles",
            description=(
                "List allowed short-video durations, content angles "
                "(intro/idea/compare/general), background themes, and motion styles. "
                "Call before advising duration/angle choices."
            ),
            parameters={"properties": {}, "required": []},
            handler=tool_list_video_styles,
        )
    )
    registry.register(
        Tool(
            name="propose_short_video",
            description=(
                "Call when the user explicitly wants a vertical 口播 short video (L0/L1), NOT 讲解演示. "
                "Does NOT create the video — signals the UI to hand off to the short-video workshop. "
                "Pass a concise topic and optional selling points. "
                "If the user has not chosen 口播 vs 讲解, call clarify_brief with need=track first. "
                "If both audience and scene are empty, call clarify_brief instead."
            ),
            parameters={
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Short video topic / title seed in Chinese",
                    },
                    "selling_points": {
                        "type": "string",
                        "description": "Key hooks or selling points, brief",
                        "default": "",
                    },
                    "audience": {
                        "type": "string",
                        "description": "Target audience",
                        "default": "",
                    },
                    "scene_setting": {
                        "type": "string",
                        "description": "Concrete pain/use scene",
                        "default": "",
                    },
                    "platform": {
                        "type": "string",
                        "description": "抖音/视频号/小红书 etc.",
                        "default": "",
                    },
                    "cta": {
                        "type": "string",
                        "description": "End call-to-action",
                        "default": "",
                    },
                    "ready": {
                        "type": "boolean",
                        "description": "True if production can start now",
                        "default": True,
                    },
                },
                "required": ["topic"],
            },
            handler=tool_propose_short_video,
        )
    )
    registry.register(
        Tool(
            name="clarify_brief",
            description=(
                "Ask the user one clarifying question before proposing. "
                "Use need=track when 口播 vs 讲解演示 is unclear. "
                "Use need=audience|scene for 口播; need=audience for 讲解演示. "
                "Shows a UI strip. Prefer this over propose_* when not ready."
            ),
            parameters={
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "One short question in Chinese",
                    },
                    "need": {
                        "type": "string",
                        "description": "Pipe-separated fields, e.g. track|audience|scene",
                        "default": "audience|scene",
                    },
                    "topic": {"type": "string", "default": ""},
                    "audience": {"type": "string", "default": ""},
                    "scene_setting": {"type": "string", "default": ""},
                    "platform": {"type": "string", "default": ""},
                    "video_track": {
                        "type": "string",
                        "description": "koubo or presentation if already known",
                        "default": "",
                    },
                    "aspect": {"type": "string", "default": "9:16"},
                    "theme": {"type": "string", "default": "talent-map"},
                },
                "required": ["question"],
            },
            handler=tool_clarify_brief,
        )
    )
    registry.register(
        Tool(
            name="present_video_artifact",
            description=(
                "Present an existing short-video project as a delivery card in chat. "
                "Primary CTA should open the short-video workshop for L0/L1; chat is handoff only."
            ),
            parameters={
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Video project UUID",
                    },
                    "note": {"type": "string", "default": ""},
                    "topic": {"type": "string", "default": ""},
                    "title": {"type": "string", "default": ""},
                },
                "required": ["project_id"],
            },
            handler=tool_present_video_artifact,
        )
    )

    registry.register(
        Tool(
            name="propose_presentation",
            description=(
                "Propose a Harness-style 讲解演示 (web stage + OBS), NOT 口播 L0/L1. "
                "After research + draft_presentation_content, pass topic, outline, full_script, thesis. "
                "Prefer aspect 9:16 for Douyin, theme talent-map|paper-press."
            ),
            parameters={
                "properties": {
                    "topic": {"type": "string"},
                    "aspect": {"type": "string", "default": "9:16"},
                    "theme": {"type": "string", "default": "talent-map"},
                    "outline": {"type": "string", "default": ""},
                    "full_script": {"type": "string", "default": ""},
                    "thesis": {"type": "string", "default": ""},
                    "audience": {"type": "string", "default": ""},
                    "research_notes": {"type": "string", "default": ""},
                },
                "required": ["topic"],
            },
            handler=tool_propose_presentation,
        )
    )
    registry.register(
        Tool(
            name="draft_presentation_content",
            description=(
                "Draft deep presentation content in 实测讲解 arc "
                "(hook/differentiate/concept/setup/demo/wrap; thesis, outline, full_script; "
                "≥18 slides; compare diagram; demo outcome + CTA). "
                "Pass research_notes from github_repo_insight/fetch_url_text. "
                "Call BEFORE propose_presentation when content is thin."
            ),
            parameters={
                "properties": {
                    "topic": {"type": "string"},
                    "research_notes": {"type": "string", "default": ""},
                    "audience": {"type": "string", "default": ""},
                    "angle": {"type": "string", "default": ""},
                    "aspect": {"type": "string", "default": "9:16"},
                    "theme": {"type": "string", "default": "talent-map"},
                    "project_id": {"type": "string", "default": ""},
                },
                "required": ["topic"],
            },
            handler=tool_draft_presentation_content,
        )
    )
    registry.register(
        Tool(
            name="confirm_checkpoint",
            description="Record that checkpoint A1 or B must be confirmed in the workshop UI/API.",
            parameters={
                "properties": {
                    "checkpoint": {"type": "string", "description": "a1 or b"},
                    "synthesize_audio": {"type": "boolean", "default": False},
                    "notes": {"type": "string", "default": ""},
                },
                "required": ["checkpoint"],
            },
            handler=tool_confirm_checkpoint,
        )
    )
    registry.register(
        Tool(
            name="scaffold_presentation",
            description="Remind to scaffold Vite presentation after A1 (API call).",
            parameters={
                "properties": {"project_id": {"type": "string", "default": ""}},
                "required": [],
            },
            handler=tool_scaffold_presentation,
        )
    )
    registry.register(
        Tool(
            name="build_chapter",
            description="Note a chapter to write under the presentation scaffold.",
            parameters={
                "properties": {
                    "project_id": {"type": "string"},
                    "chapter_id": {"type": "string"},
                    "note": {"type": "string", "default": ""},
                },
                "required": ["project_id", "chapter_id"],
            },
            handler=tool_build_chapter,
        )
    )
    registry.register(
        Tool(
            name="synthesize_narration_audio",
            description="After checkpoint B with synthesize_audio, generate narration MP3s.",
            parameters={
                "properties": {"project_id": {"type": "string", "default": ""}},
                "required": [],
            },
            handler=tool_synthesize_narration_audio,
        )
    )
    registry.register(
        Tool(
            name="presentation_preview_url",
            description="Return presentation preview URL and OBS checklist.",
            parameters={
                "properties": {
                    "project_id": {"type": "string"},
                    "aspect": {"type": "string", "default": "16:9"},
                },
                "required": ["project_id"],
            },
            handler=tool_presentation_preview_url,
        )
    )
    registry.register(
        Tool(
            name="lookup_topic_assets",
            description=(
                "Search local topic assets (past journals, evidence packs, koubo/presentation "
                "projects) BEFORE deep research or proposing a new video/card. "
                "Call with topic when the user continues a previous subject or asks to reuse work. "
                "If hits exist, present them and ask whether to reuse before scrape/generate."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to match against local assets",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max hits (1-10, default 5)",
                    },
                },
                "required": [],
            },
            handler=tool_lookup_topic_assets,
        )
    )
    registry.register(
        Tool(
            name="propose_knowledge_cards",
            description=(
                "Call when the user explicitly wants knowledge cards (封面+知识点 PNG). "
                "Does NOT scan yet — shows a UI suggestion to open the knowledge-card workshop. "
                "Pass roles as Chinese job titles separated by 、 or comma. "
                "Do not call during pure hotspot research."
            ),
            parameters={
                "properties": {
                    "roles": {
                        "type": "string",
                        "description": "Job roles, e.g. AI Agent 开发工程师、AI 全栈工程师",
                        "default": "",
                    },
                    "topic": {
                        "type": "string",
                        "description": (
                            "Subject to research, e.g. DeepSeek MLA MoE 架构. "
                            "Drives the deep-research search queries."
                        ),
                        "default": "",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Card series id: hiring_insight | product_explain | "
                            "skill_roadmap | industry_brief. Sets workshop category."
                        ),
                        "default": "",
                    },
                    "note": {"type": "string", "default": ""},
                    "research_notes": {
                        "type": "string",
                        "description": (
                            "Fetched article/source text you already researched. "
                            "Passed as seed evidence so the workshop starts on-topic "
                            "instead of blind-searching the title."
                        ),
                        "default": "",
                    },
                },
                "required": [],
            },
            handler=tool_propose_knowledge_cards,
        )
    )
    registry.register(
        Tool(
            name="scan_knowledge_cards",
            description=(
                "Signal the UI to hand off to the knowledge-card workshop. "
                "Does NOT run research automatically — user clicks「深采」then「成刊」in the workshop. "
                "Prefer propose_knowledge_cards; use this only when user explicitly asks to scan. "
                "ALWAYS pass topic when the cards are about a specific subject — "
                "the workshop searches topic + roles, so omitting it returns unrelated material. "
                "Pass category when the series is clear (product / skill / industry / hiring)."
            ),
            parameters={
                "properties": {
                    "roles": {
                        "type": "string",
                        "description": "Job roles separated by 、 or comma",
                        "default": "",
                    },
                    "topic": {
                        "type": "string",
                        "description": (
                            "Subject to research, e.g. DeepSeek MLA MoE 架构. "
                            "Drives the deep-research search queries."
                        ),
                        "default": "",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Card series id: hiring_insight | product_explain | "
                            "skill_roadmap | industry_brief"
                        ),
                        "default": "",
                    },
                    "note": {"type": "string", "default": ""},
                    "research_notes": {
                        "type": "string",
                        "description": (
                            "Fetched article/source text you already researched. "
                            "Passed as seed evidence so the workshop starts on-topic."
                        ),
                        "default": "",
                    },
                },
                "required": [],
            },
            handler=tool_scan_knowledge_cards,
        )
    )
    registry.register(
        Tool(
            name="present_knowledge_card",
            description=(
                "Present an existing knowledge-card history item in chat. "
                "Pass card_id from a prior scan result."
            ),
            parameters={
                "properties": {
                    "card_id": {
                        "type": "string",
                        "description": "History record id from /api/cards/scan",
                    },
                    "note": {"type": "string", "default": ""},
                    "title": {"type": "string", "default": ""},
                    "roles": {"type": "string", "default": ""},
                },
                "required": ["card_id"],
            },
            handler=tool_present_knowledge_card,
        )
    )
    registry.register(
        Tool(
            name="write_todos",
            description=(
                "Update the visible produce plan steps "
                "(topic/angle/brief/script/l0/l1). "
                "Call when starting a multi-step short-video task or when step status changes."
            ),
            parameters={
                "properties": {
                    "todos": {
                        "type": "array",
                        "description": "List of {id, label, status, detail}",
                        "items": {"type": "object"},
                    },
                    "active_project_id": {
                        "type": "string",
                        "description": "Optional video project UUID to bind",
                        "default": "",
                    },
                    "note": {"type": "string", "default": ""},
                },
                "required": [],
            },
            handler=tool_write_todos,
        )
    )
    registry.register(
        Tool(
            name="library_list",
            description=(
                "List the user's reference library (uploaded reference materials: "
                "notes, docs, csv, code). Call this BEFORE asking the user to paste "
                "content — if a relevant file exists, read it with library_read."
            ),
            parameters={"properties": {}, "required": []},
            handler=tool_library_list,
        )
    )
    registry.register(
        Tool(
            name="library_read",
            description=(
                "Read a reference library file by id, or fuzzy-match by name/content "
                "keyword. Returns the full text content."
            ),
            parameters={
                "properties": {
                    "id": {"type": "string", "description": "File id from library_list", "default": ""},
                    "query": {"type": "string", "description": "Name/content keyword", "default": ""},
                },
                "required": [],
            },
            handler=tool_library_read,
        )
    )
