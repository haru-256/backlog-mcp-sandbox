# Backlog MCP Chat API 設計

日付: 2026-08-08  
リポジトリ: `backlog-mcp-sandbox`  
状態: ブレインストーミング合意済み。実装プラン未作成。

## 1. 目的

このリポジトリの第一目的は **学習** である。  
公式 Backlog MCP と LLM を自前の MCP Host でつなぎ、tool loop・セッション・観測といった本番寄りの責務を、自分たちのコードとして理解するための教材兼サンドボックスとする。

接続確認だけなら Claude Desktop や Cursor に公式 MCP を足せば足りる。  
それでも自前 Chat API を置く理由は、Host の責任範囲（LLM 呼び出しと tool 実行の境界、HTTP 常駐 MCP、永続化、ログ、制限）を隠蔽せずに追える形にするためである。

実現する成果物は **Chat API** である。  
本番向けのフロントエンド製品は持たない。検証用 UI のみ各版に置く。  
ユーザー（または検証用 UI）が自然言語で Backlog 操作を依頼し、サーバー側の MCP Host が LLM と公式 Backlog MCP を仲介して回答を返す。

「動くデモ」で終わらせず、版を分けて学ぶ。  
**v1** でステートレスな Host の中核（LLM ↔ tool loop ↔ MCP）を掴み、**v2** でセッション永続化と耐障害・観測を足した最終形にする。  
v1 と v2 のコードは共有しない。差分を追いやすくするためである。

典型例は次である。

> Backlog の未完了課題を教えて

裏側の連鎖は次のとおりである。

1. Chat API（MCP Host）が発話を受け取る
2. Host が OpenCode Go（LLM）へ messages と tool schemas を渡す
3. LLM が tool call を返す
4. Host が MCP Client 経由で Backlog MCP の `tools/call` を実行する
5. Backlog MCP が Backlog API を呼び、結果を返す
6. Host が tool result を LLM に戻す
7. LLM が最終回答を返し、Host が呼び出し元へ返す

「本番を意識する」の意味は次に限定する。

- 公式 Backlog MCP を Compose 上の常駐サービスとして動かす
- Host が MCP を子プロセス（stdio）で都度起動しない
- MCP は HTTP（Streamable HTTP）でつなぐ
- 会話は最終的にサーバー側で保持し、PostgreSQL に永続化する（v2）
- timeout、tool 呼び出し回数上限、ヘルスチェック、構造化可能なログ、書き込み監査、アクセスログを備える（詳細は版ごとに後述）

次は範囲外である。

- 高度な cache、Kubernetes、サービスメッシュ、マルチリージョン
- 本格マルチテナント / RBAC / OAuth 等の認証実装（差し込み点のみ）
- 人間承認 UI（human-in-the-loop）
- Backlog MCP の自作
- LangChain / LangGraph 等へのエージェントループ委譲

## 2. 利用者と成果物の位置づけ

API 契約は、学習用スクリプトと将来の自前 Backend の両方を想定する。  
検証用に React フロントを各版へ置くが、本番 FE ではない。

学習ロードマップは次の二段とする。**v3 は作らない。**  
認証実装は将来課題とし、v2 の成功条件には含めない。

| 版 | 位置づけ | 要点 |
|---|---|---|
| **v1** | 教材 | ステートレス Host。同期 JSON のみ。DB なし。loop の理解が目的 |
| **v2** | 最終成果物 | サーバー側セッション、PostgreSQL、SSE のみ、監査、耐障害契約、health、ログ |

`v1` と `v2` はコードを共有しない。完全に独立したアプリケーションとする。

v1 の **学習順** は次の三段とする（成果物の最終形は FastAPI + 検証 FE）。

1. CLI / スクリプトで LLM ↔ MCP の手動 loop だけを動かす
2. 同じ loop を FastAPI の `POST /chat` で包む（アクセスログ / loguru）
3. `v1/frontend` で同期確認する

loop 本体は `v1/backend` 内のモジュールとして置き、CLI と API の両方から呼ぶ。  
v1 と v2 のあいだでは共有しない。

## 3. リポジトリ構成

