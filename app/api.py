from __future__ import annotations

import json
import re
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator, List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete

from .auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
)
from .models import User, ChatMessage, PlantingPlan
from .schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessageResponse,
    PlantingPlanCreate,
    PlantingPlanResponse,
    UserCreate,
    UserLogin,
    Token,
    UserResponse,
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


def _db_manager(request: Request):
    return request.app.state.db


# --- Auth Routes ---

@router.post("/auth/register", response_model=UserResponse)
def register(user_in: UserCreate, request: Request):
    db = _db_manager(request)
    with db.session() as session:
        # Check if user exists
        existing_user = session.execute(
            select(User).where(User.username == user_in.username)
        ).scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        
        new_user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            is_active=True
        )
        session.add(new_user)
        session.flush() # 确保分配了 ID
        session.refresh(new_user) # 刷新属性
        return new_user


@router.post("/auth/login", response_model=Token)
def login(user_in: UserLogin, request: Request):
    db = _db_manager(request)
    settings = request.app.state.settings
    with db.session() as session:
        user = session.execute(
            select(User).where(User.username == user_in.username)
        ).scalar_one_or_none()
        if not user or not verify_password(user_in.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username},
            secret_key=settings.secret_key,
            expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- Chat Routes ---

@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest, 
    request: Request,
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    module = _chat_module(request)
    return module.chat(
        query=req.query,
        user_id=str(current_user.id),
        session_id=req.session_id,
        location=req.location,
        rag=req.rag,
    )


@router.post("/chat/stream")
def chat_stream(
    req: ChatRequest, 
    request: Request,
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    module = _chat_module(request)

    def event_iter() -> Iterator[str]:
        try:
            for event in module.stream_chat(
                query=req.query,
                user_id=str(current_user.id),
                session_id=req.session_id,
                location=req.location,
                rag=req.rag,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_event = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
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


@router.get("/chat/history", response_model=List[ChatMessageResponse])
def get_chat_history(
    request: Request,
    current_user: User = Depends(get_current_user),
    limit: int = 50
):
    db = _db_manager(request)
    with db.session() as session:
        messages = session.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == current_user.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return list(reversed(list(messages)))


# --- Plans Routes ---

@router.post("/plans", response_model=PlantingPlanResponse)
def create_plan(
    plan_in: PlantingPlanCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        new_plan = PlantingPlan(
            user_id=current_user.id,
            crop_name=plan_in.crop_name,
            plan_details=plan_in.plan_details,
            status=plan_in.status
        )
        session.add(new_plan)
        session.flush()
        return new_plan


@router.get("/plans", response_model=List[PlantingPlanResponse])
def list_plans(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        plans = session.execute(
            select(PlantingPlan).where(PlantingPlan.user_id == current_user.id)
        ).scalars().all()
        return list(plans)


@router.delete("/plans/{plan_id}")
def delete_plan(
    plan_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        plan = session.execute(
            select(PlantingPlan).where(
                PlantingPlan.id == plan_id, 
                PlantingPlan.user_id == current_user.id
            )
        ).scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        session.delete(plan)
        return {"status": "ok"}


# --- Knowledge Routes (Admin/Internal) ---

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


@router.get("/weather")
def get_weather(city: str):
    # 模拟天气数据
    return {
        "city": city,
        "temperature": 22,
        "weather": "晴",
        "humidity": "45%",
        "windSpeed": "3级"
    }


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


# --- Debug Routes ---

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
    module = getattr(request.app.state, "graph_module", None)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable.")
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
    )
