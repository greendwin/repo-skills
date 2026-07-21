from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from cli_error import CliReporter, make_console, render_template


class Reporter(CliReporter):
    """CliReporter + in-place progress lines (running/finish + pending-eoln)."""

    def __init__(self) -> None:
        # console_err defaults to derive_stderr_console(console)
        # honor NO_COLOR (presence-based, matching Rich's native fallback)
        super().__init__(make_console(no_color="NO_COLOR" in os.environ))
        self._pending_eoln = False
        self._active_prefix: str | None = None

    @property
    def no_color(self) -> bool:
        return bool(self.console.no_color)

    @no_color.setter
    def no_color(self, value: bool) -> None:
        self.console.no_color = value
        self.console_err.no_color = value

    def print(self, template: str, /, *, end: str = "\n", **args: object) -> None:
        self._finish_eoln()
        super().print(template, end=end, **args)

    def warn(self, template: str, /, **args: object) -> None:
        self.print(render_template("[warn]Warning[/warn]: " + template, **args))

    @contextmanager
    def running(
        self, prefix: str, /, *, tty_subprocess: bool = False, **args: object
    ) -> Generator[None]:
        prefix = render_template(prefix, **args)

        if self._active_prefix is not None:
            raise AssertionError(
                f"running({prefix!r}) cannot nest inside"
                f" running({self._active_prefix!r})"
            )

        self._finish_eoln()
        # pre-formatted markup, no {} → template passthrough
        super().print(f"{prefix} ... ", end="")
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

    def finish(self, suffix: str, /, **args: object) -> None:
        suffix = render_template(suffix, **args)

        if self._pending_eoln:
            super().print(suffix)
            self._pending_eoln = False
            return

        prefix = self._active_prefix or ""
        super().print(f"{prefix} ... {suffix}")

    def _finish_eoln(self) -> None:
        if self._pending_eoln:
            super().print("")
            self._pending_eoln = False


# global instance
reporter = Reporter()
