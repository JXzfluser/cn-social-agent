"""Lightweight JD snippet scrape via httpx (Sogou / Bing / Baidu / DDG)."""

from __future__ import annotations

import asyncio
import re
from html import unescape
from typing import Any
from urllib.parse import quote

import httpx

from cn_social_agent.cards.evidence import is_useful_snippet

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# AI-tool nav/ad sites that dominate Bing CN results but carry no evidence.
AD_NAV_DOMAINS = (
    "ai-bot.cn",
    "toolify.ai",
    "jianying.com",
    "aigc.cn",
    "top10.com",
    "aibase.com",
    "grok-cn.top",
    "grok.online",
    "grokzh.com",
    "docs-zh.com",
)


def _is_ad_nav_row(url: str, text: str) -> bool:
    hay = f"{url} {text[:120]}".lower()
    return any(d in hay for d in AD_NAV_DOMAINS)


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_snippet(t: str) -> str:
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"View all", "", t, flags=re.I)
    t = re.sub(r"[\s·•\-–—]{2,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def filter_snippets(
    snippets: list[str],
    *,
    role: str = "",
    limit: int = 12,
    category: str = "hiring_insight",
) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in snippets:
        t = _clean_snippet(str(s or ""))
        if not t or t in seen:
            continue
        if not is_useful_snippet(t, role=role, category=category):
            continue
        seen.add(t)
        out.append(t[:400])
        if len(out) >= limit:
            break
    return out


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    role: str = "",
    limit: int = 12,
    category: str = "hiring_insight",
) -> list[dict[str, Any]]:
    """Dedupe + usefulness filter for structured scrape rows."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        t = _clean_snippet(str(r.get("text") or ""))
        if not t or t in seen:
            continue
        if _is_ad_nav_row(str(r.get("url") or ""), t):
            continue
        if not is_useful_snippet(t, role=role, category=category):
            continue
        seen.add(t)
        out.append({**r, "text": t[:400]})
        if len(out) >= limit:
            break
    return out


def pick_market_note(snippets: list[str], *, fallback: str = "") -> str:
    """First useful JD-like line for cover marketNote; else fallback / empty."""
    from cn_social_agent.cards.build import looks_truncated
    from cn_social_agent.cards.evidence import clean_snippet_text, looks_like_serp_noise

    for s in snippets:
        note = clean_snippet_text(s)
        if looks_like_serp_noise(note) or looks_truncated(note):
            continue
        if is_useful_snippet(note) and len(note) >= 36:
            return note if len(note) <= 56 else note[:55].rstrip("，。、；;,. ") + "…"
    fb = clean_snippet_text(fallback or "")
    if looks_like_serp_noise(fb) or looks_truncated(fb):
        return ""
    return fb.strip()[:56]


def _href_title_from_block(block: str) -> tuple[str, str]:
    """Best-effort link + title from a result card."""
    am = re.search(
        r'<h[23][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
        block,
        re.I,
    )
    if not am:
        am = re.search(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*result__a[^"\']*["\'][^>]*>([\s\S]*?)</a>',
            block,
            re.I,
        )
    if not am:
        am = re.search(
            r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            block,
            re.I,
        )
    if not am:
        return "", ""
    url = unescape(am.group(1)).strip()[:200]
    title = _clean_snippet(_strip_html(am.group(2)))[:80]
    if url.startswith("/"):
        return "", title
    return url, title


def extract_result_rows(html: str) -> list[dict[str, Any]]:
    """Parse organic search cards into {text, title, url}."""
    rows: list[dict[str, Any]] = []

    def add(block: str) -> None:
        text = _clean_snippet(_strip_html(block))
        if len(text) <= 20:
            return
        url, title = _href_title_from_block(block)
        rows.append({"text": text[:400], "title": title, "url": url})

    for m in re.finditer(r'<li class="b_algo[^>]*>[\s\S]*?</li>', html):
        add(m.group(0))
    if len(rows) < 3:
        for m in re.finditer(r'<div class="result[^"]*"[^>]*>[\s\S]*?</div>\s*</div>', html):
            add(m.group(0))
    if len(rows) < 3:
        for m in re.finditer(r'<div class="links_main[^"]*"[^>]*>[\s\S]*?</div>', html):
            add(m.group(0))
    if not rows:
        for m in re.finditer(r'<p class="b_lineclamp[^"]*"[^>]*>([\s\S]*?)</p>', html):
            t = _clean_snippet(_strip_html(m.group(0)))
            if len(t) > 20:
                rows.append({"text": t[:400], "title": "", "url": ""})
        for m in re.finditer(r'<div class="b_caption[^"]*"[^>]*>([\s\S]*?)</div>', html):
            t = _clean_snippet(_strip_html(m.group(0)))
            if len(t) > 20:
                rows.append({"text": t[:400], "title": "", "url": ""})
        for m in re.finditer(r'result__snippet[^>]*>([\s\S]*?)</a>', html):
            t = _clean_snippet(_strip_html(m.group(0)))
            if len(t) > 20:
                rows.append({"text": t[:400], "title": "", "url": ""})

    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for r in rows:
        t = r["text"]
        if t in seen:
            continue
        seen.add(t)
        uniq.append(r)
    return uniq


def extract_snippets(html: str) -> list[str]:
    return [r["text"] for r in extract_result_rows(html)]


def extract_baidu_result_rows(html: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<div class="(?:result|c-container)[^"]*"[^>]*>[\s\S]*?</div>\s*(?=<div class="(?:result|c-container)|$)',
        html,
    ):
        block = m.group(0)
        text = _clean_snippet(_strip_html(block))
        if len(text) <= 20:
            continue
        url, title = _href_title_from_block(block)
        rows.append({"text": text[:400], "title": title, "url": url})
    if rows:
        return rows
    # Fallback: abstract-only blocks without stable URL
    for pat in (
        r'<div class="c-abstract[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div class="c-span9[^"]*"[^>]*>([\s\S]*?)</div>',
    ):
        for m in re.finditer(pat, html):
            t = _clean_snippet(_strip_html(m.group(0)))
            if len(t) > 20:
                rows.append({"text": t[:400], "title": "", "url": ""})
    return rows


def extract_baidu_snippets(html: str) -> list[str]:
    return [r["text"] for r in extract_baidu_result_rows(html)]


def extract_sogou_result_rows(html: str) -> list[dict[str, Any]]:
    """Parse Sogou web results (vrwrap cards) into {text, title, url}."""
    rows: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<div class="vrwrap"[\s\S]*?(?=<div class="vrwrap"|<div id="page|$)', html
    ):
        block = m.group(0)
        text = _clean_snippet(_strip_html(block))
        if len(text) <= 20:
            continue
        url, title = "", ""
        am = re.search(
            r'<h3[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            block,
            re.I,
        )
        if not am:
            am = re.search(
                r'<a[^>]+href=["\']((?:/link\?url=|https?://)[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                block,
                re.I,
            )
        if am:
            url = unescape(am.group(1)).strip()
            title = _clean_snippet(_strip_html(am.group(2)))[:80]
        if url.startswith("/link"):
            url = "https://www.sogou.com" + url
        rows.append({"text": text[:400], "title": title, "url": url[:200]})
    return rows


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(url, headers={"User-Agent": UA}, timeout=9.0)
        if r.status_code >= 400:
            return ""
        return r.text or ""
    except Exception:  # noqa: BLE001
        return ""


def _role_query(role: str, suffix: str) -> str:
    """Quote multi-char roles so search engines don't split 独立开发者 → 独立."""
    r = (role or "").strip()
    if len(r) >= 3:
        return f'"{r}" {suffix}'.strip()
    return f"{r} {suffix}".strip()


