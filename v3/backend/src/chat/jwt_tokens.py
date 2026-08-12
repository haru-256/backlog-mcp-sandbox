import time
from typing import Any, Literal

import jwt

TokenType = Literal["connect", "mcp"]


def sign_token(
    *,
    secret: str,
    typ: TokenType,
    user_id: str,
    org_id: str,
    issuer: str,
    ttl_seconds: int,
    audience: str | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "typ": typ,
        "sub": user_id,
        "org": org_id,
        "iss": issuer,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    if audience is not None:
        payload["aud"] = audience
    return jwt.encode(payload, secret, algorithm="HS256")
