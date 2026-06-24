"""
HealthcareADK Chat API — FastAPI wrapper around the OrchestratorAgent.

Run locally:
    uvicorn api.main:app --reload --port 8000

Then open http://localhost:8000 in your browser.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from client.agents.orchestrator import run_with_meta
from client.api.models import ChatRequest, ChatResponse

load_dotenv()

app = FastAPI(title="HealthcareADK Chat API")

# CORS: UI is served from the same origin so only localhost needs to be listed.
# "null" (file://) is intentionally dropped — no longer needed.
# Override via HEALTHCAREADK_CORS_ORIGINS (comma-separated) for other environments.
_raw_origins = os.environ.get(
    "HEALTHCAREADK_CORS_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _raw_origins.split(",")],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# In-memory registry of session IDs issued by this server instance.
# Presented session IDs not in this set are treated as unknown and start fresh.
_issued_sessions: set[str] = set()


def _require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("HEALTHCAREADK_API_KEY")
    if not expected:
        raise RuntimeError("HEALTHCAREADK_API_KEY is not set — configure it in .env")
    if not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(_require_api_key)])
def chat(request: ChatRequest) -> ChatResponse:
    """Dispatch a chat message through the OrchestratorAgent.

    Defined as a sync endpoint (not async def) so FastAPI runs it in its worker
    thread pool — run_with_meta() makes blocking Anthropic API and pyodbc calls
    and must not run directly on the event loop.
    """
    # Only honour a session_id that this server issued; reject fabricated IDs.
    session_id = request.session_id if request.session_id in _issued_sessions else None

    response_text, agents, session_id = run_with_meta(request.message, session_id)
    _issued_sessions.add(session_id)
    return ChatResponse(response=response_text, session_id=session_id, agents=agents)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Serve the chat UI at http://localhost:8000 — mount last so API routes take priority.
_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")
