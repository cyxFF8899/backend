from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# --- Auth Schemas ---
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Chat Schemas ---
class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Plan Schemas ---
class PlantingPlanCreate(BaseModel):
    crop_name: str = Field(..., max_length=100)
    plan_details: str
    status: str = "进行中"


class PlantingPlanResponse(BaseModel):
    id: int
    user_id: int
    crop_name: str
    plan_details: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Expert Consultation Schemas ---
class ExpertConsultationCreate(BaseModel):
    expert_name: str = Field(..., max_length=50)
    category: str = Field(..., max_length=50)
    content: str


class ExpertConsultationResponse(BaseModel):
    id: int
    user_id: int
    expert_name: str
    category: str
    content: str
    reply: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Schedule Schemas ---
class ScheduleCreate(BaseModel):
    title: str = Field(..., max_length=100)
    content: str
    date: datetime
    is_completed: bool = False


class ScheduleResponse(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    date: datetime
    is_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CitationItem(BaseModel):
    content: str = ""
    source: str = ""
    score: float = 0.0


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, description="用户问题")
    session_id: str = Field(default="", description="会话ID，建议前端透传")
    location: str = Field(default="", description="地区信息，可选")
    rag: bool = Field(default=True, description="是否启用RAG链路")


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationItem] = Field(default_factory=list)
    need_followup: bool = False
    followup_questions: list[str] = Field(default_factory=list)
    session_id: str = ""


class IntentDebugRequest(BaseModel):
    query: str = Field(min_length=1)


class RetrievalDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    user_id: str = ""
    location: str = ""


class GraphDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = 10


class RouterDebugRequest(BaseModel):
    intent: str = ""


class KnowledgeIndexUpdateRequest(BaseModel):
    rebuild: bool = Field(default=True, description="是否重建索引（建议 true，避免重复入库）")


class KnowledgeUploadResponse(BaseModel):
    filename: str
    stored_as: str
    size_bytes: int
    raw_path: str


class KnowledgeIndexResponse(BaseModel):
    indexed_count: int
    ready: bool
    persist_dir: str
    raw_data_dir: str


class PromptRAGDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    location: str = ""
    intent_packet: dict[str, Any] = Field(default_factory=dict)
    retrieval_hits: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, str]] = Field(default_factory=list)
    target: str = "agri_expert"


class PromptDirectDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    location: str = ""
    history: list[dict[str, str]] = Field(default_factory=list)


class LLMDebugRequest(BaseModel):
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
