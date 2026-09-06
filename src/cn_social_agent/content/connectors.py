"""Content connectors registry — ingest sources + publish endpoints."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.tools.hotspots import SOURCES as HOTSPOT_SOURCES

# Top-level connectors (WorkBuddy Content OS S2)
CONNECTORS: tuple[dict[str, Any], ...] = (
    {
        "id": "hotspot_board",
        "label": "热点看板",
        "direction": "ingest",
        "description": "GitHub / HN / V2EX / 少数派等选题源",
        "kind": "hotspot",
    },
    {
        "id": "web_fetch",
        "label": "网页抓取",
        "direction": "ingest",
        "description": "URL 原文摘录与深采搜索",
        "kind": "tool",
    },
    {
        "id": "github_repo",
        "label": "GitHub 仓库洞察",
        "direction": "ingest",
        "description": "仓库 README / Star / 技术栈摘要",
        "kind": "tool",
    },
    {
        "id": "weixin_publish",
        "label": "微信公众号发布",
        "direction": "publish",
        "description": "知识卡片导出到微信",
        "kind": "oauth",
        "oauth_platform": "weixin",
    },
    {
        "id": "toutiao_publish",
        "label": "头条号发布",
        "direction": "publish",
        "description": "知识卡片导出到头条",
        "kind": "oauth",
        "oauth_platform": "toutiao",
    },
    {
        "id": "local_export",
        "label": "本地导出",
        "direction": "publish",
        "description": "PNG / MP4 下载到本机",
        "kind": "local",
    },
)

_DEFAULT_ENABLED = {c["id"]: True for c in CONNECTORS}
_HOTSPOT_IDS = {s["id"] for s in HOTSPOT_SOURCES}


def default_connector_prefs() -> dict[str, Any]:
    return {
        "connectors_enabled": dict(_DEFAULT_ENABLED),
        "hotspot_sources_enabled": {s["id"]: True for s in HOTSPOT_SOURCES},
    }


def normalize_connector_prefs(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw or {}
    enabled = src.get("connectors_enabled")
    if not isinstance(enabled, dict):
        enabled = {}
    out_en: dict[str, bool] = {}
    for cid in _DEFAULT_ENABLED:
        if cid in enabled:
            out_en[cid] = bool(enabled[cid])
        else:
            out_en[cid] = True
    # User-defined connectors (custom_*) persist their toggle too.
    for cid, val in enabled.items():
        key = str(cid)
        if key not in out_en and key.startswith("custom_"):
            out_en[key] = bool(val)

    hs = src.get("hotspot_sources_enabled")
    if not isinstance(hs, dict):
        hs = {}
    out_hs: dict[str, bool] = {}
    for sid in _HOTSPOT_IDS:
        if sid in hs:
            out_hs[sid] = bool(hs[sid])
        else:
            out_hs[sid] = True
    return {"connectors_enabled": out_en, "hotspot_sources_enabled": out_hs}


def is_connector_enabled(prefs: dict[str, Any] | None, connector_id: str) -> bool:
    norm = normalize_connector_prefs(prefs)
    return bool(norm["connectors_enabled"].get(connector_id, True))


def enabled_hotspot_sources(prefs: dict[str, Any] | None) -> list[str]:
    """Source ids allowed for board scan (empty → none)."""
    if not is_connector_enabled(prefs, "hotspot_board"):
        return []
    norm = normalize_connector_prefs(prefs)
    hs = norm["hotspot_sources_enabled"]
    return [s["id"] for s in HOTSPOT_SOURCES if hs.get(s["id"], True)]


def resolve_hotspot_source_filter(
    requested: str, prefs: dict[str, Any] | None
) -> tuple[str, list[str]]:
    """Map UI/API source param through connector prefs.

    Returns (effective_source_for_scan, skipped_source_ids).
    effective_source is 'all' | single id | 'none' (caller should return empty board).
    """
    req = (requested or "all").strip().lower() or "all"
    allowed = set(enabled_hotspot_sources(prefs))
    all_ids = [s["id"] for s in HOTSPOT_SOURCES]
    skipped = [sid for sid in all_ids if sid not in allowed]

    if not allowed:
        return "none", skipped
    if req == "all":
        if len(allowed) == len(all_ids):
            return "all", []
        # Multi-source subset: caller must scan allowed ids separately
        return "subset", skipped
    if req not in _HOTSPOT_IDS:
        return req, skipped
    if req not in allowed:
        return "none", skipped
    return req, [s for s in skipped if s != req]


def catalog_static() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in CONNECTORS:
        row = {
            "id": c["id"],
            "label": c["label"],
            "direction": c["direction"],
            "description": c["description"],
            "kind": c["kind"],
            "enabled": True,
            "status": "ready",
            "status_label": "可用",
            "children": [],
        }
        if c["id"] == "hotspot_board":
            row["children"] = [
                {
                    "id": s["id"],
                    "label": s["label"],
                    "enabled": True,
                    "parent": "hotspot_board",
                }
                for s in HOTSPOT_SOURCES
            ]
        if c.get("oauth_platform"):
            row["oauth_platform"] = c["oauth_platform"]
        rows.append(row)
    return rows


async def enrich_catalog(
    prefs: dict[str, Any] | None,
    *,
    oauth_status: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Apply prefs + optional OAuth status map {platform: {ok, …}}."""
    norm = normalize_connector_prefs(prefs)
    oauth_status = oauth_status or {}
    rows = catalog_static()
    out: list[dict[str, Any]] = []
    for row in rows:
        cid = row["id"]
        row["enabled"] = bool(norm["connectors_enabled"].get(cid, True))
        if cid == "hotspot_board":
            for ch in row["children"]:
                ch["enabled"] = bool(
                    norm["hotspot_sources_enabled"].get(ch["id"], True)
                )
            if not row["enabled"]:
                row["status"] = "off"
                row["status_label"] = "已关闭"
            elif not any(ch["enabled"] for ch in row["children"]):
                row["status"] = "empty"
                row["status_label"] = "无启用源"
            else:
                n = sum(1 for ch in row["children"] if ch["enabled"])
                row["status"] = "ready"
                row["status_label"] = f"{n} 个源开启"
        elif row.get("kind") == "oauth":
            plat = row.get("oauth_platform") or ""
            st = oauth_status.get(plat) or {}
            connected = bool(st.get("ok") or st.get("connected") or st.get("authorized"))
            if not row["enabled"]:
                row["status"] = "off"
                row["status_label"] = "已关闭"
            elif connected:
                row["status"] = "connected"
                row["status_label"] = "已授权"
            else:
                row["status"] = "need_auth"
                row["status_label"] = "未授权"
        elif not row["enabled"]:
            row["status"] = "off"
            row["status_label"] = "已关闭"
        else:
            row["status"] = "ready"
            row["status_label"] = "可用"
        out.append(row)
    return out


def apply_connector_patch(
    prefs: dict[str, Any],
    *,
    connector_id: str = "",
    enabled: Optional[bool] = None,
    hotspot_source_id: str = "",
    hotspot_enabled: Optional[bool] = None,
) -> dict[str, Any]:
    """Return updated prefs fragment for connectors."""
    norm = normalize_connector_prefs(prefs)
    en = dict(norm["connectors_enabled"])
    hs = dict(norm["hotspot_sources_enabled"])
    cid = (connector_id or "").strip()
    if cid and enabled is not None:
        # Known ids update in place; custom_* ids are admitted here as well.
        en[cid] = bool(enabled)
    sid = (hotspot_source_id or "").strip()
    if sid and sid in hs and hotspot_enabled is not None:
        hs[sid] = bool(hotspot_enabled)
    return {"connectors_enabled": en, "hotspot_sources_enabled": hs}
