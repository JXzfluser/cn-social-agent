"""Topic distillation, seed evidence, and relevance gating for card research.

When a card comes from an Agent / hotspot handoff we already have a chosen
title + fetched article notes. Feeding the whole long title into a search
engine produces off-topic junk, so we:

1. distill a short topic ("浏览器扩展合集：我们为你找到…" → "浏览器扩展合集"),
2. turn the fetched notes into *seed* evidence rows, and
3. gate any top-up scrape results by topic relevance so they stay on subject.
"""

from __future__ import annotations

import re
from typing import Any

from cn_social_agent.cards.evidence import clean_snippet_text, looks_like_serp_noise

_SEP_RE = re.compile(r"[：:｜|—\-–]\s*")
_CLAUSE_RE = re.compile(r"[，,。;；、]")
_BRACKET_RE = re.compile(r"[「」『』【】\[\]（）()\"'“”‘’]")
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#]{1,}")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")

# Generic title-filler bigrams that carry no subject signal.
_STOP_BIGRAMS = frozenset(
    {
        "我们", "你们", "他们", "这个", "那个", "这些", "那些", "为你",
        "找到", "实用", "有趣", "推荐", "分享", "介绍", "盘点", "最新",
        "今天", "如何", "怎么", "什么", "一个", "一款", "几款", "值得",
        "了解", "看看", "带你", "干货", "合辑",
    }
)

# Bigrams that appear too broadly to prove topic relevance on their own.
# (扩展/插件/合集 stay OUT of here — they are strong discriminators.)
_GENERIC_BIGRAMS = frozenset(
    {
        "浏览", "工具", "软件", "功能", "使用", "应用", "教程", "开发",
        "服务", "系统", "平台", "数据", "用户", "版本", "下载", "手机",
        "电脑", "网站", "在线", "免费", "技术", "产品", "方法", "内容",
    }
)


def extract_short_topic(title: str, notes: str = "") -> str:
    """Best-effort short subject from a long content title.

    Cuts at the first strong separator, then trims trailing clauses so the
    result is a searchable noun phrase rather than a full sentence.
    """
    raw = str(title or "").strip()
    if not raw:
        return ""
    head = _SEP_RE.split(raw, maxsplit=1)[0].strip()
    head = _BRACKET_RE.sub(" ", head)
    head = re.sub(r"\s+", " ", head).strip(" 、,，。.:：")
    if not head:
        head = raw
    if len(head) > 24:
        head = _CLAUSE_RE.split(head)[0].strip()
    # Still long / a full sentence: keep the first couple of salient tokens.
    if len(head) > 24:
        toks = _salient_tokens(head)
        if toks:
            head = " ".join(toks[:3])
    return head[:40].strip()


def _salient_tokens(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tok in _ASCII_TOKEN_RE.findall(text) + _CJK_RUN_RE.findall(text):
        t = tok.strip()
        if len(t) >= 2 and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def build_search_terms(
    title: str, notes: str = "", *, category: str = "", limit: int = 4
) -> list[str]:
    """Short, subject-bound search terms for top-up scraping."""
    topic = extract_short_topic(title, notes)
    terms: list[str] = []
    seen: set[str] = set()
    for tok in [topic, *_salient_tokens(topic)]:
        t = str(tok or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            terms.append(t)
        if len(terms) >= limit:
            break
    return terms


def topic_terms(topic: str, extra: str = "") -> dict[str, Any]:
    """Tokenize a topic into ascii words + CJK bi/tri-grams for relevance.

    Trigrams carry the discriminating subject (浏览器 / 扩展合), while single
    bigrams like 浏览 are too common to trust on their own.
    """
    blob = f"{topic} {extra}"
    ascii_words = {w.lower() for w in _ASCII_TOKEN_RE.findall(blob) if len(w) >= 2}
    bigrams: set[str] = set()
    trigrams: set[str] = set()
    for run in _CJK_RUN_RE.findall(blob):
        for i in range(len(run) - 1):
            bg = run[i : i + 2]
            if bg not in _STOP_BIGRAMS:
                bigrams.add(bg)
        for i in range(len(run) - 2):
            trigrams.add(run[i : i + 3])
    return {"ascii": ascii_words, "bigrams": bigrams, "trigrams": trigrams}


def is_topic_relevant(text: str, terms: dict[str, Any]) -> bool:
    """True when a snippet shares real subject signal with the topic.

    Relevant if it matches an ascii topic term, OR any topic trigram, OR at
    least two distinct topic bigrams. A lone common bigram (浏览, 工具…) is not
    enough. Empty topic terms → always relevant (no gate).
    """
    ascii_terms = terms.get("ascii") or set()
    bigrams = terms.get("bigrams") or set()
    trigrams = terms.get("trigrams") or set()
    if not ascii_terms and not bigrams and not trigrams:
        return True
    body = str(text or "")
    low = body.lower()
    if any(w in low for w in ascii_terms):
        return True
    if any(tg in body for tg in trigrams):
        return True
    # A single specific bigram (扩展/插件/合集…) is enough; generic ones
    # (浏览/工具/软件…) need a second distinct hit.
    hits = 0
    for bg in bigrams:
        if bg in body:
            if bg not in _GENERIC_BIGRAMS:
                return True
            hits += 1
    return hits >= 2


def _split_note_chunks(notes: str) -> list[str]:
    text = str(notes or "").replace("\r", "\n")
    chunks: list[str] = []
    for block in re.split(r"\n{1,}", text):
        block = block.strip()
        if not block:
            continue
        # Long paragraphs → sentence-ish pieces so cards cite tight snippets.
        if len(block) > 260:
            for piece in re.split(r"(?<=[。！？!?；;])\s*", block):
                piece = piece.strip()
                if piece:
                    chunks.append(piece)
        else:
            chunks.append(block)
    return chunks


# Handoff bundle prefixes we never want as standalone evidence.
_META_PREFIX_RE = re.compile(r"^(为何值得做|来源|链接)[:：]")


def seed_evidences_from_notes(
    notes: str,
    *,
    topic: str = "",
    source: str = "",
    url: str = "",
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Turn fetched article notes into scored-ready seed evidence rows."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in _split_note_chunks(notes):
        if _META_PREFIX_RE.match(chunk):
            continue
        t = clean_snippet_text(chunk)
        if len(t) < 40 or t in seen or looks_like_serp_noise(t):
            continue
        seen.add(t)
        rows.append(
            {
                "text": t[:400],
                "query": "handoff",
                "engine": "seed",
                "role": (topic or "")[:40],
                "url": (url or "")[:200],
                "title": (source or "")[:80],
            }
        )
        if len(rows) >= limit:
            break
    return rows
