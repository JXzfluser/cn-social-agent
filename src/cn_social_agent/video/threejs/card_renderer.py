import asyncio
import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional

THREEJS_DIR = Path(__file__).parent
CARD_RENDERER_SCRIPT = THREEJS_DIR / "card_renderer.js"

AVAILABLE_EFFECTS = ["particles", "waves", "grid", "rings", "none"]

ROLE_TO_EFFECT = {
    "hook": "particles",
    "pain": "waves",
    "context": "grid",
    "thesis": "rings",
    "evidence": "grid",
    "pattern": "waves",
    "verdict": "particles",
    "value": "particles",
    "steps": "grid",
    "proof": "rings",
    "compare": "waves",
    "pitfall": "waves",
    "cta": "particles",
}


async def render_card(
    output_path: Path,
    title: str = "",
    subtitle: str = "",
    role: str = "value",
    scene_num: int = 1,
    total: int = 1,
    accent_color: Tuple[int, int, int] = (255, 90, 70),
    bg_color: Tuple[int, int, int] = (10, 14, 18),
    effect: Optional[str] = None,
    reveal: float = 1.0,
    resolution: Tuple[int, int] = (1080, 1920),
) -> Path:
    if effect is None:
        effect = ROLE_TO_EFFECT.get(role, "particles")

    if effect not in AVAILABLE_EFFECTS:
        effect = "particles"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    accent_str = f"{accent_color[0]},{accent_color[1]},{accent_color[2]}"
    bg_str = f"{bg_color[0]},{bg_color[1]},{bg_color[2]}"

    cmd = [
        "node",
        str(CARD_RENDERER_SCRIPT),
        "--output", str(output_path.with_suffix("")),
        "--title", title,
        "--subtitle", subtitle,
        "--role", role,
        "--scene_num", str(scene_num),
        "--total", str(total),
        "--accent", accent_str,
        "--bg", bg_str,
        "--effect", effect,
        "--reveal", str(reveal),
        "--width", str(resolution[0]),
        "--height", str(resolution[1]),
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
            f"Card render failed (exit {proc.returncode}):\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )

    result_path = output_path.with_suffix(".png")
    if not result_path.exists():
        raise FileNotFoundError(f"Expected output not found: {result_path}")

    return result_path


def render_card_sync(
    output_path: Path,
    title: str = "",
    subtitle: str = "",
    role: str = "value",
    scene_num: int = 1,
    total: int = 1,
    accent_color: Tuple[int, int, int] = (255, 90, 70),
    bg_color: Tuple[int, int, int] = (10, 14, 18),
    effect: Optional[str] = None,
    reveal: float = 1.0,
    resolution: Tuple[int, int] = (1080, 1920),
) -> Path:
    return asyncio.run(
        render_card(
            output_path=output_path,
            title=title,
            subtitle=subtitle,
            role=role,
            scene_num=scene_num,
            total=total,
            accent_color=accent_color,
            bg_color=bg_color,
            effect=effect,
            reveal=reveal,
            resolution=resolution,
        )
    )
