from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .config import Settings


class DB:
    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.db_path = Path(settings.db_path)
        if not self.db_path.is_absolute():
            self.db_path = (project_root / self.db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        # 极简数据库：只保留一张会话历史表，后续可平滑扩展
        with self.connect() as conn:
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

    def list_history(self, *, user_id: str, limit: int = 6) -> List[Dict[str, Any]]:
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

        # 按时间正序返回，便于直接作为模型上下文
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
