from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import quote

import aiohttp

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class CompetitorConnector(IdeaConnector):
    id = "competitor"
    name = "竞品监控"
    description = "监控竞品账号更新"
    icon = "👁️"

    capabilities = {
        "source": True,
        "monitor": True,
        "realtime": False,
    }

    PLATFORMS = {
        "weixin": {
            "name": "微信公众号",
            "search_url": "https://weixin.sogou.com/weixin?type=1&query={query}",
            "article_url": "https://mp.weixin.qq.com/s/{id}",
        },
        "toutiao": {
            "name": "头条号",
            "search_url": "https://www.toutiao.com/search/?keyword={query}",
            "article_url": "https://www.toutiao.com/article/{id}/",
        },
        "weibo": {
            "name": "微博",
            "api_url": "https://m.weibo.cn/api/container/getIndex",
            "article_url": "https://m.weibo.cn/detail/{id}",
        },
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.accounts = config.extra.get("accounts", [])
        self.platforms = config.extra.get("platforms", ["weixin"])

    async def fetch(self) -> list[RawMaterial]:
        materials = []

        async with aiohttp.ClientSession() as session:
            for account in self.accounts:
                for platform in self.platforms:
                    try:
                        items = await self._fetch_account(session, account, platform)
                        materials.extend(items)
                    except Exception:
                        continue

        return materials[: self.config.max_items]

    async def _fetch_account(
        self, session: aiohttp.ClientSession, account: str, platform: str
    ) -> list[RawMaterial]:
        platform_config = self.PLATFORMS.get(platform)
        if not platform_config:
            return []

        if platform == "weibo":
            return await self._fetch_weibo(session, account)
        elif platform == "weixin":
            return await self._fetch_weixin(session, account)
        elif platform == "toutiao":
            return await self._fetch_toutiao(session, account)

        return []

    async def _fetch_weibo(
        self, session: aiohttp.ClientSession, account: str
    ) -> list[RawMaterial]:
        containerid = f"107603{account}"
        url = f"https://m.weibo.cn/api/container/getIndex"
        params = {"containerid": containerid, "page": 1}

        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        cards = data.get("data", {}).get("cards", [])
        materials = []

        for card in cards:
            mblog = card.get("mblog", {})
            if not mblog:
                continue

            mid = mblog.get("id", "")
            text = mblog.get("text", "")
            reposts = mblog.get("reposts_count", 0)
            comments = mblog.get("comments_count", 0)
            attitudes = mblog.get("attitudes_count", 0)

            import re
            clean_text = re.sub(r"<[^>]+>", "", text)[:500]

            heat = reposts + comments * 2 + attitudes
            tags = ["weibo", "competitor"]

            materials.append(
                RawMaterial(
                    id=f"weibo:{mid}",
                    connector_id=self.id,
                    source="weibo",
                    title=clean_text[:50] + "..." if len(clean_text) > 50 else clean_text,
                    url=f"https://weibo.com/detail/{mid}",
                    summary=clean_text,
                    tags=tags,
                    heat=heat,
                    raw_data={
                        "mid": mid,
                        "reposts": reposts,
                        "comments": comments,
                        "attitudes": attitudes,
                        "account": account,
                        "platform": "weibo",
                    },
                )
            )

        return materials

    async def _fetch_weixin(
        self, session: aiohttp.ClientSession, account: str
    ) -> list[RawMaterial]:
        url = f"https://weixin.sogou.com/weixin?type=1&query={quote(account)}"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()

        import re
        pattern = re.compile(
            r'<li[^>]*>.*?<p class="txt-box">.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        matches = pattern.findall(html)

        materials = []
        for href, title in matches[:10]:
            clean_title = re.sub(r"<[^>]+>", "", title).strip()
            account_hash = hashlib.md5(account.encode()).hexdigest()[:8]

            materials.append(
                RawMaterial(
                    id=f"weixin:{account_hash}:{clean_title[:20]}",
                    connector_id=self.id,
                    source="weixin",
                    title=clean_title,
                    url=href,
                    summary=None,
                    tags=["weixin", "competitor"],
                    heat=0,
                    raw_data={
                        "account": account,
                        "platform": "weixin",
                    },
                )
            )

        return materials

    async def _fetch_toutiao(
        self, session: aiohttp.ClientSession, account: str
    ) -> list[RawMaterial]:
        return []
