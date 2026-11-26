import pytest
from pydantic import ValidationError

from app.config import Settings


def test_development_settings_keep_local_defaults():
    settings = Settings(_env_file=None)
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.blueticks_mcp_url == "https://api.blueticks.co/mcp"


def test_production_rejects_placeholder_jwt_secret():
    with pytest.raises(ValidationError, match="Production requires a unique JWT_SECRET"):
        Settings(app_env="production", jwt_secret="development-only-change-me", _env_file=None)


def test_production_accepts_long_unique_jwt_secret():
    settings = Settings(
        app_env="production",
        jwt_secret="a" * 48,
        _env_file=None,
    )
    assert settings.app_env == "production"
