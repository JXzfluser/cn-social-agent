#!/usr/bin/env python3
"""Ensure InsForge workbench tables exist (via Tables API)."""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

API = os.getenv("INSFORGE_API_URL", "http://localhost:7130")
ADMIN_USER = os.getenv("INSFORGE_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("INSFORGE_ADMIN_PASSWORD", "change-this-password")

TABLES = {
    "wb_sessions": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {
            "columnName": "title",
            "type": "string",
            "isNullable": False,
            "isUnique": False,
            "defaultValue": "New chat",
        },
        {
            "columnName": "system_prompt",
            "type": "string",
            "isNullable": False,
            "isUnique": False,
            "defaultValue": "",
        },
        {
            "columnName": "model",
            "type": "string",
            "isNullable": False,
            "isUnique": False,
            "defaultValue": "",
        },
        {
            "columnName": "agent_state",
            "type": "json",
            "isNullable": True,
            "isUnique": False,
        },
    ],
    "wb_messages": [
        {"columnName": "session_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "role", "type": "string", "isNullable": False, "isUnique": False},
        {
            "columnName": "content",
            "type": "string",
            "isNullable": False,
            "isUnique": False,
            "defaultValue": "",
        },
        {"columnName": "tool_calls", "type": "json", "isNullable": True, "isUnique": False},
    ],
    "wb_skill_bindings": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "skill_id", "type": "string", "isNullable": False, "isUnique": False},
        {
            "columnName": "enabled",
            "type": "boolean",
            "isNullable": False,
            "isUnique": False,
            "defaultValue": "true",
        },
    ],
    "wb_media_objects": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "storage_path", "type": "string", "isNullable": False, "isUnique": False},
        {
            "columnName": "mime",
            "type": "string",
            "isNullable": False,
            "isUnique": False,
            "defaultValue": "application/octet-stream",
        },
    ],
    "wb_user_prefs": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": True},
        {
            "columnName": "default_audience",
            "type": "string",
            "isNullable": True,
            "isUnique": False,
            "defaultValue": "",
        },
        {
            "columnName": "default_voice",
            "type": "string",
            "isNullable": True,
            "isUnique": False,
            "defaultValue": "zh-CN-XiaoxiaoNeural",
        },
        {
            "columnName": "default_content_angle",
            "type": "string",
            "isNullable": True,
            "isUnique": False,
            "defaultValue": "intro",
        },
        {
            "columnName": "default_platform",
            "type": "string",
            "isNullable": True,
            "isUnique": False,
            "defaultValue": "抖音",
        },
        {
            "columnName": "recent_topics",
            "type": "json",
            "isNullable": True,
            "isUnique": False,
        },
        {
            "columnName": "llm_mode",
            "type": "string",
            "isNullable": True,
            "isUnique": False,
            "defaultValue": "",
        },
        {
            "columnName": "llm_model",
            "type": "string",
            "isNullable": True,
            "isUnique": False,
            "defaultValue": "",
        },
    ],
    "wb_card_history": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "email", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "owner_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "card_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "edition", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "category", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "mode", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "title", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "payload", "type": "json", "isNullable": True, "isUnique": False},
    ],
    "wb_content_projects": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "email", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "owner_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "project_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "topic", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "short_topic", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "category", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "status", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "payload", "type": "json", "isNullable": True, "isUnique": False},
    ],
    "wb_workflows": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "name", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "description", "type": "string", "isNullable": True, "isUnique": False, "defaultValue": ""},
        {"columnName": "nodes", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "[]"},
        {"columnName": "edges", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "[]"},
        {"columnName": "trigger_config", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "{}"},
        {"columnName": "enabled", "type": "boolean", "isNullable": False, "isUnique": False, "defaultValue": "true"},
    ],
    "wb_workflow_runs": [
        {"columnName": "workflow_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "status", "type": "string", "isNullable": False, "isUnique": False, "defaultValue": "pending"},
        {"columnName": "trigger_type", "type": "string", "isNullable": False, "isUnique": False, "defaultValue": "manual"},
        {"columnName": "node_states", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "{}"},
        {"columnName": "context", "type": "json", "isNullable": True, "isUnique": False, "defaultValue": "{}"},
        {"columnName": "error", "type": "string", "isNullable": True, "isUnique": False},
    ],
    "wb_workflow_templates": [
        {"columnName": "name", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "description", "type": "string", "isNullable": True, "isUnique": False, "defaultValue": ""},
        {"columnName": "category", "type": "string", "isNullable": False, "isUnique": False, "defaultValue": "content"},
        {"columnName": "nodes", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "[]"},
        {"columnName": "edges", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "[]"},
        {"columnName": "thumbnail", "type": "string", "isNullable": True, "isUnique": False},
    ],
    "wb_workflow_run_logs": [
        {"columnName": "run_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "node_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "level", "type": "string", "isNullable": False, "isUnique": False, "defaultValue": "info"},
        {"columnName": "message", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "data", "type": "json", "isNullable": True, "isUnique": False},
    ],
    "wb_workflow_versions": [
        {"columnName": "workflow_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "version", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "nodes", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "[]"},
        {"columnName": "edges", "type": "json", "isNullable": False, "isUnique": False, "defaultValue": "[]"},
        {"columnName": "name", "type": "string", "isNullable": True, "isUnique": False},
    ],
    "wb_topic_research_notes": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "topic_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "content", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "note_type", "type": "string", "isNullable": True, "isUnique": False, "defaultValue": "general"},
        {"columnName": "source", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "tags", "type": "json", "isNullable": True, "isUnique": False, "defaultValue": "[]"},
    ],
    "wb_topic_workflow_records": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "topic_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "workflow_type", "type": "string", "isNullable": True, "isUnique": False, "defaultValue": "content_creation"},
        {"columnName": "method", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "what_worked", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "what_didnt_work", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "duration_minutes", "type": "integer", "isNullable": True, "isUnique": False, "defaultValue": "0"},
        {"columnName": "content_type", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "quality_rating", "type": "integer", "isNullable": True, "isUnique": False, "defaultValue": "0"},
        {"columnName": "engagement_data", "type": "json", "isNullable": True, "isUnique": False, "defaultValue": "{}"},
        {"columnName": "notes", "type": "string", "isNullable": True, "isUnique": False},
    ],
    "wb_topic_learning_insights": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "topic_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "insight_type", "type": "string", "isNullable": True, "isUnique": False, "defaultValue": "general"},
        {"columnName": "content", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "audience_signal", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "content_angle", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "confidence", "type": "float", "isNullable": True, "isUnique": False, "defaultValue": "0.5"},
        {"columnName": "source_data", "type": "json", "isNullable": True, "isUnique": False, "defaultValue": "{}"},
    ],
    "wb_topic_hubs": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "topic_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "topic", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "summary", "type": "string", "isNullable": True, "isUnique": False},
        {"columnName": "linked_topics", "type": "json", "isNullable": True, "isUnique": False, "defaultValue": "[]"},
    ],
    "wb_topic_links": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "source_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "target_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "link_type", "type": "string", "isNullable": True, "isUnique": False, "defaultValue": "related"},
    ],
    "wb_topic_notes": [
        {"columnName": "user_id", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "topic_key", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "content", "type": "string", "isNullable": False, "isUnique": False},
        {"columnName": "source_type", "type": "string", "isNullable": True, "isUnique": False, "defaultValue": "manual"},
        {"columnName": "tags", "type": "json", "isNullable": True, "isUnique": False, "defaultValue": "[]"},
        {"columnName": "linked_notes", "type": "json", "isNullable": True, "isUnique": False, "defaultValue": "[]"},
    ],
}


