from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    content: str = ""
    source: str = ""
    score: float = 0.0


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, description="用户问题")
    user_id: str = Field(default="", description="用户ID")
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
