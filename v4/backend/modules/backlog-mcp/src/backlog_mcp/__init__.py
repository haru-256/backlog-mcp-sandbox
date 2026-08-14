"""自作 Backlog MCP Server。Host が同一プロセスで Client(server) する。

読む順:

1. `server.py` — `create_server` が MCPServer を返すこと
2. `tools.py` — 渡された space / access_token で課題を返す
3. `backlog.py` — Backlog REST。token は引数で受け取る
"""

from .server import create_server

__all__ = ["create_server"]
