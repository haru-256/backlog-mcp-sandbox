import typer

from .cli import run


def main() -> None:
    typer.run(run)