def build_queries(
    role: str, *, category: str = "hiring_insight", depth: str = "shallow"
) -> list[str]:
    """Build search queries.

    Shallow: quoted role + first 3 suffixes (compat).
    Deep: subject-forward queries — every query is bound to the role/topic so
    results follow what the user actually asked for. Suffixes are only
    framing (岗位职责 / 技术原理 / 落地案例), never standalone queries, and
    must not hardcode a technology, or every topic would return that stack.
    """
    from cn_social_agent.cards.categories import get_category

    cat = get_category(category)
    suffixes = list(
        cat.get("scrape_suffixes")
        or ["招聘 岗位职责 任职要求 技能 经验"]
    )
    role = (role or "").strip()
    if depth == "shallow":
        return [_role_query(role, suf) for suf in suffixes[:3]]
    if not role:
        return [suf for suf in suffixes[:6]]

    out: list[str] = []
    seen: set[str] = set()

    def add(q: str) -> None:
        q = re.sub(r"\s+", " ", (q or "").strip())
        if q and q not in seen:
            seen.add(q)
            out.append(q)

    # 1) Topic + engineering framing first (less ad-poisoned than quoted JD)
    for suf in suffixes[3:8]:
        add(f"{role} {suf}")
    # 2) Topic + JD framing
    for suf in suffixes[:4]:
        add(f"{role} {suf}")
    # 3) Quoted topic (works for some engines / non-spam days)
    for suf in suffixes[:3]:
        add(_role_query(role, suf))
    # 4) Category dims, still bound to the topic
    dims = [d.strip() for d in str(cat.get("llm_dims") or "").split("/") if d.strip()]
    for d in dims[:3]:
        add(f"{role} {d}")

    return out[:10]


