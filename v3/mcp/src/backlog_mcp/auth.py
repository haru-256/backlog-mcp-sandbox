"""`/mcp` の Bearer JWT（typ=mcp）を扱う。"""

from mcp.server.auth.provider import AccessToken

from .jwt_tokens import TokenError, decode_token


class HostJwtVerifier:
    """SDK が `/mcp` の Bearer を渡してきたとき、typ=mcp だけを通す。"""

    def __init__(self, secret: str, issuer: str) -> None:
        """検証に使う値を覚える。

        Args:
            secret: Host と同じ HMAC 秘密鍵。
            issuer: JWT の `iss`。Host の公開 URL。
        """
        self._secret = secret
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
