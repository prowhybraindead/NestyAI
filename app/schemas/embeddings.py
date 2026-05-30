from __future__ import annotations

from pydantic import BaseModel, Field


class EmbeddingResult(BaseModel):
    provider: str
    model: str
    embedding: list[float] = Field(default_factory=list)
    dimensions: int
    usage: dict | None = None
    latency_ms: int | None = None
