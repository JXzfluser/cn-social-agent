"""Knowledge canvas — a free-form node board bound to a Content Project or scratch space."""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

NODE_KINDS: tuple[str, ...] = (
    "note",
    "evidence",
    "hook",
    "outline",
    "question",
    "link",
)

KIND_LABELS: dict[str, str] = {
    "note": "便签",
    "evidence": "证据",
    "hook": "钩子",
    "outline": "结构",
    "question": "待验证",
    "link": "链接",
}

NODE_COLORS: tuple[str, ...] = ("", "yellow", "green", "blue", "pink", "purple", "gray")

MAX_NODES = 200
MAX_EDGES = 300
GRID = 8
DEFAULT_W = 240
DEFAULT_H = 150
COLUMN_GAP = 48
ROW_GAP = 24


def new_node_id() -> str:
    return f"nd_{uuid.uuid4().hex[:12]}"


def new_edge_id() -> str:
    return f"eg_{uuid.uuid4().hex[:10]}"


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _snap(value: Any, fallback: int = 0) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = fallback
    n = max(0, min(12000, n))
    return int(round(n / GRID) * GRID)


def normalize_node(raw: dict[str, Any] | None, *, index: int = 0) -> dict[str, Any]:
    src = dict(raw or {})
    kind = str(src.get("kind") or "note").strip().lower()
    if kind not in NODE_KINDS:
        kind = "note"
    color = str(src.get("color") or "").strip().lower()
    if color not in NODE_COLORS:
        color = ""
    col = index % 4
    row = index // 4
    now = _iso_now()
    return {
        "id": str(src.get("id") or "").strip() or new_node_id(),
        "kind": kind,
        "color": color,
        "done": bool(src.get("done")),
        "title": str(src.get("title") or "")[:120],
        "text": str(src.get("text") or "")[:4000],
        "url": str(src.get("url") or "")[:500],
        "x": _snap(src.get("x"), 40 + col * (DEFAULT_W + 24)),
        "y": _snap(src.get("y"), 40 + row * (DEFAULT_H + 24)),
        "w": max(160, min(560, _snap(src.get("w"), DEFAULT_W) or DEFAULT_W)),
        "h": max(96, min(640, _snap(src.get("h"), DEFAULT_H) or DEFAULT_H)),
        "tags": [str(t).strip()[:24] for t in (src.get("tags") or []) if str(t or "").strip()][:6],
        "pinned": bool(src.get("pinned")),
        "created_at": str(src.get("created_at") or now),
        "updated_at": now,
    }


def normalize_edge(raw: dict[str, Any] | None, *, known: set[str]) -> Optional[dict[str, Any]]:
    src = dict(raw or {})
    a = str(src.get("from") or src.get("source") or "").strip()
    b = str(src.get("to") or src.get("target") or "").strip()
    if not a or not b or a == b or a not in known or b not in known:
        return None
    return {
        "id": str(src.get("id") or "").strip() or new_edge_id(),
        "from": a,
        "to": b,
        "label": str(src.get("label") or "")[:60],
    }


def normalize_canvas(
    raw: dict[str, Any] | None,
    *,
    project_id: str = "",
    board_id: str = "",
) -> dict[str, Any]:
    src = dict(raw or {})
    nodes_raw = src.get("nodes")
    if not isinstance(nodes_raw, list):
        nodes_raw = []
    nodes = [
        normalize_node(n, index=i)
        for i, n in enumerate(nodes_raw[:MAX_NODES])
        if isinstance(n, dict)
    ]
    known = {n["id"] for n in nodes}
    edges_raw = src.get("edges") if isinstance(src.get("edges"), list) else []
    edges: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for item in edges_raw[: MAX_EDGES * 2]:
        if not isinstance(item, dict):
            continue
        edge = normalize_edge(item, known=known)
        if not edge:
            continue
        pair = (edge["from"], edge["to"])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edges.append(edge)
        if len(edges) >= MAX_EDGES:
            break
    pid = str(project_id or src.get("project_id") or "").strip()
    bid = str(board_id or src.get("board_id") or src.get("id") or "").strip()
    return {
        "project_id": pid,
        "board_id": bid,
        "title": str(src.get("title") or "").strip()[:120],
        "nodes": nodes,
        "edges": edges,
        "count": len(nodes),
        "updated_at": _iso_now(),
    }


