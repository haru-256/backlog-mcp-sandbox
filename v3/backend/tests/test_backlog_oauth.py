from urllib.parse import parse_qs

import httpx
import pytest
from pytest import MonkeyPatch

from chat.backlog_oauth import authorize_url, exchange_code, refresh_access_token
from chat.settings import Settings


def test_settings_reads_backlog_client_and_redirect(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "k")
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


@pytest.mark.anyio
async def test_refresh_access_token_posts_refresh_grant() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://acme.backlog.com/api/v2/oauth2/token"
        assert dict(request.headers)["content-type"].startswith(
            "application/x-www-form-urlencoded"
        )
        body = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert body["grant_type"] == "refresh_token"
        assert body["refresh_token"] == "old-rtk"
        assert body["client_id"] == "cid"
        assert body["client_secret"] == "csecret"
        assert "code" not in body
        return httpx.Response(
            200, json={"access_token": "new-atk", "refresh_token": "new-rtk"}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        access, refresh = await refresh_access_token(
            http, "acme.backlog.com", "cid", "csecret", "old-rtk"
        )
    assert access == "new-atk"
    assert refresh == "new-rtk"


@pytest.mark.anyio
async def test_refresh_keeps_old_refresh_when_response_omits_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"access_token": "new-atk"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        access, refresh = await refresh_access_token(
            http, "acme.backlog.com", "cid", "csecret", "old-rtk"
        )
    assert access == "new-atk"
    assert refresh == "old-rtk"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
