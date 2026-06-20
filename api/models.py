"""Pydantic request/response models for the HealthcareADK chat API."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's natural-language request")
    session_id: str | None = Field(
        default=None, description="Session ID from a prior turn; omit on the first message"
    )


class ChatResponse(BaseModel):
    response: str
    session_id: str
    agents: list[str]
