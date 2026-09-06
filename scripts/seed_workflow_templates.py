from __future__ import annotations

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cn_social_agent.insforge.client import InsForgeClient
from cn_social_agent.insforge.db import InsForgeDB

TEMPLATES = [
    {
        "id": str(uuid.uuid4()),
        "name": "热点扫描+生成",
        "description": "自动扫描热点 → LLM 生成内容 → 保存草稿",
        "category": "content",
        "nodes": [
            {"id": "n1", "type": "trigger.manual", "x": 100, "y": 200, "label": "手动触发", "config": {}},
            {"id": "n2", "type": "action.hotspot_scan", "x": 300, "y": 200, "label": "扫描热点", "config": {"source": "all", "limit": 5}},
            {"id": "n3", "type": "action.llm_generate", "x": 500, "y": 200, "label": "生成内容", "config": {"prompt": "基于以下热点生成口播文案：\n{{n2.hotspots}}"}},
            {"id": "n4", "type": "output.save_project", "x": 700, "y": 200, "label": "保存草稿", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "全流程流水线",
        "description": "热点 → 生成 → 分镜 → 渲染 → 发布",
        "category": "content",
        "nodes": [
            {"id": "n1", "type": "trigger.manual", "x": 100, "y": 200, "label": "开始", "config": {}},
            {"id": "n2", "type": "action.hotspot_scan", "x": 250, "y": 200, "label": "扫描热点", "config": {"source": "all", "limit": 3}},
            {"id": "n3", "type": "action.llm_generate", "x": 400, "y": 200, "label": "生成文案", "config": {"prompt": "为以下热点生成口播文案：\n{{n2.hotspots}}"}},
            {"id": "n4", "type": "action.storyboard", "x": 550, "y": 200, "label": "分镜脚本", "config": {"duration": 15}},
            {"id": "n5", "type": "action.video_render", "x": 700, "y": 200, "label": "渲染视频", "config": {"quality": "720p"}},
            {"id": "n6", "type": "control.condition", "x": 850, "y": 200, "label": "检查结果", "config": {"expression": "n5.status == 'done'"}},
            {"id": "n7", "type": "publish.weixin", "x": 1000, "y": 150, "label": "发布微信", "config": {}},
            {"id": "n8", "type": "publish.toutiao", "x": 1000, "y": 250, "label": "发布头条", "config": {}},
            {"id": "n9", "type": "output.save_project", "x": 1150, "y": 200, "label": "保存项目", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
            {"id": "e5", "source": "n5", "target": "n6"},
            {"id": "e6", "source": "n6", "target": "n7"},
            {"id": "e7", "source": "n6", "target": "n8"},
            {"id": "e8", "source": "n7", "target": "n9"},
            {"id": "e9", "source": "n8", "target": "n9"},
        ],
    },
    {
        "id": str(uuid.uuid4()),
        "name": "定时监控",
        "description": "定时扫描热点 → 有新内容时通知",
        "category": "automation",
        "nodes": [
            {"id": "n1", "type": "trigger.schedule", "x": 100, "y": 200, "label": "每小时", "config": {"cron": "0 * * * *"}},
            {"id": "n2", "type": "action.hotspot_scan", "x": 300, "y": 200, "label": "扫描热点", "config": {"source": "all", "limit": 10}},
            {"id": "n3", "type": "control.condition", "x": 500, "y": 200, "label": "有新热点?", "config": {"expression": "n2.count > 0"}},
            {"id": "n4", "type": "output.notify", "x": 700, "y": 150, "label": "发送通知", "config": {"channel": "default"}},
            {"id": "n5", "type": "control.stop", "x": 700, "y": 300, "label": "跳过", "config": {"reason": "no new hotspots"}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n3", "target": "n5"},
        ],
    },
]


async def seed():
    client = InsForgeClient()
    db = InsForgeDB(client)
    print("Seeding workflow templates...")

    for tpl in TEMPLATES:
        existing = await db.query("wb_workflow_templates", filters={"id": f"eq.{tpl['id']}"}, limit=1)
        if existing:
            print(f"  [skip] {tpl['name']} (already exists)")
            continue

        await db.create("wb_workflow_templates", {
            "id": tpl["id"],
            "name": tpl["name"],
            "description": tpl["description"],
            "category": tpl["category"],
            "nodes": tpl["nodes"],
            "edges": tpl["edges"],
            "thumbnail": None,
        })
        print(f"  [created] {tpl['name']}")

    print("Done!")


if __name__ == "__main__":
    asyncio.run(seed())
