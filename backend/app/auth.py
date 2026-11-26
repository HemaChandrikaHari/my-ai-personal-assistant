import asyncio\nimport jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException

from app.config import settings

APP_ENV = settings.app_env.lower()
JWT_SECRET = settings.jwt_secret
OIDC_ISSUER = settings.oidc_issuer or ""
OIDC_AUDIENCE = settings.oidc_audience or ""
OIDC_JWKS_URL = settings.oidc_jwks_url or ""
_jwks_client = PyJWKClient(OIDC_JWKS_URL, cache_keys=True) if OIDC_JWKS_URL else None


async def current_user(authorization: str | None = Header(default=None),
                       x_user_id: str | None = Header(default=None)) -> str:
    if APP_ENV == "development" and x_user_id:
        return x_user_id
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer token required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        if OIDC_ISSUER and OIDC_AUDIENCE and _jwks_client:
            signing_key = (await asyncio.to_thread(_jwks_client.get_signing_key_from_jwt, token)).key
            claims = jwt.decode(
                token, signing_key, algorithms=["RS256"], issuer=OIDC_ISSUER,
                audience=OIDC_AUDIENCE,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        else:
            if APP_ENV in {"production", "prod"}:
                raise HTTPException(503, "Production OIDC is not configured")
            if len(JWT_SECRET) < 32:
                raise HTTPException(503, "JWT_SECRET must be configured with at least 32 characters")
            claims = jwt.decode(
                token, JWT_SECRET, algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise jwt.InvalidTokenError("Missing subject")
        return subject
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid or expired bearer token")