def _evidence_node(ev: dict[str, Any], index: int) -> dict[str, Any]:
    title = str(ev.get("title") or ev.get("name") or "").strip()
    text = str(ev.get("summary") or ev.get("snippet") or ev.get("text") or "").strip()
    url = str(ev.get("url") or ev.get("link") or "").strip()
    return normalize_node(
        {
            "kind": "evidence",
            "title": title[:120],
            "text": text[:1200],
            "url": url,
            "tags": [str(ev.get("source") or "").strip()[:24]] if ev.get("source") else [],
        },
        index=index,
    )


def seed_nodes_from_project(project: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build starting nodes from a Content Project: topic, notes, evidences, terms."""
    proj = dict(project or {})
    nodes: list[dict[str, Any]] = []
    topic = str(proj.get("short_topic") or proj.get("topic") or "").strip()
    if topic:
        nodes.append(
            normalize_node(
                {
                    "kind": "outline",
                    "title": "选题",
                    "text": str(proj.get("topic") or topic)[:1200],
                    "pinned": True,
                },
                index=len(nodes),
            )
        )
    notes = str(proj.get("research_notes") or "").strip()
    if notes:
        nodes.append(
            normalize_node(
                {"kind": "note", "title": "原文笔记", "text": notes[:2000]},
                index=len(nodes),
            )
        )
    why = str(proj.get("why") or "").strip()
    if why:
        nodes.append(
            normalize_node(
                {"kind": "hook", "title": "为何值得做", "text": why[:800]},
                index=len(nodes),
            )
        )
    pack = proj.get("evidence_pack") if isinstance(proj.get("evidence_pack"), dict) else {}
    for ev in list(pack.get("evidences") or [])[:24]:
        if isinstance(ev, dict):
            nodes.append(_evidence_node(ev, len(nodes)))
    terms = [str(t).strip() for t in (proj.get("search_terms") or []) if str(t or "").strip()]
    if terms:
        nodes.append(
            normalize_node(
                {
                    "kind": "question",
                    "title": "待验证 / 检索词",
                    "text": " · ".join(terms[:8]),
                    "tags": terms[:4],
                },
                index=len(nodes),
            )
        )
    return nodes[:MAX_NODES]


def merge_seed_nodes(
    canvas: dict[str, Any] | None,
    seed: list[dict[str, Any]],
) -> dict[str, Any]:
    """Append seed nodes that are not already on the canvas (by url/title+kind)."""
    cur = normalize_canvas(canvas)
    edges = list(cur.get("edges") or [])
    seen = {
        (n["kind"], (n["url"] or n["title"] or n["text"][:40]).strip())
        for n in cur["nodes"]
    }
    added = 0
    for node in seed:
        key = (node["kind"], (node["url"] or node["title"] or node["text"][:40]).strip())
        if key in seen:
            continue
        placed = normalize_node(node, index=len(cur["nodes"]))
        # keep incoming coordinates only when the caller set them explicitly
        if not node.get("x") and not node.get("y"):
            placed["x"] = _snap(40 + (len(cur["nodes"]) % 4) * (DEFAULT_W + 24))
            placed["y"] = _snap(40 + (len(cur["nodes"]) // 4) * (DEFAULT_H + 24))
        cur["nodes"].append(placed)
        seen.add(key)
        added += 1
        if len(cur["nodes"]) >= MAX_NODES:
            break
    cur["edges"] = edges
    cur["count"] = len(cur["nodes"])
    cur["added"] = added
    return cur


def auto_arrange(canvas: dict[str, Any] | None) -> dict[str, Any]:
    """Lay nodes out in one column per kind, keeping their relative order."""
    cur = normalize_canvas(canvas)
    columns = [k for k in NODE_KINDS if any(n["kind"] == k for n in cur["nodes"])]
    tops: dict[str, int] = {k: 40 for k in columns}
    left_of = {k: 40 + i * (DEFAULT_W + COLUMN_GAP) for i, k in enumerate(columns)}
    for node in cur["nodes"]:
        kind = node["kind"]
        node["w"] = DEFAULT_W
        node["x"] = _snap(left_of.get(kind, 40))
        node["y"] = _snap(tops.get(kind, 40))
        tops[kind] = tops.get(kind, 40) + node["h"] + ROW_GAP
    return cur


def canvas_to_markdown(canvas: dict[str, Any] | None, *, title: str = "") -> str:
    """Export the board as a readable outline (kind sections + relations)."""
    cur = normalize_canvas(canvas)
    head = (title or cur["title"] or "知识画布").strip()
    lines: list[str] = [f"# {head}", ""]
    for kind in NODE_KINDS:
        group = [n for n in cur["nodes"] if n["kind"] == kind]
        if not group:
            continue
        lines.append(f"## {KIND_LABELS.get(kind, kind)}")
        for node in group:
            mark = "x" if node["done"] else " "
            heading = node["title"] or (node["text"].strip().splitlines() or ["未命名"])[0][:40]
            lines.append(f"- [{mark}] **{heading}**")
            body = node["text"].strip()
            if body and body != heading:
                for row in body.splitlines():
                    lines.append(f"  {row}".rstrip())
            if node["url"]:
                lines.append(f"  <{node['url']}>")
            if node["tags"]:
                lines.append("  " + " ".join(f"`{t}`" for t in node["tags"]))
        lines.append("")
    if cur["edges"]:
        by_id = {n["id"]: n for n in cur["nodes"]}

        def _name(nid: str) -> str:
            node = by_id.get(nid) or {}
            return str(node.get("title") or node.get("text") or nid)[:40]

        lines.append("## 关联")
        for edge in cur["edges"]:
            arrow = f"- {_name(edge['from'])} → {_name(edge['to'])}"
            if edge["label"]:
                arrow += f"（{edge['label']}）"
            lines.append(arrow)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def canvas_to_handoff(
    canvas: dict[str, Any] | None,
    node_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Turn selected nodes into a workshop handoff payload (notes + terms + urls)."""
    cur = normalize_canvas(canvas)
    wanted = {str(i) for i in (node_ids or []) if str(i or "").strip()}
    nodes = [n for n in cur["nodes"] if not wanted or n["id"] in wanted]

    lines: list[str] = []
    urls: list[str] = []
    terms: list[str] = []
    topic = ""
    for n in nodes:
        label = KIND_LABELS.get(n["kind"], n["kind"])
        head = n["title"] or label
        if n["kind"] == "outline" and not topic:
            topic = (n["title"] == "选题" and n["text"].strip()) or n["text"].strip()
        body = n["text"].strip()
        piece = f"【{label}】{head}"
        if body and body != head:
            piece += f"：{body}"
        if n["url"]:
            piece += f"（{n['url']}）"
            urls.append(n["url"])
        lines.append(piece)
        for t in n["tags"]:
            if t and t not in terms:
                terms.append(t)

    picked = {n["id"]: n for n in nodes}
    relations = [
        f"【关联】{(picked[e['from']]['title'] or picked[e['from']]['text'])[:30]}"
        f" → {(picked[e['to']]['title'] or picked[e['to']]['text'])[:30]}"
        + (f"（{e['label']}）" if e["label"] else "")
        for e in cur["edges"]
        if e["from"] in picked and e["to"] in picked
    ]
    lines.extend(relations)

    notes = "\n".join(lines)[:8000]
    return {
        "topic": (topic or "").strip()[:200],
        "research_notes": notes,
        "search_terms": terms[:8],
        "urls": urls[:20],
        "node_count": len(nodes),
    }


def canvas_stats(canvas: dict[str, Any] | None) -> dict[str, Any]:
    cur = normalize_canvas(canvas)
    by_kind: dict[str, int] = {}
    for n in cur["nodes"]:
        by_kind[n["kind"]] = by_kind.get(n["kind"], 0) + 1
    return {
        "count": cur["count"],
        "edges": len(cur["edges"]),
        "done": sum(1 for n in cur["nodes"] if n["done"]),
        "by_kind": by_kind,
        "has_evidence": by_kind.get("evidence", 0) > 0,
    }
