"""AI canvas organize — pure select / payload / validate / merge helpers."""

from __future__ import annotations

import json
from typing import Any

from cn_social_agent.content.canvas import (
    NODE_KINDS,
    normalize_canvas,
    normalize_edge,
    normalize_node,
)

# Fields the model may rewrite. Anything absent from its answer stays untouched.
EDITABLE_FIELDS: tuple[str, ...] = ("kind", "title", "text", "tags", "color", "url", "done")

SAFE_URL_SCHEMES: tuple[str, ...] = ("http://", "https://")


class OrganizeValidationError(ValueError):
    """Model output is malformed or violates the canvas contract."""


def select_nodes_for_organize(
    canvas: dict[str, Any] | None,
    node_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """Return nodes whose ids appear in node_ids (order preserved, unknowns dropped)."""
    cur = normalize_canvas(canvas)
    wanted = [str(i).strip() for i in (node_ids or []) if str(i or "").strip()]
    if not wanted:
        return []
    by_id = {n["id"]: n for n in cur["nodes"]}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for nid in wanted:
        if nid in seen:
            continue
        node = by_id.get(nid)
        if node:
            out.append(dict(node))
            seen.add(nid)
    return out


def build_organize_payload(
    canvas: dict[str, Any] | None,
    node_ids: list[str] | None,
    *,
    instruction: str = "",
) -> dict[str, Any]:
    """Constrained payload for the model: selected nodes plus their internal edges."""
    cur = normalize_canvas(canvas)
    nodes = select_nodes_for_organize(cur, node_ids)
    known = {n["id"] for n in nodes}
    slim_nodes = [
        {
            "id": n["id"],
            "kind": n["kind"],
            "title": n.get("title") or "",
            "text": n.get("text") or "",
            "tags": list(n.get("tags") or []),
            "color": n.get("color") or "",
            "url": n.get("url") or "",
            "done": bool(n.get("done")),
        }
        for n in nodes
    ]
    slim_edges = [
        {"from": e["from"], "to": e["to"], "label": e.get("label") or ""}
        for e in cur["edges"]
        if e["from"] in known and e["to"] in known
    ]
    return {
        "instruction": str(instruction or "").strip()[:500],
        "nodes": slim_nodes,
        "edges": slim_edges,
        "allowed_kinds": list(NODE_KINDS),
        "editable_fields": list(EDITABLE_FIELDS),
        "rules": [
            "Preserve every node id exactly; do not invent new ids.",
            "Return JSON object with keys nodes and edges only.",
            "Omit a field to leave it unchanged; kinds must be one of allowed_kinds.",
            "edges may only connect ids present in nodes.",
            "url must be empty or start with http:// or https://.",
        ],
    }


def _parse_raw(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise OrganizeValidationError(f"output is not valid JSON: {exc}") from None
        if isinstance(data, dict):
            return data
    raise OrganizeValidationError("organize output must be a JSON object")


def _clean_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    if not url.lower().startswith(SAFE_URL_SCHEMES):
        raise OrganizeValidationError("url must be empty or use http/https")
    return url[:500]


def validate_organize_output(
    raw: Any,
    *,
    allowed_ids: set[str],
) -> dict[str, Any]:
    """Strict validation. Only fields the model actually returned are carried over."""
    data = _parse_raw(raw)
    allowed = {str(i) for i in allowed_ids if str(i or "").strip()}
    if not allowed:
        raise OrganizeValidationError("allowed_ids required")

    nodes_raw = data.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise OrganizeValidationError("nodes required")

    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in nodes_raw:
        if not isinstance(item, dict):
            raise OrganizeValidationError("each node must be an object")
        nid = str(item.get("id") or "").strip()
        if nid not in allowed:
            raise OrganizeValidationError(f"unknown node id: {nid}")
        if nid in seen:
            raise OrganizeValidationError(f"duplicate node id: {nid}")

        node: dict[str, Any] = {"id": nid}
        if "kind" in item:
            kind = str(item.get("kind") or "").strip().lower()
            if kind not in NODE_KINDS:
                raise OrganizeValidationError(f"invalid kind: {kind}")
            node["kind"] = kind
        if "url" in item:
            node["url"] = _clean_url(item.get("url"))

        shaped = normalize_node({**item, "id": nid, "kind": node.get("kind") or "note"})
        for key in ("title", "text", "tags", "color", "done"):
            if key in item:
                node[key] = shaped[key]
        nodes.append(node)
        seen.add(nid)

    missing = allowed - seen
    if missing:
        raise OrganizeValidationError(f"missing node ids: {sorted(missing)}")

    edges_raw = data.get("edges") if isinstance(data.get("edges"), list) else []
    edges: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for item in edges_raw:
        if not isinstance(item, dict):
            raise OrganizeValidationError("each edge must be an object")
        edge = normalize_edge(item, known=allowed)
        if not edge:
            raise OrganizeValidationError("invalid edge endpoints")
        pair = (edge["from"], edge["to"])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edges.append(edge)

    return {"nodes": nodes, "edges": edges}


def merge_organize_result(
    canvas: dict[str, Any] | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Apply returned node fields; replace only edges internal to the selection."""
    cur = normalize_canvas(canvas)
    updates = {n["id"]: n for n in (result.get("nodes") or []) if isinstance(n, dict)}
    touched = set(updates)
    new_nodes: list[dict[str, Any]] = []
    for node in cur["nodes"]:
        upd = updates.get(node["id"])
        if not upd:
            new_nodes.append(node)
            continue
        merged = dict(node)
        for key in EDITABLE_FIELDS:
            if key in upd:
                merged[key] = upd[key]
        new_nodes.append(normalize_node(merged))

    # Cross-selection edges belong to nodes the model never saw as a pair — keep them.
    kept = [
        e
        for e in cur["edges"]
        if not (e["from"] in touched and e["to"] in touched)
    ]
    known = {n["id"] for n in new_nodes}
    for edge in result.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        norm = normalize_edge(edge, known=known)
        if norm and norm["from"] in touched and norm["to"] in touched:
            kept.append(norm)

    return normalize_canvas(
        {
            **cur,
            "nodes": new_nodes,
            "edges": kept,
            "title": cur.get("title") or "",
        },
        project_id=cur.get("project_id") or "",
        board_id=cur.get("board_id") or "",
    )
