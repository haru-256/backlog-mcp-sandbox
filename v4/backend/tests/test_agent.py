from typing import Any

import pytest
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from chat.agent import ToolCallLimitExceeded, run_tool_loop


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeLLM:
    def __init__(self, script: list[ChatCompletionAssistantMessageParam]) -> None:
        self.script: list[ChatCompletionAssistantMessageParam] = script
        self.seen: list[list[ChatCompletionMessageParam]] = []

    async def complete(
        self,
        messages: list[ChatCompletionMessageParam],
        tools: list[ChatCompletionToolParam],
    ) -> ChatCompletionAssistantMessageParam:
        del tools
        self.seen.append(list(messages))
        return self.script[len(self.seen) - 1]


class FakeMCP:
    def __init__(self, results: dict[str, str]) -> None:
        self.results: dict[str, str] = results
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[ChatCompletionToolParam]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": "",
                    "parameters": {"type": "object"},
                },
            }
            for name in self.results
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return self.results[name]


def tool_call(call_id: str, name: str, arguments: str) -> ChatCompletionAssistantMessageParam:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


@pytest.mark.anyio
async def test_tool_result_is_fed_back_to_the_llm() -> None:
    llm = FakeLLM(
        [
            tool_call("call_1", "list_issues", "{}"),
            {"role": "assistant", "content": "未完了の課題は 1 件です。"},
        ]
    )
    mcp = FakeMCP({"list_issues": '[{"id": 42, "summary": "資料を更新する"}]'})

    result = await run_tool_loop(
        [{"role": "user", "content": "未完了課題を教えて"}],
        llm,
        mcp,
        max_tool_calls=10,
    )

    assert mcp.calls == [("list_issues", {})]
    assert [row["role"] for row in result] == ["user", "assistant", "tool", "assistant"]


@pytest.mark.anyio
async def test_loop_stops_at_the_tool_call_limit() -> None:
    llm = FakeLLM([tool_call("call_n", "list_issues", "{}")] * 10)
    mcp = FakeMCP({"list_issues": "[]"})

    with pytest.raises(ToolCallLimitExceeded):
        _ = await run_tool_loop(
            [{"role": "user", "content": "終わらない依頼"}],
            llm,
            mcp,
            max_tool_calls=3,
        )

    assert len(mcp.calls) == 3
