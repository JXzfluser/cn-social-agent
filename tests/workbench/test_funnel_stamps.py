from cn_social_agent.video.pipeline import (
    apply_funnel_stamps,
    decode_script_bundle,
    encode_script_bundle,
    funnel_snapshot,
)


def test_stamp_once_preserves_existing():
    s1 = apply_funnel_stamps("", "t_created", "t_script_ready")
    _, m1 = decode_script_bundle(s1)
    assert m1.get("t_created")
    assert m1.get("t_script_ready")
    first = m1["t_script_ready"]
    s2 = apply_funnel_stamps(s1, "t_script_ready", "t_l0_ready")
    _, m2 = decode_script_bundle(s2)
    assert m2["t_script_ready"] == first
    assert m2.get("t_l0_ready")


def test_encode_preserves_funnel_keys():
    raw = encode_script_bundle(
        {
            "full_script": "旁白",
            "t_created": "2026-01-01T00:00:00Z",
            "t_l0_ready": "2026-01-01T01:00:00Z",
        }
    )
    _, meta = decode_script_bundle(raw)
    assert meta["t_created"] == "2026-01-01T00:00:00Z"
    assert meta["t_l0_ready"] == "2026-01-01T01:00:00Z"


def test_funnel_snapshot_fallback_created_at():
    snap = funnel_snapshot({"script": "", "created_at": "2026-02-02T00:00:00Z"})
    assert snap["t_created"] == "2026-02-02T00:00:00Z"
    assert snap["t_script_ready"] is None
