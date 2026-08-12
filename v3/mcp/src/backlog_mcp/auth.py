from mcp.server.auth.provider import AccessToken

from .jwt_tokens import TokenError, decode_token


class HostJwtVerifier:
    """Host が HS256 で署名した MCP 呼び出し用 JWT を検証する。"""

    def __init__(self, secret: str, audience: str, issuer: str) -> None:
        self._secret = secret
        self._audience = audience
        self._issuer = issuer

    async def verify_token(self, token: str) -> AccessToken | None:
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
