from collections import deque
import os
from pathlib import Path
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ui_assets import assets_enabled, configured_asset_root
from ui_runtime import (
    GameSession,
    HEURISTIC_STRATEGY_NAME,
    ISMCTS_PROF_FAST_STRATEGY_NAME,
    ISMCTS_PROF_STRATEGY_NAME,
    TEACHER_STRATEGY_NAME,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "ui_static"

app = FastAPI(title="SimuDonjon UI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
ASSET_ROOT = configured_asset_root()
if ASSET_ROOT is not None:
    app.mount("/assets", StaticFiles(directory=ASSET_ROOT), name="assets")

sessions = {}
request_metrics = deque(maxlen=300)


@app.middleware("http")
async def cache_static_assets(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    path = request.url.path
    if path.startswith("/assets/") or path.startswith("/static/assets/"):
        response.headers.setdefault("Cache-Control", "public, max-age=604800, immutable")
    elif path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=3600")
    response.headers["Server-Timing"] = f"app;dur={elapsed_ms}"
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    if path.startswith("/api/"):
        request_metrics.append({
            "ts": time.time(),
            "method": request.method,
            "path": path,
            "query": str(request.url.query),
            "status": response.status_code,
            "elapsedMs": elapsed_ms,
            "contentLength": response.headers.get("content-length"),
        })
    return response


class GameCreate(BaseModel):
    mode: str = "random"
    playerName: str = "Human"
    playerCount: int = 4
    seed: int | None = None
    botDelayMs: int = 800
    ismctsIterations: int | None = None
    ismctsMaxSeconds: int | None = None
    partyRounds: int | None = None
    botStrategies: list[str] | None = None


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
                "id": TEACHER_STRATEGY_NAME,
                "label": "Teacher",
                "description": "Uses the strongest teacher-style bot profile available in the UI branch.",
            },
            {
                "id": HEURISTIC_STRATEGY_NAME,
                "label": "Heuristic",
                "description": "Uses the baseline heuristic bot.",
            },
            {
                "id": ISMCTS_PROF_STRATEGY_NAME,
                "label": "ISMCTS Prof",
                "description": "Uses the clone-based ISMCTS teacher from the full-game branch.",
            },
            {
                "id": ISMCTS_PROF_FAST_STRATEGY_NAME,
                "label": "ISMCTS Prof Fast",
                "description": "Uses fewer ISMCTS iterations for a faster playable opponent.",
            },
        ],
        "assets": {"enabled": assets_enabled()},
    }


@app.get("/api/debug/perf")
def debug_perf():
    return {
        "pid": os.getpid(),
        "threads": threading.active_count(),
        "sessions": {
            session_id: session.debug_snapshot()
            for session_id, session in sessions.items()
        },
        "requests": list(request_metrics)[-80:],
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


@app.get("/api/games/{session_id}/debug")
def get_game_debug(session_id: str):
    return get_session(session_id).debug_snapshot()


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
