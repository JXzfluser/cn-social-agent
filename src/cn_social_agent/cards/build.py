"""Build cover + knowledge cards from scrape snippets or LLM JSON."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from cn_social_agent.cards.categories import get_category, series_for
from cn_social_agent.cards.history import default_knowledge_pad, load_history
from cn_social_agent.cards.themes import FALLBACK_COVER, THEMES


def now_label() -> str:
    d = datetime.now()
    return d.strftime("%Y.%m.%d %H:%M")


# Dangling CJK connector at end of text — typical mid-phrase cut (…中的 / …与)
DANGLING_TAIL_RE = re.compile(r"[的中与和及了在为到从把被]$")


def clip(text: Any, n: int) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)].rstrip("，。、；;,. ") + "…"


def looks_truncated(text: Any) -> bool:
    s = str(text or "").strip()
    return s.endswith("…") or s.endswith("...") or s.endswith("⋯")


def clip_complete(text: Any, n: int, *, ellipsis: bool = False) -> str:
    """Trim to n chars without slicing through ASCII tokens (LangG… / State…)."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(s) <= n:
        return s
    cut_at = n
    rest = s[n : n + 1]
    if rest and re.match(r"[A-Za-z0-9_+.#-]", rest):
        for m in re.finditer(r"[A-Za-z][A-Za-z0-9_+.#-]*", s):
            if m.start() < n <= m.end():
                cut_at = m.end() if (m.end() - n) <= 12 else m.start()
                break
    cut = s[: max(cut_at, 0)].rstrip("，。、；;,. ")
    if not cut:
        cut = s[:n].rstrip()
    if ellipsis and len(s) > len(cut):
        return cut + "…"
    return cut


def short_step(text: Any, n: int = 16) -> str:
    """Compact flow/diagram label: keep 定义StateGraph, never 定义State…."""
    s = re.sub(r"^[-•·\s]+", "", str(text or "")).strip()
    s = re.sub(r"^【[^】]*】\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    if looks_truncated(s):
        s = re.sub(r"[…⋯.]+$", "", s).strip()
    if not s:
        return ""
    head = re.split(r"[，。；;：:、]", s, maxsplit=1)[0].strip() or s
    while len(head) > 4 and DANGLING_TAIL_RE.search(head):
        head = head[:-1]
    ident = re.match(r"^([\u4e00-\u9fff]{1,8}[A-Za-z][A-Za-z0-9_+.#-]*)", head)
    if ident and len(ident.group(1)) >= 4:
        return ident.group(1)
    en = re.match(r"^([A-Za-z][A-Za-z0-9_+.#-]{2,})", head)
    if en:
        return en.group(1)
    if len(head) <= n:
        return head
    # Mostly CJK: prefer ≤8 字动作短语，截断时再回退 1 字避免半截词
    cjk_n = len(re.findall(r"[\u4e00-\u9fff]", head))
    if cjk_n >= max(4, int(len(head) * 0.55)):
        budget = min(n, 8)
        cut = head[:budget]
        while cut and re.search(r"[的中与和及了在为到从把被]$", cut) and len(cut) > 4:
            cut = cut[:-1]
        if len(head) > len(cut) and len(cut) >= 5:
            # Drop a trailing CJK char that likely starts the next compound
            if re.search(r"[\u4e00-\u9fff]$", cut):
                cut = cut[:-1]
        return cut.rstrip("，。、；;,. ") or head[:budget]
    return clip_complete(head, n)


def _flow_item_looks_cut(item: str, pts: list[str]) -> bool:
    s = str(item or "").strip()
    if not s:
        return True
    if looks_truncated(s):
        return True
    for p in pts:
        if p and s != p and p.startswith(s) and len(p) >= len(s) + 3:
            return True
    if len(s) >= 6 and DANGLING_TAIL_RE.search(s):
        return True
    return False


def normalize_flow(flow_raw: Any, real_points: list[str] | None = None) -> list[str]:
    raw = [str(x).strip() for x in (flow_raw or []) if str(x).strip()]
    pts = [str(p).strip() for p in (real_points or []) if str(p).strip()]
    if not raw or any(_flow_item_looks_cut(x, pts) for x in raw):
        src = pts or raw
        return [s for s in (short_step(p) for p in src[:5]) if s]
    return [s for s in (short_step(x) for x in raw[:5]) if s]


def format_edition(
    edition: Any = None,
    *,
    user_id: str | None = None,
    email: str | None = None,
) -> str:
    """Normalize to「第 N 期」. Empty → next history index."""
    fallback_n = len(load_history(user_id, email=email)) + 1
    if edition is None or str(edition).strip() == "":
        return f"第 {fallback_n} 期"
    s = str(edition).strip()
    if re.fullmatch(r"\d+", s):
        return f"第 {int(s)} 期"
    m = re.search(r"第\s*(\d+)\s*期", s)
    if m:
        return f"第 {int(m.group(1))} 期"
    m2 = re.search(r"(\d+)", s)
    if m2:
        return f"第 {int(m2.group(1))} 期"
    return s


def apply_edition(cover: dict[str, Any], edition: Any, **hist_kw: Any) -> dict[str, Any]:
    cover = dict(cover or {})
    cover["edition"] = format_edition(edition if edition not in (None, "") else cover.get("edition"), **hist_kw)
    return cover


def coerce_points(raw: Any) -> list[str]:
    """Normalize keyPoint into a clean list of bullet strings.

    Handles: real list, newline string, or an accidental Python/JSON
    list-repr string like "['- a', '- b', '-…" that the LLM sometimes
    nests inside keyPoint (which used to be truncated with an ellipsis).
    """
    items: list[str] = []
    if isinstance(raw, (list, tuple)):
        items = [str(x) for x in raw]
    else:
        s = str(raw or "").replace("\r", "\n").strip()
        if not s:
            return []
        looks_like_list = s.lstrip().startswith("[") or "', '" in s or '", "' in s
        if looks_like_list:
            parsed: Any = None
            try:
                import ast

                parsed = ast.literal_eval(s)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, (list, tuple)):
                items = [str(x) for x in parsed]
            else:
                # Truncated repr — recover quoted fragments, drop the cut tail
                frags = re.findall(r"['\"]([^'\"]+?)['\"]", s)
                items = [f for f in frags if not f.strip().rstrip("-").strip() in ("", "…")]
        else:
            items = re.split(r"\n+", s)
    out: list[str] = []
    for it in items:
        t = re.sub(r"^[-•·\s]+", "", str(it or "")).strip()
        t = t.rstrip("…⋯").strip()
        if t:
            out.append(t)
    return out


