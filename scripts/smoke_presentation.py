#!/usr/bin/env python3
"""Smoke: scaffold presentation into tmp and npm build."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_social_agent.video.presentation import scaffold_project  # noqa: E402
import cn_social_agent.video.presentation as pres  # noqa: E402


def main() -> int:
    template = ROOT / "templates" / "web-presentation"
    with tempfile.TemporaryDirectory() as td:
        pres.PRESENTATION_ROOT = Path(td)
        dest = scaffold_project(
            "smoke",
            aspect="9:16",
            theme="desk",
            title="Smoke",
            template_root=template,
        )
        print("scaffolded", dest)
        result = pres.run_build("smoke", timeout=300)
        print("build ok=", result.get("ok"))
        if not result.get("ok"):
            print((result.get("log") or "")[-2000:])
            return 1
        index = Path(result["dist"]) / "index.html"
        print("dist index exists=", index.is_file())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
