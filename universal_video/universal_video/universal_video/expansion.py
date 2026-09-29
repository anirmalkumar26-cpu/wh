"""Expand assessed source text when Gemini determines it needs teaching context."""

from __future__ import annotations

from typing import Any


def expand_source(client: Any, model: str, text: str, target: float) -> str:
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=(f"Expand this source into an accurate, self-contained teaching "
                  f"script of about {target:.0f} seconds at 130 words per minute. "
                  "Keep the original intent, add only useful explanations, and "
                  "return plain text.\n\nSOURCE:\n" + text),
        config=types.GenerateContentConfig(temperature=0.3),
    )
    return getattr(response, "text", "").strip() or text
