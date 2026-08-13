"""`/mcp` の Bearer JWT（typ=mcp）を扱う。

接続画面（typ=connect）はここを通らない。`custom_route` の `/connect` が
`jwt_tokens.decode_token` を直接呼ぶ。
"""

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken

from .jwt_tokens import TokenError, decode_token


class HostJwtVerifier:
    """SDK が `/mcp` の Bearer を渡してきたとき、typ=mcp だけを通す。"""

    def __init__(self, secret: str, audience: str, issuer: str) -> None:
        self._secret = secret
        self._audience = audience
        self._issuer = issuer

    async def verify_token(self, token: str) -> AccessToken | None:
        """不正な token は例外にせず None を返す。SDK が 401 にする。

        Args:
            token: Authorization ヘッダの Bearer。

        Returns:
            通ったときだけ AccessToken。`subject` が Chat の user_id。
        """
        try:
            payload = decode_token(
                token,
                self._secret,
                "mcp",
                audience=self._audience,
                issuer=self._issuer,
            )
        except TokenError:
            return None

        org = payload["org"]
        return AccessToken(
            token=token,
            client_id="chat-host",
            scopes=["mcp"],
            subject=payload["sub"],
            claims={"org": org, "iss": payload.get("iss")},
        )


def current_user_id() -> str:
    """いまの `/mcp` 呼び出しの Chat ユーザー ID。JWT の `sub`。

    Raises:
        RuntimeError: Bearer が無い、または subject が空の場合。
    """
    token = get_access_token()
    if token is None or not token.subject:
        raise RuntimeError("authenticated user is missing")
    return token.subject
