from __future__ import annotations

from typing import Any

import aiohttp

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class HackerNewsConnector(IdeaConnector):
    id = "hackernews"
    name = "Hacker News"
    description = "Hacker News 热门文章"
    icon = "🟠"

    capabilities = {
        "source": True,
        "monitor": True,
        "realtime": True,
    }

    API_BASE = "https://hacker-news.firebaseio.com/v0"

    async def fetch(self) -> list[RawMaterial]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.API_BASE}/topstories.json") as resp:
                if resp.status != 200:
                    raise Exception(f"HN API returned {resp.status}")
                story_ids = await resp.json()

            story_ids = story_ids[: self.config.max_items]

            materials = []
            for sid in story_ids:
                async with session.get(f"{self.API_BASE}/item/{sid}.json") as resp:
                    if resp.status != 200:
                        continue
                    story = await resp.json()

                if not story or story.get("type") != "story":
                    continue

                title = story.get("title", "")
                url = story.get("url", f"https://news.ycombinator.com/item?id={sid}")
                score = story.get("score", 0)
                comments = story.get("descendants", 0)

                tags = ["hackernews"]
                if story.get("category"):
                    tags.append(story["category"].lower())

                keywords_lower = [k.lower() for k in self.config.keywords]
                if keywords_lower:
                    text = f"{title}".lower()
                    if not any(k in text for k in keywords_lower):
                        continue

                materials.append(
                    RawMaterial(
                        id=f"hn:{sid}",
                        connector_id=self.id,
                        source="hackernews",
                        title=title,
                        url=url,
                        summary=story.get("text", "")[:500] if story.get("text") else None,
                        tags=tags,
                        heat=score,
                        raw_data={
                            "hn_id": sid,
                            "score": score,
                            "comments": comments,
                            "by": story.get("by", ""),
                            "time": story.get("time", 0),
                        },
                    )
                )

            return materials

    async def fetch_item(self, item_id: int) -> dict[str, Any] | None:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.API_BASE}/item/{item_id}.json") as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
