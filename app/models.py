from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Text, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    plans: Mapped[List["PlantingPlan"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    consultations: Mapped[List["ExpertConsultation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    schedules: Mapped[List["Schedule"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user, assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    user: Mapped["User"] = relationship(back_populates="messages")


class PlantingPlan(Base):
    __tablename__ = "planting_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    crop_name: Mapped[str] = mapped_column(String(100))
    plan_details: Mapped[str] = mapped_column(Text)  # Store as JSON string or Text
    status: Mapped[str] = mapped_column(String(20), default="进行中")  # 进行中, 已完成
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    user: Mapped["User"] = relationship(back_populates="plans")


class ExpertConsultation(Base):
    __tablename__ = "expert_consultations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expert_name: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="待回复")  # 待回复, 已回复
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    user: Mapped["User"] = relationship(back_populates="consultations")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    date: Mapped[datetime] = mapped_column(DateTime)
    is_completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    user: Mapped["User"] = relationship(back_populates="schedules")
