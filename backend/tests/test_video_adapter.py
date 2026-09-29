import json
from pathlib import Path

from backend.app.video.adapter import ExistingPipelineAdapter


def test_existing_pipeline_adapter_isolates_engine_and_job_files(tmp_path: Path, monkeypatch) -> None:
    workspace = Path(__file__).resolve().parents[2]
    engine_root = workspace / "a"
    original_scene_plan = (engine_root / "data" / "scene_plan.json").read_bytes()
    jobs_root = tmp_path / "video-jobs"
    adapter = ExistingPipelineAdapter(engine_root=engine_root, jobs_root=jobs_root)

    def fake_run(command, cwd, **_kwargs):
        isolated_root = Path(cwd)
        input_file = isolated_root / "data" / "backend_lesson.json"
        plan_input = json.loads(input_file.read_text(encoding="utf-8"))
        assert plan_input["topic"] == "AVL Tree Right Rotation"
        assert plan_input["script"][0]["id"] == "lesson-001"
        assert plan_input["script"][0]["actions"] == []
        assert isolated_root != engine_root
        assert command[1] == "main.py"
        output = isolated_root / "output"
        output.mkdir()
        (output / "final.mp4").write_bytes(b"mock-video")
        (output / "pipeline_report.json").write_text(
            json.dumps(
                {
                    "status": "success",
                    "duration": 12.0,
                    "segments": 1,
                    "video_validation": {
                        "video_codec": "h264",
                        "audio_codec": "aac",
                        "has_decodable_video": True,
                        "has_decodable_audio": True,
                    },
                }
            ),
            encoding="utf-8",
        )

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("backend.app.video.adapter.subprocess.run", fake_run)
    report = adapter.generate(
        {
            "topic": "AVL Tree Right Rotation",
            "content": {"sections": [{"title": "Rotation", "content": "Promote the left child.", "examples": []}]},
        },
        "fixed-test-job-id",
    )
    assert report["video_available"] is True
    assert (jobs_root / report["relative_video"]).is_file()
    assert (engine_root / "data" / "scene_plan.json").read_bytes() == original_scene_plan