```text
backlog-mcp-sandbox/
├── .envrc                # direnv。秘密情報はここに置く（git に含めない）
├── mise.toml
├── v1/
│   ├── compose.yaml      # backlog-mcp + chat-v1（この版専用）
│   ├── backend/          # 手動 loop + CLI 入口 + FastAPI（同期 Chat）
│   └── frontend/         # pnpm + React（検証用）
├── v2/
│   ├── compose.yaml      # backlog-mcp + postgres + chat-v2（この版専用）
│   ├── backend/          # FastAPI（SSE Chat + セッション）
│   └── frontend/         # pnpm + React（検証用、v1 と非共有）
└── docs/
    ├── guide/            # 学習ガイド（本資料の How）
    │   ├── assets/       # 3 冊で共有する CSS / JS
    │   ├── index.html    # 共通の地図（版に依らない原理）
    │   ├── v1.html       # v1 の手順
    │   └── v2.html       # v2 の手順（v1 を前提とする）
    ├── handsoff/
    └── superpowers/
        └── specs/
```

`v1` と `v2` は完全に独立したアプリケーションとする。  
リポジトリ直下の共通 `compose.yaml` は置かない。各版が自分の Compose・MCP・Host を持つ。

## 4. 技術スタック

| 領域 | 選択 |
|---|---|
| 言語（API） | Python 3.12+ |
| パッケージ（API） | uv + `pyproject.toml`（版ごとに独立） |
| Web | FastAPI + Uvicorn |
| 設定 | pydantic-settings |
| LLM | openai SDK（OpenCode Go 向けに `base_url` 差し替え） |
| モデル | `deepseek-v4-flash`（デフォルト） |
| MCP Client | 公式 `mcp` SDK（Streamable HTTP） |
| MCP Server | 公式 `nulab/backlog-mcp-server`（自作しない） |
| DB | PostgreSQL 16（**v2 のみ**） |
| ORM | SQLAlchemy 2.0（async + asyncpg） |
| マイグレーション | Alembic |
| ログ | loguru + アクセスログ用 middleware |
| フロント | pnpm + React + axios + SWR |
| 起動（API/MCP/DB） | 各版の `compose.yaml`（`v1/compose.yaml` / `v2/compose.yaml`） |
| 起動（FE） | ローカル `pnpm dev`（Compose に載せない） |

LLM エンドポイントのデフォルトは `https://opencode.ai/zen/go/v1` とする。  
Chat Completions は `/chat/completions` を用いる。

## 5. アーキテクチャ

```text
User / 検証 FE
    → v1/backend または v2/backend（MCP Host）
         ├─ Messages + Tool schemas → OpenCode Go (LLM)
         │                              └─ Tool Call → Host
         └─ MCP Client → tools/call → Backlog MCP → Backlog API
                              ↑              │
                              └─ Tool Result ┘
```

Host のループは手動の while である。

1. MCP に接続し `list_tools`
2. tool schemas を OpenAI 互換の tools に変換
3. LLM を呼ぶ
4. tool call があれば MCP `tools/call` を実行し messages に戻す
5. 最終テキスト回答になるまで繰り返す

Backlog tool は読み書きとも原則すべて許可する（sandbox）。  
追加の write enable フラグは持たない。

## 6. v1 の What

### 成功条件

1. `cd v1 && docker compose up` 相当で `backlog-mcp` と `chat-v1` が起動する
2. Host 実装前に、MCP へ `initialize` / `list_tools` 相当のスモークが通る
3. `POST /chat` に messages を送ると最終回答が同期 JSON で返る
4. 「未完了課題を教えて」など、実 Backlog データに基づく回答が得られる
5. 履歴の永続化をしない。クライアントが毎回 messages を送る
6. DB を使わない
7. loguru とアクセスログ middleware がある（`LOG_FORMAT` で human / json を切替可能）
8. `v1/frontend` から同期 Chat を確認できる

### API

| メソッド | パス | 役割 |
|---|---|---|
| `POST` | `/chat` | 同期で tool loop し、最終回答を返す |
| `GET` | `/health` | Compose / 接続確認用（あってよい） |

**`POST /chat` リクエスト（論理）**

- `messages`: role / content 等を含む配列（クライアントが履歴を保持して送る）

**`POST /chat` レスポンス（論理）**

