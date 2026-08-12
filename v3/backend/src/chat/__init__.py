import typer

from .cli import run


def main() -> None:
    """パッケージ入口。typer で `run` を CLI にする。

    Returns:
        なし。

    Raises:
        SystemExit: typer が引数エラーで終了する場合。
    """
    typer.run(run)
