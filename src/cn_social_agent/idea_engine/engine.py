from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from . import cloud as idea_cloud
from .cache import material_cache
from .connectors import (
    ConnectorConfig,
    manager,
)
from .connectors.base import RawMaterial
from .error_handler import error_handler
from .processor import IdeaCard, batch_generate_cards

logger = logging.getLogger(__name__)


class IdeaEngine:
    def __init__(self):
        self.materials: dict[str, list[RawMaterial]] = {}
        self.cards: dict[str, list[IdeaCard]] = {}
        self._hydrated: set[str] = set()

    async def ensure_loaded(self, user_id: str) -> None:
        """Hydrate materials/cards from the InsForge mirror once per process."""
        if user_id in self._hydrated:
            return
        self._hydrated.add(user_id)
        try:
            db_materials = await idea_cloud.load_materials(user_id)
            db_cards = await idea_cloud.load_cards(user_id)
        except Exception:  # noqa: BLE001
            return
        if db_materials:
            bucket = self.materials.setdefault(user_id, [])
            existing = {m.id for m in bucket}
            bucket.extend(m for m in db_materials if m.id not in existing)
        if db_cards:
            bucket = self.cards.setdefault(user_id, [])
            existing = {c.id for c in bucket}
            bucket.extend(c for c in db_cards if c.id not in existing)

    async def set_card_project(self, user_id: str, card_id: str, project_id: str) -> None:
        for card in self.cards.get(user_id, []):
            if card.id == card_id:
                card.project_id = project_id
                await idea_cloud.patch_card(card_id, {"project_id": project_id})
                return

    async def sync_materials(
        self,
        user_id: str,
        connector_ids: list[str] | None = None,
        llm_call=None,
    ) -> list[RawMaterial]:
        await self.ensure_loaded(user_id)
        ids = connector_ids or ["github_trending", "hackernews", "v2ex"]

        async def _fetch_one(cid: str) -> list[RawMaterial]:
            if not error_handler.should_retry(cid):
                logger.warning(f"Skipping {cid} due to repeated errors")
                return []

            cached = material_cache.get_connector_cache(cid, user_id)
            if cached is not None:
                return cached

            try:
                config = ConnectorConfig(user_id=user_id)
                connector = manager.get_or_create(user_id, cid, config)
                materials = await connector.fetch()
                material_cache.set_connector_cache(cid, user_id, materials)
                return materials
            except Exception as e:
                error_handler.record_error(cid, "fetch_error", str(e))
                return []

        results = await asyncio.gather(*[_fetch_one(cid) for cid in ids])
        all_materials = [m for batch in results for m in batch]

        if user_id not in self.materials:
            self.materials[user_id] = []

        existing_ids = {m.id for m in self.materials[user_id]}
        new_materials = []
        for m in all_materials:
            if m.id not in existing_ids and not material_cache.is_duplicate(
                {"source": m.source, "title": m.title}
            ):
                new_materials.append(m)
                existing_ids.add(m.id)
                material_cache.mark_seen({"source": m.source, "title": m.title})

        self.materials[user_id].extend(new_materials)
        if new_materials:
            await asyncio.gather(
                *[idea_cloud.upsert_material(m, user_id) for m in new_materials]
            )
        return new_materials

    async def generate_cards(
        self,
        user_id: str,
        material_ids: list[str] | None = None,
        llm_call=None,
    ) -> list[IdeaCard]:
        await self.ensure_loaded(user_id)
        user_materials = self.materials.get(user_id, [])

        if material_ids:
            materials = [m for m in user_materials if m.id in material_ids]
        else:
            materials = user_materials

        cards = await batch_generate_cards(materials, user_id, llm_call)

        if user_id not in self.cards:
            self.cards[user_id] = []

        existing_ids = {c.id for c in self.cards[user_id]}
        new_cards = [c for c in cards if c.id not in existing_ids]
        self.cards[user_id].extend(new_cards)
        if new_cards:
            await asyncio.gather(*[idea_cloud.upsert_card(c) for c in new_cards])

        return new_cards

    async def select_card(
        self,
        user_id: str,
        card_id: str,
    ) -> dict[str, Any] | None:
        await self.ensure_loaded(user_id)
        cards = self.cards.get(user_id, [])
        for card in cards:
            if card.id == card_id:
                card.status = "selected"
                card.selected_at = datetime.now()
                await idea_cloud.patch_card(
                    card_id,
                    {"status": "selected", "selected_at": card.selected_at.isoformat()},
                )
                return {
                    "card_id": card_id,
                    "title": card.title,
                    "hook": card.hook,
                    "material_id": card.material_id,
                    "content_type": card.content_type,
                }
        return None

    async def reject_card(self, user_id: str, card_id: str) -> bool:
        await self.ensure_loaded(user_id)
        cards = self.cards.get(user_id, [])
        for card in cards:
            if card.id == card_id:
                card.status = "rejected"
                card.rejected_at = datetime.now()
                await idea_cloud.patch_card(
                    card_id,
                    {"status": "rejected", "rejected_at": card.rejected_at.isoformat()},
                )
                return True
        return False

    async def feedback_card(
        self,
        user_id: str,
        card_id: str,
        feedback: str,
    ) -> bool:
        await self.ensure_loaded(user_id)
        cards = self.cards.get(user_id, [])
        for card in cards:
            if card.id == card_id:
                card.feedback = feedback
                await idea_cloud.patch_card(card_id, {"feedback": feedback})
                return True
        return False

    def get_materials(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        materials = sorted(
            self.materials.get(user_id, []),
            key=lambda m: m.created_at,
            reverse=True,
        )
        total = len(materials)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "items": [self._material_to_dict(m) for m in materials[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_cards(
        self,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        cards = self.cards.get(user_id, [])
        if status:
            cards = [c for c in cards if c.status == status]
        cards = sorted(cards, key=lambda c: c.created_at, reverse=True)

        total = len(cards)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "items": [self._card_to_dict(c) for c in cards[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_connector_status(self, user_id: str) -> list[dict[str, Any]]:
        return manager.get_user_status(user_id)

    async def fetch_single_connector(
        self,
        user_id: str,
        connector_id: str,
    ) -> list[RawMaterial]:
        await self.ensure_loaded(user_id)
        config = ConnectorConfig(user_id=user_id)
        connector = manager.get_or_create(user_id, connector_id, config)
        materials = await connector.fetch()

        if user_id not in self.materials:
            self.materials[user_id] = []

        existing_ids = {m.id for m in self.materials[user_id]}
        new_materials = [m for m in materials if m.id not in existing_ids]
        self.materials[user_id].extend(new_materials)
        if new_materials:
            await asyncio.gather(
                *[idea_cloud.upsert_material(m, user_id) for m in new_materials]
            )

        return new_materials

    def _material_to_dict(self, m: RawMaterial) -> dict[str, Any]:
        def _clean(s: str | None) -> str | None:
            if s is None:
                return None
            return s.replace("\n", " ").replace("\r", " ").replace("\t", " ")

        return {
            "id": m.id,
            "connector_id": m.connector_id,
            "source": m.source,
            "title": _clean(m.title) or "",
            "url": m.url,
            "summary": _clean(m.summary),
            "tags": m.tags,
            "heat": m.heat,
            "created_at": m.created_at.isoformat(),
        }

    def _card_to_dict(self, c: IdeaCard) -> dict[str, Any]:
        return {
            "id": c.id,
            "material_id": c.material_id,
            "title": c.title,
            "hook": c.hook,
            "angles": c.angles,
            "heat_score": c.heat_score,
            "difficulty_score": c.difficulty_score,
            "time_window": c.time_window,
            "content_type": c.content_type,
            "status": c.status,
            "feedback": c.feedback,
            "project_id": c.project_id,
            "created_at": c.created_at.isoformat(),
            "selected_at": c.selected_at.isoformat() if c.selected_at else None,
        }


engine = IdeaEngine()
