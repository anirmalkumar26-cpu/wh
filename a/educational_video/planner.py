import json
import math
from pathlib import Path
from typing import Any

from educational_video.content import generate_educational_content

AVL_IDS = {"node_10", "node_20", "node_30"}


def create_scene_plan(topic: str, content: list[dict[str, Any]]) -> dict[str, Any]:
    plan = {
        "schema_version": 1,
        "topic": topic,
        "objects": [
            {"id": "node_10", "kind": "tree_node", "value": "10"},
            {"id": "node_20", "kind": "tree_node", "value": "20"},
            {"id": "node_30", "kind": "tree_node", "value": "30"},
        ],
        "segments": content,
    }
    validate_scene_plan(plan)
    return plan


def plan_from_input(data: dict[str, Any]) -> dict[str, Any]:
    return create_scene_plan(data["topic"], generate_educational_content(data))


def validate_scene_plan(plan: dict[str, Any]) -> None:
    if not isinstance(plan, dict) or not isinstance(plan.get("topic"), str) or not plan["topic"].strip():
        raise ValueError("scene plan needs a non-empty topic")
    if not isinstance(plan.get("objects"), list) or not isinstance(plan.get("segments"), list):
        raise ValueError("scene plan objects and segments must be lists")
    if any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip()
        for item in plan["objects"]
    ):
        raise ValueError("each scene-plan object needs a non-empty string ID")
    object_ids = [item.get("id") for item in plan.get("objects", [])]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("scene plan contains duplicate visual object IDs")
    known_ids = set(object_ids)
    if not plan.get("segments"):
        raise ValueError("scene plan has no segments")
    visible_nodes: set[str] = set()
    relationships: dict[str, tuple[str, str]] = {}
    segment_ids: set[str] = set()
    for segment in plan["segments"]:
        if not isinstance(segment, dict) or not isinstance(segment.get("id"), str) or not segment["id"].strip() or not isinstance(
            segment.get("narration"), str
        ) or not segment["narration"].strip():
            raise ValueError("each segment must have an ID and narration")
        if segment["id"] in segment_ids:
            raise ValueError(f"scene plan contains duplicate segment ID {segment['id']!r}")
        segment_ids.add(segment["id"])
        if not isinstance(segment.get("actions", []), list):
            raise ValueError(f"segment {segment['id']}: actions must be a list")
        for action in segment.get("actions", []):
            if not isinstance(action, dict):
                raise ValueError(f"segment {segment['id']}: each action must be an object")
            kind = action.get("type")
            target = action.get("target")
            if not isinstance(kind, str):
                raise ValueError(f"segment {segment['id']}: action type must be a string")
            if kind in {"create_node", "highlight", "rotate_right"} and not isinstance(target, str):
                raise ValueError(f"segment {segment['id']}: action target must be a string ID")
            if kind in {"create_node", "highlight", "rotate_right"} and target not in known_ids:
                raise ValueError(f"segment {segment['id']}: unknown action target {target!r}")
            if kind == "create_node" and target not in AVL_IDS:
                raise ValueError(f"segment {segment['id']}: unsupported node identity {target!r}")
            if kind == "create_node":
                if target in visible_nodes:
                    raise ValueError(f"segment {segment['id']}: node identity {target!r} was already created")
                visible_nodes.add(target)
            if kind == "connect":
                source, destination = action.get("source"), action.get("destination")
                if not isinstance(target, str) or not target:
                    raise ValueError(f"segment {segment['id']}: relationship needs a non-empty string ID")
                if not isinstance(source, str) or not isinstance(destination, str) or source not in known_ids or destination not in known_ids:
                    raise ValueError(f"segment {segment['id']}: relationship references an unknown node")
                if source not in visible_nodes or destination not in visible_nodes:
                    raise ValueError(f"segment {segment['id']}: relationship endpoints must be created before connecting")
                if target in relationships:
                    raise ValueError(f"segment {segment['id']}: relationship identity {target!r} was already created")
                relationships[target] = (source, destination)
            if kind == "highlight" and target not in visible_nodes:
                raise ValueError(f"segment {segment['id']}: cannot highlight node {target!r} before it is created")
            if kind == "rotate_right":
                pivot = action.get("pivot")
                if not isinstance(pivot, str) or pivot not in known_ids:
                    raise ValueError(f"segment {segment['id']}: rotation references an unknown pivot")
                if target not in visible_nodes or pivot not in visible_nodes:
                    raise ValueError(f"segment {segment['id']}: rotation nodes must be created first")
                root_edge = next(
                    (edge_id for edge_id, endpoints in relationships.items() if endpoints == (target, pivot)),
                    None,
                )
                pivot_child = next(
                    (edge_id for edge_id, endpoints in relationships.items() if endpoints == (pivot, "node_10")),
                    None,
                )
                if root_edge is None or pivot_child is None:
                    raise ValueError(f"segment {segment['id']}: right rotation requires the root-pivot-child chain")
                if "edge_20_30" in relationships and root_edge != "edge_20_30":
                    raise ValueError(f"segment {segment['id']}: rotated relationship ID edge_20_30 already exists")
                del relationships[root_edge]
                relationships["edge_20_30"] = (pivot, target)
            if kind not in {"create_node", "connect", "highlight", "rotate_right"}:
                raise ValueError(f"segment {segment['id']}: unsupported visual action {kind!r}")
            duration = action.get("duration")
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
                raise ValueError(f"segment {segment['id']}: action duration must be positive")
    ids = {segment["id"] for segment in plan["segments"]}
    has_rotation = any(
        action.get("type") == "rotate_right"
        for segment in plan["segments"]
        for action in segment.get("actions", [])
    )
    if has_rotation:
        if not plan["topic"].casefold().startswith("avl"):
            raise ValueError("the right-rotation visual renderer requires an AVL topic")
        for required in ("root", "insert-20", "insert-10", "rotation", "balanced"):
            if required in ids:
                continue
            raise ValueError(f"AVL right-rotation plan is missing required segment {required!r}")


def save_scene_plan(plan: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_scene_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid scene-plan JSON: {exc}") from exc
    validate_scene_plan(plan)
    return plan
