"""
HealthcareADK Chat API — FastAPI wrapper around the OrchestratorAgent.

Run locally:
    uvicorn api.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.orchestrator import run_with_meta
from api.models import ChatRequest, ChatResponse

app = FastAPI(title="HealthcareADK Chat API")

# Local dev only — tighten allow_origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Dispatch a chat message through the OrchestratorAgent.

    Defined as a sync endpoint (not async def) so FastAPI runs it in its worker
    thread pool — run_with_meta() makes blocking Anthropic API and pyodbc calls
    and must not run directly on the event loop.
    """
    response_text, agents, session_id = run_with_meta(request.message, request.session_id)
    return ChatResponse(response=response_text, session_id=session_id, agents=agents)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
