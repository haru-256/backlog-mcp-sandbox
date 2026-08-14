"""ユーザーが書いたスペース名を、接続のキーに揃える。"""

from urllib.parse import urlparse


def normalize_space_domain(raw: str) -> str:
    """`acme` / `acme.backlog.com` / `https://acme.backlog.jp/` をホスト名にする。

    Args:
        raw: フォームの生の値。

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
