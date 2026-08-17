import asyncio
from pathlib import Path

from cn_social_agent.platforms.douyin.publisher import DouyinVideoPublisher
from cn_social_agent.video.presentation import half_auto_douyin_payload


def test_half_auto_payload():
    p = half_auto_douyin_payload(title="标题", hashtags=["AI"], description="描述")
    assert p["status"] == "skipped"
    assert "creator.douyin.com" in p["url"]
    assert p["clipboard"]["title"] == "标题"


def test_publish_without_creds_skips(tmp_path: Path):
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    pub = DouyinVideoPublisher()

    async def run():
        return await pub.publish_video(
            user_id="test-user",
            title="T",
            video_path=mp4,
            hashtags=["x"],
            description="d",
            meta={},
        )

    result = asyncio.run(run())
    assert result["status"] in ("skipped", "failed")
    assert "clipboard" in result or result.get("url")
