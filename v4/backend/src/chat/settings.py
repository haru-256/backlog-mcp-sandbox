from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogFormat = Literal["human", "json"]

_SERVER_ID = r"^[a-z][a-z0-9]{0,31}$"


class InProcessMcp(BaseModel):
    """同一プロセスの MCP。id は Host の factory 表のキー。"""

    id: str = Field(pattern=_SERVER_ID)
    kind: Literal["inprocess"] = "inprocess"


class HttpMcp(BaseModel):
    """外部 MCP。Streamable HTTP の URL。"""

    id: str = Field(pattern=_SERVER_ID)
    kind: Literal["http"]
    url: str


McpSpec = Annotated[InProcessMcp | HttpMcp, Field(discriminator="kind")]


class Settings(BaseSettings):
    """環境変数から読む Chat Host の設定。"""

    model_config = SettingsConfigDict(extra="ignore")

    opencode_go_api_key: str
    opencode_go_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_go_model: str = "deepseek-v4-flash"
    host_public_url: str = "http://localhost:8004"
    frontend_public_url: str = "http://localhost:5174"
    backlog_client_id: str
    backlog_client_secret: str
    log_format: LogFormat = "human"
    max_tool_calls: int = 10
    mcp_servers: list[McpSpec] = Field(default_factory=lambda: [InProcessMcp(id="backlog")])

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

    @field_validator("host_public_url", "frontend_public_url", mode="before")
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

    @model_validator(mode="after")
    def mcp_ids_are_unique(self) -> Self:
        """mcp_servers の id が重複していないことを確かめる。

        Returns:
            重複が無ければ self。

        Raises:
            ValueError: id が重複している場合。
        """
        ids = [spec.id for spec in self.mcp_servers]
        if len(ids) != len(set(ids)):
            raise ValueError("mcp_servers id must be unique")
        return self

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
