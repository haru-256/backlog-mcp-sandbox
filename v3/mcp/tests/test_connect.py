import pytest
from starlette.testclient import TestClient

from backlog_mcp.jwt_tokens import decode_token
from backlog_mcp.server import create_server
from backlog_mcp.settings import Settings
from backlog_mcp.store import MemoryStore, SpaceApp

SECRET = "dev-mcp-jwt-secret-change-me-please!!"
ISSUER = "http://localhost:8003"
AUDIENCE = "http://localhost:3333"


def _settings() -> Settings:
    return Settings(
        mcp_jwt_secret=SECRET,
        mcp_public_url=AUDIENCE,
        host_public_url=ISSUER,
        frontend_public_url="http://localhost:5173",
    )


def _connect_jwt(user: str = "alice", org: str = "acme") -> str:
    import time

    import jwt

    now = int(time.time())
    return jwt.encode(
        {
            "typ": "connect",
            "sub": user,
            "org": org,
            "iss": ISSUER,
            "iat": now,
            "exp": now + 600,
        },
        SECRET,
        algorithm="HS256",
    )


class FakeApi:
    async def exchange_code(
        self, domain: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> tuple[str, str | None]:
        del client_id, client_secret, redirect_uri
        return f"access-{domain}-{code}", "refresh"

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, object]]:
        del domain, access_token, status_id, count
        return []


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_health_does_not_need_jwt() -> None:
    server = create_server(_settings(), store=MemoryStore(), api=FakeApi())
    app = server.streamable_http_app(host="127.0.0.1")
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_connect_get_renders_form() -> None:
    store = MemoryStore()
    server = create_server(_settings(), store=store, api=FakeApi())
    app = server.streamable_http_app(host="127.0.0.1")
    with TestClient(app) as client:
        response = client.get("/connect", params={"state": _connect_jwt()})
    assert response.status_code == 200
    assert "スペース" in response.text
    assert "alice" in response.text


def test_connect_post_saves_unregistered_space_app() -> None:
    store = MemoryStore()
    server = create_server(_settings(), store=store, api=FakeApi())
    app = server.streamable_http_app(host="127.0.0.1")
    with TestClient(app, follow_redirects=False) as client:
        response = client.post(
            "/connect",
            data={
                "state": _connect_jwt(),
                "space": "acme.backlog.com",
                "client_id": "cid",
                "client_secret": "csecret",
            },
        )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://acme.backlog.com/OAuth2AccessRequest.action")
    saved = store.get_space_app("acme.backlog.com")
    assert saved is not None
    assert saved.client_id == "cid"
    assert len(store.pending) == 1


def test_connect_post_requires_client_when_unregistered() -> None:
    store = MemoryStore()
    server = create_server(_settings(), store=store, api=FakeApi())
    app = server.streamable_http_app(host="127.0.0.1")
    with TestClient(app, follow_redirects=False) as client:
        response = client.post(
            "/connect",
            data={"state": _connect_jwt(), "space": "acme.backlog.com"},
        )
    assert response.status_code == 400
    assert "未登録" in response.text


def test_callback_stores_connection() -> None:
    store = MemoryStore()
    store.put_space_app(SpaceApp(domain="acme.backlog.com", client_id="cid", client_secret="sec"))
    from backlog_mcp.store import PendingOAuth

    store.put_pending(
        "oauth-state", PendingOAuth(user_id="alice", org_id="acme", domain="acme.backlog.com")
    )
    server = create_server(_settings(), store=store, api=FakeApi())
    app = server.streamable_http_app(host="127.0.0.1")
    with TestClient(app, follow_redirects=False) as client:
        response = client.get(
            "/callback",
            params={"code": "abc", "state": "oauth-state"},
        )
    assert response.status_code == 302
    assert "connected=1" in response.headers["location"]
    conn = store.get_connection("alice", "acme.backlog.com")
    assert conn is not None
    assert conn.access_token == "access-acme.backlog.com-abc"


def test_decode_connect_token() -> None:
    token = _connect_jwt()
    payload = decode_token(token, SECRET, "connect", issuer=ISSUER)
    assert payload["sub"] == "alice"
    assert payload["org"] == "acme"
