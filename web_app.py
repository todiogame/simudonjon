from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ui_runtime import GameSession


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "ui_static"

app = FastAPI(title="SimuDonjon UI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

sessions = {}


class GameCreate(BaseModel):
    mode: str = "random"
    playerName: str = "Human"
    playerCount: int = 4
    seed: int | None = None
    botDelayMs: int = 800
    partyRounds: int | None = None


class DecisionSubmit(BaseModel):
    decisionId: str
    optionId: str


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/metadata")
def metadata():
    return {
        "modes": [
            {"id": "random", "label": "Random"},
            {"id": "draft", "label": "Draft"},
            {"id": "party", "label": "Party"},
        ],
        "playerCounts": [3, 4],
        "ai": [
            {
                "id": "teacher_best",
                "label": "Teacher best",
                "description": "Uses the strongest teacher-style bot profile available in the UI branch.",
            }
        ],
    }


@app.post("/api/games")
def create_game(payload: GameCreate):
    if payload.mode not in {"random", "draft", "party"}:
        raise HTTPException(status_code=400, detail="Unknown mode.")
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    session = GameSession(data)
    sessions[session.id] = session
    session.start()
    return session.snapshot()


def get_session(session_id: str) -> GameSession:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@app.get("/api/games/{session_id}")
def get_game(session_id: str):
    return get_session(session_id).snapshot()


@app.get("/api/games/{session_id}/events")
def get_events(session_id: str, after: int = 0, level: str = "full"):
    if level not in {"basic", "full"}:
        raise HTTPException(status_code=400, detail="level must be basic or full.")
    return {"events": get_session(session_id).events_after(after, level)}


@app.post("/api/games/{session_id}/decision")
def submit_decision(session_id: str, payload: DecisionSubmit):
    session = get_session(session_id)
    try:
        session.submit_decision(payload.decisionId, payload.optionId)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@app.delete("/api/games/{session_id}")
def delete_game(session_id: str):
    session = get_session(session_id)
    session.cancel()
    sessions.pop(session_id, None)
    return {"ok": True}
