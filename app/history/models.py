from datetime import datetime

from pydantic import BaseModel, Field


class ScoreHistoryEntry(BaseModel):
    id: int = Field(ge=1)
    symbol: str = Field(min_length=1, max_length=12)
    total_score: float = Field(ge=0, le=100)
    grade: str
    decision: str
    methodology_version: str = "legacy"
    created_at: datetime
