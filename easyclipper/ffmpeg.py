"""Locate FFmpeg and build video export arguments."""

import os
from pathlib import Path
import shutil

from . import ROOT


def find_ffmpeg() -> str | None:
    """Prefer FFmpeg in the project root or one of its supported bin folders."""
    filename = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    for folder in (ROOT, ROOT / "ffmpeg" / "bin", ROOT / "ffmpeg", ROOT / "bin"):
        candidate = folder / filename
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ffmpeg")


def export_args(source: Path, destination: Path, start: float,
                duration: float, bitrate: int, audio: bool) -> list[str]:
    args = [
        "-hide_banner", "-nostdin", "-y", "-ss", f"{start:.3f}",
        "-i", str(source), "-t", f"{duration:.3f}", "-map", "0:v:0",
    ]
    if audio:
        args += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "192k"]
    else:
        args += ["-an"]
    return args + [
        "-sn", "-dn", "-c:v", "libx264", "-preset", "medium",
        "-b:v", f"{bitrate}k", "-pix_fmt", "yuv420p",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", str(destination),
    ]


