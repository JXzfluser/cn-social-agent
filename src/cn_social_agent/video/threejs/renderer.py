import asyncio
import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional

THREEJS_DIR = Path(__file__).parent
RENDER_SCRIPT = THREEJS_DIR / "render.js"

AVAILABLE_TRANSITIONS = [
    "particle_converge",
    "camera_flythrough",
    "glitch_reveal",
    "light_sweep",
    "depth_blur",
]


async def render_transition(
    transition_type: str,
    text: str = "",
    accent_color: Tuple[int, int, int] = (255, 90, 70),
    output_path: Path = Path("/tmp/transition.mp4"),
    duration: float = 1.5,
    resolution: Tuple[int, int] = (1080, 1920),
    fps: int = 30,
) -> Path:
    """Render a Three.js transition to MP4.

    Args:
        transition_type: One of AVAILABLE_TRANSITIONS
        text: Text to overlay during transition
        accent_color: RGB color tuple for the transition
        output_path: Output path (will add .mp4 extension)
        duration: Duration in seconds
        resolution: (width, height)
        fps: Frames per second

    Returns:
        Path to rendered MP4 file
    """
    if transition_type not in AVAILABLE_TRANSITIONS:
        raise ValueError(
            f"Unknown transition: {transition_type}. "
            f"Available: {AVAILABLE_TRANSITIONS}"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    accent_str = f"{accent_color[0]},{accent_color[1]},{accent_color[2]}"

    cmd = [
        "node",
        str(RENDER_SCRIPT),
        "--transition", transition_type,
        "--text", text,
        "--accent", accent_str,
        "--output", str(output_path.with_suffix("")),
        "--duration", str(duration),
        "--width", str(resolution[0]),
        "--height", str(resolution[1]),
        "--fps", str(fps),
    ]

    env = os.environ.copy()
    node_path = env.get("NODE_PATH", "")
    if node_path:
        env["NODE_PATH"] = node_path

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(THREEJS_DIR),
        env=env,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"Three.js render failed (exit {proc.returncode}):\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )

    result_path = output_path.with_suffix(".mp4")
    if not result_path.exists():
        raise FileNotFoundError(f"Expected output not found: {result_path}")

    return result_path


def render_transition_sync(
    transition_type: str,
    text: str = "",
    accent_color: Tuple[int, int, int] = (255, 90, 70),
    output_path: Path = Path("/tmp/transition.mp4"),
    duration: float = 1.5,
    resolution: Tuple[int, int] = (1080, 1920),
    fps: int = 30,
) -> Path:
    return asyncio.run(
        render_transition(
            transition_type=transition_type,
            text=text,
            accent_color=accent_color,
            output_path=output_path,
            duration=duration,
            resolution=resolution,
            fps=fps,
        )
    )


def ensure_node_deps():
    node_modules = THREEJS_DIR / "node_modules"
    if not node_modules.exists():
        subprocess.run(
            ["npm", "install"],
            cwd=str(THREEJS_DIR),
            check=True,
            capture_output=True,
        )
