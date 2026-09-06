from __future__ import annotations

import re
from typing import Any

import aiohttp

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class SspaiConnector(IdeaConnector):
    id = "sspai"
    name = "少数派"
    description = "少数派热门文章"
    icon = "📱"

    capabilities = {
        "source": True,
        "monitor": True,
        "realtime": False,
    }

    API_BASE = "https://sspai.com/api/v1"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.tags = config.extra.get("tags", [])

    async def fetch(self) -> list[RawMaterial]:
        materials = []

        async with aiohttp.ClientSession() as session:
            try:
                hot_items = await self._fetch_hot(session)
                materials.extend(hot_items)
            except Exception:
                pass

            for tag in self.tags[:3]:
                try:
                    tag_items = await self._fetch_tag(session, tag)
                    materials.extend(tag_items)
                except Exception:
                    continue

        return materials[: self.config.max_items]

    async def _fetch_hot(self, session: aiohttp.ClientSession) -> list[RawMaterial]:
        url = f"{self.API_BASE}/article/tag/page/get"
        params = {"limit": 20, "offset": 0, "tag": "hot"}

        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        items = data.get("data", [])
        materials = []

        for item in items:
            title = item.get("title", "")
            aid = item.get("id", "")
            summary = item.get("summary", "")
            likes = item.get("like_count", 0)
            comments = item.get("comment_count", 0)

            tags = ["sspai", "hot"]
            if item.get("tags"):
                tags.extend([t.get("title", "") for t in item["tags"][:3]])

            heat = likes + comments * 2

            keywords_lower = [k.lower() for k in self.config.keywords]
            if keywords_lower:
                text = f"{title} {summary}".lower()
                if not any(k in text for k in keywords_lower):
                    continue

            materials.append(
                RawMaterial(
                    id=f"sspai:{aid}",
                    connector_id=self.id,
                    source="sspai",
                    title=title,
                    url=f"https://sspai.com/post/{aid}",
                    summary=summary[:500] if summary else None,
                    tags=tags,
                    heat=heat,
                    raw_data={
                        "article_id": aid,
                        "likes": likes,
                        "comments": comments,
                        "author": item.get("author", {}).get("nickname", ""),
                    },
                )
            )

        return materials

    async def _fetch_tag(
        self, session: aiohttp.ClientSession, tag: str
    ) -> list[RawMaterial]:
        url = f"{self.API_BASE}/article/tag/page/get"
        params = {"limit": 10, "offset": 0, "tag": tag}

        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        items = data.get("data", [])
        materials = []

        for item in items:
            title = item.get("title", "")
            aid = item.get("id", "")
            summary = item.get("summary", "")
            likes = item.get("like_count", 0)

            heat = likes
            tags = ["sspai", tag]

            materials.append(
                RawMaterial(
                    id=f"sspai:{aid}",
                    connector_id=self.id,
                    source="sspai",
                    title=title,
                    url=f"https://sspai.com/post/{aid}",
                    summary=summary[:500] if summary else None,
                    tags=tags,
                    heat=heat,
                    raw_data={
                        "article_id": aid,
                        "likes": likes,
                        "tag": tag,
                    },
                )
            )

        return materials
