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
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
        )
        return _to_row(completion.choices[0].message)


def _to_row(message: ChatCompletionMessage) -> ChatCompletionAssistantMessageParam:
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
