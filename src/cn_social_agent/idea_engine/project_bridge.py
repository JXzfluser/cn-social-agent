"""Bridge idea cards → Content Project hub.

IdeaIntegrator calls this adapter's `create()` when a card is selected, so
every accepted idea lands on the project board instead of vanishing.
"""

from __future__ import annotations

from typing import Any, Optional

CATEGORY_BY_CONTENT_TYPE = {
    "technical": "product_explain",
    "tutorial": "skill_roadmap",
    "opinion": "industry_brief",
    "news": "industry_brief",
}


class ContentProjectStore:
    async def create(self, user_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        from cn_social_agent.content import service as cps

        title = str(data.get("title") or "").strip()
        if not title:
            return None
        content_type = str(data.get("content_type") or "").strip()
        return await cps.create_project(
            topic=title,
            user_id=user_id,
            email=str(data.get("email") or ""),
            category=CATEGORY_BY_CONTENT_TYPE.get(content_type, ""),
            research_notes=str(data.get("description") or "").strip(),
            source={
                "kind": "idea_card",
                "card_id": str(data.get("card_id") or ""),
                "title": title,
            },
        )
