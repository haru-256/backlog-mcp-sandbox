from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from chat.settings import Settings


class OpencodeGoLLM:
    """OpenAI 互換の Chat Completions を、loop が使う 1 つの操作だけに絞る。"""

    def __init__(self, settings: Settings) -> None:
        """OpenCode Go 向けのクライアントを組み立てる。

        Args:
            settings: API キー、base_url、モデル名。

        Raises:
            なし。
        """
        self._client: AsyncOpenAI = AsyncOpenAI(
            api_key=settings.opencode_go_api_key,
            base_url=settings.opencode_go_base_url,
        )
        self._model: str = settings.opencode_go_model

    async def complete(
        self,
        messages: list[ChatCompletionMessageParam],
        tools: list[ChatCompletionToolParam],
    ) -> ChatCompletionAssistantMessageParam:
        """messages と tools を渡すと、assistant 行を 1 つ返す。

        Args:
            messages: これまでの会話履歴。OpenAI 形式。
            tools: MCP から得た tool schema。

        Returns:
            次の loop に渡せる assistant 行。不要な None フィールドは落とす。

        Raises:
            openai.APIError: LLM API が失敗した場合。
        """
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
        )
        return _to_row(completion.choices[0].message)


def _to_row(message: ChatCompletionMessage) -> ChatCompletionAssistantMessageParam:
    """SDK のモデルを、そのまま次の呼び出しへ渡せる dict にする。

    Args:
        message: Chat Completions の assistant メッセージ。

    Returns:
        role / content / tool_calls だけを持つ assistant 行。

    Raises:
        なし。
    """
    row: ChatCompletionAssistantMessageParam = {
        "role": "assistant",
        "content": message.content,
    }
    if message.tool_calls:
        tool_calls: list[ChatCompletionMessageFunctionToolCallParam] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in message.tool_calls
            if isinstance(call, ChatCompletionMessageFunctionToolCall)
        ]
        if tool_calls:
            row["tool_calls"] = tool_calls
    return row
