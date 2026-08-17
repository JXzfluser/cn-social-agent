from cn_social_agent.api.prefs import (
    merge_prefs,
    normalize_prefs,
    prefs_prompt_block,
    production_brief_from_messages,
    trim_messages_for_context,
)


def test_normalize_and_merge_push_topic():
    p = normalize_prefs({"default_content_angle": "idea", "recent_topics": ["a", "b", "c", "d"]})
    assert p["default_content_angle"] == "intro"
    assert p["recent_topics"] == ["a", "b", "c"]
    m = merge_prefs(p, {"push_topic": "新选题", "default_audience": "开发者"})
    assert m["default_audience"] == "开发者"
    assert m["recent_topics"][0] == "新选题"
    assert len(m["recent_topics"]) == 3


def test_normalize_video_track_and_merge():
    from cn_social_agent.api.prefs import normalize_prefs, normalize_video_track

    assert normalize_video_track("讲解演示") == "presentation"
    assert normalize_video_track("口播") == "koubo"
    p = normalize_prefs({"default_video_track": "presentation", "default_pres_aspect": "16:9"})
    assert p["default_video_track"] == "presentation"
    assert p["default_pres_aspect"] == "16:9"


def test_prefs_prompt_block_nonempty():
    block = prefs_prompt_block({"default_audience": "独立开发者", "default_video_track": "koubo"})
    assert "独立开发者" in block
    assert "User preferences" in block
    assert "口播" in block


def test_production_brief_and_trim():
    history = [
        {
            "role": "assistant",
            "content": "ok",
            "tool_calls": [
                {
                    "name": "propose_short_video",
                    "arguments": {"topic": "OpenClaw"},
                    "result": {
                        "success": True,
                        "data": {
                            "topic": "OpenClaw",
                            "audience": "开发者",
                            "scene_setting": "装环境",
                        },
                    },
                }
            ],
        }
    ]
    brief = production_brief_from_messages(history)
    assert "OpenClaw" in brief
    assert "开发者" in brief
    msgs = [{"role": "user", "content": str(i)} for i in range(40)]
    assert len(trim_messages_for_context(msgs, max_messages=24)) == 24
