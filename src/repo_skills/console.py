from __future__ import annotations

import shlex
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console as RichConsole
from rich.markup import escape


class Console:
    debug = False

    def __init__(self) -> None:
        self._con = RichConsole(highlight=False)
        self._con_err = RichConsole(highlight=False, stderr=True)
        self._pending_eoln = False
        self._active_prefix: str | None = None

    def print(self, message: str) -> None:
        self._finish_eoln()
        self._con.print(message)

    def debug_traceback(self) -> None:
        if not self.debug:
            return

        self._finish_eoln()
        self._con_err.print_exception()

    def debug_cmd(self, cmd: list[str], cwd: Path) -> None:
        if not self.debug:
            return

        self._finish_eoln()

        joined = shlex.join(cmd)
        self._con_err.print(f"[dim]COMMAND: {escape(joined)}[/dim]")
        self._con_err.print(f"[dim]  cwd: {escape(str(cwd))}[/dim]")

    def debug_output(self, stdout: str, stderr: str) -> None:
        if not self.debug:
            return

        self._finish_eoln()

        if stdout:
            for line in stdout.splitlines():
                self._con_err.print(f"[dim]  stdout: {escape(line)}[/dim]")
        if stderr:
            for line in stderr.splitlines():
                self._con_err.print(f"[dim]  stderr: {escape(line)}[/dim]")

    @contextmanager
    def running(self, prefix: str, *, tty_subprocess: bool = False) -> Generator[None]:
        if self._active_prefix is not None:
            raise AssertionError(
                f"running({prefix!r}) cannot nest inside"
                f" running({self._active_prefix!r})"
            )

        self._finish_eoln()
        self._con.print(f"{prefix} ... ", end="")
        self._pending_eoln = True

        self._active_prefix = prefix

        if tty_subprocess:
            self._finish_eoln()

        try:
            yield
        except Exception:
            self._finish_eoln()
            raise
        finally:
            self._active_prefix = None

    def finish(self, suffix: str) -> None:
        if self._pending_eoln:
            self._con.print(suffix)
            self._pending_eoln = False
            return

        prefix = self._active_prefix or ""
        self._con.print(f"{prefix} ... {suffix}")

    @property
    def no_color(self) -> bool:
        return self._con.no_color

    @no_color.setter
    def no_color(self, value: bool) -> None:
        self._con.no_color = value
        self._con_err.no_color = value

    def _finish_eoln(self) -> None:
        if self._pending_eoln:
            self._con.print()
            self._pending_eoln = False


def fmt_ident(text: str) -> str:
    return f"[green]{escape(text)}[/green]"


def fmt_path(path: Path | str) -> str:
    return f"[dim]{escape(str(path))}[/dim]"


def fmt_data(text: str | int | Path | list[str]) -> str:
    if isinstance(text, list):
        return ", ".join(fmt_data(p) for p in sorted(text))

    return f"[cyan]{escape(str(text))}[/cyan]"


def fmt_command(text: str) -> str:
    return f"[blue]{escape(text)}[/blue]"


def fmt_message(
    message: str,
    *,
    hint: str = "",
    props: dict[str, str] | None = None,
) -> str:
    r = message
    if props:
        for k, v in props.items():
            if k:
                r += f"\n  {k}: {v}"
            else:
                # support little hack for data without key
                r += f"\n{v.rstrip()}"
    if hint:
        r += f"\n\n{hint}"
    return r


# global instance
console = Console()
