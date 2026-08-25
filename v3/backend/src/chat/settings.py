from typing import Literal, Self

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogFormat = Literal["human", "json"]


class Settings(BaseSettings):
    """環境変数から読む Chat Host の設定。"""

    model_config = SettingsConfigDict(extra="ignore")

    opencode_go_api_key: str
    opencode_go_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_go_model: str = "deepseek-v4-flash"
    mcp_server_url: str = "http://localhost:3333/mcp"
    host_public_url: str = "http://localhost:8003"
    frontend_public_url: str = "http://localhost:5173"
    backlog_client_id: str
    backlog_client_secret: str
    log_format: LogFormat = "human"
    max_tool_calls: int = 10

    @field_validator("log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, value: object) -> str:
        """LOG_FORMAT を小文字に揃える。

        Args:
            value: 環境変数の生の値。

        Returns:
            文字列なら lower() した値。それ以外はそのまま。
        """
        if isinstance(value, str):
            return value.lower()
        return value  # type: ignore[return-value]

    @field_validator(
        "host_public_url", "mcp_server_url", "frontend_public_url", mode="before"
    )
    @classmethod
    def strip_trailing_slash(cls, value: object) -> object:
        """URL 末尾のスラッシュを除く。

        Args:
            value: 環境変数の生の値。

        Returns:
            文字列なら rstrip("/") した値。それ以外はそのまま。
        """
        if isinstance(value, str):
            return value.rstrip("/")
        return value

    def oauth_redirect_uri(self) -> str:
        return f"{self.host_public_url}/backlog/callback"

    @classmethod
    def from_env(cls) -> Self:
        """環境変数から Settings を読む。

        Returns:
            必須フィールドを env から埋めた Settings。

        Raises:
            pydantic.ValidationError: 必須 env が無い、または値が不正な場合。
        """
        return cls()  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]
