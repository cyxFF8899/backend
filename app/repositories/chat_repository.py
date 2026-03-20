from __future__ import annotations

from typing import Any

from ..db import DB


class ChatRepository:
    def __init__(self, db: DB) -> None:
        self.db = db

    def list_recent(self, *, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.db.list_recent_messages(session_id=session_id, limit=limit)

    def append_message(self, *, session_id: str, user_id: str, role: str, content: str) -> None:
        self.db.append_message(session_id=session_id, user_id=user_id, role=role, content=content)
