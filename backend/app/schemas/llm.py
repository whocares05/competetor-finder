"""Strict Pydantic Schemas for LLM Structured Outputs

CRITICAL: The LLM never invents facts from memory. All candidate extractions
and evaluations are strictly validated through these Pydantic schemas.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class BusinessProfileSchema(BaseModel):
    """Schema for Stage 1 (Understand input)."""
    business_name: Optional[str] = Field(None, description="Inferred business name if mentioned")
    business_type: str = Field(..., description="Core industry/category (e.g. 'project management SaaS')")
    offerings: List[str] = Field(default_factory=list, description="List of primary products, features, or services")
    customer_type: Literal["B2B", "B2C", "both"] = Field(
        ..., description="Target customer segment"
    )
    location: Optional[str] = Field(None, description="City or region name if applicable")
    country_code: Optional[str] = Field(None, description="ISO two-letter country code (e.g. 'US', 'DE', 'PK')")
    language: str = Field("en", description="Primary language of the query/business")
    scope_guess: Literal["local", "national", "global"] = Field(
        ..., description="Inferred scope of the business"
    )
    search_keywords: List[str] = Field(
        default_factory=list, description="Target search terms for finding alternatives and category rivals"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score from 0 to 1 in understanding the query"
    )
    clarifying_question: Optional[str] = Field(
        None, description="One single targeted question if confidence is below 0.6"
    )


class ExtractedCandidate(BaseModel):
    """Single candidate extracted strictly from scraped page text."""
    name: str = Field(..., description="Company or product name")
    domain: Optional[str] = Field(None, description="Website domain or URL if present in text")
    context_snippet: str = Field(..., description="Brief extract from page demonstrating relevance")


class CandidateExtractionResponse(BaseModel):
    """Schema for Stage 7 (Candidate extraction from text)."""
    candidates: List[ExtractedCandidate] = Field(default_factory=list)


class CompactCandidateCard(BaseModel):
    """Input payload to LLM judge in Stage 11."""
    name: str
    domain: str
    description: str = Field(..., max_length=1000)
    source_url: str
    is_synthetic_domain: bool = False


class JudgeCompetitorItem(BaseModel):
    """Evaluation of a single competitor candidate by the LLM judge."""
    name: str
    domain: str
    type: Literal["direct", "indirect", "leader"]
    match_score: float = Field(..., ge=0.0, le=100.0, description="Match score from 0 to 100")
    reason: str = Field(..., description="Concise one-line reason justifying classification and match")
    source_url: str = Field(..., description="Supporting source URL verifying existence and rivalry")
    is_competitor: bool = Field(..., description="False if this is a false positive, aggregator, or non-rival")


class JudgeOutputSchema(BaseModel):
    """Strict schema for Stage 11 LLM judge response."""
    competitors: List[JudgeCompetitorItem] = Field(default_factory=list)
    shortfall: bool = Field(
        False, description="True if fewer than requested competitors could be verified"
    )
    shortfall_explanation: Optional[str] = Field(
        None, description="Explanation when shortfall is true"
    )
    judge_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score; escalates to stronger model if low in paid tier"
    )
