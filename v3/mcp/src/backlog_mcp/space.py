from urllib.parse import urlparse


def normalize_space_domain(raw: str) -> str:
    """ユーザー入力を Backlog のホスト名に正規化する。

    `acme` / `acme.backlog.com` / `https://acme.backlog.jp/` を受け付ける。
    """
    text = raw.strip()
    if not text:
        raise ValueError("space is required")

    if "://" not in text:
        text = f"https://{text}"
    parsed = urlparse(text)
    host = (parsed.netloc or parsed.path).split("/")[0].lower()
    if not host:
        raise ValueError("space is required")
    if "." not in host:
        host = f"{host}.backlog.com"
    return host


def resolve_space(connected: list[str], requested: str | None) -> str | None:
    """list_issues の space 引数を、接続済み一覧から解決する。

    Returns:
        使う domain。未接続・複数で省略・未所持は None。
        呼び出し側が connected の長さを見てメッセージを分ける。
    """
    if requested:
        domain = normalize_space_domain(requested)
        if domain in connected:
            return domain
        return None
    if len(connected) == 1:
        return connected[0]
    return None
