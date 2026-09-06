from __future__ import annotations

from typing import Any

import aiohttp

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class ZhihuConnector(IdeaConnector):
    id = "zhihu"
    name = "知乎热榜"
    description = "知乎热门话题"
    icon = "🔵"

    capabilities = {
        "source": True,
        "monitor": True,
        "realtime": True,
    }

    API_URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.cookie = config.extra.get("cookie", "")

    async def fetch(self) -> list[RawMaterial]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.zhihu.com/hot",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        async with aiohttp.ClientSession() as session:
            async with session.get(self.API_URL, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        items = data.get("data", [])
        materials = []

        for item in items:
            target = item.get("target", {})
            title = target.get("title", "")
            qid = target.get("id", "")
            excerpt = target.get("excerpt", "")
            detail_text = item.get("detail_text", "")

            heat = 0
            if detail_text:
                try:
                    heat = int("".join(filter(str.isdigit, detail_text.split(" ")[0])))
                except (ValueError, IndexError):
                    heat = 0

            heat = heat or target.get("follower_count", 0)

            tags = ["zhihu", "hot"]
            if target.get("topics"):
                tags.extend([t.get("name", "") for t in target["topics"][:3]])

            keywords_lower = [k.lower() for k in self.config.keywords]
            if keywords_lower:
                text = f"{title} {excerpt}".lower()
                if not any(k in text for k in keywords_lower):
                    continue

            materials.append(
                RawMaterial(
                    id=f"zhihu:{qid}",
                    connector_id=self.id,
                    source="zhihu",
                    title=title,
                    url=f"https://www.zhihu.com/question/{qid}",
                    summary=excerpt[:500] if excerpt else None,
                    tags=tags,
                    heat=heat,
                    raw_data={
                        "question_id": qid,
                        "heat_text": detail_text,
                        "follower_count": target.get("follower_count", 0),
                        "answer_count": target.get("answer_count", 0),
                    },
                )
            )

        return materials[: self.config.max_items]
