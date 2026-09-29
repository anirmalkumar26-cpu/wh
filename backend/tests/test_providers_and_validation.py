from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.ai import providers
from backend.app.ai.providers import MockLessonProvider
from backend.app.schemas import LessonContent, LessonRequest
from backend.tests.conftest import headers, register


def test_mock_provider_is_selected_without_paid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        providers,
        "settings",
        SimpleNamespace(ai_provider="auto", gemini_api_key=None),
    )
    assert isinstance(providers.configured_provider(), MockLessonProvider)


def test_explicit_gemini_selection_still_starts_in_development_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        providers,
        "settings",
        SimpleNamespace(ai_provider="gemini", gemini_api_key=None, environment="development"),
    )
    assert isinstance(providers.configured_provider(), MockLessonProvider)


def test_topic_and_text_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="not both"):
        LessonRequest(topic="Trees", text="My notes", depth="beginner")
    with pytest.raises(ValueError, match="Provide a topic or text"):
        LessonRequest(topic="  ", text=None)


def test_lesson_output_schema_rejects_incomplete_provider_data() -> None:
    with pytest.raises(ValidationError):
        LessonContent.model_validate({"overview": "Only a partial response"})


def test_text_lesson_preserves_notes_and_invalid_lesson_is_rejected(client: TestClient) -> None:
    token, _ = register(client)
    response = client.post(
        "/api/v1/lessons",
        headers=headers(token),
        json={"text": "A binary search tree keeps smaller keys on the left.", "depth": "beginner"},
    )
    assert response.status_code == 201
    lesson = response.json()
    assert "keeps smaller keys on the left" in lesson["content"]["overview"]
    invalid = client.post(
        "/api/v1/lessons",
        headers=headers(token),
        json={"topic": "", "text": ""},
    )
    assert invalid.status_code == 422
