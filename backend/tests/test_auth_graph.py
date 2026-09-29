from fastapi.testclient import TestClient

from backend.app.services.auth import create_staff
from backend.tests.conftest import headers, register


def test_login_refresh_rotation_and_logout(client: TestClient) -> None:
    token, registration = register(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "StrongPass1234"},
    )
    assert login.status_code == 200
    new_pair = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert new_pair.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers(login.json()["access_token"])).status_code == 401
    old_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert old_refresh.status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(new_pair.json()["access_token"])).status_code == 401
    second_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "StrongPass1234"},
    )
    logout = client.post("/api/v1/auth/logout", headers=headers(second_login.json()["access_token"]))
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers(second_login.json()["access_token"])).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(token)).status_code == 200


def test_prerequisite_cycle_is_rejected(client: TestClient) -> None:
    with client.app.state.session_factory() as session:
        create_staff(session, "graph-teacher@example.com", "GraphTeacher12345", "teacher")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "graph-teacher@example.com", "password": "GraphTeacher12345"},
    )
    token = login.json()["access_token"]
    auth = headers(token)
    first = client.post("/api/v1/knowledge-graph/concepts", headers=auth, json={"name": "Concept A"}).json()
    second = client.post("/api/v1/knowledge-graph/concepts", headers=auth, json={"name": "Concept B"}).json()
    assert client.post(
        "/api/v1/knowledge-graph/relationships",
        headers=auth,
        json={"source_id": first["id"], "target_id": second["id"], "relation_type": "prerequisite"},
    ).status_code == 201
    cycle = client.post(
        "/api/v1/knowledge-graph/relationships",
        headers=auth,
        json={"source_id": second["id"], "target_id": first["id"], "relation_type": "prerequisite"},
    )
    assert cycle.status_code == 422
    assert "cycle" in cycle.json()["detail"]


def test_only_admin_can_create_staff_accounts(client: TestClient) -> None:
    with client.app.state.session_factory() as session:
        create_staff(session, "admin@example.com", "AdminPass12345", "administrator")
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass12345"},
    )
    assert admin_login.status_code == 200
    created = client.post(
        "/api/v1/admin/users",
        headers=headers(admin_login.json()["access_token"]),
        json={"email": "teacher@example.com", "password": "TeacherPass12345", "role": "teacher"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "teacher"
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@example.com", "password": "TeacherPass12345"},
    )
    forbidden = client.post(
        "/api/v1/admin/users",
        headers=headers(teacher_login.json()["access_token"]),
        json={"email": "another@example.com", "password": "AnotherPass12345", "role": "teacher"},
    )
    assert forbidden.status_code == 403


def test_invalid_credentials_and_duplicate_registration_are_rejected(client: TestClient) -> None:
    token, _ = register(client)
    assert token
    invalid_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "IncorrectPass123"},
    )
    assert invalid_login.status_code == 401
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": "student@example.com", "password": "DifferentPass123"},
    )
    assert duplicate.status_code == 409
