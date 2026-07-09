from __future__ import annotations

from repo_skills.cli import app
from repo_skills.console import reporter


def main() -> None:
    with reporter.handler():
        app()
