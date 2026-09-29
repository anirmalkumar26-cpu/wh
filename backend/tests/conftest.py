from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.ai.providers import MockLessonProvider
from backend.app.main import create_app


class MockVideo:
    def generate(self, lesson: dict, job_id: str) -> dict:
        return {
            "video_available": False,
            "mock": True,
            "lesson_topic": lesson["topic"],
            "job_id": job_id,
        }


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        lesson_provider=MockLessonProvider(),
        video_adapter=MockVideo(),
    )
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()


def register(client: TestClient, email: str = "student@example.com") -> tuple[str, dict]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass1234"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return data["access_token"], data


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