def clip_points(points: list[str], *, max_items: int = 3, max_len: int = 36) -> list[str]:
    out: list[str] = []
    for p in points:
        t = clip(re.sub(r"^[-•·\s]+", "", str(p or "")), max_len)
        if t:
            out.append(t)
        if len(out) >= max_items:
            break
    return out


def split_sentences(text: str) -> list[str]:
    parts = re.findall(r"[^。！？!?；;\n]+[。！？!?；;]?", text or "")
    return [s.strip() for s in parts if 10 <= len(s.strip()) <= 110]


def extract_real_points(snippets: list[str], theme: dict[str, Any]) -> list[str]:
    kws = [k.lower() for k in theme.get("keywords") or []]
    seen: set[str] = set()
    points: list[str] = []
    for snip in snippets:
        lower = snip.lower()
        if not any(k in lower for k in kws):
            continue
        for sent in split_sentences(snip):
            sl = sent.lower()
            if any(k in sl for k in kws):
                key = sent[:20]
                if key not in seen:
                    seen.add(key)
                    points.append(sent)
            if len(points) >= 4:
                break
        if len(points) >= 4:
            break
    return points[:3]


def build_cards(
    roles: list[str],
    role_snippets: list[list[str]],
    *,
    category: str = "hiring_insight",
    edition: Any = None,
    user_id: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    cat = get_category(category)
    series = series_for(category)
    all_snippets = [s for row in role_snippets for s in row if s and len(s) > 15]
    live = len(all_snippets) > 4

    scored: list[dict[str, Any]] = []
    for th in THEMES:
        matched: list[str] = []
        found: set[str] = set()
        kws = [k.lower() for k in th["keywords"]]
        for snip in all_snippets:
            lower = snip.lower()
            hit = [k for k in kws if k in lower]
            if hit:
                matched.append(snip)
                found.update(hit)
        scored.append(
            {
                "theme": th,
                "snippets": matched,
                "found": list(found),
                "score": len(matched) * 2 + len(found),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]
    while len(top) < 3 and len(top) < len(scored):
        top.append(scored[len(top)])

    knowledge: list[dict[str, Any]] = []
    for s in top:
        th = s["theme"]
        real_points = extract_real_points(s["snippets"], th)
        real_points = clip_points(real_points, max_items=3, max_len=42)
        skills = (s["found"] or [])[:8]
        key_point = (
            f"本次扫描高频提及：{'、'.join(skills)}。" if skills else th["keyBase"]
        )
        # Prefer theme teaching bullets when scrape points are thin
        if len(real_points) < 2:
            real_points = clip_points(
                [
                    re.sub(r"^[-•·\s]+", "", line).strip()
                    for line in str(th["keyBase"]).split("\n")
                    if line.strip()
                ],
                max_items=3,
                max_len=42,
            )
            key_point = th["keyBase"]
        knowledge.append(
            {
                **series,
                "topicTitle": th["topicTitle"],
                "concept": th["concept"],
                "keyPoint": key_point,
                "realPoints": real_points,
                "example": th["example"],
                "flow": list(th.get("flow") or [])[:4],
            }
        )

    from cn_social_agent.cards.scrape import pick_market_note

    market_note = pick_market_note(all_snippets)
    # Tags: topics first (up to 4), then mode chip — cover layout adapts to count
    topic_tags = [clip(r, 10) for r in roles if str(r).strip()][:4]
    mode_tag = "实时扫描" if live else "内置数据"
    tags = [*topic_tags, mode_tag, cat["label"]][:5]
    cover = {
        **series,
        "title": cat["default_title"],
        "gradientPart": f"{now_label()} {mode_tag}",
        "edition": format_edition(edition, user_id=user_id, email=email),
        "marketNote": market_note,
        "description": (
            f"基于{mode_tag}资料，围绕 "
            f"{'、'.join(roles)}，提炼出 {len(knowledge)} 个关键知识点。"
        ),
        "tags": tags,
        "spread": True,
    }
    return {
        "cover": cover,
        "knowledge": knowledge,
        "mode": "live" if live else "cached",
        "sources": all_snippets[:6],
        "snippetCount": len(all_snippets),
        "dateLabel": cover["gradientPart"],
        "edition": cover["edition"],
        "category": cat["id"],
    }


def fallback_payload(
    roles: list[str] | None = None,
    *,
    category: str = "hiring_insight",
    edition: Any = None,
    user_id: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    from cn_social_agent.cards.styles import CATEGORY_DEFAULT_STYLE, infer_card_kind

    cat = get_category(category)
    series = series_for(category)
    style_id = CATEGORY_DEFAULT_STYLE.get(cat["id"]) or "academic"
    roles = roles or ["AI Agent 开发工程师", "AI 应用开发工程师", "AI 全栈工程师"]
    knowledge = []
    for th in THEMES[:3]:
        card = {
            **series,
            "topicTitle": th["topicTitle"],
            "concept": th["concept"],
            "keyPoint": th["keyBase"],
            "realPoints": [],
            "example": th["example"],
            "flow": th.get("flow") if isinstance(th.get("flow"), list) else [],
        }
        card["card_kind"] = infer_card_kind(card)
        knowledge.append(card)
    tags = (
        FALLBACK_COVER["tags"][:3]
        if cat["id"] == "hiring_insight"
        else [clip(r, 10) for r in roles[:4]]
    )
    cover = {
        **FALLBACK_COVER,
        **series,
        "title": cat["default_title"],
        "gradientPart": f"{now_label()} 内置数据",
        "edition": format_edition(edition, user_id=user_id, email=email),
        "marketNote": "",
        "description": FALLBACK_COVER["description"]
        if cat["id"] == "hiring_insight"
        else cat["description"],
        "tags": tags,
        "spread": True,
        "visual_style": style_id,
        "source": "",
        "brand_signature": "",
    }
    return {
        "cover": cover,
        "knowledge": knowledge,
        "mode": "cached",
        "sources": [],
        "snippetCount": 0,
        "dateLabel": cover["gradientPart"],
        "edition": cover["edition"],
        "category": cat["id"],
        "visual_style": style_id,
    }


def _theme_card(
    th: dict[str, Any],
    series: dict[str, str],
    *,
    rich_journal: bool = False,
) -> dict[str, Any]:
    from cn_social_agent.cards.styles import infer_card_kind

    max_points = 6 if rich_journal else 5
    concept_max = 280 if rich_journal else 200
    example_max = 180 if rich_journal else 120
    pts = clip_points(
        [
            re.sub(r"^[-•·\s]+", "", s).strip()
            for s in re.split(r"\n+", str(th.get("keyBase") or ""))
            if s.strip()
        ],
        max_items=max_points,
        max_len=72 if rich_journal else 52,
    )
    flow = normalize_flow(th.get("flow") if isinstance(th.get("flow"), list) else [], pts)
    card = {
        **series,
        "topicTitle": clip_complete(th.get("topicTitle"), 36),
        "concept": clip(th.get("concept"), concept_max),
        "keyPoint": "\n".join(f"- {p}" for p in pts) if pts else clip(th.get("keyBase"), 200),
        "realPoints": pts,
        "example": clip(th.get("example"), example_max),
        "flow": flow,
        "source": "",
        "quote": "",
        "metric": "",
        "metric_note": "",
        "compare_left": "",
        "compare_right": "",
    }
    card["card_kind"] = infer_card_kind(card)
    return card


def _normalize_one_card(
    k: dict[str, Any],
    *,
    series: dict[str, str],
    fallback_title: str,
    rich_journal: bool = False,
) -> dict[str, Any]:
    from cn_social_agent.cards.styles import infer_card_kind

    max_points = 6 if rich_journal else 5
    point_len = 72 if rich_journal else 56
    concept_max = 280 if rich_journal else 200
    example_max = 180 if rich_journal else 120
    # Prefer explicit realPoints; else keyPoint (may arrive as list or list-repr string)
    if isinstance(k.get("realPoints"), list) and k.get("realPoints"):
        raw_points = list(k["realPoints"])
    else:
        raw_points = coerce_points(k.get("keyPoint"))
    kp = "\n".join(f"- {p}" for p in raw_points)
    real = clip_points(
        [re.sub(r"^[-•·\s]+", "", str(s)).strip() for s in raw_points if str(s).strip()],
        max_items=max_points,
        max_len=point_len,
    )
    flow = normalize_flow(k.get("flow") if isinstance(k.get("flow"), list) else [], real)
    compare = k.get("compare") if isinstance(k.get("compare"), dict) else {}
    left = clip(
        (compare.get("left") if isinstance(compare, dict) else "")
        or k.get("compare_left")
        or "",
        48,
    )
    right = clip(
        (compare.get("right") if isinstance(compare, dict) else "")
        or k.get("compare_right")
        or "",
        48,
    )
    card = {
        **series,
        "topicTitle": clip_complete(k.get("topicTitle") or fallback_title, 36),
        "concept": clip(k.get("concept") or "", concept_max),
        "keyPoint": "\n".join(f"- {p}" for p in real) if real else clip(kp, 200),
        "realPoints": real,
        "example": clip(k.get("example") or "", example_max),
        "flow": flow,
        "source": clip(k.get("source") or "", 40),
        "quote": clip(k.get("quote") or "", 80),
        "metric": clip(k.get("metric") or k.get("data_value") or "", 16),
        "metric_note": clip(k.get("metric_note") or k.get("data_note") or "", 48),
        "compare_left": left,
        "compare_right": right,
    }
    card["card_kind"] = infer_card_kind({**card, "card_kind": k.get("card_kind") or k.get("kind")})
    return card


def _attach_diagram(card: dict[str, Any], raw_diagram: Any = None) -> dict[str, Any]:
    from cn_social_agent.cards.diagram import normalize_diagram

    card["diagram"] = normalize_diagram(
        raw_diagram,
        card_kind=str(card.get("card_kind") or ""),
        flow=card.get("flow") if isinstance(card.get("flow"), list) else None,
        points=card.get("realPoints") if isinstance(card.get("realPoints"), list) else None,
        compare_left=str(card.get("compare_left") or ""),
        compare_right=str(card.get("compare_right") or ""),
        metric=str(card.get("metric") or ""),
        quote=str(card.get("quote") or ""),
    )
    return card


def _normalize_front_matter(
    parsed: dict[str, Any],
    knowledge: list[dict[str, Any]],
    roles: list[str],
    evidence_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    from cn_social_agent.cards.evidence import selected_evidences

    fm_raw = parsed.get("frontMatter") if isinstance(parsed.get("frontMatter"), dict) else {}
    guide_raw = fm_raw.get("guide") if isinstance(fm_raw.get("guide"), dict) else {}
    promises_raw = guide_raw.get("promises") if isinstance(guide_raw.get("promises"), list) else []
    promises = [clip(p, 28) for p in promises_raw if str(p).strip()][:3]
    while len(promises) < 3:
        idx = len(promises)
        if idx < len(knowledge):
            title = knowledge[idx].get("topicTitle") or "要点"
            promises.append(clip(f"掌握{title}", 28))
        else:
            promises.append(clip(f"带走要点{idx + 1}", 28))
    n_ev = len(selected_evidences(evidence_pack)) if evidence_pack is not None else 0
    role_part = "、".join(clip(r, 12) for r in (roles or [])[:3] if str(r).strip()) or "本期主题"
    meta = clip(guide_raw.get("meta") or f"基于 {n_ev} 条证据 · {role_part}", 56)
    toc = [
        {
            "index": i + 1,
            "title": str(card.get("topicTitle") or ""),
            "kind": str(card.get("card_kind") or "concept"),
            "diagram": str((card.get("diagram") or {}).get("type") or "bullets"),
        }
        for i, card in enumerate(knowledge)
    ]
    return {
        "guide": {
            "headline": clip_complete(guide_raw.get("headline") or "本期导读", 24),
            "promises": promises,
            "meta": meta,
        },
        "toc": toc,
    }


def normalize_llm_payload(
    parsed: dict[str, Any],
    roles: list[str],
    *,
    category: str = "hiring_insight",
    edition: Any = None,
    user_id: str | None = None,
    email: str | None = None,
    evidence_pack: dict[str, Any] | None = None,
    rich_journal: bool = False,
) -> dict[str, Any]:
    from cn_social_agent.cards.evidence import selected_evidences, validate_evidence_ids
    from cn_social_agent.cards.scrape import pick_market_note
    from cn_social_agent.cards.styles import CATEGORY_DEFAULT_STYLE
    from cn_social_agent.cards.themes import THEMES

    cat = get_category(category)
    series = series_for(category)
    today = now_label()
    knowledge_raw = parsed.get("knowledge") or []
    knowledge: list[dict[str, Any]] = []
    for i, k in enumerate(knowledge_raw[:8]):
        if not isinstance(k, dict):
            continue
        if not (
            k.get("topicTitle")
            or k.get("concept")
            or k.get("keyPoint")
            or k.get("example")
            or k.get("quote")
        ):
            continue
        card = _normalize_one_card(
            k, series=series, fallback_title=cat["label"], rich_journal=rich_journal
        )
        card_text = " ".join(
            str(x or "")
            for x in (
                card.get("topicTitle"),
                card.get("concept"),
                card.get("keyPoint"),
                card.get("example"),
            )
        )
        if evidence_pack is not None:
            eids = validate_evidence_ids(
                k.get("evidenceIds") if isinstance(k.get("evidenceIds"), list) else [],
                evidence_pack,
                card_text=card_text,
            )
            card["evidenceIds"] = eids
            card["stance"] = "evidence" if eids else "opinion"
        else:
            raw_ids = k.get("evidenceIds") if isinstance(k.get("evidenceIds"), list) else None
            if raw_ids is not None:
                card["evidenceIds"] = [str(x) for x in raw_ids if str(x).strip()][:4]
                card["stance"] = "evidence" if card["evidenceIds"] else "opinion"

        has_evidence = bool(card.get("evidenceIds"))
        th = THEMES[i % len(THEMES)]
        padded = False
        if len(card["concept"]) < 24 or len(card["realPoints"]) < 2:
            filled = _theme_card(th, series, rich_journal=rich_journal)
            if len(card["concept"]) < 24:
                card["concept"] = filled["concept"]
                padded = True
            # Soften: with evidenceIds, only pad missing short fields — do not wipe keypoints
            if len(card["realPoints"]) < 2 and not has_evidence:
                card["realPoints"] = filled["realPoints"]
                card["keyPoint"] = filled["keyPoint"]
                padded = True
            elif len(card["realPoints"]) < 1:
                card["realPoints"] = filled["realPoints"][:1]
                card["keyPoint"] = filled["keyPoint"]
                padded = True
            if len(card["example"]) < 20:
                card["example"] = filled["example"]
                padded = True
            if not card["flow"]:
                card["flow"] = filled.get("flow") or []
                padded = True
        if padded:
            card["paddedFromTheme"] = True
            if not card.get("stance"):
                card["stance"] = "template"
        if not card["flow"]:
            mech = next((p for p in card["realPoints"] if "机制" in p or "→" in p), "")
            parts = [p.strip() for p in re.split(r"→|➞|->|/|\|", mech) if p.strip()]
            parts = [re.sub(r"^【.*?】", "", p).strip() for p in parts]
            derived = [short_step(p) for p in parts if len(p) >= 2]
            card["flow"] = derived[:5] or normalize_flow([], card["realPoints"])
        else:
            # Heal mid-CJK cuts left by older drafts / LLM
            card["flow"] = normalize_flow(card.get("flow"), card.get("realPoints"))
        # Always attach diagram so journal pages are never blank visually
        _attach_diagram(card, k.get("diagram"))
        knowledge.append(card)
    # Non-rich scan still pads to 3 for layout; rich journal never invents silent theme cards
    if not rich_journal:
        while len(knowledge) < 3:
            th = THEMES[len(knowledge) % len(THEMES)]
            filled = _theme_card(th, series, rich_journal=False)
            filled["card_kind"] = "concept"
            filled["paddedFromTheme"] = True
            filled["stance"] = "template"
            if evidence_pack is not None:
                eids = validate_evidence_ids(
                    [], evidence_pack, card_text=filled.get("topicTitle") or ""
                )
                filled["evidenceIds"] = eids
                filled["stance"] = "evidence" if eids else "template"
            _attach_diagram(filled)
            knowledge.append(filled)
    cov = parsed.get("cover") if isinstance(parsed.get("cover"), dict) else {}
    tags_raw = cov.get("tags") if isinstance(cov.get("tags"), list) else roles
    tags = [clip_complete(t, 14) for t in (tags_raw or roles) if str(t).strip()][:5]
    tags = [t for t in tags if t and not looks_truncated(t)]
    if len(tags) < 2:
        tags = [*tags, *[clip_complete(r, 14) for r in roles if clip_complete(r, 14) not in tags]][:4]
    style_id = str(cov.get("visual_style") or parsed.get("visual_style") or "").strip()
    if not style_id:
        style_id = CATEGORY_DEFAULT_STYLE.get(cat["id"]) or "academic"
    market_note = str(cov.get("marketNote") or "").strip()
    from cn_social_agent.cards.evidence import clean_snippet_text, looks_like_serp_noise

    market_note = clean_snippet_text(market_note)
    if looks_like_serp_noise(market_note) or looks_truncated(market_note):
        market_note = ""
    if not market_note and evidence_pack is not None:
        market_note = pick_market_note(
            [e.get("text", "") for e in selected_evidences(evidence_pack)]
        )
    market_note = clean_snippet_text(market_note)
    if looks_like_serp_noise(market_note) or looks_truncated(market_note):
        market_note = ""
    market_note = clip(market_note, 56) if market_note else ""
    cover = {
        **series,
        "title": clip_complete(cov.get("title") or cat["default_title"], 40),
        "gradientPart": today,
        "edition": format_edition(
            edition if edition not in (None, "") else cov.get("edition"),
            user_id=user_id,
            email=email,
        ),
        "marketNote": market_note,
        "description": clip(
            cov.get("description") or f"围绕 {'、'.join(roles[:3])} 的{cat['label']}学习要点。",
            96,
        ),
        "tags": tags,
        "spread": True,
        "visual_style": style_id,
        "source": clip(cov.get("source") or parsed.get("source") or "", 48),
        "brand_signature": clip(
            cov.get("brand_signature") or parsed.get("brand_signature") or "", 24
        ),
    }
    out: dict[str, Any] = {
        "cover": cover,
        "knowledge": knowledge,
        "category": cat["id"],
        "visual_style": style_id,
    }
    if rich_journal or len(knowledge) >= 4:
        out["frontMatter"] = _normalize_front_matter(parsed, knowledge, roles, evidence_pack)
    return out
