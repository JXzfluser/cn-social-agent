from __future__ import annotations

import re
from typing import Any

import aiohttp

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class GitHubTrendingConnector(IdeaConnector):
    id = "github_trending"
    name = "GitHub Trending"
    description = "GitHub 热门项目"
    icon = "⭐"

    capabilities = {
        "source": True,
        "monitor": True,
        "realtime": False,
    }

    BASE_URL = "https://github.com/trending"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.language = config.extra.get("language", "")
        self.since = config.extra.get("since", "daily")

    async def fetch(self) -> list[RawMaterial]:
        url = self.BASE_URL
        if self.language:
            url += f"/{self.language}"
        url += f"?since={self.since}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"GitHub returned {resp.status}")
                html = await resp.text()

        return self._parse_trending(html)

    def _parse_trending(self, html: str) -> list[RawMaterial]:
        materials = []
        repo_pattern = re.compile(
            r'<h2 class="h3 lh-condensed">.*?<a href="/([^"]+)"', re.DOTALL
        )
        desc_pattern = re.compile(r'<p class="col-9[^"]*">\s*(.*?)\s*</p>', re.DOTALL)
        stars_pattern = re.compile(r'class="d-inline-block float-sm-right">\s*\n?\s*([\d,]+)\s*stars today')

        repos = repo_pattern.findall(html)
        descriptions = desc_pattern.findall(html)
        stars_list = stars_pattern.findall(html)

        for i, repo_path in enumerate(repos):
            parts = repo_path.strip().split("/")
            if len(parts) < 2:
                continue

            owner, name = parts[0], parts[1]
            desc = descriptions[i].strip() if i < len(descriptions) else ""
            stars_str = stars_list[i].replace(",", "") if i < len(stars_list) else "0"

            try:
                heat = int(stars_str)
            except ValueError:
                heat = 0

            tags = ["github", "trending"]
            if self.language:
                tags.append(self.language.lower())

            keywords_lower = [k.lower() for k in self.config.keywords]
            if keywords_lower:
                text = f"{owner} {name} {desc}".lower()
                if not any(k in text for k in keywords_lower):
                    continue

            materials.append(
                RawMaterial(
                    id=f"github:{owner}/{name}",
                    connector_id=self.id,
                    source="github",
                    title=f"{owner}/{name}",
                    url=f"https://github.com/{owner}/{name}",
                    summary=desc[:500] if desc else None,
                    tags=tags,
                    heat=heat,
                    raw_data={
                        "owner": owner,
                        "repo": name,
                        "stars_today": heat,
                        "language": self.language or "all",
                    },
                )
            )

        return materials[: self.config.max_items]
