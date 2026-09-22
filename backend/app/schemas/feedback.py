"""Feedback Pydantic Schemas"""
import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    search_id: uuid.UUID
    search_result_id: Optional[uuid.UUID] = None
    feedback_type: Literal["not_a_competitor", "missing_competitor"]
    competitor_name: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)


class FeedbackRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    search_id: uuid.UUID
    search_result_id: Optional[uuid.UUID]
    feedback_type: str
    competitor_name: Optional[str]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
