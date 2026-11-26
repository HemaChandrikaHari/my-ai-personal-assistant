import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import oauth_integrations as oauth
from app.db import Base, OAuthCredential


@pytest.fixture
def token_key(monkeypatch):
    monkeypatch.setattr(oauth, "TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        yield session
    await engine.dispose()


def mock_http_client(monkeypatch, handler):
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        return real_client(
            *args,
            transport=httpx.MockTransport(handler),
            **kwargs,
        )

    monkeypatch.setattr(oauth.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_todoist_authorization_url_contains_callback_and_state(monkeypatch, db_session):
    monkeypatch.setattr(oauth, "TODOIST_CLIENT_ID", "todoist-client")
    monkeypatch.setattr(oauth, "TODOIST_CLIENT_SECRET", "todoist-secret")
    monkeypatch.setattr(oauth, "TODOIST_REDIRECT_URI", "http://localhost:8000/callback")
    monkeypatch.setattr(oauth, "TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    result = await oauth.todoist_start(uid="owner-1", db=db_session)
    params = parse_qs(urlparse(result["authorization_url"]).query)

    assert params["client_id"] == ["todoist-client"]
    assert params["redirect_uri"] == ["http://localhost:8000/callback"]
    assert params["scope"] == ["data:read_write"]
    assert params["response_type"] == ["code"]
    assert len(params["state"][0]) >= 32


@pytest.mark.asyncio
async def test_todoist_code_exchange_sends_redirect_uri(monkeypatch):
    monkeypatch.setattr(oauth, "TODOIST_CLIENT_ID", "client")
    monkeypatch.setattr(oauth, "TODOIST_CLIENT_SECRET", "secret")
    monkeypatch.setattr(oauth, "TODOIST_REDIRECT_URI", "https://assistant.example/callback")

    def handler(request):
        assert request.url.host == "api.todoist.com"
        form = parse_qs(request.content.decode())
        assert form["client_id"] == ["client"]
        assert form["client_secret"] == ["secret"]
        assert form["code"] == ["one-time-code"]
        assert form["redirect_uri"] == ["https://assistant.example/callback"]
        return httpx.Response(200, json={
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "scope": "data:read_write",
        })

    mock_http_client(monkeypatch, handler)
    data = await oauth._exchange("todoist", "one-time-code")
    assert data["access_token"] == "access"
    assert data["refresh_token"] == "refresh"


@pytest.mark.asyncio
async def test_expired_todoist_token_refreshes_and_rotates_refresh_token(
    monkeypatch, token_key, db_session
):
    monkeypatch.setattr(oauth, "TODOIST_CLIENT_ID", "client")
    monkeypatch.setattr(oauth, "TODOIST_CLIENT_SECRET", "secret")
    db_session.add(OAuthCredential(
        user_id="owner-1",
        provider="todoist",
        access_token_encrypted=oauth._encrypt("old-access"),
        refresh_token_encrypted=oauth._encrypt("old-refresh"),
        scopes="data:read_write",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    await db_session.commit()

    def handler(request):
        assert request.url.path == "/oauth/access_token"
        form = parse_qs(request.content.decode())
        assert form["grant_type"] == ["refresh_token"]
        assert form["refresh_token"] == ["old-refresh"]
        return httpx.Response(200, json={
            "access_token": "new-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 3600,
            "scope": "data:read_write",
        })

    mock_http_client(monkeypatch, handler)
    token = await oauth._access_token(db_session, "owner-1", "todoist")
    assert token == "new-access"
    row = await oauth._credential(db_session, "owner-1", "todoist")
    assert oauth._decrypt(row.refresh_token_encrypted) == "rotated-refresh"
    assert oauth._aware_utc(row.expires_at) > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_gmail_message_parser_extracts_headers_and_plain_text(monkeypatch):
    encoded = base64.urlsafe_b64encode(b"Hello from the inbox").decode().rstrip("=")

    async def fake_api_get(url, token, params=None):
        assert url.endswith("/messages/message-123")
        assert token == "gmail-token"
        assert params == {"format": "full"}
        return {
            "id": "message-123",
            "threadId": "thread-1",
            "snippet": "Hello",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Integration test"},
                ],
                "parts": [{
                    "mimeType": "text/plain",
                    "body": {"data": encoded},
                }],
            },
        }

    monkeypatch.setattr(oauth, "_api_get", fake_api_get)
    result = await oauth._gmail_message_text("gmail-token", "message-123")
    assert result["from"] == "sender@example.com"
    assert result["subject"] == "Integration test"
    assert result["body_text"] == "Hello from the inbox"


@pytest.mark.asyncio
async def test_oauth_state_cannot_be_reused_or_consumed_by_another_provider(db_session):
    state = await oauth._new_state(db_session, "owner-1", "google")

    with pytest.raises(HTTPException):
        await oauth._consume_state(db_session, state, "todoist")

    assert await oauth._consume_state(db_session, state, "google") == "owner-1"
    with pytest.raises(Exception):
        await oauth._consume_state(db_session, state, "google")


@pytest.mark.asyncio
async def test_google_and_todoist_read_write_api_calls_use_user_scoped_tokens(
    monkeypatch, token_key, db_session
):
    from datetime import datetime
    from app import oauth_integrations as provider

    google_scopes = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.events"
    db_session.add_all([
        OAuthCredential(
            user_id="alice",
            provider="google",
            access_token_encrypted=provider._encrypt("alice-google-token"),
            refresh_token_encrypted=None,
            scopes=google_scopes,
        ),
        OAuthCredential(
            user_id="alice",
            provider="todoist",
            access_token_encrypted=provider._encrypt("alice-todoist-token"),
            refresh_token_encrypted=None,
            scopes="data:read_write",
        ),
    ])
    await db_session.commit()

    def handler(request):
        if request.url.host == "gmail.googleapis.com":
            assert request.headers["authorization"] == "Bearer alice-google-token"
            assert request.url.params["maxResults"] == "2"
            return httpx.Response(200, json={"messages": [{"id": "mail-1"}]})
        if request.url.host == "www.googleapis.com":
            assert request.headers["authorization"] == "Bearer alice-google-token"
            if request.method == "GET":
                return httpx.Response(200, json={"items": [{"id": "event-1"}]})
            payload = __import__("json").loads(request.content)
            assert payload["summary"] == "Integration test event"
            return httpx.Response(200, json={"id": "event-created", **payload})
        if request.url.host == "api.todoist.com":
            assert request.headers["authorization"] == "Bearer alice-todoist-token"
            if request.method == "GET":
                return httpx.Response(200, json={"results": [{"id": "task-1"}]})
            payload = __import__("json").loads(request.content)
            assert payload["content"] == "Integration test task"
            return httpx.Response(200, json={"id": "task-created", **payload})
        raise AssertionError(f"Unexpected provider URL: {request.url}")

    mock_http_client(monkeypatch, handler)

    gmail = await provider.gmail_messages(max_results=2, uid="alice", db=db_session)
    calendar = await provider.calendar_events(max_results=5, uid="alice", db=db_session)
    tasks = await provider.todoist_tasks(uid="alice", db=db_session)
    event = await provider.create_calendar_event(
        provider.CalendarEventIn(
            summary="Integration test event",
            start=datetime(2026, 11, 27, 10, 0, tzinfo=timezone.utc),
            end=datetime(2026, 11, 27, 10, 30, tzinfo=timezone.utc),
        ),
        uid="alice",
        db=db_session,
    )
    task = await provider.create_todoist_task(
        provider.TodoistTaskIn(content="Integration test task"),
        uid="alice",
        db=db_session,
    )

    assert gmail["messages"][0]["id"] == "mail-1"
    assert calendar["items"][0]["id"] == "event-1"
    assert tasks["results"][0]["id"] == "task-1"
    assert event["id"] == "event-created"
    assert task["id"] == "task-created"


@pytest.mark.asyncio
async def test_provider_credentials_are_isolated_between_users(token_key, db_session):
    from fastapi import HTTPException

    db_session.add(OAuthCredential(
        user_id="alice",
        provider="google",
        access_token_encrypted=oauth._encrypt("alice-only-token"),
        scopes="https://www.googleapis.com/auth/gmail.readonly",
    ))
    await db_session.commit()

    assert oauth._decrypt((await oauth._credential(db_session, "alice", "google")).access_token_encrypted) == "alice-only-token"
    with pytest.raises(HTTPException) as error:
        await oauth._credential(db_session, "bob", "google")
    assert error.value.status_code == 404
