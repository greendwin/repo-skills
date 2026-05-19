from __future__ import annotations

from rich.console import Console

from repo_skills.cli import app
from repo_skills.errors import error_handler


def main() -> None:
    with error_handler(Console()):
        app()
