from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IdeaIntegrator:
    def __init__(self):
        self._project_store = None
        self._canvas_store = None

    def set_project_store(self, store):
        self._project_store = store

    def set_canvas_store(self, store):
        self._canvas_store = store

    async def create_project_from_card(
        self,
        user_id: str,
        card: dict[str, Any],
        email: str = "",
    ) -> Optional[dict[str, Any]]:
        if not self._project_store:
            logger.warning("Project store not configured")
            return None

        try:
            project = await self._project_store.create(
                user_id=user_id,
                data={
                    "title": card.get("title", ""),
                    "description": card.get("hook", ""),
                    "source": "idea_engine",
                    "card_id": card.get("id"),
                    "content_type": card.get("content_type", ""),
                    "tags": card.get("angles", []),
                    "email": email,
                },
            )
            logger.info(f"Created project {project.get('id')} from card {card.get('id')}")
            return project
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None

    async def create_canvas_nodes_from_card(
        self,
        user_id: str,
        card: dict[str, Any],
        material: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if not self._canvas_store:
            logger.warning("Canvas store not configured")
            return None

        try:
            nodes = []
            x, y = 100, 100

            idea_node = {
                "id": f"idea:{card.get('id')}",
                "type": "idea",
                "x": x,
                "y": y,
                "width": 200,
                "height": 100,
                "data": {
                    "title": card.get("title", ""),
                    "hook": card.get("hook", ""),
                    "angles": card.get("angles", []),
                },
            }
            nodes.append(idea_node)

            if material:
                x += 300
                source_node = {
                    "id": f"source:{material.get('id')}",
                    "type": "source",
                    "x": x,
                    "y": y,
                    "width": 200,
                    "height": 80,
                    "data": {
                        "title": material.get("title", ""),
                        "url": material.get("url", ""),
                        "source": material.get("source", ""),
                    },
                }
                nodes.append(source_node)

            canvas = await self._canvas_store.create(
                user_id=user_id,
                data={
                    "name": card.get("title", "新画布"),
                    "nodes": nodes,
                    "edges": [],
                },
            )
            logger.info(f"Created canvas {canvas.get('id')} from card")
            return canvas
        except Exception as e:
            logger.error(f"Failed to create canvas: {e}")
            return None

    async def handle_card_selected(
        self,
        user_id: str,
        card: dict[str, Any],
        material: Optional[dict[str, Any]] = None,
        email: str = "",
    ) -> dict[str, Any]:
        result = {"card_id": card.get("card_id") or card.get("id")}

        project = await self.create_project_from_card(user_id, card, email=email)
        if project:
            result["project_id"] = project.get("id")
            result["project_created"] = True

        canvas = await self.create_canvas_nodes_from_card(user_id, card, material)
        if canvas:
            result["canvas_id"] = canvas.get("id")
            result["canvas_created"] = True

        return result


integrator = IdeaIntegrator()
