from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config import Settings


class RetrievalModule:
    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.settings = settings
        self.project_root = project_root
        self.index_service: Any | None = None
        self.retriever: Any | None = None
        self._init_error: str | None = None

        try:
            from ...rag import IndexService, Retriever

            self.index_service = IndexService(settings=settings, project_root=project_root)
            self.retriever = Retriever(
                settings=settings,
                project_root=project_root,
                index_service=self.index_service,
            )
            if self.settings.index_auto_build:
                self.index_service.ensure_index()
        except Exception as exc:
            self._init_error = str(exc)
            self.index_service = None
            self.retriever = None

    def search(self, *, query: str, user_id: str, location: str = "") -> list[dict[str, Any]]:
        _ = user_id
        if self.retriever is None:
            return []
        try:
            return self.retriever.search(
                query=query,
                k=self.settings.top_k_hits,
                location=location,
            )
        except Exception:
            return []
