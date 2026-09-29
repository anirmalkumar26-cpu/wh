import json
import wave
from pathlib import Path

import pytest

from educational_video.audio import get_audio_duration
from educational_video.content import load_input_data, validate_input
from educational_video.planner import plan_from_input, validate_scene_plan
from educational_video.timeline import create_master_timeline, create_srt_file, format_srt_timestamp, validate_timeline


def test_invalid_input_requires_topic_and_script() -> None:
    with pytest.raises(ValueError, match="topic"):
        validate_input({"script_text": "Lesson"})
    with pytest.raises(ValueError, match="script"):
        validate_input({"topic": "Trees"})


def test_load_json_input_and_plan(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps({"topic": "AVL tree right rotation", "script": [{"id": "intro", "narration": "Hello", "actions": []}]}),
        encoding="utf-8",
    )
    plan = plan_from_input(load_input_data(source, None))
    assert plan["segments"][0]["narration"] == "Hello"
    assert {obj["id"] for obj in plan["objects"]} == {"node_10", "node_20", "node_30"}


def test_scene_plan_rejects_unknown_targets() -> None:
    plan = {
        "topic": "Lesson",
        "objects": [{"id": "node_10"}],
        "segments": [{"id": "s1", "narration": "Explain", "actions": [{"type": "highlight", "target": "absent", "duration": 0.5}]}],
    }
    with pytest.raises(ValueError, match="unknown action target"):
        validate_scene_plan(plan)


def test_scene_plan_rejects_relationships_before_node_creation() -> None:
    plan = {
        "topic": "Lesson",
        "objects": [{"id": "node_10"}, {"id": "node_20"}],
        "segments": [
            {
                "id": "s1",
                "narration": "Connect nodes",
                "actions": [{"type": "connect", "target": "edge_10_20", "source": "node_10", "destination": "node_20", "duration": 0.5}],
            }
        ],
    }
    with pytest.raises(ValueError, match="endpoints must be created"):
        validate_scene_plan(plan)


def test_scene_plan_rejects_recreating_a_persistent_node() -> None:
    create = {"type": "create_node", "target": "node_10", "value": "10", "position": "left", "duration": 0.5}
    plan = {
        "topic": "Lesson",
        "objects": [{"id": "node_10"}],
        "segments": [
            {"id": "s1", "narration": "Create node", "actions": [create]},
            {"id": "s2", "narration": "Duplicate node", "actions": [create]},
        ],
    }
    with pytest.raises(ValueError, match="already created"):
        validate_scene_plan(plan)


def test_measurement_and_timeline_use_actual_wav_durations(tmp_path: Path) -> None:
    audio = tmp_path / "segment.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\0\0" * 22050)
    assert get_audio_duration(audio) == 1.0
    plan = {"topic": "Test", "segments": [{"id": "s1", "narration": "narration", "subtitle": "subtitle", "actions": []}]}
    timeline = create_master_timeline(plan, [{"audio_duration": get_audio_duration(audio), "audio_path": str(audio)}])
    validate_timeline(timeline)
    assert timeline["segments"][0]["timeline"] == {"start": 0.0, "end": 1.0}


def test_timeline_rejects_visual_actions_longer_than_audio(tmp_path: Path) -> None:
    plan = {
        "topic": "Test",
        "segments": [{"id": "s1", "narration": "short", "actions": [{"type": "highlight", "target": "n", "duration": 2.0}]}],
    }
    with pytest.raises(ValueError, match="only 1.00s"):
        create_master_timeline(plan, [{"audio_duration": 1.0, "audio_path": str(tmp_path / "s.wav")}])


def test_srt_uses_timeline_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "lesson.srt"
    timeline = {
        "topic": "Test",
        "duration": 2.25,
        "segments": [
            {
                "id": "s1",
                "subtitle": "Balanced tree.",
                "audio": {"duration": 2.25},
                "timeline": {"start": 0.0, "end": 2.25},
                "visual": {"actions": []},
            }
        ],
    }
    create_srt_file(timeline, path)
    assert path.read_text(encoding="utf-8").splitlines()[:3] == ["1", "00:00:00,000 --> 00:00:02,250", "Balanced tree."]
    assert format_srt_timestamp(3661.125) == "01:01:01,125"
