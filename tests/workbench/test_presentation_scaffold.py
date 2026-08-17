from pathlib import Path

from cn_social_agent.video.presentation import (
    PRESENTATION_ROOT,
    require_checkpoint,
    scaffold_project,
    set_checkpoint,
    write_config_ts,
)


def test_require_checkpoint():
    assert require_checkpoint({}, "a1")
    meta = set_checkpoint({"video_type": "presentation"}, "a1")
    assert require_checkpoint(meta, "a1") is None


def test_scaffold_copies_template(tmp_path, monkeypatch):
    template = Path(__file__).resolve().parents[2] / "templates" / "web-presentation"
    monkeypatch.setenv("PRESENTATION_DATA_DIR", str(tmp_path))
    # re-import roots? presentation_dir uses module-level PRESENTATION_ROOT
    import cn_social_agent.video.presentation as pres

    monkeypatch.setattr(pres, "PRESENTATION_ROOT", tmp_path)
    dest = scaffold_project(
        "proj1",
        aspect="9:16",
        theme="terminal-green",
        title="Demo",
        template_root=template,
    )
    assert (dest / "package.json").is_file()
    cfg = (dest / "src" / "config.ts").read_text(encoding="utf-8")
    assert "9:16" in cfg
    assert "1080" in cfg and "1920" in cfg
