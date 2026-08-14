"""環境変数から読む MCP の設定。"""

from typing import Literal, Self

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogFormat = Literal["human", "json"]


class Settings(BaseSettings):
    """Compose / シェルの環境変数。

    Attributes:
        mcp_jwt_secret: Host と同じ HMAC 秘密鍵。
        mcp_public_url: ブラウザから見た MCP の origin。AuthSettings の resource_server_url。
        host_public_url: Host の公開 URL。JWT の iss。
        host: bind 先。コンテナでは 0.0.0.0。
        port: 待ち受けポート。既定 3333。
        issue_limit: list_issues の件数上限。
    """

    model_config = SettingsConfigDict(extra="ignore")

    mcp_jwt_secret: str
    mcp_public_url: str = "http://localhost:3333"
    host_public_url: str = "http://localhost:8003"
    host: str = "0.0.0.0"
    port: int = 3333
    issue_limit: int = 20

    @field_validator("mcp_public_url", "host_public_url", mode="before")
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

    @classmethod
    def from_env(cls) -> Self:
        """環境変数から Settings を読む。

        Returns:
            必須フィールドを env から埋めた Settings。

        Raises:
            pydantic.ValidationError: 必須 env が無い、または値が不正な場合。
        """
        return cls()  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]
