"""Generate and normalise the visual scene plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .assessment import assess_file
    from .config import ELEMENT_TYPES, ensure_directory
    from .expansion import expand_source
except ImportError:
    from assessment import assess_file
    from config import ELEMENT_TYPES, ensure_directory
    from expansion import expand_source

SCENE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "scenes"],
    "properties": {
        "title": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["narration", "subtitle", "duration", "elements"],
                "properties": {
                    "narration": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "duration": {"type": "number"},
                    "elements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": sorted(ELEMENT_TYPES),
                                },
                                "text": {"type": "string"},
                                "position": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "color": {"type": "string"},
                                "width": {"type": "number"},
                                "height": {"type": "number"},
                                "radius": {"type": "number"},
                                "inner_radius": {"type": "number"},
                                "outer_radius": {"type": "number"},
                                "start_angle": {"type": "number"},
                                "angle": {"type": "number"},
                                "num_points": {"type": "integer"},
                                "fill_opacity": {"type": "number"},
                                "stroke_width": {"type": "number"},
                                "x_range": {"type": "array", "items": {"type": "number"}},
                                "y_range": {"type": "array", "items": {"type": "number"}},
                                "labels": {"type": "array", "items": {"type": "string"}},
                                "end": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "points": {
                                    "type": "array",
                                    "items": {"type": "array", "items": {"type": "number"},
                                              "minItems": 2, "maxItems": 2},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def _json_response(response: Any) -> dict[str, Any]:
    if not getattr(response, "text", None):
        raise RuntimeError("Gemini returned an empty response.")
    return json.loads(response.text)


def normalise_plan(plan: dict[str, Any], target_duration: float,
                   difficulty: str = "medium") -> dict[str, Any]:
    scenes = plan.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Gemini returned no scenes.")
    normalised = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        safe = []
        elements = scene.get("elements", [])
        for element in elements if isinstance(elements, list) else []:
            if not isinstance(element, dict) or element.get("type") not in ELEMENT_TYPES:
                continue
            item = dict(element)
            position = item.get("position", [0, 0])
            if not isinstance(position, list) or len(position) < 2:
                position = [0, 0]
            item["position"] = [max(-6.5, min(6.5, float(position[0]))),
                                max(-3.5, min(3.5, float(position[1])))]
            safe.append(item)
        narration = str(scene.get("narration", "")).strip()
        if narration:
            normalised.append({
                "narration": narration,
                "subtitle": str(scene.get("subtitle", narration)).strip() or narration,
                "duration": max(1.0, min(90.0, float(scene.get("duration", 5)))),
                "elements": safe,
            })
    if not normalised:
        raise ValueError("Gemini returned no usable scenes.")
    total = sum(item["duration"] for item in normalised)
    if total < target_duration:
        scale = target_duration / total
        for item in normalised:
            item["duration"] = round(min(90.0, item["duration"] * scale), 2)
    segments, start = [], 0.0
    for index, item in enumerate(normalised):
        end = round(start + item["duration"], 2)
        segments.append({"index": index, "start": round(start, 2), "end": end,
                         "narration": item["narration"], "subtitle": item["subtitle"]})
        start = end
    return {"title": str(plan.get("title", "Generated lesson")), "difficulty": difficulty,
            "target_duration": target_duration, "scenes": normalised, "segments": segments}


def create_plan(input_path: Path, output_path: Path, model: str) -> dict[str, Any]:
    text, assessment, client = assess_file(input_path, model)
    target = assessment["target_duration"]
    source = expand_source(client, model, text, target) if assessment.get("needs_expansion") else text
    from google.genai import types
    response = client.models.generate_content(
        model=model,
        contents=(f"Create 4-24 educational animation scenes for a {assessment.get('difficulty', 'medium')} "
                  f"topic lasting about {target:.0f} seconds. Use the source below. Each scene needs "
                  "natural narration, a concise subtitle (one or two lines), and 2-8 varied "
                  "supported visual elements. Prefer a mix of text/labels, geometric shapes, "
                  "arrows or lines, stars, arcs, dots, and axes when they clarify the lesson. "
                  "Use explicit safe types and simple named or hex colors. Add motion-friendly "
                  "layouts with coordinates x -6..6, y -3..3. Return JSON matching the schema.\n\nSOURCE:\n" + source),
        config=types.GenerateContentConfig(temperature=0.3, response_mime_type="application/json",
                                            response_schema=SCENE_SCHEMA),
    )
    result = normalise_plan(_json_response(response), target, str(assessment.get("difficulty", "medium")))
    ensure_directory(output_path.parent)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
