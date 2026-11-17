import os
import jwt
from fastapi import Header, HTTPException

APP_ENV = os.getenv("APP_ENV", "development")
JWT_SECRET = os.getenv("JWT_SECRET", "")

async def current_user(authorization: str | None = Header(default=None),
                       x_user_id: str | None = Header(default=None)) -> str:
    if APP_ENV == "development" and x_user_id:
        return x_user_id
    if len(JWT_SECRET) < 32:
        raise HTTPException(503, "JWT_SECRET must be configured with at least 32 characters")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer token required")
    try:
        claims = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET,
                            algorithms=["HS256"], options={"require": ["exp", "sub"]})
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise jwt.InvalidTokenError()
        return claims["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired bearer token")
