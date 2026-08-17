"""Connector registry + prefs (S2)."""

from __future__ import annotations

import pytest


def test_catalog_has_ingest_and_publish():
    from cn_social_agent.content.connectors import catalog_static

    rows = catalog_static()
    ids = {r["id"] for r in rows}
    assert "hotspot_board" in ids
    assert "weixin_publish" in ids
    assert "local_export" in ids
    hotspot = next(r for r in rows if r["id"] == "hotspot_board")
    assert any(c["id"] == "hn" for c in hotspot["children"])


def test_disable_hotspot_source_filters_board():
    from cn_social_agent.content.connectors import (
        enabled_hotspot_sources,
        resolve_hotspot_source_filter,
    )

    prefs = {
        "connectors_enabled": {"hotspot_board": True},
        "hotspot_sources_enabled": {"hn": False, "github": True, "sspai": True},
    }
    allowed = enabled_hotspot_sources(prefs)
    assert "hn" not in allowed
    assert "github" in allowed
    effective, skipped = resolve_hotspot_source_filter("all", prefs)
    assert effective == "subset"
    assert "hn" in skipped
    effective2, _ = resolve_hotspot_source_filter("hn", prefs)
    assert effective2 == "none"


def test_turn_off_hotspot_board():
    from cn_social_agent.content.connectors import enabled_hotspot_sources

    prefs = {"connectors_enabled": {"hotspot_board": False}}
    assert enabled_hotspot_sources(prefs) == []


def test_apply_connector_patch():
    from cn_social_agent.content.connectors import apply_connector_patch

    frag = apply_connector_patch(
        {}, connector_id="web_fetch", enabled=False, hotspot_source_id="v2ex", hotspot_enabled=False
    )
    assert frag["connectors_enabled"]["web_fetch"] is False
    assert frag["hotspot_sources_enabled"]["v2ex"] is False


def test_prefs_normalize_keeps_connectors():
    from cn_social_agent.api.prefs import normalize_prefs

    p = normalize_prefs(
        {
            "connectors_enabled": {"local_export": False},
            "hotspot_sources_enabled": {"devto": False},
        }
    )
    assert p["connectors_enabled"]["local_export"] is False
    assert p["connectors_enabled"]["hotspot_board"] is True
    assert p["hotspot_sources_enabled"]["devto"] is False


@pytest.mark.asyncio
async def test_enrich_catalog_oauth_status():
    from cn_social_agent.content.connectors import enrich_catalog

    rows = await enrich_catalog(
        {"connectors_enabled": {"weixin_publish": True}},
        oauth_status={"weixin": {"ok": True}},
    )
    wx = next(r for r in rows if r["id"] == "weixin_publish")
    assert wx["status"] == "connected"
