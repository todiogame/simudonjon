import time

from fastapi.testclient import TestClient

from web_app import app, sessions


def test_metadata_exposes_available_ai_profiles():
    client = TestClient(app)

    response = client.get("/api/metadata")

    assert response.status_code == 200
    ai_ids = {row["id"] for row in response.json()["ai"]}
    assert {"teacher_best", "baseline", "ismcts_prof", "ismcts_prof_fast"} <= ai_ids


def test_api_game_flow_finishes_with_default_choices():
    sessions.clear()
    client = TestClient(app)

    response = client.post(
        "/api/games",
        json={
            "mode": "random",
            "playerName": "ApiTester",
            "playerCount": 3,
            "seed": 7,
            "botDelayMs": 0,
        },
    )
    assert response.status_code == 200
    session_id = response.json()["id"]

    deadline = time.time() + 30
    while time.time() < deadline:
        snap = client.get(f"/api/games/{session_id}").json()
        if snap["pendingDecision"]:
            decision = snap["pendingDecision"]
            submit = client.post(
                f"/api/games/{session_id}/decision",
                json={
                    "decisionId": decision["id"],
                    "optionId": decision["defaultId"],
                },
            )
            assert submit.status_code == 200
        if snap["status"] in {"finished", "error", "cancelled"}:
            break
        time.sleep(0.01)

    snap = client.get(f"/api/games/{session_id}").json()
    assert snap["status"] == "finished", snap.get("error")
    assert snap["result"]["winner"] is not None

    events = client.get(f"/api/games/{session_id}/events?level=basic").json()["events"]
    assert any(event["kind"] == "finished" for event in events)


def test_api_game_flow_accepts_ismcts_iteration_override():
    sessions.clear()
    client = TestClient(app)

    response = client.post(
        "/api/games",
        json={
            "mode": "random",
            "playerName": "ApiTester",
            "playerCount": 3,
            "seed": 123,
            "botDelayMs": 0,
            "ismctsIterations": 5,
            "ismctsMaxSeconds": 5,
            "botStrategies": ["ismcts_prof", "baseline"],
        },
    )
    assert response.status_code == 200
    session_id = response.json()["id"]

    deadline = time.time() + 30
    while time.time() < deadline:
        snap = client.get(f"/api/games/{session_id}").json()
        if snap["pendingDecision"]:
            decision = snap["pendingDecision"]
            submit = client.post(
                f"/api/games/{session_id}/decision",
                json={
                    "decisionId": decision["id"],
                    "optionId": decision["defaultId"],
                },
            )
            assert submit.status_code == 200
        if snap["status"] in {"finished", "error", "cancelled"}:
            break
        time.sleep(0.01)

    snap = client.get(f"/api/games/{session_id}").json()
    assert snap["status"] == "finished", snap.get("error")
    events = client.get(f"/api/games/{session_id}/events?level=basic").json()["events"]
    assert any(event["kind"] == "bot_thinking" for event in events)
    assert any(event["kind"] == "bot_thinking_progress" for event in events)
