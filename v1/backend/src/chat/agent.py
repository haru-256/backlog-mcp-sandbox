import json
from typing import Any, Protocol, cast

from loguru import logger
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion_tool_message_param import (
    ChatCompletionToolMessageParam,
)
from pydantic import TypeAdapter

from .llm import OpencodeGoLLM
from .mcp_client import BacklogMCP
from .settings import Settings

_messages_adapter: TypeAdapter[list[ChatCompletionMessageParam]] = TypeAdapter(
    list[ChatCompletionMessageParam]
)


def _plain_messages(
    messages: list[ChatCompletionMessageParam],
) -> list[ChatCompletionMessageParam]:
    """入力を書き換えず、ValidatorIterator などをプレーンな list/dict に落とす。

    Pydantic が TypedDict の Iterable フィールドを ValidatorIterator のまま残すことがあり、
    deepcopy はそれに失敗する。JSON 往復なら呼び出し元の messages は触らない。
    """
    return cast(
        list[ChatCompletionMessageParam],
        json.loads(_messages_adapter.dump_json(messages)),
    )


class LLMCaller(Protocol):
    """messages と tools を渡すと、assistant 行を 1 つ返す。"""

    async def complete(
        self,
        messages: list[ChatCompletionMessageParam],
        tools: list[ChatCompletionToolParam],
    ) -> ChatCompletionAssistantMessageParam:
        """messages と tools を渡すと、assistant 行を 1 つ返す。"""
        ...


class MCPCaller(Protocol):
    """OpenAI 形式の tools を返し、tool の結果を文字列で返す。"""

    async def list_tools(self) -> list[ChatCompletionToolParam]:
        """OpenAI 形式の tools を返す。"""
        ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str: ...


async def run_agent(
    messages: list[ChatCompletionMessageParam], settings: Settings
) -> list[ChatCompletionMessageParam]:
    """LLM と MCP を使って、messages に対する応答を生成する。接続を開き、loop を一度回す。

    Args:
        messages: 直近の会話履歴。OpenAI 形式の messages。
        settings: エージェントの設定。

    Raises:
        RuntimeError: 最後のメッセージが assistant でない場合
    """
    llm = OpencodeGoLLM(settings)
    async with (
        streamable_http_client(settings.mcp_server_url) as (read, write),
        ClientSession(read, write) as session,
    ):
        logger.debug(f"initialize mcp session: {settings.mcp_server_url}")
        await session.initialize()
        mcp = BacklogMCP(session)
        message = await run_tool_loop(messages, llm, mcp, settings.max_tool_calls)
        if message[-1].get("role") != "assistant":
            raise RuntimeError("The last message is not from the assistant.")
        return message


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
    """LLM と MCP を使って、messages に対する応答を生成する。tool 呼び出しのループを回す。
    不変条件:
        - LLM が返した assistant 行は、tool を実行する前に messages へ追加する
        - tool 行の tool_call_id は、対応する assistant.tool_calls[i].id と一致する
        - assistant が複数の tool を要求したら、その全てに tool 行を返す
        - tool_calls を持たない assistant が出たら、そこで終える
        - 実行しようとした tool が通算 max_tool_calls を超えるなら、
          実行せずに ToolCallLimitExceeded を送出する

    Args:
        messages: 直近の会話履歴。OpenAI 形式の messages。
        llm: LLM を呼び出すためのオブジェクト。
        mcp: MCP を呼び出すためのオブジェクト。
        max_tool_calls: tool 呼び出しの最大回数。

    Returns:
        messages に追加された、LLM と MCP の応答を含む会話履歴。OpenAI 形式の messages。

    Raises:
        ToolCallLimitExceeded: tool 呼び出しの上限を超えた場合
        JSONDecodeError: LLM が返した tool_call.arguments が JSON でない場合
        ValueError: LLM が返した tool_call.type が function でない場合
    """

    # 呼び出し元の配列は触らない。作業用のプレーンなコピーだけを育てる
    messages = _plain_messages(messages)

    tools = await mcp.list_tools()
    logger.debug(f"tools num: {len(tools)}")
    tool_call_count = 0

    logger.debug(f"run_tool_loop: messages: {messages}, max_tool_calls: {max_tool_calls}")
    while True:
        assistant = await llm.complete(messages, tools)
        messages.append(assistant)
        tool_calls = assistant.get("tool_calls") or []

        if not tool_calls:
            return messages

        logger.debug(f"tool_calls: {tool_calls}")

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
            # LLM が返す tool_call.arguments は JSON 文字列なので、dict に変換する
            arguments = json.loads(tool_call["function"]["arguments"])
            logger.debug(f"tool_call: id: {tool_call_id}, name: {name}, arguments: {arguments}")

            result = await mcp.call_tool(name, arguments)
            message: ChatCompletionToolMessageParam = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
            logger.debug(f"tool_call result: {message}")
            messages.append(message)