async def main() -> int:
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        login = await client.post(
            f"{API}/api/auth/admin/sessions",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        login.raise_for_status()
        token = login.json().get("accessToken") or login.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}

        listed = await client.get(f"{API}/api/database/tables", headers=headers)
        listed.raise_for_status()
        existing = set(listed.json())
        print("existing tables:", len(existing))

        for name, columns in TABLES.items():
            if name not in existing:
                resp = await client.post(
                    f"{API}/api/database/tables",
                    headers=headers,
                    json={"tableName": name, "rlsEnabled": False, "columns": columns},
                )
                if resp.status_code in (200, 201):
                    print(f"CREATED {name}")
                else:
                    print(f"FAIL {name}: {resp.status_code} {resp.text}")
                    return 1
                continue

            # Table exists — add any missing columns via schema PATCH
            meta = await client.get(
                f"{API}/api/database/tables/{name}/schema", headers=headers
            )
            have: set[str] = set()
            if meta.status_code == 200:
                body = meta.json()
                cols = body.get("columns") or []
                if isinstance(cols, list):
                    for c in cols:
                        if isinstance(c, dict):
                            cn = c.get("columnName") or c.get("column_name") or c.get("name")
                            if cn:
                                have.add(str(cn))
            missing = [c for c in columns if c["columnName"] not in have]
            if not missing:
                print(f"OK  {name}")
                continue
            patch = await client.patch(
                f"{API}/api/database/tables/{name}/schema",
                headers=headers,
                json={"addColumns": missing},
            )
            if patch.status_code in (200, 201):
                print(f"ALTER {name}: +{[c['columnName'] for c in missing]}")
            else:
                print(f"FAIL alter {name}: {patch.status_code} {patch.text}")
                return 1

    print("\nIf PostgREST returns 404 on INSERT for new tables, restart it:")
    print("  docker restart pgrst")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
