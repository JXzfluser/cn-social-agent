from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import aiohttp

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class PainPointConnector(IdeaConnector):
    id = "pain_point"
    name = "用户痛点"
    description = "从问答社区挖掘用户需求"
    icon = "🔥"

    capabilities = {
        "source": True,
        "monitor": True,
        "realtime": False,
    }

    SOURCES = {
        "segmentfault": {
            "name": "SegmentFault",
            "api": "https://segmentfault.com/api/search/search",
            "url_template": "https://segmentfault.com/q/{id}",
        },
        "juejin": {
            "name": "掘金",
            "api": "https://api.juejin.cn/search_api/v1/search",
            "url_template": "https://juejin.cn/post/{id}",
        },
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.keywords = config.keywords
        self.platforms = config.extra.get("platforms", ["segmentfault", "juejin"])

    async def fetch(self) -> list[RawMaterial]:
        materials = []

        async with aiohttp.ClientSession() as session:
            for platform in self.platforms:
                for keyword in self.keywords[:5]:
                    try:
                        items = await self._fetch_platform(session, platform, keyword)
                        materials.extend(items)
                    except Exception:
                        continue

        return materials[: self.config.max_items]

    async def _fetch_platform(
        self, session: aiohttp.ClientSession, platform: str, keyword: str
    ) -> list[RawMaterial]:
        if platform == "segmentfault":
            return await self._fetch_segmentfault(session, keyword)
        elif platform == "juejin":
            return await self._fetch_juejin(session, keyword)
        return []

    async def _fetch_segmentfault(
        self, session: aiohttp.ClientSession, keyword: str
    ) -> list[RawMaterial]:
        url = "https://segmentfault.com/api/search/search"
        params = {"q": keyword, "type": "question", "page": 1}

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": "https://segmentfault.com/",
        }

        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        items = data.get("data", {}).get("list", [])
        materials = []

        for item in items:
            qid = item.get("id", "")
            title = item.get("title", "")
            excerpt = item.get("excerpt", "")
            votes = item.get("votes", 0)
            answers = item.get("answers", 0)

            clean_title = re.sub(r"<[^>]+>", "", title)
            clean_excerpt = re.sub(r"<[^>]+>", "", excerpt)

            heat = votes + answers * 3
            tags = ["pain_point", "segmentfault"]
            if item.get("tags"):
                tags.extend([t.get("name", "") for t in item["tags"][:3]])

            materials.append(
                RawMaterial(
                    id=f"sf:{qid}",
                    connector_id=self.id,
                    source="segmentfault",
                    title=clean_title,
                    url=f"https://segmentfault.com/q/{qid}",
                    summary=clean_excerpt[:500] if clean_excerpt else None,
                    tags=tags,
                    heat=heat,
                    raw_data={
                        "question_id": qid,
                        "votes": votes,
                        "answers": answers,
                        "keyword": keyword,
                        "platform": "segmentfault",
                    },
                )
            )

        return materials

    async def _fetch_juejin(
        self, session: aiohttp.ClientSession, keyword: str
    ) -> list[RawMaterial]:
        url = "https://api.juejin.cn/search_api/v1/search"
        payload = {
            "key_word": keyword,
            "search_type": 2,
            "limit": 10,
            "cursor": "0",
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        }

        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        items = data.get("data", [])
        materials = []

        for item in items:
            result = item.get("result_model", {})
            aid = result.get("article_id", "")
            title = result.get("article_info", {}).get("title", "")
            content = result.get("article_info", not {}).get("brief_content", "")

            clean_title = re.sub(r"<[^>]+>", "", title)
            clean_content = re.sub(r"<[^>]+>", "", content)

            heat = result.get("article_info", {}).get("digg_count", 0)
            tags = ["pain_point", "juejin"]

            materials.append(
                RawMaterial(
                    id=f"juejin:{aid}",
                    connector_id=self.id,
                    source="juejin",
                    title=clean_title,
                    url=f"https://juejin.cn/post/{aid}",
                    summary=clean_content[:500] if clean_content else None,
                    tags=tags,
                    heat=heat,
                    raw_data={
                        "article_id": aid,
                        "keyword": keyword,
                        "platform": "juejin",
                    },
                )
            )

        return materials
