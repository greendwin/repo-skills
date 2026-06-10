from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from rich.markup import escape

from .console import console, fmt_message


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        hint: str = "",
        props: dict[str, str] | None = None,
    ) -> None:
        self.message = fmt_message(message, hint=hint, props=props)
        super().__init__(self.message)


class FileNotInCommitError(AppError):
    def __init__(self, commit: str, path: str) -> None:
        self.commit = commit
        self.path = path
        super().__init__(
            "File not found at commit",
            props={"commit": commit, "path": path},
        )


class ConfigBrokenError(AppError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            "Broken config file",
            props={"path": str(path)},
        )


class NoopError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def render_error(ex: Exception) -> None:
    console.debug_traceback()

    if isinstance(ex, AppError):
        rich_text = ex.message
    else:
        rich_text = escape(str(ex))

    console.print(f"[red]Error:[/red] {rich_text}")

    seen = {id(ex)}
    cause = ex.__cause__ or ex.__context__
    while cause is not None and id(cause) not in seen:
        console.print(f"  caused by: {escape(str(cause))}")
        seen.add(id(cause))
        cause = cause.__cause__ or cause.__context__


@contextmanager
def error_handler() -> Generator[None]:
    try:
        yield
    except NoopError as ex:
        console.print(ex.message)
        raise SystemExit(0)
    except Exception as ex:
        render_error(ex)
        raise SystemExit(1)
