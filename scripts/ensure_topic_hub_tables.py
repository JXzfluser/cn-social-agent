from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "src")

from cn_social_agent.insforge.client import InsForgeClient
from cn_social_agent.insforge.config import load_config


NOTES_TABLE = "wb_topic_research_notes"
WORKFLOWS_TABLE = "wb_topic_workflow_records"
INSIGHTS_TABLE = "wb_topic_learning_insights"


async def ensure_tables():
    config = load_config()
    client = InsForgeClient(config)
    await client.admin_login()

    notes_sql = f"""
    CREATE TABLE IF NOT EXISTS {NOTES_TABLE} (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        topic_key TEXT NOT NULL,
        content TEXT NOT NULL,
        note_type TEXT DEFAULT 'general',
        source TEXT,
        tags JSONB DEFAULT '[]',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """

    workflows_sql = f"""
    CREATE TABLE IF NOT EXISTS {WORKFLOWS_TABLE} (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        topic_key TEXT NOT NULL,
        workflow_type TEXT DEFAULT 'content_creation',
        method TEXT,
        what_worked TEXT,
        what_didnt_work TEXT,
        duration_minutes INTEGER DEFAULT 0,
        content_type TEXT,
        quality_rating INTEGER DEFAULT 0,
        engagement_data JSONB DEFAULT '{{}}',
        notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """

    insights_sql = f"""
    CREATE TABLE IF NOT EXISTS {INSIGHTS_TABLE} (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        topic_key TEXT NOT NULL,
        insight_type TEXT DEFAULT 'general',
        content TEXT,
        audience_signal TEXT,
        content_angle TEXT,
        confidence REAL DEFAULT 0.5,
        source_data JSONB DEFAULT '{{}}',
        created_at TIMESTAMP DEFAULT NOW()
    );
    """

    for sql in [notes_sql, workflows_sql, insights_sql]:
        try:
            await client.execute(sql)
        except Exception as e:
            print(f"Warning: {e}")

    print("Topic Hub tables ensured.")
    await client.close()


if __name__ == "__main__":
    asyncio.run(ensure_tables())
