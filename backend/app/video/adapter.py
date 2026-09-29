import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Protocol

from backend.app.core.config import settings


class VideoAdapter(Protocol):
    def generate(self, lesson: dict, job_id: str) -> dict: ...


class ExistingPipelineAdapter:
    """Runs the existing `a/` pipeline from a per-job copy to protect its files."""

    def __init__(self, engine_root: Path | None = None, jobs_root: Path | None = None, timeout_seconds: int = 900):
        self.engine_root = (engine_root or settings.video_engine_path).resolve()
        self.jobs_root = (jobs_root or settings.video_jobs_path).resolve()
        self.timeout_seconds = timeout_seconds

    def generate(self, lesson: dict, job_id: str) -> dict:
        source_package = self.engine_root / "educational_video"
        source_entry = self.engine_root / "main.py"
        if not source_package.is_dir() or not source_entry.is_file():
            raise FileNotFoundError("Configured video engine is missing its package or entry point")

        job_root = self.jobs_root / job_id
        engine_copy = job_root / "engine"
        engine_copy.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_package, engine_copy / "educational_video", dirs_exist_ok=True)
        shutil.copy2(source_entry, engine_copy / "main.py")

        content = lesson.get("content")
        if not isinstance(content, dict) or not isinstance(content.get("sections"), list):
            raise ValueError("Lesson content is not a validated section list")
        script = []
        for index, section in enumerate(content["sections"], start=1):
            if not isinstance(section, dict):
                raise ValueError("Lesson section must be an object")
            narration = section.get("content")
            title = section.get("title")
            if not isinstance(narration, str) or not narration.strip() or not isinstance(title, str):
                raise ValueError("Lesson sections need non-empty title and content")
            script.append(
                {
                    "id": f"lesson-{index:03d}",
                    "narration": f"{title}. {narration}",
                    "subtitle": title,
                    "actions": [],
                }
            )
        if not script:
            raise ValueError("Lesson must have at least one section for video generation")
        input_path = engine_copy / "data" / "backend_lesson.json"
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text(
            json.dumps({"topic": lesson["topic"], "script": script}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        input_path = input_path.resolve()
        result = subprocess.run(
            [sys.executable, "main.py", "--input", str(input_path), "--stage", "full"],
            cwd=engine_copy,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("Existing video pipeline returned a failure")
        report_path = engine_copy / "output" / "pipeline_report.json"
        video_path = engine_copy / "output" / "final.mp4"
        if not report_path.is_file() or not video_path.is_file() or video_path.stat().st_size == 0:
            raise RuntimeError("Existing video pipeline did not produce a validated video report")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "success" or not report.get("video_validation"):
            raise RuntimeError("Existing video pipeline report indicates invalid output")
        return {
            "video_available": True,
            "relative_video": str(Path(job_id) / "engine" / "output" / "final.mp4"),
            "duration": report.get("duration"),
            "segments": report.get("segments"),
            "video_validation": report["video_validation"],
        }


class MockVideoAdapter:
    def generate(self, lesson: dict, job_id: str) -> dict:
        return {
            "video_available": False,
            "mock": True,
            "lesson_topic": lesson["topic"],
            "job_id": job_id,
            "diagnostic": "Video adapter was mocked; no media was rendered.",
        }
