from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo_skills.console import console
from repo_skills.errors import AppError
from repo_skills.git_real import RealGitRepo


@pytest.fixture(autouse=True)
def _reset_debug() -> None:
    console.debug = False


class TestDebugFlag:
    def test_disabled_by_default(self) -> None:
        assert console.debug is False

    def test_enable(self) -> None:
        console.debug = True
        assert console.debug is True

    def test_disable_after_enable(self) -> None:
        console.debug = True
        console.debug = False
        assert console.debug is False


class TestDebugCmd:
    def test_prints_command_when_enabled(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        console.debug = True
        console.debug_cmd(["git", "status"], Path("/repo"))
        captured = capsys.readouterr()
        assert "COMMAND: git status" in captured.err
        assert "cwd: /repo" in captured.err

    def test_silent_when_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        console.debug_cmd(["git", "status"], Path("/repo"))
        captured = capsys.readouterr()
        assert captured.err == ""


class TestDebugOutput:
    def test_prints_stdout_when_enabled(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        console.debug = True
        console.debug_output("main\ndev", "")
        captured = capsys.readouterr()
        assert "stdout: main" in captured.err
        assert "stdout: dev" in captured.err

    def test_prints_stderr_when_enabled(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        console.debug = True
        console.debug_output("", "warning: something")
        captured = capsys.readouterr()
        assert "stderr: warning: something" in captured.err

    def test_silent_when_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        console.debug_output("output", "error")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_skips_empty_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        console.debug = True
        console.debug_output("", "")
        captured = capsys.readouterr()
        assert captured.err == ""


class TestRunningTtySubprocess:
    def test_terminates_pending_running_line_up_front(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        console.no_color = True
        # tty_subprocess=True flushes the in-place "... " line up front, so a
        # subprocess writing to the tty cannot clobber it. Because the
        # pending-eoln state is already cleared, finish() cannot complete the
        # original line in-place; it pops the prefix stack and replays the whole
        # "<prefix> ... done" line instead.
        with console.running("Pulling x", tty_subprocess=True):
            console.finish("done")

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        # Trailing space is load-bearing: it proves the in-place status line was
        # flushed verbatim and un-clobbered. Do not rstrip/strip it.
        assert "Pulling x ... " in lines
        assert "Pulling x ... done" in lines

    def test_rejects_nested_running(self) -> None:
        # finish() replays a single active prefix, so nesting would corrupt the
        # status line; nesting is asserted against rather than silently mishandled.
        with console.running("outer"):
            with pytest.raises(AssertionError):
                with console.running("inner"):
                    pass


class TestGitRealDebugIntegration:
    def test_run_prints_debug_when_enabled(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        subprocess.run(
            ["git", "init", str(tmp_path)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        console.debug = True
        git = RealGitRepo(tmp_path)
        git.current_branch()
        captured = capsys.readouterr()
        assert "COMMAND: git branch --show-current" in captured.err
        assert "stdout: main" in captured.err

    def test_run_silent_when_disabled(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        subprocess.run(
            ["git", "init", str(tmp_path)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        git = RealGitRepo(tmp_path)
        git.current_branch()
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_run_shows_stderr_on_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        subprocess.run(
            ["git", "init", str(tmp_path)],
            capture_output=True,
            check=True,
        )

        console.debug = True
        git = RealGitRepo(tmp_path)
        with pytest.raises(AppError):
            git._run("log", "--bad-flag")
        captured = capsys.readouterr()
        assert "COMMAND: git log --bad-flag" in captured.err
