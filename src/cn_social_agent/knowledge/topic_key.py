"""Canonical topic keys for cross-workshop asset grouping."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

# Noise wrappers often pasted from titles / cover hooks
_STRIP_PREFIX = re.compile(
    r"^(关于|浅谈|一文读懂|快速了解|彻底搞懂|如何|怎样|聊聊|再说说)[:：\s]*",
    re.I,
)
_STRIP_SUFFIX = re.compile(
    r"[:：\s]*(入门|指南|教程|完全指南|完全解析|深度解析|全攻略|是什么|"
    r"框架|工具|平台|库|引擎|系统|方案|能力图谱)[:：\s]*$",
    re.I,
)
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[\"'`「」『』【】\[\]()（）{}<>《》·•|｜/\\]+")


def display_topic(raw: str) -> str:
    """Human-facing topic label (light cleanup, keep CJK casing)."""
    s = unicodedata.normalize("NFKC", (raw or "").strip())
    s = _WS.sub(" ", s)
    return s[:80]


def topic_key(raw: str) -> str:
    """Stable key for grouping. Empty string if nothing usable."""
    s = display_topic(raw)
    if not s:
        return ""
    s = _STRIP_PREFIX.sub("", s)
    s = _STRIP_SUFFIX.sub("", s)
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip().lower()
    # Drop pure punctuation leftovers
    s = re.sub(r"^[\W_]+|[\W_]+$", "", s, flags=re.UNICODE)
    return s[:64]


def topics_from_card_record(row: dict[str, Any]) -> list[str]:
    """Collect candidate topic strings from a card history record."""
    out: list[str] = []
    roles = row.get("roles")
    if isinstance(roles, list):
        out.extend(str(x) for x in roles if str(x or "").strip())
    elif isinstance(roles, str) and roles.strip():
        out.append(roles)
    knowledge = row.get("knowledge")
    if isinstance(knowledge, list):
        for k in knowledge:
            if isinstance(k, dict):
                t = str(k.get("topicTitle") or k.get("topic") or "").strip()
                if t:
                    out.append(t)
    cover = row.get("cover") if isinstance(row.get("cover"), dict) else {}
    for key in ("title", "subtitle", "topic"):
        t = str(cover.get(key) or "").strip()
        if t:
            out.append(t)
    title = str(row.get("title") or "").strip()
    if title:
        out.append(title)
    return out


def best_topic_label(candidates: Iterable[str]) -> str:
    """Pick the shortest non-empty display label among candidates."""
    labels = [display_topic(c) for c in candidates if display_topic(c)]
    if not labels:
        return ""
    labels.sort(key=lambda x: (len(x), x))
    return labels[0]


def primary_topic_key(candidates: Iterable[str]) -> str:
    for c in candidates:
        k = topic_key(c)
        if k:
            return k
    return ""
