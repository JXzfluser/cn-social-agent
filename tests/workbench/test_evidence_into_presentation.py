"""Tests for evidence → presentation research_notes."""

from __future__ import annotations

from cn_social_agent.knowledge.assets import format_evidence_pack_notes


def test_format_evidence_pack_notes_ranks_and_clips():
    pack = {
        "evidences": [
            {"id": "e1", "text": "低分证据", "score": 1, "selected": True},
            {
                "id": "e2",
                "text": "高分：Agent 实测要看可观察日志与回放，而不是口号。",
                "score": 9,
                "source": "repo README",
                "selected": True,
            },
            {"id": "e3", "text": "未选中", "score": 99, "selected": False},
        ]
    }
    notes = format_evidence_pack_notes(pack, limit=5)
    assert "本地证据包" in notes
    assert "[e2]" in notes
    assert "可观察日志" in notes
    assert "来源感：repo README" in notes
    assert "未选中" not in notes
    # higher score first
    assert notes.index("[e2]") < notes.index("[e1]")


def test_format_evidence_pack_notes_empty():
    assert format_evidence_pack_notes(None) == ""
    assert format_evidence_pack_notes({"evidences": []}) == ""
    assert format_evidence_pack_notes({"evidences": [{"text": "", "selected": True}]}) == ""
