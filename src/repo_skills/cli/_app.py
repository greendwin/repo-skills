from __future__ import annotations

import typer
from typer_di import TyperDI

from repo_skills.errors import set_print_callstack

app = TyperDI(
    help="Manage agent skills.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


@app.callback()
def _main_callback(
    debug: bool = typer.Option(False, help="Show full traceback on errors."),
) -> None:
    set_print_callstack(debug)