- `message`: 最終 assistant メッセージ
- `messages`: loop 後の全 messages（次ターン用にクライアントが保持しやすい形）

SSE は持たない。セッション API は持たない。

### フロント（`v1/frontend`）

- メッセージ一覧と入力欄
- 履歴はブラウザ状態（必要なら localStorage）
- `POST /chat` は axios。SWR は health 等の再取得向け
- ローカル `pnpm dev`。API base URL は環境変数または proxy

### v1 に含めないもの

- セッション ID、PostgreSQL、監査ログテーブル
- SSE
- 認証
- timeout / 回数上限 / エラー code の厳密な契約固定（骨格は揃えるが、本番契約の本丸は v2）

## 7. v2 の What

### 成功条件

1. `cd v2 && docker compose up` 相当で `backlog-mcp`、`postgres`、`chat-v2` が起動する（`v2/compose.yaml`。v1 と非共有）
2. サーバー側で会話セッションを作成・継続できる
3. messages 一式を PostgreSQL に永続化し、再起動後も再開できる
4. Chat 応答は **SSE のみ**（同期 JSON の Chat エンドポイントは持たない）
5. SSE で最終回答チャンクと tool 経過（started / completed / failed）を流す
6. LLM / MCP に timeout を設ける
7. tool 呼び出し回数に上限を設ける
8. `/health` で生死が分かる
9. loguru が `LOG_FORMAT` に応じて human / json を出し、アクセスログ middleware がある
10. 書き込み系 tool 呼び出しを監査ログに残す（秘密らしき値はマスク）
11. 認証は実装しないが、middleware / dependency の差し込み点がある
12. `v1` とコード・Compose を共有しない
13. `v2/frontend` から SSE を確認できる

### API

| メソッド | パス | 役割 |
|---|---|---|
| `POST` | `/sessions` | セッション作成 → `session_id` |
| `POST` | `/sessions/{id}/messages` | 発言。SSE で回答と tool 経過を流す |
| `GET` | `/sessions/{id}/messages` | 永続化 messages の取得 |
| `GET` | `/health` | ヘルスチェック（必須） |

`POST /chat`（create-or-continue 用）は **置かない**。  
未作成時のセッション作成は `v2/frontend` が `POST /sessions` してから発言する。

セッション API の範囲は最小とする。一覧、削除、メッセージ編集は持たない。

**リクエスト / レスポンス（論理）**

- `POST /sessions` レスポンス: `{ "id": "<uuid>" }`
- `POST /sessions/{id}/messages` リクエスト: `{ "content": "<user text>" }`（本文のみ。履歴はサーバー側）
- `GET /sessions/{id}/messages` レスポンス: `{ "messages": [ ... ] }`（永続化一式）

### SSE イベント（論理名）

| イベント | 内容 |
|---|---|
| `session` | 使用中の `session_id` |
| `tool_call.started` | tool 開始 |
| `tool_call.completed` | tool 成功 |
| `tool_call.failed` | tool 失敗 |
| `message.delta` | 最終回答のチャンク |
| `message.completed` | 最終 assistant メッセージ確定 |
| `error` | ループ失敗 |
| `done` | ストリーム終了 |

LLM の中間 raw 状態は SSE に出さない。loguru に出す。

### フロント（`v2/frontend`）

- セッション作成（起動時自動作成可）→ 発言 → 履歴表示
- `POST /sessions` と `GET /sessions/{id}/messages` は axios + SWR
- 発言の SSE は `fetch` ストリーム（または同等）。axios は使わない
- UI は最終回答ストリームと tool 経過を表示する
- ローカル `pnpm dev`

## 8. データモデル（v2）

### 原則

- 永続化するのは、次の LLM 呼び出しに渡せる **messages 一式** である
- SSE 経過イベントは永続化しない
- 書き込み系 tool は監査ログ必須

### `sessions`

- `id`（UUID）
- `created_at` / `updated_at`

認証導入後に足す想定の `created_by` 等は、今はカラムを持たない。

### `messages`

- `id`
- `session_id`
- `ordinal`（セッション内順序）
- `role`（`user` / `assistant` / `tool` など、OpenAI 互換に寄せる）
- `content`（テキスト。無い場合は null）
- `tool_call_id` / `tool_calls`（JSON。紐付け用）
- `created_at`

