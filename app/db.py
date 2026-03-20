from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Settings


class DB:
    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.db_path = settings.resolve_db_path(project_root)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            # Keep legacy table to avoid breaking old history data.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    time TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_history_user_time
                ON chat_history(user_id, time)
                """
            )

            # New message-level table for session-based context window.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time
                ON chat_messages(session_id, created_at)
                """
            )
            conn.commit()

    def save_chat(self, *, user_id: str, query: str, answer: str, when: str | None = None) -> None:
        timestamp = when or datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_history (user_id, query, answer, time)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, query, answer, timestamp),
            )
            conn.commit()

    def list_history(self, *, user_id: str, limit: int = 6) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, query, answer, time
                FROM chat_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, max(1, int(limit))),
            ).fetchall()

        ordered = list(reversed(rows))
        return [
            {
                "user_id": str(r["user_id"] or ""),
                "query": str(r["query"] or ""),
                "answer": str(r["answer"] or ""),
                "time": str(r["time"] or ""),
            }
            for r in ordered
        ]

    def append_message(
        self,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        when: str | None = None,
    ) -> None:
        if not session_id.strip() or not content.strip():
            return
        timestamp = when or datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (session_id, user_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id or "", role.strip().lower(), content, timestamp),
            )
            conn.commit()

    def list_recent_messages(self, *, session_id: str, limit: int = 10) -> list[dict[str, str]]:
        if not session_id.strip():
            return []

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, user_id, role, content, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, max(1, int(limit))),
            ).fetchall()

        ordered = list(reversed(rows))
        return [
            {
                "session_id": str(r["session_id"] or ""),
                "user_id": str(r["user_id"] or ""),
                "role": str(r["role"] or ""),
                "content": str(r["content"] or ""),
                "created_at": str(r["created_at"] or ""),
            }
            for r in ordered
        ]
