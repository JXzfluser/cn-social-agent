"""Shared ffmpeg/ffprobe utilities.

Extracted from pipeline.py to eliminate duplicated ffprobe calls
across pipeline and quality gates (design doc 20260822).
"""
from __future__ import annotations

import re
import subprocess
import wave
from functools import lru_cache
from pathlib import Path


def audio_duration(path: Path) -> float:
    """Return duration of an audio/video file in seconds.

    Uses ffprobe for mp3/wav/mp4. Falls back to wave module for WAV,
    or returns 3.0s as a safe default.
    """
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(r.stdout.strip())
    except Exception:
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
        return 3.0


@lru_cache(maxsize=8)
def ffmpeg_has_filter(name: str) -> bool:
    """Check whether ffmpeg has a given filter (e.g. drawtext).

    Homebrew ffmpeg 8.x ships without libfreetype, so drawtext may be absent.
    """
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    pattern = re.compile(rf"^\s*\S+\s+{re.escape(name)}\s", re.M)
    return bool(pattern.search(r.stdout or ""))
