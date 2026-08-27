from fastapi.testclient import TestClient


def test_create_session_returns_201(client: TestClient) -> None:
    response = client.post("/api/sessions", json={"title": "Retention strategy"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Retention strategy"
    assert payload["message_count"] == 0
    assert "id" in payload


def test_create_and_list_messages(client: TestClient) -> None:
    session_response = client.post("/api/sessions", json={"title": "PMF chat"})
    session_id = session_response.json()["id"]

    user_message = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "user", "content": "How do guests describe PMF?"},
    )
    assistant_message = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "assistant", "content": "Guests often emphasize customer pull."},
    )
    history_response = client.get(f"/api/sessions/{session_id}")

    assert user_message.status_code == 201
    assert assistant_message.status_code == 201
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["message_count"] == 2
    assert len(history["messages"]) == 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"


def test_multiple_sessions_remain_independent(client: TestClient) -> None:
    first_session = client.post("/api/sessions", json={"title": "Session A"}).json()["id"]
    second_session = client.post("/api/sessions", json={"title": "Session B"}).json()["id"]

    client.post(
        f"/api/sessions/{first_session}/messages",
        json={"role": "user", "content": "Question for session A"},
    )
    client.post(
        f"/api/sessions/{second_session}/messages",
        json={"role": "user", "content": "Question for session B"},
    )

    first_history = client.get(f"/api/sessions/{first_session}").json()
    second_history = client.get(f"/api/sessions/{second_session}").json()
    sessions = client.get("/api/sessions").json()

    assert first_history["message_count"] == 1
    assert second_history["message_count"] == 1
    assert first_history["messages"][0]["content"] == "Question for session A"
    assert second_history["messages"][0]["content"] == "Question for session B"
    assert {session["title"] for session in sessions} == {"Session A", "Session B"}


def test_invalid_message_role_returns_422(client: TestClient) -> None:
    session_id = client.post("/api/sessions", json={}).json()["id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "moderator", "content": "Not allowed"},
    )

    assert response.status_code == 422


def test_missing_session_returns_404(client: TestClient) -> None:
    response = client.get("/api/sessions/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404


def test_delete_session_removes_it_and_its_messages(client: TestClient) -> None:
    session_id = client.post("/api/sessions", json={"title": "To delete"}).json()["id"]
    client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "user", "content": "This should be deleted too"},
    )

    delete_response = client.delete(f"/api/sessions/{session_id}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/sessions/{session_id}")
    assert get_response.status_code == 404

    sessions = client.get("/api/sessions").json()
    assert session_id not in {s["id"] for s in sessions}


def test_delete_missing_session_returns_404(client: TestClient) -> None:
    response = client.delete("/api/sessions/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404


def test_deleting_one_session_leaves_others_intact(client: TestClient) -> None:
    keep_id = client.post("/api/sessions", json={"title": "Keep me"}).json()["id"]
    delete_id = client.post("/api/sessions", json={"title": "Delete me"}).json()["id"]

    client.delete(f"/api/sessions/{delete_id}")

    sessions = client.get("/api/sessions").json()
    assert {s["id"] for s in sessions} == {keep_id}
