from pathlib import Path

import pytest

from cn_social_agent.video.pipeline import missing_scene_clips, remux_project_final

ROOT = Path(__file__).resolve().parents[2]


def test_workbench_clarify_and_remux_ui_hooks():
    html = (ROOT / "src/cn_social_agent/workbench/index.html").read_text(encoding="utf-8")
    assert "jobRetryFullBtn" in html
    assert "clarifyTrack" in html
    assert 'data-intent="presentation"' in html
    assert "function setVideoTrack" in html


def test_missing_scene_clips_lists_holes(tmp_path, monkeypatch):
    import cn_social_agent.video.pipeline as pl

    monkeypatch.setattr(pl, "VIDEO_ROOT", tmp_path)
    pid = "proj-miss"
    root = tmp_path / pid
    root.mkdir()
    (root / "scene_1.mp4").write_bytes(b"x")
    assert missing_scene_clips(pid, 3) == [2, 3]
    (root / "scene_3.mp4").write_bytes(b"y")
    assert missing_scene_clips(pid, 3) == [2]
    (root / "scene_2.mp4").write_bytes(b"z")
    assert missing_scene_clips(pid, 3) == []


@pytest.mark.asyncio
async def test_remux_lists_all_missing_clips(tmp_path, monkeypatch):
    import cn_social_agent.video.pipeline as pl

    monkeypatch.setattr(pl, "VIDEO_ROOT", tmp_path)
    pid = "proj-remux"
    (tmp_path / pid).mkdir()
    (tmp_path / pid / "scene_1.mp4").write_bytes(b"x")
    with pytest.raises(RuntimeError, match=r"scene_2\.mp4.*scene_3\.mp4"):
        await remux_project_final(pid, 3)
