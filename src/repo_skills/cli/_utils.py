from __future__ import annotations

from rich.console import Console

console = Console()


def echo(message: str) -> None:
    console.print(message)
