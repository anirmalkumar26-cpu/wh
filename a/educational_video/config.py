from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIO_DIR = OUTPUT_DIR / "audio"
SCENE_PLAN_PATH = DATA_DIR / "scene_plan.json"
MASTER_TIMELINE_PATH = DATA_DIR / "master_timeline.json"
SUBTITLE_PATH = OUTPUT_DIR / "subtitles.srt"
NARRATION_PATH = OUTPUT_DIR / "narration.wav"
VIDEO_PATH = OUTPUT_DIR / "final.mp4"
REPORT_PATH = OUTPUT_DIR / "pipeline_report.json"
