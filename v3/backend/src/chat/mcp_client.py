import json
from typing import Any

from mcp import ClientSession
from mcp.types import TextContent
from openai.types.chat import ChatCompletionToolParam


class BacklogMCP:
    """MCP サーバーに接続するためのクライアント。"""

    def __init__(self, session: ClientSession) -> None:
        """セッションを保持する。

        Args:
            session: MCP サーバーとの通信を行うセッション。
        """
        self._session: ClientSession = session

    async def list_tools(self) -> list[ChatCompletionToolParam]:
        """OpenAI 形式の tools を返す。

        Returns:
            LLM に渡す function tool のリスト。

        Raises:
            MCP の list_tools が失敗したときのプロトコル例外。
        """
        listed = await self._session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in listed.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """指定された tool を呼び出し、結果を文字列で返す。

        tool 自身のエラーは例外にせず "tool error: ..." で返す。
        tool が見つからない等のプロトコル階層の失敗は例外として扱う。

        Args:
            name: 呼び出す tool 名。
            arguments: tool 引数。

        Returns:
            結果テキスト。失敗時は先頭が "tool error: "。

        Raises:
            MCP の call_tool がプロトコル階層で失敗したときの例外。
        """
        result = await self._session.call_tool(name, arguments)

        if result.structured_content is not None:
            text = json.dumps(result.structured_content, ensure_ascii=False)
        else:
            blocks = [b.text for b in result.content if isinstance(b, TextContent)]
            text = "\n".join(blocks) if blocks else "(tool は内容を返さなかった)"

        if result.is_error:
            return f"tool error: {text}"
        return text
