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
    """loguru の record に request_id が無ければ contextvar から補う。

    Args:
        record: loguru が渡すログレコード。
    """
    record["extra"].setdefault("request_id", request_id_var.get())


def configure_logging(settings: Settings | None = None) -> LogFormat:
    """loguru を LOG_FORMAT に応じて初期化する。

    Args:
        settings: 使う設定。省略時は環境変数から読む。

    Returns:
        適用したフォーマット。`human` または `json`。

    Raises:
        ValueError: LOG_FORMAT が human / json でない場合。
        pydantic.ValidationError: settings 省略時に必須 env が無い場合。
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
