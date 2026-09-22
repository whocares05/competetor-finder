"""Authentication and Organization Pydantic Schemas"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None
    org_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class OrgRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan_tier: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime
    active_org: Optional[OrgRead] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class TokenPayload(BaseModel):
    sub: str  # user_id
    org_id: str
    email: str
    exp: int
