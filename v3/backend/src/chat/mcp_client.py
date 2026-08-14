import json
from typing import Any

from mcp import ClientSession
from mcp.types import TextContent
from openai.types.chat import ChatCompletionToolParam

from .connections import connected_spaces, resolve_connection
from .store import MemoryStore

_CONNECTED_SPACES_TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {
        "name": "list_connected_spaces",
        "description": "このユーザーが OAuth 接続した Backlog スペースを返す。",
        "parameters": {"type": "object", "properties": {}},
    },
}


def _hide_access_token(schema: dict[str, Any]) -> dict[str, Any]:
    parameters = dict(schema)
    properties = dict(parameters.get("properties") or {})
    properties.pop("access_token", None)
    parameters["properties"] = properties
    if "required" in parameters:
        parameters["required"] = [item for item in parameters["required"] if item != "access_token"]
    return parameters


class BacklogMCP:
    """MCP サーバーに接続するためのクライアント。"""

    def __init__(self, session: ClientSession, store: MemoryStore, user_id: str) -> None:
        """セッションと、token を注入するための store を保持する。

        Args:
            session: MCP サーバーとの通信を行うセッション。
            store: Host が持つ接続表。
            user_id: Chat 上のユーザー ID。
        """
        self._session: ClientSession = session
        self._store: MemoryStore = store
        self._user_id: str = user_id

    async def list_tools(self) -> list[ChatCompletionToolParam]:
        """OpenAI 形式の tools を返す。access_token は schema から除く。

        Returns:
            LLM に渡す function tool のリスト。

        Raises:
            MCP の list_tools が失敗したときのプロトコル例外。
        """
        listed = await self._session.list_tools()
        tools: list[ChatCompletionToolParam] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": _hide_access_token(tool.input_schema),
                },
            }
            for tool in listed.tools
        ]
        if not any(t["function"]["name"] == "list_connected_spaces" for t in tools):
            tools.append(_CONNECTED_SPACES_TOOL)
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """指定された tool を呼び出し、結果を文字列で返す。

        tool 自身のエラーは例外にせず "tool error: ..." で返す。
        tool が見つからない等のプロトコル階層の失敗は例外として扱う。
        list_issues の access_token は store の値で上書きする。LLM 由来の値は捨てる。

        Args:
            name: 呼び出す tool 名。
            arguments: tool 引数。

        Returns:
            結果テキスト。失敗時は先頭が "tool error: "。

        Raises:
            MCP の call_tool がプロトコル階層で失敗したときの例外。
        """
        if name == "list_connected_spaces":
            return json.dumps(connected_spaces(self._store, self._user_id), ensure_ascii=False)

        if name == "list_issues":
            resolved = resolve_connection(self._store, self._user_id, arguments.get("space"))
            if isinstance(resolved, str):
                return resolved
            arguments = {
                "space": resolved.domain,
                "access_token": resolved.access_token,
                "status_id": arguments.get("status_id"),
            }
        else:
            arguments = {k: v for k, v in arguments.items() if k != "access_token"}

        result = await self._session.call_tool(name, arguments)

        if result.structured_content is not None:
            text = json.dumps(result.structured_content, ensure_ascii=False)
        else:
            blocks = [b.text for b in result.content if isinstance(b, TextContent)]
            text = "\n".join(blocks) if blocks else "(tool は内容を返さなかった)"

        if result.is_error:
            return f"tool error: {text}"
        return text
