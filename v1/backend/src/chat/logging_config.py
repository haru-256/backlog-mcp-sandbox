import sys
from typing import Any, Literal

from loguru import logger

from .request_context import request_id_var
from .settings import Settings

LogFormat = Literal["human", "json"]

HUMAN_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[request_id]}</cyan> | "
    "<level>{message}</level>\n"
)


def _patch_record(record: Any) -> None:
    record["extra"].setdefault("request_id", request_id_var.get())


def configure_logging(settings: Settings | None = None) -> LogFormat:
    """loguru を LOG_FORMAT に応じて初期化する。

    human: ローカル開発向けの可読ログ
    json: request_id など extra を含む structured ログ
    """
    resolved = settings or Settings.from_env()
    log_format = resolved.log_format.lower()

    logger.remove()
    logger.configure(patcher=_patch_record)

    if log_format == "json":
        logger.add(sys.stderr, serialize=True)
    elif log_format == "human":
        logger.add(sys.stderr, format=HUMAN_FORMAT)
    else:
        msg = f"LOG_FORMAT must be 'human' or 'json', got {resolved.log_format!r}"
        raise ValueError(msg)

    return log_format  # type: ignore[return-value]
