from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    content: str = ""
    source: str = ""
    score: float = 0.0


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, description="用户问题")
    user_id: str = Field(default="", description="用户ID")
    session_id: str = Field(default="", description="会话ID，建议前端透传")
    location: str = Field(default="", description="地域信息，可选")
    rag: bool = Field(default=True, description="是否启用RAG链路")


class ChatResponse(BaseModel):
    answer: str
    citations: List[CitationItem] = Field(default_factory=list)
    need_followup: bool = False
    followup_questions: List[str] = Field(default_factory=list)
    session_id: str = ""


class IntentDebugRequest(BaseModel):
    query: str = Field(min_length=1)


class RetrievalDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    user_id: str = ""
    location: str = ""


class KGDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = 3


class RouterDebugRequest(BaseModel):
    intent: str = ""
    domain: str = "unclear"


class PromptRAGDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    intent_packet: Dict[str, Any] = Field(default_factory=dict)
    retrieval_hits: List[Dict[str, Any]] = Field(default_factory=list)
    kg_hits: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[Dict[str, str]] = Field(default_factory=list)
    target: str = "agri_expert"


class PromptDirectDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    history: List[Dict[str, str]] = Field(default_factory=list)


class LLMDebugRequest(BaseModel):
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
