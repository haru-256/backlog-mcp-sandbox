import asyncio

from loguru import logger
from openai.types.chat import ChatCompletionMessageParam

from .agent import run_agent
from .logging_config import configure_logging
from .settings import Settings


async def _run(prompt: str, user_id: str, org_id: str) -> None:
    """1 件のプロンプトを agent に渡し、最終回答をログする。

    Args:
        prompt: ユーザー発話。
        user_id: Chat 上のユーザー ID。
        org_id: Chat テナント ID。

    Raises:
        RuntimeError: 最終行が assistant でない場合。
        ToolCallLimitExceeded: tool 呼び出しが上限を超えた場合。
        pydantic.ValidationError: 必須 env が無い場合。
    """
    settings = Settings.from_env()
    configure_logging(settings)
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
    result = await run_agent(messages, settings, user_id, org_id)
    logger.info(f"content: {result[-1].get('content')}")


def run(prompt: str, user_id: str = "demo-user", org_id: str = "demo-org") -> None:
    """CLI 入口。1 件のプロンプトを同期的に処理する。

    Args:
        prompt: ユーザー発話。
        user_id: Chat 上のユーザー ID。省略時は demo-user。
        org_id: Chat テナント ID。省略時は demo-org。

    Raises:
        RuntimeError: 最終行が assistant でない場合。
        ToolCallLimitExceeded: tool 呼び出しが上限を超えた場合。
        pydantic.ValidationError: 必須 env が無い場合。
    """
    asyncio.run(_run(prompt, user_id, org_id))
