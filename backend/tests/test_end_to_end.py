from fastapi.testclient import TestClient

from backend.tests.conftest import headers, register


def test_end_to_end_learning_and_video_job(client: TestClient) -> None:
    token, account = register(client)
    auth = headers(token)
    assert account["user"]["role"] == "student"
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.post(
        "/api/v1/knowledge-graph/concepts",
        headers=auth,
        json={"name": "Student-managed global concept"},
    ).status_code == 403

    lesson_response = client.post(
        "/api/v1/lessons",
        headers=auth,
        json={"topic": "AVL Tree Right Rotation", "depth": "beginner"},
    )
    assert lesson_response.status_code == 201, lesson_response.text
    lesson = lesson_response.json()
    assert lesson["content"]["objectives"]

    graph = client.get("/api/v1/knowledge-graph", headers=auth).json()
    assert {node["name"] for node in graph["nodes"]} >= {
        "AVL Tree Right Rotation",
        "Binary search trees",
        "Tree height and balance factor",
    }
    target = next(node for node in graph["nodes"] if node["name"] == lesson["topic"])
    learning_path = client.post(
        "/api/v1/learning/paths",
        headers=auth,
        params={"target_concept_id": target["id"]},
    )
    assert learning_path.status_code == 201
    assert [item["concept"] for item in learning_path.json()["steps"]][-1] == lesson["topic"]

    assessment_response = client.post(
        "/api/v1/assessments",
        headers=auth,
        json={"lesson_id": lesson["id"], "question_count": 3},
    )
    assert assessment_response.status_code == 201
    assessment = assessment_response.json()
    assert "correct_answer" not in assessment["questions"][0]

    wrong = {question["id"]: "A" for question in assessment["questions"]}
    result = client.post(
        f"/api/v1/assessments/{assessment['id']}/submit",
        headers=auth,
        json={"answers": wrong},
    )
    assert result.status_code == 200
    assert result.json()["percentage"] == 0
    assert result.json()["feedback"][0]["classification"] == "possible_knowledge_gap"

    correct = {question["id"]: "B" for question in assessment["questions"]}
    result = client.post(
        f"/api/v1/assessments/{assessment['id']}/submit",
        headers=auth,
        json={"answers": correct},
    )
    assert result.status_code == 200
    assert result.json()["percentage"] == 100
    progress = client.get("/api/v1/progress", headers=auth).json()
    mastery = next(item for item in progress["concepts"] if item["concept_id"] == target["id"])
    assert mastery["status"] == "developing"
    assert mastery["evidence_count"] == 6

    recommendation = client.get(
        "/api/v1/recommendations",
        headers=auth,
        params={"target_concept_id": target["id"]},
    )
    assert recommendation.status_code == 200
    assert recommendation.json()["items"][0]["concept"] in {
        "Binary search trees",
        "Tree height and balance factor",
    }

    job = client.post("/api/v1/videos/jobs", headers=auth, json={"lesson_id": lesson["id"]})
    assert job.status_code == 202
    status = client.get(f"/api/v1/videos/jobs/{job.json()['id']}", headers=auth).json()
    assert status["status"] == "completed"
    assert status["report"]["mock"] is True


def test_user_data_isolation_and_authentication(client: TestClient) -> None:
    first_token, _ = register(client, "first@example.com")
    second_token, _ = register(client, "second@example.com")
    lesson = client.post(
        "/api/v1/lessons",
        headers=headers(first_token),
        json={"topic": "Sorting"},
    ).json()
    response = client.get(f"/api/v1/lessons/{lesson['id']}", headers=headers(second_token))
    assert response.status_code == 404
    assert client.get("/api/v1/progress").status_code == 401
