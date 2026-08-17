from cn_social_agent.video.agnes_client import extract_completed_video_url


def test_top_level_url():
    assert extract_completed_video_url({"url": "https://cdn.example/a.mp4"}) == (
        "https://cdn.example/a.mp4"
    )


def test_nested_metadata_url():
    assert extract_completed_video_url(
        {"metadata": {"url": "https://cdn.example/b.mp4"}}
    ) == "https://cdn.example/b.mp4"


def test_nested_output_url():
    assert extract_completed_video_url(
        {"output": {"url": "https://cdn.example/c.mp4"}}
    ) == "https://cdn.example/c.mp4"


def test_missing_url():
    assert extract_completed_video_url({"status": "completed"}) == ""
