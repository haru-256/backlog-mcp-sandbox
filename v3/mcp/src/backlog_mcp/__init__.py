"""自作 Backlog MCP Server。

このパッケージは MCP の **Server** である。Chat の Host は `v3/backend`、
検証 UI は `v3/frontend`。LLM はここを直接呼ばない。

読む順:

1. `server.py` — 入口が `/mcp`（tool）と `/health` であること
2. `tools.py` — 渡された space / access_token で課題を返す
3. `backlog.py` — Backlog REST。token は引数で受け取る
"""

from .server import run


def main() -> None:
    """環境変数から設定を読み、Streamable HTTP で起動する。"""
    run()
