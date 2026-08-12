import asyncio

from loguru import logger
from openai.types.chat import ChatCompletionMessageParam

from .agent import run_agent
from .logging_config import configure_logging
from .settings import Settings


async def _run(prompt: str, user_id: str, org_id: str) -> None:
    settings = Settings.from_env()
    configure_logging(settings)
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
    result = await run_agent(messages, settings, user_id, org_id)
    logger.info(f"content: {result[-1].get('content')}")


def run(prompt: str, user_id: str = "demo-user", org_id: str = "demo-org") -> None:
    asyncio.run(_run(prompt, user_id, org_id))
