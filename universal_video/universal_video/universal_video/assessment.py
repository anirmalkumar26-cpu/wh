"""Assess educational source text with Gemini."""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from .models import Assessment
except ImportError:
    from models import Assessment

ASSESSMENT_SCHEMA = {
    "type": "object",
    "required": ["difficulty", "target_duration", "needs_expansion"],
    "properties": {
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "target_duration": {"type": "number"},
        "needs_expansion": {"type": "boolean"},
        "reason": {"type": "string"},
    },
}


def fallback_duration(text: str) -> float:
    return min(600.0, max(90.0, len(text.split()) / 2.0))


def _json_response(response: Any) -> dict[str, Any]:
    if not getattr(response, "text", None):
        raise RuntimeError("Gemini returned an empty response.")
    return json.loads(response.text)


def assess_source(client: Any, model: str, text: str) -> Assessment:
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=("Assess this educational source. Choose a difficulty, a realistic "
                  "target duration in seconds, and whether it needs expansion to "
                  "teach the topic clearly. Return JSON only.\n\nSOURCE:\n" + text),
        config=types.GenerateContentConfig(
            temperature=0.2, response_mime_type="application/json",
            response_schema=ASSESSMENT_SCHEMA,
        ),
    )
    result = _json_response(response)
    result["target_duration"] = max(
        30.0, min(600.0, float(result.get("target_duration", fallback_duration(text))))
    )
    return result


def assess_file(input_path, model: str) -> tuple[str, Assessment, Any]:
    """Read a source, require the API key, and return text, assessment, client."""
    from google import genai

    text = input_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{input_path} is empty.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY before generating a plan.")
    client = genai.Client(api_key=api_key)
    return text, assess_source(client, model, text), client
