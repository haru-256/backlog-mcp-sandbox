"""ユーザーが書いたスペース名を、接続一覧のキーに揃える。"""

from urllib.parse import urlparse


def normalize_space_domain(raw: str) -> str:
    """`acme` / `acme.backlog.com` / `https://acme.backlog.jp/` をホスト名にする。

    Args:
        raw: フォームや tool 引数の生の値。

    Returns:
        小文字のホスト名。ドットが無ければ `.backlog.com` を足す。

    Raises:
        ValueError: 空、またはホストが取れない場合。
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
    """接続済み一覧から、list_issues が使うスペースを一つ選ぶ。

    Args:
        connected: そのユーザーが OAuth 済みの domain。
        requested: tool 引数の space。省略時は None。

    Returns:
        使う domain。次は None。
        - requested があるが connected に無い
        - requested が無く、connected が 0 件または 2 件以上

    Raises:
        ValueError: requested が空文字など、正規化できない場合。
    """
    if requested:
        domain = normalize_space_domain(requested)
        if domain in connected:
            return domain
        return None
    if len(connected) == 1:
        return connected[0]
    return None
