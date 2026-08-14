import json
from typing import Any, Protocol, cast

import httpx
from loguru import logger
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
from .mcp_hub import open_mcp_hub
from .session_tokens import issue_session_auth
from .settings import Settings
from .store import MemoryStore

_messages_adapter: TypeAdapter[list[ChatCompletionMessageParam]] = TypeAdapter(
    list[ChatCompletionMessageParam]
)


def _plain_messages(
    messages: list[ChatCompletionMessageParam],
) -> list[ChatCompletionMessageParam]:
    """入力を書き換えず、ValidatorIterator などをプレーンな list/dict に落とす。

    Args:
        messages: 直近の会話履歴。OpenAI 形式の messages。

    Returns:
        JSON 往復したあとのプレーンな messages。呼び出し元の配列は変更しない。
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
        """LLM を 1 回呼び、assistant 行を返す。

        Args:
            messages: これまでの会話履歴。OpenAI 形式。
            tools: MCP から得た tool schema。OpenAI 形式。

        Returns:
            assistant の 1 行。tool_calls を含むことがある。

        Raises:
            実装依存。ネットワーク失敗や API エラーは実装側が送出する。
        """
        ...


class MCPCaller(Protocol):
    """OpenAI 形式の tools を返し、tool の結果を文字列で返す。"""

    async def list_tools(self) -> list[ChatCompletionToolParam]:
        """OpenAI 形式の tools を返す。

        Returns:
            LLM に渡す tool 定義のリスト。

        Raises:
            実装依存。MCP 接続失敗は実装側が送出する。
        """
        ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """指定された tool を呼び、結果を文字列で返す。

        Args:
            name: tool 名。
            arguments: tool 引数。

        Returns:
            tool 結果の文字列。tool 自身の失敗は "tool error: ..." になり得る。

        Raises:
            実装依存。tool が見つからない等のプロトコル失敗は実装側が送出する。
        """
        ...


async def run_agent(
    messages: list[ChatCompletionMessageParam],
    settings: Settings,
    user_id: str,
    org_id: str,
    store: MemoryStore,
) -> list[ChatCompletionMessageParam]:
    """LLM と MCP を使って、messages に対する応答を生成する。接続を開き、loop を一度回す。

    Args:
        messages: 直近の会話履歴。OpenAI 形式の messages。
        settings: エージェントの設定。
        user_id: Chat 上のユーザー ID。接続表のキー。
        org_id: Chat テナント ID。接続時に store へ書いた値。MCP には渡さない。
        store: 接続表（refresh token）。access token は `issue_session_auth` が chat 開始時に発行する。

    Returns:
        入力に LLM / tool 行を足した会話履歴。末尾は assistant。

    Raises:
        RuntimeError: 最後のメッセージが assistant でない場合。
        ToolCallLimitExceeded: tool 呼び出しが上限を超えた場合。
        UnsupportedToolCallTypeError: tool_call.type が function でない場合。
        json.JSONDecodeError: LLM が返した tool 引数が JSON でない場合。
    """
    llm = OpencodeGoLLM(settings)
    async with httpx.AsyncClient() as http:
        session_auth = await issue_session_auth(
            http,
            store,
            user_id,
            settings.backlog_client_id,
            settings.backlog_client_secret,
        )
    async with open_mcp_hub(settings, store, user_id, session_auth) as mcp:
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
    """LLM と MCP を使って、messages に対する応答を生成する。tool 呼び出しのループを回す。

    Args:
        messages: 直近の会話履歴。OpenAI 形式の messages。
        llm: LLM を呼び出すオブジェクト。
        mcp: MCP を呼び出すオブジェクト。
        max_tool_calls: tool 呼び出しの最大回数。

    Returns:
        入力に LLM / tool 行を足した会話履歴。OpenAI 形式。

    Raises:
        ToolCallLimitExceeded: tool 呼び出しの上限を超えた場合。
        UnsupportedToolCallTypeError: tool_call.type が function でない場合。
        json.JSONDecodeError: LLM が返した tool_call.arguments が JSON でない場合。
    """
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
