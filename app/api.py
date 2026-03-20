from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from .schemas import (
    ChatRequest,
    ChatResponse,
    GraphDebugRequest,
    IntentDebugRequest,
    KnowledgeIndexResponse,
    KnowledgeIndexUpdateRequest,
    KnowledgeUploadResponse,
    LLMDebugRequest,
    PromptDirectDebugRequest,
    PromptRAGDebugRequest,
    RetrievalDebugRequest,
    RouterDebugRequest,
)

router = APIRouter(prefix="/api", tags=["api"])
_ALLOWED_KNOWLEDGE_SUFFIXES = {".txt", ".md", ".json", ".csv", ".pdf", ".doc", ".docx"}
_SAFE_NAME_PATTERN = re.compile(r"[^0-9A-Za-z_.\-\u4e00-\u9fff]+")


def _chat_module(request: Request):
    return request.app.state.chat_module


def _graph_module(request: Request):
    module = getattr(request.app.state, "graph_module", None)
    if module is None:
        raise HTTPException(status_code=503, detail="Graph module is unavailable.")
    return module


def _index_service(request: Request):
    chat_module = _chat_module(request)
    retrieval = getattr(chat_module, "retrieval", None)
    service = getattr(retrieval, "index_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="RAG index service is unavailable.")
    return service


def _raw_data_dir(request: Request) -> Path:
    settings = request.app.state.settings
    project_root = Path(__file__).resolve().parents[2]
    raw_dir = settings.resolve_index_data_dir(project_root)
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def _safe_file_name(filename: str) -> str:
    original = Path(str(filename or "").strip()).name
    suffix = Path(original).suffix.lower() or ".txt"
    stem = Path(original).stem
    safe_stem = _SAFE_NAME_PATTERN.sub("_", stem).strip("._")
    if not safe_stem:
        safe_stem = f"upload_{int(time.time() * 1000)}"
    return f"{safe_stem}{suffix}"


def _index_payload(service, *, count: int) -> dict[str, Any]:
    return {
        "indexed_count": int(max(0, count)),
        "ready": bool(service.is_ready()),
        "persist_dir": str(service.persist_dir),
        "raw_data_dir": str(service.data_dir),
    }


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


@router.post("/knowledge/upload", response_model=KnowledgeUploadResponse)
async def upload_knowledge_file(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    original_name = str(file.filename or "").strip()
    if not original_name:
        raise HTTPException(status_code=400, detail="Missing uploaded file name.")

    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_KNOWLEDGE_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. Allowed: "
                + ", ".join(sorted(_ALLOWED_KNOWLEDGE_SUFFIXES))
            ),
        )

    content = await file.read()
    await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    raw_dir = _raw_data_dir(request)
    stored_name = _safe_file_name(original_name)
    target = raw_dir / stored_name
    if target.exists():
        stamp = int(time.time() * 1000)
        target = raw_dir / f"{target.stem}_{stamp}{target.suffix}"
        stored_name = target.name

    target.write_bytes(content)
    return {
        "filename": original_name,
        "stored_as": stored_name,
        "size_bytes": len(content),
        "raw_path": str(target),
    }


@router.post("/knowledge/index/update", response_model=KnowledgeIndexResponse)
def update_knowledge_index(
    req: KnowledgeIndexUpdateRequest,
    request: Request,
) -> dict[str, Any]:
    service = _index_service(request)
    try:
        count = int(service.build(rebuild=bool(req.rebuild)))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Index update failed: {exc}") from exc
    return _index_payload(service, count=count)


@router.get("/knowledge/index/status", response_model=KnowledgeIndexResponse)
def knowledge_index_status(request: Request) -> dict[str, Any]:
    service = _index_service(request)
    try:
        count = int(service.count()) if service.is_ready() else 0
    except Exception:
        count = 0
    return _index_payload(service, count=count)


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


@router.post("/debug/graph")
def debug_graph(req: GraphDebugRequest, request: Request) -> dict[str, Any]:
    module = _graph_module(request)
    hits = module.search(req.query, limit=max(1, int(req.limit)))
    return {"hits": hits, "count": len(hits)}


@router.post("/debug/router")
def debug_router(req: RouterDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    target = module.router.derive_target(intent=req.intent)
    return {"target": target}


@router.post("/debug/prompt/rag")
def debug_prompt_rag(req: PromptRAGDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    system_prompt, user_prompt = module.prompt.build_rag_messages(
        query=req.query,
        location=req.location,
        intent_packet=req.intent_packet,
        retrieval_hits=req.retrieval_hits,
        history=req.history,
        target=req.target,
    )
    return {"system_prompt": system_prompt, "user_prompt": user_prompt}


@router.post("/debug/prompt/direct")
def debug_prompt_direct(req: PromptDirectDebugRequest, request: Request) -> dict[str, Any]:
    module = _chat_module(request)
    system_prompt, user_prompt = module.prompt.build_direct_messages(
        query=req.query, history=req.history, location=req.location
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
