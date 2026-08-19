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
