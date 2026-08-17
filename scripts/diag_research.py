"""Diagnose why deep research returns an empty evidence pack.

Usage: PYTHONPATH=src .venv/bin/python scripts/diag_research.py "<topic>" [category]
"""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import quote

import httpx

from cn_social_agent.cards.evidence import (
    build_pack,
    clean_snippet_text,
    is_useful_snippet,
    looks_like_serp_noise,
)
from cn_social_agent.cards.scrape import (
    UA,
    build_queries,
    extract_baidu_result_rows,
    extract_result_rows,
)


async def probe_engines(client: httpx.AsyncClient, q: str) -> None:
    urls = {
        "bing": f"https://www.bing.com/search?q={quote(q)}&setlang=zh-CN&cc=CN&ensearch=0",
        "baidu": f"https://www.baidu.com/s?wd={quote(q)}",
        "ddg": f"https://html.duckduckgo.com/html/?q={quote(q)}",
    }
    for name, url in urls.items():
        try:
            r = await client.get(url, headers={"User-Agent": UA}, timeout=9.0)
            html = r.text or ""
            rows = (
                extract_baidu_result_rows(html)
                if name == "baidu"
                else extract_result_rows(html)
            )
            print(
                f"[net] {name}: HTTP {r.status_code}, html {len(html)}B, "
                f"parsed rows {len(rows)}"
            )
            for row in rows[:2]:
                print(f"       sample: {row['text'][:80]}")
        except Exception as e:  # noqa: BLE001
            print(f"[net] {name}: FAILED {type(e).__name__}: {e}")


async def main() -> None:
    topic = sys.argv[1] if len(sys.argv) > 1 else "Grok Build"
    category = sys.argv[2] if len(sys.argv) > 2 else "product_explain"
    queries = build_queries(topic, category=category, depth="deep")
    print(f"topic={topic!r} category={category!r}")
    print(f"queries ({len(queries)}):")
    for q in queries:
        print(f"  - {q}")

    async with httpx.AsyncClient(follow_redirects=True, trust_env=True) as client:
        print("\n== engine probes (first query) ==")
        await probe_engines(client, queries[0])

        print("\n== full scrape + filter breakdown ==")
        raw: list[dict] = []
        for q in queries[:4]:
            url = f"https://www.bing.com/search?q={quote(q)}&setlang=zh-CN&cc=CN&ensearch=0"
            try:
                r = await client.get(url, headers={"User-Agent": UA}, timeout=9.0)
                rows = extract_result_rows(r.text or "")
            except Exception as e:  # noqa: BLE001
                print(f"  fetch fail {q!r}: {type(e).__name__}")
                continue
            for row in rows:
                raw.append({**row, "query": q, "engine": "bing", "role": topic})

    print(f"raw rows: {len(raw)}")
    n_noise = n_short = n_lowsig = n_ok = 0
    for row in raw:
        t = clean_snippet_text(row["text"])
        if looks_like_serp_noise(t):
            n_noise += 1
        elif len(t) < 20:
            n_short += 1
        elif not is_useful_snippet(t, role=topic, min_len=20, category=category):
            n_lowsig += 1
        else:
            n_ok += 1
    print(
        f"filter breakdown: serp_noise={n_noise} too_short={n_short} "
        f"low_signal={n_lowsig} kept={n_ok}"
    )
    pack = build_pack(raw, limit=40, category=category)
    print(f"build_pack count: {pack['count']}")
    for e in pack["evidences"][:5]:
        print(f"  [{e['score']}] {e['text'][:90]}")

    if n_lowsig and not n_ok:
        print("\nlow-signal examples (rejected by signal_hits<2):")
        shown = 0
        for row in raw:
            t = clean_snippet_text(row["text"])
            if len(t) >= 20 and not looks_like_serp_noise(t) and not is_useful_snippet(
                t, role=topic, min_len=20, category=category
            ):
                print(f"  - {t[:110]}")
                shown += 1
                if shown >= 6:
                    break


asyncio.run(main())