async def scan_role(
    role: str,
    *,
    category: str = "hiring_insight",
    depth: str = "shallow",
    stats: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return raw evidence rows {text, query, engine, role} (not yet packed).

    Engine order: Sogou (CN-reachable, least ad-poisoned) → Bing CN →
    Baidu → DDG. If `stats` is given, per-engine fetch/row counts are
    recorded there so callers can explain an empty pack.
    """
    queries = build_queries(role, category=category, depth=depth)
    if not queries:
        return []
    per_role_stop = 6 if depth == "shallow" else 18
    limit = 12 if depth == "shallow" else 24
    rows: list[dict[str, Any]] = []
    st = stats if stats is not None else {}

    def bump(engine: str, key: str, n: int = 1) -> None:
        e = st.setdefault(engine, {"pages": 0, "raw": 0, "empty": 0})
        e[key] = e.get(key, 0) + n

    def useful_count() -> int:
        return len(filter_rows(rows, role=role, limit=limit, category=category))

    def add_rows(items: list[dict[str, Any]], *, query: str, engine: str) -> None:
        bump(engine, "pages")
        if not items:
            bump(engine, "empty")
        for item in items:
            text = str(item.get("text") or "")
            if not text:
                continue
            bump(engine, "raw")
            rows.append(
                {
                    "text": text,
                    "query": query,
                    "engine": engine,
                    "role": role,
                    "url": str(item.get("url") or "")[:200],
                    "title": str(item.get("title") or "")[:80],
                }
            )

    async with httpx.AsyncClient(follow_redirects=True, trust_env=True) as client:
        # 1) Sogou: reachable from CN and returns article/JD content where
        #    Bing CN serves mostly AI-tool nav ads.
        for q in queries[: 6 if depth == "deep" else 3]:
            html = await _fetch(client, f"https://www.sogou.com/web?query={quote(q)}")
            if html:
                add_rows(extract_sogou_result_rows(html), query=q, engine="sogou")
            if useful_count() >= per_role_stop:
                break
        # 2) Bing CN. No whole-page spam skip: junk rows are dropped
        #    per-row (ad-domain blacklist + usefulness filter), so the few
        #    good rows on an ad-heavy page still survive.
        if useful_count() < per_role_stop:
            for q in queries:
                url = (
                    f"https://www.bing.com/search?q={quote(q)}"
                    f"&setlang=zh-CN&cc=CN&ensearch=0"
                )
                html = await _fetch(client, url)
                if html:
                    add_rows(extract_result_rows(html), query=q, engine="bing")
                if useful_count() >= per_role_stop:
                    break
        # 3) Baidu fallback (often bot-blocked: returns a tiny stub page).
        if useful_count() < 4:
            for fq in queries[:3]:
                baidu = await _fetch(client, f"https://www.baidu.com/s?wd={quote(fq)}")
                if baidu:
                    add_rows(extract_baidu_result_rows(baidu), query=fq, engine="baidu")
                if useful_count() >= 4:
                    break
        # 4) DDG last resort (usually unreachable from CN; capped at one
        #    query to bound timeout latency).
        if useful_count() < 3:
            fq = queries[0]
            ddg = await _fetch(client, f"https://html.duckduckgo.com/html/?q={quote(fq)}")
            if not ddg:
                ddg = await _fetch(client, f"https://lite.duckduckgo.com/lite/?q={quote(fq)}")
            if ddg:
                add_rows(extract_result_rows(ddg), query=fq, engine="ddg")

    kept = filter_rows(rows, role=role, limit=limit, category=category)
    st["kept"] = len(kept)
    st["raw_total"] = len(rows)
    return kept


def describe_scan_stats(stats_list: list[dict[str, Any]]) -> str:
    """Human-readable per-engine summary for empty-pack diagnostics (中文)."""
    agg: dict[str, dict[str, int]] = {}
    raw_total = 0
    for st in stats_list or []:
        raw_total += int(st.get("raw_total") or 0)
        for eng, e in st.items():
            if not isinstance(e, dict):
                continue
            a = agg.setdefault(eng, {"pages": 0, "raw": 0, "empty": 0})
            for k in ("pages", "raw", "empty"):
                a[k] += int(e.get(k) or 0)
    parts: list[str] = []
    names = {"sogou": "搜狗", "bing": "必应", "baidu": "百度", "ddg": "DDG"}
    for eng in ("sogou", "bing", "baidu", "ddg"):
        e = agg.get(eng)
        label = names[eng]
        if not e or not e["pages"]:
            parts.append(f"{label}不可达/超时")
        elif not e["raw"]:
            parts.append(f"{label}返回空结果（可能被反爬拦截）")
        else:
            parts.append(f"{label}抓到 {e['raw']} 条但均为广告/导航噪声")
    return "；".join(parts)


async def scan_roles(
    roles: list[str],
    *,
    category: str = "hiring_insight",
    depth: str = "shallow",
    stats_out: list[dict[str, Any]] | None = None,
) -> list[list[dict[str, Any]]]:
    stats_list: list[dict[str, Any]] = [{} for _ in roles]
    tasks = [
        scan_role(r, category=category, depth=depth, stats=st)
        for r, st in zip(roles, stats_list)
    ]
    out = list(await asyncio.gather(*tasks))
    if stats_out is not None:
        stats_out.extend(stats_list)
    return out
