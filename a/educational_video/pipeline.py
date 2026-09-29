import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from educational_video import config
from educational_video.audio import concatenate_audio_segments, generate_audio_segments
from educational_video.content import load_input_data
from educational_video.planner import load_scene_plan, plan_from_input, save_scene_plan
from educational_video.renderer import render_complete_video
from educational_video.timeline import create_master_timeline, create_srt_file, load_timeline, save_timeline
from educational_video.video_validator import validate_final_output


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate synchronized narrated Manim educational videos.")
    parser.add_argument("--stage", choices=("full", "plan", "audio", "render"), default="full")
    parser.add_argument("--input", type=Path, help="Input JSON or a UTF-8 plain-text script")
    parser.add_argument("--topic", help="Topic override for the input/default lesson")
    parser.add_argument("--quality", choices=("low", "medium", "high"), default="low")
    return parser


def run_pipeline(
    stage: str = "full",
    input_path: Path | None = None,
    topic: str | None = None,
    quality: str = "low",
) -> dict[str, Any]:
    if stage not in {"full", "plan", "audio", "render"}:
        raise ValueError(f"Unknown pipeline stage: {stage}")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"stage": stage, "started_at": datetime.now(timezone.utc).isoformat(), "status": "running"}

    if stage in {"full", "plan"}:
        if input_path is None and topic is None:
            input_path = config.DATA_DIR / "input.json"
        input_data = load_input_data(input_path, topic)
        plan = plan_from_input(input_data)
        save_scene_plan(plan, config.SCENE_PLAN_PATH)
        report["scene_plan"] = str(config.SCENE_PLAN_PATH)
    else:
        plan = load_scene_plan(config.SCENE_PLAN_PATH)

    if stage in {"full", "audio"}:
        measured = generate_audio_segments(plan, config.AUDIO_DIR)
        timeline = create_master_timeline(plan, measured)
        save_timeline(timeline, config.MASTER_TIMELINE_PATH)
        create_srt_file(timeline, config.SUBTITLE_PATH)
        concatenate_audio_segments(measured, config.NARRATION_PATH)
        report.update(
            {
                "master_timeline": str(config.MASTER_TIMELINE_PATH),
                "subtitles": str(config.SUBTITLE_PATH),
                "narration": str(config.NARRATION_PATH),
                "duration": timeline["duration"],
                "segments": len(timeline["segments"]),
            }
        )

    if stage in {"full", "render"}:
        timeline = load_timeline(config.MASTER_TIMELINE_PATH)
        config.VIDEO_PATH.parent.mkdir(parents=True, exist_ok=True)
        render_complete_video(config.MASTER_TIMELINE_PATH, config.VIDEO_PATH, quality)
        video_validation = validate_final_output(config.VIDEO_PATH, timeline["duration"])
        report.update(
            {
                "video": str(config.VIDEO_PATH),
                "duration": timeline["duration"],
                "video_validation": video_validation,
            }
        )

    report["status"] = "success"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    config.REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
