"""Agnes Video V2.0 async client (text-to-video / image-to-video)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

import httpx

from cn_social_agent.llm.agnes import AgnesLLM


def _api_key() -> str:
    return (
        os.getenv("AGNES_API_KEY")
        or os.getenv("LLM_API_KEY")
        or AgnesLLM().api_key
        or ""
    )


def _base_url() -> str:
    return (
        os.getenv("AGNES_BASE_URL") or "https://apihub.agnes-ai.com/v1"
    ).rstrip("/")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


# Agnes rejects new jobs while its render queue is saturated; that clears on its
# own, so treat it (and generic gateway hiccups) as retryable rather than fatal.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_QUEUE_FULL_MARKERS = ("video_queue_full", "queue is full")


def is_queue_full(status_code: int, body: str) -> bool:
    return status_code in RETRYABLE_STATUS and any(
        m in (body or "").lower() for m in _QUEUE_FULL_MARKERS
    )


async def _retry_conn(awaitable_factory, *, tries: int = 4, base: float = 5.0) -> Any:
    """Retry a coroutine on transient connection/timeout errors.

    Agnes occasionally drops connections (ConnectTimeout/ReadTimeout); a single
    blip must not kill a 5–7 min scene render, so retry with exponential backoff.
    """
    last: Optional[BaseException] = None
    for i in range(max(1, tries)):
        try:
            return await awaitable_factory()
        except (
            httpx.ConnectTimeout,
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
        ) as e:
            last = e
            if i == tries - 1:
                break
            await asyncio.sleep(min(base * (2 ** i), 60.0))
    assert last is not None
    raise last


def extract_completed_video_url(result: dict[str, Any]) -> str:
    """Resolve mp4 URL from Agnes completion payload (top-level or nested)."""
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    output = result.get("output") if isinstance(result.get("output"), dict) else {}
    url = (
        (result.get("url") or "")
        or (meta.get("url") or "")
        or (output.get("url") or "")
        or (result.get("video_url") or "")
        or (result.get("download_url") or "")
    )
    return str(url).strip()


class AgnesVideoClient:
    """Create / poll / download Agnes Video V2.0 tasks."""

    MODEL = "agnes-video-v2.0"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.api_key = api_key or _api_key()
        self.base_url = (base_url or _base_url()).rstrip("/")
        # gateway root for /agnesapi polling
        self.gateway = self.base_url.rsplit("/v1", 1)[0] or "https://apihub.agnes-ai.com"

    @classmethod
    def configured(cls) -> bool:
        return bool(_api_key())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_video(
        self,
        prompt: str,
        *,
        width: int = 768,
        height: int = 1344,
        num_frames: int = 121,
        frame_rate: int = 24,
        image: Optional[str] = None,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        on_progress: Optional[Any] = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("AGNES_API_KEY not configured")
        # num_frames must be 8n+1 and <= 441
        n = int(num_frames)
        n = min(441, max(9, n))
        n = ((n - 1) // 8) * 8 + 1
        payload: dict[str, Any] = {
            "model": self.MODEL,
            "prompt": prompt,
            "width": int(width),
            "height": int(height),
            "num_frames": n,
            "frame_rate": int(frame_rate),
        }
        if image:
            payload["image"] = image
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = int(seed)

        attempts = max(1, int(_env_float("AGNES_QUEUE_RETRIES", 6)))
        backoff = _env_float("AGNES_QUEUE_BACKOFF_SECONDS", 15.0)
        backoff_max = _env_float("AGNES_QUEUE_BACKOFF_MAX_SECONDS", 90.0)

        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            last_status, last_body = 0, ""
            for attempt in range(attempts):
                resp = await _retry_conn(
                    lambda: client.post(
                        f"{self.base_url}/videos",
                        headers=self._headers(),
                        json=payload,
                    )
                )
                if not resp.is_error:
                    return resp.json()
                last_status, last_body = resp.status_code, resp.text[:500]
                if attempt == attempts - 1 or resp.status_code not in RETRYABLE_STATUS:
                    break
                wait = min(backoff * (2**attempt), backoff_max)
                if on_progress:
                    reason = "队列已满" if is_queue_full(last_status, last_body) else "服务繁忙"
                    await on_progress(
                        0,
                        f"Agnes {reason}，{wait:.0f}s 后重试（{attempt + 1}/{attempts - 1}）",
                    )
                await asyncio.sleep(wait)

        if is_queue_full(last_status, last_body):
            raise RuntimeError(
                f"Agnes 视频队列持续排满（已重试 {attempts} 次）。"
                "可稍后重试本镜，或先用 L0 本地渲染出片。"
            )
        raise RuntimeError(f"Agnes video create {last_status}: {last_body}")

    async def get_status(self, video_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            status_retries = max(1, int(_env_float("AGNES_STATUS_RETRIES", 5)))
            backoff = _env_float("AGNES_STATUS_BACKOFF_SECONDS", 6.0)
            resp = None
            for attempt in range(status_retries):
                resp = await _retry_conn(
                    lambda: client.get(
                        f"{self.gateway}/agnesapi",
                        headers=self._headers(),
                        params={"video_id": video_id, "model_name": self.MODEL},
                    ),
                    tries=2,
                )
                if not resp.is_error:
                    return resp.json()
                # 429 = rate limited → back off and retry (do NOT fall to legacy,
                # which returns task_not_exist for gateway-created tasks)
                if resp.status_code == 429:
                    await asyncio.sleep(min(backoff * (2 ** attempt), 60.0))
                    continue
                break  # non-429 error → try legacy fallback once
            # legacy fallback (only reached on a non-429 gateway error)
            if resp is not None and resp.is_error:
                resp2 = await _retry_conn(
                    lambda: client.get(
                        f"{self.base_url}/videos/{video_id}",
                        headers=self._headers(),
                    ),
                    tries=2,
                )
                if resp2.is_error:
                    raise RuntimeError(
                        f"Agnes video status {resp.status_code}/{resp2.status_code}: "
                        f"{resp.text[:200]} | {resp2.text[:200]}"
                    )
                return resp2.json()
            return resp.json()

    async def wait_until_done(
        self,
        video_id: str,
        *,
        poll_seconds: float = 8.0,
        timeout_seconds: float = 360.0,
    ) -> dict[str, Any]:
        elapsed = 0.0
        while elapsed <= timeout_seconds:
            data = await self.get_status(video_id)
            status = (data.get("status") or "").lower()
            if status == "completed":
                return data
            if status == "failed":
                err = data.get("error") or data
                raise RuntimeError(f"Agnes video failed: {err}")
            await asyncio.sleep(poll_seconds)
            elapsed += poll_seconds
        raise TimeoutError(f"Agnes video timed out after {timeout_seconds}s: {video_id}")

    async def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=180.0, trust_env=False, follow_redirects=True) as client:
            resp = await _retry_conn(lambda: client.get(url), tries=4)
            if resp.is_error:
                raise RuntimeError(f"download failed {resp.status_code}")
            dest.write_bytes(resp.content)
        return dest

    async def generate_to_file(
        self,
        prompt: str,
        dest: Path,
        *,
        width: int = 768,
        height: int = 1344,
        num_frames: int = 121,
        frame_rate: int = 24,
        on_progress: Optional[Any] = None,
    ) -> dict[str, Any]:
        created = await self.create_video(
            prompt,
            width=width,
            height=height,
            num_frames=num_frames,
            frame_rate=frame_rate,
            negative_prompt="text overlay, watermark, logo, blurry, low quality, deformed",
            on_progress=on_progress,
        )
        video_id = created.get("video_id") or created.get("task_id") or created.get("id")
        if not video_id:
            raise RuntimeError(f"Agnes video missing video_id: {created}")
        if on_progress:
            await on_progress(0, f"queued {video_id}")

        result = await self.wait_until_done(str(video_id))
        # Agnes may put the mp4 on top-level `url`, or nested under metadata/output
        url = extract_completed_video_url(result)
        if not url:
            raise RuntimeError(f"Agnes video completed but no url: {result}")
        await self.download(url, dest)
        if on_progress:
            await on_progress(100, "downloaded")
        return {"video_id": video_id, "path": str(dest), "result": result}
