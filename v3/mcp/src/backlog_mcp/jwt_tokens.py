from typing import Any, Literal

import jwt
from jwt import InvalidTokenError

TokenType = Literal["connect", "mcp"]


class TokenError(ValueError):
    """JWT が不正、期限切れ、または typ が一致しない。"""


def decode_token(
    token: str,
    secret: str,
    expected_typ: TokenType,
    audience: str | None = None,
    issuer: str | None = None,
) -> dict[str, Any]:
    """Host が署名した JWT を検証し、claims を返す。"""
    options: dict[str, Any] = {"require": ["exp", "iat", "sub", "org", "typ"]}
    kwargs: dict[str, Any] = {
        "algorithms": ["HS256"],
        "options": options,
    }
    if audience is not None:
        kwargs["audience"] = audience
    if issuer is not None:
        kwargs["issuer"] = issuer
    try:
        payload = jwt.decode(token, secret, **kwargs)
    except InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("typ") != expected_typ:
        raise TokenError(f"unexpected token typ: {payload.get('typ')!r}")

    sub = payload.get("sub")
    org = payload.get("org")
    if not isinstance(sub, str) or not sub:
        raise TokenError("sub is required")
    if not isinstance(org, str) or not org:
        raise TokenError("org is required")
    return payload
