"""環境変数から読む MCP の設定。"""

from typing import Self

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Compose / シェルの環境変数。

    Attributes:
        host: bind 先。コンテナでは 0.0.0.0。
        port: 待ち受けポート。既定 3333。
        issue_limit: list_issues の件数上限。
    """

    model_config = SettingsConfigDict(extra="ignore")

    host: str = "0.0.0.0"
    port: int = 3333
    issue_limit: int = 20

    @classmethod
    def from_env(cls) -> Self:
        """環境変数から Settings を読む。

        Returns:
            必須フィールドを env から埋めた Settings。

        Raises:
            pydantic.ValidationError: 必須 env が無い、または値が不正な場合。
        """
        return cls()
