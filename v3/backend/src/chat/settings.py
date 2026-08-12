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
    mcp_public_url: str = "http://localhost:3333"
    host_public_url: str = "http://localhost:8003"
    mcp_jwt_secret: str
    log_format: LogFormat = "human"
    max_tool_calls: int = 10
    connect_token_ttl_seconds: int = 600
    mcp_token_ttl_seconds: int = 300

    @field_validator("log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, value: object) -> str:
        if isinstance(value, str):
            return value.lower()
        return value  # type: ignore[return-value]

    @field_validator("mcp_public_url", "host_public_url", "mcp_server_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, value: object) -> object:
        if isinstance(value, str):
            return value.rstrip("/")
        return value

    @classmethod
    def from_env(cls) -> Self:
        return cls()  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]
