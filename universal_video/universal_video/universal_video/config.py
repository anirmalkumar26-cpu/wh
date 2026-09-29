"""Configuration shared by the lesson-generation pipeline."""

from __future__ import annotations

from pathlib import Path

DEFAULT_MODEL = "gemini-3.5-flash-lite"
QUALITY_NAMES = {
    "l": "low_quality",
    "m": "medium_quality",
    "h": "high_quality",
    "p": "production_quality",
}
ELEMENT_TYPES = {
    "text", "label", "circle", "rectangle", "ellipse", "line", "arrow",
    "polygon", "triangle", "star", "arc", "dot", "axes",
}


def ensure_directory(path: Path) -> Path:
    """Create and return an output directory."""
    path.mkdir(parents=True, exist_ok=True)
    return path
