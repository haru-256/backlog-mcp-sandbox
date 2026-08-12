import json
from typing import Any

from mcp import ClientSession
from mcp.types import TextContent
from openai.types.chat import ChatCompletionToolParam


class BacklogMCP:
    def __init__(self, session: ClientSession) -> None:
        self._session: ClientSession = session

    async def list_tools(self) -> list[ChatCompletionToolParam]:
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
        result = await self._session.call_tool(name, arguments)

        if result.structured_content is not None:
            text = json.dumps(result.structured_content, ensure_ascii=False)
        else:
            blocks = [b.text for b in result.content if isinstance(b, TextContent)]
            text = "\n".join(blocks) if blocks else "(tool は内容を返さなかった)"

        if result.is_error:
            return f"tool error: {text}"
        return text
