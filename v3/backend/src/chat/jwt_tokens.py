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
    """Host が MCP 向けに発行する HS256 JWT を作る。

    Args:
        secret: HMAC 秘密鍵。MCP と同じ値。
        typ: `connect`（接続画面）または `mcp`（tool 呼び出し）。
        user_id: Chat 上のユーザー ID。claim `sub`。
        org_id: Chat テナント ID。claim `org`。
        issuer: claim `iss`。通常は Host の公開 URL。
        ttl_seconds: 発行からの有効秒数。
        audience: claim `aud`。MCP 呼び出し時は MCP の公開 URL。接続用は省略する。

    Returns:
        署名済み JWT 文字列。
    """
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
