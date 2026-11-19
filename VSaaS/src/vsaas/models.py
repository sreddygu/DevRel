"""
Pydantic models used by the VSaaS Cloud API.

These models define the request bodies for `/events` and `/query`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    id: str
    ts_ms: int
    camera_id: str
    event_type: str
    severity: str = Field(default="low")
    summary: str
    payload: dict = Field(default_factory=dict)


class EventsIn(BaseModel):
    events: list[EventIn]


class QueryIn(BaseModel):
    question: str


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMessage]
    include_events: bool = True
    max_events: int = Field(default=20, ge=0, le=200)
    max_tokens: int = Field(default=384, ge=16, le=2048)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    use_fallback_summary: bool = True
