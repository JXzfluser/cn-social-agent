#!/usr/bin/env python3
"""Provision the Nexus schema with row-level security enforced at the database.

Run once (or idempotently from CI)::

    PYTHONPATH=src .venv/bin/python scripts/ensure_nexus_schema.py

What it guarantees
------------------
* Four task tables plus a user-profile table, each owned per user via
  ``user_id`` and protected by Postgres RLS (``user_id = auth.uid()``).
* ``FORCE ROW LEVEL SECURITY`` so a missing policy can never silently expose
  rows — if the policy is gone, every row is denied, which is the safe fail.
* ``GRANT`` to the ``authenticated`` role so PostgREST callers may use the
  table; RLS still decides *which* rows.
* A private storage bucket for tenant assets.

This is the migration that turns "isolation by remembering to filter" into
"isolation the database refuses to violate".

Legacy tables (the existing wb_* session/card/… tables) are intentionally NOT
touched here — they keep their app-level filtering. Pass ``--with-legacy`` to
also attach RLS policies to those, but review the impact first: it will start
denying cross-user reads the old code relied on.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from cn_social_agent.core import bind_system
from cn_social_agent.core.admin import AdminGateway, Column, Table
from cn_social_agent.insforge import InsForge


NEXUS_TABLES: list[Table] = [
    Table(
        name="wb_nexus_tasks",
        columns=[
            Column("user_id", "uuid", nullable=False),
            Column("expert_id", "string", nullable=False),
            Column("title", "string", nullable=False),
            Column("brief", "string", nullable=False),
            Column("status", "string", nullable=False, default="'draft'"),
            Column("locale", "string", nullable=False, default="'zh-CN'"),
            Column("attempt", "integer", nullable=False, default="0"),
            Column("meta", "json", nullable=True),
        ],
        rls_enabled=True,
        foreign_keys=[{
            "referenceTable": "auth.users",
            "referenceColumns": [{"sourceColumn": "user_id", "referenceColumn": "id"}],
            "onDelete": "CASCADE",
            "onUpdate": "NO ACTION",
        }],
    ),
    Table(
        name="wb_nexus_steps",
        columns=[
            Column("user_id", "uuid", nullable=False),
            Column("task_id", "string", nullable=False),
            Column("kind", "string", nullable=False),
            Column("message", "string", nullable=True),
            Column("data", "json", nullable=True),
        ],
        rls_enabled=True,
        foreign_keys=[{
            "referenceTable": "auth.users",
            "referenceColumns": [{"sourceColumn": "user_id", "referenceColumn": "id"}],
            "onDelete": "CASCADE",
            "onUpdate": "NO ACTION",
        }],
    ),
    Table(
        name="wb_nexus_artifacts",
        columns=[
            Column("user_id", "uuid", nullable=False),
            Column("task_id", "string", nullable=False),
            Column("kind", "string", nullable=False),
            Column("name", "string", nullable=True),
            Column("content", "string", nullable=True),
            Column("storage_key", "string", nullable=True),
            Column("meta", "json", nullable=True),
        ],
        rls_enabled=True,
        foreign_keys=[{
            "referenceTable": "auth.users",
            "referenceColumns": [{"sourceColumn": "user_id", "referenceColumn": "id"}],
            "onDelete": "CASCADE",
            "onUpdate": "NO ACTION",
        }],
    ),
    Table(
        name="wb_nexus_reviews",
        columns=[
            Column("user_id", "uuid", nullable=False),
            Column("task_id", "string", nullable=False),
            Column("verdict", "string", nullable=False),
            Column("passed", "boolean", nullable=False, default="false"),
            Column("score", "integer", nullable=False, default="0"),
            Column("requires_human", "boolean", nullable=False, default="false"),
            Column("human_decision", "string", nullable=True),
            Column("human_note", "string", nullable=True),
            Column("findings", "json", nullable=True),
        ],
        rls_enabled=True,
        foreign_keys=[{
            "referenceTable": "auth.users",
            "referenceColumns": [{"sourceColumn": "user_id", "referenceColumn": "id"}],
            "onDelete": "CASCADE",
            "onUpdate": "NO ACTION",
        }],
    ),
    Table(
        name="wb_user_profiles",
        columns=[
            Column("user_id", "uuid", nullable=False),
            Column("locale", "string", nullable=False, default="'zh-CN'"),
            Column("display_name", "string", nullable=True),
            Column("settings", "json", nullable=True),
        ],
        rls_enabled=True,
        foreign_keys=[{
            "referenceTable": "auth.users",
            "referenceColumns": [{"sourceColumn": "user_id", "referenceColumn": "id"}],
            "onDelete": "CASCADE",
            "onUpdate": "NO ACTION",
        }],
    ),
]

ASSET_BUCKET = "nexus-assets"

# Existing tables the old workbench relies on. Attaching RLS to them is a
# breaking change for the legacy code path, so it is opt-in only.
LEGACY_TABLES = [
    "wb_sessions", "wb_messages", "wb_skill_bindings", "wb_media_objects",
    "wb_user_prefs", "wb_card_history", "wb_content_projects", "wb_workflows",
    "wb_workflow_runs", "wb_workflow_templates", "wb_workflow_run_logs",
    "wb_workflow_versions", "wb_topic_research_notes", "wb_topic_workflow_records",
    "wb_topic_learning_insights", "wb_topic_hubs", "wb_topic_links", "wb_topic_notes",
]


async def provision(insforge: InsForge, *, with_legacy: bool = False) -> dict[str, list[str]]:
    admin = AdminGateway(insforge._client)
    bind_system("nexus schema provisioning")
    report: dict[str, list[str]] = {"created": [], "rls": [], "policies": [], "buckets": []}

    for table in NEXUS_TABLES:
        created = await admin.create_table(table)
        if created:
            report["created"].append(table.name)
        applied = await admin.ensure_rls(table.name)
        report["rls"].append(table.name)
        report["policies"].extend(applied)

    if with_legacy:
        # Belt-and-braces: add a user_id column where missing and enforce RLS.
        for name in LEGACY_TABLES:
            try:
                await admin.add_column_if_missing(
                    name, Column("user_id", "uuid", nullable=False),
                    default_sql="gen_random_uuid()",
                )
                await admin.ensure_rls(name, public_read=True)
                report["rls"].append(f"(legacy) {name}")
            except Exception as exc:  # noqa: BLE001
                print(f"  ! legacy RLS for {name} skipped: {exc}", file=sys.stderr)

    # Private, user-namespaced asset bucket.
    storage = insforge.storage
    await storage.ensure_bucket(ASSET_BUCKET, public=False)
    report["buckets"].append(ASSET_BUCKET)

    # Verify the RLS actually took effect.
    for table in NEXUS_TABLES:
        try:
            rls = await admin.has_rls(table.name)
            print(f"  RLS {table.name}: {'enabled' if rls else 'MISSING'}")
        except Exception:  # noqa: BLE001
            print(f"  RLS {table.name}: unverifiable")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Nexus schema with RLS")
    parser.add_argument("--with-legacy", action="store_true",
                        help="also attach RLS to the legacy wb_* tables")
    args = parser.parse_args()

    async def _run() -> int:
        insforge = InsForge()
        try:
            await insforge.initialize()
        except Exception as exc:  # noqa: BLE001
            print(f"InsForge unavailable: {exc}", file=sys.stderr)
            return 2
        print("Provisioning Nexus schema (tables + RLS + storage)...")
        report = await provision(insforge, with_legacy=args.with_legacy)
        print("Created tables:", report["created"] or "(none)")
        print("RLS enabled on:", len(set(report["rls"])), "tables")
        print("Policies:", len(report["policies"]))
        print("Buckets:", report["buckets"])
        print("Done.")
        return 0

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
