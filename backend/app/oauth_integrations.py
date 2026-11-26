"""Per-user Google Workspace and Todoist OAuth integrations.

Tokens are encrypted at rest with Fernet. OAuth state is random, one-time,
stored hashed, tied to the initiating user, and expires after ten minutes.
"""
import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.auth import current_user
from app.db import OAuthCredential, OAuthState, get_db

router = APIRouter(prefix="/api/v1", tags=["connected-apps"])
FRONTEND_URL = settings.frontend_url.rstrip("/")
GOOGLE_CLIENT_ID = settings.google_client_id
GOOGLE_CLIENT_SECRET = settings.google_client_secret
GOOGLE_REDIRECT_URI = settings.google_redirect_uri
TODOIST_CLIENT_ID = settings.todoist_client_id
TODOIST_CLIENT_SECRET = settings.todoist_client_secret
TODOIST_REDIRECT_URI = settings.todoist_redirect_uri
TOKEN_ENCRYPTION_KEY = settings.token_encryption_key

GOOGLE_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
TODOIST_SCOPES = ["data:read_write"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: datetime) -> datetime:
    # SQLite may return naive values for DateTime(timezone=True); PostgreSQL returns aware values.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _cipher() -> Fernet:
    if not TOKEN_ENCRYPTION_KEY:
        raise HTTPException(503, "TOKEN_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(TOKEN_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise HTTPException(503, "TOKEN_ENCRYPTION_KEY must be a valid Fernet key")


def _encrypt(value: str | None) -> str | None:
    if not value:
        return None
    return _cipher().encrypt(value.encode()).decode()


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        raise HTTPException(503, "Stored integration token could not be decrypted; check TOKEN_ENCRYPTION_KEY")


async def _new_state(db: AsyncSession, uid: str, provider: str) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(OAuthState(
        state_hash=hashlib.sha256(raw.encode()).hexdigest(),
        user_id=uid,
        provider=provider,
        expires_at=_utcnow() + timedelta(minutes=10),
    ))
    await db.commit()
    return raw


async def _consume_state(db: AsyncSession, raw: str, provider: str) -> str:
    if not raw or len(raw) > 256:
        raise HTTPException(400, "Invalid OAuth state")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = _utcnow()
    # Delete-and-return makes the state one-time even when two callbacks race.
    result = await db.execute(
        delete(OAuthState).where(
            OAuthState.state_hash == digest,
            OAuthState.provider == provider,
            OAuthState.expires_at >= now,
        ).returning(OAuthState.user_id)
    )
    uid = result.scalar_one_or_none()
    if not uid:
        # Remove an expired matching state, but never consume a state for another provider.
        await db.execute(delete(OAuthState).where(
            OAuthState.state_hash == digest,
            OAuthState.provider == provider,
            OAuthState.expires_at < now,
        ))
        await db.commit()
        raise HTTPException(400, "OAuth state is invalid or expired; restart the connection flow")
    await db.commit()
    return uid


def _configured(provider: str):
    if provider == "google":
        values = (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)
    else:
        values = (TODOIST_CLIENT_ID, TODOIST_CLIENT_SECRET, TODOIST_REDIRECT_URI)
    if not all(values):
        raise HTTPException(503, f"{provider.title()} OAuth credentials and redirect URI must be configured")


@router.get("/connections")
async def list_connections(uid: str = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(OAuthCredential).where(OAuthCredential.user_id == uid))).scalars().all()
    by_provider = {row.provider: row for row in rows}
    return [
        {"provider": provider, "connected": provider in by_provider,
         "scopes": by_provider[provider].scopes.split() if provider in by_provider else []}
        for provider in ("google", "todoist")
    ]


@router.get("/oauth/google/start")
async def google_start(uid: str = Depends(current_user), db: AsyncSession = Depends(get_db)):
    _configured("google")
    _cipher()
    state = await _new_state(db, uid, "google")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


@router.get("/oauth/todoist/start")
async def todoist_start(uid: str = Depends(current_user), db: AsyncSession = Depends(get_db)):
    _configured("todoist")
    _cipher()
    state = await _new_state(db, uid, "todoist")
    params = {
        "client_id": TODOIST_CLIENT_ID,
        "scope": ",".join(TODOIST_SCOPES),
        "redirect_uri": TODOIST_REDIRECT_URI,
        "state": state,
        "response_type": "code",
    }
    return {"authorization_url": "https://app.todoist.com/oauth/authorize?" + urlencode(params)}


