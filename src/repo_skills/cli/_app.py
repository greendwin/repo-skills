from __future__ import annotations

from typer_di import TyperDI

app = TyperDI(
    help="Manage Claude Code skills.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
