import asyncio

from loguru import logger
from openai.types.chat import ChatCompletionMessageParam

from .agent import run_agent
from .logging_config import configure_logging
from .settings import Settings


async def _run(prompt: str) -> None:
    settings = Settings.from_env()
    configure_logging(settings)
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
    result = await run_agent(messages, settings)
    logger.info(f"content: {result[-1].get('content')}")


def run(prompt: str) -> None:
    asyncio.run(_run(prompt))