async def _exchange(provider: str, code: str) -> dict:
    _configured(provider)
    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "google":
            response = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
        else:
            response = await client.post("https://api.todoist.com/oauth/access_token", data={
                "client_id": TODOIST_CLIENT_ID,
                "client_secret": TODOIST_CLIENT_SECRET,
                "code": code,
                "redirect_uri": TODOIST_REDIRECT_URI,
            })
    if response.is_error:
        raise HTTPException(502, f"{provider.title()} token exchange failed")
    return response.json()


async def _save_credential(db: AsyncSession, uid: str, provider: str, token_data: dict):
    existing = (await db.execute(select(OAuthCredential).where(
        OAuthCredential.user_id == uid, OAuthCredential.provider == provider
    ))).scalar_one_or_none()
    scopes_value = token_data.get("scope", "")
    scopes = " ".join(scopes_value) if isinstance(scopes_value, list) else str(scopes_value).replace(",", " ")
    expires_in = token_data.get("expires_in")
    expires_at = _utcnow() + timedelta(seconds=int(expires_in)) if expires_in else None
    if existing:
        existing.access_token_encrypted = _encrypt(token_data["access_token"])
        if token_data.get("refresh_token"):
            existing.refresh_token_encrypted = _encrypt(token_data["refresh_token"])
        existing.token_type = token_data.get("token_type", "Bearer")
        existing.scopes = scopes or existing.scopes
        existing.expires_at = expires_at
        existing.updated_at = _utcnow()
    else:
        db.add(OAuthCredential(
            user_id=uid,
            provider=provider,
            access_token_encrypted=_encrypt(token_data["access_token"]),
            refresh_token_encrypted=_encrypt(token_data.get("refresh_token")),
            token_type=token_data.get("token_type", "Bearer"),
            scopes=scopes,
            expires_at=expires_at,
        ))
    await db.commit()


async def _callback(provider: str, code: str | None, state: str | None, error: str | None, db: AsyncSession):
    if error:
        if state:
            await _consume_state(db, state, provider)
        return RedirectResponse(f"{FRONTEND_URL}/?oauth_error={provider}")
    if not code:
        raise HTTPException(400, "OAuth authorization code is missing")
    uid = await _consume_state(db, state or "", provider)
    token_data = await _exchange(provider, code)
    if not token_data.get("access_token"):
        raise HTTPException(502, f"{provider.title()} did not return an access token")
    await _save_credential(db, uid, provider, token_data)
    return RedirectResponse(f"{FRONTEND_URL}/?connected={provider}")


@router.get("/oauth/google/callback")
async def google_callback(code: str | None = None, state: str | None = None,
                          error: str | None = None, db: AsyncSession = Depends(get_db)):
    return await _callback("google", code, state, error, db)


@router.get("/oauth/todoist/callback")
async def todoist_callback(code: str | None = None, state: str | None = None,
                           error: str | None = None, db: AsyncSession = Depends(get_db)):
    return await _callback("todoist", code, state, error, db)


async def _credential(db: AsyncSession, uid: str, provider: str) -> OAuthCredential:
    row = (await db.execute(select(OAuthCredential).where(
        OAuthCredential.user_id == uid, OAuthCredential.provider == provider
    ))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"{provider.title()} is not connected")
    return row


