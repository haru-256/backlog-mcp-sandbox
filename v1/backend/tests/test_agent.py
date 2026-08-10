from typing import Any

import pytest
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from pydantic import TypeAdapter

from chat.agent import ToolCallLimitExceeded, run_tool_loop


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeLLM:
    """台本どおりに応答し、渡された messages を記録する偽の LLM。"""

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
    """決まった結果を返し、呼ばれた tool を記録する偽の MCP。"""

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
    """tool 結果が次の LLM 入力に入り、最終回答まで messages が揃うことを確かめる。

    一度目の assistant が tool を要求し、指定引数で MCP が一度だけ呼ばれ、
    二度目の LLM 入力にその assistant 行と対応する tool 行（同一 tool_call_id）が
    並び、返り値が user → assistant → tool → assistant になることを検証する。
    """
    llm = FakeLLM(
        [
            tool_call("call_1", "get_issues", '{"statusId[]": [1]}'),
            {"role": "assistant", "content": "未完了の課題は 1 件です。"},
        ]
    )
    mcp = FakeMCP({"get_issues": '[{"id": 42, "summary": "資料を更新する"}]'})

    result = await run_tool_loop(
        [{"role": "user", "content": "未完了課題を教えて"}],
        llm,
        mcp,
        max_tool_calls=10,
    )

    # LLM が指定した引数で、tool がちょうど一度呼ばれた
    assert mcp.calls == [("get_issues", {"statusId[]": [1]})]

    # 二度目の LLM 呼び出しは、tool を要求した assistant 行と
    # 対応する tool 行の両方を見ている
    second = llm.seen[1]
    assistant = second[1]
    assert assistant["role"] == "assistant"
    tool_calls = assistant.get("tool_calls")
    assert tool_calls is not None
    assert next(iter(tool_calls))["id"] == "call_1"

    tool_row = second[2]
    assert tool_row["role"] == "tool"
    assert tool_row["tool_call_id"] == "call_1"

    # 返る messages は 4 行そろっている
    assert [row["role"] for row in result] == ["user", "assistant", "tool", "assistant"]
    assert (
        result[-1]["role"] == "assistant"
        and result[-1].get("content") == "未完了の課題は 1 件です。"
    )


@pytest.mark.anyio
async def test_every_tool_call_gets_its_own_tool_row() -> None:
    """1 つの assistant が複数 tool を要求したとき、全てに tool 行が付くことを確かめる。

    tool_calls が 2 件のとき、返る messages に tool_call_id が対応する tool 行が
    同じ順で 2 行含まれることを検証する。
    """
    both: ChatCompletionAssistantMessageParam = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_issues", "arguments": "{}"},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "get_projects", "arguments": "{}"},
            },
        ],
    }
    llm = FakeLLM([both, {"role": "assistant", "content": "まとめました。"}])
    mcp = FakeMCP({"get_issues": "[]", "get_projects": "[]"})

    result = await run_tool_loop(
        [{"role": "user", "content": "課題とプロジェクトを教えて"}],
        llm,
        mcp,
        max_tool_calls=10,
    )

    tool_rows = [row for row in result if row["role"] == "tool"]
    assert [row["tool_call_id"] for row in tool_rows] == ["call_1", "call_2"]


@pytest.mark.anyio
async def test_loop_stops_at_the_tool_call_limit() -> None:
    """tool 実行回数が max_tool_calls を超えると例外になり、超過分は実行されないことを確かめる。

    上限 3 のとき 3 回まで MCP を呼び、4 回目の実行前に ToolCallLimitExceeded を
    送出することを検証する。
    """
    llm = FakeLLM([tool_call("call_n", "get_issues", "{}")] * 10)
    mcp = FakeMCP({"get_issues": "[]"})

    with pytest.raises(ToolCallLimitExceeded):
        _ = await run_tool_loop(
            [{"role": "user", "content": "終わらない依頼"}],
            llm,
            mcp,
            max_tool_calls=3,
        )

    # 上限を超える 4 回目は実行されていない
    assert len(mcp.calls) == 3


@pytest.mark.anyio
async def test_history_with_tool_calls_does_not_mutate_input() -> None:
    """Pydantic 検証後の tool_calls（ValidatorIterator）でも loop でき、入力は不変であることを確かめる。

    2 回目の Chat リクエスト相当として、TypeAdapter で検証した履歴を渡し、
    deepcopy 相当の失敗を起こさず最終回答まで進むこと、および呼び出し元の
    messages の長さが変わらないことを検証する。
    """
    history = TypeAdapter(list[ChatCompletionMessageParam]).validate_python(
        [
            {"role": "user", "content": "未完了課題を教えて"},
            tool_call("call_1", "get_issues", "{}"),
            {"role": "tool", "tool_call_id": "call_1", "content": "[]"},
            {"role": "assistant", "content": "未完了は 0 件です。"},
            {"role": "user", "content": "プロジェクト一覧は？"},
        ]
    )
    original_len = len(history)
    assistant_row = history[1]
    assert assistant_row["role"] == "assistant"
    assert type(assistant_row.get("tool_calls")).__name__ == "ValidatorIterator"

    llm = FakeLLM([{"role": "assistant", "content": "プロジェクトは 1 件です。"}])
    mcp = FakeMCP({"get_projects": "[]"})

    result = await run_tool_loop(history, llm, mcp, max_tool_calls=10)

    assert len(history) == original_len
    assert result[-1].get("content") == "プロジェクトは 1 件です。"
    assert len(result) == original_len + 1
