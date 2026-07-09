from __future__ import annotations

import pytest

from repo_skills.console import Reporter, reporter


@pytest.fixture(autouse=True)
def _reset() -> None:
    reporter.debug = False
    reporter.console.no_color = True


class TestProgress:
    def test_finish_completes_pending_line_in_place(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with reporter.running("Pulling x"):
            reporter.finish("done")

        lines = capsys.readouterr().out.splitlines()
        assert "Pulling x ... done" in lines

    def test_tty_subprocess_flushes_line_up_front(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # tty_subprocess=True flushes the in-place "... " line up front, so a
        # subprocess writing to the tty cannot clobber it. Because the
        # pending-eoln state is already cleared, finish() cannot complete the
        # original line in-place; it pops the prefix stack and replays the whole
        # "<prefix> ... done" line instead.
        with reporter.running("Pulling x", tty_subprocess=True):
            reporter.finish("done")

        lines = capsys.readouterr().out.splitlines()
        # Trailing space is load-bearing: it proves the in-place status line was
        # flushed verbatim and un-clobbered. Do not rstrip/strip it.
        assert "Pulling x ... " in lines
        assert "Pulling x ... done" in lines

    def test_rejects_nested_running(self) -> None:
        # finish() replays a single active prefix, so nesting would corrupt the
        # status line; nesting is asserted against rather than silently mishandled.
        with reporter.running("outer"):
            with pytest.raises(AssertionError):
                with reporter.running("inner"):
                    pass


class TestPrintFlushesEoln:
    def test_print_flushes_pending_eoln_first(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with reporter.running("Pulling x"):
            reporter.print("interrupt")

        out = capsys.readouterr().out
        lines = out.splitlines()
        # eoln flushed before the print so "interrupt" is on its own line
        assert "interrupt" in lines
        assert lines.index("interrupt") > lines.index("Pulling x ... ")


class TestDebugAttr:
    def test_mutable_and_default_false(self) -> None:
        assert reporter.debug is False
        reporter.debug = True
        assert reporter.debug is True

    def test_disable_after_enable(self) -> None:
        reporter.debug = True
        reporter.debug = False
        assert reporter.debug is False


class TestNoColorEnv:
    # env read at construction → build fresh Reporter, not the module singleton

    def test_no_color_env_set_disables_color(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        assert Reporter().console.no_color is True

    def test_no_color_env_unset_keeps_color(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)
        assert Reporter().console.no_color is False
