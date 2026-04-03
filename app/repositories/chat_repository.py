from __future__ import annotations

from typing import Any, List

from sqlalchemy import select
from ..db import DB
from ..models import ChatMessage


class ChatRepository:
    def __init__(self, db: DB) -> None:
        self.db = db

    def list_recent(self, *, user_id: str, session_id: str = "", limit: int = 10) -> list[dict[str, Any]]:
        with self.db.session() as session:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.user_id == int(user_id))
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "role": r.role,
                    "content": r.content,
                    "created_at": r.created_at.isoformat()
                }
                for r in reversed(list(rows))
            ]

    def append_message(self, *, session_id: str = "", user_id: str, role: str, content: str) -> None:
        with self.db.session() as session:
            msg = ChatMessage(
                user_id=int(user_id),
                role=role,
                content=content
            )
            session.add(msg)
            session.commit()
