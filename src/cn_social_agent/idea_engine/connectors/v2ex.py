from __future__ import annotations

from typing import Any

import aiohttp

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class V2EXConnector(IdeaConnector):
    id = "v2ex"
    name = "V2EX"
    description = "V2EX 热门话题"
    icon = "💬"

    capabilities = {
        "source": True,
        "monitor": True,
        "realtime": False,
    }

    API_BASE = "https://www.v2ex.com/api/v2"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.nodes = config.extra.get("nodes", ["hot", "all"])
        self.token = config.extra.get("token", "")

    async def fetch(self) -> list[RawMaterial]:
        materials = []

        async with aiohttp.ClientSession() as session:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            for node in self.nodes:
                try:
                    node_materials = await self._fetch_node(session, node, headers)
                    materials.extend(node_materials)
                except Exception:
                    continue

        return materials[: self.config.max_items]

    async def _fetch_node(
        self, session: aiohttp.ClientSession, node: str, headers: dict
    ) -> list[RawMaterial]:
        url = f"{self.API_BASE}/nodes/{node}/topics"
        params = {"p": 1}

        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        topics = data.get("data", [])
        materials = []

        for topic in topics:
            title = topic.get("title", "")
            tid = topic.get("id", 0)
            content = topic.get("content", "")
            replies = topic.get("replies", 0)
            created = topic.get("created", 0)

            tags = ["v2ex", node]
            if topic.get("node"):
                tags.append(topic["node"].get("name", ""))

            keywords_lower = [k.lower() for k in self.config.keywords]
            if keywords_lower:
                text = f"{title} {content}".lower()
                if not any(k in text for k in keywords_lower):
                    continue

            materials.append(
                RawMaterial(
                    id=f"v2ex:{tid}",
                    connector_id=self.id,
                    source="v2ex",
                    title=title,
                    url=f"https://www.v2ex.com/t/{tid}",
                    summary=content[:500] if content else None,
                    tags=tags,
                    heat=replies,
                    raw_data={
                        "topic_id": tid,
                        "node": node,
                        "replies": replies,
                        "created": created,
                        "author": topic.get("member", {}).get("username", ""),
                    },
                )
            )

        return materials

    async def fetch_topic(self, topic_id: int) -> dict[str, Any] | None:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.API_BASE}/topics/{topic_id}") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("data")
