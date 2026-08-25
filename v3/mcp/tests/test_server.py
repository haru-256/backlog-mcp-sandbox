import pytest
from starlette.testclient import TestClient

from backlog_mcp.server import create_server
from backlog_mcp.settings import Settings


class FakeApi:
    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, object]]:
        del domain, access_token, status_id, count
        return []


def test_settings_does_not_require_backlog_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACKLOG_CLIENT_ID", raising=False)
    monkeypatch.delenv("BACKLOG_CLIENT_SECRET", raising=False)
    loaded = Settings()
    assert loaded.port == 3333


def test_health() -> None:
    server = create_server(Settings(), api=FakeApi())
    app = server.streamable_http_app(host="127.0.0.1")
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
