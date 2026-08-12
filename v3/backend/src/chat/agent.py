import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol, cast

from loguru import logger
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion_tool_message_param import (
    ChatCompletionToolMessageParam,
)
from pydantic import TypeAdapter

from .jwt_tokens import sign_token
from .llm import OpencodeGoLLM
from .mcp_client import BacklogMCP
from .settings import Settings

_messages_adapter: TypeAdapter[list[ChatCompletionMessageParam]] = TypeAdapter(
    list[ChatCompletionMessageParam]
)


def _plain_messages(
    messages: list[ChatCompletionMessageParam],
) -> list[ChatCompletionMessageParam]:
    return cast(
        list[ChatCompletionMessageParam],
        json.loads(_messages_adapter.dump_json(messages)),
    )


class LLMCaller(Protocol):
    async def complete(
        self,
        messages: list[ChatCompletionMessageParam],
        tools: list[ChatCompletionToolParam],
    ) -> ChatCompletionAssistantMessageParam: ...


class MCPCaller(Protocol):
    async def list_tools(self) -> list[ChatCompletionToolParam]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str: ...


def mcp_bearer_token(settings: Settings, user_id: str, org_id: str) -> str:
    return sign_token(
        secret=settings.mcp_jwt_secret,
        typ="mcp",
        user_id=user_id,
        org_id=org_id,
        issuer=settings.host_public_url,
        ttl_seconds=settings.mcp_token_ttl_seconds,
        audience=settings.mcp_public_url,
    )


@asynccontextmanager
async def open_mcp_session(
    settings: Settings, user_id: str, org_id: str
) -> AsyncIterator[ClientSession]:
    token = mcp_bearer_token(settings, user_id, org_id)
    async with (
        create_mcp_http_client(headers={"Authorization": f"Bearer {token}"}) as http_client,
        streamable_http_client(settings.mcp_server_url, http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        yield session


async def run_agent(
    messages: list[ChatCompletionMessageParam],
    settings: Settings,
    user_id: str,
    org_id: str,
) -> list[ChatCompletionMessageParam]:
    llm = OpencodeGoLLM(settings)
    async with open_mcp_session(settings, user_id, org_id) as session:
        logger.debug(f"initialize mcp session: {settings.mcp_server_url}")
        await session.initialize()
        mcp = BacklogMCP(session)
        result = await run_tool_loop(messages, llm, mcp, settings.max_tool_calls)
        if result[-1].get("role") != "assistant":
            raise RuntimeError("The last message is not from the assistant.")
        return result


class ToolCallLimitExceeded(RuntimeError):
    """tool の実行回数が上限に達した。"""


class UnsupportedToolCallTypeError(ValueError):
    """LLM が返した tool_call.type に未対応。"""


async def run_tool_loop(
    messages: list[ChatCompletionMessageParam],
    llm: LLMCaller,
    mcp: MCPCaller,
    max_tool_calls: int,
) -> list[ChatCompletionMessageParam]:
    messages = _plain_messages(messages)

    tools = await mcp.list_tools()
    logger.debug(f"tools num: {len(tools)}")
    tool_call_count = 0

    while True:
        assistant = await llm.complete(messages, tools)
        messages.append(assistant)
        tool_calls = assistant.get("tool_calls") or []

        if not tool_calls:
            return messages

        for tool_call in tool_calls:
            tool_call_count += 1
            if tool_call_count > max_tool_calls:
                raise ToolCallLimitExceeded(f"tool 呼び出しの上限 {max_tool_calls} を超えました。")

            if tool_call["type"] != "function":
                raise UnsupportedToolCallTypeError(
                    f"tool_call.type が function ではありません: {tool_call}"
                )

            tool_call_id = tool_call["id"]
            name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])
            result = await mcp.call_tool(name, arguments)
            message: ChatCompletionToolMessageParam = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
            messages.append(message)
