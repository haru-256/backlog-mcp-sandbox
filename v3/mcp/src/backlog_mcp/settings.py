from typing import Literal, Self

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogFormat = Literal["human", "json"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    mcp_jwt_secret: str
    mcp_public_url: str = "http://localhost:3333"
    host_public_url: str = "http://localhost:8003"
    frontend_public_url: str = "http://localhost:5173"
    host: str = "0.0.0.0"
    port: int = 3333
    allowed_hosts: str = "mcp,mcp:3333,localhost,127.0.0.1,localhost:3333,127.0.0.1:3333"
    allowed_origins: str = "http://localhost:*,http://127.0.0.1:*"
    issue_limit: int = 20

    @field_validator("mcp_public_url", "host_public_url", "frontend_public_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, value: object) -> object:
        if isinstance(value, str):
            return value.rstrip("/")
        return value

    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @classmethod
    def from_env(cls) -> Self:
        return cls()  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]
