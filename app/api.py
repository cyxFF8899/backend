from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete

from .database.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_user,
)
from .database.models import User, ChatMessage, PlantingPlan
from .schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessageResponse,
    PlantingPlanCreate,
    PlantingPlanResponse,
    ExpertConsultationCreate,
    ExpertConsultationResponse,
    ScheduleCreate,
    ScheduleResponse,
    UserCreate,
    UserLogin,
    UserUpdate,
    Token,
    UserResponse,
    GraphDebugRequest,
    IntentDebugRequest,
    KnowledgeIndexResponse,
    KnowledgeIndexUpdateRequest,
    KnowledgeUploadResponse,
    KnowledgeNodeCreate,
    KnowledgeEdgeCreate,
    LLMDebugRequest,
    PromptDirectDebugRequest,
    PromptRAGDebugRequest,
    RetrievalDebugRequest,
    RouterDebugRequest,
)

router = APIRouter(prefix="/api", tags=["api"])


def _verify_admin(current_user: User):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only admins can access this resource"
        )
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
        session.flush()
        session.refresh(new_user)
        return new_user


@router.post("/auth/login", response_model=Token)
def login(user_in: UserLogin, request: Request):
    db = _db_manager(request)
    settings = request.app.state.settings
    try:
        with db.session() as session:
            user = session.execute(
                select(User).where(User.username == user_in.username)
            ).scalar_one_or_none()
            password_ok = bool(user) and verify_password(user_in.password, user.hashed_password)
            if user and not password_ok and user.hashed_password == user_in.password:
                user.hashed_password = get_password_hash(user_in.password)
                session.add(user)
                session.flush()
                password_ok = True

            if not user or not password_ok:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled",
                )
            
            access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
            access_token = create_access_token(
                data={"sub": user.username},
                secret_key=settings.secret_key,
                expires_delta=access_token_expires
            )
            return {
                "access_token": access_token, 
                "token_type": "bearer",
                "username": user.username,
                "is_admin": user.is_admin
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Login failed: {exc}") from exc


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- Chat Routes ---

@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest, 
    request: Request,
    current_user: User = Depends(get_optional_user)
) -> dict[str, Any]:
    module = _chat_module(request)
    user_id = str(current_user.id) if current_user else "3"
    return module.chat(
        query=req.query,
        user_id=user_id,
        session_id=req.session_id,
        location=req.location,
        rag=req.rag,
    )


