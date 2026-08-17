from cn_social_agent.video.pipeline import (
    _board_to_cinematic_shot,
    _content_bits,
    _split_visual_board_shot,
)


def test_split_visual_board_shot():
    board, shot = _split_visual_board_shot("数据条+关键数字｜俯拍显示器折线图缓慢推进")
    assert "数据条" in board
    assert "俯拍" in shot


def test_content_bits_skips_densify_filler():
    narr = "第一步先装环境。这里补一句可执行细节：围绕「X」先定义问题。"
    bits = _content_bits(narr, "步骤清单 1/3", limit=3)
    assert bits
    assert all("补一句可执行细节" not in b for b in bits)


def test_board_to_shot_prefers_shot_segment():
    shot = _board_to_cinematic_shot(
        visual="数据条｜hands typing while dashboard bars rise",
        role="evidence",
        on_screen="证据① 硬指标",
        title="OpenClaw",
        narration="证据一：看增长指标。",
    )
    assert "dashboard" in shot or "hands" in shot


def test_ensure_visual_adds_shot_half():
    from cn_social_agent.video.pipeline import ensure_visual_board_shot

    out = ensure_visual_board_shot(
        "数据条+关键数字",
        role="evidence",
        on_screen="证据①",
        title="OpenClaw",
        narration="证据一：看增长指标。",
    )
    assert "｜" in out
    board, shot = _split_visual_board_shot(out)
    assert "数据条" in board
    assert len(shot) >= 8


def test_board_to_shot_translates_jargon():
    shot = _board_to_cinematic_shot(
        visual="趋势折线+标注",
        role="pattern",
        on_screen="热闹≠兑现",
        title="分析",
        narration="规律是热闹先行。",
    )
    assert "chart" in shot.lower() or "line" in shot.lower()
