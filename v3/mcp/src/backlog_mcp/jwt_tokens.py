"""Host が署名した JWT を検証する。

`/mcp` の Bearer は `typ=mcp`。発行は Host（`v3/backend`）側。
このモジュールは検証だけをする。
"""

from typing import Any, Literal

import jwt
from jwt import InvalidTokenError

TokenType = Literal["mcp"]


class TokenError(ValueError):
    """JWT が不正、期限切れ、または typ が一致しない。"""


def decode_token(
    token: str,
    secret: str,
    expected_typ: TokenType,
    issuer: str | None = None,
) -> dict[str, Any]:
    """Host が署名した JWT を検証し、claims を返す。

    Args:
        token: 検証する JWT。
        secret: Host と同じ HMAC 秘密鍵。
        expected_typ: この呼び出しで許す `typ`。
        issuer: 付けるなら claim `iss`。通常は Host の公開 URL。

    Returns:
        `sub`（user_id）と `org`（org_id）を含む claims。

    Raises:
        TokenError: 署名・期限・typ・必須 claim のいずれかが合わない場合。
    """
    options: dict[str, Any] = {"require": ["exp", "iat", "sub", "org", "typ"]}
    kwargs: dict[str, Any] = {
        "algorithms": ["HS256"],
        "options": options,
    }
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
