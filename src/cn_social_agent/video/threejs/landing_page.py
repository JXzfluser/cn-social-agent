import asyncio
import json
from pathlib import Path
from typing import List, Dict, Optional

THREEJS_DIR = Path(__file__).parent
LANDING_PAGE_SCRIPT = THREEJS_DIR / "landing_page.js"

AVAILABLE_TEMPLATES = ["product", "tech", "minimal"]


async def generate_landing_page(
    output_path: Path,
    title: str = "",
    subtitle: str = "",
    sections: Optional[List[Dict]] = None,
    accent_color: tuple = (255, 90, 70),
    bg_color: tuple = (10, 14, 18),
    template: str = "product",
) -> Path:
    if template not in AVAILABLE_TEMPLATES:
        template = "product"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sections_json = json.dumps(sections or [], ensure_ascii=False)
    accent_str = f"{accent_color[0]},{accent_color[1]},{accent_color[2]}"
    bg_str = f"{bg_color[0]},{bg_color[1]},{bg_color[2]}"

    cmd = [
        "node",
        str(LANDING_PAGE_SCRIPT),
        "--output", str(output_path),
        "--title", title,
        "--subtitle", subtitle,
        "--sections", sections_json,
        "--accent", accent_str,
        "--bg", bg_str,
        "--template", template,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(THREEJS_DIR),
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"Landing page generation failed (exit {proc.returncode}):\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )

    if not output_path.exists():
        raise FileNotFoundError(f"Expected output not found: {output_path}")

    return output_path


def generate_landing_page_sync(
    output_path: Path,
    title: str = "",
    subtitle: str = "",
    sections: Optional[List[Dict]] = None,
    accent_color: tuple = (255, 90, 70),
    bg_color: tuple = (10, 14, 18),
    template: str = "product",
) -> Path:
    return asyncio.run(
        generate_landing_page(
            output_path=output_path,
            title=title,
            subtitle=subtitle,
            sections=sections,
            accent_color=accent_color,
            bg_color=bg_color,
            template=template,
        )
    )
