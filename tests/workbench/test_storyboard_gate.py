"""Storyboard confirm gate + one-beat scene split."""

from __future__ import annotations

from cn_social_agent.video.pipeline import (
    decode_script_bundle,
    encode_script_bundle,
    speakable_narration,
    split_scenes_one_beat,
    storyboard_outline,
)


def test_encode_storyboard_confirmed_roundtrip():
    raw = encode_script_bundle(
        {
            "full_script": "旁白",
            "storyboard_confirmed": True,
            "content_angle": "intro",
        }
    )
    _plain, meta = decode_script_bundle(raw)
    assert meta.get("storyboard_confirmed") is True


def test_speakable_strips_legacy_densify_filler():
    raw = (
        "很多人装完跑不起来。"
        "这里补一句可执行细节：围绕「Artifact Plan 冒烟：三分钟讲清 Agent」先定义问题，再动手验证，别只记名词。"
    )
    speak = speakable_narration(raw)
    assert "补一句可执行细节" not in speak
    assert "装完跑不起来" in speak
    assert "「" not in speak


def test_split_scenes_one_beat_splits_multi_clause():
    scenes = [
        {
            "num": 1,
            "role": "hook",
            "narration": "很多人装了不会用。第一步先把环境跑通。第二步只接一个工具。",
            "on_screen": "装了不会用",
            "visual": "痛点｜close-up",
        }
    ]
    out = split_scenes_one_beat(scenes, max_chars_per_scene=80, max_scenes=10)
    assert len(out) >= 3
    assert out[0]["role"] == "hook"
    assert out[-1]["role"] == "cta"
    assert all("。" in s["narration"] or len(s["narration"]) < 40 for s in out[:-1])


def test_split_keeps_short_scene():
    scenes = [
        {
            "num": 1,
            "role": "hook",
            "narration": "今天只讲一件事。",
            "on_screen": "一件事",
            "visual": "钩子",
        },
        {
            "num": 2,
            "role": "cta",
            "narration": "关注我下期继续。",
            "on_screen": "关注",
            "visual": "行动",
        },
    ]
    out = split_scenes_one_beat(scenes, max_chars_per_scene=80, max_scenes=10)
    assert len(out) == 2


def test_storyboard_outline_from_scenes():
    rows = storyboard_outline(
        [
            {
                "scene_num": 1,
                "content": "钩子旁白很长很长",
                "image_path": '{"role":"hook","on_screen":"装了不会用","visual":"痛点｜close-up"}',
            }
        ]
    )
    assert rows[0]["role"] == "hook"
    assert rows[0]["on_screen"] == "装了不会用"
    assert "钩子" in rows[0]["narration_preview"]
