import json

import pytest
from pydantic import ValidationError

from chat.settings import Settings


def test_default_mcp_servers_is_backlog_inprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_SERVERS", raising=False)
    loaded = Settings.from_env()
    assert len(loaded.mcp_servers) == 1
    assert loaded.mcp_servers[0].id == "backlog"
    assert loaded.mcp_servers[0].kind == "inprocess"


def test_mcp_servers_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "MCP_SERVERS",
        json.dumps(
            [
                {"id": "backlog", "kind": "inprocess"},
                {"id": "docs", "kind": "http", "url": "http://127.0.0.1:9/mcp"},
            ]
        ),
    )
    loaded = Settings.from_env()
    assert [s.kind for s in loaded.mcp_servers] == ["inprocess", "http"]


def test_mcp_servers_duplicate_id_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "MCP_SERVERS",
        json.dumps(
            [
                {"id": "backlog", "kind": "inprocess"},
                {"id": "backlog", "kind": "http", "url": "http://127.0.0.1:9/mcp"},
            ]
        ),
    )
    with pytest.raises(ValidationError):
        Settings.from_env()
