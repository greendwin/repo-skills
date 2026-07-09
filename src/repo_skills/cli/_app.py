from __future__ import annotations

from importlib.metadata import version

import typer
from cli_error import CliExit
from typer_di import TyperDI

from repo_skills.console import reporter

app = TyperDI(
    help="Manage agent skills.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    if value:
        ver = version("repo-skills")
        raise CliExit("[bold]repo-skills[/bold] [id]{ver}[/id]", ver=ver)


@app.callback()
def _main_callback(
    debug: bool = typer.Option(False, help="Show full traceback on errors."),
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    reporter.debug = debug