### 保存タイミング

- user 行は loop 開始前に DB へ入れる
- assistant / tool 行は loop 成功後にまとめて保存する
- `error` や `max_tool_calls` で終わった場合は、途中の tool 状態だけを残さない

### `tool_audit_logs`

- `id`
- `session_id` / `request_id`
- `tool_name`
- `arguments_json`（マスク済み）
- `result_json`（マスク済み。失敗時はエラー要約可）
- `status`（`ok` / `error`）
- `started_at` / `finished_at`
- `created_at`

**書き込み判定**: Host 内に「書き込み系 tool 名」の集合を設定として持つ。  
公式 Backlog MCP の更新系 tool 名を初期登録し、一致したものだけ監査必須とする。  
読み取り tool の監査は任意であり、成功条件には含めない。

**マスク**: API key、Bearer トークン、パスワードらしき文字列を赤くする。  
課題本文など一般コンテンツは、sandbox 前提でマスク対象にしない。

## 9. エラーと制限

### エラー応答の骨格（v1 / v2 共通）

```json
{
  "error": {
    "code": "mcp_timeout",
    "message": "human readable",
    "retryable": true,
    "details": {}
  }
}
```

SSE 時は同等の内容を `error` イベントで送り、その後 `done` を送る。  
途中で `message.delta` が出ていても、`error` で終わった場合は完了扱いしない。

### 初期 `code`

| code | 意味 | retryable 目安 |
|---|---|---|
| `llm_timeout` | LLM 応答待ち超過 | true |
| `llm_error` | LLM 側障害・不正応答 | 状況依存 |
| `mcp_timeout` | MCP 呼び出し超過 | true |
| `mcp_error` | MCP / Backlog 側失敗 | 状況依存 |
| `max_tool_calls` | tool 回数上限 | false |
| `session_not_found` | 不明な session（v2） | false |
| `validation_error` | リクエスト不正 | false |
| `internal_error` | その他 | false |

### 制限のデフォルト（v2。設定で変更可）

| 項目 | デフォルト |
|---|---|
| LLM timeout | 60 秒 |
| MCP `tools/call` timeout | 30 秒 |
| 1 リクエストあたりの tool 呼び出し上限 | 10 回 |

v1 は同等の防御を簡易に入れてもよいが、契約としての固定は v2 の成功条件とする。

## 10. ログと観測

### アプリログ

- ライブラリは **loguru**
- `LOG_FORMAT=human|json` で切替
  - `human`: ローカル可読性優先
  - `json`: request_id / session_id 等を含む structured

### アクセスログ

- FastAPI / Starlette の **middleware** で実装する（v1 / v2 とも）
- リクエストごとに `request_id` を採番（受信ヘッダがあれば継承してよい）
- 応答後に method / path / status / duration_ms / request_id を記録
- v2 では取れる範囲で `session_id` も付与
- 出力は loguru 経由とし、`LOG_FORMAT` に従う

アプリログとアクセスログは `request_id` で相関できるようにする。

### ヘルスチェック

- v2 は `/health` 必須
- v1 も付けてよい
- 応答はプロセス生存が分かれば足りる。依存（MCP / DB）の深掘りは必須にしない

### 認証差し込み点（v2）

- middleware または dependency を置ける位置を空ける
- 現状は無認証で全 API オープン（sandbox）
- 完成判定に認証は含めない

## 11. Compose と環境変数

### 各版の `compose.yaml`

| 版 | パス | サービス |
|---|---|---|
| v1 | `v1/compose.yaml` | `backlog-mcp`, `chat-v1`（`build: ./backend`） |
| v2 | `v2/compose.yaml` | `backlog-mcp`, `postgres`, `chat-v2`（`build: ./backend`） |

- 起動は版ディレクトリで行う（例: `cd v1 && docker compose up`）
- frontend は載せない
- MCP は各版の Compose がそれぞれ持つ（v1 と v2 で共有しない）
- MCP は Compose 内部ネットワークに閉じる。Host からの URL 例: `http://backlog-mcp:3333/mcp`

### 環境変数（名前のみ。値はドキュメントに書かない）

