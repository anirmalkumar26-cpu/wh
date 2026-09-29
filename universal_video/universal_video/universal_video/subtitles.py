"""Timing helpers for narration segments and subtitles."""

from __future__ import annotations

from typing import Any


def retime_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    start = 0.0
    for segment in segments:
        segment["start"] = round(start, 2)
        start += segment["duration"]
        segment["end"] = round(start, 2)
    return segments
