from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as api_router
from .config import Settings
from .db import DB
from .modules import (
    ChatModule,
    GraphModule,
    IntentModule,
    LLMModule,
    PromptModule,
    RetrievalModule,
    RouterModule,
)
from .repositories import ChatRepository


def create_app() -> FastAPI:
    project_root = Path(__file__).resolve().parents[2]
    settings = Settings.from_env()

    db = DB(settings=settings, project_root=project_root)
    db.init()
    chat_repo = ChatRepository(db=db)

    intent = IntentModule(settings=settings, project_root=project_root)
    retrieval = RetrievalModule(settings=settings, project_root=project_root)
    graph = GraphModule(settings=settings, project_root=project_root)
    router = RouterModule()
    prompt = PromptModule()
    llm = LLMModule(settings=settings)

    chat_module = ChatModule(
        settings=settings,
        db=db,
        chat_repo=chat_repo,
        intent=intent,
        retrieval=retrieval,
        router=router,
        prompt=prompt,
        llm=llm,
    )

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.chat_module = chat_module
    app.state.graph_module = graph
    app.include_router(api_router)
    return app


app = create_app()
