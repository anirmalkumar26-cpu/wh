"""Small typed aliases for the JSON documents passed between pipeline stages."""

from __future__ import annotations

from typing import Any, TypedDict

Plan = dict[str, Any]
Segment = dict[str, Any]


class Assessment(TypedDict, total=False):
    difficulty: str
    target_duration: float
    needs_expansion: bool
    reason: str