async def _access_token(db: AsyncSession, uid: str, provider: str) -> str:
    row = await _credential(db, uid, provider)
    if row.expires_at and _aware_utc(row.expires_at) <= _utcnow() + timedelta(seconds=90):
        refresh_token = _decrypt(row.refresh_token_encrypted)
        if not refresh_token:
            raise HTTPException(401, f"{provider.title()} token expired; reconnect the account")
        if provider == "google":
            form = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
            token_url = "https://oauth2.googleapis.com/token"
        else:
            form = {
                "client_id": TODOIST_CLIENT_ID,
                "client_secret": TODOIST_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
            token_url = "https://api.todoist.com/oauth/access_token"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(token_url, data=form)
        if response.is_error:
            raise HTTPException(401, f"{provider.title()} refresh failed; reconnect the account")
        data = response.json()
        row.access_token_encrypted = _encrypt(data["access_token"])
        if data.get("refresh_token"):
            row.refresh_token_encrypted = _encrypt(data["refresh_token"])
        row.expires_at = _utcnow() + timedelta(seconds=int(data.get("expires_in", 3600)))
        if data.get("scope"):
            scopes_value = data["scope"]
            row.scopes = " ".join(scopes_value) if isinstance(scopes_value, list) else str(scopes_value).replace(",", " ")
        row.updated_at = _utcnow()
        await db.commit()
    return _decrypt(row.access_token_encrypted) or ""


async def _api_get(url: str, token: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
    if response.status_code == 401:
        raise HTTPException(401, "Provider rejected the access token; reconnect the account")
    if response.is_error:
        raise HTTPException(502, "Connected provider request failed")
    return response.json()


async def _gmail_message_text(token: str, message_id: str) -> dict:
    data = await _api_get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
        token, {"format": "full"},
    )
    headers = {
        item.get("name", "").lower(): item.get("value", "")
        for item in (data.get("payload", {}).get("headers") or [])
    }
    plain_parts = []

    def collect(part: dict):
        body = part.get("body") or {}
        encoded = body.get("data")
        if encoded and part.get("mimeType") == "text/plain":
            try:
                padded = encoded + "=" * (-len(encoded) % 4)
                plain_parts.append(base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace"))
            except (ValueError, TypeError):
                pass
        for child in part.get("parts") or []:
            collect(child)

    collect(data.get("payload") or {})
    body_text = "\n".join(plain_parts)[:12000]
    return {
        "id": data.get("id"),
        "threadId": data.get("threadId"),
        "snippet": data.get("snippet", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "body_text": body_text,
    }


class CalendarEventIn(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    start: datetime
    end: datetime
    timezone: str = "UTC"


class TodoistTaskIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    due_string: str | None = Field(default=None, max_length=100)
    project_id: str | None = None


@router.get("/google/gmail/messages")
async def gmail_messages(max_results: int = Query(default=10, ge=1, le=50),
                         uid: str = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await _credential(db, uid, "google")
    if "https://www.googleapis.com/auth/gmail.readonly" not in row.scopes:
        raise HTTPException(403, "Gmail read permission was not granted; reconnect Google")
    token = await _access_token(db, uid, "google")
    return await _api_get("https://gmail.googleapis.com/gmail/v1/users/me/messages", token,
                          {"maxResults": max_results})


@router.get("/google/gmail/messages/{message_id}")
async def gmail_message(message_id: str, uid: str = Depends(current_user),
                        db: AsyncSession = Depends(get_db)):
    if not message_id or len(message_id) > 256 or "/" in message_id:
        raise HTTPException(400, "Invalid Gmail message id")
    row = await _credential(db, uid, "google")
    if "https://www.googleapis.com/auth/gmail.readonly" not in row.scopes:
        raise HTTPException(403, "Gmail read permission was not granted; reconnect Google")
    token = await _access_token(db, uid, "google")
    return await _gmail_message_text(token, message_id)


@router.get("/google/calendar/events")
async def calendar_events(max_results: int = Query(default=20, ge=1, le=100),
                           uid: str = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await _credential(db, uid, "google")
    if "https://www.googleapis.com/auth/calendar.events" not in row.scopes:
        raise HTTPException(403, "Calendar event permission was not granted; reconnect Google")
    token = await _access_token(db, uid, "google")
    return await _api_get("https://www.googleapis.com/calendar/v3/calendars/primary/events", token,
                          {"maxResults": max_results, "singleEvents": "true",
                           "orderBy": "startTime", "timeMin": _utcnow().isoformat().replace("+00:00", "Z")})


@router.post("/google/calendar/events")
async def create_calendar_event(body: CalendarEventIn, uid: str = Depends(current_user),
                                db: AsyncSession = Depends(get_db)):
    if body.end <= body.start:
        raise HTTPException(422, "Event end must be after event start")
    row = await _credential(db, uid, "google")
    if "https://www.googleapis.com/auth/calendar.events" not in row.scopes:
        raise HTTPException(403, "Calendar event permission was not granted; reconnect Google")
    token = await _access_token(db, uid, "google")
    payload = {
        "summary": body.summary,
        "description": body.description,
        "start": {"dateTime": body.start.isoformat(), "timeZone": body.timezone},
        "end": {"dateTime": body.end.isoformat(), "timeZone": body.timezone},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post("https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"}, json=payload)
    if response.is_error:
        raise HTTPException(502, "Google Calendar event creation failed")
    return response.json()


@router.get("/todoist/tasks")
async def todoist_tasks(uid: str = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await _credential(db, uid, "todoist")
    if "data:read" not in row.scopes and "data:read_write" not in row.scopes:
        raise HTTPException(403, "Todoist read permission was not granted; reconnect Todoist")
    token = await _access_token(db, uid, "todoist")
    return await _api_get("https://api.todoist.com/api/v1/tasks", token)


@router.post("/todoist/tasks")
async def create_todoist_task(body: TodoistTaskIn, uid: str = Depends(current_user),
                              db: AsyncSession = Depends(get_db)):
    row = await _credential(db, uid, "todoist")
    if "data:read_write" not in row.scopes:
        raise HTTPException(403, "Todoist write permission was not granted; reconnect with full access")
    token = await _access_token(db, uid, "todoist")
    payload = body.model_dump(exclude_none=True)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post("https://api.todoist.com/api/v1/tasks",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload)
    if response.is_error:
        raise HTTPException(502, "Todoist task creation failed")
    return response.json()


@router.delete("/connections/{provider}")
async def disconnect(provider: str, uid: str = Depends(current_user),
                     db: AsyncSession = Depends(get_db)):
    if provider not in {"google", "todoist"}:
        raise HTTPException(404, "Unknown connected provider")
    row = await _credential(db, uid, provider)
    await db.delete(row)
    await db.commit()
    return {"provider": provider, "connected": False, "message": "Local credentials deleted; revoke app access in provider settings if needed."}


CHAT_READ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "google_gmail_list",
            "description": "Search the connected user's Gmail inbox and return message IDs and thread IDs. Read-only.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "maxLength": 200, "description": "Optional Gmail search query."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
            }, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "google_gmail_get",
            "description": "Read the headers and plain-text body of one Gmail message by its message ID. Read-only.",
            "parameters": {"type": "object", "properties": {
                "message_id": {"type": "string", "minLength": 1, "maxLength": 256},
            }, "required": ["message_id"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "google_calendar_list",
            "description": "List upcoming events in the connected user's primary Google Calendar. Read-only.",
            "parameters": {"type": "object", "properties": {
                "max_results": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            }, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todoist_tasks_list",
            "description": "List tasks from the connected user's Todoist account. Read-only.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


async def execute_chat_read_tool(db: AsyncSession, uid: str, tool_name: str, arguments: dict):
    """Execute only the fixed read-only provider tools exposed to chat."""
    if tool_name == "google_gmail_list":
        row = await _credential(db, uid, "google")
        if "https://www.googleapis.com/auth/gmail.readonly" not in row.scopes:
            raise HTTPException(403, "Gmail read scope is not connected")
        token = await _access_token(db, uid, "google")
        query = arguments.get("query", "")
        if not isinstance(query, str) or len(query) > 200:
            raise HTTPException(422, "Invalid Gmail query")
        maximum = arguments.get("max_results", 10)
        if not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 20:
            raise HTTPException(422, "max_results must be between 1 and 20")
        params = {"maxResults": maximum}
        if query:
            params["q"] = query
        return await _api_get("https://gmail.googleapis.com/gmail/v1/users/me/messages", token, params)
    if tool_name == "google_gmail_get":
        message_id = arguments.get("message_id")
        if not isinstance(message_id, str) or not message_id or len(message_id) > 256 or "/" in message_id:
            raise HTTPException(422, "Invalid Gmail message id")
        row = await _credential(db, uid, "google")
        if "https://www.googleapis.com/auth/gmail.readonly" not in row.scopes:
            raise HTTPException(403, "Gmail read scope is not connected")
        token = await _access_token(db, uid, "google")
        return await _gmail_message_text(token, message_id)
    if tool_name == "google_calendar_list":
        row = await _credential(db, uid, "google")
        if "https://www.googleapis.com/auth/calendar.events" not in row.scopes:
            raise HTTPException(403, "Calendar read scope is not connected")
        maximum = arguments.get("max_results", 10)
        if not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 50:
            raise HTTPException(422, "max_results must be between 1 and 50")
        token = await _access_token(db, uid, "google")
        return await _api_get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events", token,
            {"maxResults": maximum, "singleEvents": "true", "orderBy": "startTime",
             "timeMin": _utcnow().isoformat().replace("+00:00", "Z")},
        )
    if tool_name == "todoist_tasks_list":
        row = await _credential(db, uid, "todoist")
        if "data:read" not in row.scopes and "data:read_write" not in row.scopes:
            raise HTTPException(403, "Todoist read scope is not connected")
        token = await _access_token(db, uid, "todoist")
        return await _api_get("https://api.todoist.com/api/v1/tasks", token)
    raise HTTPException(403, "Tool is not in the read-only allowlist")
