from typing import Literal, Self

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogFormat = Literal["human", "json"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    opencode_go_api_key: str
    opencode_go_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_go_model: str = "deepseek-v4-flash"
    mcp_server_url: str = "http://localhost:3333/mcp"
    log_format: LogFormat = "human"
    max_tool_calls: int = 10

    @field_validator("log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, value: object) -> str:
        if isinstance(value, str):
            return value.lower()
        return value  # type: ignore[return-value]

    @classmethod
    def from_env(cls) -> Self:
        """環境変数から Settings を読む。

        pydantic-settings は実行時に必須フィールドを env から埋めるが、
        型チェッカーはコンストラクタ引数として要求する。読み込み口をここに寄せる。
        """
        return cls()  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]
