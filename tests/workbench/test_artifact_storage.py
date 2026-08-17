"""Tests for InsForge video artifact storage helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cn_social_agent.video.artifact_storage import (
    DEFAULT_BUCKET,
    download_project_bytes,
    object_key_for_project,
    storage_ref_from_project,
    upload_project_final,
)
from cn_social_agent.video.pipeline import decode_script_bundle, encode_script_bundle, merge_script_meta


def test_object_key_stable():
    assert object_key_for_project("u1", "p1") == "u1/p1/final.mp4"


def test_storage_ref_from_wbmeta():
    script = encode_script_bundle(
        {
            "full_script": "hello",
            "output_storage_bucket": "koubo-videos",
            "output_storage_key": "u1/p1/final.mp4",
        }
    )
    ref = storage_ref_from_project({"script": script})
    assert ref == ("koubo-videos", "u1/p1/final.mp4")
    assert storage_ref_from_project({"script": ""}) is None


def test_encode_preserves_storage_keys():
    script = merge_script_meta(
        encode_script_bundle({"full_script": "x"}),
        output_storage_bucket="b",
        output_storage_key="k/final.mp4",
    )
    _plain, meta = decode_script_bundle(script)
    assert meta["output_storage_bucket"] == "b"
    assert meta["output_storage_key"] == "k/final.mp4"


@pytest.mark.asyncio
async def test_upload_project_final_writes_meta(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_UPLOAD", "1")
    mp4 = tmp_path / "final.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")

    storage = MagicMock()
    storage.ensure_bucket = AsyncMock(return_value=DEFAULT_BUCKET)
    storage.upload_file = AsyncMock(
        return_value={"bucket": DEFAULT_BUCKET, "key": "u/p/final.mp4", "size": 10}
    )

    out = await upload_project_final(
        storage,
        user_id="u",
        project_id="p",
        local_path=mp4,
        script=encode_script_bundle({"full_script": "n"}),
    )
    assert out["ok"] is True
    assert out["key"] == "u/p/final.mp4"
    _plain, meta = decode_script_bundle(out["script"])
    assert meta["output_storage_key"] == "u/p/final.mp4"
    storage.ensure_bucket.assert_awaited()
    storage.upload_file.assert_awaited()


@pytest.mark.asyncio
async def test_upload_skips_when_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VIDEO_STORAGE_UPLOAD", "0")
    mp4 = tmp_path / "final.mp4"
    mp4.write_bytes(b"x")
    storage = MagicMock()
    out = await upload_project_final(
        storage, user_id="u", project_id="p", local_path=mp4, script=""
    )
    assert out.get("skipped") is True
    assert out["ok"] is False


@pytest.mark.asyncio
async def test_download_project_bytes():
    script = encode_script_bundle(
        {
            "full_script": "",
            "output_storage_bucket": "koubo-videos",
            "output_storage_key": "a/b/final.mp4",
        }
    )
    storage = MagicMock()
    storage.download = AsyncMock(return_value=b"mp4bytes")
    data = await download_project_bytes(storage, {"script": script})
    assert data == b"mp4bytes"
    storage.download.assert_awaited_with("koubo-videos", "a/b/final.mp4")


@pytest.mark.asyncio
async def test_storage_upload_uses_multipart():
    from cn_social_agent.insforge.client import InsForgeClient
    from cn_social_agent.insforge.storage import InsForgeStorage

    client = InsForgeClient()
    client._admin_token = "tok"

    class _Resp:
        status_code = 201
        is_error = False
        text = "{}"

        def json(self):
            return {"data": {"bucket": "koubo-videos", "key": "u/p/final.mp4", "size": 3}}

    put = AsyncMock(return_value=_Resp())
    client._http = MagicMock()
    client._http.put = put

    storage = InsForgeStorage(client)
    result = await storage.upload(
        "koubo-videos", "u/p/final.mp4", b"abc", content_type="video/mp4", upsert=False
    )
    assert result["key"] == "u/p/final.mp4"
    assert put.await_count == 1
    kwargs = put.await_args.kwargs
    assert "files" in kwargs
    assert kwargs["files"]["file"][0] == "final.mp4"
    assert kwargs["headers"].get("Authorization") == "Bearer tok"
