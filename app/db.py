from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Base


class DB:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_engine(
            settings.database_url,
            # MySQL optimizations
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self.engine,
            expire_on_commit=False  # 防止提交后对象失效
        )

    def init(self) -> None:
        """Create tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        inspector = inspect(self.engine)
        dialect = self.engine.dialect.name
        table_names = set(inspector.get_table_names())
        if dialect in {"mysql", "mariadb"} and "users" in table_names:
            columns = inspector.get_columns("users")
            by_name = {col["name"]: col for col in columns}
            with self.engine.begin() as conn:
                if "email" not in by_name:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(100) NULL"))
                if "hashed_password" not in by_name:
                    conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255) NULL"))
                    hashed_col_type = "VARCHAR(255)"
                else:
                    hashed_col_type = str(by_name["hashed_password"].get("type") or "VARCHAR(255)")
                conn.execute(text("UPDATE users SET hashed_password='' WHERE hashed_password IS NULL"))
                conn.execute(text(f"ALTER TABLE users MODIFY COLUMN hashed_password {hashed_col_type} NOT NULL"))

                if "is_active" not in by_name:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1"))
                if "is_admin" not in by_name:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0"))
                if "created_at" not in by_name:
                    conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME NULL"))
                    conn.execute(text("UPDATE users SET created_at=NOW() WHERE created_at IS NULL"))
                    conn.execute(text("ALTER TABLE users MODIFY COLUMN created_at DATETIME NOT NULL"))
        if dialect in {"mysql", "mariadb"} and "planting_plans" in table_names:
            columns = inspector.get_columns("planting_plans")
            plan_details_col = next((col for col in columns if col["name"] == "plan_details"), None)
            with self.engine.begin() as conn:
                if plan_details_col is None:
                    conn.execute(text("ALTER TABLE planting_plans ADD COLUMN plan_details TEXT NULL"))
                    col_type = "TEXT"
                else:
                    col_type = str(plan_details_col.get("type") or "TEXT")
                conn.execute(text("UPDATE planting_plans SET plan_details='' WHERE plan_details IS NULL"))
                conn.execute(text(f"ALTER TABLE planting_plans MODIFY COLUMN plan_details {col_type} NOT NULL"))

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
