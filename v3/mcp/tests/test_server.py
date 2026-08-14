import time

import jwt
import pytest
from starlette.testclient import TestClient

from backlog_mcp.jwt_tokens import decode_token
from backlog_mcp.server import create_server
from backlog_mcp.settings import Settings

SECRET = "dev-mcp-jwt-secret-change-me-please!!"
ISSUER = "http://localhost:8003"
AUDIENCE = "http://localhost:3333"


def _settings() -> Settings:
    return Settings(
        mcp_jwt_secret=SECRET,
        mcp_public_url=AUDIENCE,
        host_public_url=ISSUER,
    )


class FakeApi:
    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, object]]:
        del domain, access_token, status_id, count
        return []


def test_settings_does_not_require_backlog_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_JWT_SECRET", SECRET)
    monkeypatch.delenv("BACKLOG_CLIENT_ID", raising=False)
    monkeypatch.delenv("BACKLOG_CLIENT_SECRET", raising=False)
    loaded = Settings()
    assert loaded.mcp_jwt_secret == SECRET


def test_health_does_not_need_jwt() -> None:
    server = create_server(_settings(), api=FakeApi())
    app = server.streamable_http_app(host="127.0.0.1")
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_decode_mcp_token() -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "typ": "mcp",
            "sub": "alice",
            "org": "acme",
            "iss": ISSUER,
            "iat": now,
            "exp": now + 600,
        },
        SECRET,
        algorithm="HS256",
    )
    payload = decode_token(token, SECRET, "mcp", issuer=ISSUER)
    assert payload["sub"] == "alice"
    assert payload["org"] == "acme"