@router.post("/chat/stream")
def chat_stream(
    req: ChatRequest, 
    request: Request,
    current_user: User = Depends(get_optional_user)
) -> StreamingResponse:
    module = _chat_module(request)
    user_id = str(current_user.id) if current_user else "3"

    def event_iter() -> Iterator[str]:
        try:
            for event in module.stream_chat(
                query=req.query,
                user_id=user_id,
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


# --- Planting Schemes Routes ---

@router.post("/planting-schemes", response_model=PlantingPlanResponse)
def create_planting_scheme(
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


@router.get("/planting-schemes", response_model=List[PlantingPlanResponse])
def list_planting_schemes(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        plans = session.execute(
            select(PlantingPlan).where(PlantingPlan.user_id == current_user.id)
        ).scalars().all()
        return list(plans)


@router.delete("/planting-schemes/{plan_id}")
def delete_planting_scheme(
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
            raise HTTPException(status_code=404, detail="Planting scheme not found")
        session.delete(plan)
        return {"status": "ok"}


# --- Expert Consultation Routes ---

@router.post("/expert-consultations", response_model=ExpertConsultationResponse)
def create_consultation(
    cons_in: ExpertConsultationCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        from .database.models import ExpertConsultation
        new_cons = ExpertConsultation(
            user_id=current_user.id,
            expert_name=cons_in.expert_name,
            category=cons_in.category,
            content=cons_in.content,
            status="pending"
        )
        session.add(new_cons)
        session.flush()
        return new_cons


@router.get("/expert-consultations", response_model=List[ExpertConsultationResponse])
def list_consultations(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        from .database.models import ExpertConsultation
        cons = session.execute(
            select(ExpertConsultation).where(ExpertConsultation.user_id == current_user.id)
        ).scalars().all()
        return list(cons)


# --- Schedules Routes ---

@router.get("/schedules", response_model=List[ScheduleResponse])
def list_schedules(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        from .database.models import Schedule
        schedules = session.execute(
            select(Schedule).where(Schedule.user_id == current_user.id)
        ).scalars().all()
        return list(schedules)


@router.post("/schedules", response_model=ScheduleResponse)
def create_schedule(
    sched_in: ScheduleCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        from .database.models import Schedule
        new_sched = Schedule(
            user_id=current_user.id,
            title=sched_in.title,
            content=sched_in.content,
            date=sched_in.date,
            is_completed=sched_in.is_completed
        )
        session.add(new_sched)
        session.flush()
        return new_sched


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    sched_in: ScheduleCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        from .database.models import Schedule
        sched = session.execute(
            select(Schedule).where(
                Schedule.id == schedule_id, 
                Schedule.user_id == current_user.id
            )
        ).scalar_one_or_none()
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        sched.title = sched_in.title
        sched.content = sched_in.content
        sched.date = sched_in.date
        sched.is_completed = sched_in.is_completed
        return sched


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    db = _db_manager(request)
    with db.session() as session:
        from .database.models import Schedule
        sched = session.execute(
            select(Schedule).where(
                Schedule.id == schedule_id, 
                Schedule.user_id == current_user.id
            )
        ).scalar_one_or_none()
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")
        session.delete(sched)
        return {"status": "ok"}


# --- Admin Routes ---

# --- Admin User Management Routes ---

@router.get("/admin/users", response_model=List[UserResponse])
def get_admin_users(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    db = _db_manager(request)
    with db.session() as session:
        users = session.execute(select(User)).scalars().all()
        return list(users)


@router.get("/admin/users/{user_id}", response_model=UserResponse)
def get_admin_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    db = _db_manager(request)
    with db.session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user


@router.post("/admin/users", response_model=UserResponse)
def create_admin_user(
    user_in: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    db = _db_manager(request)
    with db.session() as session:
        existing_user = session.execute(
            select(User).where(User.username == user_in.username)
        ).scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        new_user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            is_active=True,
            is_admin=False
        )
        session.add(new_user)
        session.flush()
        session.refresh(new_user)
        return new_user


@router.put("/admin/users/{user_id}", response_model=UserResponse)
def update_admin_user(
    user_id: int,
    user_in: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    db = _db_manager(request)
    with db.session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user_in.email is not None:
            user.email = user_in.email
        if user_in.is_active is not None:
            user.is_active = user_in.is_active
        if user_in.is_admin is not None:
            user.is_admin = user_in.is_admin
        if user_in.password:
            user.hashed_password = get_password_hash(user_in.password)
            
        session.flush()
        session.refresh(user)
        return user


@router.delete("/admin/users/{user_id}")
def delete_admin_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    db = _db_manager(request)
    try:
        with db.session() as session:
            user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            from .database.models import ExpertConsultation, Schedule

            session.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))
            session.execute(delete(PlantingPlan).where(PlantingPlan.user_id == user_id))
            session.execute(delete(ExpertConsultation).where(ExpertConsultation.user_id == user_id))
            session.execute(delete(Schedule).where(Schedule.user_id == user_id))
            session.delete(user)
            session.flush()
            return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Delete user failed: {exc}") from exc


# --- Admin Dashboard Routes ---

@router.get("/admin/dashboard/stats")
def get_dashboard_stats(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    db = _db_manager(request)
    with db.session() as session:
        from sqlalchemy import func
        user_count = session.execute(select(func.count(User.id))).scalar()
        msg_count = session.execute(select(func.count(ChatMessage.id))).scalar()
        plan_count = session.execute(select(func.count(PlantingPlan.id))).scalar()
        
        return {
            "total_users": user_count,
            "total_messages": msg_count,
            "total_plans": plan_count,
            "system_status": "healthy"
        }


# --- Admin Knowledge Management Routes ---

def _graph_module(request: Request):
    return getattr(request.app.state, "graph_module", None)


@router.get("/admin/knowledge/nodes")
def get_knowledge_nodes(
    request: Request,
    current_user: User = Depends(get_current_user),
    query: str = "",
    limit: int = 100
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    return module.search(query, limit=limit)


@router.get("/admin/knowledge/nodes/{node_id}")
def get_knowledge_node(
    node_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    node = module.get_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.post("/admin/knowledge/nodes")
def create_knowledge_node(
    node_in: KnowledgeNodeCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    return module.create_node(node_in.label, node_in.properties)


@router.put("/admin/knowledge/nodes/{node_id}")
def update_knowledge_node(
    node_id: str,
    node_in: KnowledgeNodeCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    return module.update_node(node_id, node_in.properties)


@router.delete("/admin/knowledge/nodes/{node_id}")
def delete_knowledge_node(
    node_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    success = module.delete_node(node_id)
    return {"status": "ok" if success else "error"}


@router.get("/admin/knowledge/edges")
def get_knowledge_edges(
    node_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    return module.get_relationships(node_id)


@router.post("/admin/knowledge/edges")
def create_knowledge_edge(
    edge_in: KnowledgeEdgeCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    success = module.create_relationship(
        edge_in.start_id, 
        edge_in.end_id, 
        edge_in.relationship_type, 
        edge_in.properties
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create relationship")
    return {"status": "ok"}


@router.delete("/admin/knowledge/edges/{rel_id}")
def delete_knowledge_edge(
    rel_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    module = _graph_module(request)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable")
    success = module.delete_relationship(rel_id)
    return {"status": "ok" if success else "error"}


@router.get("/admin/knowledge/materials")
def list_knowledge_materials(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    raw_dir = _raw_data_dir(request)
    materials = []
    for p in raw_dir.glob("*"):
        if p.is_file():
            materials.append({
                "id": p.name,
                "name": p.name,
                "size": p.stat().st_size,
                "created_at": datetime.fromtimestamp(p.stat().st_ctime)
            })
    return materials


@router.post("/admin/knowledge/materials")
async def upload_knowledge_material(
    request: Request,
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...)
):
    _verify_admin(current_user)
    return await upload_knowledge_file(request, file)


@router.delete("/admin/knowledge/materials/{material_id}")
def delete_knowledge_material(
    material_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    _verify_admin(current_user)
    raw_dir = _raw_data_dir(request)
    target = raw_dir / material_id
    if target.exists() and target.is_file():
        target.unlink()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Material not found")


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
    return {
        "city": city,
        "temperature": 22,
        "weather": "sunny",
        "humidity": "45%",
        "windSpeed": "3m/s"
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


@router.get("/graph/stats")
def graph_stats(request: Request) -> dict[str, Any]:
    module = getattr(request.app.state, "graph_module", None)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable.")
    return module.get_stats()


@router.get("/graph/labels")
def graph_labels(request: Request) -> dict[str, Any]:
    module = getattr(request.app.state, "graph_module", None)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable.")
    label_counts = module.get_labels()
    return {"label_counts": label_counts}


@router.get("/graph/nodes")
def graph_nodes(
    request: Request,
    label: str = None,
    keyword: str = None,
    limit: int = 100
) -> dict[str, Any]:
    module = getattr(request.app.state, "graph_module", None)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable.")
    nodes = module.get_nodes(label=label, keyword=keyword, limit=limit)
    return {"nodes": nodes, "count": len(nodes)}


@router.get("/graph/subgraph")
def graph_subgraph(
    request: Request,
    depth: int = 1,
    limit: int = 80,
    keyword: str = None,
    label: str = None,
    node_ids: str = None
) -> dict[str, Any]:
    module = getattr(request.app.state, "graph_module", None)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable.")

    node_id_list = []
    if node_ids:
        node_id_list = node_ids.split(",")

    subgraph = module.get_subgraph(
        depth=depth,
        limit=limit,
        keyword=keyword,
        label=label,
        node_ids=node_id_list if node_id_list else None
    )
    return {
        "nodes": subgraph["nodes"],
        "edges": subgraph.get("edges", []),
        "node_count": len(subgraph["nodes"]),
        "relationship_count": len(subgraph.get("edges", []))
    }


@router.get("/graph/relationships/{node_id:path}")
def graph_node_relationships(node_id: str, request: Request) -> dict[str, Any]:
    module = getattr(request.app.state, "graph_module", None)
    if not module:
        raise HTTPException(status_code=503, detail="Graph module is unavailable.")
    relationships = module.get_node_relationships(node_id)
    return {"relationships": relationships}


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
