from __future__ import annotations

import json
from typing import Any, Iterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .schemas import (
    ChatRequest,
    ChatResponse,
    IntentDebugRequest,
    KGDebugRequest,
    LLMDebugRequest,
    PromptDirectDebugRequest,
    PromptRAGDebugRequest,
    RetrievalDebugRequest,
    RouterDebugRequest,
)

router = APIRouter(prefix="/api", tags=["api"])


def _chat_module(request: Request):
    return request.app.state.chat_module


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    return module.chat(
        query=req.query,
        user_id=req.user_id,
        session_id=req.session_id,
        location=req.location,
        rag=req.rag,
    )


@router.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
    module = _chat_module(request)

    def event_iter() -> Iterator[str]:
        for event in module.stream_chat(
            query=req.query,
            user_id=req.user_id,
            session_id=req.session_id,
            location=req.location,
            rag=req.rag,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "event: end\ndata: [DONE]\n\n"

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/debug/intent")
def debug_intent(req: IntentDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    packet = module.intent.predict(req.query)
    return {"intent_packet": packet}


@router.post("/debug/retrieval")
def debug_retrieval(req: RetrievalDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    hits = module.retrieval.search(query=req.query, user_id=req.user_id, location=req.location)
    return {"hits": hits, "count": len(hits)}


@router.post("/debug/kg")
def debug_kg(req: KGDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    hits = module.kg.search(req.query, top_k=max(1, int(req.top_k)))
    return {"hits": hits, "count": len(hits)}


@router.post("/debug/router")
def debug_router(req: RouterDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    target = module.router.derive_target(intent=req.intent, domain=req.domain)
    return {"target": target}


@router.post("/debug/prompt/rag")
def debug_prompt_rag(req: PromptRAGDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    system_prompt, user_prompt = module.prompt.build_rag_messages(
        query=req.query,
        intent_packet=req.intent_packet,
        retrieval_hits=req.retrieval_hits,
        kg_hits=req.kg_hits,
        history=req.history,
        target=req.target,
    )
    return {"system_prompt": system_prompt, "user_prompt": user_prompt}


@router.post("/debug/prompt/direct")
def debug_prompt_direct(req: PromptDirectDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    system_prompt, user_prompt = module.prompt.build_direct_messages(
        query=req.query, history=req.history
    )
    return {"system_prompt": system_prompt, "user_prompt": user_prompt}


@router.post("/debug/llm")
def debug_llm(req: LLMDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    answer = module.llm.chat(system_prompt=req.system_prompt, user_prompt=req.user_prompt)
    return {"answer": answer}


@router.post("/debug/llm/stream")
def debug_llm_stream(req: LLMDebugRequest, request: Request) -> StreamingResponse:
    module = _chat_module(request)

    def event_iter() -> Iterator[str]:
        for token in module.llm.stream_chat(
            system_prompt=req.system_prompt, user_prompt=req.user_prompt
        ):
            yield f"data: {json.dumps({'type': 'chunk', 'content': token}, ensure_ascii=False)}\n\n"
        yield "event: end\ndata: [DONE]\n\n"

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
