from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://assistant:assistant@localhost:5432/assistant"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-only-change-me"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    blueticks_mcp_url: str = "https://api.blueticks.co/mcp"
    blueticks_bearer_token: str = ""
    blueticks_read_only_tools: str = ""
    blueticks_send_tools: str = ""
    blueticks_secret_arn: str | None = None
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"
    token_encryption_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    todoist_client_id: str = ""
    todoist_client_secret: str = ""
    todoist_redirect_uri: str = ""
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.app_env.lower() in {"production", "prod"}:
            if not (self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url):
                raise ValueError("Production requires OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL")
            if not self.token_encryption_key:
                raise ValueError("Production requires TOKEN_ENCRYPTION_KEY")
        if self.blueticks_mcp_url != "https://api.blueticks.co/mcp":
            raise ValueError("BLUETICKS_MCP_URL must remain https://api.blueticks.co/mcp")
        return self


settings = Settings()
