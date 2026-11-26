import pytest
from pydantic import ValidationError

from app.config import Settings


def test_development_settings_keep_local_defaults():
    settings = Settings(_env_file=None)
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.blueticks_mcp_url == "https://api.blueticks.co/mcp"


def test_production_rejects_missing_oidc_configuration():
    with pytest.raises(ValidationError, match="Production requires OIDC_ISSUER"):
        Settings(app_env="production", _env_file=None)


def test_production_accepts_complete_oidc_and_encryption_configuration():
    settings = Settings(
        app_env="production",
        frontend_url="https://assistant.example.com",
        oidc_issuer="https://issuer.example.com/",
        oidc_audience="assistant-api",
        oidc_jwks_url="https://issuer.example.com/.well-known/jwks.json",
        token_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        _env_file=None,
    )
    assert settings.app_env == "production"
    assert settings.oidc_audience == "assistant-api"


def test_blueticks_endpoint_is_pinned():
    with pytest.raises(ValidationError, match="BLUETICKS_MCP_URL must remain"):
        Settings(blueticks_mcp_url="https://example.com/mcp", _env_file=None)


def test_wildcard_cors_is_rejected():
    with pytest.raises(ValidationError, match="CORS_ORIGINS must not contain a wildcard"):
        Settings(cors_origins="*", _env_file=None)
