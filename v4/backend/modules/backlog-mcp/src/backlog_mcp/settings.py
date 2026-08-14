"""環境変数から読む MCP の設定。待ち受けは持たない。"""

from typing import Self

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Host に載ったときの件数上限。

    Attributes:
        issue_limit: list_issues の件数上限。
    """

    model_config = SettingsConfigDict(extra="ignore")

    issue_limit: int = 20

    @classmethod
    def from_env(cls) -> Self:
        """環境変数から Settings を読む。

        Returns:
            必須フィールドを env から埋めた Settings。
        """
        return cls()
