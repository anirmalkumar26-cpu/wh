import json
import math
from pathlib import Path
from typing import Any


def create_master_timeline(plan: dict[str, Any], measured_segments: list[dict[str, Any]]) -> dict[str, Any]:
    timeline_segments = []
    current = 0.0
    for segment, measured in zip(plan["segments"], measured_segments, strict=True):
        duration = float(measured["audio_duration"])
        action_duration = sum(float(action["duration"]) for action in segment.get("actions", []))
        if action_duration > duration:
            raise ValueError(
                f"segment {segment['id']}: visual actions take {action_duration:.2f}s "
                f"but narration is only {duration:.2f}s"
            )
        timeline_segments.append(
            {
                "id": segment["id"],
                "narration": segment["narration"],
                "subtitle": segment.get("subtitle", segment["narration"]),
                "audio": {"file": measured["audio_path"], "duration": duration},
                "timeline": {"start": current, "end": current + duration},
                "visual": {"actions": segment.get("actions", [])},
            }
        )
        current += duration
    if len(timeline_segments) != len(plan["segments"]):
        raise ValueError("Audio segment count does not match the scene plan")
    return {"schema_version": 1, "topic": plan["topic"], "duration": current, "segments": timeline_segments}


def validate_timeline(timeline: dict[str, Any]) -> None:
    expected_start = 0.0
    for segment in timeline.get("segments", []):
        start, end = segment["timeline"]["start"], segment["timeline"]["end"]
        audio_duration = segment["audio"]["duration"]
        if not all(math.isfinite(value) for value in (start, end, audio_duration)) or start != expected_start or end <= start:
            raise ValueError(f"segment {segment['id']}: invalid timeline bounds")
        if abs((end - start) - audio_duration) > 0.001:
            raise ValueError(f"segment {segment['id']}: segment time does not match measured audio")
        action_duration = sum(action["duration"] for action in segment["visual"]["actions"])
        if action_duration > audio_duration:
            raise ValueError(f"segment {segment['id']}: visual actions exceed narration duration")
        expected_start = end
    if not timeline.get("segments") or abs(expected_start - timeline["duration"]) > 0.001:
        raise ValueError("timeline duration does not match its segment bounds")


def format_srt_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{millis:03}"


def create_srt_file(timeline: dict[str, Any], path: Path) -> Path:
    validate_timeline(timeline)
    cues = []
    for index, segment in enumerate(timeline["segments"], start=1):
        cues.extend(
            [
                str(index),
                f"{format_srt_timestamp(segment['timeline']['start'])} --> {format_srt_timestamp(segment['timeline']['end'])}",
                segment["subtitle"],
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(cues), encoding="utf-8")
    return path


def save_timeline(timeline: dict[str, Any], path: Path) -> None:
    validate_timeline(timeline)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(timeline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_timeline(path: Path) -> dict[str, Any]:
    try:
        timeline = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid master-timeline JSON: {exc}") from exc
    validate_timeline(timeline)
    for segment in timeline["segments"]:
        audio_path = Path(segment["audio"]["file"])
        if not audio_path.is_file():
            raise FileNotFoundError(f"segment {segment['id']}: audio asset is missing: {audio_path}")
    return timeline
