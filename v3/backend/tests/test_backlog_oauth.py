import httpx
import pytest
from pytest import MonkeyPatch

from chat.backlog_oauth import authorize_url, exchange_code
from chat.settings import Settings


def test_settings_reads_backlog_client_and_redirect(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "k")
    monkeypatch.setenv("MCP_JWT_SECRET", "s")
    monkeypatch.setenv("BACKLOG_CLIENT_ID", "cid")
    monkeypatch.setenv("BACKLOG_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("HOST_PUBLIC_URL", "http://localhost:8003")
    monkeypatch.setenv("FRONTEND_PUBLIC_URL", "http://localhost:5173")
    loaded = Settings.from_env()
    assert loaded.backlog_client_id == "cid"
    assert loaded.backlog_client_secret == "csecret"
    assert loaded.oauth_redirect_uri() == "http://localhost:8003/backlog/callback"


def test_authorize_url_uses_space_host() -> None:
    url = authorize_url(
        "other.backlog.com", "cid", "http://localhost:8003/backlog/callback", "st"
    )
    assert url.startswith("https://other.backlog.com/OAuth2AccessRequest.action")
    assert "client_id=cid" in url
    assert "state=st" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8003%2Fbacklog%2Fcallback" in url


@pytest.mark.anyio
async def test_exchange_code_posts_to_space_token_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://acme.backlog.com/api/v2/oauth2/token"
        return httpx.Response(200, json={"access_token": "atk", "refresh_token": "rtk"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        access, refresh = await exchange_code(
            http,
            "acme.backlog.com",
            "cid",
            "csecret",
            "code-1",
            "http://localhost:8003/backlog/callback",
        )
    assert access == "atk"
    assert refresh == "rtk"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
