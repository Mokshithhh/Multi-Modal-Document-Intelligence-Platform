from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    created_at: datetime


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    filename: str
    file_size: int
    file_type: str
    status: str
    error_message: str | None
    created_at: datetime


class Citation(BaseModel):
    document_id: UUID
    filename: str
    page_number: int
    snippet_text: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: str
    citations: list[Citation]
    retrieval_latency_ms: float