| 名前 | 用途 |
|---|---|
| `BACKLOG_DOMAIN` | Backlog スペース |
| `BACKLOG_API_KEY` | Backlog API |
| `OPENCODE_GO_API_KEY` | LLM |
| `OPENCODE_GO_BASE_URL` | デフォルトあり |
| `OPENCODE_GO_MODEL` | デフォルト `deepseek-v4-flash` |
| `MCP_SERVER_URL` | Host → MCP |
| `LOG_FORMAT` | `human` \| `json` |
| `DATABASE_URL` | v2 のみ |
| `POSTGRES_PASSWORD` | v2 のみ |
| `LLM_TIMEOUT_SECONDS`、`MCP_TIMEOUT_SECONDS`、`MAX_TOOL_CALLS` | v2 必須設定として持つ |

秘密情報はリポジトリ直下の `.envrc` を direnv で読み込む想定とする。  
版ごとの `.env` は必須にしない。Compose は起動シェルに載った環境変数を参照する。  
ガイド、design doc、コミット、Issue、PR に秘密の値を書かない。

## 12. テスト方針

### v1

- Host の tool loop を、LLM / MCP をモックして単位テストする
- 「tool call → 結果反映 → 最終回答」の経路がメッセージ配列上で正しいことを検証する
- 可能なら Compose 起動後の手動確認（実 Backlog）を README に手順として残す

### v2

- v1 相当の loop テストに加え、セッション永続化（保存 → 再読込 → 継続）をテストする
- timeout / max iterations が期待の `error.code` になることをテストする
- 書き込み tool 名に対して監査ログ行が増えることをテストする
- SSE は、イベント種別の最低限（completed / error / done）をテストクライアントで検証する

E2E のブラウザ自動テストは必須にしない。検証 FE は人手確認でよい。

## 13. 明示的非目標（再掲）

- リポジトリ直下の共通 `compose.yaml`
- v1 と v2 の共通ライブラリ化
- 認証実装（将来。差し込み点のみ）
- SSE 経過イベントの DB 保存
- セッション一覧 / 削除 / メッセージ編集 API
- v2 の同期 JSON Chat
- FE の Compose 常駐
- MCP 自作、エージェントフレームワークへの委譲
- Redis 等の高度 cache、Kubernetes、HITL 承認 UI

## 14. 実装への落とし込み（概位）

手順の本文は `docs/guide/` に書く。  
版に依らない原理は `index.html` に置き、`v1.html` と `v2.html` はその版の手順だけを持つ。  
v2.html は v1 を終えていることを前提にし、tool loop を説明し直さない。

ガイドは学習対象になるコード（`run_tool_loop`、`stream_turn`）を渡さず、  
不変条件と、読者が自分で通せるテストを置く。SDK を捌くだけの雑務コードは全文を渡す。

順序の意図だけ示す。

1. `v1/compose.yaml` + 公式 Backlog MCP（HTTP）
2. `v1/backend` の手動 loop を **CLI から** 動かす
3. 同じ loop を FastAPI の同期 `/chat` で包む（アクセスログ / loguru）
4. `v1/frontend` で同期確認
5. `v2/compose.yaml` + `v2/backend` のセッション + PostgreSQL + SSE + 監査 + 制限 + health（v1 とは非共有）
6. `v2/frontend` で SSE 確認

## 15. 前合意からの変更点

引き継ぎ資料（2026-08-07）からの主な更新は次である。

- 認証は実装せず、v2 に差し込み点のみ（成功条件から外す）
- 検証用 FE を `v1/frontend` / `v2/frontend` に追加（pnpm + React + axios + SWR）
- v1 は同期 JSON のみ、v2 は SSE のみ（同期 Chat を置かない）
- v2 の create-or-continue 用 `POST /chat` は置かない（FE が create → messages）
- ログは loguru。`LOG_FORMAT` で human / json。アクセスログは middleware（両版）
- Compose は各版直下（`v1/compose.yaml` / `v2/compose.yaml`）。リポジトリ直下の共通 Compose は置かない
- API コードは各版の `backend/` 配下
- FE は Compose に載せずローカル `pnpm dev`
- v1 の学習順を CLI → FastAPI → FE の三段にした（案 A）
- 秘密情報は既存の直下 `.envrc` + direnv を使い、版ごとの `.env` は必須にしない
