import json
from pathlib import Path
from typing import Any


AVL_TOPIC = "AVL tree right rotation"
AVL_SCRIPT = [
    {
        "id": "intro",
        "narration": "AVL trees rebalance after updates.",
        "subtitle": "AVL trees rebalance after updates.",
        "actions": [],
    },
    {
        "id": "root",
        "narration": "Start with 30.",
        "subtitle": "30 is the root.",
        "actions": [
            {"type": "create_node", "target": "node_30", "value": "30", "position": "root", "duration": 0.7}
        ],
    },
    {
        "id": "insert-20",
        "narration": "Insert 20 to its left.",
        "subtitle": "Insert 20 to the left.",
        "actions": [
            {"type": "create_node", "target": "node_20", "value": "20", "position": "left", "duration": 0.65},
            {"type": "connect", "target": "edge_30_20", "source": "node_30", "destination": "node_20", "duration": 0.4},
        ],
    },
    {
        "id": "insert-10",
        "narration": "Place 10 below 20; this left-left chain unbalances 30.",
        "subtitle": "The left-left chain unbalances 30.",
        "actions": [
            {"type": "create_node", "target": "node_10", "value": "10", "position": "left_left", "duration": 0.6},
            {"type": "connect", "target": "edge_20_10", "source": "node_20", "destination": "node_10", "duration": 0.35},
            {"type": "highlight", "target": "node_30", "duration": 0.7},
        ],
    },
    {
        "id": "imbalance",
        "narration": "The left side is two levels taller; 30's balance factor is plus two.",
        "subtitle": "Node 30 has a balance factor of plus two.",
        "actions": [
            {"type": "highlight", "target": "node_30", "duration": 1.0},
        ],
    },
    {
        "id": "rotation",
        "narration": "Rotate right: promote 20, move 30 right, and keep 10 left.",
        "subtitle": "Promote 20; move 30 right and keep 10 left.",
        "actions": [
            {"type": "rotate_right", "target": "node_30", "pivot": "node_20", "duration": 1.5},
        ],
    },
    {
        "id": "balanced",
        "narration": "Now 20 has children 10 and 30, restoring balance.",
        "subtitle": "20 is the root, with children 10 and 30.",
        "actions": [
            {"type": "highlight", "target": "node_20", "duration": 0.6},
            {"type": "highlight", "target": "node_10", "duration": 0.45},
            {"type": "highlight", "target": "node_30", "duration": 0.45},
        ],
    },
]


def load_input_data(input_path: Path | None, topic: str | None) -> dict[str, Any]:
    if input_path is None:
        if topic:
            if topic.casefold() != AVL_TOPIC.casefold():
                raise ValueError("Topic-only content generation is available for the AVL example; provide a script input for other topics")
            return {"topic": topic, "script": AVL_SCRIPT}
        raise ValueError("Provide an input JSON/text script or use the default data/input.json")

    source = input_path.read_text(encoding="utf-8")
    if input_path.suffix.lower() == ".json":
        try:
            data = json.loads(source)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{input_path}: invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{input_path}: top-level JSON value must be an object")
    else:
        data = {"topic": topic or input_path.stem, "script_text": source}
    if topic:
        data["topic"] = topic
    validate_input(data, input_path)
    return data


def validate_input(data: dict[str, Any], source: Path | None = None) -> None:
    label = f"{source}: " if source else ""
    if not isinstance(data.get("topic"), str) or not data["topic"].strip():
        raise ValueError(f"{label}input must provide a non-empty topic")
    script = data.get("script")
    text = data.get("script_text")
    if script is not None:
        if not isinstance(script, list) or not script:
            raise ValueError(f"{label}script must be a non-empty list of segments")
        for index, segment in enumerate(script):
            if not isinstance(segment, dict) or not isinstance(segment.get("narration"), str) or not segment["narration"].strip():
                raise ValueError(f"{label}script segment {index} needs non-empty narration")
            if not isinstance(segment.get("id"), str) or not segment["id"].strip():
                raise ValueError(f"{label}script segment {index} needs a non-empty string ID")
            if "subtitle" in segment and not isinstance(segment["subtitle"], str):
                raise ValueError(f"{label}script segment {index} subtitle must be text")
            if not isinstance(segment.get("actions", []), list):
                raise ValueError(f"{label}script segment {index} actions must be a list")
            if any(not isinstance(action, dict) for action in segment.get("actions", [])):
                raise ValueError(f"{label}script segment {index} actions must contain objects")
    elif not isinstance(text, str) or not text.strip():
        raise ValueError(f"{label}input must provide script segments or non-empty script_text")


def generate_educational_content(data: dict[str, Any]) -> list[dict[str, Any]]:
    validate_input(data)
    if "script" in data:
        return data["script"]
    paragraphs = [part.strip() for part in data["script_text"].splitlines() if part.strip()]
    return [
        {
            "id": f"segment-{index:03d}",
            "narration": paragraph,
            "subtitle": paragraph,
            "actions": [],
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]
