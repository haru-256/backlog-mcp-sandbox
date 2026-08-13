"""接続画面の HTML。OAuth の手順は `connect.py` を読む。"""

from html import escape

from starlette.responses import HTMLResponse

CONNECT_FORM = """<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>Backlog を接続</title></head>
<body>
  <h1>Backlog を接続</h1>
  <p>Chat のテナント <code>{org}</code> / ユーザー <code>{user}</code> に、Backlog スペースを追加します。</p>
  {error}
  <form method="post" action="/connect">
    <input type="hidden" name="state" value="{state}">
    <p>
      <label>スペース<br>
        <input name="space" size="40" placeholder="acme.backlog.com" required>
      </label>
    </p>
    <p>未登録のスペースでは、そのスペースに作った OAuth アプリの値も入力してください。</p>
    <p>
      <label>Client ID（未登録時のみ必須）<br>
        <input name="client_id" size="40">
      </label>
    </p>
    <p>
      <label>Client Secret（未登録時のみ必須）<br>
        <input name="client_secret" size="40" type="password">
      </label>
    </p>
    <button type="submit">Backlog で認可する</button>
  </form>
</body>
</html>
"""


def connect_form(org: str, user: str, state: str, error: str | None = None) -> HTMLResponse:
    """スペース入力フォーム。エラー時は 400 で同じ画面を返す。

    Args:
        org: Chat テナント ID。画面に表示する。
        user: Chat ユーザー ID。画面に表示する。
        state: 次の POST に載せる connect JWT。
        error: あればアラートとして出す。

    Returns:
        フォーム HTML。error があれば status 400。
    """
    error_html = f'<p role="alert">{escape(error)}</p>' if error else ""
    body = CONNECT_FORM.format(
        org=escape(org),
        user=escape(user),
        state=escape(state),
        error=error_html,
    )
    return HTMLResponse(body, status_code=400 if error else 200)


def error_page(message: str, status: int = 400) -> HTMLResponse:
    """フォームに戻せないときの短いエラー。

    Args:
        message: 画面に出す文。
        status: HTTP status。既定は 400。

    Returns:
        一文だけの HTML。
    """
    return HTMLResponse(
        f"<!doctype html><html lang='ja'><body><p>{escape(message)}</p></body></html>",
        status_code=status,
    )
