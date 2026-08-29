import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DocumentStatus, Role


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    name: str
    role: Role


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    page_count: int | None
    error: str | None
    metadata_: dict
    created_at: datetime


class Citation(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    page_number: int | None
    excerpt: str
    relevance: float


class GenerateRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    mode: Literal["portfolio_summary", "risk_insight", "client_communication", "question"] = "question"
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    top_k: int = Field(default=6, ge=1, le=12)


class GenerateResponse(BaseModel):
    id: uuid.UUID
    answer: str
    citations: list[Citation]
    model: str


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str | None
    detail: dict
    created_at: datetime

