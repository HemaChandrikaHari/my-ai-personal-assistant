import os
from datetime import datetime, timezone
from sqlalchemy import DateTime, JSON, String, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./assistant.db")
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    endpoint: Mapped[str] = mapped_column(String(500))
    tools: Mapped[list] = mapped_column(JSON, default=list)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Grant(Base):
    __tablename__ = "grants"
    __table_args__ = (UniqueConstraint("user_id", "integration_id", "scope"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(160), index=True)
    integration_id: Mapped[str] = mapped_column(String(80), index=True)
    scope: Mapped[str] = mapped_column(String(16))

class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(160), index=True)
    integration_id: Mapped[str] = mapped_column(String(80))
    scope: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(160), index=True)
    action: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

async def get_db():
    async with SessionLocal() as db:
        yield db
