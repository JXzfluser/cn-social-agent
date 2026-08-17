"""Upload L0/L1 finals to InsForge Storage; resolve download from disk or cloud."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from cn_social_agent.video.pipeline import decode_script_bundle, merge_script_meta

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = (os.getenv("VIDEO_STORAGE_BUCKET") or "koubo-videos").strip() or "koubo-videos"


def video_storage_enabled() -> bool:
    return (os.getenv("VIDEO_STORAGE_UPLOAD") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def storage_ref_from_project(project: dict[str, Any]) -> tuple[str, str] | None:
    """Return (bucket, key) from wbmeta if present."""
    _plain, meta = decode_script_bundle(project.get("script") or "")
    key = (meta.get("output_storage_key") or "").strip()
    if not key:
        return None
    bucket = (meta.get("output_storage_bucket") or DEFAULT_BUCKET).strip() or DEFAULT_BUCKET
    return bucket, key


def object_key_for_project(user_id: str, project_id: str) -> str:
    uid = (user_id or "anon").strip() or "anon"
    pid = (project_id or "unknown").strip() or "unknown"
    return f"{uid}/{pid}/final.mp4"


async def upload_project_final(
    storage: Any,
    *,
    user_id: str,
    project_id: str,
    local_path: str | Path,
    script: str = "",
) -> dict[str, Any]:
    """Upload final.mp4 and return {script, bucket, key, size} (best-effort).

    Never raises — failures are logged and returned as ``ok=False``.
    """
    path = Path(local_path)
    if not path.is_file():
        return {"ok": False, "error": "local file missing"}
    if storage is None:
        return {"ok": False, "error": "storage unavailable"}
    if not video_storage_enabled():
        return {"ok": False, "error": "upload disabled", "skipped": True}

    bucket = DEFAULT_BUCKET
    key = object_key_for_project(user_id, project_id)
    try:
        await storage.ensure_bucket(bucket, public=False)
        result = await storage.upload_file(
            bucket, key, path, content_type="video/mp4", upsert=True
        )
        final_key = str(result.get("key") or key)
        final_bucket = str(result.get("bucket") or bucket)
        new_script = merge_script_meta(
            script or "",
            output_storage_bucket=final_bucket,
            output_storage_key=final_key,
        )
        return {
            "ok": True,
            "bucket": final_bucket,
            "key": final_key,
            "size": result.get("size"),
            "script": new_script,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "video storage upload failed project=%s: %s", project_id, exc
        )
        return {"ok": False, "error": str(exc)}


async def download_project_bytes(
    storage: Any,
    project: dict[str, Any],
) -> Optional[bytes]:
    """Fetch final bytes from Storage when local path is gone."""
    ref = storage_ref_from_project(project)
    if not ref or storage is None:
        return None
    bucket, key = ref
    try:
        return await storage.download(bucket, key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("video storage download failed: %s", exc)
        return None
