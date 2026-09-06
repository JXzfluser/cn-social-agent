"""Create Idea Engine tables in InsForge."""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "src")

from cn_social_agent.insforge.db import get_client


MATERIALS_TABLE = "wb_idea_materials"
CARDS_TABLE = "wb_idea_cards"
CONNECTORS_TABLE = "wb_idea_connectors"
FRAGMENTS_TABLE = "wb_idea_fragments"


async def ensure_tables():
    client = await get_client()

    materials_sql = f"""
    CREATE TABLE IF NOT EXISTS {MATERIALS_TABLE} (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        connector_id TEXT NOT NULL,
        source TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT,
        summary TEXT,
        tags JSONB DEFAULT '[]',
        heat INTEGER DEFAULT 0,
        raw_data JSONB DEFAULT '{{}}',
        processed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """

    cards_sql = f"""
    CREATE TABLE IF NOT EXISTS {CARDS_TABLE} (
        id TEXT PRIMARY KEY,
        material_id TEXT REFERENCES {MATERIALS_TABLE}(id),
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        hook TEXT,
        angles JSONB DEFAULT '[]',
        heat_score INTEGER DEFAULT 0,
        difficulty_score INTEGER DEFAULT 0,
        time_window TEXT,
        status TEXT DEFAULT 'pending',
        project_id TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        selected_at TIMESTAMP,
        rejected_at TIMESTAMP
    );
    """

    connectors_sql = f"""
    CREATE TABLE IF NOT EXISTS {CONNECTORS_TABLE} (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        connector_id TEXT NOT NULL,
        config JSONB DEFAULT '{{}}',
        enabled BOOLEAN DEFAULT TRUE,
        last_sync_at TIMESTAMP,
        sync_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, connector_id)
    );
    """

    fragments_sql = f"""
    CREATE TABLE IF NOT EXISTS {FRAGMENTS_TABLE} (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        content TEXT NOT NULL,
        fragment_type TEXT DEFAULT 'text',
        auto_tags JSONB DEFAULT '[]',
        related_material_id TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """

    for sql in [materials_sql, cards_sql, connectors_sql, fragments_sql]:
        try:
            await client.execute(sql)
        except Exception as e:
            print(f"Warning: {e}")

    # Columns added after the initial schema shipped
    alter_sqls = [
        f"ALTER TABLE {CARDS_TABLE} ADD COLUMN IF NOT EXISTS content_type TEXT DEFAULT 'technical';",
        f"ALTER TABLE {CARDS_TABLE} ADD COLUMN IF NOT EXISTS feedback TEXT;",
    ]
    for sql in alter_sqls:
        try:
            await client.execute(sql)
        except Exception as e:
            print(f"Warning: {e}")

    print("Idea Engine tables ensured.")


if __name__ == "__main__":
    asyncio.run(ensure_tables())
