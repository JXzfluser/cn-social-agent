"""Video project persistence via InsForge PostgREST tables."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.video.pipeline import pack_scene_meta


class VideoStore:
    PROJECTS = "video_projects"
    SCENES = "video_scenes"

    def __init__(self, db: Any) -> None:
        self.db = db

    async def list_projects(self, user_id: str) -> list[dict[str, Any]]:
        return await self.db.query(
            self.PROJECTS,
            filters={"user_id": f"eq.{user_id}"},
            order="updated_at.desc",
            limit=100,
        )

    async def create_project(
        self,
        user_id: str,
        *,
        topic: str,
        title: str = "",
        target_seconds: int = 15,
        voice: str = "zh-CN-XiaoxiaoNeural",
        tone: str = "活泼口播",
        video_type: str = "口播",
    ) -> dict[str, Any]:
        row = {
            "user_id": user_id,
            "title": title or topic[:40] or "未命名视频",
            "topic": topic,
            "video_type": video_type or "口播",
            "status": "draft",
            "script": "",
            "duration_seconds": int(target_seconds),
            "output_path": "",
            "generation_mode": "local",
            "agnes_video_task_id": voice,  # reuse field as voice id for v1
        }
        # store tone in script header temporarily if no column — keep in script meta via empty
        created = await self.db.create(self.PROJECTS, row)
        project = created[0] if created else row
        # stash tone in unused way: prepend to script as JSON comment later; also return tone to client
        project["_tone"] = tone
        project["_voice"] = voice
        return project

    async def get_project(self, user_id: str, project_id: str) -> Optional[dict[str, Any]]:
        row = await self.db.get_by_id(self.PROJECTS, project_id)
        if row and str(row.get("user_id")) == str(user_id):
            return row
        return None

    async def update_project(
        self, user_id: str, project_id: str, **fields: Any
    ) -> Optional[dict[str, Any]]:
        if not await self.get_project(user_id, project_id):
            return None
        allowed = {
            "title",
            "topic",
            "status",
            "script",
            "duration_seconds",
            "output_path",
            "agnes_video_task_id",
            "video_type",
        }
        payload = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not payload:
            return await self.get_project(user_id, project_id)
        updated = await self.db.update(
            self.PROJECTS, {"id": f"eq.{project_id}"}, payload
        )
        return updated[0] if updated else await self.get_project(user_id, project_id)

    async def delete_project(self, user_id: str, project_id: str) -> bool:
        if not await self.get_project(user_id, project_id):
            return False
        await self.db.delete(self.SCENES, filters={"project_id": f"eq.{project_id}"})
        await self.db.delete(self.PROJECTS, filters={"id": f"eq.{project_id}"})
        return True

    async def list_scenes(self, project_id: str) -> list[dict[str, Any]]:
        return await self.db.query(
            self.SCENES,
            filters={"project_id": f"eq.{project_id}"},
            order="scene_num.asc",
            limit=200,
        )

    async def replace_scenes(
        self, project_id: str, scenes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        await self.db.delete(self.SCENES, filters={"project_id": f"eq.{project_id}"})
        rows = []
        for s in scenes:
            meta = pack_scene_meta(
                {
                    "role": s.get("role") or "value",
                    "on_screen": s.get("on_screen") or "",
                    "visual": s.get("visual") or "",
                    "mood": s.get("mood") or "",
                }
            )
            rows.append(
                {
                    "project_id": project_id,
                    "scene_num": int(s.get("num") or s.get("scene_num") or 1),
                    "content": s.get("narration") or s.get("content") or "",
                    "tts_duration_seconds": float(s.get("tts_duration_seconds") or 0),
                    "tts_path": s.get("tts_path") or "",
                    "image_path": meta,
                }
            )
        if not rows:
            return []
        created = await self.db.create(self.SCENES, rows)
        return created if isinstance(created, list) else rows

    async def get_scene(self, scene_id: str) -> Optional[dict[str, Any]]:
        return await self.db.get_by_id(self.SCENES, scene_id)

    async def update_scene(self, scene_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        allowed = {"content", "image_path", "tts_path", "tts_duration_seconds", "scene_num"}
        payload = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not payload:
            return await self.get_scene(scene_id)
        updated = await self.db.update(self.SCENES, {"id": f"eq.{scene_id}"}, payload)
        return updated[0] if updated else await self.get_scene(scene_id)
