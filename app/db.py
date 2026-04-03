from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
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
