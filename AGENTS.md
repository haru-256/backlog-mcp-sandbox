# AGENTS.md

## Cursor Cloud specific instructions

This repo is a learning sandbox for wiring a Chat API to a Backlog MCP. The current,
active product is **`v3`** (a self-hosted Backlog MCP with an explicit, out-of-chat OAuth
connect flow). `v1` is an earlier learning stage and is only run via `docker compose`.
Unless told otherwise, work against `v3`.

### Toolchain

Tool versions are pinned in `mise.toml` (node, pnpm, python, uv, xh). The startup update
script installs `mise`, runs `mise install`, and refreshes dependencies. `mise` is **not**
auto-activated in non-interactive shells, so prefix commands with `mise exec --`
(e.g. `mise exec -- uv run pytest .`) or activate it for your shell first
(`eval "$(mise activate bash)"`).

### v3 services

Three services make up the v3 product. Standard lint/test/lock/install targets live in
`make/python.mk` (Python) and `v3/frontend/package.json` (frontend); run them from each
service directory.

| Service | Dir | Dev run command | Port |
| --- | --- | --- | --- |
| MCP (custom Backlog MCP) | `v3/mcp` | `mise exec -- uv run backlog-mcp` | 3333 |
| Chat API (host) | `v3/backend` | `mise exec -- uv run uvicorn chat.api:app --host 0.0.0.0 --port 8003 --reload` | 8003 |
| Frontend (Vite/React) | `v3/frontend` | `mise exec -- pnpm dev --host` | 5173 |

Lint/test per Python service: `mise exec -- uv run ruff check .`, `mise exec -- uv run mypy .`,
`mise exec -- uv run pytest .` (also `make lint` / `make test`). Frontend: `pnpm lint`
(oxlint) and `pnpm build` (tsc + vite build); there are no frontend unit tests.

`docker compose up` from `v3/` is the container path, but Docker is not installed in this
environment — run the services directly with the commands above for development.

### Non-obvious run notes / gotchas

- **Shared JWT secret.** The Chat API and MCP authenticate to each other with a shared
  `MCP_JWT_SECRET`. It must be **identical** for both processes or the MCP session and the
  `/connect` state token will fail verification. Any value works locally.
- **Avoid `!` in shell-exported secrets.** The compose default secret ends in `!!`, which an
  interactive `bash` expands via history expansion. Use a secret without `!` (or `set +H`)
  when exporting it in a shell/tmux session.
- **Backend needs `OPENCODE_GO_API_KEY` just to boot.** `chat/settings.py` marks it required,
  so the app fails to import without it — even though the key is only used per `/chat`
  request. Set any placeholder to boot and serve `/health` and `/backlog/connect`; a **real**
  key is required for actual chat completions (LLM provider is `opencode.ai`).
- **Local URLs must line up.** Run the backend on port `8003` so its default
  `host_public_url` (`http://localhost:8003`) matches; set `MCP_SERVER_URL=http://localhost:3333/mcp`
  for the backend (the compose default `http://mcp:3333/mcp` only resolves inside Docker).
  The frontend reads the backend URL from `v3/frontend/.env.development`
  (`VITE_API_BASE_URL=http://localhost:8003`).
- **Actually listing Backlog issues** requires a real Backlog space plus an OAuth app
  (client id/secret) registered for that space; the connect form collects these and the MCP
  performs the real OAuth code exchange. Without them you can still exercise everything up to
  and including rendering the `/connect` form.
- The MCP store is in-memory (`store.py`), so connections reset when the MCP process restarts.

### Required secrets for full end-to-end

- `OPENCODE_GO_API_KEY` — LLM key for `/chat` completions.
- A Backlog space + OAuth app client id/secret — to complete the connect flow and list issues.
