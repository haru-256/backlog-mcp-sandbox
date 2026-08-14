"""複数 MCP を Client のリストとして開き、prefix して LLM に見せる。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent
from openai.types.chat import ChatCompletionToolParam

from .connections import NOT_CONNECTED, REFRESH_FAILED
from .session_tokens import SessionAuth
from .settings import HttpMcp, InProcessMcp, Settings
from .store import MemoryStore

_HOST_HIDDEN_PARAMS = ("space", "access_token")


def _prefix_tool_name(server_id: str, tool_name: str) -> str:
    return f"{server_id}_{tool_name}"


def _split_prefixed(name: str, server_ids: list[str]) -> tuple[str, str] | None:
    for server_id in sorted(server_ids, key=len, reverse=True):
        prefix = f"{server_id}_"
        if name.startswith(prefix):
            rest = name[len(prefix) :]
            if rest:
                return server_id, rest
    return None


def _hide_host_params(schema: dict[str, Any]) -> dict[str, Any]:
    parameters = dict(schema)
    properties = dict(parameters.get("properties") or {})
    for key in _HOST_HIDDEN_PARAMS:
        properties.pop(key, None)
    parameters["properties"] = properties
    if "required" in parameters:
        parameters["required"] = [
            item for item in parameters["required"] if item not in _HOST_HIDDEN_PARAMS
        ]
    return parameters


def _tool_result_text(result: object) -> str:
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        text = json.dumps(structured, ensure_ascii=False)
    else:
        blocks = [b.text for b in getattr(result, "content", []) if isinstance(b, TextContent)]
        text = "\n".join(blocks) if blocks else "(tool は内容を返さなかった)"
    if getattr(result, "is_error", False):
        return f"tool error: {text}"
    return text


def create_inprocess_server(server_id: str) -> MCPServer[None]:
    """id に対応する同一プロセス MCPServer を返す。

    Args:
        server_id: Settings.mcp_servers の inprocess id。

    Returns:
        開く対象の MCPServer。

    Raises:
        ValueError: 未知の id。
    """
    if server_id == "backlog":
        from backlog_mcp.server import create_server
        from backlog_mcp.settings import Settings as BacklogSettings

        return create_server(BacklogSettings.from_env())
    raise ValueError(f"unknown in-process MCP id: {server_id}")


class McpHub:
    """複数 Client を束ね、LLM 向けには prefix 付き tool 名だけを出す。"""

    def __init__(
        self,
        clients: dict[str, Client],
        store: MemoryStore,
        user_id: str,
        session_auth: SessionAuth | None,
    ) -> None:
        """開いた Client と、Backlog 注入用の接続を持つ。

        Args:
            clients: server id → 初期化済み Client。
            store: 未接続判定に使う接続表。
            user_id: Chat 上のユーザー ID。
            session_auth: この chat で発行した Backlog access。未接続・失敗なら None。
        """
        self._clients = clients
        self._store = store
        self._user_id = user_id
        self._session_auth = session_auth

    async def list_tools(self) -> list[ChatCompletionToolParam]:
        """全サーバーの tools を prefix して返す。space と access_token は schema から除く。

        Returns:
            LLM に渡す function tool のリスト。
        """
        tools: list[ChatCompletionToolParam] = []
        for server_id, client in self._clients.items():
            listed = await client.list_tools()
            for tool in listed.tools:
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": _prefix_tool_name(server_id, tool.name),
                            "description": tool.description or "",
                            "parameters": _hide_host_params(tool.input_schema),
                        },
                    }
                )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """prefix を外して該当 Client へ振る。backlog の list_issues には Host が space と token を入れる。

        Args:
            name: LLM が見た tool 名（prefix 付き）。
            arguments: LLM が付けた引数。

        Returns:
            結果テキスト。tool 自身の失敗は "tool error: ..." になり得る。
        """
        split = _split_prefixed(name, list(self._clients))
        if split is None:
            return f"tool error: unknown tool: {name}"
        server_id, tool_name = split
        client = self._clients[server_id]

        if server_id == "backlog" and tool_name == "list_issues":
            if self._session_auth is None:
                connection = self._store.get_connection(self._user_id)
                return NOT_CONNECTED if connection is None else REFRESH_FAILED
            arguments = {
                "space": self._session_auth.domain,
                "access_token": self._session_auth.access_token,
                "status_id": arguments.get("status_id"),
            }
        else:
            arguments = {k: v for k, v in arguments.items() if k != "access_token"}

        result = await client.call_tool(tool_name, arguments)
        return _tool_result_text(result)


@asynccontextmanager
async def open_mcp_hub(
    settings: Settings,
    store: MemoryStore,
    user_id: str,
    session_auth: SessionAuth | None,
) -> AsyncIterator[McpHub]:
    """設定された MCP を開き、閉じるまで Hub を貸す。

    Args:
        settings: mcp_servers を含む設定。
        store: 接続表。
        user_id: Chat 上のユーザー ID。
        session_auth: この chat の Backlog access。

    Yields:
        初期化済みの McpHub。
    """
    async with AsyncExitStack() as stack:
        clients: dict[str, Client] = {}
        for spec in settings.mcp_servers:
            if isinstance(spec, InProcessMcp):
                server = create_inprocess_server(spec.id)
                client = await stack.enter_async_context(Client(server))
            elif isinstance(spec, HttpMcp):
                client = await stack.enter_async_context(Client(spec.url))
            else:
                raise TypeError(f"unsupported MCP spec: {spec}")
            clients[spec.id] = client
        yield McpHub(clients, store, user_id, session_auth)
