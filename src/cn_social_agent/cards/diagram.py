"""Diagram type inference and normalization for knowledge cards."""

from __future__ import annotations

import re
from typing import Any

DIAGRAM_TYPES = frozenset({"flow", "cycle", "compare", "stack", "callout", "bullets"})

KIND_DEFAULT = {
    "steps": "flow",
    "compare": "compare",
    "data": "callout",
    "quote": "callout",
    "keypoints": "bullets",
    "concept": "stack",
}


def infer_diagram_type(card_kind: str) -> str:
    return KIND_DEFAULT.get((card_kind or "").lower(), "bullets")


def _node_label(text: str, n: int = 16) -> str:
    s = re.sub(r"^[-•·\s]+", "", str(text or "")).strip()
    s = re.sub(r"^【[^】]*】\s*", "", s)
    s = re.sub(r"[…⋯.]+$", "", s).strip()
    if not s:
        return ""
    head = re.split(r"[，。；;：:、]", s, maxsplit=1)[0].strip() or s
    ident = re.match(r"^([\u4e00-\u9fff]{1,8}[A-Za-z][A-Za-z0-9_+.#-]*)", head)
    if ident and len(ident.group(1)) >= 4:
        return ident.group(1)
    en = re.match(r"^([A-Za-z][A-Za-z0-9_+.#-]{2,})", head)
    if en:
        return en.group(1)
    return head if len(head) <= n else head[:n]


def _looks_truncated(text: str) -> bool:
    s = str(text or "").strip()
    return s.endswith("…") or s.endswith("...") or s.endswith("⋯")


def _nodes_from_points(points: list[Any] | None) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    for p in points or []:
        if len(nodes) >= 5:
            break
        text = re.sub(r"^[-•·\s]+", "", str(p or "")).strip()
        text = re.sub(r"^【[^】]*】\s*", "", text)
        if not text or _looks_truncated(text):
            continue
        label = _node_label(text)
        if not label:
            continue
        note = ""
        if len(text) > len(label):
            rest = text[len(label) :].lstrip("，。；;：:、 ")
            note = rest[:40]
        nodes.append({"label": label, "note": note})
    return nodes


def normalize_diagram(
    raw: Any,
    *,
    card_kind: str,
    flow: list[str] | None = None,
    points: list[Any] | None = None,
    compare_left: str = "",
    compare_right: str = "",
    metric: str = "",
    quote: str = "",
) -> dict[str, Any]:
    d = raw if isinstance(raw, dict) else {}
    t = str(d.get("type") or "").lower()
    if t not in DIAGRAM_TYPES:
        t = infer_diagram_type(card_kind)
    nodes: list[dict[str, str]] = []
    for n in (d.get("nodes") or [])[:5]:
        if isinstance(n, dict) and n.get("label"):
            label = str(n["label"])
            if _looks_truncated(label):
                continue
            nodes.append({"label": _node_label(label), "note": str(n.get("note") or "")[:40]})
        elif isinstance(n, str) and n.strip() and not _looks_truncated(n):
            nodes.append({"label": _node_label(n.strip()), "note": ""})
    if not nodes and flow:
        kept = [str(s).strip() for s in flow[:5] if str(s).strip() and not _looks_truncated(s)]
        nodes = [{"label": _node_label(s), "note": ""} for s in kept if _node_label(s)]
    if not nodes:
        nodes = _nodes_from_points(points)
    if t == "compare" and len(nodes) < 2:
        nodes = [
            {
                "label": _node_label(compare_left or "误区"),
                "note": (compare_left[16:56] if len(compare_left) > 16 else ""),
            },
            {
                "label": _node_label(compare_right or "正解"),
                "note": (compare_right[16:56] if len(compare_right) > 16 else ""),
            },
        ]
    if t == "callout" and not nodes:
        label = _node_label(metric or quote or "要点")
        nodes = [{"label": label, "note": (quote[16:56] if quote and not metric else "")}]
    if len(nodes) < 2 and t in ("flow", "cycle", "stack", "bullets"):
        nodes = nodes + [
            {"label": f"要点{i}", "note": ""} for i in range(len(nodes) + 1, 3)
        ]
    return {"type": t, "nodes": nodes[:5]}
