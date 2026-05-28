from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from rich.console import Console
from rich.markup import escape

from repo_skills.utils import fmt_message

_print_callstack = False


def set_print_callstack(value: bool) -> None:
    global _print_callstack
    _print_callstack = value


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


class NoopError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@contextmanager
def error_handler(console: Console) -> Generator[None]:
    try:
        yield
    except NoopError as ex:
        console.print(ex.message)
        raise SystemExit(0)
    except AppError as ex:
        if _print_callstack:
            console.print_exception()
            raise SystemExit(1)

        console.print(f"[red]Error:[/red] {ex.message}")
        raise SystemExit(1)
    except Exception as ex:
        if _print_callstack:
            console.print_exception()
            raise SystemExit(1)

        console.print(f"[red]Error:[/red] {escape(str(ex))}")
        cause = ex.__cause__ or ex.__context__
        while cause:
            console.print(f"  caused by: {escape(str(cause))}")
            cause = cause.__cause__ or cause.__context__
        raise SystemExit(1)
