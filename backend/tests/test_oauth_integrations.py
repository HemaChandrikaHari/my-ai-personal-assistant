import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base
from app import oauth_integrations as oauth


@pytest.mark.asyncio
async def test_oauth_state_is_provider_bound_and_one_time():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        mismatched = await oauth._new_state(db, "user-1", "google")
        with pytest.raises(HTTPException) as mismatch:
            await oauth._consume_state(db, mismatched, "todoist")
        assert mismatch.value.status_code == 400

        valid = await oauth._new_state(db, "user-1", "google")
        uid = await oauth._consume_state(db, valid, "google")
        assert uid == "user-1"
        with pytest.raises(HTTPException):
            await oauth._consume_state(db, valid, "google")
    await engine.dispose()


def test_oauth_tokens_are_encrypted_and_round_trip(monkeypatch):
    monkeypatch.setattr(oauth, "TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    raw = "access-token-that-must-not-be-stored-in-plaintext"
    encrypted = oauth._encrypt(raw)
    assert encrypted != raw
    assert raw not in encrypted
    assert oauth._decrypt(encrypted) == raw


def test_missing_encryption_key_fails_closed(monkeypatch):
    monkeypatch.setattr(oauth, "TOKEN_ENCRYPTION_KEY", "")
    with pytest.raises(HTTPException) as error:
        oauth._encrypt("sensitive")
    assert error.value.status_code == 503
