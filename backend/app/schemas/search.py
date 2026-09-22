"""Search Request, Response, and Result Pydantic Schemas"""
import uuid
from datetime import datetime
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class SearchCreate(BaseModel):
    query: str = Field(..., min_length=2, description="Business name, website URL, or free-text description")
    location: Optional[str] = Field(None, description="City, region, or country (optional; inferred if missing)")
    num_competitors: int = Field(10, ge=3, le=50, description="Desired competitor count (3 to 50, capped by plan tier)")
    scope_override: Optional[Literal["auto", "local", "national", "global"]] = Field(
        "auto", description="Scope override"
    )
    competitor_types: Optional[List[Literal["direct", "indirect", "leader"]]] = Field(
        default=["direct", "indirect", "leader"],
        description="Filter by competitor classification"
    )
    idempotency_key: Optional[str] = Field(None, description="Client-provided idempotency key")


class SearchResultItem(BaseModel):
    id: uuid.UUID
    competitor_name: str
    domain: str
    competitor_type: Literal["direct", "indirect", "leader"]
    match_score: float = Field(..., ge=0, le=100)
    reason: str
    source_url: str
    verified_at: datetime
    metadata_json: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class ClarifyingQuestion(BaseModel):
    question: str
    options: Optional[List[str]] = None
    context: Optional[str] = None


class SearchRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    query: str
    location: Optional[str]
    num_competitors: int
    scope_override: Optional[str]
    competitor_types: Optional[List[str]]
    status: Literal["queued", "running", "completed", "failed", "clarification_needed"]
    tier: str
    estimated_cost: float
    actual_cost: float
    shortfall: bool
    shortfall_reason: Optional[str]
    clarifying_question: Optional[str]
    providers_used: Optional[List[str]]
    error_message: Optional[str] = None
    results: List[SearchResultItem] = []
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SearchEvent(BaseModel):
    event: Literal["profile", "clarification_needed", "candidate_progress", "result", "done", "error"]
    data: Dict[str, Any]
