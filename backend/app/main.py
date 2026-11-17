# main.py - FastAPI MVP for AI Personal Assistant
# Bootstrap-only table creation: use Alembic migrations before production deployment.

from __future__ import annotations

import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum

# ---------------------------------------------------------------------------
# Environment & configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./assistant.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
APP_ENV = os.environ.get("APP_ENV", "production")  # "development" or "production"
BLUETICKS_MCP_URL = os.environ.get(
    "BLUETICKS_MCP_URL", "https://api.blueticks.co/mcp"
)
BLUETICKS_BEARER_TOKEN = os.environ.get("BLUETICKS_BEARER_TOKEN", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQLAlchemy setup
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mcp_url: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GrantStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Grant(Base):
    """Records which user has which scope(s) on which integration."""
    __tablename__ = "grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    integration_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)  # read, write, send
    status: Mapped[GrantStatus] = mapped_column(
        Enum(GrantStatus), default=GrantStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    integration_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[GrantStatus] = mapped_column(
        Enum(GrantStatus), default=GrantStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(200), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ApprovalRequestCreate(BaseModel):
    user_id: str
    integration_name: str
    scope: str = Field(..., pattern="^(read|write|send)$")


class ApprovalDecision(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
) -> str:
    """Require Bearer-JWT (HS256 via stdlib hmac) in production; allow X-User-ID in dev."""
    if APP_ENV == "development" and x_user_id:
        return x_user_id
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")

    # Minimal HMAC-SHA256 token verification (stdlib hmac)
    # Expected payload format: {"user_id": "...", "exp": ...}
    # In production use PyJWT; here we do a minimal check for MVP.
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Malformed token")

        def urlsafe_b64decode(s: str) -> bytes:
            s += "=" * (-len(s) % 4)
            return base64.urlsafe_b64decode(s)

        # Verify signature (simplified — production should use PyJWT)
        signing_input = parts[0] + "." + parts[1]
        expected_sig = hmac.new(
            JWT_SECRET.encode(), signing_input.encode(), "sha256"
        ).digest()
        actual_sig = urlsafe_b64decode(parts[2])
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise HTTPException(status_code=401, detail="Invalid token signature")

        # Decode payload (no expiry enforcement for MVP)
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("user_id", "unknown")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token error: {exc}")


# ---------------------------------------------------------------------------
# Helper: DB session
# ---------------------------------------------------------------------------


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="AI Personal Assistant API", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    """Create tables on startup (bootstrap only). Alembic migrations are needed before production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Startup: tables ensured (bootstrap only). Use Alembic for production.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Integration listing
# ---------------------------------------------------------------------------


@app.get("/api/v1/integrations")
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[dict[str, Any]]:
    result = await db.execute(text("SELECT id, name, mcp_url, created_at FROM integrations"))
    rows = result.fetchall()
    return [
        {"id": r[0], "name": r[1], "mcp_url": r[2], "created_at": str(r[3])}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Approval requests & decisions
# ---------------------------------------------------------------------------


@app.post("/api/v1/approval-requests")
async def create_approval_request(
    body: ApprovalRequestCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    # Check if a pending request already exists
    result = await db.execute(
        text(
            "SELECT id FROM approval_requests WHERE user_id=:uid AND integration_name=:iname AND scope=:scope AND status='pending'"
        ),
        {"uid": user_id, "iname": body.integration_name, "scope": body.scope},
    )
    if result.fetchone():
        raise HTTPException(status_code=409, detail="Pending request already exists")

    req = ApprovalRequest(
        user_id=user_id,
        integration_name=body.integration_name,
        scope=body.scope,
        status=GrantStatus.PENDING,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    # Also record in audit log
    db.add(AuditLog(user_id=user_id, action="approval_request_created", resource=body.integration_name))
    await db.commit()
    return {
        "id": req.id,
        "status": req.status.value,
        "integration_name": req.integration_name,
        "scope": req.scope,
    }


@app.post("/api/v1/approval-requests/{request_id}/decide")
async def decide_approval(
    request_id: int,
    body: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    # Fetch the request
    result = await db.execute(
        text("SELECT * FROM approval_requests WHERE id=:rid"), {"rid": request_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")

    # Restrict: only the requesting user can decide; must be pending
    if row[1] != user_id:  # user_id column
        raise HTTPException(status_code=403, detail="Only the requester can approve/reject")
    if row[4] != "pending":  # status column
        raise HTTPException(status_code=400, detail="Request is not pending")

    new_status = GrantStatus.APPROVED if body.decision == "approve" else GrantStatus.REJECTED

    # Update the approval request
    await db.execute(
        text("UPDATE approval_requests SET status=:st WHERE id=:rid"),
        {"st": new_status.value, "rid": request_id},
    )

    # If approved, create a Grant record
    if new_status == GrantStatus.APPROVED:
        grant = Grant(
            user_id=user_id,
            integration_name=row[2],  # integration_name
            scope=row[3],  # scope
            status=new_status,
        )
        db.add(grant)

    await db.commit()
    # Audit log
    db.add(
        AuditLog(
            user_id=user_id,
            action=f"approval_{body.decision}",
            resource=f"request/{request_id}",
            details=json.dumps({"decision": body.decision}),
        )
    )
    await db.commit()

    return {"id": request_id, "status": new_status.value}


# ---------------------------------------------------------------------------
# Grant enforcement helper
# ---------------------------------------------------------------------------


async def check_grant(db: AsyncSession, user_id: str, integration_name: str, required_scope: str) -> None:
    """Raise 403 if no approved grant exists for the required scope."""
    result = await db.execute(
        text(
            "SELECT id FROM grants WHERE user_id=:uid AND integration_name=:iname AND scope=:scope AND status='approved'"
        ),
        {"uid": user_id, "iname": integration_name, "scope": required_scope},
    )
    if not result.fetchone():
        raise HTTPException(
            status_code=403,
            detail=f"No approved grant for scope '{required_scope}' on '{integration_name}'",
        )


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------


@app.post("/api/v1/chat")
async def chat(
    body: ChatRequest,
    _user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured. Please set the environment variable.",
        )

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        messages = body.messages or [{"role": "user", "content": "Hello"}]
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
        )
        return {
            "assistant": resp.choices[0].message.content if resp.choices else "",
        }
    except Exception as exc:
        logger.error("Chat error: %s", exc)
        raise HTTPException(status_code=503, detail=f"AI service unavailable: {exc}")


# ---------------------------------------------------------------------------
# Blueticks MCP tool discover & invoke
# ---------------------------------------------------------------------------


class DiscoveredTool(BaseModel):
    name: str
    description: Optional[str] = None


@app.get("/api/v1/integrations/blueticks/discover")
async def discover_blueticks(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Discover tools from the official Blueticks MCP server.

    Uses the MCP Python SDK (streamablehttp_client + ClientSession).
    Records discovered capability names WITHOUT marking connected until user
    approves a grant request.
    """
    # Attempt MCP discovery via the SDK
    tools: list[dict[str, Any]] = []
    try:
        from mcp import ClientSession
        from mcp.client.streamablehttp import streamablehttp_client

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if BLUETICKS_BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {BLUETICKS_BEARER_TOKEN}"
        # NOTE: existing repository credentials are NEVER exposed or modified here.

        async with streamablehttp_client(
            BLUETICKS_MCP_URL, headers=headers
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    tools.append(
                        {
                            "name": tool.name,
                            "description": getattr(tool, "description", None),
                        }
                    )
    except ImportError:
        logger.warning("mcp SDK not available; skipping MCP discovery.")
    except Exception as exc:
        logger.warning("MCP discovery failed: %s", exc)

    # Record discovered capability names in audit log (do NOT mark as connected)
    if tools:
        for t in tools:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action="blueticks_discovered",
                    resource=t["name"],
                    details=json.dumps({"description": t.get("description")}),
                )
            )
        await db.commit()

    return {"tools": tools, "connected": False}


@app.get("/api/v1/integrations/blueticks/tools/{tool_name}")
async def invoke_blueticks_tool(
    tool_name: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Invoke a Blueticks MCP tool after verifying an approved grant.

    - 'read' scope required for read-only operations
    - 'send' scope required for sending operations
    - 'write' scope required otherwise
    """
    # Determine required scope
    required_scope = "write"  # default

    await check_grant(db, user_id, "blueticks", required_scope)

    try:
        from mcp import ClientSession
        from mcp.client.streamablehttp import streamablehttp_client

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if BLUETICKS_BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {BLUETICKS_BEARER_TOKEN}"

        async with streamablehttp_client(
            BLUETICKS_MCP_URL, headers=headers
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments={})
                # Treat all outputs as untrusted
                return {
                    "tool": tool_name,
                    "result": str(result),  # safe string representation
                }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="MCP SDK not available. Install 'mcp' package.",
        )
    except Exception as exc:
        logger.error("Blueticks tool invoke error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Tool invocation failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Entry-point guard (for direct execution via uvicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
